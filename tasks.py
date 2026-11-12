#!/usr/bin/env python3
"""Developer tasks. Run from the repository root (WSL on Windows):

    python3 tasks.py check      # everything a change must pass (backend + frontend)
    python3 tasks.py test       # backend + frontend tests only
    python3 tasks.py dev        # backend on 127.0.0.1:27960 (serves frontend/dist); --port, --data-dir DIR
    python3 tasks.py build      # frontend production build into frontend/dist
    python3 tasks.py api-types  # regenerate frontend/src/api/schema.d.ts from the backend's OpenAPI
    python3 tasks.py package    # Windows app + setup program into packaging/dist (needs Windows Python 3.12 + Inno Setup)

Needs uv and Node.js on PATH (see CONTRIBUTING.md).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
ENV = {
    **os.environ,
    # The virtualenv lives on the Linux side: faster than /mnt/<drive> and no NTFS symlink issues.
    "UV_PROJECT_ENVIRONMENT": os.environ.get("UV_PROJECT_ENVIRONMENT", str(Path.home() / ".cache/oldschool/venv")),
    "UV_LINK_MODE": "copy",
}


def run(cmd: list[str], cwd: Path) -> None:
    print(f"\n$ {' '.join(cmd)}   ({cwd.relative_to(ROOT) or '.'})", flush=True)
    if subprocess.run(cmd, cwd=cwd, env=ENV).returncode:
        sys.exit(f"FAILED: {' '.join(cmd)}")


def backend_check() -> None:
    run(["uv", "sync", "--locked", "--extra", "desktop"], BACKEND)
    run(["uv", "run", "ruff", "check", "."], BACKEND)
    run(["uv", "run", "ruff", "format", "--check", "."], BACKEND)
    run(["uv", "run", "pytest"], BACKEND)


OPENAPI_TS = "openapi-typescript@7.13.0"  # run through npx: it pins TypeScript 5, the app uses 6
SCHEMA_TS = FRONTEND / "src" / "api" / "schema.d.ts"


def api_types(check: bool = False) -> None:
    """Dump the OpenAPI schema and turn it into TypeScript types. With
    ``check``, fail when the committed types are out of date."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        spec = Path(tmp) / "openapi.json"
        out = Path(tmp) / "schema.d.ts"
        code = (
            "import json,sys,tempfile; from pathlib import Path; from oldschool.api.app import create_app;"
            "d=tempfile.mkdtemp(); print(json.dumps(create_app(Path(d)/'x.sqlite').openapi(), indent=1))"
        )
        with spec.open("w") as f:
            if subprocess.run(["uv", "run", "python", "-c", code], cwd=BACKEND, env=ENV, stdout=f).returncode:
                sys.exit("FAILED: could not export the OpenAPI schema")
        run(["npx", "-y", OPENAPI_TS, str(spec), "-o", str(out)], FRONTEND)
        new = out.read_text(encoding="utf-8")
    if check:
        if not SCHEMA_TS.exists() or SCHEMA_TS.read_text(encoding="utf-8") != new:
            sys.exit("FAILED: frontend/src/api/schema.d.ts is out of date: run python3 tasks.py api-types")
        print("API types up to date")
    else:
        SCHEMA_TS.parent.mkdir(parents=True, exist_ok=True)
        SCHEMA_TS.write_text(new, encoding="utf-8")
        print(f"wrote {SCHEMA_TS.relative_to(ROOT)}")


def frontend_check() -> None:
    if not (FRONTEND / "node_modules").exists():
        run(["npm", "ci", "--no-fund", "--no-audit"], FRONTEND)
    api_types(check=True)
    run(["npm", "run", "typecheck"], FRONTEND)
    run(["npm", "run", "lint"], FRONTEND)
    run(["npm", "test"], FRONTEND)
    run(["npm", "run", "build"], FRONTEND)


# ------------------------------------------------------------------ Windows package

PACKAGING = ROOT / "packaging"
PYINSTALLER = "pyinstaller==6.16.0"


def wsl_to_win(p: Path) -> str:
    return subprocess.run(["wslpath", "-w", str(p)], capture_output=True, text=True, check=True).stdout.strip()


def win_to_wsl(p: str) -> Path:
    return Path(subprocess.run(["wslpath", "-u", p], capture_output=True, text=True, check=True).stdout.strip())


def win_env(name: str) -> str:
    out = subprocess.run(["cmd.exe", "/c", f"echo %{name}%"], capture_output=True, text=True, cwd="/mnt/c").stdout
    return out.strip()


