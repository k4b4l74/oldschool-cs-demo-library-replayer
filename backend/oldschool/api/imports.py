"""Imports: Drop folder, uploads from the page, folders, retries, re-analysis.

The work itself runs in the background (``oldschool.jobs``); these
endpoints queue jobs and report on them.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from oldschool.api.deps import Db
from oldschool.api.models import (
    FolderImport,
    ImportCounts,
    ImportFolder,
    ImportsView,
    Job,
    JobDetail,
    JobFile,
    MatchLink,
    Reanalyse,
    Uploaded,
)
from oldschool.api.player import require_app
from oldschool.importer import PARSE_VERSION
from oldschool.jobs import INCOMING, enqueue, importable, unique_path
from oldschool.player.platform import to_local, to_native

router = APIRouter(prefix="/api")
action = APIRouter(prefix="/api", dependencies=[Depends(require_app)])

MAX_UPLOAD = 4 * 1024**3
_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _native(p: str) -> str:
    return to_native(p) if p.startswith("/") else p


def job_model(r: sqlite3.Row) -> Job:
    payload = json.loads(r["payload"] or "{}")
    progress = json.loads(r["progress"] or "{}")
    return Job(
        id=r["id"],
        kind=r["kind"],
        origin=payload.get("origin"),
        state=r["state"],
        paths=[_native(p) for p in payload.get("paths", [])],
        copy_demos=bool(payload.get("copy_demos", True)),
        done=progress.get("done", 0),
        total=progress.get("total", 0),
        current=progress.get("current") or None,
        counts=ImportCounts(**progress.get("summary", {})),
        error=r["error"],
        created_at=r["created_at"],
        started_at=r["started_at"],
        finished_at=r["finished_at"],
    )


def _get_job(db: sqlite3.Connection, job_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "import not found")
    return row


@router.get("/imports")
def imports(db: Db, request: Request) -> ImportsView:
    active = [
        job_model(r)
        for r in db.execute("SELECT * FROM jobs WHERE state IN ('running', 'queued') ORDER BY state = 'queued', id")
    ]
    recent = [
        job_model(r)
        for r in db.execute("SELECT * FROM jobs WHERE state NOT IN ('running', 'queued') ORDER BY id DESC LIMIT 15")
    ]
    folders: dict[str, ImportFolder] = {}
    for r in db.execute(
        "SELECT id, payload, coalesce(finished_at, created_at) AS at FROM jobs"
        " WHERE kind = 'import' AND json_extract(payload, '$.origin') = 'folder' ORDER BY id"
    ):
        p = json.loads(r["payload"])
        for path in p.get("paths", []):
            folders[path] = ImportFolder(
                path=_native(path), copy_demos=bool(p.get("copy_demos", True)), last_job_id=r["id"], last_run=r["at"]
            )
    open_failures = db.execute(
        "SELECT count(*) FROM job_files f WHERE status = 'failed' AND retry_job_id IS NULL"
        " AND NOT EXISTS (SELECT 1 FROM job_files g WHERE g.path = f.path AND g.id > f.id)"
    ).fetchone()[0]
    outdated = db.execute(
        "SELECT count(DISTINCT a.original_id) FROM archive_members a JOIN demos d ON d.sha1 = a.demo_sha1"
        " WHERE d.parse_version < ?",
        (PARSE_VERSION,),
    ).fetchone()[0]
    return ImportsView(
        drop_dir=to_native(Path(request.app.state.drop).resolve()),
        active=active,
        recent=recent,
        folders=sorted(folders.values(), key=lambda f: f.path.lower()),
        open_failures=open_failures,
        outdated_files=outdated,
        library_files=db.execute("SELECT count(*) FROM originals").fetchone()[0],
    )


@router.get("/imports/{job_id}")
def import_detail(
    job_id: int,
    db: Db,
    status: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
) -> JobDetail:
    job = _get_job(db, job_id)
    counts = {
        r[0]: r[1] for r in db.execute("SELECT status, count(*) FROM job_files WHERE job_id = ? GROUP BY 1", (job_id,))
    }
    where, args = "job_id = ?", [job_id]
    if status:
        where += " AND status = ?"
        args.append(status)
    total = db.execute(f"SELECT count(*) FROM job_files WHERE {where}", args).fetchone()[0]
    order = "CASE status WHEN 'failed' THEN 0 WHEN 'missing' THEN 1 ELSE 2 END, id"
    files = []
    for r in db.execute(
        f"SELECT * FROM job_files WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?", [*args, size, (page - 1) * size]
    ):
        links = []
        if r["original_id"] and r["status"] in ("imported", "reanalysed"):
            links = [
                MatchLink(id=m[0], name=m[1])
                for m in db.execute(
                    "SELECT id, library_name FROM matches WHERE original_id = ? ORDER BY id LIMIT 20",
                    (r["original_id"],),
                )
            ]
        files.append(
            JobFile(
                id=r["id"],
                path=_native(r["path"]),
                label=r["label"],
                status=r["status"],
                matches=links,
                demos_new=r["demos_new"],
                message=r["message"],
                moved_to=_native(r["moved_to"]) if r["moved_to"] else None,
                retry_job_id=r["retry_job_id"],
                original_id=r["original_id"],
            )
        )
    return JobDetail(job=job_model(job), status_counts=counts, files=files, total_files=total, page=page, size=size)


@action.post("/imports")
def import_folder(body: FolderImport, db: Db, request: Request) -> Job:
    """Import a folder left where it is. Again later: only new files are read."""
    native = body.path.strip().strip('"').rstrip("\\/") or body.path
    local = to_local(native)
    if not local.is_dir():
        raise HTTPException(422, f"folder not found: {native}")
    data = Path(request.app.state.data_dir).resolve()
    if local.resolve() == data or local.resolve().is_relative_to(data):
        raise HTTPException(422, "this folder belongs to the app: put files in the Drop folder instead")
    job_id = enqueue(
        db, "import", {"origin": "folder", "paths": [str(local)], "mode": "referenced", "copy_demos": body.copy_demos}
    )
    request.app.state.jobs.wake()
    return job_model(_get_job(db, job_id))


@action.post("/imports/reanalyse")
def reanalyse(body: Reanalyse, db: Db, request: Request) -> Job:
    if db.execute("SELECT 1 FROM jobs WHERE kind = 'reanalyse' AND state IN ('queued', 'running')").fetchone():
        raise HTTPException(409, "a re-analysis is already queued or running")
    job_id = enqueue(db, "reanalyse", {"only_outdated": body.only_outdated})
    request.app.state.jobs.wake()
    return job_model(_get_job(db, job_id))


@action.post("/imports/{job_id}/cancel")
def cancel(job_id: int, db: Db, request: Request) -> Job:
    _get_job(db, job_id)
    if not request.app.state.jobs.cancel(db, job_id):
        raise HTTPException(409, "this import is already finished")
    return job_model(_get_job(db, job_id))


@action.post("/imports/files/{file_id}/retry")
def retry(file_id: int, db: Db, request: Request) -> Job:
    f = db.execute(
        "SELECT f.*, j.payload FROM job_files f JOIN jobs j ON j.id = f.job_id WHERE f.id = ?", (file_id,)
    ).fetchone()
    if not f:
        raise HTTPException(404, "file not found")
    if f["status"] != "failed":
        raise HTTPException(409, "only a failed file can be retried")
    if f["retry_job_id"]:
        raise HTTPException(409, f"already retried (import #{f['retry_job_id']})")
    path = f["moved_to"] or f["path"]
    if not Path(path).is_file():
        raise HTTPException(410, f"the file is no longer there: {_native(path)}")
    payload = json.loads(f["payload"])
    from_drop = payload.get("origin") == "drop" or payload.get("mode") == "moved"
    job_id = enqueue(
        db,
        "import",
        {
            "origin": "retry",
            "paths": [path],
            "labels": {path: f["label"]},
            "mode": "moved" if from_drop else payload.get("mode", "referenced"),
            "copy_demos": bool(payload.get("copy_demos", True)),
        },
    )
    db.execute("UPDATE job_files SET retry_job_id = ? WHERE id = ?", (job_id, file_id))
    request.app.state.jobs.wake()
    return job_model(_get_job(db, job_id))


def clean_name(name: str) -> str:
    base = _BAD_CHARS.sub("_", name.replace("\\", "/").rsplit("/", 1)[-1]).strip().lstrip("._ ")
    return base[:180]


@action.put("/drop")
async def upload(request: Request, name: str = Query(..., min_length=1, max_length=255)) -> Uploaded:
    """A file sent by the page (drag and drop): written to the Drop folder,
    where the watcher imports it like any dropped file."""
    clean = clean_name(name)
    if not clean or not importable(clean):
        raise HTTPException(422, f"{name}: not a demo (.dem) or an archive (.zip, .rar, .7z, .ace…)")
    drop = Path(request.app.state.drop)
    incoming = drop / INCOMING
    incoming.mkdir(parents=True, exist_ok=True)
    part = incoming / f"{uuid.uuid4().hex}.part"
    size = 0
    try:
        with part.open("wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, "file larger than 4 GB")
                out.write(chunk)
        if size == 0:
            raise HTTPException(422, f"{name}: empty file")
        target = unique_path(drop / clean)
        os.replace(part, target)
    finally:
        part.unlink(missing_ok=True)
    return Uploaded(name=target.name, size=size)


@action.post("/drop/open")
def open_drop(request: Request) -> dict:
    drop = Path(request.app.state.drop)
    drop.mkdir(parents=True, exist_ok=True)
    request.app.state.runner.open_folder(drop)
    return {"opened": to_native(drop.resolve())}
