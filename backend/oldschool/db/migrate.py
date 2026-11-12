"""Open the SQLite database and apply numbered migrations.

Migrations are ``schema/NNNN_name.sql`` files applied in order, each in its
own transaction, and recorded in ``schema_migrations``. Released
migrations are never edited: every schema change is a new file.
"""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path

SCHEMA_PACKAGE = "oldschool.db.schema"


def connect(path: Path | str) -> sqlite3.Connection:
    """Connection with the settings every part of the app relies on."""
    # check_same_thread=False: FastAPI may create a request's connection in
    # one worker thread and run the endpoint in another. A connection is
    # still used by one request at a time, which is what sqlite3 requires.
    db = sqlite3.connect(
        str(path), timeout=30, isolation_level=None, check_same_thread=False
    )  # autocommit; explicit BEGIN
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    if str(path) != ":memory:":
        db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA synchronous = NORMAL")
    return db


def migrations() -> list[tuple[int, str, str]]:
    """[(number, name, sql)] sorted by number."""
    out = []
    for entry in resources.files(SCHEMA_PACKAGE).iterdir():
        name = entry.name
        if name.endswith(".sql") and name[:4].isdigit():
            out.append((int(name[:4]), name, entry.read_text(encoding="utf-8")))
    out.sort()
    numbers = [n for n, *_ in out]
    if numbers != list(range(1, len(numbers) + 1)):
        raise RuntimeError(f"migration numbers must be 1..n without gaps, got {numbers}")
    return out


def migrate(db: sqlite3.Connection) -> list[str]:
    """Apply pending migrations; return the names applied."""
    db.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "number INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    done = {row[0] for row in db.execute("SELECT number FROM schema_migrations")}
    applied = []
    for number, name, sql in migrations():
        if number in done:
            continue
        db.execute("BEGIN")
        try:
            for statement in _statements(sql):
                db.execute(statement)
            db.execute("INSERT INTO schema_migrations(number, name) VALUES (?, ?)", (number, name))
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise
        applied.append(name)
    return applied


def _statements(sql: str):
    """Split a migration into complete statements (sqlite3.complete_statement
    keeps triggers and strings with ';' intact)."""
    buf = ""
    for line in sql.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            if buf.strip():
                yield buf
            buf = ""
    if buf.strip() and not buf.strip().startswith("--"):
        raise ValueError(f"incomplete SQL statement at end of migration: {buf[:80]!r}")


def open_database(path: Path | str) -> sqlite3.Connection:
    db = connect(path)
    migrate(db)
    return db
