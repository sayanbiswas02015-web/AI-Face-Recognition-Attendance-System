"""
auth/admin_auth.py
Administrator authentication with bcrypt password hashing,
login-attempt tracking, and lockout.
"""

import logging
import time
from typing import Optional
from datetime import datetime

import bcrypt

from database import db_manager as db

logger = logging.getLogger(__name__)

# ─── In-memory brute-force tracking ──────────────────────────────────────────
_failed_attempts: dict = {}   # username -> {"count": int, "locked_until": float}

MAX_ATTEMPTS    = 5
LOCKOUT_SECONDS = 300


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _track_failure(username: str) -> int:
    rec = _failed_attempts.setdefault(username, {"count": 0, "locked_until": 0.0})
    rec["count"] += 1
    if rec["count"] >= MAX_ATTEMPTS:
        rec["locked_until"] = time.time() + LOCKOUT_SECONDS
    return rec["count"]


def _reset_attempts(username: str) -> None:
    _failed_attempts.pop(username, None)


def _is_locked(username: str) -> tuple[bool, float]:
    rec = _failed_attempts.get(username)
    if not rec:
        return False, 0.0
    if rec.get("locked_until", 0) > time.time():
        return True, rec["locked_until"] - time.time()
    return False, 0.0


# ─── Public API ───────────────────────────────────────────────────────────────

def needs_first_time_setup() -> bool:
    """True if no admin accounts exist yet."""
    return db.count_admins() == 0


def setup_admin(username: str, password: str) -> tuple[bool, str]:
    """Create the first administrator account."""
    if not username or len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if db.count_admins() > 0:
        return False, "Admin account already exists."
    try:
        hashed = _hash_password(password)
        db.create_admin(username, hashed)
        db.audit("SYSTEM", "ADMIN_SETUP", f"username={username}")
        return True, "Admin account created successfully."
    except Exception as exc:
        logger.error("Admin setup failed: %s", exc)
        return False, str(exc)


def login(username: str, password: str) -> tuple[bool, str]:
    """Verify credentials. Returns (success, message)."""
    locked, remaining = _is_locked(username)
    if locked:
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        return False, f"Account locked. Try again in {mins}m {secs}s."

    row = db.get_admin(username)
    if not row or not _verify_password(password, row["password_hash"]):
        count = _track_failure(username)
        remaining_attempts = MAX_ATTEMPTS - count
        if remaining_attempts <= 0:
            db.audit(username, "LOGIN_LOCKED", "too many failed attempts")
            return False, f"Too many failed attempts. Account locked for {LOCKOUT_SECONDS // 60} minutes."
        db.audit(username, "LOGIN_FAILED", f"attempt={count}")
        return False, f"Invalid credentials. {remaining_attempts} attempt(s) remaining."

    _reset_attempts(username)
    db.audit(username, "LOGIN_SUCCESS")
    return True, "Login successful."


def change_password(username: str, old_password: str, new_password: str) -> tuple[bool, str]:
    if len(new_password) < 8:
        return False, "New password must be at least 8 characters."
    row = db.get_admin(username)
    if not row or not _verify_password(old_password, row["password_hash"]):
        return False, "Current password is incorrect."
    try:
        new_hash = _hash_password(new_password)
        db.update_admin_password(username, new_hash)
        db.audit(username, "PASSWORD_CHANGED")
        return True, "Password changed successfully."
    except Exception as exc:
        logger.error("Password change failed: %s", exc)
        return False, str(exc)
