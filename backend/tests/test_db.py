"""Migrations apply cleanly, once, with foreign keys on."""

import sqlite3

import pytest

from oldschool.db import migrate


def test_migrations_apply_once(tmp_path):
    db = migrate.connect(tmp_path / "t.sqlite")
    first = migrate.migrate(db)
    assert first and first[0] == "0001_init.sql"
    assert migrate.migrate(db) == []
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"originals", "demos", "matches", "rounds", "kills", "engines", "jobs"} <= tables
    assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_foreign_keys_enforced(tmp_path):
    db = migrate.open_database(tmp_path / "t.sqlite")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO match_demos(match_id, demo_sha1, part_no) VALUES (999, 'x', 1)")


def test_statement_splitter_keeps_semicolons_in_strings():
    sql = "CREATE TABLE a(x TEXT DEFAULT 'a;b');\n-- comment\nCREATE TABLE b(y);\n"
    assert len(list(migrate._statements(sql))) == 2
