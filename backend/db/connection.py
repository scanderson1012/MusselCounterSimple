"""SQLite database_connection factory used by all DB helper modules."""

import sqlite3

from backend.init_db import DB_PATH


def get_database_connection() -> sqlite3.Connection:
    """Open one SQLite database_connection with project defaults applied.

    Defaults:
    - `row_factory=sqlite3.Row` for dict-like column access.
    - `PRAGMA foreign_keys=ON` to enforce relational integrity.
    """
    database_connection = sqlite3.connect(DB_PATH)
    database_connection.row_factory = sqlite3.Row
    database_connection.execute("PRAGMA foreign_keys = ON;")
    return database_connection
