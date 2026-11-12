"""M4: Drop folder, uploads, folder imports, retries, cancel, re-analysis.

Jobs are run with ``jobs.run_once()`` (no thread) except in the last test,
which runs the real background threads behind the server."""

import os
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from oldschool.api.app import create_app
from oldschool.importer import FileTask, import_files
from oldschool.jobs import Jobs
from tests.demo_factory import MATCH, build_demo, build_round_demo
from tests.engine_factory import FakeRunner

H = {"X-Oldschool": "1"}


@pytest.fixture
def env(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    jobs = Jobs(data / "library.sqlite", data / "store", data / "Drop", workers=1)
    app = create_app(data / "library.sqlite", data_dir=data, runner=FakeRunner(), scan_on_start=False, jobs=jobs)
    client = TestClient(app)
    return client, jobs, data, data / "Drop", tmp_path


def zip_with(path, *members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members:
            zf.writestr(zipfile.ZipInfo(name, date_time=(2002, 5, 4, 21, 0, 0)), data)
    return path


def tree(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and ".incoming" not in p.parts)


def db_of(client):
    from oldschool.db.migrate import connect

    return connect(client.app.state.database)


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="needs a file its owner cannot read (POSIX)")
def test_drop_folder_import_and_retry(env):
    client, jobs, _data, drop, tmp = env
    zip_with(drop / "aaa_vs_gg_dust2.zip", ("kabal_dust2.dem", build_demo(1, hltv=False)), ("readme.txt", "LAN"))
    (drop / "rounds.dem").write_bytes(build_round_demo(MATCH))
    (drop / "rounds_copy.dem").write_bytes(build_round_demo(MATCH))  # same content: already in the library
    locked = zip_with(drop / "locked.zip", ("other.dem", build_demo(2, hltv=False)))
    locked.chmod(0)  # unreadable: the import fails
    (drop / "notes.txt").write_text("not a demo")
    (drop / "pack").mkdir()
    zip_with(drop / "pack" / "lan.zip", ("a.dem", build_demo(3, hltv=False)))
    (drop / "pack" / "info.nfo").write_text("pack info")
    (drop / "_failed").mkdir()  # folders starting with _ are the app's
    (drop / "desktop.ini").write_text("")

    job_id = jobs.scan_drop(stable_seconds=0)
    assert job_id and jobs.scan_drop(stable_seconds=0) is None  # entries are claimed by the queued job
    assert jobs.run_once()

    view = client.get("/api/imports").json()
    job = view["recent"][0]
    assert (job["id"], job["state"], job["origin"]) == (job_id, "done", "drop")
    assert job["counts"] == {"imported": 3, "already": 1, "no_demo": 0, "failed": 1, "matches": 3, "demos_new": 3}
    assert (job["done"], job["total"]) == (5, 5)
    assert view["open_failures"] == 1 and view["library_files"] == 3
    # Drop is emptied: what was not imported is moved aside, never deleted.
    assert tree(drop) == [
        "_already imported/rounds_copy.dem",
        "_failed/locked.zip",
        "_failed/locked.zip.txt",
        "_skipped/notes.txt",
        "_skipped/pack/info.nfo",
        "desktop.ini",
    ]
    assert "PermissionError" in (drop / "_failed" / "locked.zip.txt").read_text()
    assert len(list((_data / "store" / "originals").rglob("*.*"))) == 3  # the imported files are kept by the app
    # The folder name stays in the label (it hints at teams and year).
    db = db_of(client)
    assert {r[0] for r in db.execute("SELECT label FROM originals")} == {
        "aaa_vs_gg_dust2.zip",
        "rounds.dem",
        "pack/lan.zip",
    }

    detail = client.get(f"/api/imports/{job_id}").json()
    assert detail["status_counts"] == {"imported": 3, "already": 1, "failed": 1}
    first = detail["files"][0]  # failures first
    assert first["status"] == "failed" and first["moved_to"].endswith("_failed/locked.zip")
    imported = [f for f in detail["files"] if f["status"] == "imported"]
    assert all(len(f["matches"]) == 1 for f in imported)
    assert client.get(f"/api/imports/{job_id}", params={"status": "already"}).json()["total_files"] == 1

    # Retry once the file is readable again: imported, and gone from _failed with its note.
    (drop / "_failed" / "locked.zip").chmod(0o644)
    assert client.post(f"/api/imports/files/{first['id']}/retry").status_code == 403  # header required
    retry = client.post(f"/api/imports/files/{first['id']}/retry", headers=H).json()
    assert retry["origin"] == "retry" and retry["state"] == "queued"
    assert client.post(f"/api/imports/files/{first['id']}/retry", headers=H).status_code == 409
    jobs.run_once()
    again = client.get(f"/api/imports/{retry['id']}").json()
    assert again["job"]["counts"]["imported"] == 1 and again["files"][0]["status"] == "imported"
    assert not (drop / "_failed" / "locked.zip").exists() and not (drop / "_failed" / "locked.zip.txt").exists()
    assert client.get("/api/imports").json()["open_failures"] == 0


def test_folder_import_in_place_and_again(env):
    client, jobs, data, _drop, tmp = env
    src = tmp / "my demos"
    (src / "2002").mkdir(parents=True)
    zip_with(src / "2002" / "aaa_vs_gg_dust2.zip", ("kabal_dust2.dem", build_demo(1, hltv=False)))
    assert client.post("/api/imports", json={"path": str(tmp / "nope")}, headers=H).status_code == 422
    assert client.post("/api/imports", json={"path": str(data / "Drop")}, headers=H).status_code == 422
    job = client.post("/api/imports", json={"path": str(src), "copy_demos": False}, headers=H).json()
    jobs.run_once()
    assert client.get(f"/api/imports/{job['id']}").json()["job"]["counts"]["imported"] == 1
    db = db_of(client)
    o = db.execute("SELECT * FROM originals").fetchone()
    assert (o["label"], o["mode"], o["demo_copies"]) == ("2002/aaa_vs_gg_dust2.zip", "referenced", 0)
    assert db.execute("SELECT store_path FROM demos").fetchone()[0] == ""  # read from the folder when played
    assert (src / "2002" / "aaa_vs_gg_dust2.zip").exists()  # left where it was

    zip_with(src / "2002" / "new.zip", ("x.dem", build_demo(2, hltv=False)))
    job2 = client.post("/api/imports", json={"path": str(src), "copy_demos": False}, headers=H).json()
    jobs.run_once()
    d = client.get(f"/api/imports/{job2['id']}").json()
    assert d["job"]["counts"]["imported"] == 1 and d["job"]["counts"]["already"] == 1
    assert d["total_files"] == 1  # files already imported from this folder are not listed again
    folders = client.get("/api/imports").json()["folders"]
    assert [(f["path"], f["copy_demos"], f["last_job_id"]) for f in folders] == [(str(src), False, job2["id"])]


def test_reanalyse_rewrites_from_the_files(env):
    client, jobs, _data, drop, tmp = env
    (drop / "rounds.dem").write_bytes(build_round_demo(MATCH))
    src = tmp / "src"
    src.mkdir()
    zip_with(src / "gone.zip", ("gone.dem", build_demo(4, hltv=False)))
    jobs.scan_drop(stable_seconds=0)
    jobs.run_once()
    client.post("/api/imports", json={"path": str(src)}, headers=H)
    jobs.run_once()
    db = db_of(client)
    sha1 = db.execute("SELECT sha1 FROM demos WHERE kill_count > 0").fetchone()[0]
    before = {
        "kills": db.execute("SELECT count(*) FROM kills").fetchone()[0],
        "rounds": db.execute("SELECT count(*) FROM rounds").fetchone()[0],
        "matches": [
            tuple(r) for r in db.execute("SELECT library_name, map, demo_count, kill_count FROM matches ORDER BY id")
        ],
    }
    # Damage the derived data, and remove the referenced folder's file.
    db.execute("DELETE FROM kills WHERE demo_sha1 = ?", (sha1,))
    db.execute("UPDATE matches SET library_name = 'broken'")
    db.execute("UPDATE demos SET parse_version = 0")
    (src / "gone.zip").unlink()
    assert client.get("/api/imports").json()["outdated_files"] == 2

    job = client.post("/api/imports/reanalyse", json={"only_outdated": True}, headers=H).json()
    assert client.post("/api/imports/reanalyse", json={}, headers=H).status_code == 409
    jobs.run_once()
    d = client.get(f"/api/imports/{job['id']}").json()
    assert d["status_counts"] == {"reanalysed": 1, "missing": 1}
    assert d["files"][0]["status"] == "missing"
    assert db.execute("SELECT count(*) FROM kills").fetchone()[0] == before["kills"]
    assert db.execute("SELECT count(*) FROM rounds").fetchone()[0] == before["rounds"]
    after = [tuple(r) for r in db.execute("SELECT library_name, map, demo_count, kill_count FROM matches ORDER BY id")]
    assert sorted(after) == sorted([before["matches"][0], ("broken", *before["matches"][1][1:])])
    assert db.execute("SELECT store_path FROM demos WHERE sha1 = ?", (sha1,)).fetchone()[0] != ""
    assert client.get("/api/imports").json()["outdated_files"] == 1  # the missing file keeps its old data


def test_cancel_queued_drop_job_moves_files_aside(env):
    client, jobs, _data, drop, _tmp = env
    (drop / "rounds.dem").write_bytes(build_round_demo(MATCH))
    job_id = jobs.scan_drop(stable_seconds=0)
    r = client.post(f"/api/imports/{job_id}/cancel", headers=H).json()
    assert r["state"] == "cancelled"
    assert tree(drop) == ["_cancelled/rounds.dem"]
    assert not jobs.run_once()
    assert client.post(f"/api/imports/{job_id}/cancel", headers=H).status_code == 409


def test_stop_after_a_file(tmp_path):
    from oldschool.db.migrate import open_database

    db = open_database(tmp_path / "t.sqlite")
    src = tmp_path / "src"
    src.mkdir()
    tasks = []
    for i in range(3):
        p = src / f"{i}.dem"
        p.write_bytes(build_demo(i + 1, hltv=False))
        tasks.append(FileTask(str(p), p.name))
    seen = []
    s = import_files(db, tasks, tmp_path / "store", workers=1, on_file=seen.append, stop=lambda: len(seen) >= 1)
    assert len(seen) == 1 and seen[0]["status"] == "imported" and s.imported == 1


def test_upload_and_open_drop(env):
    client, jobs, _data, drop, _tmp = env
    body = build_round_demo(MATCH)
    assert client.put("/api/drop", params={"name": "x.dem"}, content=body).status_code == 403
    r = client.put("/api/drop", params={"name": "..\\..\\evil:name.dem"}, content=body, headers=H)
    assert r.status_code == 200 and r.json() == {"name": "evil_name.dem", "size": len(body)}
    assert client.put("/api/drop", params={"name": "evil_name.dem"}, content=body, headers=H).json()["name"] == (
        "evil_name (2).dem"
    )
    assert client.put("/api/drop", params={"name": "photo.jpg"}, content=b"x", headers=H).status_code == 422
    assert client.put("/api/drop", params={"name": "empty.zip"}, content=b"", headers=H).status_code == 422
    assert tree(drop) == ["evil_name (2).dem", "evil_name.dem"]
    assert client.post("/api/drop/open", headers=H).status_code == 200
    assert client.app.state.runner.opened == [drop]


def test_background_threads_import_a_dropped_file(tmp_path):
    """The real thing: threads started with the server, worker processes spawned."""
    data = tmp_path / "data"
    data.mkdir()
    jobs = Jobs(data / "library.sqlite", data / "store", data / "Drop", workers=1, poll_seconds=0.2)
    app = create_app(
        data / "library.sqlite", data_dir=data, runner=FakeRunner(), scan_on_start=False, background=True, jobs=jobs
    )
    with TestClient(app) as client:
        (data / "Drop" / "rounds.dem").write_bytes(build_round_demo(MATCH))
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            recent = client.get("/api/imports").json()["recent"]
            if recent and recent[0]["state"] == "done":
                break
            time.sleep(0.2)
        assert recent[0]["counts"]["imported"] == 1
        assert client.get("/api/stats").json()["matches"] == 1
    assert not any(t.is_alive() for t in jobs._threads)  # stopped with the server
