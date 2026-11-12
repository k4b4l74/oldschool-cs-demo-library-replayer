---
name: game-playback
description: Work on Play, the round jump, engine detection and routing, the keys file, window size or bringing the game to the front. Holds the hard-won lessons about the old WON and CS 1.6 engines. Use before touching player/*.py or anything that changes what hl.exe receives.
---

# Game playback

## Never start the game yourself

Tests and agents never run `hl.exe` or `POST /api/play` against a real install. Tests pass a `FakeRunner` (`tests/engine_factory.py`) that records `spawned`, `video`, `opened`; fake installs come from `make_install(root, name, release, steam=…, maps=…)`. Anything only the game can show goes into `docs/CHECKLISTS.md` for a person to run, with exact clicks and the expected result.

## The pieces (`backend/oldschool/player/`)

| File | Does |
| --- | --- |
| `engines.py` | scans folders for `hl.exe`; detects family (WON / 1.6 build via `FileSystem_Steam.dll`), build, protocol, release (`cstrike/liblist.gam`), round-jump method, window mode, launch args; problems; user overrides; routing (user choice, else same protocol + release, newest build; protocol 46 never mixes 1.5 and 1.6) |
| `launch.py` | `play()`: demo copy `cstrike/csdemoplay.dem` (+ jump, + keys), missing map copy, WON registry video mode, args, `Runner.spawn` |
| `seek.py` | round jump and `inject_at_start` |
| `controls.py` | Controls actions, defaults, `cstrike/oldschool.cfg` text, unbinding keys no longer used |
| `focus.py` | waits for the `hl.exe` window and brings it in front (ctypes on Windows, PowerShell under WSL) |
| `platform.py` | `Runner` (registry, tasklist, spawn, Explorer), WSL ↔ Windows paths |

## Engine lessons (do not relearn)

- **WON 1.1.0.6 – 1.1.1.0 path rules:** no `.` in the folders before `hl.exe` (a `.dat` check file is named after the path cut at the first dot) and no `-w` / `-h` in the path (switches are matched as substrings of the whole command line). Pass `-newdat`. Name installs `CS13_P45_hl1108`, `CS16_P47_build3248`.
- **WON window size** comes from `HKCU\Software\Valve\Half-Life\Settings\EngineModeW/H/Windowed`, written before launch; only 4:3 modes. CS 1.3 / 1.4 must use the demo's recorded viewport or the view is cut.
- **WON launcher menu:** `+connect` (no argument) skips it.
- **Round jump:** 1.1.0.9+ (CS 1.4 – 1.6) obey `host_framerate` during playback: inject a console-command frame (type 3) **and** an `svc_stufftext` switching it on at the first playback frame and off (`host_framerate 0;nosound 0`) at the target. 1.1.0.6 / 1.1.0.8 (CS 1.0 – 1.3) run demo commands but ignore `host_framerate`: compress the copy's timestamps before the target (`inject_seek_retime`, ×20). Always send both routes and `echo` a marker; `qconsole.log` (`-condebug`) tells which ran.
- **Command-line settings can be undone:** 1.1.0.8 runs its `config.cfg` (which starts with `unbindall`) after the command line. Anything that must stick (the keys) also runs from inside the demo copy, one second into playback (`inject_at_start`).
- **Keys:** engines before the 2013 Steam versions read key positions with a US layout: store engine names (`w`, `kp_plus`, `mouse1`), show the user's printed key (browser keyboard map). The game saves binds into its `config.cfg` on quit, so keys the app stops using must be `unbind`-ed (read back from the previous `oldschool.cfg`).
- **Protocol 46 + CS 1.6** (2003 betas, FAMAS / Galil) only play on build 2511; Steam-era engines cannot read protocol 46. Protocol 48 plays on build 4554 without Steam.
- **Front window:** a game started by a background server opens behind the browser; `focus.py` pushes it in front until it stays there.
- One old engine at a time: Play refuses (409) while `hl.exe` runs.

## Changing playback

1. Unit-test what the copy and the command line contain: `written_demo(...)` bytes, `runner.spawned[0]` args, `runner.video`, the keys file lines (see `tests/test_play.py`, `tests/test_seek.py`).
2. Add or update the checklist (`C-PLAY`, `C-SEEK`, `C-KEYS`) with the versions to try: 1.0/1.1, 1.3, 1.4, 1.5 and the 1.6 builds behave differently.
3. Record what was learned in `docs/ARCHITECTURE.md` §8 and a dated line in `docs/DECISIONS.md`.
