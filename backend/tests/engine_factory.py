"""Fake game installs (empty files with the right names) for tests."""

from pathlib import Path


def make_install(root: Path, name: str, release: str = "1.5", steam: bool = False, steam_api: bool = False,
                 maps: tuple[str, ...] = (), skip: tuple[str, ...] = ()) -> Path:  # fmt: skip
    d = root / name
    files = ["hl.exe", "hw.dll", "cstrike/cl_dlls/client.dll"]
    if steam:
        files.append("FileSystem_Steam.dll")
    if steam_api:
        files.append("steam_api.dll")
    for f in files:
        if f in skip:
            continue
        p = d / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
    (d / "cstrike" / "maps").mkdir(parents=True, exist_ok=True)
    if "liblist.gam" not in skip:
        (d / "cstrike" / "liblist.gam").write_text(f'game "Counter-Strike"\nversion "{release}"\n')
    for m in maps:
        (d / "cstrike" / "maps" / f"{m}.bsp").write_bytes(b"BSP")
    return d


class FakeRunner:
    """Records what Play would do instead of doing it."""

    def __init__(self, running: bool = False):
        self.is_running = running
        self.video: list[dict] = []
        self.spawned: list[tuple] = []
        self.opened: list = []

    def running(self, image: str = "hl.exe") -> bool:
        return self.is_running

    def set_won_video(self, values: dict) -> None:
        self.video.append(values)

    def spawn(self, exe, args, cwd) -> None:
        self.spawned.append((exe, list(args), cwd))

    def open_folder(self, folder) -> None:
        self.opened.append(folder)
