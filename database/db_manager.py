"""
database/db_manager.py
Central SQLite manager for the AI Face Attendance System.
All SQL goes through this module using parameterized queries.
"""

import sqlite3
import logging
import numpy as np
import io
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from config import DB_PATH_STR

logger = logging.getLogger(__name__)


# ─── Connection helper ────────────────────────────────────────────────────────

@contextmanager
def get_conn():
    """Yield a WAL-mode, FK-enabled connection; roll back on error."""
    conn = sqlite3.connect(DB_PATH_STR, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── Schema initialisation ────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables and indexes if they do not already exist."""
    schema_path = Path(__file__).parent / "schema.sql"
    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                emp_id      TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                is_active   INTEGER NOT NULL DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS face_embeddings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_id      TEXT    NOT NULL,
                embedding   BLOB    NOT NULL,
                created_at  TEXT    NOT NULL,
                FOREIGN KEY (emp_id) REFERENCES employees(emp_id) ON DELETE RESTRICT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                attendance_date TEXT    NOT NULL,
                entry_time      TEXT    NOT NULL,
                name            TEXT    NOT NULL,
                emp_id          TEXT    NOT NULL,
                UNIQUE (emp_id, attendance_date)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                created_at    TEXT    NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                ts      TEXT    NOT NULL,
                actor   TEXT    NOT NULL,
                action  TEXT    NOT NULL,
                details TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_face_emp ON face_embeddings(emp_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_att_date ON attendance(attendance_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_att_emp  ON attendance(emp_id)")

    logger.info("Database initialised at %s", DB_PATH_STR)


# ─── Embedding serialisation ──────────────────────────────────────────────────

def embedding_to_blob(embedding: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, embedding.astype(np.float32))
    return buf.getvalue()


def blob_to_embedding(blob: bytes) -> np.ndarray:
    buf = io.BytesIO(blob)
    return np.load(buf)


# ─── Admin Users ──────────────────────────────────────────────────────────────

def count_admins() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM admin_users").fetchone()
        return row[0]


def create_admin(username: str, password_hash: str) -> None:
    ts = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO admin_users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, ts)
        )
    logger.info("Admin account created: %s", username)


def get_admin(username: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM admin_users WHERE username = ?", (username,)
        ).fetchone()


def update_admin_password(username: str, new_hash: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE admin_users SET password_hash = ? WHERE username = ?",
            (new_hash, username)
        )


# ─── Employees ────────────────────────────────────────────────────────────────

def employee_exists(emp_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM employees WHERE emp_id = ?", (emp_id,)
        ).fetchone()
        return row is not None


def create_employee(emp_id: str, name: str) -> None:
    ts = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO employees (emp_id, name, created_at, is_active) VALUES (?, ?, ?, 1)",
            (emp_id, name, ts)
        )
    logger.info("Employee created: %s / %s", emp_id, name)


def get_employee(emp_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM employees WHERE emp_id = ?", (emp_id,)
        ).fetchone()


def list_employees() -> List[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM employees ORDER BY created_at DESC"
        ).fetchall()


def set_employee_active(emp_id: str, active: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE employees SET is_active = ? WHERE emp_id = ?",
            (1 if active else 0, emp_id)
        )


def delete_employee_full(emp_id: str) -> None:
    """Permanently delete employee + embeddings. Attendance is preserved."""
    with get_conn() as conn:
        conn.execute("DELETE FROM face_embeddings WHERE emp_id = ?", (emp_id,))
        conn.execute("DELETE FROM employees WHERE emp_id = ?", (emp_id,))
    logger.info("Employee fully deleted: %s", emp_id)


# ─── Face Embeddings ──────────────────────────────────────────────────────────

def save_embeddings(emp_id: str, embeddings: List[np.ndarray]) -> None:
    ts = datetime.now().isoformat()
    with get_conn() as conn:
        # Remove old embeddings for this employee first
        conn.execute("DELETE FROM face_embeddings WHERE emp_id = ?", (emp_id,))
        for emb in embeddings:
            blob = embedding_to_blob(emb)
            conn.execute(
                "INSERT INTO face_embeddings (emp_id, embedding, created_at) VALUES (?, ?, ?)",
                (emp_id, blob, ts)
            )
    logger.info("Saved %d embeddings for %s", len(embeddings), emp_id)


def load_all_embeddings() -> Dict[str, List[np.ndarray]]:
    """
    Returns {emp_id: [embedding, ...]} for all ACTIVE employees.
    """
    result: Dict[str, List[np.ndarray]] = {}
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT fe.emp_id, fe.embedding
            FROM face_embeddings fe
            JOIN employees e ON e.emp_id = fe.emp_id
            WHERE e.is_active = 1
        """).fetchall()
    for row in rows:
        emb = blob_to_embedding(row["embedding"])
        result.setdefault(row["emp_id"], []).append(emb)
    return result


