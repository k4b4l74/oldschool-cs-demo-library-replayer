"""The Windows app: starts the local server, opens the library in the
browser and stays in the notification area (tray) until Quit.

This is what ``OldschoolCSDemos.exe`` runs. Starting it again while it runs
only opens the browser on the running one. Settings for tests:
OLDSCHOOL_PORT (first port tried), OLDSCHOOL_NO_BROWSER=1, OLDSCHOOL_NO_TRAY=1,
OLDSCHOOL_EXIT_AFTER=<seconds> (stop by itself; the build's smoke test).
"""

from __future__ import annotations

import hashlib
import multiprocessing
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

MUTEX_NAME = "OldschoolCSDemosLibraryReplayer"  # also known by the installer (AppMutex)
PORT_RANGE = 20


def _quiet_streams() -> None:
    """A windowed .exe has no console: give libraries somewhere to write."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115


def mutex_name(data_dir: Path) -> str:
    """One running copy per library folder. The usual library keeps the plain
    name (the setup program checks it); another folder, like the build's
    smoke test, gets its own, so it can run beside the installed app."""
    if "OLDSCHOOL_DATA_DIR" not in os.environ:
        return MUTEX_NAME
    digest = hashlib.sha1(str(data_dir).lower().encode()).hexdigest()[:12]
    return f"{MUTEX_NAME}-{digest}"


def already_running(name: str = MUTEX_NAME) -> bool:
    """Windows named mutex: True when another copy of the app holds it."""
    if os.name != "nt":
        return False
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW(None, False, name)  # kept until the process ends
    return kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def free_port(host: str, first: int) -> int:
    for port in range(first, first + PORT_RANGE):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
            except OSError:
                continue
            return port
    raise SystemExit(f"no free port between {first} and {first + PORT_RANGE - 1}")


def open_browser(url: str) -> None:
    if os.environ.get("OLDSCHOOL_NO_BROWSER") != "1":
        webbrowser.open(url)


def tray(url: str, drop: Path, quit_app) -> None:
    """Blocks until Quit. Without a tray (or pystray), waits for the server."""
    try:
        import pystray

        from oldschool.icon import draw
    except ImportError:
        return quit_app(wait_only=True)

    def on_quit(icon, _item):
        icon.visible = False
        icon.stop()

    def open_drop(_icon, _item):
        if os.name == "nt":
            os.startfile(drop)  # noqa: S606

    menu = pystray.Menu(
        pystray.MenuItem("Open the library", lambda _i, _m: webbrowser.open(url), default=True),
        pystray.MenuItem("Open the Drop folder", open_drop),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )
    pystray.Icon("oldschool", draw(64), "Oldschool CS Demos", menu).run()
    quit_app()


def main() -> None:
    multiprocessing.freeze_support()  # import worker processes re-run this .exe
    _quiet_streams()

    import uvicorn

    from oldschool.api.app import create_app
    from oldschool.config import DEFAULT_PORT, HOST, Paths, default_data_dir, frontend_dist
    from oldschool.main import log_to_file

    paths = Paths(default_data_dir()).ensure()
    port_file = paths.root / "app.port"
    if already_running(mutex_name(paths.root)):
        port = port_file.read_text().strip() if port_file.exists() else str(DEFAULT_PORT)
        open_browser(f"http://{HOST}:{port}/")
        return

    log_file = log_to_file(paths.root / "logs" / "app.log")
    port = free_port(HOST, int(os.environ.get("OLDSCHOOL_PORT", DEFAULT_PORT)))
    port_file.write_text(str(port))
    app = create_app(paths.database, frontend_dist(), store=paths.store, data_dir=paths.root, background=True)
    app.state.log_file = str(log_file)
    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=port, log_config=None, log_level="info"))
    thread = threading.Thread(target=server.run, name="oldschool-server")
    thread.start()
    deadline = time.monotonic() + 60
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.1)
    url = f"http://{HOST}:{port}/"
    if server.started:
        open_browser(url)
    exit_after = float(os.environ.get("OLDSCHOOL_EXIT_AFTER", "0"))
    if exit_after:
        threading.Timer(exit_after, lambda: setattr(server, "should_exit", True)).start()

    def quit_app(wait_only: bool = False) -> None:
        if not wait_only:
            server.should_exit = True
        thread.join()

    if os.environ.get("OLDSCHOOL_NO_TRAY") == "1":
        quit_app(wait_only=True)
    else:
        tray(url, paths.drop, quit_app)


if __name__ == "__main__":
    main()
