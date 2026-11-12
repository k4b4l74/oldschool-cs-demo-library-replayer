"""Engine detection, checks, overrides and routing on fake installs."""

import json

import pytest

from oldschool.db.migrate import open_database
from oldschool.player import engines as en
from tests.engine_factory import make_install


@pytest.fixture
def db(tmp_path):
    return open_database(tmp_path / "t.sqlite")


def by_name(db):
    return {r["name"]: r for r in db.execute("SELECT * FROM engines")}


def test_detect_won_and_steam_builds(tmp_path):
    root = tmp_path / "installed"
    won = en.detect(make_install(root, "CS13_P45_hl1108", "1.3"))
    assert (won["kind"], won["build"], won["protocol"], won["release"]) == ("won", "1.1.0.8", 45, "CS1.3")
    assert (won["seek_method"], won["video"]) == ("retime", "registry-demo")
    assert "-newdat" in won["args"] and "-windowed" not in won["args"]
    cs15 = en.detect(make_install(root, "CS15_P46_hl1110", "1.5"))
    assert (cs15["build"], cs15["protocol"], cs15["seek_method"], cs15["video"]) == (
        "1.1.1.0",
        46,
        "framerate",
        "registry",
    )
    assert "-newdat" not in cs15["args"]
    p48 = en.detect(make_install(root, "CS16_P48_build4554", "1.6", steam=True, steam_api=True))
    assert (p48["kind"], p48["build"], p48["protocol"], p48["release"], p48["video"]) == (
        "steam",
        "build 4554",
        48,
        "CS1.6",
        "args",
    )
    assert p48["args"][:3] == ["-steam", "-appid", "10"] and "-w" in p48["args"]
    p47 = en.detect(make_install(root, "CS16_P47_build3248", "1.6", steam=True))
    assert p47["args"][0] == "-game"


def test_protocol_from_build_and_provenance(tmp_path):
    root = tmp_path / "installed"
    plain = en.detect(make_install(root, "MyOld_hl1106", "1.1"))
    assert (plain["build"], plain["protocol"]) == ("1.1.0.6", 43)  # from the build when the name has no P43
    d = make_install(root, "SomeCS16", "1.6", steam=True)
    (d / "INSTALL-PROVENANCE.json").write_text(
        json.dumps({"reported_network_protocol": 47, "reported_engine_build": "17:40:39 Sep 15 2005 (3248)"}),
        encoding="utf-8",
    )
    prov = en.detect(d)
    assert (prov["protocol"], prov["build"]) == (47, "build 3248")
    unknown = en.detect(make_install(root, "Mystery", "1.6", steam=True))
    assert unknown["protocol"] is None


def test_checks_and_status(tmp_path, db):
    root = tmp_path / "installed"
    make_install(root, "CS13_P45_hl1108", "1.3")
    make_install(root, "CS11_P43_hl1106", "1.1", skip=("hw.dll",))
    make_install(root, "Mystery", "1.6", steam=True)
    make_install(root, "CS15_P46_hl1110", "1.5")
    en.scan(db, [str(root)])
    rows = by_name(db)
    assert rows["CS13_P45_hl1108"]["status"] == "ok"
    assert rows["CS11_P43_hl1106"]["status"] == "broken"
    assert "hw.dll missing" in json.loads(rows["CS11_P43_hl1106"]["status_detail"])
    assert rows["Mystery"]["status"] == "warning"  # protocol unknown: playable once set
    # Path rules of the 1.1.0.6-1.1.0.9 hl.exe (the folder path is checked as stored).
    assert any(
        "dot" in p
        for p in en.checks(
            r"E:\games\CS-1.3_hl1108", {"kind": "won", "build": "1.1.0.8", "protocol": 45, "release": "CS1.3"}
        )
    )
    assert any(
        "'-w' or '-h'" in p
        for p in en.checks(
            r"E:\games\CS13-hl1108", {"kind": "won", "build": "1.1.0.8", "protocol": 45, "release": "CS1.3"}
        )
    )
    # 1.1.1.0 has no such rule (it ran from "CS-1.5").
    assert not any(
        "dot" in p for p in en.checks(str(root / "CS15_P46_hl1110"), {**en.effective(rows["CS15_P46_hl1110"])})
    )


def test_overrides_and_reset(tmp_path, db):
    root = tmp_path / "installed"
    make_install(root, "Mystery", "1.6", steam=True)
    en.scan(db, [str(root)])
    eid = by_name(db)["Mystery"]["id"]
    en.update(db, eid, {"protocol": 47})
    row = by_name(db)["Mystery"]
    assert (en.effective(row)["protocol"], row["status"]) == (47, "ok")
    en.scan(db, [str(root)])  # a new scan keeps the user's choice
    assert en.effective(by_name(db)["Mystery"])["protocol"] == 47
    en.update(db, eid, {"protocol": None})
    assert en.effective(by_name(db)["Mystery"])["protocol"] is None
    with pytest.raises(ValueError):
        en.update(db, eid, {"seek_method": "teleport"})
    with pytest.raises(ValueError):
        en.update(db, eid, {"protocol": 49})


def test_routing(tmp_path, db):
    root = tmp_path / "installed"
    for name, rel, steam in [("CS11_P43_hl1106", "1.1", False), ("CS13_P45_hl1108", "1.3", False), ("CS14_P45_hl1109", "1.4", False),
                             ("CS15_P46_hl1110", "1.5", False), ("CS16_P46_build2511", "1.6", True), ("CS16_beta_P46_build2273", "1.6", True),
                             ("CS16_P47_build2603", "1.6", True), ("CS16_P47_build3248", "1.6", True)]:  # fmt: skip
        make_install(root, name, rel, steam=steam)
    en.scan(db, [str(root)])

    def pick(p, r):
        row, how = en.route(db, p, r)
        return (row["name"] if row else None), how

    assert pick(43, "CS1.0")[0] == "CS11_P43_hl1106"  # no 1.0 install: same protocol
    assert pick(45, "CS1.3")[0] == "CS13_P45_hl1108"
    assert pick(45, "CS1.4")[0] == "CS14_P45_hl1109"
    assert pick(46, "CS1.5")[0] == "CS15_P46_hl1110"
    assert pick(46, "CS1.6")[0] == "CS16_P46_build2511"  # newest 1.6 build on 46, never the 1.5 engine
    assert pick(47, "CS1.6")[0] == "CS16_P47_build3248"
    name, why = pick(48, "CS1.6")
    assert name is None and "no working install for CS1.6 (network protocol 48)" in why
    # The user's choice wins, until that install is disabled.
    old = by_name(db)["CS16_P47_build2603"]["id"]
    en.set_route(db, 47, "CS1.6", old)
    assert pick(47, "CS1.6") == ("CS16_P47_build2603", "chosen in Settings")
    en.update(db, old, {"enabled": False})
    assert pick(47, "CS1.6") == ("CS16_P47_build3248", "automatic")
    en.set_route(db, 47, "CS1.6", None)
    assert db.execute("SELECT count(*) FROM engine_routes").fetchone()[0] == 0


def test_missing_folder_is_flagged(tmp_path, db):
    root = tmp_path / "installed"
    d = make_install(root, "CS15_P46_hl1110", "1.5")
    en.scan(db, [str(root)])
    import shutil

    shutil.rmtree(d)
    en.scan(db, [str(root)])
    row = by_name(db)["CS15_P46_hl1110"]
    assert (row["missing"], row["status"]) == (1, "broken")
