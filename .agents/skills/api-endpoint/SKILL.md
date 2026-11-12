---
name: api-endpoint
description: Add or change a backend API endpoint and wire it to the frontend (FastAPI route, pydantic models, generated TypeScript types, typed client, React Query). Use for any new data the pages need or any new action the user can trigger.
---

# Add or change an endpoint

The backend is FastAPI with plain SQL on SQLite; the frontend types are **generated** from the OpenAPI schema.

## 1. Model

`backend/oldschool/api/models.py`: one pydantic `BaseModel` per response or request body. Fields are the contract: name them for the UI, keep names and tags **as printed**, and give every estimate its `*_basis` field.

## 2. Route

Pick the router by what the request does:

| Router | Use | Guard |
| --- | --- | --- |
| `router = APIRouter(prefix="/api")` | reads (GET) | none |
| `action = APIRouter(prefix="/api", dependencies=[Depends(require_app)])` | anything that changes data, starts the game or touches files | needs `X-Oldschool: 1` and a same-site `Origin` (403 otherwise) |

Files: `api/library.py` (library reads), `api/player.py` (engines, routes, settings, play), `api/imports.py` (imports, Drop). New router modules are included in `api/app.py`.

- One SQLite connection per request: take `db: Db` (from `api/deps.py`).
- Validation errors the user can fix → `HTTPException(422, "plain sentence")`; missing things → 404; conflicts (a game already running, a job already queued) → 409. The frontend shows `detail` as is, so write it for a user.
- Unexpected errors are logged with a traceback to `<data dir>/logs/app.log` by the generic handler; don't swallow them.
- Search text fields go through `search_groups()` / `_search()` in `api/library.py` (`|`, `+`, `*`, `"…"`).

## 3. Backend tests

API tests use FastAPI's `TestClient` on a temporary database (see `tests/test_api_library.py`, `tests/test_play.py`):

```python
c = TestClient(create_app(tmp_path / "t.sqlite", store=store, runner=FakeRunner(), scan_on_start=False))
assert c.post("/api/thing", json={...}).status_code == 403            # guard works
r = c.post("/api/thing", json={...}, headers={"X-Oldschool": "1"})
```

Build libraries from synthetic demos (`tests/demo_factory.py`) and fake installs (`tests/engine_factory.make_install`). Never `runner=None` in a test that may Play.

## 4. Types and client

1. `python3 tasks.py api-types` regenerates `frontend/src/api/schema.d.ts` (never edit it by hand).
2. `frontend/src/api/client.ts`: export the type (`export type Thing = S['Thing']`) and add a function to `api`: `get<T>(path, params)` for reads, `send<T>(method, path, body)` for changes (it adds the header and turns `detail` into the error message).
3. Pages use TanStack Query: `useQuery({ queryKey: ['thing', id], queryFn: … })`; after a change, `invalidateQueries` the keys that show it, and report errors with `useToast()`.

## 5. Frontend tests

`mockApi({ '/api/thing': fixture })` and `renderAt(path, routePath, <Page />)` from `src/test-utils.tsx`; assert on the `fetch` calls for changes (method, URL, JSON body). Update every fixture of a model you extended (TypeScript will tell you).

Then run `python3 tasks.py check`.
