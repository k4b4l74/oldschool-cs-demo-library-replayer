"""Import pipeline on synthetic archives: identification, grouping, dedupe, modes."""

import io
import json
import tarfile
import zipfile

import pytest

from oldschool import store
from oldschool.db.migrate import open_database
from oldschool.importer import import_paths
from tests.demo_factory import MATCH, build_demo, build_round_demo


@pytest.fixture
def lib(tmp_path):
    db = open_database(tmp_path / "lib.sqlite")
    return db, tmp_path / "store", tmp_path / "src"


def run(lib, *paths, mode="referenced"):
    db, store_root, _src = lib
    return import_paths(db, paths, store_root, mode=mode, workers=1)


def matches(db):
    return [dict(r) for r in db.execute("SELECT * FROM matches ORDER BY id")]


def test_pov_zip_is_identified(lib):
    db, store_root, src = lib
    src.mkdir()
    p = src / "aaa_vs_gg_dust2.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr(
            zipfile.ZipInfo("aaa-gg/kabal_dust2.dem", date_time=(2002, 5, 4, 21, 0, 0)), build_demo(1, hltv=False)
        )
        zf.writestr("readme.txt", "LAN test")
    s = run(lib, src)
    assert (s.imported, s.matches, s.demos_new, s.failed) == (1, 1, 1, 0)
    m = matches(db)[0]
    assert m["library_name"] == "[aAa]_[GG]_[de_dust2]_[KabaL]_[ctt].zip"
    assert (m["release"], m["year_est"], m["pov"], m["sides"]) == ("CS1.5", "2002", "KabaL", "ctt")
    assert "member timestamp" in m["year_basis"]
    team1 = db.execute("SELECT tag_as_printed FROM teams WHERE id = ?", (m["team1_id"],)).fetchone()[0]
    assert team1 == "aAa"
    lineup = db.execute(
        "SELECT p.name_as_printed FROM match_players mp JOIN player_names p ON p.id = mp.player_name_id"
        " WHERE mp.match_id = ? AND mp.team_key = 'team1' ORDER BY 1",
        (m["id"],),
    ).fetchall()
    assert [r[0] for r in lineup] == ["aAa|Fatal", "aAa|KabaL"]  # same as the wiki catalogue
    texts = db.execute("SELECT text_content FROM archive_members WHERE name = 'readme.txt'").fetchone()
    assert texts[0] == "LAN test"
    original = db.execute("SELECT mode, kept_path, source_path FROM originals").fetchone()
    assert (original["mode"], original["kept_path"]) == ("referenced", None)
    assert p.exists()


def test_nested_hltv_pack_orders_teams_like_the_filename(lib):
    _db, _store, src = lib
    src.mkdir()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as inner:
        inner.writestr(zipfile.ZipInfo("gg_aaa.dem", date_time=(2002, 1, 2, 3, 4, 5)), build_demo())
    with zipfile.ZipFile(src / "gg-aaa.zip", "w") as zf:
        zf.writestr("pack/gg_aaa.zip", buf.getvalue())
    run(lib, src)
    m = matches(lib[0])[0]
    assert m["library_name"] == "[GG]_[aAa]_[de_dust2]_[HLTV]_[ctt].zip"
    member = lib[0].execute("SELECT chain, name FROM archive_members WHERE demo_sha1 IS NOT NULL").fetchone()
    assert tuple(member) == ("pack/gg_aaa.zip", "gg_aaa.dem")


def test_pack_split_by_map_and_duplicates_skipped(lib):
    db, store_root, src = lib
    dust = build_demo(recorder_slot=1, hltv=False, steam=True)
    nuke = dust.replace(b"de_dust2", b"de_nuke\x00")  # same length, another map
    (src / "a").mkdir(parents=True)
    (src / "b").mkdir()
    with zipfile.ZipFile(src / "a" / "pack.zip", "w") as zf:
        zf.writestr(zipfile.ZipInfo("kabal_dust2.dem", date_time=(2002, 5, 4, 21, 0, 0)), dust)
        zf.writestr(zipfile.ZipInfo("kabal_nuke.dem", date_time=(2002, 5, 5, 21, 0, 0)), nuke)
    (src / "b" / "copy_of_dust2.dem").write_bytes(dust)
    s = run(lib, src)
    assert (s.imported, s.matches, s.duplicate_groups, s.demos_new, s.demos_seen_before) == (2, 2, 1, 2, 1)
    names = sorted(m["library_name"] for m in matches(db))
    assert names == ["[aAa]_[GG]_[de_dust2]_[KabaL]_[ctt].zip", "[aAa]_[GG]_[de_nuke]_[KabaL]_[ctt].zip"]
    # The duplicate's file is still recorded as a place where the demo was found.
    sha1 = store.file_sha1(src / "b" / "copy_of_dust2.dem")
    places = db.execute("SELECT count(*) FROM archive_members WHERE demo_sha1 = ?", (sha1,)).fetchone()[0]
    assert places == 2
    kabal = db.execute("SELECT steamid FROM player_names WHERE name_as_printed = 'aAa|KabaL'").fetchall()
    assert [r[0] for r in kabal] == ["STEAM_0:1:1"]
    # Re-running imports nothing new.
    again = run(lib, src)
    assert (again.already, again.imported, again.matches) == (2, 0, 0)


