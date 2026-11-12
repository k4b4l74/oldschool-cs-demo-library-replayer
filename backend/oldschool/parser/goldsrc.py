"""Read GoldSrc (Half-Life 1 / Counter-Strike 1.x) ``.dem`` recordings.

Origin: copied on 2026-11-11 from the research wiki's ``wiki/tools/goldsrc_demo.py``
(same behaviour; it will be split into smaller modules in a later step).

The parser walks the demo container exactly (header, directory, frames) and then
pattern-matches a small set of self-describing server messages inside the
network packets. It does not implement the entity delta decoder, so it never
reconstructs positions; it only recovers messages that carry their own length or
a string terminator:

* ``svc_serverinfo``        hostname, max clients, recording slot
* ``svc_updateuserinfo``    player names, ``*sid`` (SteamID64), ``*hltv`` flag
* ``svc_newusermsg``        the mod's user-message table (version fingerprint)
* ``DeathMsg``              kill feed (killer, victim, headshot, weapon)
* ``TeamInfo``              which side each slot is on, over time
* ``TeamScore``             round score per side
* ``SayText``               chat lines
* ``ServerName``            HLTV server name

Everything here is stdlib only and works on bytes, so it can be fed straight
from an archive stream. Times are demo clock seconds, not wall-clock dates: a
demo file has no calendar date inside it.
"""

from __future__ import annotations

import bisect
import math
import re
import struct
from collections import Counter, defaultdict

MAGIC = b"HLDEMO\x00\x00"
HEADER_SIZE = 544
DIR_ENTRY_SIZE = 92
# Per-netmsg prefix: timestamp + ref_params + usercmd + movevars + view +
# viewmodel (436 bytes) followed by seven int32 sequence counters. Network
# protocol 43 (CS 1.0/1.1 era) recordings use a 560-byte block; the size is
# detected per file by walking the first frames with each candidate.
NETMSG_PREFIX = 464
NETMSG_PREFIX_CANDIDATES = (464, 560)
REFPARAMS_PLAYERNUM = 4 + 180  # offset of ref_params.playernum in the prefix
REFPARAMS_SPECTATOR = 4 + 76
MAX_NETMSG = 1 << 20

STEAM64_BASE = 76561197960265728

SIDES = ("CT", "TERRORIST")
SIDE_SHORT = {"CT": "ct", "TERRORIST": "t"}


class DemoError(ValueError):
    pass


# ---------------------------------------------------------------- container


def parse_header(data: bytes) -> dict:
    if data[:8] == b"HL2DEMO\x00" and len(data) >= 1072:
        # Source engine (CS:Source / CS:GO): header has server, client, map, game dir.
        game, mapname = _cstr(data[796:1056]), _cstr(data[536:796])
        raise DemoError(f"Source-engine demo (HL2DEMO), game '{game}', map '{mapname}': not CS 1.x")
    if len(data) < HEADER_SIZE or data[:8] != MAGIC:
        raise DemoError("not a GoldSrc demo (missing HLDEMO magic)")
    demo_protocol, network_protocol = struct.unpack_from("<ii", data, 8)
    map_crc, directory_offset = struct.unpack_from("<Ii", data, 536)
    return {
        "demo_protocol": demo_protocol,
        "network_protocol": network_protocol,
        "map": _cstr(data[16:276]),
        "game_dir": _cstr(data[276:536]),
        "map_crc": map_crc,
        "directory_offset": directory_offset,
    }


def read_directory(data: bytes, offset: int) -> list[dict] | None:
    """Return directory entries, or None when the directory is missing/corrupt
    (typical for recordings that were interrupted)."""
    if not HEADER_SIZE <= offset <= len(data) - 4:
        return None
    count = struct.unpack_from("<i", data, offset)[0]
    if not 1 <= count <= 1024 or offset + 4 + count * DIR_ENTRY_SIZE > len(data):
        return None
    entries = []
    for i in range(count):
        p = offset + 4 + i * DIR_ENTRY_SIZE
        kind = struct.unpack_from("<i", data, p)[0]
        flags, cd_track, track_time, frames, off, length = struct.unpack_from("<iifiii", data, p + 68)
        if off < HEADER_SIZE or length < 0 or off + length > len(data):
            return None
        entries.append(
            {
                "type": kind,
                "description": _cstr(data[p + 4 : p + 68]),
                "flags": flags,
                "track_time": track_time if math.isfinite(track_time) else None,
                "frames": frames,
                "offset": off,
                "length": length,
            }
        )
    return entries


