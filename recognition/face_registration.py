"""
recognition/face_registration.py
Collects multiple face samples during employee registration,
validates quality, generates embeddings, and persists them.
"""

import logging
import time
from typing import Callable, List, Optional, Tuple, Any

import cv2
import numpy as np

from config import MIN_FACE_SAMPLES
from recognition.face_detector import FaceDetector

logger = logging.getLogger(__name__)


class RegistrationCapture:
    """
    Drives the face-capture phase of employee registration.

    Supports both CameraService and raw cv2.VideoCapture instances.
    """

    def __init__(self, recognizer, camera_source: Any, num_samples: int = MIN_FACE_SAMPLES):
        self.recognizer      = recognizer
        self.camera_source   = camera_source
        self.num_samples     = num_samples
        self._detector       = FaceDetector(min_confidence=0.75)
        self.running         = False

    def collect(
        self,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
        frame_cb:    Optional[Callable[[np.ndarray], None]] = None,
    ) -> Tuple[List[np.ndarray], str]:
        """
        Capture `num_samples` valid face embeddings.
        Returns (embeddings_list, status_message).
        """
        self.running = True
        embeddings: List[np.ndarray] = []
        last_capture = 0.0

        while self.running and len(embeddings) < self.num_samples:
            if hasattr(self.camera_source, "read_frame"):
                ret, frame = self.camera_source.read_frame()
            else:
                ret, raw = self.camera_source.read()
                frame = cv2.flip(raw, 1) if (ret and raw is not None) else None

            if not ret or frame is None:
                time.sleep(0.04)
                continue

            display = frame.copy()

            # Direct InsightFace path (optimal accuracy & speed)
            if self.recognizer.uses_insightface():
                faces = self.recognizer.get_all_faces(frame)

                if len(faces) == 0:
                    self._annotate(display, None, "Looking for face - look at camera")
                    if frame_cb:
                        frame_cb(display)
                    if progress_cb:
                        progress_cb(len(embeddings), self.num_samples, "Looking for face...")
                    time.sleep(0.04)
                    continue

                if len(faces) > 1:
                    self._annotate(display, None, "Multiple faces detected - one person only")
                    if frame_cb:
                        frame_cb(display)
                    if progress_cb:
                        progress_cb(len(embeddings), self.num_samples, "Multiple faces detected")
                    time.sleep(0.04)
                    continue

                face = faces[0]
                x1, y1, x2, y2 = [int(v) for v in face.bbox]
                fh, fw = frame.shape[:2]
                x1, y1 = max(0, min(fw - 1, x1)), max(0, min(fh - 1, y1))
                x2, y2 = max(0, min(fw, x2)), max(0, min(fh, y2))
                w, h = x2 - x1, y2 - y1

                # Quality gate: face must be reasonably sized
                if w < 50 or h < 50:
                    self._annotate(display, (x1, y1, w, h), "Move closer to camera")
                    if frame_cb:
                        frame_cb(display)
                    time.sleep(0.04)
                    continue

                now = time.time()
                if now - last_capture < 0.4:
                    self._annotate(display, (x1, y1, w, h), f"Hold still... {len(embeddings)}/{self.num_samples}")
                    if frame_cb:
                        frame_cb(display)
                    time.sleep(0.04)
                    continue

                emb = face.embedding
                if emb is None:
                    self._annotate(display, (x1, y1, w, h), "Analyzing face...")
                    if frame_cb:
                        frame_cb(display)
                    time.sleep(0.04)
                    continue

                emb = emb / (np.linalg.norm(emb) + 1e-8)
                embeddings.append(emb)
                last_capture = now

                msg = f"Sample {len(embeddings)}/{self.num_samples} captured!"
                self._annotate(display, (x1, y1, w, h), msg, success=True)
                if frame_cb:
                    frame_cb(display)
                if progress_cb:
                    progress_cb(len(embeddings), self.num_samples, msg)

                time.sleep(0.1)

            else:
                # Fallback path using OpenCV FaceDetector
                detections = self._detector.detect(frame)

                if len(detections) == 0:
                    self._annotate(display, None, "Looking for face - look at camera")
                    if frame_cb:
                        frame_cb(display)
                    if progress_cb:
                        progress_cb(len(embeddings), self.num_samples, "Looking for face...")
                    time.sleep(0.04)
                    continue

                if len(detections) > 1:
                    self._annotate(display, None, "Multiple faces detected - one person only")
                    if frame_cb:
                        frame_cb(display)
                    if progress_cb:
                        progress_cb(len(embeddings), self.num_samples, "Multiple faces detected")
                    time.sleep(0.04)
                    continue

                (x, y, w, h, conf) = detections[0]

                if w < 50 or h < 50:
                    self._annotate(display, (x, y, w, h), "Move closer to camera")
                    if frame_cb:
                        frame_cb(display)
                    time.sleep(0.04)
                    continue

                now = time.time()
                if now - last_capture < 0.4:
                    self._annotate(display, (x, y, w, h), f"Hold still... {len(embeddings)}/{self.num_samples}")
                    if frame_cb:
                        frame_cb(display)
                    time.sleep(0.04)
                    continue

                roi = self._detector.extract_face_roi(frame, x, y, w, h)
                emb = self.recognizer.get_embedding(roi)
                if emb is None:
                    self._annotate(display, (x, y, w, h), "Analyzing face...")
                    if frame_cb:
                        frame_cb(display)
                    time.sleep(0.04)
                    continue

                embeddings.append(emb)
                last_capture = now

                msg = f"Sample {len(embeddings)}/{self.num_samples} captured!"
                self._annotate(display, (x, y, w, h), msg, success=True)
                if frame_cb:
                    frame_cb(display)
                if progress_cb:
                    progress_cb(len(embeddings), self.num_samples, msg)

                time.sleep(0.1)

        self.running = False
        if len(embeddings) >= self.num_samples:
            return embeddings, "Face registration complete."
        return embeddings, "Registration cancelled."

    def stop(self):
        self.running = False

    @staticmethod
    def _annotate(frame, bbox, msg, success=False):
        color = (0, 220, 100) if success else (0, 165, 255)
        # Background bar for top instructions
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 44), (15, 20, 25), -1)
        if bbox:
            x, y, w, h = bbox
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            # Corner accents
            line_len = max(10, min(w, h) // 5)
            cv2.line(frame, (x, y), (x + line_len, y), (0, 255, 128), 3)
            cv2.line(frame, (x, y), (x, y + line_len), (0, 255, 128), 3)
            cv2.line(frame, (x + w, y + h), (x + w - line_len, y + h), (0, 255, 128), 3)
            cv2.line(frame, (x + w, y + h), (x + w, y + h - line_len), (0, 255, 128), 3)
        else:
            # Draw subtle center guide
            fh, fw = frame.shape[:2]
            cx, cy = fw // 2, fh // 2
            cv2.rectangle(frame, (cx - 100, cy - 120), (cx + 100, cy + 120), (80, 80, 80), 1, cv2.LINE_AA)
        cv2.putText(frame, msg, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
