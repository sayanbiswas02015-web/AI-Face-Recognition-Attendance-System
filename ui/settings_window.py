"""
ui/settings_window.py
Application settings page in the admin dashboard.
"""

import customtkinter as ctk
from tkinter import messagebox

from auth.admin_auth import change_password
from config import (
    COLOR_ACCENT, COLOR_BG_DARK, COLOR_CARD, COLOR_ERROR,
    COLOR_SIDEBAR, COLOR_SUBTEXT, COLOR_SUCCESS, COLOR_TEXT,
    RECOGNITION_THRESHOLD, RECOGNITION_COOLDOWN, CAMERA_INDEX, TIMEZONE
)
from database import db_manager as db


class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, username: str):
        super().__init__(parent, fg_color=COLOR_BG_DARK)
        self.pack(fill="both", expand=True)
        self.username = username
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="⚙️  Settings",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COLOR_ACCENT).pack(anchor="w", padx=24, pady=(20, 12))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        # ── Camera Settings ────────────────────────────────────────────────────
        self._section(scroll, "📷  Camera Settings")

        cam_frame = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=10)
        cam_frame.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(cam_frame, text="Camera Device Index",
                     text_color=COLOR_TEXT, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(12, 2))
        self._cam_idx = ctk.CTkEntry(cam_frame, height=34)
        self._cam_idx.insert(0, db.get_setting("camera_index", str(CAMERA_INDEX)))
        self._cam_idx.pack(fill="x", padx=16, pady=(0, 12))

        # ── Recognition Settings ──────────────────────────────────────────────
        self._section(scroll, "🧠  Recognition Settings")

        rec_frame = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=10)
        rec_frame.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(rec_frame, text="Recognition Threshold (0.1 – 1.0)",
                     text_color=COLOR_TEXT, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(rec_frame,
                     text="Higher = stricter matching. Default: 0.55",
                     text_color=COLOR_SUBTEXT, font=ctk.CTkFont(size=10)).pack(anchor="w", padx=16, pady=(0, 4))
        self._threshold = ctk.CTkEntry(rec_frame, height=34)
        self._threshold.insert(0, db.get_setting("recognition_threshold", str(RECOGNITION_THRESHOLD)))
        self._threshold.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(rec_frame, text="Recognition Cooldown (seconds)",
                     text_color=COLOR_TEXT, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(4, 2))
        self._cooldown = ctk.CTkEntry(rec_frame, height=34)
        self._cooldown.insert(0, db.get_setting("recognition_cooldown", str(RECOGNITION_COOLDOWN)))
        self._cooldown.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(rec_frame, text="Timezone (e.g. Asia/Kolkata)",
                     text_color=COLOR_TEXT, font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(4, 2))
        self._tz = ctk.CTkEntry(rec_frame, height=34)
        self._tz.insert(0, db.get_setting("timezone", TIMEZONE))
        self._tz.pack(fill="x", padx=16, pady=(0, 12))

        self._lbl_rec_msg = ctk.CTkLabel(rec_frame, text="", font=ctk.CTkFont(size=11))
        self._lbl_rec_msg.pack(pady=4)
        ctk.CTkButton(rec_frame, text="💾  Save Recognition Settings",
                      fg_color=COLOR_ACCENT, text_color="#000000",
                      height=36, command=self._save_rec_settings).pack(padx=16, pady=(0, 12))

        # ── Database Location ─────────────────────────────────────────────────
        self._section(scroll, "🗄️  Database")

        db_frame = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=10)
        db_frame.pack(fill="x", pady=(0, 12))

        from config import DB_PATH_STR
        ctk.CTkLabel(db_frame, text=f"Location: {DB_PATH_STR}",
                     text_color=COLOR_SUBTEXT, font=ctk.CTkFont(size=11),
                     wraplength=600).pack(anchor="w", padx=16, pady=14)

        # ── Change Password ───────────────────────────────────────────────────
        self._section(scroll, "🔑  Change Admin Password")

        pw_frame = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=10)
        pw_frame.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(pw_frame, text="Current Password", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(12, 2))
        self._cur_pw = ctk.CTkEntry(pw_frame, show="•", height=34)
        self._cur_pw.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(pw_frame, text="New Password (min 8 chars)", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(4, 2))
        self._new_pw = ctk.CTkEntry(pw_frame, show="•", height=34)
        self._new_pw.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(pw_frame, text="Confirm New Password", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(4, 2))
        self._conf_pw = ctk.CTkEntry(pw_frame, show="•", height=34)
        self._conf_pw.pack(fill="x", padx=16, pady=(0, 8))

        self._lbl_pw_msg = ctk.CTkLabel(pw_frame, text="", font=ctk.CTkFont(size=11))
        self._lbl_pw_msg.pack(pady=4)
        ctk.CTkButton(pw_frame, text="🔑  Change Password",
                      fg_color=COLOR_ERROR, text_color="#ffffff",
                      height=36, command=self._change_pw).pack(padx=16, pady=(0, 12))

    def _section(self, parent, title: str):
        ctk.CTkLabel(parent, text=title,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COLOR_TEXT).pack(anchor="w", pady=(16, 4))

    def _save_rec_settings(self):
        try:
            thr = float(self._threshold.get())
            if not (0.1 <= thr <= 1.0):
                raise ValueError("Threshold out of range")
            cool = int(self._cooldown.get())
            tz   = self._tz.get().strip()
            cam  = int(self._cam_idx.get())
        except ValueError as e:
            self._lbl_rec_msg.configure(text=f"❌ Invalid value: {e}", text_color=COLOR_ERROR)
            return

        db.set_setting("recognition_threshold", str(thr))
        db.set_setting("recognition_cooldown",  str(cool))
        db.set_setting("timezone",              tz)
        db.set_setting("camera_index",          str(cam))
        db.audit(self.username, "SETTINGS_UPDATED")
        self._lbl_rec_msg.configure(
            text="✅ Settings saved. Restart the app to apply camera changes.",
            text_color=COLOR_SUCCESS
        )

    def _change_pw(self):
        cur  = self._cur_pw.get()
        new  = self._new_pw.get()
        conf = self._conf_pw.get()
        if new != conf:
            self._lbl_pw_msg.configure(text="❌ New passwords do not match.", text_color=COLOR_ERROR)
            return
        ok, msg = change_password(self.username, cur, new)
        color = COLOR_SUCCESS if ok else COLOR_ERROR
        self._lbl_pw_msg.configure(text=("✅ " if ok else "❌ ") + msg, text_color=color)
        if ok:
            self._cur_pw.delete(0, "end")
            self._new_pw.delete(0, "end")
            self._conf_pw.delete(0, "end")
