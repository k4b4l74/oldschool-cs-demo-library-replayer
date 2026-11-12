"""Command line.

python -m oldschool serve  [--port 27960] [--data-dir PATH]
python -m oldschool import PATH... [--mode referenced|copied|moved] [--workers 4] [--data-dir PATH]
python -m oldschool stats  [--data-dir PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from oldschool.config import Paths, default_data_dir
from oldschool.db.migrate import open_database


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="oldschool", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--data-dir", type=Path, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="start the local web app")
    s.add_argument("--port", type=int, default=None)
    i = sub.add_parser("import", help="import demo files, archives or folders")
    i.add_argument("paths", nargs="+", type=Path)
    i.add_argument(
        "--mode",
        choices=("referenced", "copied", "moved"),
        default="referenced",
        help="referenced: leave files where they are (default); copied/moved: keep them in the store",
    )
    i.add_argument("--workers", type=int, default=4)
    i.add_argument(
        "--no-demo-copies",
        action="store_true",
        help="do not copy demos into the store: they are read from these files when played (for a library that stays in place)",
    )
    sub.add_parser("stats", help="print library counts")
    args = ap.parse_args(argv)
    paths = Paths(args.data_dir or default_data_dir()).ensure()

    if args.cmd == "serve":
        from oldschool import main as server

        return server.main((["--port", str(args.port)] if args.port else []) + ["--data-dir", str(paths.root)]) or 0

    db = open_database(paths.database)
    if args.cmd == "import":
        from oldschool.importer import import_paths

        started = time.monotonic()

        def progress(done, total, label, s):
            print(f"[{done}/{total}] {label}  (matches {s.matches}, new demos {s.demos_new})", flush=True)

        summary = import_paths(
            db, args.paths, paths.store, args.mode, args.workers, progress, copy_demos=not args.no_demo_copies
        )
        print(json.dumps({**summary.__dict__, "seconds": round(time.monotonic() - started)}, indent=2))
        return 1 if summary.failed else 0
    if args.cmd == "stats":
        for table in ("originals", "demos", "matches", "rounds", "kills", "player_names", "teams"):
            print(f"{table:13} {db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]:>10,}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
