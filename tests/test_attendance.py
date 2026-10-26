"""
tests/test_attendance.py — Attendance recording and duplicate prevention tests
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import unittest
from unittest.mock import patch
from datetime import date

import config as _cfg
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_cfg.DB_PATH_STR = _tmp.name
_tmp.close()

from database import db_manager as db
from attendance.attendance_service import AttendanceService


class TestAttendanceRecording(unittest.TestCase):
    def setUp(self):
        db.init_db()
        try:
            db.create_employee("ATT1", "Grace")
        except Exception:
            pass
        # Clear any existing attendance for ATT1 today
        today = date.today().isoformat()
        with db.get_conn() as conn:
            conn.execute("DELETE FROM attendance WHERE emp_id='ATT1' AND attendance_date=?", (today,))

    def test_first_attendance_recorded(self):
        inserted, orig = db.record_attendance("ATT1", "Grace")
        self.assertTrue(inserted)
        self.assertIsNone(orig)

    def test_duplicate_prevented(self):
        db.record_attendance("ATT1", "Grace")
        inserted, orig = db.record_attendance("ATT1", "Grace")
        self.assertFalse(inserted)
        self.assertIsNotNone(orig)

    def test_today_count(self):
        count_before = db.today_count()
        db.record_attendance("ATT1", "Grace")
        self.assertGreaterEqual(db.today_count(), count_before)

    def test_attendance_in_today_list(self):
        db.record_attendance("ATT1", "Grace")
        rows = db.get_today_attendance()
        emp_ids = [r["emp_id"] for r in rows]
        self.assertIn("ATT1", emp_ids)

    def test_delete_attendance_record(self):
        db.record_attendance("ATT1", "Grace")
        rows = db.get_today_attendance()
        rec_id = next(r["id"] for r in rows if r["emp_id"] == "ATT1")
        db.delete_attendance_record(rec_id)
        rows_after = [r for r in db.get_today_attendance() if r["id"] == rec_id]
        self.assertEqual(rows_after, [])


class TestAttendanceService(unittest.TestCase):
    def setUp(self):
        db.init_db()
        try:
            db.create_employee("SVC1", "Hank")
        except Exception:
            pass
        today = date.today().isoformat()
        with db.get_conn() as conn:
            conn.execute("DELETE FROM attendance WHERE emp_id='SVC1' AND attendance_date=?", (today,))

    def test_service_records(self):
        svc = AttendanceService(cooldown_seconds=0)
        status, msg = svc.try_record("SVC1", "Hank")
        self.assertEqual(status, "recorded")

    def test_service_already_marked(self):
        svc = AttendanceService(cooldown_seconds=0)
        svc.try_record("SVC1", "Hank")
        status, msg = svc.try_record("SVC1", "Hank")
        self.assertEqual(status, "already_marked")

    def test_service_cooldown(self):
        svc = AttendanceService(cooldown_seconds=9999)
        # first call succeeds
        status, _ = svc.try_record("SVC1", "Hank")
        # simulate a second employee frame quickly
        # reset DB so second insert would succeed, but cooldown should block
        today = date.today().isoformat()
        with db.get_conn() as conn:
            conn.execute("DELETE FROM attendance WHERE emp_id='SVC1' AND attendance_date=?", (today,))
        status2, _ = svc.try_record("SVC1", "Hank")
        self.assertEqual(status2, "cooldown")


class TestAttendanceFilters(unittest.TestCase):
    def setUp(self):
        db.init_db()
        try:
            db.create_employee("FLT1", "Iris")
        except Exception:
            pass
        today = date.today().isoformat()
        with db.get_conn() as conn:
            conn.execute("DELETE FROM attendance WHERE emp_id='FLT1' AND attendance_date=?", (today,))
        db.record_attendance("FLT1", "Iris")

    def test_filter_by_emp_id(self):
        rows, total = db.get_attendance_filtered(emp_id="FLT1")
        self.assertGreaterEqual(total, 1)

    def test_filter_by_name(self):
        rows, total = db.get_attendance_filtered(name_like="Iris")
        self.assertGreaterEqual(total, 1)

    def test_filter_no_match(self):
        rows, total = db.get_attendance_filtered(emp_id="ZZZZZZ")
        self.assertEqual(total, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
