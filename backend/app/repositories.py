from __future__ import annotations

import sqlite3


def count_admins(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) AS count FROM admins").fetchone()
    return int(row["count"])


def find_admin_by_email(connection: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT id, full_name, email, password_hash FROM admins WHERE email = ?",
        (email,),
    ).fetchone()


def create_admin(
    connection: sqlite3.Connection, full_name: str, email: str, password_hash: str
) -> sqlite3.Row:
    cursor = connection.execute(
        "INSERT INTO admins (full_name, email, password_hash) VALUES (?, ?, ?)",
        (full_name, email, password_hash),
    )
    return connection.execute(
        "SELECT id, full_name, email FROM admins WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()


def find_student_by_login(connection: sqlite3.Connection, student_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """SELECT id, student_id, full_name, password_hash, is_active
           FROM students WHERE student_id = ?""",
        (student_id,),
    ).fetchone()

