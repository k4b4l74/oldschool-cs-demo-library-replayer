"""User settings, stored as JSON values in the ``settings`` table."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from typing import Any

from oldschool.player import controls

# The WON hl.exe offers only these 4:3 window sizes.
WON_MODES = ["640x480", "800x600", "1024x768", "1152x864", "1280x960"]

DEFAULTS: dict[str, Any] = {
    "engine_roots": [],  # folders whose sub-folders are game installs (Windows paths)
    "map_folders": [],  # extra folders searched for a missing map .bsp
    "won_resolution": "1280x960",  # CS 1.0-1.5 window size
    "windowed": True,
    "seek_framerate": 0.5,  # host_framerate while fast-forwarding (engines 1.1.0.9+)
    "seek_retime_factor": 20.0,  # time compression before the target (engines 1.1.0.6/1.1.0.8)
    "welcomed": False,  # the first-run page was completed or skipped
    "controls": {},  # {action id: [key, alternate]} changed from the defaults (player/controls.py)
    "binds": [],  # the player's own commands: [{"key": "f6", "command": "..."}]
}


def env_engine_roots() -> list[str]:
    """OLDSCHOOL_ENGINE_ROOTS: extra roots, ';'-separated (development)."""
    return [p for p in os.environ.get("OLDSCHOOL_ENGINE_ROOTS", "").split(";") if p.strip()]


def _stored(db: sqlite3.Connection) -> dict[str, Any]:
    return {k: json.loads(v) for k, v in db.execute("SELECT key, value FROM settings") if k in DEFAULTS}


def get_all(db: sqlite3.Connection) -> dict[str, Any]:
    """Every setting; ``controls`` holds every action, defaults included."""
    out = dict(DEFAULTS)
    out.update(_stored(db))
    out["controls"] = controls.merged({a: k for a, k in out["controls"].items() if a in controls.BY_ID}, out["binds"])
    return out


def validate(key: str, value: Any) -> Any:
    if key not in DEFAULTS:
        raise ValueError(f"unknown setting: {key}")
    if key in ("engine_roots", "map_folders"):
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
            raise ValueError(f"{key} must be a list of folder paths")
        return [v.strip() for v in value]
    if key == "won_resolution":
        if value not in WON_MODES:
            raise ValueError(f"won_resolution must be one of {', '.join(WON_MODES)}")
        return value
    if key in ("windowed", "welcomed"):
        return bool(value)
    if key == "seek_framerate":
        v = float(value)
        if not 0.05 <= v <= 5:
            raise ValueError("seek_framerate must be between 0.05 and 5")
        return v
    if key == "seek_retime_factor":
        v = float(value)
        if not 2 <= v <= 100:
            raise ValueError("seek_retime_factor must be between 2 and 100")
        return v
    if key == "binds":
        return controls.clean_binds(value)
    if key == "controls":
        return controls.clean_controls(value)
    return value


def put(db: sqlite3.Connection, changes: dict[str, Any]) -> dict[str, Any]:
    clean = {k: validate(k, v) for k, v in changes.items()}
    if "controls" in clean or "binds" in clean:
        current = _stored(db)
        controls.check_unique(
            clean.get("controls", current.get("controls", {})), clean.get("binds", current.get("binds", []))
        )
    for k, v in clean.items():
        db.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (k, json.dumps(v)),
        )
    return get_all(db)


def resolution(value: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d+)x(\d+)", value)
    if not m:
        raise ValueError(value)
    return int(m[1]), int(m[2])
