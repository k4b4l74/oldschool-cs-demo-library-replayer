"""Shared FastAPI dependencies."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request

from oldschool.db.migrate import connect


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    """One connection per request: sqlite3 connections are bound to the
    thread that created them, and FastAPI runs sync endpoints in a pool."""
    db = connect(request.app.state.database)
    try:
        yield db
    finally:
        db.close()


Db = Annotated[sqlite3.Connection, Depends(get_db)]
