"""Identify demos and group them into matches: release, year estimate,
teams, line-ups, POV/HLTV, sides, and a library file name.

Origin: ported on 2026-11-11 from the research wiki's ``wiki/tools/demo_catalog.py``
(calibrated on cs-demos/oldArchive), unchanged in behaviour.

Every estimate carries its basis. A year comes from an HLTV name stamp, an
archive member timestamp or a path; it is a filing estimate, never a played date.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from oldschool.archives import ARCHIVE_EXT, _ext
from oldschool.parser import goldsrc as gd

# ------------------------------------------------------- version and year

# Counter-Strike releases and the years they were the competitive version.
# Used only to sanity-check a member timestamp, never to invent a year.
VERSION_YEARS = {
    "CS1.0": (2000, 2001),
    "CS1.1": (2001, 2002),
    "CS1.3": (2001, 2003),
    "CS1.4": (2002, 2003),
    "CS1.5": (2002, 2006),
    "CS1.6": (2003, 2030),
}
CS16_WEAPONS = {"galil", "famas", "shield", "shieldgun"}
CS16_USERMSGS = {
    "BotProgress",
    "Brass",
    "Fog",
    "ShadowIdx",
    "Location",
    "ReceiveW",
    "TaskBar",
    "SpecHealth2",
    "BarTime2",
    "ItemStatus",
    "BuyClose",
    "BotVoice",
    "ShowTimer",
    "Account",
    "HealthInfo",
}


def guess_version(demo: dict) -> dict:
    """Return {'version', 'basis'}.

    Calibrated on cs-demos/oldArchive (1,574 archives) against its curated
    "Demos in 1.x.txt" lists and member dates (2026-11-08):
      protocol 43, no AllowSpec usermsg  -> 1.0  (4 demos, all dated <= 2001-02)
      protocol 43 with AllowSpec         -> 1.1  (curated 1.0/1.1 list)
      protocol 45, no BombDrop usermsg   -> 1.3  (curated 1.3 list; 1.2 not separated)
      protocol 45 with BombDrop          -> 1.4  (first plausible date 2002-04)
      protocol 46                        -> 1.5
      46 with famas/galil, or 47/48      -> 1.6  (curated 1.6-on-46 list)
    """
    proto = demo["header"]["network_protocol"]
    fp = demo.get("fingerprint", {})
    names = set(demo.get("usermsgs", {}))
    weapons = set(fp.get("weapons", []))
    basis = [f"network protocol {proto}"]
    if proto >= 47:
        return {"version": "CS1.6", "basis": basis}
    cs16 = sorted((weapons & CS16_WEAPONS) | (names & CS16_USERMSGS))
    if cs16:
        return {"version": "CS1.6", "basis": basis + ["1.6-only content: " + ",".join(cs16)]}
    if not names:
        basis.append("user-message table not found; release inferred from protocol only")
    if proto == 46:
        return {"version": "CS1.5", "basis": basis}
    if proto == 45:
        if "BombDrop" in names:
            return {"version": "CS1.4", "basis": basis + ["BombDrop usermsg present"]}
        return {
            "version": "CS1.3",
            "basis": basis + (["no BombDrop usermsg (1.2 and 1.3 not separated)"] if names else []),
        }
    if proto == 43:
        if names and "AllowSpec" not in names:
            return {"version": "CS1.0", "basis": basis + ["no AllowSpec usermsg"]}
        return {"version": "CS1.1", "basis": basis + (["AllowSpec usermsg present"] if names else [])}
    return {"version": "unknown", "basis": basis}


_PATH_YEAR = re.compile(r"(?<![0-9])(199[89]|20[0-2][0-9])(?![0-9])")
_HLTV_STAMP = re.compile(r"-(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})-")


def guess_year(demos: list, path: str, version: str) -> dict:
    lo, hi = VERSION_YEARS.get(version, (1999, 2030))
    candidates = []
    for d in demos:
        m = _HLTV_STAMP.search(PurePosixPath(d["member"]).name)
        if m:
            y = 2000 + int(m.group(1))
            if 1 <= int(m.group(2)) <= 12 and lo <= y <= hi:
                candidates.append((y, "HLTV auto-name stamp in demo filename"))
    times = sorted(d["mtime"] for d in demos if d.get("mtime") and d.get("mtime_basis") == "archive_member")
    for t in times:
        y = int(t[:4])
        if lo <= y <= hi:
            candidates.append(
                (y, "earliest .dem member timestamp in archive (file write time, not a verified played date)")
            )
            break
    for m in _PATH_YEAR.finditer(path):
        y = int(m.group(1))
        if lo <= y <= hi:
            candidates.append((y, "year written in the archive path"))
            break
    if candidates:
        y, why = candidates[0]
        return {"year": str(y), "basis": why, "candidates": [list(c) for c in candidates]}
    return {"year": "unknown-year", "basis": "no stamp, usable member timestamp or path year within the version era"}


# ---------------------------------------------------------- proposal/name

_BAD_CHARS = re.compile(r'[\[\]\\/:*?"<>|\x00-\x1f]+')
KEEP_EXT = (".zip", ".rar", ".7z", ".ace")


def safe(s: str | None, fallback: str) -> str:
    s = _BAD_CHARS.sub("", s or "").strip(" ._-")
    s = re.sub(r"\s+", " ", s)
    return s[:40].strip(" ._-") if s else fallback


def _nested(member: str) -> bool:
    return any(_ext(part) in ARCHIVE_EXT for part in PurePosixPath(member).parts[:-1])


def _signature(d: dict) -> dict:
    rec = d["recorder"]
    names = {n.casefold() for p in d["players"] if not p["hltv"] for n in p["names"]}
    rnames = rec.get("names") or ([rec["name"]] if rec.get("name") else [])
    return {
        "map": d["header"]["map"].casefold(),
        "names": names,
        "tags": {t["tag"].casefold() for t in d["teams"] if t["tag"]},
        "kind": "hltv" if rec["kind"] == "hltv" else "player",
        "recorder": {n.casefold() for n in rnames},
    }


def _same_match(a: dict, b: dict) -> bool:
    if a["map"] != b["map"] or a["kind"] != b["kind"]:
        return False
    if a["kind"] == "player" and a["recorder"] and b["recorder"] and not a["recorder"] & b["recorder"]:
        return False
    if len(a["tags"]) == 2 and len(b["tags"]) == 2:
        return a["tags"] == b["tags"]
    if a["names"] and b["names"]:
        return len(a["names"] & b["names"]) >= 0.7 * min(len(a["names"]), len(b["names"]))
    return True


def split_matches(demos: list) -> list[list]:
    """Group one archive's demos into matches: same map, same recorder
    (HLTV or the same player) and the same line-ups. Halves of one match stay
    together; a POV pack of several matches is split."""
    groups: list[list] = []
    for d in sorted(demos, key=lambda d: d["member"]):
        sig = _signature(d)
        for g in groups:
            if any(_same_match(_signature(x), sig) for x in g):
                g.append(d)
                break
        else:
            groups.append([d])
    return groups


def propose(rec: dict) -> dict:
    demos = [d for d in rec["demos"] if "error" not in d]
    if not demos:
        return {"status": "no-demo" if not rec["demos"] else "unreadable"}
    curated = _curated_name(rec["path"])
    if curated:
        # A person already grouped this archive as one match: only split it
        # by map. The part on the map named in the filename keeps that name.
        by_map: dict[str, list] = {}
        for d in demos:
            by_map.setdefault(d["header"]["map"].casefold(), []).append(d)
        if len(by_map) == 1:
            return {"status": "ok", "targets": [_propose_group(rec, demos, True)]}
        named = curated[2].casefold()
        return {
            "status": "ok",
            "targets": [_propose_group(rec, g, False, keep_curated=(m == named)) for m, g in by_map.items()],
        }
    groups = split_matches(demos)
    whole = len(groups) == 1 and _ext(rec["path"]) in KEEP_EXT and not any(_nested(d["member"]) for d in demos)
    return {"status": "ok", "targets": [_propose_group(rec, g, whole) for g in groups]}


def _propose_group(rec: dict, demos: list, whole: bool, keep_curated: bool = False) -> dict:
    versions = sorted({d["version"]["version"] for d in demos})
    version = versions[0] if len(versions) == 1 else "+".join(versions)
    maps = list({d["header"]["map"].casefold(): d["header"]["map"].lower() for d in demos}.values())
    kinds = [d["recorder"]["kind"] for d in demos]
    hltv = all(k == "hltv" for k in kinds)
    pov_names = [
        d["recorder"].get("name") for d in demos if d["recorder"]["kind"] == "player" and d["recorder"].get("name")
    ]

    team_tags: list[str] = []
    for d in demos:
        for t in d["teams"]:
            if t["tag"] and t["tag"].casefold() not in (x.casefold() for x in team_tags):
                team_tags.append(t["tag"])
    pov_tag = None
    pov_sides: list[str] = []
    for d in demos:
        slot = d["recorder"]["slot"]
        for t in d["teams"]:
            if slot in t["slots"]:
                pov_tag = pov_tag or t["tag"]
        if d["recorder"]["kind"] == "player":
            pov_sides += [s for s in d["recorder"]["sides"] if s not in pov_sides]
    curated = _curated_name(rec["path"]) if (whole or keep_curated) else None
    if curated:
        # "unknown" in a curated name is a placeholder, not a team called "unknown".
        known = tuple(None if _placeholder(x) else x for x in curated[:2])
        hint = known if any(known) else None
    else:
        hint = _filename_teams(rec["path"], maps)
    team1 = team2 = None
    if pov_tag:
        team1 = pov_tag
        team2 = next((t for t in team_tags if t.casefold() != pov_tag.casefold()), None)
    elif hint and not team_tags:
        team1, team2 = hint
    elif team_tags:
        # HLTV: order the tags as the archive/demo names list the teams.
        haystack = _norm(" ".join([PurePosixPath(rec["path"]).name] + [d["member"] for d in demos]))

        def rank(tag):
            if hint:
                for i, h in enumerate(hint):
                    if h and _same_team(tag, h):
                        return (i, 0)
            pos = [haystack.find(t) for t in [_norm(tag)] + [_norm(w) for w in re.split(r"[\W_]+", tag) if len(w) >= 3]]
            pos = [p for p in pos if p >= 0]
            return (2, min(pos) if pos else 10**6)

        ordered = sorted(team_tags, key=rank)
        team1 = ordered[0]
        team2 = ordered[1] if len(ordered) > 1 else None
    if hint and not team2:
        team2 = next((h for h in hint if h and (not team1 or not _same_team(team1, h))), None)
    if hltv:
        pov = "HLTV"
        sides = []
        for d in demos:
            for t in d["teams"]:
                if team1 and t["tag"] and t["tag"].casefold() == team1.casefold():
                    sides += [s for s in t["sides"] if s not in sides]
        pov_sides = sides
    else:
        raw = pov_names[0] if pov_names else None
        pov = gd.display_alias(raw, pov_tag) if raw else None
        if curated and not _placeholder(curated[3]) and safe(pov, "") != curated[3]:
            # A person named the POV in the file name. Prefer the recorder name
            # that matches it: players often renamed themselves "ready"/"go".
            names = [n for d in demos if d["recorder"]["kind"] == "player" for n in d["recorder"].get("names") or []]
            pov = next((a for a in (gd.display_alias(n, pov_tag) for n in names) if safe(a, "") == curated[3]), pov)
    side = "".join(gd.SIDE_SHORT[s] for s in ("CT", "TERRORIST") if s in pov_sides) or "unknown"
    if len(pov_sides) > 1:
        side = "ctt"
    ext = _ext(rec["path"]) if whole else ".zip"
    year = guess_year(demos, rec["path"], version)
    name = (
        "_".join(
            f"[{x}]"
            for x in (
                safe(team1, "unknown"),
                safe(team2, "unknown"),
                safe("+".join(maps), "unknown"),
                safe(pov, "unknown"),
                side,
            )
        )
        + ext
    )
    result = {
        "version": version,
        "version_basis": sorted({"; ".join(d["version"]["basis"]) for d in demos}),
        "year": year["year"],
        "year_basis": year["basis"],
        "team1": team1,
        "team2": team2,
        "maps": maps,
        "pov": pov,
        "sides": side,
        "filename": name,
        "team_basis": "player-name clan tag" if team_tags else ("archive filename" if hint else "none"),
        "mode": "copy" if whole else "repack",
        "members": [d["member"] for d in demos],
        "demo_sha1": [d["sha1"] for d in demos],
        "lineups": _lineups(demos, team1, team2),
        "servers": sorted(
            {d["server"].get("hostname") for d in demos if d.get("server") and d["server"].get("hostname")}
        ),
        "scores": [d["final_score"] for d in demos],
    }
    if curated:
        # Already named by a person in the target scheme: keep their name,
        # keep ours alongside for comparison.
        result["derived_filename"] = name
        result["filename"] = PurePosixPath(rec["path"]).name if whole else PurePosixPath(rec["path"]).stem + ".zip"
        result["team_basis"] = "existing curated filename"
    return result


def _lineups(demos: list, team1: str | None, team2: str | None) -> dict:
    """Players per team across the group's demos: alias plus SteamID if any."""
    out: dict[str, dict] = {}
    for d in demos:
        by_slot = {p["slot"]: p for p in d["players"]}
        for i, t in enumerate(d["teams"]):
            label = t["tag"] or f"team{i + 1}"
            for want, key in ((team1, "team1"), (team2, "team2")):
                if want and t["tag"] and _same_team(want, t["tag"]):
                    label = key
            team = out.setdefault(label, {})
            for slot in t["slots"]:
                p = by_slot.get(slot)
                if not p or not p["names"]:
                    continue
                entry = team.setdefault(p["names"][-1], {"steamid": None, "aliases": []})
                entry["steamid"] = entry["steamid"] or p.get("steamid")
                for n in p["names"][:-1]:
                    if n not in entry["aliases"]:
                        entry["aliases"].append(n)
    return out


