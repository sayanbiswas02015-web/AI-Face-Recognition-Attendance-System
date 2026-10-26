"""
ui/attendance_records.py
Attendance Records page and Export Reports page for the admin dashboard.
"""

import logging
from datetime import datetime, date
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from config import (
    COLOR_ACCENT, COLOR_BG_DARK, COLOR_CARD, COLOR_ERROR,
    COLOR_SIDEBAR, COLOR_SUBTEXT, COLOR_SUCCESS, COLOR_TEXT
)
from database import db_manager as db
from attendance.report_export import export_to_csv, export_to_excel

logger = logging.getLogger(__name__)

PAGE_SIZE = 50


class AttendanceRecordsPage(ctk.CTkFrame):
    def __init__(self, parent, admin_user: str = "admin"):
        super().__init__(parent, fg_color=COLOR_BG_DARK)
        self.pack(fill="both", expand=True)
        self.admin_user = admin_user
        self._offset    = 0
        self._total     = 0
        self._build()
        self._refresh()

    def _build(self):
        ctk.CTkLabel(self, text="📅  Attendance Records",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COLOR_ACCENT).pack(anchor="w", padx=24, pady=(20, 8))

        # ── Filter bar ────────────────────────────────────────────────────────
        fb = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR, corner_radius=10)
        fb.pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkLabel(fb, text="Employee ID:", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(12, 4), pady=10)
        self._f_emp = ctk.CTkEntry(fb, placeholder_text="EMP001", width=100, height=32)
        self._f_emp.grid(row=0, column=1, padx=4)

        ctk.CTkLabel(fb, text="Name:", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=2, padx=(12, 4))
        self._f_name = ctk.CTkEntry(fb, placeholder_text="Search name", width=130, height=32)
        self._f_name.grid(row=0, column=3, padx=4)

        ctk.CTkLabel(fb, text="Date From:", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=4, padx=(12, 4))
        self._f_from = ctk.CTkEntry(fb, placeholder_text="YYYY-MM-DD", width=110, height=32)
        self._f_from.grid(row=0, column=5, padx=4)

        ctk.CTkLabel(fb, text="To:", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=6, padx=(8, 4))
        self._f_to = ctk.CTkEntry(fb, placeholder_text="YYYY-MM-DD", width=110, height=32)
        self._f_to.grid(row=0, column=7, padx=4)

        ctk.CTkButton(fb, text="Today", width=64, height=32,
                      fg_color=COLOR_ACCENT, text_color="#000000",
                      command=self._set_today).grid(row=0, column=8, padx=4)
        ctk.CTkButton(fb, text="🔍 Filter", width=80, height=32,
                      fg_color=COLOR_ACCENT, text_color="#000000",
                      command=self._search).grid(row=0, column=9, padx=4)
        ctk.CTkButton(fb, text="Clear", width=60, height=32,
                      fg_color=COLOR_SIDEBAR, text_color=COLOR_TEXT,
                      command=self._clear_filters).grid(row=0, column=10, padx=(4, 12))

        # ── Summary ───────────────────────────────────────────────────────────
        self._lbl_summary = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=11), text_color=COLOR_SUBTEXT
        )
        self._lbl_summary.pack(anchor="w", padx=24, pady=(4, 4))

        # ── Table header ──────────────────────────────────────────────────────
        thead = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR)
        thead.pack(fill="x", padx=20, pady=(0, 2))
        for col, w in [("Date", 110), ("Time", 90), ("Name", 180), ("Emp ID", 110), ("", 80)]:
            ctk.CTkLabel(thead, text=col, width=w,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=COLOR_ACCENT).pack(side="left", padx=6, pady=6)

        # ── Rows ─────────────────────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=COLOR_CARD, corner_radius=10)
        self._scroll.pack(fill="both", expand=True, padx=20, pady=(0, 4))

        # ── Pagination ────────────────────────────────────────────────────────
        pag = ctk.CTkFrame(self, fg_color="transparent")
        pag.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkButton(pag, text="◀ Prev", width=80, height=30,
                      command=self._prev_page).pack(side="left", padx=4)
        self._lbl_page = ctk.CTkLabel(pag, text="Page 1", text_color=COLOR_TEXT,
                                      font=ctk.CTkFont(size=11))
        self._lbl_page.pack(side="left", padx=8)
        ctk.CTkButton(pag, text="Next ▶", width=80, height=30,
                      command=self._next_page).pack(side="left", padx=4)
        ctk.CTkButton(pag, text="🔄 Refresh", width=90, height=30,
                      fg_color=COLOR_SIDEBAR, text_color=COLOR_TEXT,
                      command=self._refresh).pack(side="right", padx=4)

    # ── Filter helpers ────────────────────────────────────────────────────────

    def _set_today(self):
        today = date.today().isoformat()
        self._f_from.delete(0, "end"); self._f_from.insert(0, today)
        self._f_to.delete(0, "end");   self._f_to.insert(0, today)
        self._search()

    def _clear_filters(self):
        for e in [self._f_emp, self._f_name, self._f_from, self._f_to]:
            e.delete(0, "end")
        self._offset = 0
        self._refresh()

    def _search(self):
        self._offset = 0
        self._refresh()

    def _refresh(self):
        emp   = self._f_emp.get().strip() or None
        name  = self._f_name.get().strip() or None
        dfrom = self._f_from.get().strip() or None
        dto   = self._f_to.get().strip() or None

        rows, total = db.get_attendance_filtered(dfrom, dto, emp, name, PAGE_SIZE, self._offset)
        self._total = total

        # clear
        for w in self._scroll.winfo_children():
            w.destroy()

        if not rows:
            ctk.CTkLabel(self._scroll, text="No records match the filters.",
                         text_color=COLOR_SUBTEXT, font=ctk.CTkFont(size=12)).pack(pady=20)
        else:
            for row in rows:
                self._render_row(row)

        page = self._offset // PAGE_SIZE + 1
        max_page = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self._lbl_page.configure(text=f"Page {page} / {max_page}")
        self._lbl_summary.configure(
            text=f"Total records: {total}   |   Showing {self._offset+1}–{min(self._offset+PAGE_SIZE, total)}"
        )

    def _render_row(self, row):
        r = ctk.CTkFrame(self._scroll, fg_color=COLOR_SIDEBAR, corner_radius=6)
        r.pack(fill="x", pady=2, padx=2)
        for val, w in [
            (row["attendance_date"], 110),
            (row["entry_time"],       90),
            (row["name"],            180),
            (row["emp_id"],          110),
        ]:
            ctk.CTkLabel(r, text=val, width=w, font=ctk.CTkFont(size=11),
                         text_color=COLOR_TEXT).pack(side="left", padx=6, pady=5)

        ctk.CTkButton(
            r, text="🗑", width=36, height=26,
            fg_color="#550000", text_color=COLOR_ERROR,
            font=ctk.CTkFont(size=11),
            command=lambda rid=row["id"]: self._delete_record(rid)
        ).pack(side="right", padx=6, pady=3)

    def _delete_record(self, record_id: int):
        if not messagebox.askyesno("Delete Record",
                                   f"Delete attendance record #{record_id}?\n"
                                   "This action is logged and cannot be undone."):
            return
        db.delete_attendance_record(record_id)
        db.audit(self.admin_user, "ATTENDANCE_DELETED", f"record_id={record_id}")
        self._refresh()

    def _prev_page(self):
        if self._offset >= PAGE_SIZE:
            self._offset -= PAGE_SIZE
            self._refresh()

    def _next_page(self):
        if self._offset + PAGE_SIZE < self._total:
            self._offset += PAGE_SIZE
            self._refresh()


