"""Read-only library endpoints: matches, rounds, players, teams."""

from __future__ import annotations

import json
import sqlite3
from pathlib import PurePosixPath
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from oldschool.api.deps import Db
from oldschool.api.models import (
    DemoRounds,
    Facet,
    Kill,
    LibraryStats,
    Lineup,
    LineupPlayer,
    MatchDemo,
    MatchDetail,
    MatchPage,
    MatchSummary,
    PlayerDetail,
    PlayerMatch,
    PlayerSummary,
    Round,
    Source,
    TeamDetail,
    TeamSummary,
)
from oldschool.player import engines as en

router = APIRouter(prefix="/api")

# One row per match with everything the list needs (totals are stored at
# import, migration 0003).
SUMMARY_SQL = """
SELECT m.id, m.release, m.year_est, m.year_basis, m.map, m.pov, m.sides, m.servers, m.scores, m.library_name,
       t1.tag_as_printed AS team1, t2.tag_as_printed AS team2,
       m.demo_count AS demos, m.duration_s, m.kill_count AS kills, m.file_date
FROM matches m
LEFT JOIN teams t1 ON t1.id = m.team1_id
LEFT JOIN teams t2 ON t2.id = m.team2_id
"""

SORTS = {
    "date": "m.year_est {dir}, file_date {dir}, m.id {dir}",
    "release": "m.release {dir}, m.year_est {dir}, m.id",
    "map": "m.map {dir}, m.year_est, m.id",
    "team": "lower(coalesce(team1, '~')) {dir}, lower(coalesce(team2, '~')) {dir}, m.id",
    "kills": "kills {dir}, m.id",
    "duration": "duration_s {dir}, m.id",
}


def _scores(raw: str | None) -> str:
    parts = []
    for s in json.loads(raw or "[]"):
        if s:
            parts.append(f"CT {s.get('CT', '?')} : T {s.get('TERRORIST', '?')}")
    return " | ".join(parts)


def _summary(r: sqlite3.Row) -> MatchSummary:
    return MatchSummary(
        id=r["id"],
        release=r["release"],
        year=r["year_est"],
        year_basis=r["year_basis"],
        file_date=r["file_date"][:10] if r["file_date"] else None,
        map=r["map"],
        team1=r["team1"],
        team2=r["team2"],
        pov=r["pov"],
        sides=r["sides"],
        servers=json.loads(r["servers"] or "[]"),
        scores=_scores(r["scores"]),
        demos=r["demos"],
        duration_s=round(r["duration_s"] or 0),
        kills=r["kills"] or 0,
    )


def _like(s: str) -> str:
    return "%" + s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def search_groups(text: str) -> list[list[str]]:
    """Search syntax shared by the library's text fields, as LIKE patterns:
    ``a|b`` any of them, ``a + b`` all of them, ``*`` anything in between,
    ``"..."`` the text as typed (for names with | + or * in them).
    Returns groups (all must match) of alternatives (one must match)."""
    groups: list[list[str]] = [[]]
    word: list[tuple[str, bool]] = []  # (character, typed inside quotes)
    quoted = False

    def end_word():
        while word and not word[0][1] and word[0][0].isspace():
            word.pop(0)
        while word and not word[-1][1] and word[-1][0].isspace():
            word.pop()
        if word:
            out = []
            for ch, lit in word:
                esc = ch.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                out.append("%" if ch == "*" and not lit else esc)
            groups[-1].append("%" + "".join(out) + "%")
        word.clear()

    for ch in text:
        if ch == '"':
            quoted = not quoted
        elif quoted:
            word.append((ch, True))
        elif ch == "|":
            end_word()
        elif ch == "+":
            end_word()
            groups.append([])
        else:
            word.append((ch, False))
    end_word()
    return [g for g in groups if g]


def _search(text: str, template: str, per_alt: int, where: list, args: list) -> None:
    """One WHERE condition per group; ``template`` holds ``per_alt`` placeholders."""
    for group in search_groups(text):
        where.append("(" + " OR ".join(f"({template})" for _ in group) + ")")
        for pattern in group:
            args += [pattern] * per_alt


