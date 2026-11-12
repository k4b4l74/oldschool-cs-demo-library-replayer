# Architecture

How Oldschool CS Demos Library Replayer works, as built in version 1.0. For setup and rules see [CONTRIBUTING.md](../CONTRIBUTING.md); for the reasons behind choices see [DECISIONS.md](DECISIONS.md).

## 1. Goal

A Windows application anyone can install to **collect, identify, browse and replay old Counter-Strike demos (CS 1.0 – 1.6)**. The user adds demos or demo archives; the app:

1. imports them, whatever the archive format or nesting;
2. identifies release, map, teams, players, SteamIDs, server, scores, rounds and kill feed;
3. groups them into matches;
4. shows everything in a local web interface;
5. plays any demo, or any round of it, in the matching game engine.

Out of scope for now: cloud or shared libraries, accounts, editing demos (beyond the temporary playback copy), CS:Source / CS:GO demos (`HL2DEMO`, recognised and refused).

## 2. Constraints

| Constraint | Consequence |
| --- | --- |
| Playback needs the original `hl.exe` engines, which only run on Windows | A Windows-only app. Development happens in WSL; the app is built and tested on Windows. |
| `hl.exe`, engine DLLs, game files and maps are Valve's | The app ships no game files. It finds engine installs the user already has (§8.1). Everything except playback works without any engine. |
| Old engines only play their own network protocol (43 / 45 / 46 / 47 / 48) | An engine registry maps each kind of demo to a compatible install (§8.2). |
| WON `hl.exe` 1.1.0.6 – 1.1.1.0 quirks | Install paths are checked (no `.` in the folders before `hl.exe`, no `-w`/`-h`), `-newdat` is passed, and the window size is written to `HKCU\Software\Valve\Half-Life\Settings\EngineMode*` before launch (§8.3). |
| Demo archives come as zip, rar (including RAR 1.5/2.0), 7z, ace, tar/gz/bz2, nested | One module reads them all: Windows' `tar.exe` (libarchive), a bundled 7-Zip for what libarchive cannot read, and the pure-Python `acefile`. |
| Unsigned `.exe` files trigger SmartScreen, and one-file PyInstaller builds attract antivirus false positives | PyInstaller **onedir** build and an Inno Setup installer. The app is not code-signed. |

## 3. Overview

```
┌──────────────────────── user's Windows PC ──────────────────────────┐
│                                                                      │
│  Browser ── http://127.0.0.1:<port> ──┐                              │
│    React + TypeScript UI               │                              │
│                                        ▼                              │
│  OldschoolCSDemos.exe  (Python, frozen with PyInstaller)              │
│   ├─ API server (FastAPI + Uvicorn, localhost only)                   │
│   ├─ Import jobs: one thread + worker processes ◄── Drop folder       │
│   ├─ Parser and identification                                        │
│   ├─ Store (content-addressed demo copies)                            │
│   ├─ SQLite database (WAL)                                            │
│   └─ Player: engine registry, round jump, keys, launches hl.exe ──► CS│
│                                                                      │
│  Tray icon: Open the library · Open the Drop folder · Quit           │
└──────────────────────────────────────────────────────────────────────┘
```

Because the server runs on the user's machine, ▶ Play simply calls the local API and the server starts the game: no protocol handler, no file association.

The server binds `127.0.0.1` only. Requests that change something must carry the `X-Oldschool: 1` header and a same-site `Origin`, so other web pages cannot drive the API.

## 4. Technology

| Layer | Choice | Why |
| --- | --- | --- |
| Backend | Python 3.12 | The demo parser and identification logic are Python. Parsing is about 0.1 s per demo; archive I/O is the bottleneck, not the language. |
| Web framework | FastAPI + Uvicorn | Typed models and an OpenAPI schema from which the frontend's TypeScript types are generated. |
| Database | SQLite (stdlib `sqlite3`, WAL), plain SQL, numbered migration files | One file, no setup, plenty for one user (100k demos, millions of kills). No ORM: queries are explicit and tested. |
| Background work | A job table in SQLite, one job thread, a process pool for reading files | Survives restarts, visible in the UI, no external queue. |
| Frontend | React 19 + TypeScript + Vite, TanStack Query, React Router | Mainstream, typed, fast to build. |
| Desktop shell | The default browser + a notification-area icon (pystray) | No extra web engine to ship; drag and drop from Explorer works. |
| Packaging | PyInstaller (onedir) + Inno Setup | The usual pair for Python desktop apps on Windows. |
| Tests | pytest, Vitest + Testing Library, manual in-game checklists | Covers parser, API and UI without the game; the game itself is checked by hand. |

