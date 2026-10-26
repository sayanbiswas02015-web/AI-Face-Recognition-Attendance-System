"""
main.py — AI Face Attendance System entry point.

Startup sequence:
1. Configure logging
2. Initialise the database
3. Load face recognizer and gallery from DB
4. Launch the live scanner window
"""

import logging
import logging.handlers
import sys
import os

# ─── Ensure project root is on the path ──────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from config import LOG_FILE, DB_PATH_STR, RECOGNITION_COOLDOWN


def _configure_logging():
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s: %(message)s"
    ))
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(logging.Formatter("%(levelname)-8s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, stream])


def main():
    _configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== AI Face Attendance System starting ===")

    # ── Phase 1: Database ────────────────────────────────────────────────────
    from database import db_manager as db
    try:
        db.init_db()
        logger.info("Database ready: %s", DB_PATH_STR)
    except Exception as exc:
        logger.critical("Database init failed: %s", exc)
        sys.exit(1)

    # ── Phase 2: Face Recognizer ─────────────────────────────────────────────
    from recognition.face_recognizer import FaceRecognizer
    logger.info("Loading face recognition model…")
    try:
        recognizer = FaceRecognizer()
        logger.info("Recognizer backend: %s", recognizer.backend_name)
    except Exception as exc:
        logger.critical("Recognizer init failed: %s", exc)
        sys.exit(1)

    # ── Phase 3: Load gallery from DB ────────────────────────────────────────
    try:
        gallery = db.load_all_embeddings()
        recognizer.load_gallery(gallery)
        logger.info("Gallery loaded: %d employee(s)", len(gallery))
    except Exception as exc:
        logger.error("Gallery load failed (non-fatal): %s", exc)

    # ── Phase 4: Attendance service ──────────────────────────────────────────
    from attendance.attendance_service import AttendanceService
    attendance_service = AttendanceService(cooldown_seconds=int(
        db.get_setting("recognition_cooldown", str(RECOGNITION_COOLDOWN))
    ))

    # ── Phase 5: Launch UI ───────────────────────────────────────────────────
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    from ui.scanner_window import ScannerWindow
    logger.info("Launching scanner window…")
    app = ScannerWindow(recognizer=recognizer, attendance_service=attendance_service)
    app.mainloop()

    logger.info("Application exited cleanly.")


if __name__ == "__main__":
    main()
