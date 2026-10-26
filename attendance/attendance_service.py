"""
attendance/attendance_service.py
Business-logic layer for recording, querying, and managing attendance.
"""

import logging
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

from database import db_manager as db

logger = logging.getLogger(__name__)


class AttendanceService:
    """
    Wraps attendance recording with cooldown management so the camera
    loop does not spam the database.
    """

    def __init__(self, cooldown_seconds: int = 30):
        self.cooldown = cooldown_seconds
        # {emp_id: last_recorded_timestamp}
        self._last_recorded: Dict[str, float] = {}

    def try_record(
        self, emp_id: str, name: str
    ) -> Tuple[str, Optional[str]]:
        """
        Attempt to record attendance.
        Returns (status, message):
          status: "recorded" | "already_marked" | "cooldown" | "error"
          message: human-readable detail
        """
        now = time.time()
        last = self._last_recorded.get(emp_id, 0)

        # Cooldown check (in-session)
        if now - last < self.cooldown:
            remaining = int(self.cooldown - (now - last))
            return "cooldown", f"Cooldown active ({remaining}s)"

        try:
            inserted, orig_time = db.record_attendance(emp_id, name)
        except Exception as exc:
            logger.error("Attendance DB error for %s: %s", emp_id, exc)
            return "error", str(exc)

        self._last_recorded[emp_id] = now

        if inserted:
            ts_str = datetime.now().strftime("%H:%M:%S")
            return "recorded", f"Attendance recorded at {ts_str}"
        else:
            return "already_marked", f"Already marked today (first entry: {orig_time})"

    def reset_cooldown(self, emp_id: str) -> None:
        self._last_recorded.pop(emp_id, None)

    def get_today_summary(self):
        return db.get_today_attendance()