def iter_frames(data: bytes, start: int, end: int, prefix: int = NETMSG_PREFIX):
    """Yield ``(type, time, frame_no, offset, netmsg_or_None)`` until a
    NextSection frame. Raises DemoError at the first undecodable frame."""
    pos = start
    unpack = struct.unpack_from
    while pos + 9 <= end:
        ftype, ftime, fno = unpack("<Bfi", data, pos)
        here = pos
        pos += 9
        msg = None
        if ftype in (0, 1):
            if pos + prefix + 4 > end:
                raise DemoError(f"truncated netmsg frame at {here}")
            length = unpack("<i", data, pos + prefix)[0]
            if not 0 <= length <= MAX_NETMSG or pos + prefix + 4 + length > end:
                raise DemoError(f"bad netmsg length {length} at {here}")
            body = pos + prefix + 4
            msg = data[body : body + length]
            yield ftype, ftime, fno, here, msg
            pos = body + length
            continue
        if ftype == 2:
            pass
        elif ftype == 3:
            pos += 64
        elif ftype == 4:
            pos += 32
        elif ftype == 5:
            yield ftype, ftime, fno, here, None
            return
        elif ftype == 6:
            pos += 84
        elif ftype == 7:
            pos += 8
        elif ftype == 8:
            if pos + 8 > end:
                raise DemoError(f"truncated sound frame at {here}")
            length = unpack("<i", data, pos + 4)[0]
            if not 0 <= length <= 4096:
                raise DemoError(f"bad sound frame at {here}")
            pos += 8 + length + 16
        elif ftype == 9:
            if pos + 4 > end:
                raise DemoError(f"truncated buffer frame at {here}")
            length = unpack("<i", data, pos)[0]
            if not 0 <= length <= MAX_NETMSG:
                raise DemoError(f"bad buffer frame at {here}")
            pos += 4 + length
        else:
            raise DemoError(f"unknown frame type {ftype} at {here}")
        if pos > end:
            raise DemoError(f"frame overruns segment at {here}")
        yield ftype, ftime, fno, here, msg


def detect_prefix(data: bytes, spans) -> int:
    """Pick the netmsg prefix size that decodes the most leading frames."""
    best, best_n = NETMSG_PREFIX, -1
    for cand in NETMSG_PREFIX_CANDIDATES:
        n = 0
        for start, end, _label in spans:
            try:
                for i, (ftype, *_rest) in enumerate(iter_frames(data, start, end, cand)):
                    n += 1
                    if i >= 400 or ftype == 5:
                        break
            except DemoError:
                pass
        if n > best_n:
            best, best_n = cand, n
    return best


def resync(data: bytes, pos: int, end: int, prefix: int, last_time: float | None, window: int = 4 << 20) -> int | None:
    """After a corrupt stretch, find the next offset where three consecutive
    frames decode with a plausible clock. Returns None if nothing is found."""
    stop = min(end, pos + window)
    unpack = struct.unpack_from
    p = pos
    while True:
        p = data.find(b"\x01", p + 1, stop)
        if p == -1:
            return None
        if p + 9 + prefix + 4 > end:
            return None
        t = unpack("<f", data, p + 1)[0]
        if not math.isfinite(t) or t < 0 or (last_time is not None and not last_time - 1 <= t <= last_time + 3600):
            continue
        try:
            n = 0
            for _ in iter_frames(data, p, min(end, p + (1 << 18)), prefix):
                n += 1
                if n >= 3:
                    return p
        except DemoError:
            continue


def collect_segments(data: bytes, header: dict) -> tuple[list[dict], list[str]]:
    """Walk every segment. Uses the directory when valid, otherwise walks the
    frames sequentially from the end of the header (interrupted recordings)."""
    problems: list[str] = []
    directory = read_directory(data, header["directory_offset"])
    if directory:
        spans = [(e["offset"], e["offset"] + e["length"], e["description"]) for e in directory]
    else:
        problems.append("directory missing or invalid; frames walked sequentially")
        spans = [(HEADER_SIZE, len(data), None)]
    prefix = detect_prefix(data, spans)
    header["netmsg_prefix"] = prefix
    segments = []
    for start, end, label in spans:
        pos = start
        while pos < end:
            seg = {
                "label": label,
                "offset": pos,
                "msgs": [],
                "times": [],
                "frames": 0,
                "first_time": None,
                "last_time": None,
                "complete": False,
                "playernum": None,
            }
            try:
                for ftype, ftime, _fno, off, msg in iter_frames(data, pos, end, prefix):
                    seg["frames"] += 1
                    if math.isfinite(ftime):
                        if seg["first_time"] is None:
                            seg["first_time"] = ftime
                        seg["last_time"] = ftime
                    if msg is not None:
                        seg["msgs"].append(msg)
                        seg["times"].append(ftime)
                        if seg["playernum"] is None and prefix == NETMSG_PREFIX:
                            seg["playernum"] = struct.unpack_from("<i", data, off + 9 + REFPARAMS_PLAYERNUM)[0]
                    if ftype == 5:
                        seg["complete"] = True
                        pos = off + 9
                        break
                else:
                    pos = end
            except DemoError as exc:
                problems.append(str(exc))
                seg["broken"] = True
                pos = end
            segments.append(seg)
            # Skip over corrupt bytes (damaged archives) and keep reading.
            # Give up when resyncs keep failing quickly: the rest is noise.
            short_runs = 0
            while seg.get("broken") and short_runs < 3:
                at = int(problems[-1].rsplit(" at ", 1)[-1]) if " at " in problems[-1] else None
                nxt = resync(data, at, end, prefix, seg["last_time"]) if at is not None else None
                if nxt is None:
                    break
                problems.append(f"resynchronised at {nxt} after skipping {nxt - at} bytes")
                seg["broken"] = False
                before = seg["frames"]
                try:
                    for ftype, ftime, _fno, off, msg in iter_frames(data, nxt, end, prefix):
                        seg["frames"] += 1
                        if math.isfinite(ftime):
                            seg["last_time"] = ftime
                        if msg is not None:
                            seg["msgs"].append(msg)
                            seg["times"].append(ftime)
                        if ftype == 5:
                            seg["complete"] = True
                            pos = off + 9
                            break
                except DemoError as exc:
                    problems.append(str(exc))
                    seg["broken"] = True
                    short_runs = short_runs + 1 if seg["frames"] - before < 200 else 0
            if seg.get("broken") and short_runs >= 3:
                problems.append("stream stays corrupt after repeated resynchronisation; rest of file ignored")
            if directory:
                break  # one directory entry = one segment
            if not seg["complete"]:
                break
            if seg["label"] is None:
                seg["label"] = "LOADING" if len(segments) == 1 else "Playback"
    return segments, problems


