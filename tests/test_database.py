"""
tests/test_database.py  — Database initialisation and CRUD tests
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sqlite3
import tempfile
import unittest
import numpy as np

# Point DB at a temp file for isolation
import config as _cfg
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_cfg.DB_PATH_STR = _tmp.name
_tmp.close()

from database import db_manager as db


class TestDatabaseInit(unittest.TestCase):
    def setUp(self):
        db.init_db()

    def test_tables_created(self):
        with db.get_conn() as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        for t in ["employees", "face_embeddings", "attendance", "admin_users"]:
            self.assertIn(t, tables, f"Missing table: {t}")

    def test_create_and_get_employee(self):
        db.create_employee("E001", "Alice")
        row = db.get_employee("E001")
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "Alice")

    def test_duplicate_employee_raises(self):
        db.create_employee("E002", "Bob")
        with self.assertRaises(Exception):
            db.create_employee("E002", "Bob Again")

    def test_employee_exists(self):
        db.create_employee("E003", "Carol")
        self.assertTrue(db.employee_exists("E003"))
        self.assertFalse(db.employee_exists("XXXX"))

    def test_delete_employee(self):
        db.create_employee("E004", "Dave")
        db.delete_employee_full("E004")
        self.assertIsNone(db.get_employee("E004"))

    def test_set_employee_active(self):
        db.create_employee("E005", "Eve")
        db.set_employee_active("E005", False)
        row = db.get_employee("E005")
        self.assertEqual(row["is_active"], 0)


class TestEmbeddings(unittest.TestCase):
    def setUp(self):
        db.init_db()
        try:
            db.create_employee("EMB1", "Frank")
        except Exception:
            pass

    def test_save_and_load_embeddings(self):
        emb = np.random.rand(512).astype(np.float32)
        db.save_embeddings("EMB1", [emb])
        gallery = db.load_all_embeddings()
        self.assertIn("EMB1", gallery)
        loaded = gallery["EMB1"][0]
        np.testing.assert_allclose(loaded, emb, atol=1e-6)

    def test_has_embeddings(self):
        emb = np.random.rand(512).astype(np.float32)
        db.save_embeddings("EMB1", [emb])
        self.assertTrue(db.has_embeddings("EMB1"))

    def test_delete_embeddings(self):
        emb = np.random.rand(512).astype(np.float32)
        db.save_embeddings("EMB1", [emb])
        db.delete_embeddings("EMB1")
        self.assertFalse(db.has_embeddings("EMB1"))

    def test_blob_roundtrip(self):
        arr = np.random.rand(512).astype(np.float32)
        blob = db.embedding_to_blob(arr)
        recovered = db.blob_to_embedding(blob)
        np.testing.assert_allclose(recovered, arr, atol=1e-6)


class TestAdminUsers(unittest.TestCase):
    def setUp(self):
        db.init_db()

    def test_create_admin(self):
        # may already exist; ignore
        try:
            db.create_admin("testadmin", "fakehash")
        except Exception:
            pass
        row = db.get_admin("testadmin")
        self.assertIsNotNone(row)
        self.assertEqual(row["username"], "testadmin")

    def test_count_admins(self):
        try:
            db.create_admin("testadmin2", "fakehash2")
        except Exception:
            pass
        self.assertGreaterEqual(db.count_admins(), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
