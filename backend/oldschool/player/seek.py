"""Seek inside a demo on engines that cannot seek.

The old GoldSrc engines have no "go to time" command. To start a demo at a
given point we:

1. insert a console-command frame (frame type 3, the same frame ``record``
   uses for typed commands) at the target time into the *copy* of the demo
   handed to the game, holding the ``resume`` command;
2. start playback fast-forwarded and muted (``start_args``).

When playback reaches the inserted frame the engine runs ``resume`` and the
demo continues at normal speed. ``host_framerate`` and ``nosound`` are not
saved to config.cfg, so quitting during the fast-forward leaves no trace.

Confirmed in game on 2026-11-11: this method on CS 1.4 and 1.5
(engines 1.1.0.9, 1.1.1.0); ``inject_seek_retime`` on CS 1.0/1.1 and 1.3
(engines 1.1.0.6, 1.1.0.8).
"""

from __future__ import annotations

import struct
from collections.abc import Callable

from oldschool.parser import goldsrc as gd

COMMAND_FRAME = 3
COMMAND_SIZE = 64  # fixed, NUL padded
DEFAULT_RATE = 0.5  # demo seconds per rendered frame (~50x at 100 fps)
DEFAULT_RESUME = "host_framerate 0;nosound 0"


def start_args(rate: float = DEFAULT_RATE) -> list[str]:
    """Command-line commands that start playback fast-forwarded and muted."""
    if not 0 < rate <= 5:
        raise ValueError(f"seek rate out of range: {rate}")
    return ["+host_framerate", f"{rate:g}", "+nosound", "1"]


# How the "back to normal" command reaches the engine. Engines 1.1.0.9
# (CS 1.4) and 1.1.1.0 (CS 1.5) run console-command frames; on 1.1.0.6
# (CS 1.0/1.1) and 1.1.0.8 (CS 1.3) the jump failed (in game, 2026-11-11), so
# the command is also appended to a server message as svc_stufftext, which
# every Half-Life client executes. The echo markers show in qconsole.log
# which route worked.
SVC_STUFFTEXT = 9
FRAME_RESUME = DEFAULT_RESUME + ";echo seek: frame"
STUFF_RESUME = DEFAULT_RESUME + ";echo seek: stufftext"


def inject_resume(data: bytes, at: float) -> bytes:
    """Both routes at ``at``: a command frame and a stufftext. Running the
    resume command twice is harmless."""
    return inject_command(inject_stufftext(data, at, STUFF_RESUME), at, FRAME_RESUME)


def first_playback_time(data: bytes) -> float:
    header, directory, prefix = _layout(data)
    _i, offset, _fno = _find(data, directory, prefix, float("-inf"), netmsg_only=True)
    return struct.unpack_from("<f", data, offset + 1)[0]


def inject_seek(data: bytes, at: float, rate: float = DEFAULT_RATE) -> bytes:
    """Fast-forward from the first playback frame to ``at``, then play normally.

    The fast-forward is switched on inside the demo too, not only on the
    command line: on older engines the command-line value may not survive
    until playback starts. Every switch goes by both routes and echoes a
    marker into qconsole.log ("seek: fast …", "seek: frame/stufftext")."""
    start_args(rate)  # validates the rate
    fast = f"host_framerate {rate:g};nosound 1"
    t0 = first_playback_time(data)
    if at <= t0:
        return data
    out = inject_resume(data, at)
    out = inject_stufftext(out, t0, fast + ";echo seek: fast stufftext")
    return inject_command(out, t0, fast + ";echo seek: fast frame")


# Engines 1.1.0.6 (CS 1.0/1.1) and 1.1.0.8 (CS 1.3) run the injected
# commands but do not speed demo playback up with host_framerate (in game,
# 2026-11-11: "seek : fast frame" in qconsole.log, normal speed on screen).
# For them the demo copy itself is made faster: the timestamps before the
# target are divided by RETIME_FACTOR, so the engine reaches the round
# sooner while pacing frames as usual; later frames keep their spacing.
RETIME_FACTOR = 20.0


def retime(data: bytes, at: float, factor: float = RETIME_FACTOR) -> tuple[bytes, Callable[[float], float]]:
    """Copy of ``data`` with playback time between the first playback frame
    and ``at`` compressed ``factor`` times. Returns (demo, time mapping)."""
    if factor < 1:
        raise ValueError("retime factor must be >= 1")
    header, directory, prefix = _layout(data)
    t0 = first_playback_time(data)
    shift = (at - t0) * (1 - 1 / factor)

    def f(t: float) -> float:
        if t <= t0:
            return t
        if t < at:
            return t0 + (t - t0) / factor
        return t - shift

    out = bytearray(data)
    for i, entry in enumerate(directory):
        if entry["type"] == 0:  # LOADING segment
            continue
        start, end = entry["offset"], entry["offset"] + entry["length"]
        try:
            for ftype, ftime, _fno, offset, _msg in gd.iter_frames(data, start, end, prefix):
                struct.pack_into("<f", out, offset + 1, f(ftime))
                if ftype in (0, 1):  # the network-message block starts with its own timestamp
                    inner = struct.unpack_from("<f", data, offset + 9)[0]
                    struct.pack_into("<f", out, offset + 9, f(inner))
        except gd.DemoError as exc:
            raise ValueError(f"cannot walk the demo frames: {exc}") from exc
        p = header["directory_offset"] + 4 + gd.DIR_ENTRY_SIZE * i
        track = struct.unpack_from("<f", out, p + 76)[0]
        struct.pack_into("<f", out, p + 76, f(track))
    return bytes(out), f


