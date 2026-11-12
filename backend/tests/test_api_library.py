"""Library API on a small library imported from synthetic demos."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from oldschool.api.app import create_app
from oldschool.db.migrate import open_database
from oldschool.importer import import_paths
from tests.demo_factory import MATCH, build_demo, build_round_demo


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("lib")
    lib = tmp / "sorted"
    (lib / "CS1.5" / "2002").mkdir(parents=True)
    with zipfile.ZipFile(lib / "CS1.5" / "2002" / "aaa_vs_gg_dust2.zip", "w") as zf:
        zf.writestr(
            zipfile.ZipInfo("kabal_dust2.dem", date_time=(2002, 5, 4, 21, 0, 0)), build_demo(1, hltv=False, steam=True)
        )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as inner:
        inner.writestr(zipfile.ZipInfo("gg_aaa.dem", date_time=(2002, 1, 2, 3, 4, 5)), build_demo())
    with zipfile.ZipFile(lib / "CS1.5" / "2002" / "gg-aaa.zip", "w") as zf:
        zf.writestr("pack/gg_aaa.zip", buf.getvalue())
    (lib / "rounds.dem").write_bytes(build_round_demo(MATCH))
    db = open_database(tmp / "t.sqlite")
    import_paths(db, [lib], tmp / "store", workers=1)
    db.close()
    return TestClient(create_app(tmp / "t.sqlite", store=tmp / "store", scan_on_start=False))


def test_stats(client):
    s = client.get("/api/stats").json()
    assert (s["matches"], s["demos"]) == (3, 3)
    assert {f["value"] for f in s["releases"]} == {"CS1.5"}
    assert s["rounds"] == 3


def test_list_search_and_filters(client):
    page = client.get("/api/matches").json()
    assert page["total"] == 3 and len(page["items"]) == 3
    first = page["items"][0]
    assert set(first) >= {"id", "release", "year", "map", "team1", "team2", "pov", "scores", "kills", "duration_s"}
    assert client.get("/api/matches", params={"q": "kabal"}).json()["total"] == 3  # name in every line-up
    assert client.get("/api/matches", params={"pov": "hltv"}).json()["total"] == 2
    assert client.get("/api/matches", params={"pov": "player"}).json()["total"] == 1
    assert client.get("/api/matches", params={"player": "kabal+eclair"}).json()["total"] == 3
    assert client.get("/api/matches", params={"player": "nobody|kabal"}).json()["total"] == 3
    assert client.get("/api/matches", params={"player": "nobody"}).json()["total"] == 0
    assert client.get("/api/matches", params={"steamid": "STEAM_0:1:1"}).json()["total"] == 1
    assert (
        client.get("/api/matches", params={"team": "gg", "map": "de_dust2"}).json()["total"] == 2
    )  # the round demo has no clan tags
    assert client.get("/api/matches", params={"release": ["CS1.6"]}).json()["total"] == 0
    assert client.get("/api/matches", params={"q": "50%_"}).json()["total"] == 0  # LIKE wildcards are escaped
    by_kills = client.get("/api/matches", params={"sort": "kills", "dir": "desc"}).json()["items"]
    assert [m["kills"] for m in by_kills] == sorted((m["kills"] for m in by_kills), reverse=True)
    paged = client.get("/api/matches", params={"size": 2, "page": 2}).json()
    assert (paged["total"], len(paged["items"])) == (3, 1)


def test_match_detail_lineups_demos_sources(client):
    m = next(x for x in client.get("/api/matches", params={"pov": "player"}).json()["items"])
    d = client.get(f"/api/matches/{m['id']}").json()
    assert d["library_name"] == "[aAa]_[GG]_[de_dust2]_[KabaL]_[ctt].zip"
    assert [lu["key"] for lu in d["lineups"]][:2] == ["team1", "team2"]
    team1 = d["lineups"][0]
    assert team1["tag"] == "aAa"
    kabal = next(p for p in team1["players"] if p["name"] == "aAa|KabaL")
    assert (kabal["steamid"], kabal["kills"], kabal["headshots"]) == ("STEAM_0:1:1", 1, 1)
    demo = d["demos"][0]
    assert demo["recorder_kind"] == "player" and demo["net_protocol"] == 46
    assert demo["engine"] is None and "no working install for CS1.5" in demo["play_problem"]
    assert d["sources"][0]["member"] == "kabal_dust2.dem"
    assert client.get("/api/matches/9999").status_code == 404


def test_rounds_and_feed(client):
    m = next(
        x
        for x in client.get("/api/matches").json()["items"]
        if x["demos"] and x["kills"] == 3 and x["scores"].startswith("CT 0")
    )
    d = client.get(f"/api/matches/{m['id']}").json()
    r = client.get(f"/api/demos/{d['demos'][0]['sha1']}/rounds").json()
    assert [x["no"] for x in r["rounds"]] == [1, 2, 3]
    k = r["rounds"][0]["kills"][0]
    assert (k["killer"], k["victim"], k["weapon"], k["headshot"]) == ("aAa|KabaL", "GG.Eclair", "ak47", True)
    assert client.get("/api/demos/" + "0" * 40 + "/rounds").status_code == 404


def test_players_and_teams(client):
    players = client.get("/api/players", params={"q": "kabal"}).json()
    names = {(p["name"], p["steamid"]) for p in players}
    assert ("aAa|KabaL", "STEAM_0:1:1") in names and ("aAa|KabaL", "") in names
    with_sid = next(p for p in players if p["steamid"])
    detail = client.get(f"/api/players/{with_sid['name_id']}").json()
    assert detail["player"]["matches"] == 1 and detail["matches"][0]["team_key"] == "team1"
    assert [p["steamid"] for p in detail["same_name"]] == [""]  # same name, no SteamID: shown apart, not merged
    teams = client.get("/api/teams", params={"q": "aaa"}).json()
    assert teams[0]["tag"] == "aAa" and teams[0]["matches"] == 2
    t = client.get(f"/api/teams/{teams[0]['id']}").json()
    assert len(t["matches"]) == 2 and any(p["name"] == "aAa|KabaL" for p in t["players"])


def test_spa_fallback(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>")
    (dist / "favicon.svg").write_text("<svg/>")
    c = TestClient(create_app(tmp_path / "t.sqlite", frontend_dist=dist))
    assert c.get("/match/12").text == "<html>app</html>"
    assert c.get("/favicon.svg").text == "<svg/>"
    assert c.get("/api/nothing").status_code == 404
    assert c.get("/../t.sqlite").text == "<html>app</html>"


def test_parallel_requests_on_a_real_server(tmp_path):
    """Regression: connections were bound to the thread that opened them, and
    parallel page loads failed with 500 on the real server (not with the
    test client, which runs requests differently)."""
    import socket
    import threading
    import time
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor

    import uvicorn

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(create_app(tmp_path / "t.sqlite"), host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)

        def status(path):
            try:
                return urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10).status
            except urllib.error.HTTPError as e:
                return e.code

        urls = ["/api/health", "/api/stats", "/api/matches", "/api/players", "/api/teams"] * 8
        with ThreadPoolExecutor(10) as pool:
            codes = list(pool.map(status, urls))
        assert codes == [200] * len(urls)
    finally:
        server.should_exit = True
        thread.join(10)


def test_search_syntax_in_every_text_field(client):
    def total(**params):
        return client.get("/api/matches", params=params).json()["total"]

    assert total(team="aaa+gg") == 2  # a match between both tags
    assert total(team="aaa+nobody") == 0
    assert total(team="nobody|AAA") == 2
    assert total(q="aaa + kabal") == 3 and total(q="nobody|kabal") == 3 and total(q="aaa+nobody") == 0
    assert total(player="kab*l") == 3 and total(player="kab*x") == 0  # * = anything in between
    assert total(player="x|kabal") == 3
    assert total(player='"x|kabal"') == 0  # in quotes: the text as typed (names can hold | + *)
    assert total(player='"aAa|KabaL"') == 3


def test_search_groups():
    from oldschool.api.library import search_groups

    assert search_groups("heaton + pott1") == [["%heaton%"], ["%pott1%"]]
    assert search_groups(" heaton|ht + pott1 ") == [["%heaton%", "%ht%"], ["%pott1%"]]
    assert search_groups("k*l") == [["%k%l%"]]
    assert search_groups('"[GG]*x|y" + z') == [["%[GG]*x|y%"], ["%z%"]]
    assert search_groups("50%_") == [["%50\\%\\_%"]]
    assert search_groups(" | + ") == []