NAME_IN_MATCH = (
    "EXISTS (SELECT 1 FROM match_players mp JOIN player_names p ON p.id = mp.player_name_id"
    " WHERE mp.match_id = m.id AND {cond})"
)


@router.get("/stats")
def stats(db: Db) -> LibraryStats:
    def facet(sql: str) -> list[Facet]:
        return [Facet(value=str(v), count=n) for v, n in db.execute(sql) if v is not None]

    count = {t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("matches", "demos", "rounds", "kills")}
    return LibraryStats(
        matches=count["matches"],
        demos=count["demos"],
        rounds=count["rounds"],
        kills=count["kills"],
        player_names=db.execute("SELECT count(*) FROM player_names").fetchone()[0],
        teams=db.execute("SELECT count(*) FROM teams").fetchone()[0],
        releases=facet("SELECT release, count(*) FROM matches GROUP BY release ORDER BY release"),
        maps=facet("SELECT map, count(*) n FROM matches GROUP BY map ORDER BY n DESC, map"),
        years=facet("SELECT year_est, count(*) FROM matches GROUP BY year_est ORDER BY year_est"),
    )


@router.get("/matches")
def list_matches(
    db: Db,
    q: str = Query("", description="team, player, server or file; same syntax as player"),
    player: str = Query("", description="name part; 'a|b' any of them, 'a+b' all in the same match, '*' anything"),
    steamid: str = "",
    team: str = Query("", description="team tag; same syntax as player ('aAa+GG': a match between both)"),
    map: str = "",
    release: list[str] = Query(default_factory=list),
    year_from: str = "",
    year_to: str = "",
    include_unknown_year: bool = True,
    pov: Literal["", "hltv", "player"] = "",
    sort: Literal["date", "release", "map", "team", "kills", "duration"] = "date",
    dir: Literal["asc", "desc"] = "asc",
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
) -> MatchPage:
    where, args = [], []
    _search(
        q,
        "m.library_name LIKE ? ESCAPE '\\' OR team1 LIKE ? ESCAPE '\\' OR team2 LIKE ? ESCAPE '\\'"
        " OR m.servers LIKE ? ESCAPE '\\' OR " + NAME_IN_MATCH.format(cond="p.name_as_printed LIKE ? ESCAPE '\\'"),
        5,
        where,
        args,
    )
    _search(player, NAME_IN_MATCH.format(cond="p.name_as_printed LIKE ? ESCAPE '\\'"), 1, where, args)
    if steamid.strip():
        where.append(NAME_IN_MATCH.format(cond="p.steamid = ?"))
        args.append(steamid.strip())
    _search(team, "team1 LIKE ? ESCAPE '\\' OR team2 LIKE ? ESCAPE '\\'", 2, where, args)
    if map:
        where.append("m.map = ?")
        args.append(map)
    if release:
        where.append(f"m.release IN ({','.join('?' * len(release))})")
        args += release
    if year_from or year_to:
        rng = "(m.year_est BETWEEN ? AND ?)"
        where.append(f"({rng} OR m.year_est = 'unknown-year')" if include_unknown_year else rng)
        args += [year_from or "0000", year_to or "9999"]
    elif not include_unknown_year:
        where.append("m.year_est != 'unknown-year'")
    if pov == "hltv":
        where.append("m.pov = 'HLTV'")
    elif pov == "player":
        where.append("coalesce(m.pov, '') != 'HLTV'")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    # team1/team2/kills are output columns: wrap so WHERE and ORDER BY can use them.
    sql = f"SELECT * FROM ({SUMMARY_SQL}) AS m{clause}"
    total = db.execute(f"SELECT count(*) FROM ({sql})", args).fetchone()[0]
    order = SORTS[sort].format(dir=dir.upper()).replace("m.", "")
    rows = db.execute(f"{sql} ORDER BY {order} LIMIT ? OFFSET ?", [*args, size, (page - 1) * size]).fetchall()
    return MatchPage(total=total, page=page, size=size, items=[_summary(r) for r in rows])