def test_hltv_tarball_year_from_name_stamp(lib):
    _db, _store, src = lib
    src.mkdir()
    data = build_demo()
    with tarfile.open(src / "GG.aAa.123456.tar.bz2", "w:bz2") as tf:
        info = tarfile.TarInfo("61.1.123456-0205041200-de_dust2.dem")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    run(lib, src)
    m = matches(lib[0])[0]
    assert (m["library_name"], m["year_est"]) == ("[GG]_[aAa]_[de_dust2]_[HLTV]_[ctt].zip", "2002")
    assert m["year_basis"] == "HLTV auto-name stamp in demo filename"


def test_rounds_kills_and_store(lib):
    db, store_root, src = lib
    src.mkdir()
    data = build_round_demo(MATCH)
    (src / "rounds.dem").write_bytes(data)
    run(lib, src)
    sha1 = store.file_sha1(src / "rounds.dem")
    assert store.read_demo(store_root, sha1) == data
    demo = db.execute("SELECT * FROM demos WHERE sha1 = ?", (sha1,)).fetchone()
    assert (demo["map"], demo["net_protocol"], demo["kill_count"], demo["parse_error"]) == ("de_dust2", 46, 3, None)
    assert json.loads(demo["analysis"])["final_score"] == {"CT": 0, "TERRORIST": 1}
    rounds = db.execute("SELECT no, start_t, end_t, winner FROM rounds ORDER BY no").fetchall()
    assert [tuple(r) for r in rounds] == [(1, pytest.approx(0.1), 30.0, "CT"), (2, 41.0, 60.0, "TERRORIST"),
                                         (3, 86.0, 100.0, "TERRORIST")]  # fmt: skip
    feed = db.execute(
        "SELECT r.no, k.weapon, k.headshot, a.name_as_printed, b.name_as_printed FROM kills k"
        " JOIN rounds r ON r.id = k.round_id JOIN player_names a ON a.id = k.killer_name_id"
        " JOIN player_names b ON b.id = k.victim_name_id ORDER BY k.t"
    ).fetchall()
    assert [tuple(r) for r in feed] == [(1, "ak47", 1, "aAa|KabaL", "GG.Eclair"), (2, "awp", 0, "GG.Eclair", "aAa|KabaL"),
                                       (3, "deagle", 0, "aAa|KabaL", "GG.Eclair")]  # fmt: skip


def test_copied_and_moved_modes(lib):
    db, store_root, src = lib
    src.mkdir()
    (src / "one.dem").write_bytes(build_demo())
    (src / "two.dem").write_bytes(build_demo(recorder_slot=1, hltv=False))
    run(lib, src / "one.dem", mode="copied")
    run(lib, src / "two.dem", mode="moved")
    rows = {r["file_name"]: r for r in db.execute("SELECT * FROM originals")}
    assert (src / "one.dem").exists() and not (src / "two.dem").exists()
    for name in ("one.dem", "two.dem"):
        kept = rows[name]["kept_path"]
        assert kept.endswith(".dem") and store.file_sha1(__import__("pathlib").Path(kept)) == rows[name]["sha1"]


def test_unreadable_and_empty_files(lib):
    db, _store, src = lib
    src.mkdir()
    (src / "broken.dem").write_bytes(b"HLDEMO\x00\x00" + b"\x00" * 10)
    with zipfile.ZipFile(src / "nodemo.zip", "w") as zf:
        zf.writestr("readme.txt", "nothing here")
    (src / "bad.zip").write_bytes(b"PK\x03\x04 not really a zip")
    s = run(lib, src)
    assert s.failed == 0 and s.matches == 0
    statuses = {r["file_name"]: (r["status"], r["demo_count"]) for r in db.execute("SELECT * FROM originals")}
    assert statuses["broken.dem"] == ("done", 1)
    assert statuses["nodemo.zip"] == ("no-demo", 0)
    assert statuses["bad.zip"][0] == "no-demo"
    err = db.execute("SELECT parse_error FROM demos").fetchone()[0]
    assert "HLDEMO" in err or "demo" in err
    bad = db.execute("SELECT errors FROM originals WHERE file_name = 'bad.zip'").fetchone()[0]
    assert bad and "bad.zip" in bad