_CURATED = re.compile(r"^\[([^\]]*)\]_\[([^\]]*)\]_\[([^\]]*)\]_\[([^\]]*)\]_\[([^\]]*)\]\.(zip|rar|7z|ace)$", re.I)


def _placeholder(x: str | None) -> bool:
    return not x or x.casefold() in ("unknown", "unknown-year")


def _curated_name(path: str):
    m = _CURATED.match(PurePosixPath(path).name)
    return m.groups()[:5] if m else None


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-z]", "", s.casefold())


def _initials(s: str) -> str:
    words = re.findall(r"[A-Z][a-z]+|[a-z]+|[A-Z]+(?![a-z])|\d+", s)
    return "".join(w[0] for w in words).casefold() if len(words) >= 2 else ""


def _same_team(a: str, b: str) -> bool:
    """Loose match between a clan tag and a team name from a filename:
    containment, a shared 4-letter start, or initials (EG ~ EvilGeniuses)."""
    x, y = _norm(a), _norm(b)
    if not (x and y):
        return False
    if x in y or y in x or (len(x) >= 4 and len(y) >= 4 and x[:4] == y[:4]):
        return True
    return (len(x) >= 2 and x == _initials(b)) or (len(y) >= 2 and y == _initials(a))


_VS = re.compile(
    r"(?i)^(.+?)(?:[ _.\-]+(?:vs\.?|versus|v)[ _.\-]+|[ _]*-vs-[ _]*)(.+?)(?:[ _.\-]+(?:de|cs|aim|fy)_[a-z0-9_]+.*|[ _.\-]+(?:dust2|nuke|train|inferno|cbble|aztec|mill|prodigy|cpl_\w+).*)?$"
)


