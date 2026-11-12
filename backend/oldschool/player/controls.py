"""Keys in the game: the actions worth a key while watching demos, like the
game's own Controls page, plus the player's own commands.

Before each Play the app writes ``cstrike/oldschool.cfg`` in the install that
plays the demo and the game runs it (``+exec``) before the demo starts. The
player's ``config.cfg`` is not edited by the app, but the game saves its
current keys there when it closes, so a key the app no longer uses is
explicitly unbound (the file remembers which keys it set).

Key names are the engine's. Before the 2013 Steam versions the engine reads a
key's *position* with a US layout: the key labelled Z on a French keyboard is
"w" for the game, so the usual W A S D is Z Q S D there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

NAMED_KEYS = {
    "tab", "enter", "space", "backspace", "uparrow", "downarrow", "leftarrow", "rightarrow",
    "alt", "ctrl", "shift", "ins", "del", "pgdn", "pgup", "home", "end", "pause", "capslock", "semicolon",
    "kp_home", "kp_uparrow", "kp_pgup", "kp_leftarrow", "kp_5", "kp_rightarrow", "kp_end", "kp_downarrow",
    "kp_pgdn", "kp_enter", "kp_ins", "kp_del", "kp_slash", "kp_minus", "kp_plus",
    "mouse1", "mouse2", "mouse3", "mouse4", "mouse5", "mwheelup", "mwheeldown",
    *(f"f{n}" for n in range(1, 13)),
}  # fmt: skip
CHAR_KEYS = set("abcdefghijklmnopqrstuvwxyz0123456789[]\\',./-=`*")
KEYS_PER_ACTION = 2  # key + alternate, as in the game
CFG_NAME = "oldschool.cfg"
PAUSE_RATE = "0.0001"  # demo seconds per frame: the demo almost stops


@dataclass(frozen=True)
class Action:
    id: str
    group: str
    label: str
    command: str  # what the key runs; toggles call an alias defined in ALIASES
    defaults: tuple[str, ...] = ()
    hint: str = ""
    toggles: tuple[str, ...] = field(default=(), compare=False)


GROUPS = {
    "camera": (
        "Camera (HLTV demos)",
        "In an HLTV demo you watch as a spectator: these keys fly the free camera and choose who to follow. "
        "In a demo recorded by a player you see what they saw, so these keys do nothing.",
    ),
    "demo": ("Watching", ""),
    "speed": ("Speed (CS 1.4 – 1.6)", "The 1.0 – 1.3 engines ignore these during a demo."),
    "game": ("Game", ""),
}

ACTIONS: tuple[Action, ...] = (
    Action("forward", "camera", "Move forward", "+forward", ("w", "uparrow")),
    Action("back", "camera", "Move back", "+back", ("s", "downarrow")),
    Action("moveleft", "camera", "Move left (strafe)", "+moveleft", ("a",)),
    Action("moveright", "camera", "Move right (strafe)", "+moveright", ("d",)),
    Action("jump", "camera", "Jump", "+jump", ("space",), "changes the camera mode"),
    Action("duck", "camera", "Duck", "+duck", ("ctrl",)),
    Action("attack", "camera", "Fire", "+attack", ("mouse1",), "follows the next player"),
    Action("attack2", "camera", "Secondary fire", "+attack2", ("mouse2",), "follows the previous player"),
    Action("scores", "demo", "Scores", "+showscores", ("tab",)),
    Action("hud", "demo", "Show / hide the HUD", "os_hud", ("h",)),
    Action("snapshot", "demo", "Screenshot", "snapshot", ("f5",), ".bmp file in the install's cstrike folder"),
    Action("console", "demo", "Console", "toggleconsole", ("`",)),
    Action("pause", "speed", "Pause / resume", "os_pause", ("p",)),
    Action("slow", "speed", "Slow motion", "os_speed 0.004", ("kp_minus",)),
    Action("fast", "speed", "Fast forward", "os_speed 0.05", ("kp_plus",)),
    Action("normal", "speed", "Normal speed", "os_speed 0", ("kp_enter",)),
    Action("stop", "game", "Stop the demo", "disconnect"),
    Action("quit", "game", "Quit the game", "quit"),
)
BY_ID = {a.id: a for a in ACTIONS}

# Toggles and speed changes, the usual way with aliases. Every speed change
# also resets the pause toggle so the next press pauses.
ALIASES = [
    ("os_hud", "os_hud_off"),
    ("os_hud_off", "hud_draw 0; alias os_hud os_hud_on"),
    ("os_hud_on", "hud_draw 1; alias os_hud os_hud_off"),
    ("os_pause", "os_pause_on"),
    ("os_pause_on", f"host_framerate {PAUSE_RATE}; alias os_pause os_pause_off"),
    ("os_pause_off", "host_framerate 0; alias os_pause os_pause_on"),
]


def is_key(name: str) -> bool:
    return name in NAMED_KEYS or name in CHAR_KEYS


def default_controls() -> dict[str, list[str]]:
    return {a.id: list(a.defaults) for a in ACTIONS}


def clean_controls(value: object) -> dict[str, list[str]]:
    """Validated {action id: [key, alternate]} (missing actions keep their defaults)."""
    if not isinstance(value, dict):
        raise ValueError("controls must map actions to keys")
    out: dict[str, list[str]] = {}
    for action, keys in value.items():
        if action not in BY_ID:
            raise ValueError(f"unknown action: {action!r}")
        if not isinstance(keys, list) or len(keys) > KEYS_PER_ACTION or not all(isinstance(k, str) for k in keys):
            raise ValueError(f"{action}: at most {KEYS_PER_ACTION} keys")
        names = [k.strip().lower() for k in keys if k.strip()]
        for k in names:
            if not is_key(k):
                raise ValueError(f"unknown key for the game: {k!r}")
        if len(set(names)) != len(names):
            raise ValueError(f"{action}: the same key twice")
        out[action] = names
    return out


def clean_binds(value: object) -> list[dict[str, str]]:
    """The player's own commands: [{"key": "f6", "command": "..."}]."""
    if not isinstance(value, list) or len(value) > 64:
        raise ValueError("binds must be a list of at most 64 keys")
    out: list[dict[str, str]] = []
    for item in value:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("key"), str)
            or not isinstance(item.get("command"), str)
        ):
            raise ValueError("each bind needs a key and a command")
        k, command = item["key"].strip().lower(), item["command"].strip()
        if not is_key(k):
            raise ValueError(f"unknown key for the game: {item['key']!r}")
        if not command or len(command) > 200 or any(c in command for c in '"\r\n'):
            raise ValueError(f'key {k}: the command must be one line of at most 200 characters, without "')
        out.append({"key": k, "command": command})
    return out


