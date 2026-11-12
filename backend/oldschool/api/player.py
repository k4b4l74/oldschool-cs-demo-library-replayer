"""Engines, settings and Play.

Changing endpoints (POST/PUT/PATCH/DELETE) need the ``X-Oldschool: 1``
header and, when the browser sends one, an Origin on this server: a web
page from elsewhere cannot add a custom header without a CORS preflight,
which this server never grants, so it cannot start the game or change
settings through the visitor's browser.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request

from oldschool import settings as cfg
from oldschool.api.deps import Db
from oldschool.api.models import (
    ControlAction,
    ControlGroup,
    Engine,
    EngineAdd,
    EnginePatch,
    EngineRoute,
    EnginesView,
    PlayRequest,
    PlayResponse,
    Root,
    RouteChange,
    ScanResult,
    Settings,
    SettingsChange,
)
from oldschool.player import controls as ctl
from oldschool.player import engines as en
from oldschool.player.launch import PlayError, play
from oldschool.player.platform import to_local

ACTION_HEADER = "x-oldschool"


def require_app(request: Request) -> None:
    if request.headers.get(ACTION_HEADER) != "1":
        raise HTTPException(403, "missing X-Oldschool header")
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).netloc != request.headers.get("host"):
        raise HTTPException(403, "request from another site")


router = APIRouter(prefix="/api")
action = APIRouter(prefix="/api", dependencies=[Depends(require_app)])


def effective_roots(request: Request, db: sqlite3.Connection) -> list[Root]:
    roots: list[Root] = []
    seen = set()

    def add(path: str, source: str):
        if path and path.lower() not in seen:
            seen.add(path.lower())
            roots.append(Root(path=path, source=source, exists=to_local(path).is_dir()))

    for p in cfg.get_all(db)["engine_roots"]:
        add(p, "settings")
    for p in cfg.env_engine_roots():
        add(p, "environment")
    add(request.app.state.default_engine_root, "default")
    return roots


def scan_all(request: Request, db: sqlite3.Connection) -> dict:
    return en.scan(db, [r.path for r in effective_roots(request, db) if r.exists])


def _engine(r: sqlite3.Row) -> Engine:
    e = en.effective(r)
    return Engine(
        id=r["id"],
        name=r["name"] or r["path"],
        path=r["path"],
        source=r["source"],
        enabled=bool(r["enabled"]),
        missing=bool(r["missing"]),
        status=r["status"],
        problems=json.loads(r["status_detail"] or "[]"),
        kind=e.get("kind"),
        build=e.get("build"),
        protocol=e.get("protocol"),
        release=e.get("release"),
        seek_method=e.get("seek_method"),
        video=e.get("video"),
        args=e.get("args") or [],
        detected=json.loads(r["detected"] or "{}"),
        overrides=json.loads(r["overrides"] or "{}"),
    )


@router.get("/engines")
def list_engines(db: Db) -> EnginesView:
    engines = [_engine(r) for r in db.execute("SELECT * FROM engines ORDER BY name")]
    kinds = en.demo_kinds(db)  # only the kinds of demo present in the library are listed
    routes = []
    for protocol, release, demos in kinds:
        chosen = db.execute(
            "SELECT engine_id FROM engine_routes WHERE protocol = ? AND release = ?", (protocol, release)
        ).fetchone()
        engine, how = en.route(db, protocol, release)
        routes.append(
            EngineRoute(
                protocol=protocol,
                release=release,
                demos=demos,
                engine_id=engine["id"] if engine else None,
                chosen_id=chosen[0] if chosen else None,
                how=how,
                candidate_ids=[r["id"] for r in en.candidates(db, protocol, release)],
            )
        )
    return EnginesView(engines=engines, routes=routes)


@action.post("/engines/scan")
def scan(db: Db, request: Request) -> ScanResult:
    return ScanResult(**scan_all(request, db))


@action.post("/engines")
def add_engine(body: EngineAdd, db: Db) -> Engine:
    path = body.path.strip().strip('"')
    if not to_local(path).is_dir():
        raise HTTPException(422, f"folder not found: {path}")
    engine_id = en.add(db, path, "manual")
    return _engine(db.execute("SELECT * FROM engines WHERE id = ?", (engine_id,)).fetchone())


@action.patch("/engines/{engine_id}")
def patch_engine(engine_id: int, body: EnginePatch, db: Db) -> Engine:
    try:
        en.update(db, engine_id, body.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(404, "engine not found") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _engine(db.execute("SELECT * FROM engines WHERE id = ?", (engine_id,)).fetchone())


@action.delete("/engines/{engine_id}")
def delete_engine(engine_id: int, db: Db) -> dict:
    """Forget an install (its files are not touched). A scan finds it again
    if it is still in a scanned folder; disabling keeps it out for good."""
    if not db.execute("DELETE FROM engines WHERE id = ? RETURNING id", (engine_id,)).fetchone():
        raise HTTPException(404, "engine not found")
    return {"deleted": engine_id}


@action.put("/routes")
def put_route(body: RouteChange, db: Db) -> EnginesView:
    try:
        en.set_route(db, body.protocol, body.release, body.engine_id)
    except KeyError as exc:
        raise HTTPException(404, "engine not found") from exc
    return list_engines(db)


@router.get("/settings")
def get_settings(db: Db, request: Request) -> Settings:
    s = cfg.get_all(db)
    return Settings(
        **s,
        effective_roots=effective_roots(request, db),
        won_modes=cfg.WON_MODES,
        actions=[
            ControlAction(
                id=a.id, group=a.group, label=a.label, command=a.command, defaults=list(a.defaults), hint=a.hint
            )
            for a in ctl.ACTIONS
        ],
        control_groups=[ControlGroup(id=g, label=label, hint=hint) for g, (label, hint) in ctl.GROUPS.items()],
        data_dir=request.app.state.data_dir_native,
    )


@action.put("/settings")
def put_settings(body: SettingsChange, db: Db, request: Request) -> Settings:
    changes = body.model_dump(exclude_unset=True)
    try:
        cfg.put(db, changes)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if "engine_roots" in changes:
        scan_all(request, db)
    return get_settings(db, request)


@action.post("/play")
def play_demo(body: PlayRequest, db: Db, request: Request) -> PlayResponse:
    try:
        r = play(db, Path(request.app.state.store), body.sha1, body.seek, request.app.state.runner)
    except PlayError as exc:
        raise HTTPException(exc.status, exc.message) from exc
    return PlayResponse(**r.__dict__)
