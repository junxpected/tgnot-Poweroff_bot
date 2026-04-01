"""SQLite data access layer."""

from __future__ import annotations

import sqlite3
from typing import Optional

from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(cur: sqlite3.Cursor, table: str, column_def: str) -> None:
    column_name = column_def.split()[0]
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    if column_name not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")


def init_db() -> None:
    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                city TEXT,
                street TEXT,
                house TEXT,
                queue TEXT,
                subqueue TEXT
            )
        """
        )

        # Safe migrations for old DBs.
        _ensure_column(cur, "users", "city TEXT")
        _ensure_column(cur, "users", "street TEXT")
        _ensure_column(cur, "users", "house TEXT")
        _ensure_column(cur, "users", "queue TEXT")
        _ensure_column(cur, "users", "subqueue TEXT")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                queue TEXT NOT NULL,
                off_time TEXT NOT NULL,
                on_time TEXT NOT NULL
            )
        """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                kind TEXT NOT NULL,
                UNIQUE(user_id, date, time, kind)
            )
        """
        )


def upsert_user(user_id: int, username: str, first_name: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
        """,
            (user_id, username, first_name),
        )


def set_user_address(
    user_id: int,
    city: str,
    street: str,
    house: str,
    queue: str,
    subqueue: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, city, street, house, queue, subqueue)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                city = excluded.city,
                street = excluded.street,
                house = excluded.house,
                queue = excluded.queue,
                subqueue = excluded.subqueue
        """,
            (user_id, city, street, house, queue, subqueue),
        )


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone()


def get_all_users() -> list[sqlite3.Row]:
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM users WHERE queue IS NOT NULL")
        return cur.fetchall()


def save_schedule(date: str, queue: str, off_time: str, on_time: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO schedules (date, queue, off_time, on_time)
            VALUES (?, ?, ?, ?)
        """,
            (date, queue, off_time, on_time),
        )


def clear_schedule_for(date: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM schedules WHERE date = ?", (date,))


def get_schedule_for(date: str, queue: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT * FROM schedules
            WHERE date = ? AND queue = ?
            ORDER BY off_time
        """,
            (date, queue),
        )
        return cur.fetchall()


def notification_exists(user_id: int, date: str, time: str, kind: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT 1 FROM notifications
            WHERE user_id = ? AND date = ? AND time = ? AND kind = ?
        """,
            (user_id, date, time, kind),
        )
        return cur.fetchone() is not None


def add_notification_mark(user_id: int, date: str, time: str, kind: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO notifications (user_id, date, time, kind)
            VALUES (?, ?, ?, ?)
        """,
            (user_id, date, time, kind),
        )


def get_schedule_for_date(date: str) -> dict[str, list[str]]:
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT queue, off_time, on_time FROM schedules
            WHERE date = ?
            ORDER BY queue, off_time
        """,
            (date,),
        )
        rows = cur.fetchall()

    result: dict[str, list[str]] = {}
    for row in rows:
        queue = row["queue"]
        interval = f"{row['off_time']}-{row['on_time']}"
        result.setdefault(queue, []).append(interval)
    return result
