"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from oldschool import __version__
from oldschool.api import imports, library, player
from oldschool.api.deps import Db
from oldschool.api.models import Health
from oldschool.config import APP_NAME
from oldschool.db.migrate import connect, open_database
from oldschool.jobs import Jobs
from oldschool.player.platform import Runner, to_native

log = logging.getLogger("oldschool")


def create_app(
    database: Path | str,
    frontend_dist: Path | None = None,
    store: Path | None = None,
    data_dir: Path | None = None,
    runner: Runner | None = None,
    scan_on_start: bool = True,
    background: bool = False,
    jobs: Jobs | None = None,
) -> FastAPI:
    """``store``/``data_dir`` default to the database's folder (tests).
    ``runner`` performs the side effects of Play (a fake in tests).
    ``background``: run queued imports and watch the Drop folder while the
    server runs (the app does; tests run jobs themselves with ``jobs.run_once``)."""
    database = Path(database)
    data_dir = Path(data_dir or database.parent)
    open_database(database).close()  # create / migrate once at start
    store = Path(store or data_dir / "store")
    drop = data_dir / "Drop"
    drop.mkdir(parents=True, exist_ok=True)
    jobs = jobs or Jobs(database, store, drop)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if background:
            jobs.start()
        try:
            yield
        finally:
            if background:
                jobs.stop()

    app = FastAPI(title=APP_NAME, version=__version__, lifespan=lifespan)
    app.state.database = str(database)
    app.state.store = str(store)
    app.state.data_dir = str(data_dir)
    app.state.drop = str(drop)
    app.state.jobs = jobs
    app.state.data_dir_native = to_native(data_dir.resolve())
    app.state.log_file = None  # set by main() when it logs to a file
    app.state.default_engine_root = to_native((data_dir / "Engines").resolve())
    app.state.runner = runner or Runner()

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        """A bug: keep the traceback in the log file and tell the page where it is."""
        log.error("unexpected error on %s %s", request.method, request.url.path, exc_info=exc)
        detail = f"unexpected error ({type(exc).__name__}: {exc}); details in {app.state.log_file or 'the console'}"
        return JSONResponse({"detail": detail}, status_code=500)

    @app.get("/api/health")
    def health(db: Db) -> Health:
        schema = db.execute("SELECT max(number) FROM schema_migrations").fetchone()[0]
        return Health(app=APP_NAME, version=__version__, schema_version=schema)

    app.include_router(library.router)
    app.include_router(player.router)
    app.include_router(player.action)
    app.include_router(imports.router)
    app.include_router(imports.action)

    if scan_on_start:

        class _Req:  # the scan needs the roots, which depend on app.state only
            def __init__(self, a):
                self.app = a

        db = connect(database)
        try:
            found = player.scan_all(_Req(app), db)
            log.info("engine scan: %s", found)
        finally:
            db.close()

    if frontend_dist and (frontend_dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")
        index = frontend_dist / "index.html"

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            """Files from the build, otherwise index.html: the page routes
            (/match/12, /player/3…) are handled in the browser."""
            if path.startswith("api/"):
                raise HTTPException(404)
            f = (frontend_dist / path).resolve()
            if path and f.is_file() and f.is_relative_to(frontend_dist.resolve()):
                return FileResponse(f)
            return FileResponse(index)

    return app
