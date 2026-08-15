import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parent.parent / "echo_database.sqlite"

@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS validations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT NOT NULL,
                is_valid INTEGER NOT NULL CHECK (is_valid IN (0, 1)),
                feedback TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_validations_alert_id
            ON validations(alert_id)
        """)


def save_validation(alert_id: str, is_valid: bool, feedback: str | None = None) -> bool:
    if not alert_id or not alert_id.strip():
        return False 
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO validations (alert_id, is_valid, feedback, timestamp) ""VALUES (?, ?, ?, ?)",
                (alert_id.strip(), int(is_valid), feedback, datetime.now(timezone.utc).isoformat()),)
        return True
    except sqlite3.Error as e:
        print(f"[storage.py] DB error saving validation for {alert_id}: {e}")
        return False


def get_validation_status(alert_id: str) -> list[dict]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM validations WHERE alert_id = ? ORDER BY id DESC", (alert_id,)
        ).fetchall()
        return [dict(r) for r in rows]