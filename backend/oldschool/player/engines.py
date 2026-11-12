"""Game installs: detection, checks and which one plays which demo.

An install is a folder with ``hl.exe`` and a ``cstrike`` game folder. Two
families:

* ``won``: the original Half-Life 1.1.x engines (CS 1.0-1.5). Window size and
  mode come from the registry; ``+connect`` skips their launcher menu;
  1.1.0.6-1.1.0.9 also need ``-newdat`` and a path with no dot and no
  ``-w``/``-h`` (docs/ARCHITECTURE.md §3);
* ``steam``: the 2003-2009 CS 1.6 builds (``FileSystem_Steam.dll``). They
  take the window size from their arguments.

The demo's network protocol must match the engine's. Protocol and build
are read from the folder name (``CS13_P45_hl1108``, ``CS16_P47_build3248``),
an ``INSTALL-PROVENANCE.json`` or ``engine.json`` next to ``hl.exe``, or the
build; the CS release from ``cstrike/liblist.gam``. Everything detected can
be overridden in Settings.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from oldschool.player.platform import to_local, to_native

KINDS = ("won", "steam")
SEEK_METHODS = ("framerate", "retime")
VIDEO_MODES = ("registry", "registry-demo", "args")
EDITABLE = ("protocol", "release", "seek_method", "video", "args", "kind")

WON_BASE_ARGS = ["-game", "cstrike", "-console", "-gl", "-nojoy", "-nomaster", "-condebug"]
STEAM_BASE_ARGS = ["-game", "cstrike", "-console", "-windowed", "-w", "1280", "-h", "960", "-gl",
                   "-nojoy", "-nomaster", "-noauth", "-noip", "-noipx", "-condebug"]  # fmt: skip
# Engine build -> network protocol, for folders whose name does not say it.
WON_PROTOCOL = {"1.1.0.6": 43, "1.1.0.8": 45, "1.1.0.9": 45, "1.1.1.0": 46}
_NAME_PROTOCOL = re.compile(r"(?:^|[_\-])P(4[3-9])(?:[_\-]|$)", re.I)
_NAME_WON = re.compile(r"hl(1\d{3})", re.I)
_NAME_BUILD = re.compile(r"build[_\-]?(\d{4})", re.I)
_LIBLIST_VERSION = re.compile(rb'^\s*version\s+"([0-9.]+)"', re.I | re.M)


def _ci(folder: Path, name: str) -> Path | None:
    """File in ``folder`` whatever its case (Windows names, Linux checks)."""
    p = folder / name
    if p.exists():
        return p
    try:
        low = name.lower()
        return next((c for c in folder.iterdir() if c.name.lower() == low), None)
    except OSError:
        return None


def detect(local: Path) -> dict:
    """What can be said about an install folder without running it."""
    name = local.name
    info: dict = {"kind": None, "build": None, "protocol": None, "release": None, "notes": []}
    info["kind"] = "steam" if _ci(local, "FileSystem_Steam.dll") else "won"
    for meta_name in ("engine.json", "INSTALL-PROVENANCE.json"):
        meta = _ci(local, meta_name)
        if meta:
            try:
                m = json.loads(meta.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                info["notes"].append(f"{meta.name} unreadable")
                continue
            if isinstance(m.get("reported_network_protocol") or m.get("protocol"), int):
                info["protocol"] = m.get("reported_network_protocol") or m.get("protocol")
            build = m.get("reported_engine_build") or m.get("build")
            if build:
                b = re.search(r"\((\d{4})\)\s*$", str(build))
                info["build"] = f"build {b.group(1)}" if b else str(build)
    m = _NAME_WON.search(name)
    if m and not info["build"]:
        digits = m.group(1)
        info["build"] = ".".join(digits)  # hl1108 -> 1.1.0.8
    m = _NAME_BUILD.search(name)
    if m and not info["build"]:
        info["build"] = f"build {m.group(1)}"
    m = _NAME_PROTOCOL.search(name)
    if m:
        info["protocol"] = int(m.group(1))
    if info["protocol"] is None and info["build"] in WON_PROTOCOL:
        info["protocol"] = WON_PROTOCOL[info["build"]]
    liblist = _ci(local / "cstrike", "liblist.gam") if (local / "cstrike").is_dir() else None
    if liblist:
        v = _LIBLIST_VERSION.search(liblist.read_bytes())
        if v:
            info["release"] = "CS" + v.group(1).decode()
    info["seek_method"] = "retime" if info["build"] in ("1.1.0.6", "1.1.0.8") else "framerate"
    if info["kind"] == "steam":
        info["video"] = "args"
        info["args"] = (["-steam", "-appid", "10"] if _ci(local, "steam_api.dll") else []) + STEAM_BASE_ARGS
    else:
        # 1.1.0.8/1.1.0.9 draw the 3D view at the demo's recorded size.
        info["video"] = "registry-demo" if info["build"] in ("1.1.0.8", "1.1.0.9") else "registry"
        old = info["build"] in ("1.1.0.6", "1.1.0.8", "1.1.0.9")
        info["args"] = WON_BASE_ARGS + (["-newdat"] if old else [])
    return info


def checks(native: str, eff: dict) -> list[str]:
    """Problems that stop or spoil playback, in plain words."""
    problems = []
    if eff.get("kind") == "won" and eff.get("build") in ("1.1.0.6", "1.1.0.8", "1.1.0.9"):
        folder = native.rstrip("\\/")
        if "." in folder:
            problems.append(
                "the folder path contains a dot: old hl.exe versions cut their path at the first dot and refuse to start"
            )
        if "-w" in folder or "-h" in folder:
            problems.append(
                "the folder path contains '-w' or '-h': old hl.exe versions read it as a window size switch"
            )
    local = to_local(native)
    if not local.is_dir():
        return ["folder not found", *problems]
    if not _ci(local, "hl.exe"):
        problems.append("hl.exe missing")
    if not _ci(local, "hw.dll"):
        problems.append("hw.dll missing")
    cstrike = local / "cstrike"
    if not cstrike.is_dir():
        problems.append("cstrike folder missing")
    else:
        if not _ci(cstrike, "liblist.gam"):
            problems.append("cstrike/liblist.gam missing")
        if not (cstrike / "cl_dlls").is_dir() or not _ci(cstrike / "cl_dlls", "client.dll"):
            problems.append("cstrike/cl_dlls/client.dll missing")
    if eff.get("protocol") is None:
        problems.append("network protocol unknown: set it in Settings")
    if not eff.get("release"):
        problems.append("CS release unknown: set it in Settings")
    return problems


def effective(row: sqlite3.Row | dict) -> dict:
    detected = json.loads(row["detected"] or "{}")
    overrides = json.loads(row["overrides"] or "{}")
    return {**detected, **{k: v for k, v in overrides.items() if k in EDITABLE}}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def save(db: sqlite3.Connection, engine_id: int) -> None:
    """Recompute effective values and checks for one install."""
    row = db.execute("SELECT * FROM engines WHERE id = ?", (engine_id,)).fetchone()
    eff = effective(row)
    problems = checks(row["path"], eff)
    fatal = ("missing", "not found", "contains a dot", "'-w' or '-h'")
    status = "broken" if any(f in p for p in problems for f in fatal) else ("warning" if problems else "ok")
    db.execute(
        "UPDATE engines SET kind = ?, build = ?, protocols = ?, releases = ?, status = ?, status_detail = ?,"
        " last_check = ?, missing = ? WHERE id = ?",
        (
            eff.get("kind") or "won", eff.get("build"), json.dumps([eff["protocol"]] if eff.get("protocol") else []),
            json.dumps([eff["release"]] if eff.get("release") else []), status, json.dumps(problems), _now(),
            int(bool(problems) and problems[0] == "folder not found"), engine_id,
        ),
    )  # fmt: skip


def add(db: sqlite3.Connection, native: str, source: str = "manual") -> int:
    native = native.rstrip("\\/") or native
    row = db.execute("SELECT id FROM engines WHERE path = ?", (native,)).fetchone()
    detected = detect(to_local(native)) if to_local(native).is_dir() else {}
    if row:
        db.execute(
            "UPDATE engines SET detected = ?, name = ? WHERE id = ?", (json.dumps(detected), _name(native), row[0])
        )
        engine_id = row[0]
    else:
        engine_id = db.execute(
            "INSERT INTO engines(path, name, kind, detected, source) VALUES (?, ?, ?, ?, ?) RETURNING id",
            (native, _name(native), detected.get("kind") or "won", json.dumps(detected), source),
        ).fetchone()[0]
    save(db, engine_id)
    return engine_id


def _name(native: str) -> str:
    return re.split(r"[\\/]", native.rstrip("\\/"))[-1]


def scan(db: sqlite3.Connection, roots: list[str]) -> dict:
    """Find installs in each root (folders containing hl.exe), refresh known
    ones. User overrides are kept; installs no longer found are flagged."""
    found = 0
    for root in roots:
        local_root = to_local(root)
        if not local_root.is_dir():
            continue
        for child in sorted(local_root.iterdir()):
            if child.is_dir() and _ci(child, "hl.exe"):
                windows_root = root[1:2] == ":"
                native = root.rstrip("\\/") + "\\" + child.name if windows_root else to_native(child)
                add(db, native, "scan")
                found += 1
    for (engine_id,) in db.execute("SELECT id FROM engines").fetchall():
        save(db, engine_id)
    return {"found": found, "roots": len(roots)}


def update(db: sqlite3.Connection, engine_id: int, changes: dict) -> None:
    row = db.execute("SELECT * FROM engines WHERE id = ?", (engine_id,)).fetchone()
    if not row:
        raise KeyError(engine_id)
    overrides = json.loads(row["overrides"] or "{}")
    for key, value in changes.items():
        if key == "enabled":
            db.execute("UPDATE engines SET enabled = ? WHERE id = ?", (int(bool(value)), engine_id))
            continue
        if key not in EDITABLE:
            raise ValueError(f"cannot change {key}")
        if value is None:
            overrides.pop(key, None)  # back to the detected value
            continue
        if key == "protocol" and not (isinstance(value, int) and 40 <= value <= 48):
            raise ValueError("protocol must be a number from 40 to 48")
        if key == "release" and not re.fullmatch(r"CS1\.[0-6]|CSbeta[0-9.]*", str(value)):
            raise ValueError("release looks like CS1.0 … CS1.6")
        if key == "seek_method" and value not in SEEK_METHODS:
            raise ValueError(f"seek_method is one of {SEEK_METHODS}")
        if key == "video" and value not in VIDEO_MODES:
            raise ValueError(f"video is one of {VIDEO_MODES}")
        if key == "kind" and value not in KINDS:
            raise ValueError(f"kind is one of {KINDS}")
        if key == "args" and not (isinstance(value, list) and all(isinstance(a, str) for a in value)):
            raise ValueError("args must be a list of strings")
        overrides[key] = value
    db.execute("UPDATE engines SET overrides = ? WHERE id = ?", (json.dumps(overrides), engine_id))
    save(db, engine_id)


# ---------------------------------------------------------------- routing


def _usable(row) -> bool:
    return bool(row["enabled"]) and row["status"] != "broken"


def _newest_first(row) -> tuple:
    """Newer build first: within one protocol it usually plays older demos
    best (CS 1.6 build 3248 before 2603)."""
    digits = re.findall(r"\d+", effective(row).get("build") or "")
    return tuple(-int(d) for d in digits) or (0,)


def candidates(db: sqlite3.Connection, protocol: int | None, release: str | None) -> list[sqlite3.Row]:
    """Installs that can play (protocol, release), best first: same release,
    then any release on the same protocol - newest build first - except protocol 46, where CS 1.5
    and CS 1.6 need their own game files (FAMAS, Galil…)."""
    rows = sorted((r for r in db.execute("SELECT * FROM engines ORDER BY name") if _usable(r)), key=_newest_first)
    same = [r for r in rows if protocol is not None and effective(r).get("protocol") == protocol]
    exact = [r for r in same if effective(r).get("release") == release]
    if exact or protocol == 46:
        return exact
    return same


def route(db: sqlite3.Connection, protocol: int | None, release: str | None) -> tuple[sqlite3.Row | None, str]:
    """The install for a demo, and how it was chosen (or why none)."""
    chosen = db.execute(
        "SELECT e.* FROM engine_routes r JOIN engines e ON e.id = r.engine_id WHERE r.protocol = ? AND r.release = ?",
        (protocol, release),
    ).fetchone()
    if chosen and _usable(chosen):
        return chosen, "chosen in Settings"
    best = candidates(db, protocol, release)
    if best:
        return best[0], "automatic"
    if protocol is None:
        return None, "the demo's network protocol is unknown"
    return (
        None,
        f"no working install for {release or 'this release'} (network protocol {protocol}): add one in Settings",
    )


def set_route(db: sqlite3.Connection, protocol: int, release: str, engine_id: int | None) -> None:
    if engine_id is None:
        db.execute("DELETE FROM engine_routes WHERE protocol = ? AND release = ?", (protocol, release))
        return
    if not db.execute("SELECT 1 FROM engines WHERE id = ?", (engine_id,)).fetchone():
        raise KeyError(engine_id)
    db.execute(
        "INSERT INTO engine_routes(protocol, release, engine_id) VALUES (?, ?, ?)"
        " ON CONFLICT(protocol, release) DO UPDATE SET engine_id = excluded.engine_id",
        (protocol, release, engine_id),
    )


def demo_kinds(db: sqlite3.Connection) -> list[tuple[int, str, int]]:
    """(protocol, release, demos) present in the library: the rows of the
    routing table in Settings."""
    return [
        (r[0], r[1], r[2])
        for r in db.execute(
            "SELECT net_protocol, release, count(*) FROM demos WHERE net_protocol IS NOT NULL AND release IS NOT NULL"
            " GROUP BY net_protocol, release ORDER BY net_protocol, release"
        )
    ]
