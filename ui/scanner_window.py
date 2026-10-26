"""
ui/scanner_window.py
Live attendance scanner — the default startup view.
Camera runs in a background thread; frames are delivered to the Tkinter
main loop via after() to keep the UI responsive.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional

import cv2
import customtkinter as ctk
from PIL import Image, ImageTk

from config import (
    APP_TITLE, CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT,
    RECOGNITION_THRESHOLD, RECOGNITION_COOLDOWN,
    COLOR_BG_DARK, COLOR_SIDEBAR, COLOR_ACCENT, COLOR_SUCCESS,
    COLOR_ERROR, COLOR_WARNING, COLOR_TEXT, COLOR_SUBTEXT, COLOR_CARD, COLOR_BORDER
)
from database import db_manager as db
from recognition.camera_service import CameraService

logger = logging.getLogger(__name__)


class ScannerWindow(ctk.CTk):
    """
    Main application window — live attendance scanner.
    Clicking Admin Login opens the login dialog on top of this window.
    """

    def __init__(self, recognizer, attendance_service):
        super().__init__()
        self.recognizer         = recognizer
        self.attendance_service = attendance_service

        self._cap:      Optional[cv2.VideoCapture] = None
        self._running   = False
        self._cam_thread: Optional[threading.Thread] = None

        # pending frame to render
        self._pending_frame = None
        self._pending_faces  = []
        self._frame_lock    = threading.Lock()

        self._setup_window()
        self._build_ui()
        self._start_camera()
        self._clock_tick()
        self._stats_tick()

    # ─── Window setup ────────────────────────────────────────────────────────

    def _setup_window(self):
        self.title(APP_TITLE)
        self.geometry("1280x750")
        self.minsize(1100, 650)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=COLOR_BG_DARK)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Top bar ──────────────────────────────────────────────────────────
        topbar = ctk.CTkFrame(self, fg_color=COLOR_SIDEBAR, height=60, corner_radius=0)
        topbar.pack(fill="x", side="top")
        topbar.pack_propagate(False)

        ctk.CTkLabel(
            topbar, text=f"🎯  {APP_TITLE}",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLOR_ACCENT
        ).pack(side="left", padx=20, pady=10)

        self._lbl_clock = ctk.CTkLabel(
            topbar, text="", font=ctk.CTkFont(size=14),
            text_color=COLOR_TEXT
        )
        self._lbl_clock.pack(side="right", padx=20)

        self._btn_admin = ctk.CTkButton(
            topbar, text="🔐  Admin Login",
            fg_color=COLOR_ACCENT, hover_color="#00A882",
            text_color="#000000", font=ctk.CTkFont(weight="bold"),
            command=self._open_login, width=140
        )
        self._btn_admin.pack(side="right", padx=10, pady=10)

        # ── Main body ────────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color=COLOR_BG_DARK)
        body.pack(fill="both", expand=True, padx=10, pady=10)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # ── Camera panel ─────────────────────────────────────────────────────
        cam_panel = ctk.CTkFrame(body, fg_color=COLOR_CARD, corner_radius=12)
        cam_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self._canvas = ctk.CTkCanvas(
            cam_panel, bg="#000000",
            highlightthickness=0
        )
        self._canvas.pack(fill="both", expand=True, padx=4, pady=4)

        # Status bar under camera
        status_bar = ctk.CTkFrame(cam_panel, fg_color=COLOR_BG_DARK, height=36, corner_radius=0)
        status_bar.pack(fill="x", side="bottom")

        self._lbl_cam_status = ctk.CTkLabel(
            status_bar, text="⬛  Camera Initialising…",
            font=ctk.CTkFont(size=12), text_color=COLOR_WARNING
        )
        self._lbl_cam_status.pack(side="left", padx=12)

        self._lbl_recog_status = ctk.CTkLabel(
            status_bar, text="",
            font=ctk.CTkFont(size=12), text_color=COLOR_TEXT
        )
        self._lbl_recog_status.pack(side="right", padx=12)

        # ── Right panel ───────────────────────────────────────────────────────
        right = ctk.CTkFrame(body, fg_color=COLOR_BG_DARK)
        right.grid(row=0, column=1, sticky="nsew")

        # Stats cards
        stats = ctk.CTkFrame(right, fg_color=COLOR_CARD, corner_radius=12)
        stats.pack(fill="x", pady=(0, 8))

        self._lbl_count = self._stat_card(stats, "Today's Attendance", "0")
        stats.pack(fill="x", pady=(0, 8))

        # Latest entries
        entries_label = ctk.CTkFrame(right, fg_color=COLOR_SIDEBAR, corner_radius=12)
        entries_label.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(
            entries_label, text="Latest Entries",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_ACCENT
        ).pack(anchor="w", padx=12, pady=6)

        self._entries_frame = ctk.CTkScrollableFrame(
            right, fg_color=COLOR_CARD, corner_radius=12, height=400
        )
        self._entries_frame.pack(fill="both", expand=True)

    def _stat_card(self, parent, label: str, value: str):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=8)
        card.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=11),
                     text_color=COLOR_SUBTEXT).pack(anchor="w", padx=10, pady=(6, 0))
        lbl = ctk.CTkLabel(card, text=value,
                           font=ctk.CTkFont(size=28, weight="bold"),
                           text_color=COLOR_ACCENT)
        lbl.pack(anchor="w", padx=10, pady=(0, 6))
        return lbl

    # ─── Camera thread ───────────────────────────────────────────────────────

    def _start_camera(self):
        if self._running:
            return
        self._set_cam_status("🟡  Camera Initialising…", COLOR_WARNING)
        self.camera_service = CameraService.get_instance()

        def _async_init():
            online = self.camera_service.start(timeout_sec=6.0)
            if not online:
                self.after(0, lambda: (
                    self._set_cam_status("🔴  Camera Offline", COLOR_ERROR),
                    self._show_offline_frame(),
                ))
                return

            self._running = True
            self._cam_thread = threading.Thread(target=self._camera_loop, daemon=True)
            self._cam_thread.start()
            self.after(0, lambda: self.after(16, self._render_frame))
            self.after(0, lambda: self._set_cam_status(
                f"🟢  Camera Online (Index {self.camera_service.camera_index})",
                COLOR_SUCCESS
            ))

        threading.Thread(target=_async_init, daemon=True).start()

    def stop_camera(self):
        """Pause scanner processing loop (camera service remains warm)."""
        self._running = False
        if self._cam_thread and self._cam_thread.is_alive():
            self._cam_thread.join(timeout=1.5)
        self._cam_thread = None

    def start_camera(self):
        """Resume scanner processing loop."""
        if not self._running:
            self._start_camera()

    def _camera_loop(self):
        """Worker thread that runs face recognition on frames from CameraService."""
        threshold = float(db.get_setting("recognition_threshold", str(RECOGNITION_THRESHOLD)))

        while self._running:
            ret, frame = self.camera_service.read_frame()
            if not ret or frame is None:
                time.sleep(0.03)
                continue

            face_data = self.recognizer.process_frame(frame, threshold)
            annotated = self._annotate(frame.copy(), face_data)

            # Record attendance for recognised faces
            for fd in face_data:
                if fd["recognized"] and fd["emp_id"]:
                    emp_row = db.get_employee(fd["emp_id"])
                    name = emp_row["name"] if emp_row else fd["emp_id"]
                    status, msg = self.attendance_service.try_record(fd["emp_id"], name)
                    fd["att_status"] = status
                    fd["att_msg"]    = msg

            with self._frame_lock:
                self._pending_frame = annotated
                self._pending_faces = face_data

            time.sleep(0.015)

    def _annotate(self, frame, face_data: list) -> "cv2.ndarray":
        for fd in face_data:
            x, y, w, h = fd["x"], fd["y"], fd["w"], fd["h"]
            if fd["recognized"]:
                color = (0, 220, 90)
                emp_row = db.get_employee(fd["emp_id"])
                name = emp_row["name"] if emp_row else fd["emp_id"]
                label = f"{name} [{fd['emp_id']}] {fd['similarity']:.2f}"
            else:
                color = (0, 70, 230)
                label = f"Unknown ({fd['similarity']:.2f})"
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, label, (x, max(y - 10, 16)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        return frame

    def _render_frame(self):
        """Called on the UI thread via after()."""
        if not self._running:
            return
        with self._frame_lock:
            frame = self._pending_frame
            faces = list(self._pending_faces)

        if frame is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            cw = self._canvas.winfo_width()
            ch = self._canvas.winfo_height()
            # Safeguard: winfo_width returns 1 before initial geometry layout
            if cw < 100 or ch < 100:
                cw = CAMERA_WIDTH
                ch = CAMERA_HEIGHT

            # Fit into canvas preserving aspect ratio
            fw, fh = frame.shape[1], frame.shape[0]
            scale = min(cw / fw, ch / fh)
            nw, nh = max(1, int(fw * scale)), max(1, int(fh * scale))
            img = img.resize((nw, nh), Image.BILINEAR)

            tk_img = ImageTk.PhotoImage(img)
            self._canvas.delete("all")
            pos_x = (cw - nw) // 2
            pos_y = (ch - nh) // 2
            self._canvas.create_image(pos_x, pos_y, anchor="nw", image=tk_img)
            self._canvas._img = tk_img   # keep reference

            # Update recognition status label
            if faces:
                recognized = [f for f in faces if f["recognized"]]
                unknown    = [f for f in faces if not f["recognized"]]
                parts = []
                if recognized:
                    parts.append(f"✅ Recognized: {len(recognized)}")
                if unknown:
                    parts.append(f"❌ Unknown: {len(unknown)}")
                self._set_recog_status("  |  ".join(parts))
            else:
                self._set_recog_status("👁  Scanning… (Face camera directly)")

        self.after(33, self._render_frame)   # ~30 fps render

    def _show_offline_frame(self):
        self._canvas.configure(bg="#1A0000")
        self._canvas.create_text(
            320, 240, text="📷  Camera Offline\nClick Retry Camera to reconnect",
            fill=COLOR_ERROR, font=("Helvetica", 18), justify="center"
        )
        # Retry button
        retry_btn = ctk.CTkButton(
            self._canvas, text="🔄  Retry Camera",
            command=self._retry_camera,
            fg_color=COLOR_WARNING, text_color="#000000"
        )
        self._canvas.create_window(320, 360, window=retry_btn)

    def _retry_camera(self):
        self.stop_camera()
        self._start_camera()

    # ─── Clock & stats refresh ────────────────────────────────────────────────

    def _clock_tick(self):
        now = datetime.now().strftime("%A, %d %B %Y   %H:%M:%S")
        self._lbl_clock.configure(text=now)
        self.after(1000, self._clock_tick)

    def _stats_tick(self):
        try:
            count = db.today_count()
            self._lbl_count.configure(text=str(count))
            self._refresh_entries()
        except Exception:
            pass
        self.after(5000, self._stats_tick)

    def _refresh_entries(self):
        """Update the latest-entries panel."""
        for w in self._entries_frame.winfo_children():
            w.destroy()

        rows = db.get_today_attendance()
        if not rows:
            ctk.CTkLabel(
                self._entries_frame, text="No attendance recorded today.",
                text_color=COLOR_SUBTEXT, font=ctk.CTkFont(size=11)
            ).pack(pady=8)
            return

        for row in rows[:20]:
            card = ctk.CTkFrame(self._entries_frame, fg_color=COLOR_SIDEBAR, corner_radius=8)
            card.pack(fill="x", padx=4, pady=3)
            ctk.CTkLabel(
                card,
                text=f"✅  {row['name']}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLOR_SUCCESS
            ).pack(anchor="w", padx=10, pady=(4, 0))
            ctk.CTkLabel(
                card,
                text=f"ID: {row['emp_id']}   •   {row['entry_time']}",
                font=ctk.CTkFont(size=10),
                text_color=COLOR_SUBTEXT
            ).pack(anchor="w", padx=10, pady=(0, 4))

    # ─── Admin Login ─────────────────────────────────────────────────────────

    def _open_login(self):
        from ui.login_window import LoginDialog
        LoginDialog(self, on_success=self._open_admin_dashboard)

    def _open_admin_dashboard(self, username: str):
        from ui.admin_dashboard import AdminDashboard
        # Release camera so admin registration can use webcam without conflict
        self.stop_camera()
        self.withdraw()
        dash = AdminDashboard(self, recognizer=self.recognizer, username=username)
        dash.protocol("WM_DELETE_WINDOW", lambda: self._on_dash_close(dash))

    def _on_dash_close(self, dash):
        dash.destroy()
        self.deiconify()
        # Resume camera scanning on main window
        self.start_camera()

    # ─── Status helpers ──────────────────────────────────────────────────────

    def _set_cam_status(self, text: str, color: str = COLOR_TEXT):
        self.after(0, lambda: self._lbl_cam_status.configure(text=text, text_color=color))

    def _set_recog_status(self, text: str):
        self.after(0, lambda: self._lbl_recog_status.configure(text=text))

    # ─── Shutdown ────────────────────────────────────────────────────────────

    def _on_close(self):
        self.stop_camera()
        try:
            CameraService.get_instance().stop()
        except Exception:
            pass
        self.destroy()