def _filename_teams(path: str, maps=()):
    """Team names from an archive name such as ``a_vs_b_dust2.zip``,
    ``a___v___b-0704071543-de_dust2.dem.bz2`` or HLTV's ``A.B.123456.tar.bz2``."""
    stem = PurePosixPath(path).name
    stem = re.sub(r"(\.(zip|rar|7z|ace|dem|gz|bz2|tar))+$", "", stem, flags=re.I)
    stem = re.sub(r"-\d{10}-.*$", "", stem)  # HLTV auto-name stamp and map
    stem = stem.replace("___v___", " vs ")
    for m in maps:  # cut at the map name: a_vs_b_tuscan_cup
        short = re.sub(r"^(de|cs|aim|fy|awp)_", "", m)
        hit = re.search(r"[ _.\-@]+(?:(?:de|cs|aim|fy|awp)_)?" + re.escape(short) + r"(?![a-z0-9])", stem, flags=re.I)
        if hit and hit.start() > 0:
            stem = stem[: hit.start()]
    m = _VS.match(stem)
    if m:
        a, b = (re.sub(r"[_.]+", " ", x).strip(" -") for x in m.groups())
        return (a, b) if a and b else None
    m = re.match(r"^([^.\s]+)\.([^.\s]+)\.\d{4,}$", stem)  # HLTV.org TeamA.TeamB.id
    if m:
        return m.group(1), m.group(2)
    return None