def _match_row(db: sqlite3.Connection, match_id: int) -> sqlite3.Row:
    row = db.execute(f"SELECT * FROM ({SUMMARY_SQL}) WHERE id = ?", (match_id,)).fetchone()
    if not row:
        raise HTTPException(404, "match not found")
    return row


@router.get("/matches/{match_id}")
def match_detail(match_id: int, db: Db) -> MatchDetail:
    r = _match_row(db, match_id)
    m = db.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    lineups: dict[str, list[LineupPlayer]] = {}
    for p in db.execute(
        """SELECT mp.team_key, p.id, p.name_as_printed, p.steamid, mp.aliases,
                  coalesce(sum(dp.kills), 0) k, coalesce(sum(dp.deaths), 0) d, coalesce(sum(dp.headshots), 0) hs
           FROM match_players mp JOIN player_names p ON p.id = mp.player_name_id
           LEFT JOIN demo_players dp ON dp.player_name_id = p.id
                AND dp.demo_sha1 IN (SELECT demo_sha1 FROM match_demos WHERE match_id = mp.match_id)
           WHERE mp.match_id = ? GROUP BY mp.team_key, p.id ORDER BY mp.team_key, lower(p.name_as_printed)""",
        (match_id,),
    ):
        lineups.setdefault(p["team_key"], []).append(
            LineupPlayer(
                name_id=p["id"],
                name=p["name_as_printed"],
                steamid=p["steamid"],
                aliases=json.loads(p["aliases"] or "[]"),
                kills=p["k"],
                deaths=p["d"],
                headshots=p["hs"],
            )
        )
    order = [k for k in ("team1", "team2") if k in lineups] + sorted(k for k in lineups if k not in ("team1", "team2"))
    tags = {"team1": r["team1"], "team2": r["team2"]}
    demos = []
    for d in db.execute(
        """SELECT md.part_no, md.label, d.sha1, d.recorder_kind, d.net_protocol, d.duration_s, d.kill_count,
                  d.analysis, d.map, d.release, (SELECT count(*) FROM rounds WHERE demo_sha1 = d.sha1) AS rounds
           FROM match_demos md JOIN demos d ON d.sha1 = md.demo_sha1 WHERE md.match_id = ? ORDER BY md.part_no""",
        (match_id,),
    ):
        a = json.loads(d["analysis"] or "{}")
        rec = a.get("recorder") or {}
        engine, why = en.route(db, d["net_protocol"], d["release"])
        demos.append(
            MatchDemo(
                sha1=d["sha1"],
                part=d["part_no"],
                member=d["label"],
                label=PurePosixPath(d["label"]).name,
                recorder_kind=d["recorder_kind"],
                recorder_name=rec.get("name"),
                net_protocol=d["net_protocol"],
                duration_s=d["duration_s"],
                kills=d["kill_count"],
                rounds=d["rounds"],
                final_score=a.get("final_score") or {},
                engine=engine["name"] if engine else None,
                play_problem=None if engine else why,
            )
        )
    sources = [
        Source(
            file_name=s["file_name"],
            source_path=s["source_path"],
            member="/".join(x for x in (s["chain"], s["name"]) if x),
        )
        for s in db.execute(
            """SELECT DISTINCT o.file_name, o.source_path, a.chain, a.name FROM archive_members a
               JOIN originals o ON o.id = a.original_id
               WHERE a.demo_sha1 IN (SELECT demo_sha1 FROM match_demos WHERE match_id = ?)
               ORDER BY o.id, a.chain, a.name""",
            (match_id,),
        )
    ]
    return MatchDetail(
        summary=_summary(r),
        release_basis=json.loads(m["release_basis"] or "[]"),
        team_basis=m["team_basis"],
        library_name=m["library_name"],
        lineups=[
            Lineup(key=k, tag=tags.get(k, k if k not in ("team1", "team2") else None), players=lineups[k])
            for k in order
        ],
        demos=demos,
        sources=sources,
    )


