"""Play: engine choice, demo copy with the jump, video mode, maps, API guard.
A fake runner records the launch: no game is started."""

import pytest
from fastapi.testclient import TestClient

from oldschool import settings as cfg
from oldschool import store as store_mod
from oldschool.api.app import create_app
from oldschool.db.migrate import open_database
from oldschool.importer import import_paths
from oldschool.player.launch import PlayError, play, won_mode_for
from tests.demo_factory import MATCH, build_round_demo
from tests.engine_factory import FakeRunner, make_install


@pytest.fixture
def lib(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "rounds.dem").write_bytes(build_round_demo(MATCH))  # CS 1.5, protocol 46, de_dust2
    db = open_database(tmp_path / "t.sqlite")
    import_paths(db, [src], tmp_path / "store", workers=1)
    sha1 = db.execute("SELECT sha1 FROM demos").fetchone()[0]
    root = tmp_path / "installed"
    make_install(root, "CS15_P46_hl1110", "1.5")
    make_install(root, "CS13_P45_hl1108", "1.3", maps=("de_dust2",))
    from oldschool.player import engines as en

    en.scan(db, [str(root)])
    return db, tmp_path / "store", sha1, root


def written_demo(root, name):
    return (root / name / "cstrike" / "csdemoplay.dem").read_bytes()


def test_play_from_start(lib):
    db, store, sha1, root = lib
    runner = FakeRunner()
    r = play(db, store, sha1, None, runner)
    assert (r.engine, r.chosen, r.seek_method, r.window) == ("CS15_P46_hl1110", "automatic", None, "1280x960 windowed")
    exe, args, cwd = runner.spawned[0]
    assert exe.name == "hl.exe" and cwd == root / "CS15_P46_hl1110"
    assert args[-5:] == ["+connect", "+exec", "oldschool.cfg", "+playdemo", "csdemoplay"]
    assert runner.video == [{"EngineModeW": 1280, "EngineModeH": 960, "EngineModeWindowed": 1}]
    copy = written_demo(root, "CS15_P46_hl1110")  # no jump: only the keys file, run from inside the demo
    assert b"exec oldschool.cfg;echo keys: frame" in copy and b"host_framerate" not in copy
    assert len(copy) > len(store_mod.read_demo(store, sha1))
    # The map was missing in the 1.5 install: copied from the 1.3 one.
    assert (root / "CS15_P46_hl1110" / "cstrike" / "maps" / "de_dust2.bsp").read_bytes() == b"BSP"
    assert "copied" in r.map_note


def test_play_with_jump_framerate(lib):
    db, store, sha1, root = lib
    cfg.put(db, {"won_resolution": "1024x768", "windowed": False})
    runner = FakeRunner()
    r = play(db, store, sha1, 40.0, runner)
    _exe, args, _cwd = runner.spawned[0]
    assert r.seek_method == "framerate"
    assert args[-9:] == [
        "+connect",
        "+exec",
        "oldschool.cfg",
        "+host_framerate",
        "0.5",
        "+nosound",
        "1",
        "+playdemo",
        "csdemoplay",
    ]
    assert runner.video[0] == {"EngineModeW": 1024, "EngineModeH": 768, "EngineModeWindowed": 0}
    assert b"host_framerate 0;nosound 0" in written_demo(root, "CS15_P46_hl1110")


def test_play_with_jump_retime(lib):
    db, store, sha1, root = lib
    from oldschool.player import engines as en

    eid = db.execute("SELECT id FROM engines WHERE name = 'CS15_P46_hl1110'").fetchone()[0]
    en.update(db, eid, {"seek_method": "retime"})
    runner = FakeRunner()
    r = play(db, store, sha1, 40.0, runner)
    _exe, args, _cwd = runner.spawned[0]
    assert r.seek_method == "retime" and "+host_framerate" not in args
    copy = written_demo(root, "CS15_P46_hl1110")
    assert b"nosound 1;echo seek: fast retime frame" in copy and b"host_framerate" not in copy


def test_refusals(lib):
    db, store, sha1, _root = lib
    with pytest.raises(PlayError) as e:
        play(db, store, sha1, None, FakeRunner(running=True))
    assert e.value.status == 409 and "already running" in e.value.message
    with pytest.raises(PlayError) as e:
        play(db, store, "0" * 40, None, FakeRunner())
    assert e.value.status == 404
    db.execute("UPDATE engines SET enabled = 0")
    with pytest.raises(PlayError) as e:
        play(db, store, sha1, None, FakeRunner())
    assert e.value.status == 409 and "no working install for CS1.5" in e.value.message