## 5. Import

Every import is a **job** (`jobs` table: kind `import` or `reanalyse`, origin `drop`, `folder` or `retry`), and every file it handles gets a row in `job_files` (imported, already, no-demo, failed, missing, reanalysed; reason; where a Drop file was moved). One job runs at a time in a thread started with the server; its files are read by worker processes, and only the job thread writes to the database. A job interrupted by closing the app is queued again at the next start, and files already done are skipped.

For each file:

1. **Duplicates first.** A worker hashes the file (SHA-1) and asks the database, read-only, whether it is known: a file already in the library costs one hash.
2. **Expand.** Archives are walked recursively through `archives.py`. Every member is recorded with its chain (archive → inner archive → file), size and timestamp.
3. **Store demos.** Each `.dem` is hashed; a new one is written once to `store/demos/ab/<sha1>.dem.gz`, whatever archive it came from. For a collection read in place (`--no-demo-copies`, or "Read the demos from this folder when played"), only its location is recorded, and Play extracts it and checks its SHA-1.
4. **Parse.** Header, server, players (names over time, SteamIDs, HLTV slot), sides, kill feed, scores, chat, rounds, recorded viewport, duration. Unreadable demos are kept with `parse_error`.
5. **Identify.** Release (network protocol + game fingerprint), team tags and line-ups (clustered across side swaps), POV or HLTV, and a year estimate **with its basis** (HLTV name stamp, member file date, folder name). These are always labelled estimates, never a played date.
6. **Group into matches.** Demos from one source sharing a map and line-ups become one match (halves, overtime). Per-match totals (demos, length, kills, file date) are stored so lists stay fast.

**Ways in:**

- **Drop folder** (`<data>\Drop`): a watcher checks it every second; an entry (file or folder) is queued once it has not changed for 2 s. Imported files are kept in `store/originals` and leave the Drop folder. Nothing is deleted: failures go to `Drop\_failed` with a `.txt` reason, duplicates to `_already imported`, other files to `_skipped`, stopped imports to `_cancelled`. Folders starting with `_` or `.` belong to the app.
- **Uploads:** files dragged onto any page are sent with `PUT /api/drop?name=` into `Drop\.incoming`, then moved into the Drop folder when complete. Browsers cannot send folders reliably, so folders go through "Import a folder" or the Drop folder.
- **Import a folder:** a collection kept in place, with its demos copied into the store or read from the folder when played. Running it again only reads files not seen at the same path and size. `originals.label` keeps each file's path relative to that folder, because folder names feed the team and year guesses.

**Re-analysis** reads each original again (the kept copy, else its source) and rebuilds its members, demo data and matches; the result equals a fresh import, and matches get new ids. "Re-analyse the older ones" picks files read by a parser older than `importer.PARSE_VERSION`.

## 6. Data model

Full DDL in `backend/oldschool/db/schema/` (migrations `0001` – `0004`).

```
originals(id, sha1, file_name, size, source_path, mode, kept_path, label, demo_copies, status, demo_count,
          errors, imported_at, analysed_at)
archive_members(id, original_id, chain, name, size, mtime, mtime_basis, demo_sha1, text_content)
demos(sha1, size, store_path, demo_protocol, net_protocol, map, game_dir, map_crc, duration_s, kill_count,
      release, release_basis, recorder_kind, recorder_slot, server_name, viewport_w, viewport_h,
      parse_version, parse_error, analysis)
matches(id, original_id, map, team1_id, team2_id, release, release_basis, year_est, year_basis, pov, sides,
        team_basis, library_name, servers, scores, demo_count, duration_s, kill_count, file_date, created_at)
match_demos(match_id, demo_sha1, part_no, label)        halves, overtime
teams(id, tag_as_printed, norm_tag)                     never merged automatically
players(id, display_name, note)                         identity; merges will be explicit user actions
player_names(id, name_as_printed, steamid, player_id)   names as printed
demo_players, match_players                             per-demo and per-match line-ups with K/D/HS
rounds(id, demo_sha1, no, start_t, start_basis, end_t, winner, reason, score_ct, score_t)
kills(id, demo_sha1, round_id, t, killer_name_id, victim_name_id, weapon, headshot, killer_side, victim_side)
chat(id, demo_sha1, t, sender_entity, text)
engines(id, path, name, kind, build, protocols, releases, status, detected, overrides, source, enabled, missing)
engine_routes(protocol, release, engine_id)             the user's choice per kind of demo
jobs, job_files                                         imports (§5)
settings(key, value)
```

