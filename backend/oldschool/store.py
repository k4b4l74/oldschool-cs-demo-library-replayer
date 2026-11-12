"""Content-addressed demo store.

Each distinct ``.dem`` is kept once, gzip-compressed, at
``<store>/demos/<sha1[:2]>/<sha1>.dem.gz`` whatever archive it came from.
Writes are atomic (temporary file + rename), so a crash never leaves a
half-written demo, and two workers writing the same demo is harmless.
"""

from __future__ import annotations

import gzip
import hashlib
import os
import tempfile
from pathlib import Path

GZIP_LEVEL = 6


def demo_path(store: Path, sha1: str) -> Path:
    return store / "demos" / sha1[:2] / f"{sha1}.dem.gz"


def put_demo(store: Path, data: bytes, sha1: str | None = None) -> tuple[str, Path, bool]:
    """Store ``data``; return (sha1, path, newly_written)."""
    sha1 = sha1 or hashlib.sha1(data).hexdigest()
    path = demo_path(store, sha1)
    if path.exists():
        return sha1, path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".part")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(gzip.compress(data, compresslevel=GZIP_LEVEL, mtime=0))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return sha1, path, True


def read_demo(store: Path, sha1: str) -> bytes:
    data = gzip.decompress(demo_path(store, sha1).read_bytes())
    if hashlib.sha1(data).hexdigest() != sha1:
        raise ValueError(f"stored demo {sha1} is corrupt (hash mismatch)")
    return data


def file_sha1(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()