def package(skip_tests: bool = False) -> None:
    """Build OldschoolCSDemos.exe (PyInstaller, one folder) and the setup
    program (Inno Setup), on Windows, driven from WSL."""
    import shutil

    sys.path.insert(0, str(BACKEND))
    from oldschool import __version__

    local = win_to_wsl(win_env("LOCALAPPDATA"))
    work = local / "oldschool-build"  # Windows-side build environment (fast, not on the repository drive)
    venv_py = work / "venv" / "Scripts" / "python.exe"
    build, dist = PACKAGING / "build", PACKAGING / "dist"
    build.mkdir(parents=True, exist_ok=True)

    run(["npm", "run", "build"], FRONTEND)
    if not venv_py.exists():
        py = shutil.which("py.exe")
        if not py:
            sys.exit("FAILED: Windows Python launcher (py.exe) not found: install Python 3.12 for Windows")
        run([py, "-3.12", "-m", "venv", wsl_to_win(work / "venv")], ROOT)
    req = build / "requirements-windows.txt"
    with req.open("w") as f:
        if subprocess.run(
            ["uv", "export", "--frozen", "--all-groups", "--extra", "desktop", "--no-hashes", "--no-emit-project"],
            cwd=BACKEND, env=ENV, stdout=f,
        ).returncode:  # fmt: skip
            sys.exit("FAILED: uv export")
    run([str(venv_py), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", wsl_to_win(req), PYINSTALLER], ROOT)

    if not skip_tests:  # the same tests, natively on Windows
        run([str(venv_py), "-m", "pytest", "-q", "-p", "no:cacheprovider"], BACKEND)

    icon = build / "app.ico"
    code = f"import sys; sys.path.insert(0, r'{wsl_to_win(BACKEND)}'); from oldschool.icon import save_ico; save_ico(r'{wsl_to_win(icon)}')"
    run([str(venv_py), "-c", code], ROOT)
    seven = Path("/mnt/c/Program Files/7-Zip")
    tools = build / "tools" / "7-Zip"
    if (seven / "7z.exe").exists():  # 7-Zip may be redistributed (GNU LGPL + unRAR restriction): see its License.txt
        tools.mkdir(parents=True, exist_ok=True)
        for name in ("7z.exe", "7z.dll", "License.txt"):
            target = tools / name
            if target.exists():
                target.chmod(0o666)  # copied from Program Files read-only
                target.unlink()
            if (seven / name).exists():
                shutil.copyfile(seven / name, target)
    else:
        print("note: 7-Zip not found: RAR 1.5/2.0 archives will need a 7-Zip install on the user's PC")

    shutil.rmtree(dist / "OldschoolCSDemos", ignore_errors=True)
    run(
        [str(venv_py), "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
         "--distpath", wsl_to_win(dist), "--workpath", wsl_to_win(work / "pyinstaller"), wsl_to_win(PACKAGING / "oldschool.spec")],
        ROOT,
    )  # fmt: skip

    # Smoke test of the built app: starts, serves the page, imports a dropped demo with its worker processes.
    smoke = work / "smoke"
    shutil.rmtree(smoke, ignore_errors=True)
    (smoke / "Drop").mkdir(parents=True)
    from tests.demo_factory import MATCH, build_round_demo

    (smoke / "Drop" / "smoke.dem").write_bytes(build_round_demo(MATCH))
    port = 27990
    env = {**os.environ, "OLDSCHOOL_DATA_DIR": str(smoke), "OLDSCHOOL_PORT": str(port), "OLDSCHOOL_NO_BROWSER": "1",
           "OLDSCHOOL_NO_TRAY": "1", "OLDSCHOOL_EXIT_AFTER": "60",
           "WSLENV": "OLDSCHOOL_DATA_DIR/p:OLDSCHOOL_PORT:OLDSCHOOL_NO_BROWSER:OLDSCHOOL_NO_TRAY:OLDSCHOOL_EXIT_AFTER"}  # fmt: skip
    proc = subprocess.Popen([str(dist / "OldschoolCSDemos" / "OldschoolCSDemos.exe")], env=env, cwd=str(smoke))
    check = subprocess.run([str(venv_py), wsl_to_win(PACKAGING / "smoke_check.py"), f"http://127.0.0.1:{port}", "50"])
    ok = check.returncode == 0
    proc.wait(timeout=90)
    log = smoke / "logs" / "app.log"
    if not ok:
        print(log.read_text(encoding="utf-8", errors="replace")[-3000:] if log.exists() else "(no log)")
        sys.exit("FAILED: smoke test of the built app (server, page or import)")
    print("smoke test: the built app served the page and imported a dropped demo")

    iscc = next(
        (p for p in (local / "Programs" / "Inno Setup 6" / "ISCC.exe", Path("/mnt/c/Program Files (x86)/Inno Setup 6/ISCC.exe")) if p.exists()),
        None,
    )
    if not iscc:
        sys.exit("FAILED: Inno Setup 6 not found (winget install JRSoftware.InnoSetup)")
    run([str(iscc), "/Q", f"/DAppVersion={__version__}", wsl_to_win(PACKAGING / "installer.iss")], PACKAGING)
    setup = dist / f"OldschoolCSDemos-Setup-{__version__}.exe"
    print(f"\nBuilt {wsl_to_win(setup)} ({setup.stat().st_size / 1024**2:.0f} MB)")


def main() -> None:
    task = sys.argv[1] if len(sys.argv) > 1 else "check"
    if task == "check":
        backend_check()
        frontend_check()
        print("\nALL CHECKS PASSED")
    elif task == "test":
        run(["uv", "run", "pytest"], BACKEND)
        run(["npm", "test"], FRONTEND)
    elif task == "api-types":
        api_types()
    elif task == "build":
        run(["npm", "run", "build"], FRONTEND)
    elif task == "package":
        package(skip_tests="--skip-tests" in sys.argv)
    elif task == "dev":
        # Optional: OLDSCHOOL_ENGINE_ROOTS (game install folders, ';'-separated) and OLDSCHOOL_TMP
        # (a temporary folder Windows' 7z.exe can reach) come from the environment.
        run(["uv", "run", "python", "-m", "oldschool.main", *sys.argv[2:]], BACKEND)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
