"""Get a demo's bytes: from the store when it was copied there, otherwise
from a file it was imported from (an archive member or a loose .dem).

Libraries imported with ``--no-demo-copies`` stay where they are and are
read on demand; every candidate source is checked against the demo's SHA-1.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from oldschool import archives, store


class DemoUnavailable(Exception):
    pass


def demo_bytes(db: sqlite3.Connection, store_root: Path, sha1: str) -> bytes:
    if store.demo_path(store_root, sha1).exists():
        return store.read_demo(store_root, sha1)
    tried = []
    for row in db.execute(
        """SELECT a.chain, a.name, o.source_path, o.kept_path FROM archive_members a
           JOIN originals o ON o.id = a.original_id WHERE a.demo_sha1 = ? ORDER BY o.id""",
        (sha1,),
    ):
        for p in (row["kept_path"], row["source_path"]):
            if not p or not Path(p).is_file():
                continue
            tried.append(p)
            data = _member(Path(p), row["chain"], row["name"])
            if data is not None and hashlib.sha1(data).hexdigest() == sha1:
                return data
    if tried:
        raise DemoUnavailable(f"the demo could not be read again from {tried[0]} (changed or damaged?)")
    raise DemoUnavailable("the demo's file is no longer where it was imported from")


def _member(path: Path, chain: str, name: str) -> bytes | None:
    if not chain and path.name == name and path.suffix.lower() == ".dem":
        return path.read_bytes()
    want = (tuple(c for c in chain.split("/") if c), name)
    # Nested chains contain '/' inside member names too: compare the joined path.
    joined = "/".join([*want[0], name])
    for m in archives.iter_members(path, errors=[]):
        if "/".join(m["chain"] + (m["name"],)) == joined:
            return m["read"]()
    return None
