# Contributing

Thanks for your interest! Bug reports, demo packs that don't import well, ideas and code are all welcome.

## Report a bug or a demo problem

Open an [issue](../../issues) with:

- the app version (top right of the app) and your Windows version;
- what you did, what you expected, what happened;
- for an import problem: the file name, where it comes from (a link if it is public), and the reason shown on the Import page (or the `.txt` next to the file in `Drop\_failed`);
- for a playback problem: the match page's details (release, network protocol, which install was chosen) and the engine's `cstrike\qconsole.log`;
- the app's log: `%LOCALAPPDATA%\OldschoolCSDemos\logs\app.log`.

Never attach game files (engines, maps, `hl.exe`…): they are Valve's.

## Set up a development environment

The app is Windows-only (the old engines only run there). Development happens in **WSL 2** on Windows; the setup program is built from WSL with Windows tools.

In WSL (Ubuntu):

- [uv](https://docs.astral.sh/uv/) (it installs and manages Python 3.12);
- Node.js 24 LTS;
- `git`.

On Windows (only to build the setup program, and for RAR 1.5/2.0 archives):

- Python 3.12 with the `py` launcher;
- [Inno Setup 6](https://jrsoftware.org/isinfo.php);
- [7-Zip](https://www.7-zip.org/) (the app finds `7z.exe` in `Program Files`).

Then, from the repository root in WSL:

```
python3 tasks.py check                          # installs dependencies, lints, tests, builds: must pass
python3 tasks.py dev --data-dir ~/oldschool-dev  # http://127.0.0.1:27960
```

`tasks.py` keeps the Python virtualenv in `~/.cache/oldschool/venv` (on the Linux side: faster than `/mnt/c`, and no NTFS symlink issues).

Useful environment variables for `dev`:

| Variable | Meaning |
| --- | --- |
| `OLDSCHOOL_ENGINE_ROOTS` | folders with game installs, `;`-separated Windows paths (`E:\Games\CS versions`) |
| `OLDSCHOOL_TMP` | a temporary folder on a Windows drive, so `7z.exe` can extract there (`/mnt/e/tmp`) |
| `OLDSCHOOL_DATA_DIR` | the library folder (same as `--data-dir`) |

Import from the command line: `cd backend && uv run python -m oldschool --data-dir ~/oldschool-dev import <folders> --workers 4` (add `--no-demo-copies` to read demos from their archives instead of copying them).

Always use a separate `--data-dir` for development, never your real library.

## Commands

| Command | What it does |
| --- | --- |
| `python3 tasks.py check` | backend lint (ruff), format check, tests (pytest); frontend typecheck, lint (oxlint), tests (vitest), build |
| `python3 tasks.py test` | tests only |
| `python3 tasks.py dev` | the server, serving `frontend/dist` (`--port`, `--data-dir`); restart it after backend changes |
| `python3 tasks.py build` | frontend production build |
| `python3 tasks.py api-types` | regenerate `frontend/src/api/schema.d.ts` after changing API models or routes (`check` fails when it is stale) |
| `python3 tasks.py package` | the Windows app and its setup program in `packaging/dist`: frontend build, Windows virtualenv, backend tests on Windows, PyInstaller, a smoke test of the built `.exe`, Inno Setup |
| `cd frontend && npm run dev` | Vite dev server with hot reload, `/api` proxied to port 27960 |

## Where things are

[AGENTS.md](AGENTS.md) has a file-by-file map, and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) explains the design: import pipeline, data model, playback, the Windows app.

[`.agents/skills/`](.agents/skills) holds step-by-step guides for common tasks (a new API endpoint, a schema migration, a parser change, playback, a page, a release). They are written for AI coding agents and work just as well for people.

## Rules

- **No demos, game files or game installs in git.** Tests use synthetic demos built by `backend/tests/demo_factory.py`. Real demos for local regression tests go in `backend/tests/corpus/` (git-ignored).
- **The user's files are read-only.** Originals are never modified; the playback copy in the engine's folder is the only file the app writes there (plus `cstrike\oldschool.cfg` for the keys and missing maps copied from other installs).
- **Names as printed.** Player names and team tags keep their exact spelling and case. Never merge players or teams automatically.
- **Estimates carry their basis.** Release, year and teams are estimates and say where they come from. A file date is never a match date.
- **Local only.** The server binds `127.0.0.1`. Requests that change something need the `X-Oldschool: 1` header and a same-site origin.
- **No Valve assets** in the interface: colours and shapes only.
- **Migrations are append-only.** Add a numbered file in `backend/oldschool/db/schema/`; never edit one that has shipped.
- **Parser changes:** bump `importer.PARSE_VERSION`, so users can re-analyse the files read by an older version.

## Tests

- Every change comes with tests, and `python3 tasks.py check` must pass.
- GitHub runs the same check on every push and pull request (Linux), plus the backend tests on Windows (`.github/workflows/check.yml`).
- Backend tests never start the game: they pass a `FakeRunner` that records what Play would do.
- Anything only the game can show (playback, round jump, keys, window size) is checked by hand with the lists in [docs/CHECKLISTS.md](docs/CHECKLISTS.md). If your change affects the game, add or update a checklist and say in your pull request which steps you ran, on which versions.

## Pull requests

- One topic per pull request, with a short description of what changes for the user.
- `check` passes (the CI shows it on the pull request); the generated API types are up to date.
- Update the docs your change affects: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for design, a dated entry in [docs/DECISIONS.md](docs/DECISIONS.md) for a change of scope or behaviour, and the README for anything users see.
- Interface texts are short, plain English.
