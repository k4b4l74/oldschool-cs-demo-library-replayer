"""Seek injection: the demo stays readable and the command lands in time."""

import pytest

from oldschool.parser import goldsrc as gd
from oldschool.player import seek
from tests.demo_factory import MATCH, build_demo, build_round_demo


def frames_of(data):
    header = gd.parse_header(data)
    seg = gd.read_directory(data, header["directory_offset"])[1]
    return seg, list(gd.iter_frames(data, seg["offset"], seg["offset"] + seg["length"]))


def test_inject_keeps_demo_readable():
    data = build_round_demo(MATCH)
    out = seek.inject_command(data, 41.0)
    assert len(out) == len(data) + 73
    seg, frames = frames_of(out)
    cmds = [(t, out[off + 9 : off + 73].rstrip(b"\x00")) for ft, t, _n, off, _m in frames if ft == 3]
    assert cmds == [(41.0, seek.DEFAULT_RESUME.encode())]
    times = [t for ft, t, *_ in frames if ft != 5]
    assert times == sorted(times)
    assert seg["frames"] == 1
    assert len(gd.rounds(out)["rounds"]) == 3


def test_existing_command_frames_are_kept():
    data = build_demo()  # already holds a "+attack" command frame
    out = seek.inject_command(data, 900.0)
    _seg, frames = frames_of(out)
    cmds = [out[off + 9 : off + 73].rstrip(b"\x00") for ft, _t, _n, off, _m in frames if ft == 3]
    assert cmds == [b"+attack", seek.DEFAULT_RESUME.encode()]
    assert gd.analyse(out)["kill_count"] == gd.analyse(data)["kill_count"]


def test_seek_past_end_lands_before_next_section():
    data = build_round_demo(MATCH)
    out = seek.inject_command(data, 5000.0)
    _seg, frames = frames_of(out)
    assert [f[0] for f in frames][-2:] == [3, 5]


def test_rejects_long_command_and_missing_directory():
    data = build_round_demo(MATCH)
    with pytest.raises(ValueError):
        seek.inject_command(data, 10.0, "x" * 64)
    broken = bytearray(data)
    broken[540:544] = b"\x00\x00\x00\x00"
    with pytest.raises(ValueError):
        seek.inject_command(bytes(broken), 10.0)


def test_start_args():
    assert seek.start_args() == ["+host_framerate", "0.5", "+nosound", "1"]
    with pytest.raises(ValueError):
        seek.start_args(0)


def test_stufftext_appended_to_next_network_message():
    data = build_round_demo(MATCH)
    out = seek.inject_stufftext(data, 41.0, "host_framerate 0")
    payload = b"\x09host_framerate 0\n\x00"
    assert len(out) == len(data) + len(payload)
    _seg, frames = frames_of(out)
    hit = [(t, m) for ft, t, _n, _o, m in frames if ft in (0, 1) and m.endswith(payload)]
    assert [t for t, _m in hit] == [41.0]
    assert gd.rounds(out)["rounds"] == gd.rounds(data)["rounds"]


def test_stufftext_past_end_uses_last_message():
    data = build_round_demo(MATCH)
    out = seek.inject_stufftext(data, 5000.0, "x")
    _seg, frames = frames_of(out)
    netmsgs = [m for ft, _t, _n, _o, m in frames if ft in (0, 1)]
    assert netmsgs[-1].endswith(b"\x09x\n\x00")


def test_inject_resume_uses_both_routes():
    data = build_round_demo(MATCH)
    out = seek.inject_resume(data, 41.0)
    _seg, frames = frames_of(out)
    cmds = [out[off + 9 : off + 73].rstrip(b"\x00") for ft, _t, _n, off, _m in frames if ft == 3]
    assert cmds == [seek.FRAME_RESUME.encode()]
    assert any(m.endswith(b"\x09" + seek.STUFF_RESUME.encode() + b"\n\x00") for ft, *_r, m in frames if ft in (0, 1))
    assert len(gd.rounds(out)["rounds"]) == 3


def test_inject_seek_switches_fast_then_normal():
    data = build_round_demo(MATCH)
    out = seek.inject_seek(data, 41.0)
    _seg, frames = frames_of(out)
    cmds = [(round(t, 3), out[off + 9 : off + 73].rstrip(b"\x00").decode()) for ft, t, _n, off, _m in frames if ft == 3]
    assert cmds == [(0.1, "host_framerate 0.5;nosound 1;echo seek: fast frame"), (41.0, seek.FRAME_RESUME)]
    stuffed = [round(t, 3) for ft, t, _n, _o, m in frames if ft in (0, 1) and b"\x09host_framerate" in m]
    assert stuffed == [0.1, 41.0]
    assert gd.rounds(out)["rounds"] == gd.rounds(data)["rounds"]
    assert seek.inject_seek(data, 0.0) == data


def test_retime_compresses_time_before_target_only():
    data = build_round_demo(MATCH)
    out, f = seek.retime(data, 41.0, 20)
    assert len(out) == len(data)
    _seg, before = frames_of(data)
    _seg, after = frames_of(out)
    pairs = [(round(a[1], 3), round(b[1], 3)) for a, b in zip(before, after, strict=True)]
    assert (0.1, 0.1) in pairs  # first playback frame unchanged
    assert (20.0, round(0.1 + 19.9 / 20, 3)) in pairs  # compressed 20 times
    assert (41.0, round(f(41.0), 3)) in pairs and (60.0, round(f(41.0) + 19.0, 3)) in pairs  # spacing kept after
    times = [t for _a, t in pairs]
    assert times == sorted(times)


def test_inject_seek_retime_markers_and_rounds():
    data = build_round_demo(MATCH)
    out = seek.inject_seek_retime(data, 41.0)
    _seg, frames = frames_of(out)
    cmds = [out[off + 9 : off + 73].rstrip(b"\x00").decode() for ft, _t, _n, off, _m in frames if ft == 3]
    assert cmds == ["nosound 1;echo seek: fast retime frame", "nosound 0;echo seek: frame"]
    assert not any(b"host_framerate" in m for ft, *_r, m in frames if ft in (0, 1))
    r = gd.rounds(out)["rounds"]
    assert [x["winner"] for x in r] == [x["winner"] for x in gd.rounds(data)["rounds"]]
    assert r[1]["start"] < 41.0  # the round now arrives sooner


def test_inject_at_start_runs_after_the_engine_start_up():
    data = build_round_demo(MATCH)
    out = seek.inject_at_start(seek.inject_seek(data, 41.0), "exec oldschool.cfg", "keys")
    _seg, frames = frames_of(out)
    cmds = [(round(t, 3), out[off + 9 : off + 73].rstrip(b"\x00").decode()) for ft, t, _n, off, _m in frames if ft == 3]
    assert (1.1, "exec oldschool.cfg;echo keys: frame") in cmds  # a second after the first playback frame (0.1)
    assert ("exec oldschool.cfg;echo keys: stufftext") in str(
        [m for ft, *_r, m in frames if ft in (0, 1) and b"\x09exec oldschool.cfg" in m]
    )
    assert gd.rounds(out)["rounds"] == gd.rounds(data)["rounds"]