@router.get("/demos/{sha1}/rounds")
def demo_rounds(sha1: str, db: Db) -> DemoRounds:
    if not db.execute("SELECT 1 FROM demos WHERE sha1 = ?", (sha1,)).fetchone():
        raise HTTPException(404, "demo not found")
    kills: dict[int | None, list[Kill]] = {}
    for k in db.execute(
        """SELECT k.round_id, k.t, k.weapon, k.headshot, k.killer_side, k.victim_side,
                  a.id kid, a.name_as_printed killer, b.id vid, b.name_as_printed victim
           FROM kills k LEFT JOIN player_names a ON a.id = k.killer_name_id
           LEFT JOIN player_names b ON b.id = k.victim_name_id
           WHERE k.demo_sha1 = ? ORDER BY k.t, k.id""",
        (sha1,),
    ):
        kills.setdefault(k["round_id"], []).append(
            Kill(
                t=k["t"],
                killer=k["killer"],
                killer_id=k["kid"],
                killer_side=k["killer_side"],
                victim=k["victim"],
                victim_id=k["vid"],
                victim_side=k["victim_side"],
                weapon=k["weapon"],
                headshot=None if k["headshot"] is None else bool(k["headshot"]),
            )
        )
    rounds = [
        Round(
            no=r["no"],
            start=r["start_t"],
            start_basis=r["start_basis"],
            end=r["end_t"],
            winner=r["winner"],
            reason=r["reason"],
            score_ct=r["score_ct"],
            score_t=r["score_t"],
            kills=kills.get(r["id"], []),
        )
        for r in db.execute("SELECT * FROM rounds WHERE demo_sha1 = ? ORDER BY no", (sha1,))
    ]
    return DemoRounds(sha1=sha1, rounds=rounds, other_kills=len(kills.get(None, [])))


PLAYER_SQL = """
SELECT p.id, p.name_as_printed, p.steamid,
       (SELECT count(DISTINCT match_id) FROM match_players WHERE player_name_id = p.id) AS matches,
       (SELECT coalesce(sum(kills), 0) FROM demo_players WHERE player_name_id = p.id) AS kills,
       (SELECT coalesce(sum(deaths), 0) FROM demo_players WHERE player_name_id = p.id) AS deaths
FROM player_names p
"""


def _player(r: sqlite3.Row) -> PlayerSummary:
    return PlayerSummary(
        name_id=r["id"],
        name=r["name_as_printed"],
        steamid=r["steamid"],
        matches=r["matches"],
        kills=r["kills"],
        deaths=r["deaths"],
    )


@router.get("/players")
def list_players(db: Db, q: str = "", limit: int = Query(100, ge=1, le=1000)) -> list[PlayerSummary]:
    if q.strip():
        rows = db.execute(
            f"SELECT * FROM ({PLAYER_SQL}) WHERE name_as_printed LIKE ? ESCAPE '\\' OR steamid = ?"
            " ORDER BY matches DESC, lower(name_as_printed) LIMIT ?",
            (_like(q.strip()), q.strip(), limit),
        )
    else:
        rows = db.execute(
            f"SELECT * FROM ({PLAYER_SQL}) ORDER BY matches DESC, lower(name_as_printed) LIMIT ?", (limit,)
        )
    return [_player(r) for r in rows if r["matches"] or q.strip()]


