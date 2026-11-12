"""What the player needs from the operating system.

The app runs on Windows. During development it runs under WSL and reaches
Windows through interop (``reg.exe``, ``tasklist.exe``, running ``hl.exe``).
Engine paths are stored as Windows paths (``E:\\CounterStrike\\…``) and
converted to local paths only to touch files from WSL.
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import threading
from pathlib import Path, PureWindowsPath

from oldschool.config import NO_WINDOW

IS_WINDOWS = os.name == "nt"
IS_WSL = not IS_WINDOWS and "microsoft" in platform.release().lower()
_DRIVE = re.compile(r"^([A-Za-z]):[\\/](.*)$")
_MNT = re.compile(r"^/mnt/([a-z])(?:/(.*))?$")
_WSL_SHARE = re.compile(r"^\\\\wsl(?:\.localhost|\$)\\[^\\]+(\\.*)?$", re.IGNORECASE)
WON_SETTINGS_KEY = r"HKCU\Software\Valve\Half-Life\Settings"


def to_local(native: str) -> Path:
    """Windows path -> path usable by this process."""
    if IS_WINDOWS:
        return Path(native)
    m = _DRIVE.match(native)
    if m:
        return Path(f"/mnt/{m.group(1).lower()}") / m.group(2).replace("\\", "/")
    m = _WSL_SHARE.match(native)
    if m:  # \\wsl.localhost\<distro>\home\… is this machine's own /home/…
        return Path((m.group(1) or "\\").replace("\\", "/"))
    return Path(native)


def to_native(local: Path | str) -> str:
    """Local path -> Windows path (what is stored and shown)."""
    s = str(local)
    if IS_WINDOWS:
        return str(Path(s).resolve()) if s else s
    m = _MNT.match(Path(s).as_posix())
    if m:
        return str(PureWindowsPath(f"{m.group(1).upper()}:\\") / (m.group(2) or "").replace("/", "\\"))
    distro = os.environ.get("WSL_DISTRO_NAME")
    if IS_WSL and distro and s.startswith("/"):  # a folder inside WSL, as Explorer reaches it
        return f"\\\\wsl.localhost\\{distro}" + s.replace("/", "\\")
    return s


class Runner:
    """Real side effects. Tests pass a fake with the same methods."""

    def running(self, image: str = "hl.exe") -> bool:
        exe = "tasklist" if IS_WINDOWS else "tasklist.exe"
        try:
            out = subprocess.run(
                [exe, "/FI", f"IMAGENAME eq {image}", "/NH"],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=20,
                **NO_WINDOW,
            ).stdout
        except (OSError, subprocess.TimeoutExpired):
            return False
        return image.lower() in out.lower()

    def set_won_video(self, values: dict[str, int]) -> None:
        """Values the WON clients read for their video mode (what
        Configuration > Video saves). Shared by every WON install."""
        if IS_WINDOWS:
            import winreg

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Half-Life\Settings") as k:
                for name, v in values.items():
                    winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, int(v))
            return
        for name, v in values.items():
            subprocess.run(
                ["reg.exe", "add", WON_SETTINGS_KEY, "/v", name, "/t", "REG_DWORD", "/d", str(int(v)), "/f"],
                capture_output=True,
                timeout=20,
                check=True,
            )

    def spawn(self, exe: Path, args: list[str], cwd: Path) -> None:
        """Start the game detached: closing the app does not close the game.
        Its window is then brought in front of the browser (see focus.py)."""
        self._start(exe, args, cwd)
        from oldschool.player.focus import bring_to_front

        threading.Thread(target=bring_to_front, args=(exe.name,), name="oldschool-front", daemon=True).start()

    def _start(self, exe: Path, args: list[str], cwd: Path) -> None:
        if IS_WINDOWS:
            flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            subprocess.Popen([str(exe), *args], cwd=str(cwd), creationflags=flags, close_fds=True)
        else:
            subprocess.Popen(
                [str(exe), *args],
                cwd=str(cwd),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

    def open_folder(self, folder: Path) -> None:
        """Show a folder in Windows Explorer."""
        native = to_native(folder.resolve())
        exe = "explorer" if IS_WINDOWS else "explorer.exe"
        subprocess.Popen([exe, native], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
