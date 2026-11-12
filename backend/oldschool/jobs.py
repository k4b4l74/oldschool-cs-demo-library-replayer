"""Background imports: the job queue, its worker and the Drop folder watcher.

One job runs at a time (SQLite has one writer); inside a job, files are
read by worker processes (``importer.import_files``). Jobs live in the
``jobs`` table, each file's outcome in ``job_files``, so the page can show
progress and results, and a job interrupted by closing the app resumes at
the next start.

Kinds of job:

* ``import``, origin ``drop``: files put in the Drop folder (or sent by the
  page). They are kept in ``store/originals`` and leave the Drop folder;
  what cannot be imported is moved aside, never deleted:
  ``_failed`` (with a ``.txt`` reason), ``_already imported``, ``_skipped``
  (not a demo or archive), ``_cancelled``.
* ``import``, origin ``folder``: a folder chosen in the app, left in place.
  Running it again only reads files not imported yet.
* ``import``, origin ``retry``: one file that failed, read again.
* ``reanalyse``: every file of the library read again by this version of
  the app, in import order (``Writer.replace``).
"""

from __future__ import annotations

import json
import logging
import multiprocessing
import os
import shutil
import sqlite3
import threading
import time
from pathlib import Path

from oldschool import archives
from oldschool.db.migrate import connect
from oldschool.importer import IMPORT_EXT, PARSE_VERSION, FileTask, Summary, import_files

log = logging.getLogger("oldschool.jobs")

ASIDE = {"failed": "_failed", "already": "_already imported", "skipped": "_skipped", "cancelled": "_cancelled"}
IGNORED_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}
INCOMING = ".incoming"  # uploads being written; moved into Drop when complete
STABLE_SECONDS = 2.0  # a dropped file must stop changing this long before it is read


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def default_workers() -> int:
    return max(1, min(4, (os.cpu_count() or 2) - 1))


def enqueue(db: sqlite3.Connection, kind: str, payload: dict) -> int:
    return db.execute(
        "INSERT INTO jobs(kind, payload) VALUES (?, ?) RETURNING id", (kind, json.dumps(payload, ensure_ascii=False))
    ).fetchone()[0]


