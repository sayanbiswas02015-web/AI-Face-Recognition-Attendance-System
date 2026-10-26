"""
ui/employee_management.py
Register Employee and Employee Database pages for the admin dashboard.
"""

import logging
import threading
import time
import cv2
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image, ImageTk
from typing import Optional

from config import (
    CAMERA_INDEX, COLOR_ACCENT, COLOR_BG_DARK, COLOR_CARD,
    COLOR_ERROR, COLOR_SUCCESS, COLOR_SIDEBAR, COLOR_SUBTEXT,
    COLOR_TEXT, MIN_FACE_SAMPLES
)
from database import db_manager as db
from recognition.face_registration import RegistrationCapture
from recognition.camera_service import CameraService

logger = logging.getLogger(__name__)


class RegisterEmployeePage(ctk.CTkFrame):
    def __init__(self, parent, recognizer, on_done=None):
        super().__init__(parent, fg_color=COLOR_BG_DARK)
        self.pack(fill="both", expand=True)
        self.recognizer = recognizer
        self.on_done    = on_done
        self._cap: Optional[cv2.VideoCapture] = None
        self._capture: Optional[RegistrationCapture] = None
        self._running_camera = False
        self._thread: Optional[threading.Thread] = None
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="👤  Register New Employee",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COLOR_ACCENT).pack(anchor="w", padx=24, pady=(20, 12))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        # ── Form ─────────────────────────────────────────────────────────────
        form = ctk.CTkFrame(body, fg_color=COLOR_CARD, corner_radius=12)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=4)

        ctk.CTkLabel(form, text="Employee Details",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COLOR_TEXT).pack(anchor="w", padx=16, pady=(16, 8))

        ctk.CTkLabel(form, text="Employee ID *", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(4, 2))
        self._entry_id = ctk.CTkEntry(form, placeholder_text="e.g. EMP001", height=38)
        self._entry_id.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(form, text="Full Name *", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(4, 2))
        self._entry_name = ctk.CTkEntry(form, placeholder_text="e.g. Jane Doe", height=38)
        self._entry_name.pack(fill="x", padx=16, pady=(0, 16))

        self._lbl_status = ctk.CTkLabel(form, text="", font=ctk.CTkFont(size=11))
        self._lbl_status.pack(pady=6)

        self._progress = ctk.CTkProgressBar(form, mode="determinate")
        self._progress.set(0)
        self._progress.pack(fill="x", padx=16, pady=(0, 8))

        self._lbl_progress = ctk.CTkLabel(form, text=f"Samples: 0/{MIN_FACE_SAMPLES}",
                                          text_color=COLOR_SUBTEXT, font=ctk.CTkFont(size=11))
        self._lbl_progress.pack(pady=(0, 8))

        btn_box = ctk.CTkFrame(form, fg_color="transparent")
        btn_box.pack(fill="x", padx=16, pady=(0, 8))
        btn_box.columnconfigure((0, 1), weight=1)

        self._btn_capture = ctk.CTkButton(
            btn_box, text="📷  Start Capture",
            fg_color=COLOR_ACCENT, hover_color="#00A882",
            text_color="#000000", font=ctk.CTkFont(weight="bold"),
            height=40, command=self._start_capture
        )
        self._btn_capture.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self._btn_stop = ctk.CTkButton(
            btn_box, text="⏹  Stop",
            fg_color="#441111", hover_color="#661111",
            text_color="#FF6666", font=ctk.CTkFont(weight="bold"),
            height=40, command=self.stop_capture, state="disabled"
        )
        self._btn_stop.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        ctk.CTkButton(
            form, text="✅  Save Employee",
            fg_color=COLOR_SUCCESS, hover_color="#00A050",
            text_color="#000000", font=ctk.CTkFont(weight="bold"),
            height=40, command=self._save_employee
        ).pack(fill="x", padx=16, pady=(0, 16))

        # ── Camera preview ────────────────────────────────────────────────────
        cam_frame = ctk.CTkFrame(body, fg_color=COLOR_CARD, corner_radius=12)
        cam_frame.grid(row=0, column=1, sticky="nsew", pady=4)

        ctk.CTkLabel(cam_frame, text="Face Capture Preview",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COLOR_TEXT).pack(anchor="w", padx=16, pady=(16, 8))

        self._cam_canvas = ctk.CTkCanvas(cam_frame, width=400, height=300, bg="#000000",
                                         highlightthickness=0)
        self._cam_canvas.pack(padx=16, pady=(0, 8))

        self._lbl_instructions = ctk.CTkLabel(
            cam_frame,
            text="Click 'Start Capture' to begin.\nLook straight at the camera,\nthen slightly adjust angle or smile.",
            text_color=COLOR_SUBTEXT, font=ctk.CTkFont(size=11), justify="center"
        )
        self._lbl_instructions.pack(pady=(0, 16))

        # saved embeddings
        self._captured_embeddings = []
        self._previewing = True
        self._running_camera = False
        self._capture = None
        self._camera_service = CameraService.get_instance()
        self._start_preview()

    # ── Camera capture flow ───────────────────────────────────────────────────

    def _start_preview(self):
        """Start gentle preview stream so user can position themselves before capturing."""
        self._camera_service.start(timeout_sec=4.0)
        self._tick_preview()

    def _tick_preview(self):
        if not self._previewing:
            return
        if not self._running_camera:
            ret, frame = self._camera_service.read_frame()
            if ret and frame is not None:
                display = frame.copy()
                fh, fw = display.shape[:2]
                cx, cy = fw // 2, fh // 2
                cv2.rectangle(display, (cx - 100, cy - 130), (cx + 100, cy + 130), (0, 200, 150), 1, cv2.LINE_AA)
                cv2.putText(display, "Position face in box, then click Start Capture", (12, fh - 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 220, 200), 1)
                self._draw_canvas(display)
        if self._previewing:
            self.after(40, self._tick_preview)

    def _draw_canvas(self, bgr_frame):
        if bgr_frame is None:
            return
        try:
            rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            cw = self._cam_canvas.winfo_width()
            ch = self._cam_canvas.winfo_height()
            if cw < 50 or ch < 50:
                cw, ch = 400, 300
            fw, fh = bgr_frame.shape[1], bgr_frame.shape[0]
            scale = min(cw / fw, ch / fh)
            nw, nh = max(1, int(fw * scale)), max(1, int(fh * scale))
            img = Image.fromarray(rgb).resize((nw, nh), Image.BILINEAR)
            tk_img = ImageTk.PhotoImage(img)
            self._cam_canvas.delete("all")
            pos_x = (cw - nw) // 2
            pos_y = (ch - nh) // 2
            self._cam_canvas.create_image(pos_x, pos_y, anchor="nw", image=tk_img)
            self._cam_canvas._img = tk_img
        except Exception:
            pass

    def stop_capture(self):
        """Cancel capture and release camera immediately."""
        self._running_camera = False
        self._previewing = False
        if self._capture:
            self._capture.stop()
        self._btn_capture.configure(state="normal", text="📷  Start Capture")
        self._btn_stop.configure(state="disabled")
        self._set_status("Capture stopped.", COLOR_SUBTEXT)

    def _start_capture(self):
        emp_id = self._entry_id.get().strip()
        name   = self._entry_name.get().strip()
        if not emp_id or not name:
            self._set_status("⚠️  Please fill in Employee ID and Name first.", COLOR_ERROR)
            return

        self._captured_embeddings = []
        self._progress.set(0)
        self._lbl_progress.configure(text=f"Samples: 0/{MIN_FACE_SAMPLES}")
        self._btn_capture.configure(state="disabled", text="Capturing…")
        self._btn_stop.configure(state="normal")
        self._set_status("📷  Capturing — look at the camera.", COLOR_ACCENT)

        self._running_camera = True
        self._thread = threading.Thread(target=self._run_capture, daemon=True)
        self._thread.start()

    def _run_capture(self):
        """Runs in background: captures samples from CameraService without opening hardware."""
        self._camera_service.start(timeout_sec=4.0)

        self._capture = RegistrationCapture(self.recognizer, self._camera_service)
        embs, msg = self._capture.collect(
            progress_cb=self._on_progress,
            frame_cb=self._on_frame,
        )

        self._captured_embeddings = embs
        self._running_camera = False
        self.after(0, lambda: self._capture_done(embs, msg))

    def _on_progress(self, done, total, msg):
        self.after(0, lambda: (
            self._progress.set(done / total),
            self._lbl_progress.configure(text=f"Samples: {done}/{total}"),
            self._set_status(msg, COLOR_SUCCESS if done > 0 else COLOR_SUBTEXT),
        ))

    def _on_frame(self, bgr):
        self.after(0, lambda f=bgr: self._draw_canvas(f))

    def _capture_done(self, embs, msg):
        self._btn_capture.configure(state="normal", text="📷  Start Capture")
        self._btn_stop.configure(state="disabled")
        if len(embs) >= MIN_FACE_SAMPLES:
            self._set_status(f"✅  {msg} ({len(embs)} samples)", COLOR_SUCCESS)
        else:
            self._set_status(f"⚠️  Only {len(embs)} samples captured.", COLOR_ERROR)

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save_employee(self):
        emp_id = self._entry_id.get().strip().upper()
        name   = self._entry_name.get().strip()

        if not emp_id or not name:
            self._set_status("⚠️  Employee ID and Name are required.", COLOR_ERROR)
            return
        if not self._captured_embeddings:
            self._set_status("⚠️  Please capture face samples first.", COLOR_ERROR)
            return
        if len(self._captured_embeddings) < MIN_FACE_SAMPLES:
            if not messagebox.askyesno(
                "Insufficient Samples",
                f"Only {len(self._captured_embeddings)} of {MIN_FACE_SAMPLES} samples captured.\n"
                "Registration quality may be lower. Continue anyway?"
            ):
                return

        if db.employee_exists(emp_id):
            overwrite = messagebox.askyesno(
                "Employee Already Exists",
                f"Employee '{emp_id}' already exists.\n"
                "Update their face registration? Attendance history will be preserved."
            )
            if not overwrite:
                return
        else:
            try:
                db.create_employee(emp_id, name)
            except Exception as exc:
                self._set_status(f"❌  {exc}", COLOR_ERROR)
                return

        try:
            db.save_embeddings(emp_id, self._captured_embeddings)
            self.recognizer.add_to_gallery(emp_id, self._captured_embeddings)
            db.audit("admin", "EMPLOYEE_REGISTERED", f"emp_id={emp_id}")
            self._set_status(f"✅  Employee '{name}' registered successfully!", COLOR_SUCCESS)
            self._entry_id.delete(0, "end")
            self._entry_name.delete(0, "end")
            self._captured_embeddings = []
            self._progress.set(0)
            self._lbl_progress.configure(text=f"Samples: 0/{MIN_FACE_SAMPLES}")
            if self.on_done:
                self.after(1500, self.on_done)
        except Exception as exc:
            self._set_status(f"❌  {exc}", COLOR_ERROR)

    def _set_status(self, msg, color=COLOR_TEXT):
        self.after(0, lambda: self._lbl_status.configure(text=msg, text_color=color))