def inject_seek_retime(data: bytes, at: float, factor: float = RETIME_FACTOR) -> bytes:
    """Seek for engines that ignore host_framerate during playback: compress
    the time before ``at`` and mute sound until then. Markers in
    qconsole.log: "seek: fast retime …" at the start, "seek: frame/stufftext"
    at the target."""
    t0 = first_playback_time(data)
    if at <= t0:
        return data
    out, f = retime(data, at, factor)
    target = f(at)
    out = inject_command(
        inject_stufftext(out, target, "nosound 0;echo seek: stufftext"), target, "nosound 0;echo seek: frame"
    )
    out = inject_stufftext(out, t0, "nosound 1;echo seek: fast retime stufftext")
    return inject_command(out, t0, "nosound 1;echo seek: fast retime frame")


def _layout(data: bytes):
    header = gd.parse_header(data)
    directory = gd.read_directory(data, header["directory_offset"])
    if not directory:
        raise ValueError("demo has no readable directory (interrupted recording); cannot seek in it")
    spans = [(e["offset"], e["offset"] + e["length"], e["description"]) for e in directory]
    return header, directory, gd.detect_prefix(data, spans)


def _find(data: bytes, directory: list, prefix: int, at: float, netmsg_only: bool):
    """(segment index, frame offset, frame number) of the first playback frame
    at or after ``at``. With ``netmsg_only`` only network-message frames
    count, falling back to the last one before the end."""
    last = None
    for i, entry in enumerate(directory):
        if entry["type"] == 0:  # LOADING segment
            continue
        start, end = entry["offset"], entry["offset"] + entry["length"]
        try:
            for ftype, ftime, fno, offset, _msg in gd.iter_frames(data, start, end, prefix):
                if netmsg_only:
                    if ftype in (0, 1):
                        if ftime >= at:
                            return i, offset, fno
                        last = (i, offset, fno)
                    elif ftype == 5 and last:
                        return last
                elif ftype == 5 or ftime >= at:
                    return i, offset, fno
        except gd.DemoError as exc:
            raise ValueError(f"cannot walk the demo frames: {exc}") from exc
    if last:
        return last
    raise ValueError(f"no playback frame at or after {at:.1f}s")


def _insert(
    data: bytes, header: dict, directory: list, seg_index: int, at_offset: int, blob: bytes, new_frames: int
) -> bytearray:
    """Insert ``blob`` at ``at_offset`` inside segment ``seg_index`` and fix the
    header's directory offset and the directory entries."""
    out = bytearray(data[:at_offset] + blob + data[at_offset:])
    grow = len(blob)
    dir_at = header["directory_offset"]
    new_dir = dir_at + grow if dir_at >= at_offset else dir_at
    struct.pack_into("<i", out, 540, new_dir)
    for i in range(len(directory)):
        p = new_dir + 4 + gd.DIR_ENTRY_SIZE * i
        frames, off, length = struct.unpack_from("<iii", out, p + 80)
        if i == seg_index:
            struct.pack_into("<iii", out, p + 80, frames + new_frames, off, length + grow)
        elif off >= at_offset:
            struct.pack_into("<i", out, p + 84, off + grow)
    return out


# Commands run once playback has started, e.g. the player's keys file. On
# CS 1.3 (engine 1.1.0.8) the engine runs config.cfg, which starts with
# "unbindall", after the command line (seen in game, 2026-11-12): a command-line
# "+exec" is undone. A second into the demo the start-up is over.
START_DELAY = 1.0


def inject_at_start(data: bytes, command: str, marker: str, delay: float = START_DELAY) -> bytes:
    """Run ``command`` ``delay`` seconds after playback starts, by both routes
    (echo "<marker>: frame/stufftext" in qconsole.log)."""
    at = first_playback_time(data) + delay
    out = inject_stufftext(data, at, f"{command};echo {marker}: stufftext")
    return inject_command(out, at, f"{command};echo {marker}: frame")


def inject_command(data: bytes, at: float, command: str = DEFAULT_RESUME) -> bytes:
    """Return a copy of ``data`` with a console-command frame placed before
    the first playback frame whose clock reaches ``at`` (or before the end
    of the playback segment). Raises ValueError when the demo cannot take it."""
    cmd = command.encode("ascii")
    if len(cmd) >= COMMAND_SIZE:
        raise ValueError(f"demo command too long ({len(cmd)} bytes, max {COMMAND_SIZE - 1}): {command}")
    header, directory, prefix = _layout(data)
    seg_index, offset, frame_no = _find(data, directory, prefix, at, netmsg_only=False)
    frame = struct.pack("<Bfi", COMMAND_FRAME, at, frame_no) + cmd.ljust(COMMAND_SIZE, b"\x00")
    return bytes(_insert(data, header, directory, seg_index, offset, frame, 1))


def inject_stufftext(data: bytes, at: float, command: str = DEFAULT_RESUME) -> bytes:
    """Return a copy of ``data`` where the first network message at or after
    ``at`` ends with an extra svc_stufftext carrying ``command``."""
    cmd = command.encode("ascii")
    if b"\x00" in cmd or len(cmd) > 1000:
        raise ValueError("bad stufftext command")
    header, directory, prefix = _layout(data)
    seg_index, offset, _fno = _find(data, directory, prefix, at, netmsg_only=True)
    len_at = offset + 9 + prefix
    length = struct.unpack_from("<i", data, len_at)[0]
    payload = bytes([SVC_STUFFTEXT]) + cmd + b"\n\x00"
    out = _insert(data, header, directory, seg_index, len_at + 4 + length, payload, 0)
    struct.pack_into("<i", out, len_at, length + len(payload))
    return bytes(out)