def delete_embeddings(emp_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM face_embeddings WHERE emp_id = ?", (emp_id,))
    logger.info("Embeddings deleted for %s", emp_id)


def has_embeddings(emp_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM face_embeddings WHERE emp_id = ?", (emp_id,)
        ).fetchone()
        return row is not None


# ─── Attendance ───────────────────────────────────────────────────────────────

def record_attendance(emp_id: str, name: str) -> Tuple[bool, Optional[str]]:
    """
    Insert attendance for today. Returns (inserted, existing_entry_time).
    Uses INSERT OR IGNORE so the UNIQUE(emp_id, date) constraint is respected.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    now   = datetime.now().strftime("%H:%M:%S")
    try:
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT OR IGNORE INTO attendance
                   (attendance_date, entry_time, name, emp_id)
                   VALUES (?, ?, ?, ?)""",
                (today, now, name, emp_id)
            )
            if cur.rowcount == 1:
                logger.info("Attendance recorded: %s %s", emp_id, name)
                return True, None
            else:
                # Already exists — fetch original time
                row = conn.execute(
                    "SELECT entry_time FROM attendance WHERE emp_id=? AND attendance_date=?",
                    (emp_id, today)
                ).fetchone()
                orig = row["entry_time"] if row else "?"
                return False, orig
    except Exception as exc:
        logger.error("Attendance insert failed: %s", exc)
        return False, None


def get_today_attendance() -> List[sqlite3.Row]:
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM attendance
               WHERE attendance_date = ?
               ORDER BY entry_time DESC""",
            (today,)
        ).fetchall()


def get_attendance_filtered(
    date_from: Optional[str] = None,
    date_to:   Optional[str] = None,
    emp_id:    Optional[str] = None,
    name_like: Optional[str] = None,
    limit:     int = 500,
    offset:    int = 0
) -> Tuple[List[sqlite3.Row], int]:
    """Return (rows, total_count) matching filters."""
    clauses, params = [], []

    if date_from:
        clauses.append("attendance_date >= ?"); params.append(date_from)
    if date_to:
        clauses.append("attendance_date <= ?"); params.append(date_to)
    if emp_id:
        clauses.append("emp_id = ?"); params.append(emp_id)
    if name_like:
        clauses.append("name LIKE ?"); params.append(f"%{name_like}%")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM attendance {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"""SELECT * FROM attendance {where}
                ORDER BY attendance_date DESC, entry_time DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset]
        ).fetchall()
    return rows, total


def delete_attendance_record(record_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM attendance WHERE id = ?", (record_id,))


def today_count() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM attendance WHERE attendance_date = ?", (today,)
        ).fetchone()
        return row[0]


# ─── Statistics ───────────────────────────────────────────────────────────────

def dashboard_stats() -> Dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        total_emp    = conn.execute("SELECT COUNT(*) FROM employees WHERE is_active=1").fetchone()[0]
        present_today = conn.execute(
            "SELECT COUNT(*) FROM attendance WHERE attendance_date=?", (today,)
        ).fetchone()[0]
        absent_today  = max(0, total_emp - present_today)
        total_records = conn.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
        latest_att    = conn.execute(
            "SELECT * FROM attendance WHERE attendance_date=? ORDER BY entry_time DESC LIMIT 5", (today,)
        ).fetchall()
        recent_emp    = conn.execute(
            "SELECT * FROM employees ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
    return {
        "total_employees": total_emp,
        "present_today":   present_today,
        "absent_today":    absent_today,
        "total_records":   total_records,
        "latest_attendance": latest_att,
        "recent_employees":  recent_emp,
    }


# ─── Settings ─────────────────────────────────────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (key, value)
        )


# ─── Audit Log ────────────────────────────────────────────────────────────────

def audit(actor: str, action: str, details: str = "") -> None:
    ts = datetime.now().isoformat()
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO audit_log (ts, actor, action, details) VALUES (?, ?, ?, ?)",
                (ts, actor, action, details)
            )
    except Exception as exc:
        logger.warning("Audit log failed: %s", exc)
