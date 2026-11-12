---
name: windows-release
description: Bump the version, build the Windows app and its setup program, smoke-test it and publish a GitHub release. Use when shipping a new version or when the packaging (PyInstaller spec, Inno Setup script, desktop launcher) changes.
---

# Windows release

## Version

The version appears in these places; change them together:

- `backend/pyproject.toml` (`version`), then `cd backend && uv lock`
- `backend/oldschool/__init__.py` (`__version__`, shown at the top right of the app)
- `README.md` (version badge) and the example in `.github/ISSUE_TEMPLATE/bug.yml`
- the setup file name follows automatically (`OldschoolCSDemos-Setup-<version>.exe`)

Add a dated line to `docs/DECISIONS.md` for what the version changes.

## Build

`python3 tasks.py package` (from WSL; needs Windows Python 3.12 with the `py` launcher and Inno Setup 6):

1. frontend build;
2. a Windows virtualenv (`%LOCALAPPDATA%\oldschool-build\venv`) from `uv export`;
3. the backend tests on Windows (skip with `--skip-tests` only for a rebuild of tested code);
4. the icon (drawn by `oldschool/icon.py`), 7-Zip copied into `packaging/build/tools`;
5. PyInstaller (`packaging/oldschool.spec`, onedir, no console);
6. **smoke test**: the built `.exe` runs with its own data folder, serves the page and imports a dropped demo (`packaging/smoke_check.py`, run by Windows Python because WSL cannot reach a Windows server on 127.0.0.1);
7. Inno Setup (`packaging/installer.iss`) → `packaging/dist/OldschoolCSDemos-Setup-<version>.exe`.

Packaging rules: no Valve file in the build; per-user install, no administrator rights; `AppMutex=OldschoolCSDemosLibraryReplayer` (the mutex name in `desktop.py` for the default library); the library in `%LOCALAPPDATA%\OldschoolCSDemos` survives updates and, unless the user says otherwise, uninstalls.

## Manual check

Run checklist `C-M5` in `docs/CHECKLISTS.md` (install, Welcome page, drag demos, second start, tray menu, install over the previous version, uninstall), and the game checklists the release touches.

## Publish

```bash
cd packaging/dist && sha256sum OldschoolCSDemos-Setup-X.Y.Z.exe > OldschoolCSDemos-Setup-X.Y.Z.exe.sha256
gh release create vX.Y.Z --target main --title "Oldschool CS Demos X.Y.Z" --notes-file <notes.md> --latest \
  packaging/dist/OldschoolCSDemos-Setup-X.Y.Z.exe packaging/dist/OldschoolCSDemos-Setup-X.Y.Z.exe.sha256
```

Release notes: what changed for the user, how to install (SmartScreen: More info → Run anyway; installing over the previous version keeps the library), where to get the game versions. Never attach game files to a release.
