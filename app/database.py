import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = "platform.db"


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hypervisor TEXT NOT NULL,
                reachable INTEGER NOT NULL,
                checked_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                hypervisor TEXT NOT NULL,
                vm_id TEXT NOT NULL,
                action TEXT NOT NULL,
                success INTEGER NOT NULL,
                performed_at TEXT NOT NULL
            )
        """)
        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def record_health_check(hypervisor: str, reachable: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO health_checks (hypervisor, reachable, checked_at) VALUES (?, ?, ?)",
            (hypervisor, int(reachable), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


def record_activity(username: str, hypervisor: str, vm_id: str, action: str, success: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO activity_log (username, hypervisor, vm_id, action, success, performed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (username, hypervisor, vm_id, action, int(success), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


def get_uptime_history(limit: int = 200) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT hypervisor, reachable, checked_at FROM health_checks "
            "ORDER BY checked_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def get_activity_log(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT username, hypervisor, vm_id, action, success, performed_at FROM activity_log "
            "ORDER BY performed_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]