# ------------------------------------------------------------ message scans

_RE_NEWUSERMSG = re.compile(rb"\x27([\x40-\xff])([\x00-\xff])([A-Za-z][A-Za-z0-9_]{1,14})\x00", re.S)
_RE_USERINFO = re.compile(rb"\x0d([\x00-\x3f])([\x00-\xff]{4})(\\[^\x00]{3,1500})\x00", re.S)
_RE_USERINFO_OLD = re.compile(rb"\x0d([\x00-\x3f])(\\[^\x00]{3,1500})\x00", re.S)
_RE_SERVERINFO_TAIL = re.compile(rb"([^\x00]{0,255})\x00maps/([^\x00]{1,64})\.bsp\x00", re.S)


def _scan_usermsgs(blob: bytes) -> dict:
    """The table is sent as back-to-back 19-byte svc_newusermsg records; the
    16-byte name field is not zero padded, so isolated look-alikes inside
    compressed entity data are rejected by requiring a neighbour record."""
    hits = [(m.start(), m) for m in _RE_NEWUSERMSG.finditer(blob)]
    starts = {pos for pos, _ in hits}
    table: dict[str, dict] = {}
    for pos, m in hits:
        if pos - 19 in starts or pos + 19 in starts:
            name = m.group(3).decode("ascii")
            table.setdefault(name, {"id": m.group(1)[0], "size": m.group(2)[0]})
    return table


def _parse_userinfo(raw: bytes) -> dict | None:
    parts = raw.split(b"\\")
    if len(parts) < 3 or parts[0] != b"" or len(parts) % 2 == 0:
        return None
    info = {}
    for k, v in zip(parts[1::2], parts[2::2], strict=True):
        if not k or len(k) > 64:
            return None
        info[_text(k)] = _text(v)
    return info if "name" in info else None


def _variable_messages(blob: bytes, msg_id: int, min_len: int = 1):
    """Yield (pos, payload) for every plausible variable-length user message."""
    marker = bytes([msg_id])
    find = blob.find
    pos = find(marker)
    n = len(blob)
    while pos != -1:
        if pos + 2 <= n:
            length = blob[pos + 1]
            if length >= min_len and pos + 2 + length <= n:
                yield pos, blob[pos + 2 : pos + 2 + length]
        pos = find(marker, pos + 1)


_WEAPON_RE = re.compile(rb"[a-z][a-z0-9_]{1,31}")
_PRINTABLE = re.compile(rb"[\x01-\x08\x0a-\x1f\x7f]")


def _death_messages(blob: bytes, msg_id: int):
    seen_end = -1
    for pos, p in _variable_messages(blob, msg_id, 4):
        if pos < seen_end or p[-1] != 0:
            continue
        killer, victim = p[0], p[1]
        if killer > 32 or not 1 <= victim <= 32:
            continue
        rest = p[2:-1]
        headshot = None
        if rest[:1] in (b"\x00", b"\x01"):
            headshot = rest[0] == 1
            rest = rest[1:]
        if not _WEAPON_RE.fullmatch(rest):
            continue
        seen_end = pos + 2 + len(p)
        yield pos, {"killer": killer, "victim": victim, "headshot": headshot, "weapon": rest.decode("ascii")}


# CS 1.3 and earlier send "Ct"/"Terrorist"; later versions upper-case.
_TEAM_NAMES = {
    b"ct": "CT",
    b"terrorist": "TERRORIST",
    b"unassigned": "UNASSIGNED",
    b"spectator": "SPECTATOR",
    b"": "UNASSIGNED",
}


