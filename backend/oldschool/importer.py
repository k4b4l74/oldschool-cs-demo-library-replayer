"""Import demo files and archives into the library.

Pipeline (docs/ARCHITECTURE.md §7), per file:

1. hash the file; skip it if the same file was already imported;
2. keep it: ``referenced`` (left where it is, path recorded), ``copied`` or
   ``moved`` into ``store/originals``;
3. walk the archive (nested up to 3 levels) and record every member;
4. store each ``.dem`` once in the content-addressed store;
5. parse it: header, players, sides, kill feed, scores, chat, rounds;
6. identify release, year estimate, teams, line-ups and POV, and group
   the demos into matches (``identify.propose``);
7. write everything in one transaction.

Steps 1-6 run in worker processes (``inspect_file``); only the main process
writes to the database, so SQLite sees a single writer.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import struct
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from oldschool import archives, identify, store
from oldschool.parser import goldsrc as gd

PARSE_VERSION = 1
IMPORT_EXT = archives.ARCHIVE_EXT | {".dem"}
MODES = ("referenced", "copied", "moved")


# ------------------------------------------------------------------ worker


def inspect_file(
    path: Path, label: str, store_root: Path, mode: str, copy_demos: bool = True, database: str | None = None
) -> dict:
    """Read one file (worker process). Returns plain data, no demo bytes.

    With ``copy_demos`` False the demos are not copied into the store: the
    app reads them from this file when they are played (``sources.py``).
    Meant for a library that stays where it is.

    With ``database``, a file whose content is already in the library is
    not read further: ``{"already": original_id, ...}``."""
    rec: dict = {
        "path": label,
        "source": str(path),
        "file_name": path.name,
        "size": path.stat().st_size,
        "sha1": store.file_sha1(path),
        "members": [],
        "demos": [],
        "errors": [],
        "demo_copies": copy_demos,
    }
    if database:
        hit = _known_original(database, rec["sha1"])
        if hit is not None:
            return {**rec, "already": hit}
    for m in archives.iter_members(path, errors=rec["errors"]):
        member = "/".join(m["chain"] + (m["name"],))
        ext = archives._ext(m["name"])
        entry = {
            "chain": "/".join(m["chain"]),
            "name": m["name"],
            "size": m["size"],
            "mtime": archives._iso(m["mtime"]),
            "mtime_basis": m["mtime_basis"],
            "demo_sha1": None,
            "text": None,
        }
        rec["members"].append(entry)
        if ext == ".dem":
            if m["size"] and m["size"] > archives.MAX_DEMO_BYTES:
                rec["errors"].append(f"{member}: demo larger than {archives.MAX_DEMO_BYTES} bytes skipped")
                continue
            try:
                data = m["read"]()
            except Exception as exc:
                rec["errors"].append(f"{member}: read failed: {type(exc).__name__}: {exc}")
                continue
            if copy_demos:
                sha1, _p, _new = store.put_demo(store_root, data)
            else:
                sha1 = hashlib.sha1(data).hexdigest()
            entry["demo_sha1"] = sha1
            rec["demos"].append(_parse_demo(data, sha1, member, entry))
        elif ext in archives.TEXT_EXT and m["size"] and m["size"] <= archives.MAX_TEXT_BYTES:
            try:
                entry["text"] = archives._decode_text(m["read"]())
            except Exception:
                pass
    good = [d for d in rec["demos"] if "error" not in d]
    rec["proposal"] = identify.propose(rec) if rec["demos"] else {"status": "no-demo"}
    rec["parsed"] = len(good)
    if mode in ("copied", "moved"):
        kept = store_root / "originals" / rec["sha1"][:2] / (rec["sha1"] + _suffix(path))
        kept.parent.mkdir(parents=True, exist_ok=True)
        if not kept.exists():
            shutil.copy2(path, kept)
        rec["kept_path"] = str(kept)
    return rec


_READERS: dict[str, sqlite3.Connection] = {}


def _known_original(database: str, sha1: str) -> int | None:
    """Read-only lookup from a worker process (one connection per process)."""
    db = _READERS.get(database)
    if db is None:
        db = _READERS[database] = sqlite3.connect(f"{Path(database).as_uri()}?mode=ro", uri=True, timeout=30)
    row = db.execute("SELECT id FROM originals WHERE sha1 = ?", (sha1,)).fetchone()
    return row[0] if row else None


def _suffix(path: Path) -> str:
    name = path.name.lower()
    for double in (".tar.gz", ".tar.bz2", ".tar.xz"):
        if name.endswith(double):
            return double
    return path.suffix.lower()


def _parse_demo(data: bytes, sha1: str, member: str, entry: dict) -> dict:
    demo = {
        "member": member,
        "size": len(data),
        "sha1": sha1,
        "mtime": entry["mtime"],
        "mtime_basis": entry["mtime_basis"],
    }
    try:
        a = gd.analyse(data, keep_kills=True, keep_chat=10_000)
        demo.update(a)
        demo["version"] = identify.guess_version(demo)
        demo["rounds"] = gd.rounds(data, a)
        demo["viewport"] = _viewport(data, a)
    except gd.DemoError as exc:
        demo["error"] = str(exc)
    except Exception as exc:  # a parser bug must not stop the import
        demo["error"] = f"parser failure: {type(exc).__name__}: {exc}"
    demo.pop("kills", None)  # the time-aware feed in demo["rounds"] replaces it
    return demo


def _viewport(data: bytes, a: dict) -> tuple[int, int] | None:
    """Largest recorded 3D view size (CS 1.3/1.4 engines need it at playback)."""
    best = None
    header = a["header"]
    directory = gd.read_directory(data, header["directory_offset"]) or []
    spans = [(e["offset"], e["offset"] + e["length"], e["description"]) for e in directory]
    if not spans:
        return None
    prefix = gd.detect_prefix(data, spans)
    at = 4 + 208  # ref_params.viewport[4] inside the netmsg prefix
    for start, end, _label in spans:
        try:
            for ftype, _t, _n, off, _m in gd.iter_frames(data, start, end, prefix):
                if ftype in (0, 1):
                    _, _, w, h = struct.unpack_from("<4i", data, off + 9 + at)
                    if 0 < w <= 4096 and 0 < h <= 4096 and (best is None or w * h > best[0] * best[1]):
                        best = (w, h)
        except gd.DemoError:
            continue
    return best


# ------------------------------------------------------------------ writer


@dataclass
class Summary:
    files: int = 0
    imported: int = 0
    already: int = 0
    no_demo: int = 0
    failed: int = 0
    demos_new: int = 0
    demos_seen_before: int = 0
    demo_errors: int = 0
    matches: int = 0
    duplicate_groups: int = 0
    warnings: list[str] = field(default_factory=list)


class Writer:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.names: dict[tuple[str, str], int] = {}
        self.teams: dict[str, int] = {}

    def name_id(self, name: str, steamid: str | None = None) -> int:
        key = (name, steamid or "")
        hit = self.names.get(key)
        if hit is None:
            self.db.execute(
                "INSERT INTO player_names(name_as_printed, steamid) VALUES (?, ?) ON CONFLICT DO NOTHING", key
            )
            hit = self.db.execute(
                "SELECT id FROM player_names WHERE name_as_printed = ? AND steamid = ?", key
            ).fetchone()[0]
            self.names[key] = hit
        return hit

    def team_id(self, tag: str | None) -> int | None:
        if not tag:
            return None
        hit = self.teams.get(tag)
        if hit is None:
            row = self.db.execute("SELECT id FROM teams WHERE tag_as_printed = ?", (tag,)).fetchone()
            if row:
                hit = row[0]
            else:
                norm = "".join(ch for ch in tag.casefold() if ch.isalnum())
                hit = self.db.execute(
                    "INSERT INTO teams(tag_as_printed, norm_tag) VALUES (?, ?) RETURNING id", (tag, norm)
                ).fetchone()[0]
            self.teams[tag] = hit
        return hit

    def write(self, rec: dict, mode: str, summary: Summary) -> dict:
        """Add one inspected file. Returns {status, original_id, matches, demos_new}
        with status imported / already / no-demo."""
        db = self.db
        row = db.execute("SELECT id FROM originals WHERE sha1 = ?", (rec["sha1"],)).fetchone()
        if row:
            summary.already += 1
            return {"status": "already", "original_id": row[0], "matches": 0, "demos_new": 0}
        status = "done" if rec["demos"] else "no-demo"
        before = (summary.matches, summary.demos_new)
        db.execute("BEGIN")
        try:
            original_id = db.execute(
                "INSERT INTO originals(sha1, file_name, size, source_path, mode, kept_path, status, demo_count, errors,"
                " label, demo_copies, analysed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))"
                " RETURNING id",
                (
                    rec["sha1"],
                    rec["file_name"],
                    rec["size"],
                    rec["source"],
                    mode,
                    rec.get("kept_path"),
                    status,
                    len(rec["demos"]),
                    json.dumps(rec["errors"], ensure_ascii=False) if rec["errors"] else None,
                    rec["path"],
                    int(rec.get("demo_copies", True)),
                ),
            ).fetchone()[0]
            for d in rec["demos"]:
                if db.execute("SELECT 1 FROM demos WHERE sha1 = ?", (d["sha1"],)).fetchone():
                    summary.demos_seen_before += 1
                    continue
                self._write_demo(d, stored=rec.get("demo_copies", True))
                summary.demos_new += 1
                summary.demo_errors += "error" in d
            self._write_members_and_matches(original_id, rec, summary)
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        summary.imported += status == "done"
        summary.no_demo += status == "no-demo"
        return {
            "status": "imported" if status == "done" else "no-demo",
            "original_id": original_id,
            "matches": summary.matches - before[0],
            "demos_new": summary.demos_new - before[1],
        }

    def replace(self, original_id: int, rec: dict, summary: Summary) -> dict:
        """Re-analysis: rewrite everything read from one file already in the
        library (its members, its demos' data and its matches). Done in the
        order files were imported, the result equals a fresh import."""
        db = self.db
        status = "done" if rec["demos"] else "no-demo"
        before = summary.matches
        db.execute("BEGIN")
        try:
            db.execute("DELETE FROM matches WHERE original_id = ?", (original_id,))
            db.execute("DELETE FROM archive_members WHERE original_id = ?", (original_id,))
            db.execute(
                "UPDATE originals SET status = ?, demo_count = ?, errors = ?, label = ?,"
                " analysed_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
                (
                    status,
                    len(rec["demos"]),
                    json.dumps(rec["errors"], ensure_ascii=False) if rec["errors"] else None,
                    rec["path"],
                    original_id,
                ),
            )
            seen = set()
            for d in rec["demos"]:
                if d["sha1"] in seen:
                    continue
                seen.add(d["sha1"])
                self._write_demo(d, stored=rec.get("demo_copies", True), replace=True)
                summary.demos_new += 1
                summary.demo_errors += "error" in d
            self._write_members_and_matches(original_id, rec, summary)
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        summary.imported += 1
        return {"status": "reanalysed", "original_id": original_id, "matches": summary.matches - before, "demos_new": 0}

    def _write_members_and_matches(self, original_id: int, rec: dict, summary: Summary) -> None:
        db = self.db
        for m in rec["members"]:
            db.execute(
                "INSERT INTO archive_members(original_id, chain, name, size, mtime, mtime_basis, demo_sha1,"
                " text_content) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    original_id,
                    m["chain"],
                    m["name"],
                    m["size"],
                    m["mtime"],
                    m["mtime_basis"],
                    m["demo_sha1"],
                    m["text"],
                ),
            )
        if rec["proposal"].get("status") == "ok":
            for target in rec["proposal"]["targets"]:
                if self._write_match(original_id, target):
                    summary.matches += 1
                else:
                    summary.duplicate_groups += 1

    def _insert_demo(self, cols: dict, replace: bool) -> None:
        names = ", ".join(cols)
        sql = f"INSERT INTO demos({names}) VALUES ({', '.join('?' * len(cols))})"
        if replace:
            sql += " ON CONFLICT(sha1) DO UPDATE SET " + ", ".join(f"{c} = excluded.{c}" for c in cols if c != "sha1")
        self.db.execute(sql, tuple(cols.values()))

    def _write_demo(self, d: dict, stored: bool = True, replace: bool = False) -> None:
        db = self.db
        h = d.get("header") or {}
        if replace:  # the rows read from the demo are written again below
            for table in ("kills", "rounds", "demo_players", "chat"):
                db.execute(f"DELETE FROM {table} WHERE demo_sha1 = ?", (d["sha1"],))
            row = db.execute("SELECT store_path FROM demos WHERE sha1 = ?", (d["sha1"],)).fetchone()
            stored = stored or bool(row and row[0])  # never forget a copy that exists
        cols = dict.fromkeys(DEMO_COLUMNS)
        cols.update(
            sha1=d["sha1"],
            size=d["size"],
            store_path=_rel_store(d["sha1"]) if stored else "",
            parse_version=PARSE_VERSION,
        )
        if "error" in d:
            cols["parse_error"] = d["error"]
            self._insert_demo(cols, replace)
            return
        rec = d["recorder"]
        view = d.get("viewport") or (None, None)
        analysis = {
            k: d.get(k)
            for k in (
                "problems",
                "fingerprint",
                "usermsgs",
                "teams",
                "score_history",
                "final_score",
                "server",
                "server_names",
                "segments",
                "recorder",
            )
        }
        cols.update(
            demo_protocol=h.get("demo_protocol"), net_protocol=h.get("network_protocol"), map=h.get("map"),
            game_dir=h.get("game_dir"), map_crc=h.get("map_crc"), duration_s=d.get("duration_seconds"),
            kill_count=d.get("kill_count"), release=d["version"]["version"],
            release_basis=json.dumps(d["version"]["basis"]), recorder_kind=rec.get("kind"),
            recorder_slot=rec.get("slot"), server_name=(d.get("server") or {}).get("hostname"),
            viewport_w=view[0], viewport_h=view[1], analysis=json.dumps(analysis, ensure_ascii=False),
        )  # fmt: skip
        self._insert_demo(cols, replace)
        steam_of = {}
        for p in d["players"]:
            if not p["names"]:
                continue
            for n in p["names"]:
                steam_of.setdefault(n, p.get("steamid"))
            db.execute(
                "INSERT INTO demo_players(demo_sha1, slot, player_name_id, names, is_hltv, is_bot, sides, kills,"
                " deaths, headshots, teamkills) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    d["sha1"], p["slot"], self.name_id(p["names"][-1], p.get("steamid")),
                    json.dumps(p["names"], ensure_ascii=False), int(p["hltv"]), int(p["bot"]),
                    json.dumps(p["sides"]), p["kills"], p["deaths"], p["headshots"], p["teamkills"],
                ),
            )  # fmt: skip
        r = d["rounds"]
        for x in r["rounds"]:
            sc = x["score_after"]
            round_id = db.execute(
                "INSERT INTO rounds(demo_sha1, no, start_t, start_basis, end_t, winner, reason, score_ct, score_t)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (d["sha1"], x["number"], x["start"], x["start_basis"], x["end"], x["winner"], x["reason"],
                 sc.get("CT"), sc.get("TERRORIST")),
            ).fetchone()[0]  # fmt: skip
            self._write_kills(d["sha1"], round_id, x["kills"], steam_of)
        self._write_kills(d["sha1"], None, r["other_kills"], steam_of)
        for c in d.get("chat", []):
            db.execute(
                "INSERT INTO chat(demo_sha1, t, sender_entity, text) VALUES (?, ?, ?, ?)",
                (d["sha1"], c["time"], c["sender"], c["text"]),
            )

    def _write_kills(self, sha1: str, round_id: int | None, kills: list, steam_of: dict) -> None:
        for k in kills:
            killer = self.name_id(k["killer"], steam_of.get(k["killer"])) if k["killer"] else None
            victim = self.name_id(k["victim"], steam_of.get(k["victim"])) if k["victim"] else None
            self.db.execute(
                "INSERT INTO kills(demo_sha1, round_id, t, killer_name_id, victim_name_id, weapon, headshot,"
                " killer_side, victim_side) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sha1, round_id, k["time"], killer, victim, k["weapon"],
                 None if k["headshot"] is None else int(k["headshot"]), k["killer_side"], k["victim_side"]),
            )  # fmt: skip

    def _write_match(self, original_id: int, t: dict) -> bool:
        """Create a match unless all its demos already belong to one."""
        db = self.db
        fresh, seen = [], set()
        for i, sha1 in enumerate(t["demo_sha1"]):
            if sha1 in seen:  # the same demo twice in one archive (e.g. also inside a nested copy)
                continue
            seen.add(sha1)
            if not db.execute("SELECT 1 FROM match_demos WHERE demo_sha1 = ?", (sha1,)).fetchone():
                fresh.append((i, sha1))
        if not fresh:
            return False
        match_id = db.execute(
            "INSERT INTO matches(original_id, map, team1_id, team2_id, release, release_basis, year_est, year_basis,"
            " pov, sides, team_basis, library_name, servers, scores) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " RETURNING id",
            (
                original_id, "+".join(t["maps"]), self.team_id(t["team1"]), self.team_id(t["team2"]), t["version"],
                json.dumps(t["version_basis"]), t["year"], t["year_basis"], t["pov"], t["sides"], t["team_basis"],
                t["filename"], json.dumps(t["servers"], ensure_ascii=False), json.dumps(t["scores"]),
            ),
        ).fetchone()[0]  # fmt: skip
        for part, (i, sha1) in enumerate(fresh, start=1):
            db.execute(
                "INSERT INTO match_demos(match_id, demo_sha1, part_no, label) VALUES (?, ?, ?, ?)",
                (match_id, sha1, part, t["members"][i]),
            )
        db.execute(MATCH_TOTALS_SQL, (match_id,))
        for team_key, players in t["lineups"].items():
            for name, v in players.items():
                db.execute(
                    "INSERT INTO match_players(match_id, team_key, player_name_id, aliases) VALUES (?, ?, ?, ?)"
                    " ON CONFLICT DO NOTHING",
                    (match_id, team_key, self.name_id(name, v.get("steamid")),
                     json.dumps(v["aliases"], ensure_ascii=False) if v.get("aliases") else None),
                )  # fmt: skip
        return True


MATCH_TOTALS_SQL = """
UPDATE matches SET
    demo_count = (SELECT count(*) FROM match_demos md WHERE md.match_id = matches.id),
    duration_s = (SELECT coalesce(sum(d.duration_s), 0) FROM match_demos md JOIN demos d ON d.sha1 = md.demo_sha1
                  WHERE md.match_id = matches.id),
    kill_count = (SELECT coalesce(sum(d.kill_count), 0) FROM match_demos md JOIN demos d ON d.sha1 = md.demo_sha1
                  WHERE md.match_id = matches.id),
    file_date = (SELECT min(a.mtime) FROM match_demos md JOIN archive_members a ON a.demo_sha1 = md.demo_sha1
                 WHERE md.match_id = matches.id AND a.original_id = matches.original_id AND a.mtime_basis = 'archive_member')
WHERE id = ?
"""


DEMO_COLUMNS = (
    "sha1", "size", "store_path", "demo_protocol", "net_protocol", "map", "game_dir", "map_crc", "duration_s",
    "kill_count", "release", "release_basis", "recorder_kind", "recorder_slot", "server_name", "viewport_w",
    "viewport_h", "parse_version", "parse_error", "analysis",
)  # fmt: skip


def _rel_store(sha1: str) -> str:
    return f"demos/{sha1[:2]}/{sha1}.dem.gz"


# ------------------------------------------------------------------ driver


@dataclass
class FileTask:
    """One file to read. ``replace``: id of the original it re-analyses."""

    path: str
    label: str
    copy_demos: bool = True
    replace: int | None = None


def collect(paths: Iterable[Path]) -> list[tuple[Path, str]]:
    """(file, label) for every importable file under ``paths``. The label is
    the path relative to the folder given (its name hints at teams and year)."""
    out = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and archives._ext(f.name) in IMPORT_EXT and not f.name.startswith("."):
                    out.append((f, f.relative_to(p).as_posix()))
        elif p.is_file():
            out.append((p, p.name))
    return out


def _job(args):
    task, store_root, mode, database = args
    try:
        rec = inspect_file(
            Path(task.path),
            task.label,
            Path(store_root),
            "referenced" if task.replace else mode,  # a re-analysed file is already kept
            task.copy_demos,
            None if task.replace else database,
        )
    except Exception as exc:  # unreadable file: reported, import continues
        return {"failed": task.path, "error": f"{type(exc).__name__}: {exc}", "task": task}
    rec["task"] = task
    return rec


def database_file(db: sqlite3.Connection) -> str | None:
    row = db.execute("PRAGMA database_list").fetchone()
    return row[2] or None


def import_files(
    db: sqlite3.Connection,
    tasks: list[FileTask],
    store_root: Path,
    mode: str = "referenced",
    workers: int = 4,
    progress: Callable[[int, int, str, Summary], None] | None = None,
    on_file: Callable[[dict], None] | None = None,
    stop: Callable[[], bool] | None = None,
    mp_context=None,
) -> Summary:
    """Read ``tasks`` in worker processes, write each result here.

    ``on_file`` gets one dict per file: path, label, status (imported,
    already, no-demo, failed, reanalysed), original_id, matches, demos_new,
    message. ``stop`` is checked after every file; files not started are
    left for a later run."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    summary = Summary(files=len(tasks))
    writer = Writer(db)
    database = database_file(db)
    done = 0
    pool = ProcessPoolExecutor(max_workers=max(1, workers), mp_context=mp_context)
    try:
        for rec in pool.map(_job, [(t, str(store_root), mode, database) for t in tasks], chunksize=1):
            done += 1
            if "failed" in rec:
                summary.failed += 1
                summary.warnings.append(f"{rec['failed']}: {rec['error']}")
                task = rec["task"]
                result = {"status": "failed", "message": rec["error"], "original_id": task.replace}
            else:
                task = rec["task"]
                try:
                    if "already" in rec:
                        summary.already += 1
                        result = {"status": "already", "original_id": rec["already"]}
                    elif task.replace:
                        result = writer.replace(task.replace, rec, summary)
                    else:
                        result = writer.write(rec, mode, summary)
                except sqlite3.Error as exc:  # one bad file must not stop the import (it was rolled back)
                    summary.failed += 1
                    summary.warnings.append(f"{rec['source']}: database write failed: {exc}")
                    result = {"status": "failed", "message": f"database write failed: {exc}"}
                else:
                    if rec.get("errors"):
                        result["message"] = "\n".join(rec["errors"])
                    if mode == "moved" and rec.get("kept_path") and result["status"] in ("imported", "no-demo"):
                        os.remove(rec["source"])
            if on_file:
                on_file({"path": task.path, "label": task.label, "matches": 0, "demos_new": 0, **result})
            if progress:
                progress(done, len(tasks), task.label, summary)
            if stop and stop():
                break
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    return summary


def import_paths(
    db: sqlite3.Connection,
    paths: Iterable[Path],
    store_root: Path,
    mode: str = "referenced",
    workers: int = 4,
    progress: Callable[[int, int, str, Summary], None] | None = None,
    copy_demos: bool = True,
) -> Summary:
    """Import every file under ``paths``, skipping files already imported
    from the same place (same path and size)."""
    files = collect(paths)
    known = {(row[0], row[1]) for row in db.execute("SELECT source_path, size FROM originals")}
    todo = [FileTask(str(f), label, copy_demos) for f, label in files if (str(f), f.stat().st_size) not in known]
    summary = import_files(db, todo, store_root, mode, workers, progress)
    summary.files = len(files)
    summary.already += len(files) - len(todo)
    return summary
