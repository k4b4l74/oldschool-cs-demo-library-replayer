---
name: check-and-ci
description: Run and fix the project checks (python3 tasks.py check), read CI failures on GitHub, and do visual checks of pages. Use before calling any change done, when `check` or the GitHub "Check" workflow fails, or when a page needs to be looked at.
---

# Checks and CI

`python3 tasks.py check` (WSL, repository root) is the gate: a change is not done until it passes. GitHub runs the same on every push and pull request (`.github/workflows/check.yml`): job **Linux** = the whole `check`, job **Windows** = backend `uv sync --locked --extra desktop` + `uv run pytest`.

## What `check` runs, in order

1. `uv sync --locked --extra desktop` → `ruff check` → `ruff format --check` → `pytest` (backend)
2. `npm ci` if `node_modules` is missing → API types up to date → `typecheck` → `lint` (oxlint) → `vitest` → `vite build` (frontend)

Faster loops while working:

```bash
cd backend && UV_PROJECT_ENVIRONMENT=~/.cache/oldschool/venv uv run pytest -q tests/test_play.py -k keys
cd frontend && npx vitest run src/pages/Settings.test.tsx
```

## Usual failures and their fix

| Message | Fix |
| --- | --- |
| `ruff format --check` would reformat | `cd backend && uv run ruff format .` (use `# fmt: skip` only for hand-aligned tables) |
| `schema.d.ts is out of date` | `python3 tasks.py api-types`, commit the regenerated file |
| `uv sync --locked` fails | the lock is stale after editing `pyproject.toml`: `cd backend && uv lock` |
| oxlint `only-export-components` | a `.tsx` file exports a non-component: move helpers/types to a `.ts` file (see `upload-context.ts`, `keys.ts`) |
| Testing Library cannot find a `textbox` | an `<input list=…>` has role `combobox`; a `type="search"` input is `searchbox` |
| Windows job fails, Linux passes | path or process assumptions: use `pathlib`, `config.NO_WINDOW` for helper programs, and tests that skip what needs `os.getuid`/chmod on `nt` |
| A test passes alone but fails in the full run | timing: background-thread tests poll with a deadline; rerun the full suite before assuming a real bug |

Read a CI failure with the GitHub CLI (Windows): `gh run list --limit 3`, `gh run view <id> --log-failed`.

## Visual checks

- `python3 tasks.py dev --port 27971 --data-dir <scratch dir>` in the background, then headless Chrome on Windows: `chrome.exe --headless=new --hide-scrollbars --window-size=1400,900 --virtual-time-budget=6000 --screenshot=<file> http://127.0.0.1:27971/<page>`.
- Chrome lays pages out at least 500 px wide. For a phone width, put a page in `frontend/dist` that frames the app in a 380 px `<iframe>` (same origin), screenshot it, delete it.
- Stop the server with `pkill -f "[-]-port 27971"` (the bracket stops pkill matching its own command line).
- Never point a dev server at the user's real library (`%LOCALAPPDATA%\OldschoolCSDemos`).

## Before committing

- `check` passes; tests cover the change; docs touched where behaviour changed (`docs/DECISIONS.md` gets a dated line for scope/behaviour changes).
- Stage files by name (`git add <paths>`), never `git add -A`: big local files live in git-ignored folders of the repository.
