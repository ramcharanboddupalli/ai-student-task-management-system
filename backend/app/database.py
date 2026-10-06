from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def database_session(database_path: Path) -> Generator[sqlite3.Connection, None, None]:
    connection = connect(database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(database_path: Path) -> None:
    with database_session(database_path) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        task_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(tasks)")
        }
        additions = {
            "requirements_json": "TEXT NOT NULL DEFAULT '[]'",
            "expected_outcome": "TEXT NOT NULL DEFAULT ''",
            "evaluation_criteria_json": "TEXT NOT NULL DEFAULT '[]'",
        }
        for column, definition in additions.items():
            if column not in task_columns:
                connection.execute(f"ALTER TABLE tasks ADD COLUMN {column} {definition}")
