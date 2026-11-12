# Decisions

One dated entry per decision that changes scope or behaviour. Newest last.

## 2026-11-11

- **Product:** an app anyone can install on their own Windows PC. Playback needs the original `hl.exe` engines, so it is Windows-only. No Docker, no cloud, no accounts.
- **Backend in Python**, reusing the calibrated demo parser and identification logic. Speed comes from native archive tools, not from the language.
- **Frontend: React + TypeScript + Vite**, chosen with a future 2D radar / 3D replayer in mind.
- **SQLite** is the source of truth; an export to a "sorted" folder view can come later.
- **Name:** "Oldschool CS Demos Library Replayer".
- **No Valve files in the app.** Game installs are found on the user's PC.
- **Round jump:** an injected console-command frame plus `host_framerate` fast-forward, confirmed in game on CS 1.5 demos. On the older engines the fast-forward is switched on and off *inside the demo*, each switch sent both as a command frame and as an `svc_stufftext`, with `echo` markers in `qconsole.log`.
- **Round jump on 1.1.0.6 / 1.1.0.8 (CS 1.0 – 1.3):** these engines run demo commands but ignore `host_framerate` during playback, so the playback copy's timestamps before the target are compressed (×20). CS 1.4 – 1.6 keep the `host_framerate` method.
- **Engine folder names:** `CS<release>_P<protocol>_hl<engine>` for WON (`CS13_P45_hl1108`) and `CS16_P<protocol>_build<n>` for 1.6 builds: no dots or `-`, because of the WON `hl.exe` path rules.
- **CS 1.6 routing without Steam:** protocol 46 + CS 1.6 → build 2511 (the CS 1.5 engine cannot play 1.6 beta demos with FAMAS / Galil, and later engines cannot read protocol 46); protocol 47 → build 3248 (or 2603); protocol 48 → build 4554. No demo in a 66,000-demo catalogue uses a protocol above 48, the last GoldSrc protocol.
- **The app starts games itself** (`POST /api/play`): no protocol handler. Changing requests carry `X-Oldschool: 1` and a same-site `Origin`. Among installs of the same protocol and release, the newest build is chosen automatically; the user can pick another per kind of demo.
- **Look:** an olive theme after the CS 1.x in-game menus (bevels, Tahoma, amber HUD digits, team-coloured kill feed), plus a light "paper" variant. Colours and shapes only: no Valve logos, fonts or images.
- **Large libraries can be read in place:** `import --no-demo-copies` records where each demo is (archive and member) instead of copying it; Play extracts it and checks its SHA-1. Dropped files are always copied.
- **Per-match totals** (demos, length, kills, file date) are stored at import (migration 0003) so lists stay fast on ~40,000 matches.

## 2026-11-12

- **CS 1.6 builds 2511, 3248 and 4554** confirmed in game for Play and the round jump (protocols 46, 47, 48).
- **The Drop folder never deletes a file it could not import:** failures, duplicates and other files are moved to `_failed` (with the reason), `_already imported` and `_skipped`. Imported files are kept in `store/originals`.
- **Folders cannot be uploaded from the browser** (no reliable way to read a dropped folder): the page points to "Import a folder" or the Drop folder.
- **Re-analysis gives matches new ids** (they are rebuilt from the files); the page warns that saved links to a match may stop working.
- **One import at a time:** SQLite has one writer; inside an import, files are read in parallel by worker processes.
- **The app opens in the user's browser**, with an icon in the notification area, rather than in its own window: no extra web engine to ship, and drag and drop from Explorer works.
- **Per-user install** (no administrator prompt) in `%LOCALAPPDATA%\Programs`; the library stays in `%LOCALAPPDATA%\OldschoolCSDemos` and is kept on uninstall unless the user chooses to delete it.
- **7-Zip ships with the app** (its licence allows it) so RAR 1.5/2.0 archives import on any PC.
- **Version 0.5.0:** the first setup program.
- **The game window is brought to the front** after ▶ Play: CS 1.3 – 1.5 opened behind the browser and grabbed the mouse. Windows lets only the program in use choose the front window, so the app waits up to 40 s for the `hl.exe` window and pushes it in front until it stays there 3 s. (0.5.1)
- **One running copy per library folder:** the default library keeps the mutex name the setup program checks; another data folder (the build's smoke test) gets its own, so it can run beside the installed app.
- **Keys as a Controls page**, like the game's: a fixed list of actions useful for watching (HLTV camera, jump, duck, fire, secondary fire, scores, HUD, screenshot, console, pause, slow / fast / normal speed, stop, quit), a key and an alternate each, plus the user's own commands. Written before each Play to `cstrike\oldschool.cfg` of the install used; the user's `config.cfg` is not edited. Defaults are the game's usual keys and apply even if the page was never opened, so every install behaves the same. A key the app set before and no longer uses is unbound. (0.5.2)
- **One default layout for every keyboard:** engines before the 2013 Steam versions read key positions with a US layout, so the game's W A S D are Z Q S D on a French keyboard. The page shows keys as printed on the user's keyboard and stores the engine's names.
- **Contact page** with the author's links and the project page for bug reports; plain text links, no brand logos. (0.5.3)
- **Keys also run from inside the demo:** on CS 1.3 the keys set by `+exec oldschool.cfg` were gone, because the engine runs its `config.cfg` (which begins with `unbindall`) after the command line. The playback copy now also runs `exec oldschool.cfg` one second after playback starts (command frame + stufftext, like the round jump). Confirmed in game. (0.5.4)
- **One search syntax for every text field of the library:** Anything, Player(s) and Team tag take `|` (any of them), `+` (all of them in the same match: `aAa + GG` = their matches), `*` (anything in between) and `"…"` (the text as typed). Matching stays case-insensitive "contains"; SteamID is an exact ID. (0.5.5)
- **Engines are never in git or on GitHub:** files over 100 MB are refused by GitHub, and gigabytes of engines would weigh on every clone. `engines/` is git-ignored. The 9 installs are published on the Internet Archive as [cs11to16-engines](https://archive.org/details/cs11to16-engines) (`CS_ENGINES.zip`, 3.9 GB, SHA-1 `c97ec8875e2da13a9ec4a03eff9e5fa2d1e44764`); the README points there, and the engines download (M3b) will use it.
- **Public documentation:** README for users, CONTRIBUTING for contributors, this log and ARCHITECTURE for the design. Notes about a particular machine stay in a git-ignored `CLAUDE.local.md`.
- **MIT licence**, the most open choice for contributions. Bundled 7-Zip and acefile keep their own licences; the setup program installs `LICENSE.txt` with the app.
- **The repository starts a new history** before going public: one initial commit with the current files.
- **Version 1.0.0, the first public release** (the 0.5.x versions were test builds): the setup program on the GitHub Releases page with its SHA-256.
- **Trailer** in `docs/trailer/`: 38 s, 1080p, made for X; an HTML page animated frame by frame from the app's screens, one CC0 orchestral piece ("Battle Theme A", cynicmusic) and soft effects synthesised in code. No Valve artwork. The README shows its poster, linked to the video.