def _team_infos(blob: bytes, msg_id: int):
    for pos, p in _variable_messages(blob, msg_id, 2):
        if p[-1] != 0 or not 1 <= p[0] <= 32 or len(p) > 12:
            continue
        team = _TEAM_NAMES.get(p[1:-1].lower())
        if team:
            yield pos, p[0], team


def _team_scores(blob: bytes, msg_id: int):
    for pos, p in _variable_messages(blob, msg_id, 4):
        cut = p.find(b"\x00")
        team = _TEAM_NAMES.get(p[:cut].lower()) if cut > 0 else None
        if team in SIDES and len(p) in (cut + 3, cut + 5):
            yield pos, team, struct.unpack_from("<h", p, cut + 1)[0]


def _say_texts(blob: bytes, msg_id: int):
    for pos, p in _variable_messages(blob, msg_id, 3):
        if p[-1] != 0 or p[0] > 32:
            continue
        strings = p[1:-1].split(b"\x00")
        if (
            not strings[0]
            or len(strings) > 4
            or any(
                _PRINTABLE.search(
                    s.replace(b"\x02", b"").replace(b"\x01", b"").replace(b"\x03", b"").replace(b"\n", b"")
                )
                for s in strings
            )
        ):
            continue
        yield pos, p[0], [_text(s).strip("\x01\x02\x03\n ") for s in strings]


def _server_names(blob: bytes, msg_id: int):
    for pos, p in _variable_messages(blob, msg_id, 2):
        text = p[:-1]
        if (
            p[-1] == 0
            and len(text) >= 2
            and b"\x00" not in text
            and not _PRINTABLE.search(text)
            and sum(32 <= c < 127 for c in text) >= 0.8 * len(text)
        ):
            yield pos, _text(text)


def _server_info(blob: bytes, game_dir: str, network_protocol: int) -> dict | None:
    marker = game_dir.encode("latin-1", "replace") + b"\x00"
    pos = blob.find(marker)
    while pos != -1:
        m = _RE_SERVERINFO_TAIL.match(blob, pos + len(marker))
        if m and pos >= 3:
            maxclients, playernum, _dm = blob[pos - 3], blob[pos - 2], blob[pos - 1]
            layout = None
            for back, hashed in ((3 + 16 + 12, True), (3 + 12, False)):
                start = pos - back
                if (
                    start >= 1
                    and blob[start - 1] == 11
                    and struct.unpack_from("<i", blob, start)[0] == network_protocol
                ):
                    layout = hashed
                    break
            hostname = _text(m.group(1))
            if hostname.startswith("maps/") and hostname.endswith(".bsp"):
                hostname = None  # old protocols send no hostname here
            if 1 <= maxclients <= 32 and playernum < 32:
                return {
                    "hostname": hostname,
                    "map_path": "maps/" + _text(m.group(2)) + ".bsp",
                    "maxclients": maxclients,
                    "playernum": playernum,
                    "layout_confirmed": layout is not None,
                }
        pos = blob.find(marker, pos + 1)
    return None


# ----------------------------------------------------------------- analysis


class _Timeline:
    def __init__(self, segments):
        self.starts, self.times, parts, n = [], [], [], 0
        for seg in segments:
            for msg, t in zip(seg["msgs"], seg["times"], strict=False):
                self.starts.append(n)
                self.times.append(t)
                parts.append(msg)
                n += len(msg)
        self.blob = b"".join(parts)

    def time(self, pos: int) -> float:
        i = bisect.bisect_right(self.starts, pos) - 1
        return round(self.times[i], 2) if i >= 0 else 0.0


