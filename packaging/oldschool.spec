# PyInstaller recipe for OldschoolCSDemos.exe (one folder, no console window).
# Run by `python3 tasks.py package`, with the Windows build environment.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 (set by PyInstaller)
BUILD = ROOT / "packaging" / "build"
sys.path.insert(0, str(ROOT / "backend"))

datas = [(str(ROOT / "frontend" / "dist"), "frontend_dist")]
datas += collect_data_files("oldschool", includes=["**/*.sql"])  # database migrations
if (BUILD / "tools").is_dir():
    datas.append((str(BUILD / "tools"), "tools"))  # 7-Zip, for RAR 1.5/2.0 archives

hidden = collect_submodules("uvicorn") + collect_submodules("oldschool") + ["pystray._win32"]

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "launch.py")],
    pathex=[str(ROOT / "backend")],
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "pytest", "_pytest"],
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OldschoolCSDemos",
    console=False,
    icon=str(BUILD / "app.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="OldschoolCSDemos")  # noqa: F821