# ─── Employee Database Page ───────────────────────────────────────────────────

class EmployeeDatabasePage(ctk.CTkFrame):
    def __init__(self, parent, recognizer, on_change=None):
        super().__init__(parent, fg_color=COLOR_BG_DARK)
        self.pack(fill="both", expand=True)
        self.recognizer = recognizer
        self.on_change  = on_change
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 8))
        ctk.CTkLabel(hdr, text="📋  Employee Database",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COLOR_ACCENT).pack(side="left")
        ctk.CTkButton(hdr, text="🔄 Refresh", fg_color=COLOR_SIDEBAR,
                      text_color=COLOR_TEXT, height=32,
                      command=self._refresh).pack(side="right")

        # Header row
        header = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR)
        header.pack(fill="x", padx=20, pady=(0, 4))
        for txt, w in [("Emp ID", 110), ("Name", 200), ("Registered", 160),
                       ("Status", 80), ("Has Face", 80), ("", 220)]:
            ctk.CTkLabel(header, text=txt, width=w,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=COLOR_ACCENT).pack(side="left", padx=6, pady=6)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=COLOR_CARD, corner_radius=12)
        self._scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self._refresh()

    def _refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        employees = db.list_employees()
        if not employees:
            ctk.CTkLabel(self._scroll, text="No employees registered.",
                         text_color=COLOR_SUBTEXT, font=ctk.CTkFont(size=12)).pack(pady=20)
            return
        for emp in employees:
            self._render_row(emp)

    def _render_row(self, emp):
        row = ctk.CTkFrame(self._scroll, fg_color=COLOR_SIDEBAR, corner_radius=8)
        row.pack(fill="x", padx=4, pady=3)

        has_face = db.has_embeddings(emp["emp_id"])
        status_color = COLOR_SUCCESS if emp["is_active"] else COLOR_ERROR
        status_txt   = "Active" if emp["is_active"] else "Inactive"
        face_txt     = "✅ Yes" if has_face else "❌ No"

        for val, w in [
            (emp["emp_id"],    110),
            (emp["name"],      200),
            (emp["created_at"][:10], 160),
        ]:
            ctk.CTkLabel(row, text=val, width=w, font=ctk.CTkFont(size=11),
                         text_color=COLOR_TEXT).pack(side="left", padx=6, pady=6)

        ctk.CTkLabel(row, text=status_txt, width=80, font=ctk.CTkFont(size=11),
                     text_color=status_color).pack(side="left", padx=6)
        ctk.CTkLabel(row, text=face_txt, width=80, font=ctk.CTkFont(size=11),
                     text_color=COLOR_TEXT).pack(side="left", padx=6)

        # Actions
        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.pack(side="right", padx=6)

        toggle_text = "Deactivate" if emp["is_active"] else "Activate"
        ctk.CTkButton(
            btn_frame, text=toggle_text, width=90, height=28,
            fg_color=COLOR_ERROR if emp["is_active"] else COLOR_SUCCESS,
            text_color="#ffffff", font=ctk.CTkFont(size=11),
            command=lambda eid=emp["emp_id"], act=emp["is_active"]: self._toggle_active(eid, act)
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btn_frame, text="🗑 Delete", width=80, height=28,
            fg_color="#550000", text_color=COLOR_ERROR,
            font=ctk.CTkFont(size=11),
            command=lambda eid=emp["emp_id"], nm=emp["name"]: self._delete(eid, nm)
        ).pack(side="left", padx=3)

    def _toggle_active(self, emp_id: str, currently_active: int):
        action = "Deactivate" if currently_active else "Activate"
        if not messagebox.askyesno(f"{action} Employee",
                                   f"Are you sure you want to {action.lower()} employee {emp_id}?\n"
                                   "Their attendance history will be preserved."):
            return
        db.set_employee_active(emp_id, not currently_active)
        if currently_active:
            self.recognizer.remove_from_gallery(emp_id)
        else:
            embs = db.load_all_embeddings().get(emp_id, [])
            if embs:
                self.recognizer.add_to_gallery(emp_id, embs)
        db.audit("admin", f"EMPLOYEE_{action.upper()}", f"emp_id={emp_id}")
        self._refresh()

    def _delete(self, emp_id: str, name: str):
        resp = messagebox.askyesno(
            "Delete Employee",
            f"Delete employee '{name}' ({emp_id})?\n\n"
            "• Face embeddings and employee record will be removed.\n"
            "• Historical attendance records will be PRESERVED.\n\n"
            "This action cannot be undone.",
        )
        if not resp:
            return
        try:
            db.delete_employee_full(emp_id)
            self.recognizer.remove_from_gallery(emp_id)
            db.audit("admin", "EMPLOYEE_DELETED", f"emp_id={emp_id}, name={name}")
            self._refresh()
            if self.on_change:
                self.on_change()
        except Exception as exc:
            messagebox.showerror("Delete Error", str(exc))