def analyse(data: bytes, *, keep_kills: bool = True, keep_chat: int = 40) -> dict:
    header = parse_header(data)
    segments, problems = collect_segments(data, header)
    playback = [s for s in segments if s["label"] != "LOADING"] or segments
    clock = [t for s in playback for t in s["times"] if math.isfinite(t) and t >= 0]
    first = min(clock, default=None)
    last = max(clock, default=None)
    tl = _Timeline(segments)
    blob = tl.blob

    usermsgs = _scan_usermsgs(blob)
    server = _server_info(blob, header["game_dir"], header["network_protocol"]) or {}
    if not server:
        problems.append("svc_serverinfo not found")

    # Players, keyed by slot; names may change and slots may be reused.
    players: dict[int, dict] = {}
    for rx, has_userid in ((_RE_USERINFO, True), (_RE_USERINFO_OLD, False)):
        found = False
        for m in rx.finditer(blob):
            info = _parse_userinfo(m.group(3) if has_userid else m.group(2))
            if not info:
                continue
            found = True
            slot = m.group(1)[0]
            p = players.setdefault(
                slot,
                {
                    "slot": slot,
                    "names": [],
                    "userids": [],
                    "steamid64": None,
                    "hltv": False,
                    "bot": False,
                    "models": [],
                },
            )
            name = info.get("name", "")
            if name and name not in p["names"]:
                p["names"].append(name)
            if has_userid:
                uid = struct.unpack("<i", m.group(2))[0]
                if uid not in p["userids"]:
                    p["userids"].append(uid)
            sid = info.get("*sid")
            if sid and sid.isdigit() and int(sid) > STEAM64_BASE:
                p["steamid64"] = sid
            if info.get("*hltv"):
                p["hltv"] = True
            if info.get("*bot"):
                p["bot"] = True
            model = info.get("model")
            if model and model not in p["models"]:
                p["models"].append(model)
        if found:
            break

    def name_of(entity: int) -> str | None:
        p = players.get(entity - 1)
        return p["names"][-1] if p and p["names"] else None

    # Side timeline per entity index (1-based).
    side_events: dict[int, list[tuple[float, str]]] = defaultdict(list)
    if "TeamInfo" in usermsgs:
        for pos, ent, team in _team_infos(blob, usermsgs["TeamInfo"]["id"]):
            ev = side_events[ent]
            t = tl.time(pos)
            if not ev or ev[-1][1] != team:
                ev.append((t, team))

    def side_at(ent: int, t: float) -> str | None:
        ev = side_events.get(ent)
        if not ev:
            return None
        i = bisect.bisect_right([e[0] for e in ev], t) - 1
        return ev[max(i, 0)][1]

    kills = []
    if "DeathMsg" in usermsgs:
        for pos, k in _death_messages(blob, usermsgs["DeathMsg"]["id"]):
            t = tl.time(pos)
            k["time"] = t
            k["killer_name"] = name_of(k["killer"]) if k["killer"] else None
            k["victim_name"] = name_of(k["victim"])
            k["killer_side"] = side_at(k["killer"], t) if k["killer"] else None
            k["victim_side"] = side_at(k["victim"], t)
            kills.append(k)

    scores = []
    if "TeamScore" in usermsgs:
        for pos, team, score in _team_scores(blob, usermsgs["TeamScore"]["id"]):
            t = tl.time(pos)
            if not scores or scores[-1][1:] != (team, score):
                scores.append((t, team, score))

    chat = []
    if "SayText" in usermsgs:
        for pos, sender, strings in _say_texts(blob, usermsgs["SayText"]["id"]):
            chat.append({"time": tl.time(pos), "sender": sender, "text": " ".join(s for s in strings if s)})

    server_names = []
    if "ServerName" in usermsgs:
        connect = (first or 0.0) + 5.0
        for pos, name in _server_names(blob, usermsgs["ServerName"]["id"]):
            if tl.time(pos) > connect or sum(ch.isalnum() for ch in name) < 3:
                continue
            if name not in server_names:
                server_names.append(name)

    def played_sides(ent: int) -> list[str]:
        """Sides held while the action happened; a short warm-up or knife
        round on the other side does not count once the demo has 10+ kills."""
        order = [s for s in dict.fromkeys(e[1] for e in side_events.get(ent, [])) if s in SIDES]
        if len(kills) < 10 or len(order) < 2:
            return order
        share = Counter(side_at(ent, k["time"]) for k in kills)
        need = max(3, 0.15 * len(kills))
        return [s for s in order if share[s] >= need] or order

    # Per-player stats and sides.
    for slot, p in players.items():
        ent = slot + 1
        p["sides"] = played_sides(ent)
        p["kills"] = sum(
            1 for k in kills if k["killer"] == ent and k["victim"] != ent and k["killer_side"] != k["victim_side"]
        )
        p["deaths"] = sum(1 for k in kills if k["victim"] == ent)
        p["headshots"] = sum(1 for k in kills if k["killer"] == ent and k["headshot"] and k["victim"] != ent)
        p["teamkills"] = sum(
            1
            for k in kills
            if k["killer"] == ent and k["victim"] != ent and k["killer_side"] and k["killer_side"] == k["victim_side"]
        )
        if p["steamid64"]:
            v = int(p["steamid64"]) - STEAM64_BASE
            p["steamid"] = f"STEAM_0:{v % 2}:{v // 2}"
        else:
            p["steamid"] = None

    # Recorder.
    rec_slot = server.get("playernum")
    if rec_slot is None:
        rec_slot = next((s["playernum"] for s in playback if s["playernum"] is not None), None)
    recorder = {"slot": rec_slot, "name": None, "kind": "unknown", "sides": []}
    rp = players.get(rec_slot) if rec_slot is not None else None
    if rp:
        recorder["name"] = rp["names"][-1] if rp["names"] else None
        recorder["names"] = rp["names"]
        recorder["kind"] = "hltv" if rp["hltv"] else "player"
        recorder["sides"] = rp["sides"]
    elif any(p["hltv"] for p in players.values()):
        recorder["kind"] = "hltv"

    teams = _cluster_teams(players, side_events, kills, last or 0.0)

    final_score = {}
    for _t, team, score in scores:
        final_score[team] = score

    result = {
        "header": header,
        "segments": [
            {"label": s["label"], "frames": s["frames"], "netmsgs": len(s["msgs"]), "complete": s["complete"]}
            for s in segments
        ],
        "duration_seconds": round(last - first, 1) if first is not None and last is not None else None,
        "problems": problems,
        "server": server,
        "server_names": server_names,
        "recorder": recorder,
        "usermsgs": usermsgs,
        "players": sorted(players.values(), key=lambda p: p["slot"]),
        "teams": teams,
        "kill_count": len(kills),
        "score_history": [{"time": t, "side": s, "score": v} for t, s, v in scores],
        "final_score": final_score,
        "chat": chat[:keep_chat],
        "fingerprint": fingerprint(blob, usermsgs),
    }
    if keep_kills:
        result["kills"] = kills
    return result