def unique_path(path: Path) -> Path:
    """``x.zip`` → ``x (2).zip`` … when taken."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    n = 2
    while (candidate := path.with_name(f"{stem} ({n}){suffix}")).exists():
        n += 1
    return candidate


def importable(name: str) -> bool:
    return archives._ext(name) in IMPORT_EXT and not name.startswith(".")


class Jobs:
    def __init__(
        self,
        database: Path | str,
        store_root: Path,
        drop_dir: Path | None = None,
        workers: int | None = None,
        mp_context=None,
        poll_seconds: float = 1.0,
    ):
        self.database = str(database)
        self.store_root = Path(store_root)
        self.drop = Path(drop_dir) if drop_dir else None
        self.workers = workers or default_workers()
        # Threads run next to the web server: start worker processes fresh (no fork).
        self.mp_context = mp_context or multiprocessing.get_context("spawn")
        self.poll = poll_seconds
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._cancel: set[int] = set()
        self._threads: list[threading.Thread] = []
        self._seen: dict[str, tuple] = {}  # Drop entry -> (signature, time first seen with it)
        if self.drop:
            (self.drop / INCOMING).mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- lifecycle

    def start(self) -> None:
        db = connect(self.database)
        try:  # the app was closed during a job: run it again (finished files are skipped)
            db.execute("UPDATE jobs SET state = 'queued' WHERE state = 'running'")
        finally:
            db.close()
        self._threads = [threading.Thread(target=self._work_loop, name="oldschool-jobs", daemon=True)]
        if self.drop:
            self._threads.append(threading.Thread(target=self._watch_loop, name="oldschool-drop", daemon=True))
        for t in self._threads:
            t.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        for t in self._threads:
            t.join(timeout=60)

    def wake(self) -> None:
        self._wake.set()

    def cancel(self, db: sqlite3.Connection, job_id: int) -> bool:
        row = db.execute(
            "UPDATE jobs SET state = 'cancelled', finished_at = ? WHERE id = ? AND state = 'queued' RETURNING payload",
            (now(), job_id),
        ).fetchone()
        if row:
            payload = json.loads(row[0])
            if payload.get("origin") == "drop":
                self._clear_entries(payload, "cancelled")
            return True
        if db.execute("SELECT 1 FROM jobs WHERE id = ? AND state = 'running'", (job_id,)).fetchone():
            self._cancel.add(job_id)
            return True
        return False

    # ---------------------------------------------------------------- worker

    def _work_loop(self) -> None:
        while not self._stop.is_set():
            try:
                ran = self.run_once()
            except Exception:
                log.exception("job worker")
                ran = False
            if not ran:
                self._wake.wait(self.poll)
                self._wake.clear()

    def run_once(self) -> bool:
        """Run the oldest queued job. False when there is none."""
        db = connect(self.database)
        try:
            row = db.execute("SELECT id FROM jobs WHERE state = 'queued' ORDER BY id LIMIT 1").fetchone()
            if not row:
                return False
            job_id = row[0]
            taken = db.execute(
                "UPDATE jobs SET state = 'running', attempts = attempts + 1, started_at = coalesce(started_at, ?)"
                " WHERE id = ? AND state = 'queued' RETURNING kind, payload",
                (now(), job_id),
            ).fetchone()
            if not taken:
                return True
            kind, payload = taken[0], json.loads(taken[1])
            try:
                state = self._run(db, job_id, kind, payload)
            except Exception as exc:
                log.exception("job %s failed", job_id)
                db.execute(
                    "UPDATE jobs SET state = 'failed', error = ?, finished_at = ? WHERE id = ?",
                    (f"{type(exc).__name__}: {exc}", now(), job_id),
                )
                if payload.get("origin") == "drop":
                    self._clear_entries(payload, "failed", reason=f"{type(exc).__name__}: {exc}")
                return True
            if state == "queued":  # the app is closing: resume at the next start
                db.execute("UPDATE jobs SET state = 'queued' WHERE id = ?", (job_id,))
            else:
                db.execute("UPDATE jobs SET state = ?, finished_at = ? WHERE id = ?", (state, now(), job_id))
            return True
        finally:
            db.close()

    def _run(self, db: sqlite3.Connection, job_id: int, kind: str, payload: dict) -> str:
        if kind == "reanalyse":
            tasks, skipped = self._reanalyse_tasks(db, job_id, payload)
            mode = "referenced"
        elif kind == "import":
            tasks, skipped = self._import_tasks(db, payload)
            mode = payload.get("mode", "referenced")
        else:
            raise ValueError(f"unknown job kind {kind}")
        origin = payload.get("origin")
        last = [0.0]

        def save_progress(done: int, total: int, label: str, summary: Summary, force: bool = False) -> None:
            if force or time.monotonic() - last[0] > 0.5:
                last[0] = time.monotonic()
                info = {"done": done, "total": total, "current": label, "summary": _summary(summary, skipped)}
                db.execute("UPDATE jobs SET progress = ? WHERE id = ?", (json.dumps(info, ensure_ascii=False), job_id))

        def on_file(r: dict) -> None:
            moved_to = None
            if origin == "drop" and r["status"] in ("failed", "already"):
                moved_to = self._aside(Path(r["path"]), r["label"], r["status"], r.get("message"))
            if origin == "retry" and r["status"] in ("imported", "no-demo", "already"):
                Path(r["path"] + ".txt").unlink(missing_ok=True)  # the reason written next to a failed Drop file
            db.execute(
                "INSERT INTO job_files(job_id, path, label, status, original_id, matches, demos_new, message, moved_to)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id, r["path"], r["label"], r["status"], r.get("original_id"), r.get("matches", 0),
                    r.get("demos_new", 0), r.get("message"), str(moved_to) if moved_to else None,
                ),
            )  # fmt: skip

        def stop() -> bool:
            return self._stop.is_set() or job_id in self._cancel

        save_progress(0, len(tasks), "", Summary(files=len(tasks)), force=True)
        summary = import_files(
            db,
            tasks,
            self.store_root,
            mode,
            self.workers,
            progress=save_progress,
            on_file=on_file,
            stop=stop,
            mp_context=self.mp_context,
        )
        done = db.execute("SELECT count(*) FROM job_files WHERE job_id = ?", (job_id,)).fetchone()[0]
        save_progress(done, len(tasks), "", summary, force=True)
        if self._stop.is_set() and done < len(tasks):
            return "queued"
        cancelled = job_id in self._cancel
        self._cancel.discard(job_id)
        if origin == "drop":
            self._clear_entries(payload, "cancelled" if cancelled else "skipped")
        return "cancelled" if cancelled else "done"

    def _import_tasks(self, db: sqlite3.Connection, payload: dict) -> tuple[list[FileTask], int]:
        """Files of the job not imported yet from the same place."""
        copy = bool(payload.get("copy_demos", True))
        labels = payload.get("labels") or {}
        drop = payload.get("origin") == "drop"
        found: list[tuple[Path, str]] = []
        for p in payload["paths"]:
            path = Path(p)
            if path.is_dir():
                base = path.parent if drop else path  # Drop: keep the dropped folder's name in the label
                for f in sorted(path.rglob("*")):
                    if f.is_file() and importable(f.name):
                        found.append((f, f.relative_to(base).as_posix()))
            elif path.is_file() and importable(path.name):
                found.append((path, labels.get(p) or path.name))
        known = {
            (r[0], r[1])
            for r in db.execute(
                "SELECT source_path, size FROM originals WHERE source_path IN (SELECT value FROM json_each(?))",
                (json.dumps([str(f) for f, _ in found]),),
            )
        }
        tasks = [FileTask(str(f), label, copy) for f, label in found if (str(f), f.stat().st_size) not in known]
        return tasks, len(found) - len(tasks)

    def _reanalyse_tasks(self, db: sqlite3.Connection, job_id: int, payload: dict) -> tuple[list[FileTask], int]:
        done = {r[0] for r in db.execute("SELECT original_id FROM job_files WHERE job_id = ?", (job_id,))}
        where = ""
        if payload.get("only_outdated"):
            where = (
                " WHERE o.id IN (SELECT a.original_id FROM archive_members a JOIN demos d ON d.sha1 = a.demo_sha1"
                f" WHERE d.parse_version < {int(PARSE_VERSION)})"
            )
        tasks = []
        for r in db.execute(f"SELECT o.* FROM originals o{where} ORDER BY o.id"):
            if r["id"] in done:
                continue
            label = r["label"] or r["file_name"]
            path = next((p for p in (r["kept_path"], r["source_path"]) if p and Path(p).is_file()), None)
            if path is None:
                db.execute(
                    "INSERT INTO job_files(job_id, path, label, status, original_id, message) VALUES (?, ?, ?, 'missing', ?, ?)",
                    (
                        job_id,
                        r["source_path"],
                        label,
                        r["id"],
                        "the file is no longer there: its data was kept as it was",
                    ),
                )
                continue
            tasks.append(FileTask(path, label, bool(r["demo_copies"]), replace=r["id"]))
        return tasks, 0

    # ---------------------------------------------------------------- Drop folder

    def _aside(self, path: Path, label: str, why: str, message: str | None = None) -> Path | None:
        """Move a Drop file out of the way, keeping its relative path."""
        if not self.drop or not path.exists():
            return None
        target = unique_path(self.drop / ASIDE[why] / label)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), target)
        if why == "failed":
            target.with_name(target.name + ".txt").write_text(
                f"{label}\nnot imported: {message or 'unknown error'}\n", encoding="utf-8"
            )
        return target

    def _clear_entries(self, payload: dict, why: str, reason: str | None = None) -> None:
        """After a Drop job: what is left of its entries goes aside, empty folders go."""
        for p in payload.get("paths", []):
            entry = Path(p)
            if entry.is_file():
                self._aside(entry, entry.name, why, reason)
            elif entry.is_dir():
                for f in sorted(entry.rglob("*")):
                    if f.is_file():
                        self._aside(f, f.relative_to(entry.parent).as_posix(), why, reason)
                for d in sorted((d for d in entry.rglob("*") if d.is_dir()), key=lambda d: -len(d.parts)):
                    _rmdir(d)
                _rmdir(entry)

    def _watch_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.scan_drop()
            except Exception:
                log.exception("drop folder watcher")
            self._stop.wait(self.poll)

    def scan_drop(self, stable_seconds: float = STABLE_SECONDS) -> int | None:
        """Queue one job with the Drop entries that stopped changing. Returns its id."""
        if not self.drop or not self.drop.is_dir():
            return None
        db = connect(self.database)
        try:
            claimed = set()
            for (payload,) in db.execute(
                "SELECT payload FROM jobs WHERE kind = 'import' AND state IN ('queued', 'running')"
            ):
                claimed.update(json.loads(payload).get("paths", []))
            ready, current = [], {}
            t = time.monotonic()
            for entry in sorted(self.drop.iterdir()):
                if entry.name.startswith(("_", ".")) or entry.name.lower() in IGNORED_NAMES:
                    continue
                key = str(entry)
                if key in claimed:
                    continue
                sig = _signature(entry)
                seen = self._seen.get(key)
                current[key] = (sig, seen[1] if seen and seen[0] == sig else t)
                if t - current[key][1] >= stable_seconds:
                    ready.append(key)
            self._seen = current
            if not ready:
                return None
            for key in ready:
                self._seen.pop(key, None)
            job_id = enqueue(db, "import", {"origin": "drop", "paths": ready, "mode": "moved", "copy_demos": True})
            log.info("Drop: queued job %s for %d entries", job_id, len(ready))
        finally:
            db.close()
        self.wake()
        return job_id


def _signature(entry: Path) -> tuple:
    try:
        if entry.is_file():
            st = entry.stat()
            return (st.st_size, st.st_mtime_ns)
        files = [f.stat() for f in entry.rglob("*") if f.is_file()]
        return (len(files), sum(s.st_size for s in files), max((s.st_mtime_ns for s in files), default=0))
    except OSError:  # changing under our feet
        return (time.monotonic(),)


def _rmdir(d: Path) -> None:
    try:
        d.rmdir()
    except OSError:
        pass


def _summary(s: Summary, skipped: int) -> dict:
    return {
        "imported": s.imported,
        "already": s.already + skipped,
        "no_demo": s.no_demo,
        "failed": s.failed,
        "matches": s.matches,
        "demos_new": s.demos_new,
    }