@router.get("/players/{name_id}")
def player_detail(name_id: int, db: Db) -> PlayerDetail:
    me = db.execute(f"SELECT * FROM ({PLAYER_SQL}) WHERE id = ?", (name_id,)).fetchone()
    if not me:
        raise HTTPException(404, "player name not found")
    same_sid = (
        [
            _player(r)
            for r in db.execute(f"SELECT * FROM ({PLAYER_SQL}) WHERE steamid = ? AND id != ?", (me["steamid"], name_id))
        ]
        if me["steamid"]
        else []
    )
    same_name = [
        _player(r)
        for r in db.execute(
            f"SELECT * FROM ({PLAYER_SQL}) WHERE name_as_printed = ? AND id != ?", (me["name_as_printed"], name_id)
        )
    ]
    matches = []
    for r in db.execute(
        f"""SELECT s.*, mp.team_key,
                   (SELECT coalesce(sum(dp.kills), 0) FROM demo_players dp JOIN match_demos md ON md.demo_sha1 = dp.demo_sha1
                     WHERE md.match_id = s.id AND dp.player_name_id = ?) AS pk,
                   (SELECT coalesce(sum(dp.deaths), 0) FROM demo_players dp JOIN match_demos md ON md.demo_sha1 = dp.demo_sha1
                     WHERE md.match_id = s.id AND dp.player_name_id = ?) AS pd,
                   (SELECT coalesce(sum(dp.headshots), 0) FROM demo_players dp JOIN match_demos md ON md.demo_sha1 = dp.demo_sha1
                     WHERE md.match_id = s.id AND dp.player_name_id = ?) AS phs
            FROM match_players mp JOIN ({SUMMARY_SQL}) s ON s.id = mp.match_id
            WHERE mp.player_name_id = ? ORDER BY s.year_est, s.file_date, s.id""",
        (name_id, name_id, name_id, name_id),
    ):
        matches.append(
            PlayerMatch(match=_summary(r), team_key=r["team_key"], kills=r["pk"], deaths=r["pd"], headshots=r["phs"])
        )
    hs = db.execute(
        "SELECT coalesce(sum(headshots), 0) FROM demo_players WHERE player_name_id = ?", (name_id,)
    ).fetchone()[0]
    return PlayerDetail(player=_player(me), headshots=hs, same_steamid=same_sid, same_name=same_name, matches=matches)


TEAM_SQL = """
SELECT t.id, t.tag_as_printed,
       (SELECT count(*) FROM matches m WHERE m.team1_id = t.id OR m.team2_id = t.id) AS matches
FROM teams t
"""


@router.get("/teams")
def list_teams(db: Db, q: str = "", limit: int = Query(100, ge=1, le=1000)) -> list[TeamSummary]:
    cond, args = ("WHERE tag_as_printed LIKE ? ESCAPE '\\'", [_like(q.strip())]) if q.strip() else ("", [])
    rows = db.execute(
        f"SELECT * FROM ({TEAM_SQL}) {cond} ORDER BY matches DESC, lower(tag_as_printed) LIMIT ?", [*args, limit]
    )
    return [TeamSummary(id=r["id"], tag=r["tag_as_printed"], matches=r["matches"]) for r in rows]


@router.get("/teams/{team_id}")
def team_detail(team_id: int, db: Db) -> TeamDetail:
    t = db.execute(f"SELECT * FROM ({TEAM_SQL}) WHERE id = ?", (team_id,)).fetchone()
    if not t:
        raise HTTPException(404, "team not found")
    matches = [
        _summary(r)
        for r in db.execute(
            f"SELECT * FROM ({SUMMARY_SQL}) s WHERE s.id IN (SELECT id FROM matches WHERE team1_id = ? OR team2_id = ?)"
            " ORDER BY s.year_est, s.file_date, s.id",
            (team_id, team_id),
        )
    ]
    players = [
        _player(r)
        for r in db.execute(
            f"""SELECT ps.* FROM ({PLAYER_SQL}) ps WHERE ps.id IN (
                  SELECT mp.player_name_id FROM match_players mp JOIN matches m ON m.id = mp.match_id
                  WHERE (mp.team_key = 'team1' AND m.team1_id = ?) OR (mp.team_key = 'team2' AND m.team2_id = ?))
                ORDER BY ps.matches DESC, lower(ps.name_as_printed) LIMIT 200""",
            (team_id, team_id),
        )
    ]
    return TeamDetail(
        team=TeamSummary(id=t["id"], tag=t["tag_as_printed"], matches=t["matches"]), players=players, matches=matches
    )
