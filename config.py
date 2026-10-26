"""
config.py - Central configuration for AI Face Attendance System
"""
import os
from pathlib import Path

# ─── Base Paths ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ─── Database ─────────────────────────────────────────────────────────────────
DB_PATH = DATA_DIR / "attendance.db"
DB_PATH_STR = str(DB_PATH)

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

# ─── Face Recognition ─────────────────────────────────────────────────────────
RECOGNITION_THRESHOLD = 0.55      # cosine similarity threshold (0–1); higher = stricter
FACE_DETECTION_CONFIDENCE = 0.85  # minimum detector confidence
MIN_FACE_SAMPLES = 5              # samples collected during registration
RECOGNITION_COOLDOWN = 30         # seconds between repeated recognition events
EMBEDDING_DIM = 512               # InsightFace ArcFace embedding dimension

# ─── Camera ───────────────────────────────────────────────────────────────────
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# ─── Attendance ───────────────────────────────────────────────────────────────
ATTENDANCE_POLICY = "single_per_day"   # "single_per_day" | "checkin_checkout"
TIMEZONE = "Asia/Kolkata"              # local timezone name

# ─── Security ─────────────────────────────────────────────────────────────────
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 300   # seconds

# ─── UI ───────────────────────────────────────────────────────────────────────
APP_TITLE = "AI FACE ATTENDANCE SYSTEM"
WINDOW_MIN_W = 1200
WINDOW_MIN_H = 700

# ─── Colours ──────────────────────────────────────────────────────────────────
COLOR_BG_DARK   = "#0D1B2A"   # deep navy background
COLOR_SIDEBAR   = "#1B2A3B"   # sidebar navy
COLOR_ACCENT    = "#00D4AA"   # teal accent
COLOR_SUCCESS   = "#00C853"   # green
COLOR_ERROR     = "#FF1744"   # red
COLOR_WARNING   = "#FFC107"   # amber
COLOR_TEXT      = "#E0E6ED"   # light text
COLOR_SUBTEXT   = "#8899AA"   # muted text
COLOR_CARD      = "#1E3048"   # card background
COLOR_BORDER    = "#2C3E50"   # borders

# ─── Export ───────────────────────────────────────────────────────────────────
EXPORT_DIR = DATA_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)
