"""Start the app: data folders, database, local web server.

python -m oldschool.main [--port 27960] [--data-dir PATH]
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
from pathlib import Path

import uvicorn

from oldschool.api.app import create_app
from oldschool.config import DEFAULT_PORT, HOST, Paths, default_data_dir, frontend_dist

FRONTEND_DIST = frontend_dist()


def log_to_file(path: Path) -> Path:
    """App messages and errors (with tracebacks) go to <data dir>/logs/app.log too."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    for name in ("oldschool", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return path


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--data-dir", type=Path, default=None)
    args = ap.parse_args(argv)
    paths = Paths(args.data_dir or default_data_dir()).ensure()
    log_file = log_to_file(paths.root / "logs" / "app.log")
    app = create_app(paths.database, FRONTEND_DIST, store=paths.store, data_dir=paths.root, background=True)
    app.state.log_file = str(log_file)
    print(f"Data: {paths.root}\nOpen http://{HOST}:{args.port}/")
    uvicorn.run(app, host=HOST, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
