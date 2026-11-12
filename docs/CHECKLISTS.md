# Manual test checklists

What automated tests cannot check: the setup program, and everything that needs the game itself. Each list says what to do and what to expect. Run the lists a change affects, on the game versions it affects, and add a line to the results table.

You need the game installs (one folder per version, see the README) and a few demo archives of different versions, POV and HLTV.

## C-M5 — install the Windows app

Use the setup program built by `python3 tasks.py package` (`packaging\dist\OldschoolCSDemos-Setup-<version>.exe`). Best done on another Windows user account or another PC.

1. Run the setup program. Windows may say "Windows protected your PC" (the app is not signed): **More info → Run anyway**. Expected: no administrator prompt; the setup speaks French if Windows is in French; option "Create a desktop shortcut".
2. Finish with "Launch Oldschool CS Demos" ticked. Expected: the browser opens the app on the **Welcome** page; an olive icon with a green crosshair appears near the clock (maybe under the ^ arrow).
3. Welcome page: type the folder that holds your game installs, click **Look in this folder**. Expected: "N ready" and the list of versions. Click **Open the library**.
4. Drag 2–3 demo archives onto the window. Expected: imported (Import page), matches in the Library; ▶ Play starts the game.
5. Start the app again from the Start menu while it runs. Expected: only a new browser tab, no second copy.
6. Right-click the tray icon: **Open the Drop folder** (Explorer opens `%LOCALAPPDATA%\OldschoolCSDemos\Drop`), then **Quit**. Expected: the page stops answering; the icon disappears.
7. Install a newer version over it. Expected: the setup asks to close the app if it runs; the library is still there afterwards.
8. Uninstall (Windows Settings → Apps → Oldschool CS Demos Library Replayer). Expected: a question "Also delete your demo library…?"; No keeps `%LOCALAPPDATA%\OldschoolCSDemos`.

| Date | Version | Result |
| --- | --- | --- |
| 2026-11-12 | 0.5.0 – 0.5.5 | ✅ all steps |

## C-M2 — browse the library

1. Library: search a team, a player (`heaton|pott1`, `heaton + pott1`), a team pair (`aAa + GG` in Team tag); filter by release, year, map or HLTV/POV; sort; change pages. Copy the address bar: it reopens the same search.
2. Open a match: line-ups with K/D/HS, each demo's rounds with kill feed.
3. Click a player name (line-up or kill feed) → player page; Teams → a tag → team page.

| Date | Version | Result |
| --- | --- | --- |
| 2026-11-12 | 0.5.5 | ✅ all steps |

## C-M4 — import from the app

1. **Drag and drop:** drag 2–3 demo archives from Explorer onto any page. Expected: a dark overlay "Drop demos or archives to import them", then the Import page shows each file being sent, then an import "Drop folder: …" with a progress bar, and a message at the top right when it ends. The menu shows the progress (e.g. `IMPORT 3/5`).
2. **Duplicate:** drag one of those files again. Expected: "1 already in library"; the file ends in `Drop\_already imported`.
3. **Drop folder:** click "open it" next to the Drop folder path. Copy a folder of demos into it. Expected: imported a few seconds after the copy ends; the folder leaves Drop; a `readme.txt` or picture inside goes to `_skipped`.
4. **Wrong file:** drag a `.jpg` onto the page. Expected: refused in the list ("not a demo or an archive").
5. **Results:** in Recent imports click **Files** on an import. Expected: each file with its result and links to the new matches.
6. **Import a folder:** type a folder with a few demos, choose "Read the demos from this folder", Import. Expected: the folder is listed under "Folders imported"; ▶ on one of its matches plays. "check for new files" right after: "0 imported · … already in library".
7. **Stop:** start a big folder import and click **Stop**. Expected: the import ends as "cancelled" after the current file; what was imported stays.
8. **Re-analyse** (long on a big library): "Re-analyse everything". Library counts come back the same.

| Date | Version | Result |
| --- | --- | --- |
| 2026-11-12 | 0.5.5 | ✅ steps 1–7 (step 8 not run) |

## C-PLAY — play from the app

1. **Settings:** the game installs are listed as READY; "Which install plays which demos" shows one line per kind of demo in the library.
2. For one match of each version (1.0/1.1, 1.3, 1.4, 1.5, 1.6): open it, click **▶ Play**. Expected: a message "Starting CS1.x" at the top right, then the game opens **in front of the browser** and plays the demo from the start.
3. While a game is open, click another ▶. Expected: a red message "a game is already running".
4. Settings → Disable the CS 1.5 install, open a CS 1.5 match. Expected: ▶ buttons greyed, a note "no working install for CS1.5…". Enable it again.
5. Settings → change the window size to 1024x768, play a CS 1.5 demo: the window is smaller. Put it back.

| Date | Version | Result |
| --- | --- | --- |
| 2026-11-12 | 0.5.5, CS 1.0 – 1.6 | ✅ all steps |

## C-SEEK — jump to a round

1. Open a match, click **▶ R5** (or any round in the middle of the demo).
2. Expected: the demo runs fast and silent for a few seconds, then continues at normal speed, with sound, about 1 s before that round starts.
3. Click a kill time in the feed. Expected: normal speed about 5 s before that kill.

After a test, `cstrike\qconsole.log` of the engine used shows which route ran: `seek: fast frame` / `seek: fast stufftext` when the fast-forward starts, `seek: frame` / `seek: stufftext` at the round.

| Engine | CS | Method | Result |
| --- | --- | --- | --- |
| WON 1.1.0.6 | 1.0, 1.1 | retime (the copy's clock is compressed ×20) | ✅ 2026-11-11 (`host_framerate` is ignored during playback by this engine) |
| WON 1.1.0.8 | 1.3 | retime | ✅ 2026-11-11 (same) |
| WON 1.1.0.9 | 1.4 | `host_framerate` | ✅ 2026-11-11 |
| WON 1.1.1.0 | 1.5 | `host_framerate` | ✅ 2026-11-11 |
| builds 2511, 3248, 4554 | 1.6 (protocols 46, 47, 48) | `host_framerate` | ✅ 2026-11-12 |

## C-KEYS — keys in the game

1. Settings → Keys in the game. Expected: keys shown as printed on your keyboard (on a French keyboard: Move forward **Z** and ↑, Move left **Q**, Console **²**).
2. ▶ Play a demo, wait two seconds, Escape → Configuration → Controls. Expected: the app's keys are there (Jump on Space).
3. ▶ Play an **HLTV** demo. Check: the movement keys fly the free camera; Jump changes the camera mode; left / right click follow the next / previous player; Tab shows the scores; H hides and shows the HUD; F5 saves a screenshot.
4. Same demo (1.4 – 1.6): P pauses and resumes, Num − slow motion, Num + fast, Num Enter normal speed.
5. Change Screenshot to F6 (click its key, press F6), Save keys, ▶ Play. Expected: F6 takes the screenshot, F5 does nothing anymore.
6. Add an own command `say gg` on F9, Save keys, ▶ Play: F9 shows "gg" in the game.

`qconsole.log` shows `keys: frame` or `keys: stufftext` when the keys file ran from inside the demo.

| Date | Version | Result |
| --- | --- | --- |
| 2026-11-12 | 0.5.3, CS 1.3 | ❌ the app's keys were gone: the engine runs its `config.cfg` (`unbindall`) after the command line. Fixed in 0.5.4 |
| 2026-11-12 | 0.5.4 – 0.5.5, CS 1.3 – 1.6 | ✅ all steps |