def test_same_demo_twice_in_one_archive(lib):
    db, _store, src = lib
    src.mkdir()
    data = build_demo()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as inner:
        inner.writestr("gg_aaa-t.dem", data)
    with zipfile.ZipFile(src / "gg-aaa.zip", "w") as zf:
        zf.writestr("gg_aaa-t.dem", data)
        zf.writestr("gg_aaa-ct.zip", buf.getvalue())  # nested copy of the same demo
    s = run(lib, src)
    assert (s.imported, s.matches, s.failed, s.demos_new) == (1, 1, 0, 1)
    assert db.execute("SELECT count(*) FROM match_demos").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM archive_members WHERE demo_sha1 IS NOT NULL").fetchone()[0] == 2


def test_curated_names_placeholders_and_pov(lib):
    db, _store, src = lib
    src.mkdir()
    pov = build_demo(recorder_slot=1, hltv=False)
    with zipfile.ZipFile(src / "[unknown]_[unknown]_[de_dust2]_[KabaL]_[ctt].zip", "w") as zf:
        zf.writestr(zipfile.ZipInfo("a.dem", date_time=(2002, 5, 4, 21, 0, 0)), pov)
    run(lib, src)
    m = matches(db)[0]
    # Clan tags from the demo win over the "unknown" placeholders of the curated name.
    teams = {r[0] for r in db.execute("SELECT tag_as_printed FROM teams")}
    assert "unknown" not in teams
    assert m["pov"] == "KabaL"


def test_player_in_both_lineups_is_kept(lib):
    """The catalogue lists a reused slot's name in both line-ups; so must we."""
    from oldschool.importer import Writer

    db, _store, src = lib
    src.mkdir()
    (src / "x.dem").write_bytes(build_demo())
    run(lib, src)
    sha1 = db.execute("SELECT sha1 FROM demos").fetchone()[0]
    db.execute("DELETE FROM match_demos")
    target = {
        "maps": ["de_dust2"], "team1": "aAa", "team2": "GG", "version": "CS1.5", "version_basis": [], "year": "2002",
        "year_basis": "test", "pov": "HLTV", "sides": "ctt", "team_basis": "test", "filename": "x.zip",
        "servers": [], "scores": [], "members": ["x.dem"], "demo_sha1": [sha1],
        "lineups": {"team1": {"aAa|Ozie": {"steamid": None, "aliases": []}},
                    "team2": {"aAa|Ozie": {"steamid": None, "aliases": []}}},
    }  # fmt: skip
    assert Writer(db)._write_match(1, target)
    keys = db.execute("SELECT team_key FROM match_players mp JOIN player_names p ON p.id = mp.player_name_id"
                      " WHERE p.name_as_printed = 'aAa|Ozie' AND mp.match_id = (SELECT max(id) FROM matches)"
                      " ORDER BY 1").fetchall()  # fmt: skip
    assert [k[0] for k in keys] == ["team1", "team2"]


def test_import_without_demo_copies_reads_from_the_source(lib):
    from oldschool import sources

    db, store_root, src = lib
    src.mkdir()
    data = build_demo()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as inner:
        inner.writestr("x.dem", data)
    with zipfile.ZipFile(src / "pack.zip", "w") as zf:
        zf.writestr("nested/x.zip", buf.getvalue())
    import_paths(db, [src], store_root, workers=1, copy_demos=False)
    sha1 = db.execute("SELECT sha1 FROM demos").fetchone()[0]
    assert not store.demo_path(store_root, sha1).exists()
    assert db.execute("SELECT store_path FROM demos").fetchone()[0] == ""
    assert sources.demo_bytes(db, store_root, sha1) == data
    m = matches(db)[0]
    assert (m["demo_count"], m["kill_count"]) == (1, 3)  # totals stored at import (migration 0003)
    (src / "pack.zip").unlink()
    with pytest.raises(sources.DemoUnavailable):
        sources.demo_bytes(db, store_root, sha1)
