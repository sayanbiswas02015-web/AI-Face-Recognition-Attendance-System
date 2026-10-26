"""
ui/login_window.py
Admin login dialog with rate-limit feedback.
"""

import customtkinter as ctk
from typing import Callable

from auth.admin_auth import login, needs_first_time_setup, setup_admin
from config import COLOR_ACCENT, COLOR_ERROR, COLOR_SUCCESS, COLOR_CARD, COLOR_SIDEBAR, COLOR_TEXT, COLOR_SUBTEXT


class LoginDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_success: Callable[[str], None]):
        super().__init__(parent)
        self.on_success = on_success
        self.title("Admin Login")
        self.geometry("420x460")
        self.resizable(False, False)
        self.grab_set()
        self.configure(fg_color=COLOR_SIDEBAR)
        self._build()
        self.after(100, self._entry_user.focus)

    def _build(self):
        ctk.CTkLabel(
            self, text="🔐  Administrator Login",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_ACCENT
        ).pack(pady=(28, 8))

        ctk.CTkLabel(
            self, text="Enter your admin credentials to continue.",
            font=ctk.CTkFont(size=11), text_color=COLOR_SUBTEXT
        ).pack(pady=(0, 20))

        form = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12)
        form.pack(padx=32, fill="x")

        ctk.CTkLabel(form, text="Username", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(16, 2))
        self._entry_user = ctk.CTkEntry(form, placeholder_text="admin", height=38)
        self._entry_user.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(form, text="Password", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(4, 2))
        self._entry_pass = ctk.CTkEntry(form, placeholder_text="••••••••", show="•", height=38)
        self._entry_pass.pack(fill="x", padx=16, pady=(0, 16))
        self._entry_pass.bind("<Return>", lambda e: self._do_login())

        self._lbl_msg = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11))
        self._lbl_msg.pack(pady=8)

        ctk.CTkButton(
            self, text="Login",
            fg_color=COLOR_ACCENT, hover_color="#00A882",
            text_color="#000000", font=ctk.CTkFont(weight="bold"),
            height=42, command=self._do_login
        ).pack(padx=32, fill="x", pady=(4, 8))

        ctk.CTkButton(
            self, text="Cancel",
            fg_color="transparent", border_color=COLOR_ACCENT, border_width=1,
            text_color=COLOR_ACCENT, height=38, command=self.destroy
        ).pack(padx=32, fill="x")

        # First-time setup notice
        if needs_first_time_setup():
            self._show_setup_prompt()

    def _show_setup_prompt(self):
        """Redirect to first-time admin setup."""
        for w in self.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self, text="🛠  First-Time Setup",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=COLOR_ACCENT
        ).pack(pady=(28, 6))
        ctk.CTkLabel(
            self, text="No admin account found.\nCreate one to continue.",
            font=ctk.CTkFont(size=11), text_color=COLOR_SUBTEXT, justify="center"
        ).pack(pady=(0, 16))

        form = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12)
        form.pack(padx=32, fill="x")

        ctk.CTkLabel(form, text="Username", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(16, 2))
        self._su_user = ctk.CTkEntry(form, placeholder_text="admin", height=38)
        self._su_user.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(form, text="Password (min 8 chars)", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(4, 2))
        self._su_pass = ctk.CTkEntry(form, show="•", height=38)
        self._su_pass.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(form, text="Confirm Password", text_color=COLOR_TEXT,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=(4, 2))
        self._su_conf = ctk.CTkEntry(form, show="•", height=38)
        self._su_conf.pack(fill="x", padx=16, pady=(0, 16))

        self._su_msg = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11))
        self._su_msg.pack(pady=6)

        ctk.CTkButton(
            self, text="Create Admin Account",
            fg_color=COLOR_ACCENT, hover_color="#00A882",
            text_color="#000000", font=ctk.CTkFont(weight="bold"),
            height=42, command=self._do_setup
        ).pack(padx=32, fill="x", pady=(4, 8))

    def _do_setup(self):
        u = self._su_user.get().strip()
        p = self._su_pass.get()
        c = self._su_conf.get()
        if p != c:
            self._su_msg.configure(text="Passwords do not match.", text_color=COLOR_ERROR)
            return
        ok, msg = setup_admin(u, p)
        if ok:
            self._su_msg.configure(text="✅ " + msg, text_color=COLOR_SUCCESS)
            self.after(1200, self._rebuild_login)
        else:
            self._su_msg.configure(text="❌ " + msg, text_color=COLOR_ERROR)

    def _rebuild_login(self):
        for w in self.winfo_children():
            w.destroy()
        self._build()

    def _do_login(self):
        u = self._entry_user.get().strip()
        p = self._entry_pass.get()
        ok, msg = login(u, p)
        if ok:
            self._lbl_msg.configure(text="✅ " + msg, text_color=COLOR_SUCCESS)
            self.after(600, lambda: (self.destroy(), self.on_success(u)))
        else:
            self._lbl_msg.configure(text="❌ " + msg, text_color=COLOR_ERROR)
