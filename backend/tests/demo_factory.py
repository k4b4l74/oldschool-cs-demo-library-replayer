"""Synthetic GoldSrc demos for tests (no real demo files needed)."""

import struct

from oldschool.parser import goldsrc as gd

PROTO = 46


def _frame_netmsg(t, n, msg, playernum=0):
    prefix = bytearray(gd.NETMSG_PREFIX)
    struct.pack_into("<i", prefix, gd.REFPARAMS_PLAYERNUM, playernum)
    return struct.pack("<Bfi", 1, t, n) + bytes(prefix) + struct.pack("<i", len(msg)) + msg


def _usermsg_table(names):
    out = b""
    for i, (name, size) in enumerate(names):
        field = name.encode() + b"\x00"
        field += b"\x7f" * (16 - len(field))  # engine does not zero-pad
        out += bytes([39, 64 + i, size]) + field
    return out


USERMSGS = [("SayText", 255), ("DeathMsg", 255), ("TeamInfo", 255), ("TeamScore", 255), ("ServerName", 255)]
IDS = {name: 64 + i for i, (name, _s) in enumerate(USERMSGS)}


def _var(name, payload):
    return bytes([IDS[name], len(payload)]) + payload


def _userinfo(slot, userid, info):
    return b"\x0d" + bytes([slot]) + struct.pack("<i", userid) + info + b"\x00" + b"\x11" * 16


def build_demo(recorder_slot=0, hltv=True, steam=False):
    serverinfo = (
        b"\x0b"
        + struct.pack("<iiI", PROTO, 1, 0x1234)
        + b"\xaa" * 16
        + bytes([11, recorder_slot, 1])
        + b"cstrike\x00Test LAN #1\x00maps/de_dust2.bsp\x00\x00"
    )
    players = [(0, b"\\*hltv\\1\\name\\HLTV Proxy\\model\\urban")] if hltv else []
    names = ["aAa|KabaL", "aAa|Fatal", "aAa|Ozie", "GG.Eclair", "GG.Bisou", "GG.Moon"]
    for i, n in enumerate(names, start=1):
        sid = f"\\*sid\\{gd.STEAM64_BASE + 2 * i + 1}".encode() if steam else b""
        players.append((i, b"\\name\\" + n.encode() + sid + b"\\model\\gign"))
    loading = serverinfo + _usermsg_table(USERMSGS) + b"".join(_userinfo(s, 100 + s, info) for s, info in players)
    t1 = b"".join(_var("TeamInfo", bytes([e]) + (b"CT" if e <= 3 else b"TERRORIST") + b"\x00") for e in range(2, 8))
    t1 += _var("ServerName", b"Test LAN HLTV\x00")
    k1 = _var("DeathMsg", bytes([2, 5, 1]) + b"ak47\x00") + _var("DeathMsg", bytes([6, 3, 0]) + b"awp\x00")
    s1 = _var("TeamScore", b"CT\x00" + struct.pack("<h", 1))
    swap = b"".join(_var("TeamInfo", bytes([e]) + (b"TERRORIST" if e <= 3 else b"CT") + b"\x00") for e in range(2, 8))
    k2 = _var("DeathMsg", bytes([3, 6, 0]) + b"deagle\x00") + _var("SayText", bytes([2]) + b"\x02aAa|KabaL :  gg\n\x00")
    s2 = _var("TeamScore", b"TERRORIST\x00" + struct.pack("<h", 13))
    seg0 = _frame_netmsg(0.0, 0, loading, recorder_slot) + struct.pack("<Bfi", 5, 0.0, 1)
    seg1 = (
        struct.pack("<Bfi", 2, 0.0, 0)
        + _frame_netmsg(0.5, 1, t1, recorder_slot)
        + struct.pack("<Bfi", 3, 0.6, 2)
        + b"+attack".ljust(64, b"\x00")
        + _frame_netmsg(10.0, 3, k1 + s1, recorder_slot)
        + _frame_netmsg(900.0, 4, swap, recorder_slot)
        + _frame_netmsg(950.0, 5, k2 + s2, recorder_slot)
        + struct.pack("<Bfi", 5, 951.0, 6)
    )
    header = bytearray(gd.HEADER_SIZE)
    header[:8] = gd.MAGIC
    struct.pack_into("<ii", header, 8, 5, PROTO)
    header[16 : 16 + 9] = b"de_dust2\x00"
    header[276 : 276 + 8] = b"cstrike\x00"
    off0 = gd.HEADER_SIZE
    off1 = off0 + len(seg0)
    diroff = off1 + len(seg1)
    struct.pack_into("<Ii", header, 536, 0x1234, diroff)
    directory = struct.pack("<i", 2)
    for i, (label, off, seg) in enumerate(((b"LOADING", off0, seg0), (b"Playback", off1, seg1))):
        directory += (
            struct.pack("<i", i) + label.ljust(64, b"\x00") + struct.pack("<iifiii", 0, 0, 0.0, 0, off, len(seg))
        )
    return bytes(header) + seg0 + seg1 + directory


