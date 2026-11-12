"""Where the app keeps its data, and its basic settings.

Windows: %LOCALAPPDATA%\\OldschoolCSDemos. Elsewhere (development under WSL):
~/.local/share/oldschool-cs-demos. OLDSCHOOL_DATA_DIR overrides both.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "Oldschool CS Demos Library Replayer"
HOST = "127.0.0.1"  # never listen on the network
DEFAULT_PORT = 27960


FROZEN = bool(getattr(sys, "frozen", False))  # running from the packaged app (PyInstaller)

# Helper programs (tar.exe, 7z.exe, tasklist) must not flash a console window from the windowed app.
NO_WINDOW: dict = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def resource_dir() -> Path:
    """Files shipped with the app: the PyInstaller bundle, else the repository."""
    if FROZEN:
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def frontend_dist() -> Path:
    return resource_dir() / ("frontend_dist" if FROZEN else "frontend/dist")


def default_data_dir() -> Path:
    env = os.environ.get("OLDSCHOOL_DATA_DIR")
    if env:
        return Path(env)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "OldschoolCSDemos"
    return Path.home() / ".local" / "share" / "oldschool-cs-demos"


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def database(self) -> Path:
        return self.root / "library.sqlite"

    @property
    def store(self) -> Path:
        return self.root / "store"

    @property
    def drop(self) -> Path:
        return self.root / "Drop"

    @property
    def engines(self) -> Path:
        return self.root / "Engines"

    def ensure(self) -> Paths:
        for p in (self.root, self.store, self.drop, self.engines):
            p.mkdir(parents=True, exist_ok=True)
        return self