def test_won_mode_for_recorded_view():
    assert won_mode_for((1280, 1024)) == (1280, 960)
    assert won_mode_for((800, 600)) == (800, 600)
    assert won_mode_for(None) == (1024, 768)


def test_api_play_and_guard(lib, tmp_path):
    db, store, sha1, root = lib
    db.close()
    runner = FakeRunner()
    c = TestClient(create_app(tmp_path / "t.sqlite", store=store, runner=runner, scan_on_start=False))
    assert c.post("/api/play", json={"sha1": sha1}).status_code == 403  # no X-Oldschool header
    h = {"X-Oldschool": "1"}
    assert c.post("/api/play", json={"sha1": sha1}, headers={**h, "Origin": "http://evil.example"}).status_code == 403
    r = c.post("/api/play", json={"sha1": sha1, "seek": 40}, headers=h)
    assert r.status_code == 200 and r.json()["engine"] == "CS15_P46_hl1110"
    assert len(runner.spawned) == 1
    runner.is_running = True
    r = c.post("/api/play", json={"sha1": sha1}, headers=h)
    assert r.status_code == 409 and "already running" in r.json()["detail"]


def test_api_engines_settings_routes(lib, tmp_path):
    db, store, _sha1, root = lib
    db.close()
    c = TestClient(create_app(tmp_path / "t.sqlite", store=store, runner=FakeRunner(), scan_on_start=False))
    h = {"X-Oldschool": "1"}
    view = c.get("/api/engines").json()
    names = {e["name"]: e for e in view["engines"]}
    assert set(names) == {"CS15_P46_hl1110", "CS13_P45_hl1108"}
    assert view["routes"] == [
        {"protocol": 46, "release": "CS1.5", "demos": 1, "engine_id": names["CS15_P46_hl1110"]["id"], "chosen_id": None,
         "how": "automatic", "candidate_ids": [names["CS15_P46_hl1110"]["id"]]}
    ]  # fmt: skip
    eid = names["CS13_P45_hl1108"]["id"]
    assert c.patch(f"/api/engines/{eid}", json={"protocol": 46}).status_code == 403
    e = c.patch(f"/api/engines/{eid}", json={"protocol": 46, "release": "CS1.5"}, headers=h).json()
    assert (e["protocol"], e["release"], e["overrides"]) == (46, "CS1.5", {"protocol": 46, "release": "CS1.5"})
    routes = c.put("/api/routes", json={"protocol": 46, "release": "CS1.5", "engine_id": eid}, headers=h).json()[
        "routes"
    ]
    assert (routes[0]["engine_id"], routes[0]["how"]) == (eid, "chosen in Settings")
    assert c.patch(f"/api/engines/{eid}", json={"video": "hologram"}, headers=h).status_code == 422
    s = c.put("/api/settings", json={"engine_roots": [str(root)], "won_resolution": "800x600"}, headers=h).json()
    assert s["won_resolution"] == "800x600" and s["effective_roots"][0] == {
        "path": str(root),
        "source": "settings",
        "exists": True,
    }
    assert c.put("/api/settings", json={"won_resolution": "1600x1200"}, headers=h).status_code == 422
    assert c.post("/api/engines", json={"path": str(tmp_path / "nope")}, headers=h).status_code == 422
    assert c.delete(f"/api/engines/{eid}", headers=h).json() == {"deleted": eid}


def test_unexpected_error_is_explained(lib, tmp_path, monkeypatch):
    db, store, sha1, _root = lib
    db.close()
    app = create_app(tmp_path / "t.sqlite", store=store, runner=FakeRunner(), scan_on_start=False)
    app.state.log_file = "C:/data/logs/app.log"
    from oldschool import sources

    def broken(*_a):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(sources, "demo_bytes", broken)
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post("/api/play", json={"sha1": sha1}, headers={"X-Oldschool": "1"})
    assert r.status_code == 500
    assert r.json()["detail"] == "unexpected error (RuntimeError: disk on fire); details in C:/data/logs/app.log"


def cfg_lines(root):
    return (root / "CS15_P46_hl1110" / "cstrike" / "oldschool.cfg").read_bytes().decode().split("\r\n")