# ------------------------------------------------------------------- rounds

# TextMsg titles that end a round, and the side they credit (None = draw).
ROUND_END = {
    b"#Terrorists_Win": "TERRORIST",
    b"#CTs_Win": "CT",
    b"#Round_Draw": None,
    b"#Target_Bombed": "TERRORIST",
    b"#Bomb_Defused": "CT",
    b"#Target_Saved": "CT",
    b"#All_Hostages_Rescued": "CT",
    b"#Hostages_Not_Rescued": "TERRORIST",
    b"#VIP_Escaped": "CT",
    b"#VIP_Assassinated": "TERRORIST",
    b"#VIP_Not_Escaped": "TERRORIST",
    b"#CTs_PreventEscape": "CT",
    b"#Terrorists_Escaped": "TERRORIST",
    b"#Terrorists_Not_Escaped": "CT",
    b"#Escaping_Terrorists_Neutralized": "CT",
}
# Some recordings (e.g. CS 1.3 HLTV) carry no win TextMsg, only the radio
# sound the game plays at the round end (SendAudio).
ROUND_END_AUDIO = {b"%!MRAD_terwin": "TERRORIST", b"%!MRAD_ctwin": "CT", b"%!MRAD_rounddraw": None}
AUDIO_REASON = {b"%!MRAD_terwin": "Terrorists_Win", b"%!MRAD_ctwin": "CTs_Win", b"%!MRAD_rounddraw": "Round_Draw"}
RESTART = (b"#Game_will_restart_in", b"#Game_Commencing")
_RE_ROUND_TEXT = re.compile(
    rb"(?:" + b"|".join(re.escape(k) for k in (*ROUND_END, *ROUND_END_AUDIO, *RESTART)) + rb")\x00"
)
ROUND_START_WINDOW = (2.0, 20.0)  # RoundTime follows a round end by ~5-11 s


def _round_times(blob: bytes, msg_id: int):
    """RoundTime is a fixed 2-byte message (id + short seconds) with no length
    byte, so look-alikes are common. Callers only trust a hit that falls in
    the short window after a round end or restart."""
    for m in re.finditer(re.escape(bytes([msg_id])) + rb"(..)", blob, re.S):
        v = struct.unpack("<h", m.group(1))[0]
        if 1 <= v <= 900:
            yield m.start(), v


