-- AI Face Attendance System — SQLite Schema
-- This file is for documentation; actual table creation is done by db_manager.py

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS employees (
    emp_id      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS face_embeddings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_id      TEXT    NOT NULL,
    embedding   BLOB    NOT NULL,
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (emp_id) REFERENCES employees(emp_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS attendance (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    attendance_date TEXT    NOT NULL,
    entry_time      TEXT    NOT NULL,
    name            TEXT    NOT NULL,
    emp_id          TEXT    NOT NULL,
    UNIQUE (emp_id, attendance_date)
);

CREATE TABLE IF NOT EXISTS admin_users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    actor       TEXT    NOT NULL,
    action      TEXT    NOT NULL,
    details     TEXT
);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_face_emp ON face_embeddings(emp_id);
CREATE INDEX IF NOT EXISTS idx_att_date ON attendance(attendance_date);
CREATE INDEX IF NOT EXISTS idx_att_emp  ON attendance(emp_id);
