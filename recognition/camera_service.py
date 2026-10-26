"""
recognition/camera_service.py
Central thread-safe Camera Service.
Maintains a single VideoCapture instance and continuously streams MJPG frames,
eliminating OS camera lock contention between the scanner and registration pages.
"""

import logging
import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from config import CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS
from database import db_manager as db

logger = logging.getLogger(__name__)


class CameraService:
    _instance: Optional["CameraService"] = None
    _singleton_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "CameraService":
        with cls._singleton_lock:
            if cls._instance is None:
                cam_idx = int(db.get_setting("camera_index", str(CAMERA_INDEX)))
                cls._instance = CameraService(camera_index=cam_idx)
            return cls._instance

    def __init__(self, camera_index: int = CAMERA_INDEX):
        self.camera_index = camera_index
        self._cap: Optional[cv2.VideoCapture] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._is_online = False

    def start(self, timeout_sec: float = 6.0) -> bool:
        """Start background camera streaming thread with timeout."""
        if self._running and self._is_online and self._latest_frame is not None:
            return True

        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()

        # Wait for camera driver to initialize and deliver first frame
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            with self._frame_lock:
                if self._is_online and self._latest_frame is not None:
                    return True
            time.sleep(0.08)
        return self.is_online

    def stop(self):
        """Stop capture thread and release hardware cleanly."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        with self._frame_lock:
            if self._cap:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
            self._is_online = False

    def _capture_loop(self):
        """Worker thread that interacts with the camera driver."""
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(self.camera_index)

        # Automatic fallback to index 0 if chosen index failed
        if not cap.isOpened() and self.camera_index != 0:
            logger.warning(
                "Camera index %d failed to open, falling back to index 0",
                self.camera_index,
            )
            self.camera_index = 0
            try:
                db.set_setting("camera_index", "0")
            except Exception:
                pass
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            logger.error("Failed to open camera index %d", self.camera_index)
            with self._frame_lock:
                self._is_online = False
            return

        # Force Motion-JPEG to avoid raw sensor byte alignment/stride distortion
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

        # Discard first 3 warm-up frames
        for _ in range(3):
            cap.read()

        with self._frame_lock:
            self._cap = cap
            self._is_online = True

        logger.info("CameraService streaming on index %d (MJPG)", self.camera_index)

        while self._running:
            ret, frame = cap.read()
            if not ret or frame is None:
                with self._frame_lock:
                    self._is_online = False
                time.sleep(0.05)
                continue

            frame_flipped = cv2.flip(frame, 1)

            with self._frame_lock:
                self._latest_frame = frame_flipped
                self._is_online = True

            time.sleep(0.015)  # ~60 fps capture limit

        try:
            cap.release()
        except Exception:
            pass
        with self._frame_lock:
            self._cap = None
            self._is_online = False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Return (success, frame_copy). Thread-safe and fast."""
        with self._frame_lock:
            if not self._is_online or self._latest_frame is None:
                return False, None
            return True, self._latest_frame.copy()

    @property
    def is_online(self) -> bool:
        with self._frame_lock:
            return self._is_online