def merged(stored: dict[str, list[str]], binds: list[dict[str, str]]) -> dict[str, list[str]]:
    """Defaults, then what the player changed; a key taken by one of their own
    commands is left to that command."""
    own = {b["key"] for b in binds}
    out = default_controls()
    out.update(stored)
    return {a: [k for k in keys if k not in own] for a, keys in out.items()}


def check_unique(controls: dict[str, list[str]], binds: list[dict[str, str]]) -> None:
    seen: dict[str, str] = {}
    for action, keys in controls.items():
        for k in keys:
            if k in seen:
                raise ValueError(f"key {k} is used by {BY_ID[seen[k]].label} and {BY_ID[action].label}")
            seen[k] = action
    for b in binds:
        if b["key"] in seen:
            other = BY_ID[seen[b["key"]]].label if seen[b["key"]] in BY_ID else "another command"
            raise ValueError(f"key {b['key']} is used twice ({other})")
        seen[b["key"]] = "own"


_BOUND = re.compile(r'^\s*(?:un)?bind\s+"([^"]+)"', re.IGNORECASE)


def previous_keys(path: Path) -> set[str]:
    """Keys the app bound or unbound in this install last time."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return {m.group(1).lower() for line in text.splitlines() if (m := _BOUND.match(line))}


def cfg_text(controls: dict[str, list[str]], binds: list[dict[str, str]], before: set[str] = frozenset()) -> str:
    bound: dict[str, str] = {}
    for a in ACTIONS:
        for k in controls.get(a.id, []):
            bound[k] = a.command
    for b in binds:
        bound[b["key"]] = b["command"]
    defaults = {k for a in ACTIONS for k in a.defaults}
    free = sorted((set(before) | defaults) - set(bound) - {"`"})  # never leave the game without a console key
    lines = ["// Written by Oldschool CS Demos before each Play: change the keys in the app's Settings, not here."]
    lines += [f'alias {name} "{body}"' for name, body in ALIASES]
    lines += [f'unbind "{k}"' for k in free]
    lines += [f'bind "{k}" "{_expand(c)}"' for k, c in bound.items()]
    return "\r\n".join(lines) + "\r\n"


def _expand(command: str) -> str:
    """Speed actions, written in full (aliases take no arguments in these engines)."""
    m = re.fullmatch(r"os_speed (\S+)", command)
    if m:
        return f"host_framerate {m.group(1)}; alias os_pause os_pause_on"
    return command