# ------------------------------------------------- round-oriented demos

ROUND_USERMSGS = [("DeathMsg", 255), ("TeamInfo", 255), ("TeamScore", 255), ("TextMsg", 255), ("RoundTime", 2)]
ROUND_ID = {name: 64 + i for i, (name, _s) in enumerate(ROUND_USERMSGS)}


def round_var(name, payload):
    return bytes([ROUND_ID[name], len(payload)]) + payload


def text(title):
    return round_var("TextMsg", b"\x04" + title + b"\x00")


def roundtime(v):
    return bytes([ROUND_ID["RoundTime"]]) + struct.pack("<h", v)


def score(side, v):
    return round_var("TeamScore", side + b"\x00" + struct.pack("<h", v))


def build_round_demo(frames):
    """frames: [(time, message bytes)] in the playback segment."""
    serverinfo = (
        b"\x0b"
        + struct.pack("<iiI", PROTO, 1, 0x1234)
        + b"\xaa" * 16
        + bytes([11, 0, 1])
        + b"cstrike\x00Test\x00maps/de_dust2.bsp\x00\x00"
    )
    players = [(0, b"\\*hltv\\1\\name\\HLTV"), (1, b"\\name\\aAa|KabaL"), (2, b"\\name\\GG.Eclair")]
    loading = serverinfo + _usermsg_table(ROUND_USERMSGS) + b"".join(_userinfo(s, 100 + s, i) for s, i in players)
    teams = round_var("TeamInfo", b"\x02CT\x00") + round_var("TeamInfo", b"\x03TERRORIST\x00")
    seg0 = _frame_netmsg(0.0, 0, loading) + struct.pack("<Bfi", 5, 0.0, 1)
    seg1 = struct.pack("<Bfi", 2, 0.0, 0) + _frame_netmsg(0.1, 1, teams)
    for n, (t, msg) in enumerate(frames, start=2):
        seg1 += _frame_netmsg(t, n, msg)
    seg1 += struct.pack("<Bfi", 5, frames[-1][0] + 1, len(frames) + 2)
    header = bytearray(gd.HEADER_SIZE)
    header[:8] = gd.MAGIC
    struct.pack_into("<ii", header, 8, 5, PROTO)
    header[16:25] = b"de_dust2\x00"
    header[276:284] = b"cstrike\x00"
    off1 = gd.HEADER_SIZE + len(seg0)
    struct.pack_into("<Ii", header, 536, 0x1234, off1 + len(seg1))
    directory = struct.pack("<i", 2)
    for i, (label, off, seg) in enumerate(((b"LOADING", gd.HEADER_SIZE, seg0), (b"Playback", off1, seg1))):
        directory += (
            struct.pack("<i", i) + label.ljust(64, b"\x00") + struct.pack("<iifiii", 0, 0, 0.0, 0, off, len(seg))
        )
    return bytes(header) + seg0 + seg1 + directory


def kill(killer, victim, weapon, hs=0):
    return round_var("DeathMsg", bytes([killer, victim, hs]) + weapon + b"\x00")


MATCH = [
    (2.0, roundtime(180)),
    (20.0, kill(2, 3, b"ak47", 1)),
    (30.0, text(b"#CTs_Win") + score(b"CT", 1)),
    (41.0, roundtime(180)),
    (50.0, kill(3, 2, b"awp")),
    (60.0, text(b"#Target_Bombed") + score(b"TERRORIST", 1)),
    (65.0, roundtime(777)),  # look-alike value: ignored
    (71.0, roundtime(180)),
    (80.0, text(b"#Game_will_restart_in")),
    (86.0, roundtime(180)),
    (90.0, kill(2, 3, b"deagle")),
    (100.0, text(b"#Terrorists_Win") + score(b"TERRORIST", 1) + score(b"CT", 0)),
]
