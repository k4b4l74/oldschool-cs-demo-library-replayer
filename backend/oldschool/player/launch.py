"""Start a demo (optionally at a given moment) in the right game install.

Ported from the csdemo:// prototype (game/demo-player/csdemo_launcher.py):
same engine rules, now driven by the engine registry and the settings.
Only the demo copy written for playback is ever changed; the stored demo
stays untouched.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from oldschool import settings as cfg
from oldschool import sources
from oldschool.player import controls as ctl
from oldschool.player import engines as en
from oldschool.player import seek as sk
from oldschool.player.platform import Runner, to_local

log = logging.getLogger("oldschool.play")
DEMO_NAME = "csdemoplay"  # old engines dislike '-' and long names
WON_MODES = [(640, 480), (800, 600), (1024, 768), (1152, 864), (1280, 960)]
DEMO_SIZE_FALLBACK = (1024, 768)


class PlayError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class PlayResult:
    engine: str
    engine_path: str
    chosen: str
    release: str | None
    protocol: int | None
    seek: float | None
    seek_method: str | None
    window: str | None
    map_note: str | None
    command: list[str]


def won_mode_for(view: tuple[int, int] | None) -> tuple[int, int]:
    """The hl.exe mode equal to the recorded view, else the largest that fits."""
    if not view:
        return DEMO_SIZE_FALLBACK
    if view in WON_MODES:
        return view
    fits = [m for m in WON_MODES if m[0] <= view[0] and m[1] <= view[1]]
    return max(fits) if fits else WON_MODES[0]


def ensure_map(db: sqlite3.Connection, engine_local: Path, mapname: str | None, extra_folders: list[str]) -> str | None:
    """Copy a missing map .bsp from another install or a map folder."""
    if not mapname:
        return None
    target = engine_local / "cstrike" / "maps" / f"{mapname}.bsp"
    if target.exists():
        return None
    sources = [to_local(r["path"]) / "cstrike" / "maps" for r in db.execute("SELECT path FROM engines")]
    sources += [to_local(f) for f in extra_folders]
    for folder in sources:
        src = folder / f"{mapname}.bsp"
        if src.is_file() and src.resolve() != target.resolve():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            return f"map {mapname} was missing and was copied from {folder}"
    return f"map {mapname}.bsp was not found in any install or map folder: the demo may stop with 'map not found'"


def write_if_changed(path: Path, text: str) -> None:
    if not path.is_file() or path.read_text(encoding="utf-8", errors="replace") != text:
        path.write_text(text, encoding="utf-8", newline="")


def play(
    db: sqlite3.Connection, store_root: Path, sha1: str, seek: float | None = None, runner: Runner | None = None
) -> PlayResult:
    runner = runner or Runner()
    demo = db.execute(
        "SELECT sha1, net_protocol, release, map, viewport_w, viewport_h, parse_error FROM demos WHERE sha1 = ?",
        (sha1,),
    ).fetchone()
    if not demo:
        raise PlayError(404, "demo not found")
    engine, chosen = en.route(db, demo["net_protocol"], demo["release"])
    if not engine:
        raise PlayError(409, chosen)
    eff = en.effective(engine)
    settings = cfg.get_all(db)
    if runner.running():
        raise PlayError(409, "a game is already running: close it first (the old versions cannot run twice)")
    try:
        data = sources.demo_bytes(db, store_root, sha1)
    except sources.DemoUnavailable as exc:
        raise PlayError(410, str(exc)) from exc

    seek_args: list[str] = []
    method = None
    if seek is not None and seek >= 1:
        method = eff.get("seek_method", "framerate")
        try:
            if method == "retime":
                data = sk.inject_seek_retime(data, seek, float(settings["seek_retime_factor"]))
            else:
                rate = float(settings["seek_framerate"])
                data = sk.inject_seek(data, seek, rate)
                seek_args = sk.start_args(rate)
        except ValueError as exc:
            raise PlayError(422, f"cannot jump inside this demo: {exc}") from exc

    local = to_local(engine["path"])
    exe = en._ci(local, "hl.exe")
    if not exe:
        raise PlayError(409, f"hl.exe not found in {engine['path']}")
    try:  # the keys file again from inside the demo, after the engine's own config.cfg
        data = sk.inject_at_start(data, f"exec {ctl.CFG_NAME}", "keys")
    except ValueError as exc:
        log.warning("keys not injected into the demo copy: %s", exc)
    (local / "cstrike" / f"{DEMO_NAME}.dem").write_bytes(data)
    map_note = ensure_map(db, local, demo["map"], settings["map_folders"])

    window = None
    if eff.get("kind") == "won" and eff.get("video") in ("registry", "registry-demo"):
        if eff["video"] == "registry-demo":
            view = (demo["viewport_w"], demo["viewport_h"]) if demo["viewport_w"] else None
            w, h = won_mode_for(view)
        else:
            w, h = cfg.resolution(settings["won_resolution"])
        runner.set_won_video(
            {"EngineModeW": w, "EngineModeH": h, "EngineModeWindowed": 1 if settings["windowed"] else 0}
        )
        window = f"{w}x{h}{' windowed' if settings['windowed'] else ''}"
    args = list(eff.get("args") or [])
    if eff.get("kind") == "won":
        args.append("+connect")  # skips the WON launcher menu; prints "usage: connect" and goes on
    keys_file = local / "cstrike" / ctl.CFG_NAME  # the player's keys, the same in every install
    text = ctl.cfg_text(settings["controls"], settings["binds"], ctl.previous_keys(keys_file))
    write_if_changed(keys_file, text)
    args += ["+exec", ctl.CFG_NAME]  # early, for engines that keep it; see seek.inject_at_start
    args += seek_args + ["+playdemo", DEMO_NAME]
    runner.spawn(exe, args, local)
    log.info("play %s on %s (%s) seek=%s args=%s", sha1, engine["name"], chosen, seek, " ".join(args))
    return PlayResult(
        engine=engine["name"],
        engine_path=engine["path"],
        chosen=chosen,
        release=demo["release"],
        protocol=demo["net_protocol"],
        seek=seek,
        seek_method=method,
        window=window,
        map_note=map_note,
        command=[exe.name, *args],
    )
