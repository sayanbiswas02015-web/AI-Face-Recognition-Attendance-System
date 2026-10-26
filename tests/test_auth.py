"""
tests/test_auth.py — Admin authentication tests
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import unittest

import config as _cfg
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_cfg.DB_PATH_STR = _tmp.name
_tmp.close()

from database import db_manager as db
from auth import admin_auth as auth


class TestAdminAuth(unittest.TestCase):
    def setUp(self):
        db.init_db()
        # Clear admins
        with db.get_conn() as conn:
            conn.execute("DELETE FROM admin_users")
        auth._failed_attempts.clear()

    def test_needs_first_time_setup(self):
        self.assertTrue(auth.needs_first_time_setup())

    def test_setup_admin(self):
        ok, msg = auth.setup_admin("admin", "securepass123")
        self.assertTrue(ok)
        self.assertFalse(auth.needs_first_time_setup())

    def test_setup_admin_short_password(self):
        ok, msg = auth.setup_admin("admin", "short")
        self.assertFalse(ok)

    def test_setup_admin_short_username(self):
        ok, msg = auth.setup_admin("ab", "validpassword")
        self.assertFalse(ok)

    def test_duplicate_setup_fails(self):
        auth.setup_admin("admin", "securepass123")
        ok, msg = auth.setup_admin("admin2", "anotherpass")
        self.assertFalse(ok)

    def test_login_success(self):
        auth.setup_admin("admin", "correctpass!")
        ok, msg = auth.login("admin", "correctpass!")
        self.assertTrue(ok)

    def test_login_wrong_password(self):
        auth.setup_admin("admin", "correctpass!")
        ok, msg = auth.login("admin", "wrongpassword")
        self.assertFalse(ok)

    def test_login_nonexistent_user(self):
        ok, msg = auth.login("nobody", "password")
        self.assertFalse(ok)

    def test_lockout_after_max_attempts(self):
        auth.setup_admin("admin", "correctpass!")
        for _ in range(auth.MAX_ATTEMPTS):
            auth.login("admin", "wrong")
        ok, msg = auth.login("admin", "correctpass!")
        self.assertFalse(ok)
        self.assertIn("locked", msg.lower())

    def test_change_password(self):
        auth.setup_admin("admin", "oldpassword1")
        ok, msg = auth.change_password("admin", "oldpassword1", "newpassword2")
        self.assertTrue(ok)
        ok2, _ = auth.login("admin", "newpassword2")
        self.assertTrue(ok2)

    def test_change_password_wrong_current(self):
        auth.setup_admin("admin", "realpassword")
        ok, msg = auth.change_password("admin", "wrongcurrent", "newpassword")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
