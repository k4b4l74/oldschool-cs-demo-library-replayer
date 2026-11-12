# AGENTS.md — Oldschool CS Demos Library Replayer

Guide for AI coding agents (and a quick reference for people). A Windows app to import, identify, browse and replay old Counter-Strike (1.0 – 1.6) demos.
Read [CONTRIBUTING.md](CONTRIBUTING.md) for the setup and the rules, and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how it works.
If a `CLAUDE.local.md` exists next to this file, read it too: it holds notes about the local machine (git-ignored).

Task guides live in `.agents/skills/` — load the one that matches the work before starting:

| Skill | When |
| --- | --- |
| `check-and-ci` | running and fixing `tasks.py check`, CI failures, visual checks, committing |
| `api-endpoint` | a new or changed API route, its models, generated types and client |
| `db-migration` | any schema change or back-fill |
| `demo-parser` | parser, rounds, release / teams / year identification, `PARSE_VERSION` |
| `game-playback` | Play, round jump, engines, keys, window: the old-engine lessons |
| `frontend-page` | pages and components: theme, texts, data, tests |
| `windows-release` | version bump, packaging, smoke test, GitHub release |

## Commands (WSL, from the repository root)

```
python3 tasks.py check     # backend lint + format + tests, frontend typecheck + lint + tests + build
python3 tasks.py test      # tests only
python3 tasks.py dev       # backend on http://127.0.0.1:27960 serving frontend/dist (--port, --data-dir)
python3 tasks.py api-types # after changing api/models.py or routes: regenerate frontend/src/api/schema.d.ts
python3 tasks.py package   # Windows app + setup program → packaging/dist (Windows Python 3.12 + Inno Setup)
cd frontend && npm run dev # Vite dev server with /api proxied to :27960
```

- `check` must pass before a change is done. Every change comes with tests.
- Use a separate `--data-dir` for development, never the default library (`%LOCALAPPDATA%\OldschoolCSDemos`).
- When the parser changes, bump `importer.PARSE_VERSION` so "Re-analyse the older ones" picks the files up.
- The dev server does not reload: restart it after backend changes. Server errors go to `<data dir>/logs/app.log`.
- WSL cannot reach a server running on the Windows side at 127.0.0.1 (the reverse works): checks of the built .exe run with the Windows build Python (`packaging/smoke_check.py`). Windows processes started from WSL only see environment variables listed in `WSLENV`.
- Visual checks: headless Chrome on Windows can load `http://127.0.0.1:<port>/` served from WSL. It lays pages out at least 500 px wide; for a phone width, frame the page in a 380 px iframe served from `frontend/dist`.

## Layout

```
backend/oldschool/   Python package (FastAPI app, parser, player, db)
  __main__.py        CLI: python -m oldschool serve | import PATH... | stats  (--data-dir)
  main.py            dev server entry (tasks.py dev); desktop.py is the Windows app entry
  parser/goldsrc.py  GoldSrc demo parser: header, frames, players, kill feed, rounds
  archives.py        read any archive, nested (zip, rar, 7z, ace, tar…); uses tar.exe / 7z.exe
  identify.py        release, year estimate, teams, line-ups, match grouping
  importer.py        import pipeline: workers inspect files, one writer fills SQLite; Writer.replace = re-analysis
  jobs.py            background imports: job queue + worker thread, Drop folder watcher
  sources.py         where a demo's bytes are (store copy, or the original archive when read in place)
  store.py           content-addressed demo store: store/demos/ab/<sha1>.dem.gz
  _vendor/acefile.py ACE reader (BSD-2), bundled because its PyPI build needs a C compiler
  player/engines.py  install detection, checks, overrides, routing (protocol + release → install)
  player/launch.py   Play: demo copy (+ jump, + keys), missing map copy, WON window size via registry, start hl.exe
  player/seek.py     round jump: inject_seek (host_framerate, 1.4–1.6) and inject_seek_retime (1.0–1.3); inject_at_start
  player/controls.py keys in the game: actions, defaults, cstrike/oldschool.cfg
  player/focus.py    after Play: bring the hl.exe window in front of the browser
  player/platform.py Windows access (native or WSL interop); Runner = side effects (FakeRunner in tests)
  settings.py        user settings (engine/map folders, window size, jump speeds, welcomed, controls, own binds)
  desktop.py         the Windows app: server + browser + tray icon, single instance (OldschoolCSDemos.exe)
  icon.py            app icon drawn in code (no game artwork)
  config.py          data dir, ports, FROZEN/resource_dir() for the packaged app, NO_WINDOW for helper programs
  api/app.py         create_app(): routers, built frontend with page fallback (/match/12…)
  api/library.py     read-only endpoints (matches, rounds, players, teams), plain SQL; search syntax | + * "…"
  api/player.py      engines, routes, settings, play; changing requests need the X-Oldschool: 1 header
  api/imports.py     imports: list/detail, folder import, cancel, retry, re-analyse, upload to Drop (PUT /api/drop)
  api/models.py      response models; the frontend types are generated from them
  db/schema/*.sql    numbered migrations
backend/tests/       pytest; demo_factory.py builds synthetic demos (no real demos in git)
backend/tools/       development tools, not shipped
frontend/            React 19 + TypeScript + Vite; TanStack Query; React Router; vitest + Testing Library; oxlint
  src/api/schema.d.ts  GENERATED from the backend (python3 tasks.py api-types); `check` fails when stale
  src/pages/         Library, Match, Player(s), Team(s), Import, Settings, Welcome, Contact
  src/index.css      olive "old CS menus" theme (default) + "paper"; colours and shapes only, no Valve assets
packaging/           oldschool.spec (PyInstaller), installer.iss (Inno Setup), launch.py, smoke_check.py
docs/                ARCHITECTURE.md, DECISIONS.md, CHECKLISTS.md, images/
.agents/skills/      task guides for coding agents (see the table above)
.github/             CI (check.yml), issue forms, pull request template
tasks.py             developer tasks
```

## Rules that matter

- **Never commit demos, Valve files or game installs.** Test demos are synthetic (`backend/tests/demo_factory.py`) or live in `backend/tests/corpus/` (git-ignored). Stage files by name, not `git add -A`.
- The app never modifies the user's source files: originals are kept untouched, and the demo copy written for playback is the only thing that is ever changed.
- Names and tags are stored **as printed**; never merge players or teams automatically, never upper-case them. Estimated values (release, year, teams) always carry their basis.
- Times inside a demo are demo-clock seconds, never dates. A file timestamp is never a played date.
- The server listens on `127.0.0.1` only.
- Tests never start the game: they use `FakeRunner`. Behaviour that needs the game goes into `docs/CHECKLISTS.md` for a person to run.
- Lessons from the old engines are in `docs/ARCHITECTURE.md` (no `.`/`-w`/`-h` in WON install paths, `-newdat`, registry video mode, CS 1.3/1.4 viewport sizing, `config.cfg` running after the command line). Do not relearn them.
- Decisions that change scope or behaviour get a dated entry in `docs/DECISIONS.md`.