def rounds(data: bytes, analysis: dict | None = None) -> dict:
    """Split a demo into rounds with their kill feed, for seeking.

    Round ends come from the TextMsg titles in ROUND_END and restarts from
    RESTART. A round starts at the first plausible RoundTime message 2-20 s
    after the previous end (the respawn), or 5 s after it when none is
    found, or at the first playback frame. All times are demo-clock seconds,
    the same clock the engine uses during playback. Kill names are resolved
    at the time of the kill, because HLTV slots are reused and renamed."""
    a = analysis if analysis is not None and "kills" in analysis else analyse(data, keep_kills=True)
    header = a["header"]
    segments, _problems = collect_segments(data, header)
    tl = _Timeline(segments)
    blob = tl.blob
    playback = [s for s in segments if s["label"] != "LOADING"] or segments
    clock = [t for s in playback for t in s["times"] if math.isfinite(t) and t >= 0]
    first, last = min(clock, default=0.0), max(clock, default=0.0)

    names: dict[int, list[tuple[float, str]]] = defaultdict(list)
    for rx, has_userid in ((_RE_USERINFO, True), (_RE_USERINFO_OLD, False)):
        for m in rx.finditer(blob):
            info = _parse_userinfo(m.group(3) if has_userid else m.group(2))
            if info and info.get("name"):
                ev = names[m.group(1)[0] + 1]
                if not ev or ev[-1][1] != info["name"]:
                    ev.append((tl.time(m.start()), info["name"]))
        if names:
            break

    def name_at(ent: int, t: float) -> str | None:
        ev = names.get(ent)
        if not ev:
            return None
        i = bisect.bisect_right([e[0] for e in ev], t) - 1
        return ev[max(i, 0)][1]

    events = []  # (time, kind, winner, title, from_audio)
    for m in _RE_ROUND_TEXT.finditer(blob):
        title = m.group()[:-1]
        t = tl.time(m.start())
        kind = "restart" if title in RESTART else "end"
        audio = title in ROUND_END_AUDIO
        if audio:
            ev = (t, kind, ROUND_END_AUDIO[title], AUDIO_REASON[title], True)
        else:
            ev = (t, kind, ROUND_END.get(title), title.decode()[1:], False)
        if events and events[-1][1] == kind and abs(t - events[-1][0]) < 1.5:
            if events[-1][4] and not audio:  # the TextMsg names the reason; prefer it
                events[-1] = ev
            continue  # the same round end seen twice
        events.append(ev)

    # The server sends the same RoundTime value at every respawn (its freeze
    # or round time), so the value seen most often right after round ends is
    # the real one; other hits in the window are look-alikes.
    hits = (
        sorted((tl.time(p), v) for p, v in _round_times(blob, a["usermsgs"]["RoundTime"]["id"]))
        if "RoundTime" in a["usermsgs"]
        else []
    )
    hit_times = [h[0] for h in hits]

    def window(t: float):
        i = bisect.bisect_left(hit_times, t + ROUND_START_WINDOW[0])
        while i < len(hits) and hits[i][0] <= t + ROUND_START_WINDOW[1]:
            yield hits[i]
            i += 1

    anchors = [t for t, kind, *_ in events]
    votes = Counter(v for t in anchors for v in {v for _h, v in window(t)})
    usual = {v for v, n in votes.most_common(2) if n >= max(2, len(anchors) // 3)}
    gaps = sorted(
        g for g in (next((h - t for h, v in window(t) if v in usual), None) for t in anchors) if g is not None
    )
    usual_gap = gaps[len(gaps) // 2] if gaps else 5.0

    def start_after(t: float) -> tuple[float, str]:
        for h, v in window(t):
            if v in usual:
                return h, f"RoundTime {v}"
        return min(t + usual_gap, last), f"end+{usual_gap:.0f}s"

    scores = a["score_history"]

    def score_at(t: float) -> dict:
        out = {}
        for s in scores:
            if s["time"] <= t + 0.5:
                out[s["side"]] = s["score"]
        return out

    out_rounds = []
    start, basis = first, "demo start"
    for t, kind, winner, title, _audio in events:
        if kind == "restart":
            start, basis = start_after(t)
            continue
        if t <= start:  # end message before the respawn: skip
            continue
        out_rounds.append(
            {
                "start": round(start, 2),
                "start_basis": basis,
                "end": t,
                "winner": winner,
                "reason": title,
                "score_after": score_at(t + 0.5),
            }
        )
        start, basis = start_after(t)

    kills = []
    for k in a.get("kills", []):
        t = k["time"]
        kills.append(
            {
                "time": t,
                "killer": name_at(k["killer"], t) if k["killer"] else None,
                "victim": name_at(k["victim"], t),
                "weapon": k["weapon"],
                "headshot": k["headshot"],
                "killer_side": k["killer_side"],
                "victim_side": k["victim_side"],
            }
        )
    # A round's kills run from just before its respawn to a few seconds after
    # its end (post-round frags); warm-up kills between restarts stay apart.
    bounds = [r["start"] for r in out_rounds[1:]] + [math.inf]
    assigned = set()
    for r, nxt in zip(out_rounds, bounds, strict=False):  # bounds has one more item when there are no rounds
        stop = min(nxt - 1.0, r["end"] + 6.0)
        r["kills"] = [k for k in kills if r["start"] - 1.0 <= k["time"] < stop]
        assigned.update(id(k) for k in r["kills"])
    for i, r in enumerate(out_rounds, 1):
        r["number"] = i
    return {
        "first": round(first, 2),
        "last": round(last, 2),
        "rounds": out_rounds,
        "restarts": [round(t, 2) for t, kind, *_ in events if kind == "restart"],
        "other_kills": [k for k in kills if id(k) not in assigned],
    }


def fingerprint(blob: bytes, usermsgs: dict) -> dict:
    """Facts that separate Counter-Strike releases sharing a network protocol."""
    weapons = sorted({m.group(1).decode() for m in re.finditer(rb"weapon_([a-z0-9]{2,12})\x00", blob)})
    return {"usermsg_count": len(usermsgs), "weapons": weapons}


def _cluster_teams(players, side_events, kills, end_time) -> list[dict]:
    """Split real players into two line-ups that stay together across a side
    swap. Players are compared by how often they share a side at each kill."""
    real = {s + 1: p for s, p in players.items() if not p["hltv"] and p["sides"]}
    if not real:
        return []

    def side_at(ent, t):
        ev = side_events.get(ent)
        if not ev:
            return None
        i = bisect.bisect_right([e[0] for e in ev], t) - 1
        s = ev[max(i, 0)][1]
        return s if s in SIDES else None

    times = sorted({k["time"] for k in kills}) or [end_time]
    snaps = [{e: side_at(e, t) for e in real} for t in times]
    # Seed: the snapshot with the most players placed, earliest first.
    seed = max(snaps, key=lambda s: sum(1 for v in s.values() if v))
    groups = {"A": {e for e, v in seed.items() if v == "CT"}, "B": {e for e, v in seed.items() if v == "TERRORIST"}}
    for e in real:
        if e in groups["A"] or e in groups["B"]:
            continue
        votes = Counter()
        for snap in snaps:
            mine = snap.get(e)
            if not mine:
                continue
            for g, members in groups.items():
                for other in members:
                    if snap.get(other):
                        votes[g] += 1 if snap[other] == mine else -1
        if votes:
            groups[max(groups, key=lambda g: votes[g])].add(e)
    out = []
    for g in ("A", "B"):
        ents = sorted(groups[g])
        if not ents:
            continue
        names = [real[e]["names"][-1] for e in ents if real[e]["names"]]
        sides, held = [], Counter()
        for snap in snaps:
            vals = Counter(snap[e] for e in ents if snap.get(e))
            if vals:
                s = vals.most_common(1)[0][0]
                held[s] += 1
                if s not in sides:
                    sides.append(s)
        if len(snaps) >= 10:
            sides = [s for s in sides if held[s] >= max(3, 0.15 * len(snaps))] or sides
        out.append({"slots": [e - 1 for e in ents], "names": names, "tag": clan_tag(names), "sides": sides})
    return out


# ------------------------------------------------------------ name helpers

_TAG_EDGE = " -_.|:~*^=+#!/\\()[]{}<>'\"`,;@"


def clan_tag(names: list[str]) -> str | None:
    """Longest prefix or suffix shared by most of a line-up, trimmed of the
    decoration characters that usually surround clan tags."""
    names = [n for n in names if n]
    if len(names) < 2:
        return None
    need = max(2, (len(names) + 1) // 2 + (1 if len(names) >= 4 else 0))
    need = min(need, len(names))
    best = None
    for fn in (_prefix_candidates, _suffix_candidates):
        cand = Counter()
        for n in names:
            for c in fn(n):
                cand[c] += 1
        for c, cnt in cand.items():
            core = c.strip(_TAG_EDGE)
            if cnt >= need and len(core) >= 1 and (best is None or (len(core), cnt) > (len(best[0]), best[1])):
                best = (core, cnt)
    return tag_spelling(best[0], names) if best else None


def _cut(a: str, b: str) -> bool:
    """True when a tag may end between characters a and b."""
    return a in _TAG_EDGE or b in _TAG_EDGE or (a.isalpha() and b.isdigit())


def _prefix_candidates(name: str):
    low = name.casefold()
    for i in range(2, min(len(name), 24) + 1):
        if i == len(name) or _cut(name[i - 1], name[i]):
            yield low[:i]


def _suffix_candidates(name: str):
    low = name.casefold()
    for i in range(2, min(len(name), 24) + 1):
        j = len(name) - i
        if j == 0 or _cut(name[j - 1], name[j]):
            yield low[j:]


def tag_spelling(tag: str | None, names: list[str]) -> str | None:
    """Return the tag with the capitalisation used in the most names."""
    if not tag:
        return None
    spellings = Counter()
    low = tag.casefold()
    for n in names:
        i = n.casefold().find(low)
        if i != -1:
            spellings[n[i : i + len(tag)]] += 1
    return spellings.most_common(1)[0][0] if spellings else tag


_SEPARATORS = " -_.|:~*^=+#!/\\,;@'\"`"
_EMPTY_BRACKETS = re.compile(r"\[[\W_]*\]|\([\W_]*\)|\{[\W_]*\}|<[\W_]*>")


def strip_tag(name: str, tag: str | None) -> str:
    """Player alias without its clan tag and the decoration around it."""
    if not name:
        return name
    out = name
    if tag:
        sep = re.escape(_SEPARATORS)
        digits = r"\d*" if tag[-1:].isalpha() else ""  # GG51 OliGan -> OliGan
        out = re.sub(f"[{sep}]*{re.escape(tag)}{digits}[{sep}]*", " ", name, count=1, flags=re.I)
    out = _EMPTY_BRACKETS.sub(" ", out).strip(_SEPARATORS)
    for opener, closer in ("[]", "()", "{}", "<>"):
        if out.startswith(closer):
            out = out[1:]
        if out.endswith(opener):
            out = out[:-1]
    out = out.strip(_SEPARATORS)
    return out or name.strip() or name


_NICK = re.compile(r"^(.*?)\s*[<\[({]([^<>\[\](){}]{2,})[>\])}]\s*$")


def display_alias(name: str, tag: str | None) -> str:
    """Alias for a filename: tag removed and, for league-style names such as
    ``3D.Morgan<bullseye>`` (surname plus nickname), the nickname."""
    alias = strip_tag(name, tag)
    m = _NICK.match(alias)
    if m and m.group(1).strip(_SEPARATORS + "[](){}<>"):
        return m.group(2).strip()
    return alias


def _cstr(b: bytes) -> str:
    return _text(b.split(b"\x00", 1)[0])


def _text(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp1252", "replace")