Identity rules: names and tags are stored **as printed**; same-name players and same-tag teams are never merged automatically; every estimated value carries its basis. Times inside a demo are demo-clock seconds.

## 7. Local API

```
GET  /api/health  /api/stats
GET  /api/matches?q=&player=&team=&steamid=&map=&release=&year_from=&year_to=&pov=&sort=&dir=&page=
GET  /api/matches/{id}            line-ups, demos (with the engine that would play each), sources
GET  /api/demos/{sha1}/rounds     rounds and kill feed
GET  /api/players?q=  /api/players/{id}    GET /api/teams?q=  /api/teams/{id}
GET  /api/engines                 installs and routes      POST /api/engines {path}  POST /api/engines/scan
PATCH /api/engines/{id}  DELETE /api/engines/{id}  PUT /api/routes
GET/PUT /api/settings             folders, window size, round-jump speeds, controls, own key binds
POST /api/play {sha1, seek?}      starts the engine; returns which one, or why not
GET  /api/imports  /api/imports/{id}   POST /api/imports {path, copy_demos}  POST /api/imports/{id}/cancel
POST /api/imports/files/{id}/retry  POST /api/imports/reanalyse  PUT /api/drop?name=  POST /api/drop/open
```

**Search syntax** (`q`, `player`, `team`): `a|b` any of them, `a + b` all of them in the same match (`aAa + GG` in `team`: matches between both), `*` anything in between, `"…"` the text as typed. Matching is case-insensitive "contains" (SQL `LIKE`, with `%` and `_` escaped). `steamid` is an exact ID.

## 8. Playback

### 8.1 Engine installs

The app scans folders for sub-folders holding an `hl.exe`: the folders given by the user (Welcome page, Settings), `<data>\Engines`, and `OLDSCHOOL_ENGINE_ROOTS` (development). For each install it detects:

- the family: WON (1.0 – 1.5) or a CS 1.6 build (`FileSystem_Steam.dll`);
- build and network protocol, from the folder name (`CS13_P45_hl1108`, `CS16_P47_build3248`), a manifest (`INSTALL-PROVENANCE.json` / `engine.json`) or the build;
- the CS release (`cstrike/liblist.gam`);
- the round-jump method, window mode and launch options;
- problems: missing files, WON path rules.

Users can change any detected value (stored apart as `overrides`, kept across rescans), disable an install, or forget it.

| Demos | Engine that plays them |
| --- | --- |
| protocol 43 (CS 1.0 / 1.1) | WON 1.1.0.6 |
| CS 1.3 (protocol 45) | WON 1.1.0.8 |
| CS 1.4 (protocol 45) | WON 1.1.0.9 |
| CS 1.5 (protocol 46) | WON 1.1.1.0 |
| CS 1.6 on protocol 46 (2003, FAMAS / Galil) | 1.6 build 2511 (later engines cannot read protocol 46) |
| protocol 47 | 1.6 build 2603 or 3248 |
| protocol 48 | 1.6 build 4554 (no Steam needed) |

### 8.2 Routing

For each kind of demo (network protocol + release), the user's choice in Settings wins; otherwise an enabled install of the same protocol and release, newest build first. Protocol 46 never mixes CS 1.5 and CS 1.6. The match page shows which install will play each demo, or why none can.

### 8.3 Launch

1. Write the demo, decompressed, to `<install>\cstrike\csdemoplay.dem` (old engines dislike `-` and long names), with the round jump and the keys added to that copy (§8.4, §8.5).
2. Copy a missing map `.bsp` from another install or a user map folder (never from the internet).
3. WON engines: write the window size and mode to the registry. CS 1.3 / 1.4 size the window to the demo's recorded viewport, others use the size from Settings.
4. Start `hl.exe` detached with the install's options, `+exec oldschool.cfg` and `+playdemo csdemoplay` (WON engines also get `+connect` to skip their launcher menu).
5. Only one old engine runs at a time; Play refuses while one is open.
6. Bring the game window to the front (`player/focus.py`): Windows lets only the program in use choose the front window, so a game started by a background server can open behind the browser. The app waits for the `hl.exe` window and pushes it in front until it stays there.

### 8.4 Round jump

The old engines have no "go to time" command. The playback copy is edited instead:

- **CS 1.4 – 1.6** (engines 1.1.0.9+): a console-command frame (type 3, as `record` writes for typed commands) and an `svc_stufftext` switch `host_framerate <rate>; nosound 1` on at the first playback frame and `host_framerate 0; nosound 0` back at the target time. The command line starts fast too.
- **CS 1.0 / 1.1 / 1.3** (engines 1.1.0.6, 1.1.0.8): these engines run demo commands but ignore `host_framerate` during playback, so the copy's timestamps before the target are divided by a factor (×20), and sound is muted until the target.

Every injected command echoes a marker (`seek: frame`, `seek: stufftext`…) into `qconsole.log` for diagnosis. `host_framerate` and `nosound` are not saved to `config.cfg`, so quitting mid-jump leaves no trace.

### 8.5 Keys in the game

A Controls page lists the actions worth a key while watching (HLTV free camera, jump = camera mode, fire / secondary fire = next / previous player, scores, HUD, screenshot, console, pause, slow / fast / normal speed, stop, quit) with a key and an alternate, plus the user's own commands. Before each Play the app writes `cstrike\oldschool.cfg` in the install used:

- aliases for the toggles (HUD, pause), then `bind` lines;
- `unbind` for keys the app set before and no longer uses (read back from the previous file), because the game saves current binds into its own `config.cfg` when it closes;
- the file runs from the command line **and again one second into the demo** (injected like the round jump): the 1.1.0.8 engine runs its `config.cfg`, which begins with `unbindall`, after the command line.

Key names are the engine's. Engines before the 2013 Steam versions read key *positions* with a US layout, so the game's W A S D are Z Q S D on a French keyboard; the page shows keys as printed on the user's keyboard (the browser's keyboard map) and stores the engine's names.

## 9. The Windows app

- **`OldschoolCSDemos.exe`** (`desktop.py`, PyInstaller onedir, no console window) starts the server on 127.0.0.1 (port 27960 or the next free one, written to `<data>\app.port`), opens the library in the default browser and stays in the notification area. A second start only opens a browser tab: a named mutex per library folder (`OldschoolCSDemosLibraryReplayer` for the default one, also known to the installer).
- **Data:** `%LOCALAPPDATA%\OldschoolCSDemos` (library, store, Drop, Engines, `logs\app.log`).
- **Setup** (`packaging/installer.iss`, Inno Setup 6): per-user install in `%LOCALAPPDATA%\Programs\Oldschool CS Demos`, no administrator rights, English or French. Uninstall asks whether to delete the library too (default: keep it).
- **Bundled:** the built pages, the migrations, and 7-Zip (`7z.exe` / `7z.dll` with its licence) for RAR 1.5/2.0. `tar.exe` comes with Windows 10/11. No Valve file.
- **First start:** a Welcome page asks for the folder with the game installs and explains the three ways to add demos.
- **Build:** `python3 tasks.py package` from WSL: frontend build, a Windows Python 3.12 virtualenv, the backend tests on Windows, the icon (drawn in code), PyInstaller, a smoke test of the built `.exe` with its own data folder (serves the page, imports a dropped demo), then Inno Setup → `packaging\dist\OldschoolCSDemos-Setup-<version>.exe`.

## 10. Frontend

Pages: **Library** (search and filters kept in the URL), **Match** (line-ups with K/D/HS, each demo's rounds with kill feed and ▶ per round or kill), **Player** and **Team**, **Import** (drop zone, live jobs, per-file results, retry, folder import, re-analysis), **Settings** (installs, routing, folders, window, round-jump speeds, controls), **Welcome**, **Contact**. Files dragged anywhere on the app are uploaded to the Drop folder. Two themes: olive "old CS menus" (default) and light "paper", colours and shapes only.

## 11. Testing

- **Backend:** pytest on synthetic demos (`tests/demo_factory.py` builds GoldSrc demos with players, kills, rounds, HLTV or POV); API tests with FastAPI's test client on temporary databases; Play is tested with a `FakeRunner` that records what would be launched.
- **Frontend:** Vitest + Testing Library with a mocked API.
- **Packaging:** the built `.exe` is started and checked before the setup program is made; the backend tests also run natively on Windows.
- **Corpus:** real demos for local regression checks go in `backend/tests/corpus/` (not committed). [reports/M1-import.md](reports/M1-import.md) compares a 2,104-archive import with a reference catalogue.
- **In game:** [CHECKLISTS.md](CHECKLISTS.md) says exactly what to click and what to expect on each engine.