# ─── Export Reports Page ─────────────────────────────────────────────────────

class ExportReportsPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=COLOR_BG_DARK)
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="📤  Export Reports",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COLOR_ACCENT).pack(anchor="w", padx=24, pady=(20, 12))

        body = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12)
        body.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(body, text="Filters (optional)",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=COLOR_TEXT).pack(anchor="w", padx=16, pady=(14, 6))

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", padx=16)

        ctk.CTkLabel(row, text="Emp ID:", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(0, 4), pady=6)
        self._f_emp = ctk.CTkEntry(row, placeholder_text="All", width=90, height=32)
        self._f_emp.grid(row=0, column=1, padx=4)

        ctk.CTkLabel(row, text="Name:", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=2, padx=(12, 4))
        self._f_name = ctk.CTkEntry(row, placeholder_text="All", width=120, height=32)
        self._f_name.grid(row=0, column=3, padx=4)

        ctk.CTkLabel(row, text="Date From:", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=4, padx=(12, 4))
        self._f_from = ctk.CTkEntry(row, placeholder_text="YYYY-MM-DD", width=110, height=32)
        self._f_from.grid(row=0, column=5, padx=4)

        ctk.CTkLabel(row, text="To:", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=6, padx=(8, 4))
        self._f_to = ctk.CTkEntry(row, placeholder_text="YYYY-MM-DD", width=110, height=32)
        self._f_to.grid(row=0, column=7, padx=(4, 0))

        # Today shortcut
        ctk.CTkButton(body, text="Set Today's Date",
                      fg_color=COLOR_SIDEBAR, text_color=COLOR_TEXT,
                      height=30, command=self._set_today).pack(anchor="w", padx=16, pady=(6, 12))

        ctk.CTkFrame(body, fg_color=COLOR_SIDEBAR, height=1).pack(fill="x", padx=16, pady=4)

        self._lbl_msg = ctk.CTkLabel(body, text="", font=ctk.CTkFont(size=11))
        self._lbl_msg.pack(pady=4)

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(pady=(4, 16))

        ctk.CTkButton(
            btn_row, text="⬇  Export CSV",
            fg_color=COLOR_SUCCESS, text_color="#000000",
            font=ctk.CTkFont(weight="bold"), height=40, width=160,
            command=self._export_csv
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_row, text="⬇  Export Excel (.xlsx)",
            fg_color=COLOR_ACCENT, text_color="#000000",
            font=ctk.CTkFont(weight="bold"), height=40, width=180,
            command=self._export_excel
        ).pack(side="left", padx=8)

    def _set_today(self):
        today = date.today().isoformat()
        self._f_from.delete(0, "end"); self._f_from.insert(0, today)
        self._f_to.delete(0, "end");   self._f_to.insert(0, today)

    def _filters(self):
        return {
            "emp_id":    self._f_emp.get().strip() or None,
            "name_like": self._f_name.get().strip() or None,
            "date_from": self._f_from.get().strip() or None,
            "date_to":   self._f_to.get().strip() or None,
        }

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile=f"attendance_{date.today().isoformat()}.csv"
        )
        if not path:
            return
        f = self._filters()
        ok, msg = export_to_csv(path, f["date_from"], f["date_to"], f["emp_id"], f["name_like"])
        color = COLOR_SUCCESS if ok else COLOR_ERROR
        self._lbl_msg.configure(text=msg, text_color=color)

    def _export_excel(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
            initialfile=f"attendance_{date.today().isoformat()}.xlsx"
        )
        if not path:
            return
        f = self._filters()
        ok, msg = export_to_excel(path, f["date_from"], f["date_to"], f["emp_id"], f["name_like"])
        color = COLOR_SUCCESS if ok else COLOR_ERROR
        self._lbl_msg.configure(text=msg, text_color=color)