def test_play_writes_the_keys_file(lib):
    db, store, sha1, root = lib
    play(db, store, sha1, None, FakeRunner())  # nothing changed: the default keys
    lines = cfg_lines(root)
    assert 'bind "w" "+forward"' in lines and 'bind "mouse1" "+attack"' in lines and 'bind "p" "os_pause"' in lines
    assert 'alias os_pause_on "host_framerate 0.0001; alias os_pause os_pause_off"' in lines
    assert 'bind "kp_plus" "host_framerate 0.05; alias os_pause os_pause_on"' in lines
    assert not [x for x in lines if x.startswith("unbind")]
    assert not (root / "CS15_P46_hl1110" / "cstrike" / "config.cfg").exists()  # the player's own config: untouched

    # Forward moves to the arrow only, f5 runs the player's own command, h is freed.
    cfg.put(
        db,
        {
            "controls": {"forward": ["uparrow"], "hud": [], "snapshot": ["f6"]},
            "binds": [{"key": "w", "command": "say hi"}],
        },
    )
    s = cfg.get_all(db)
    assert s["controls"]["forward"] == ["uparrow"] and s["controls"]["back"] == ["s", "downarrow"]
    play(db, store, sha1, None, FakeRunner())
    lines = cfg_lines(root)
    assert 'bind "w" "say hi"' in lines and 'bind "uparrow" "+forward"' in lines and 'bind "f6" "snapshot"' in lines
    assert {'unbind "h"', 'unbind "f5"'} <= set(lines) and 'unbind "w"' not in lines

    # A key the app set last time in this install and no longer uses is freed too.
    cfg.put(db, {"binds": [{"key": "f9", "command": "say gg"}]})
    play(db, store, sha1, None, FakeRunner())
    play(db, store, sha1, None, FakeRunner())  # and again: it stays freed
    lines = cfg_lines(root)
    assert 'bind "f9" "say gg"' in lines and 'unbind "w"' in lines and 'bind "w" "say hi"' not in lines
    cfg.put(db, {"binds": []})
    play(db, store, sha1, None, FakeRunner())
    assert 'unbind "f9"' in cfg_lines(root)


def test_keys_are_checked(lib, tmp_path):
    db, store, _sha1, _root = lib
    ok = cfg.put(
        db, {"binds": [{"key": " F6 ", "command": " say hi; quit "}], "controls": {"jump": [" MWHEELUP ", "space"]}}
    )
    assert ok["binds"] == [{"key": "f6", "command": "say hi; quit"}] and ok["controls"]["jump"] == ["mwheelup", "space"]
    # The player's own command on a default key takes it from the action.
    assert cfg.put(db, {"binds": [{"key": "tab", "command": "say gg"}]})["controls"]["scores"] == []
    for bad, why in [
        ({"binds": [{"key": "escape", "command": "quit"}]}, "unknown key"),
        ({"binds": [{"key": "é", "command": "quit"}]}, "unknown key"),
        ({"binds": [{"key": "a", "command": 'say "hi"'}]}, "one line"),
        ({"binds": [{"key": "a", "command": "  "}]}, "one line"),
        ({"binds": [{"key": "f7", "command": "x"}, {"key": "F7", "command": "y"}]}, "twice"),
        ({"binds": [{"key": "a"}]}, "key and a command"),
        ({"binds": "f5 snapshot"}, "list"),
        ({"controls": {"fly": ["a"]}}, "unknown action"),
        ({"controls": {"jump": ["a", "b", "c"]}}, "at most 2"),
        ({"controls": {"jump": ["space"], "duck": ["space"]}}, "Jump and Duck"),
        ({"controls": {"jump": ["f6"]}, "binds": [{"key": "f6", "command": "x"}]}, "twice"),
    ]:
        with pytest.raises(ValueError, match=why):
            cfg.put(db, bad)
    db.close()
    c = TestClient(create_app(tmp_path / "t.sqlite", store=store, runner=FakeRunner(), scan_on_start=False))
    h = {"X-Oldschool": "1"}
    s = c.get("/api/settings").json()
    assert s["controls"]["forward"] == ["w", "uparrow"] and s["actions"][0]["label"] == "Move forward"
    assert [g["id"] for g in s["control_groups"]] == ["camera", "demo", "speed", "game"]
    r = c.put("/api/settings", json={"controls": {"jump": ["f13"]}}, headers=h)
    assert r.status_code == 422 and "f13" in r.json()["detail"]
