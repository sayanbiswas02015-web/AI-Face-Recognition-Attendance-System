"""
ui/admin_dashboard.py
Admin dashboard with sidebar navigation — shown after successful login.
"""

import logging
import customtkinter as ctk
from datetime import datetime

from config import (
    COLOR_BG_DARK, COLOR_SIDEBAR, COLOR_ACCENT, COLOR_SUCCESS,
    COLOR_ERROR, COLOR_TEXT, COLOR_SUBTEXT, COLOR_CARD, COLOR_BORDER, APP_TITLE
)
from database import db_manager as db

logger = logging.getLogger(__name__)

NAV_ITEMS = [
    ("📊", "Overview"),
    ("👤", "Register Employee"),
    ("📋", "Employee Database"),
    ("📅", "Attendance Records"),
    ("📤", "Export Reports"),
    ("⚙️", "Settings"),
]


class AdminDashboard(ctk.CTkToplevel):
    def __init__(self, scanner_win, recognizer, username: str):
        super().__init__(scanner_win)
        self.scanner_win = scanner_win
        self.recognizer  = recognizer
        self.username    = username

        self.title(f"{APP_TITLE} — Admin Dashboard ({username})")
        self.geometry("1300x780")
        self.minsize(1100, 680)
        self.configure(fg_color=COLOR_BG_DARK)
        self.protocol("WM_DELETE_WINDOW", self._logout)

        self._active_page = None
        self._nav_btns: dict = {}
        self._content_frame = None

        self._build_layout()
        self._show_page("Overview")

    # ─── Layout ──────────────────────────────────────────────────────────────

    def _build_layout(self):
        # Sidebar
        self._sidebar = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR, width=220, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        ctk.CTkLabel(
            self._sidebar, text=f"🎯 Admin Panel",
            font=ctk.CTkFont(size=15, weight="bold"), text_color=COLOR_ACCENT
        ).pack(pady=(20, 4), padx=16, anchor="w")

        ctk.CTkLabel(
            self._sidebar, text=f"👤 {self.username}",
            font=ctk.CTkFont(size=11), text_color=COLOR_SUBTEXT
        ).pack(pady=(0, 16), padx=16, anchor="w")

        ctk.CTkFrame(self._sidebar, fg_color=COLOR_BORDER, height=1).pack(fill="x", padx=12, pady=(0, 10))

        for icon, label in NAV_ITEMS:
            btn = ctk.CTkButton(
                self._sidebar,
                text=f"  {icon}  {label}",
                anchor="w",
                fg_color="transparent",
                hover_color=COLOR_CARD,
                text_color=COLOR_TEXT,
                font=ctk.CTkFont(size=13),
                height=42,
                corner_radius=8,
                command=lambda l=label: self._show_page(l)
            )
            btn.pack(fill="x", padx=10, pady=2)
            self._nav_btns[label] = btn

        # Logout at bottom of sidebar
        ctk.CTkFrame(self._sidebar, fg_color=COLOR_BORDER, height=1).pack(fill="x", padx=12, pady=10, side="bottom")
        ctk.CTkButton(
            self._sidebar, text="  🚪  Logout", anchor="w",
            fg_color="transparent", hover_color="#3D0000",
            text_color=COLOR_ERROR, font=ctk.CTkFont(size=13),
            height=42, command=self._logout
        ).pack(fill="x", padx=10, pady=6, side="bottom")

        # Content area
        self._content_frame = ctk.CTkFrame(self, fg_color=COLOR_BG_DARK, corner_radius=0)
        self._content_frame.pack(side="right", fill="both", expand=True)

    def _cleanup_active_page(self):
        if self._content_frame:
            for child in self._content_frame.winfo_children():
                if hasattr(child, "stop_capture"):
                    try:
                        child.stop_capture()
                    except Exception:
                        pass

    # ─── Navigation ───────────────────────────────────────────────────────────

    def _show_page(self, label: str):
        # Stop any active capture on the current page before switching
        self._cleanup_active_page()

        # Highlight active button
        for lbl, btn in self._nav_btns.items():
            btn.configure(
                fg_color=COLOR_ACCENT if lbl == label else "transparent",
                text_color="#000000" if lbl == label else COLOR_TEXT,
            )

        # Clear content
        for w in self._content_frame.winfo_children():
            w.destroy()

        self._active_page = label

        if label == "Overview":
            self._page_overview()
        elif label == "Register Employee":
            self._page_register()
        elif label == "Employee Database":
            self._page_employees()
        elif label == "Attendance Records":
            self._page_attendance()
        elif label == "Export Reports":
            self._page_export()
        elif label == "Settings":
            self._page_settings()

    # ─── Overview Page ────────────────────────────────────────────────────────

    def _page_overview(self):
        p = self._content_frame
        ctk.CTkLabel(p, text="📊  Dashboard Overview",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COLOR_ACCENT).pack(anchor="w", padx=24, pady=(20, 12))

        stats = db.dashboard_stats()

        cards = ctk.CTkFrame(p, fg_color="transparent")
        cards.pack(fill="x", padx=20)
        for i, (label, value, color) in enumerate([
            ("Total Employees",   stats["total_employees"], COLOR_ACCENT),
            ("Present Today",     stats["present_today"],   COLOR_SUCCESS),
            ("Absent Today",      stats["absent_today"],    COLOR_ERROR),
            ("All-Time Records",  stats["total_records"],   COLOR_TEXT),
        ]):
            card = ctk.CTkFrame(cards, fg_color=COLOR_CARD, corner_radius=12)
            card.grid(row=0, column=i, padx=8, sticky="ew")
            cards.columnconfigure(i, weight=1)
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=11),
                         text_color=COLOR_SUBTEXT).pack(anchor="w", padx=14, pady=(10, 2))
            ctk.CTkLabel(card, text=str(value), font=ctk.CTkFont(size=30, weight="bold"),
                         text_color=color).pack(anchor="w", padx=14, pady=(0, 10))

        # Latest attendance
        ctk.CTkLabel(p, text="Latest Attendance Today",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COLOR_TEXT).pack(anchor="w", padx=24, pady=(24, 6))

        tbl = ctk.CTkScrollableFrame(p, fg_color=COLOR_CARD, corner_radius=12, height=200)
        tbl.pack(fill="x", padx=20)
        self._render_att_table(tbl, stats["latest_attendance"])

        # Recent employees
        ctk.CTkLabel(p, text="Recently Registered Employees",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COLOR_TEXT).pack(anchor="w", padx=24, pady=(20, 6))

        emp_tbl = ctk.CTkScrollableFrame(p, fg_color=COLOR_CARD, corner_radius=12, height=160)
        emp_tbl.pack(fill="x", padx=20)
        for row in stats["recent_employees"]:
            r = ctk.CTkFrame(emp_tbl, fg_color="transparent")
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=f"  {row['emp_id']}", width=120, font=ctk.CTkFont(size=11),
                         text_color=COLOR_SUBTEXT).pack(side="left")
            ctk.CTkLabel(r, text=row["name"], font=ctk.CTkFont(size=12),
                         text_color=COLOR_TEXT).pack(side="left", padx=8)
            status = "Active" if row["is_active"] else "Inactive"
            ctk.CTkLabel(r, text=status, font=ctk.CTkFont(size=10),
                         text_color=COLOR_SUCCESS if row["is_active"] else COLOR_ERROR
                         ).pack(side="right", padx=12)

    def _render_att_table(self, parent, rows):
        header = ctk.CTkFrame(parent, fg_color=COLOR_SIDEBAR)
        header.pack(fill="x", pady=(0, 2))
        for col, w in [("Date", 100), ("Time", 80), ("Name", 160), ("Emp ID", 100)]:
            ctk.CTkLabel(header, text=col, width=w, font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=COLOR_ACCENT).pack(side="left", padx=6, pady=4)

        if not rows:
            ctk.CTkLabel(parent, text="No records.", text_color=COLOR_SUBTEXT,
                         font=ctk.CTkFont(size=11)).pack(pady=12)
            return

        for row in rows:
            r = ctk.CTkFrame(parent, fg_color="transparent")
            r.pack(fill="x", pady=1)
            for val, w in [
                (row["attendance_date"], 100),
                (row["entry_time"],      80),
                (row["name"],            160),
                (row["emp_id"],          100),
            ]:
                ctk.CTkLabel(r, text=val, width=w, font=ctk.CTkFont(size=11),
                             text_color=COLOR_TEXT).pack(side="left", padx=6, pady=2)

    # ─── Register Employee Page ───────────────────────────────────────────────

    def _page_register(self):
        from ui.employee_management import RegisterEmployeePage
        RegisterEmployeePage(self._content_frame, self.recognizer, on_done=self._refresh_page)

    def _refresh_page(self):
        self._show_page(self._active_page)

    # ─── Employee Database Page ───────────────────────────────────────────────

    def _page_employees(self):
        from ui.employee_management import EmployeeDatabasePage
        EmployeeDatabasePage(self._content_frame, self.recognizer,
                             on_change=self._refresh_page)

    # ─── Attendance Records Page ──────────────────────────────────────────────

    def _page_attendance(self):
        from ui.attendance_records import AttendanceRecordsPage
        AttendanceRecordsPage(self._content_frame, admin_user=self.username)

    # ─── Export Reports Page ──────────────────────────────────────────────────

    def _page_export(self):
        from ui.attendance_records import ExportReportsPage
        ExportReportsPage(self._content_frame)

    # ─── Settings Page ────────────────────────────────────────────────────────

    def _page_settings(self):
        from ui.settings_window import SettingsPage
        SettingsPage(self._content_frame, username=self.username)

    # ─── Logout ───────────────────────────────────────────────────────────────

    def _logout(self):
        self._cleanup_active_page()
        db.audit(self.username, "LOGOUT")
        self.destroy()
        self.scanner_win.deiconify()
        if hasattr(self.scanner_win, "start_camera"):
            self.scanner_win.start_camera()
