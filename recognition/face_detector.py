"""
recognition/face_detector.py
Face detection using OpenCV's built-in DNN face detector or
InsightFace's detector (whichever is available).

Falls back to Haar cascade if neither DNN model is present.
"""

import logging
import os
import urllib.request
from pathlib import Path
from typing import List, Tuple, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────
_MODEL_DIR = Path(__file__).parent.parent / "data" / "models"
_MODEL_DIR.mkdir(parents=True, exist_ok=True)

_PROTOTXT_URL = (
    "https://raw.githubusercontent.com/opencv/opencv/master/"
    "samples/dnn/face_detector/deploy.prototxt"
)
_CAFFEMODEL_URL = (
    "https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/"
    "res10_300x300_ssd_iter_140000.caffemodel"
)
_PROTOTXT   = _MODEL_DIR / "deploy.prototxt"
_CAFFEMODEL = _MODEL_DIR / "res10_300x300_ssd_iter_140000.caffemodel"


def _download(url: str, dest: Path) -> bool:
    try:
        logger.info("Downloading %s -> %s", url, dest)
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception as exc:
        logger.warning("Download failed: %s", exc)
        return False


class FaceDetector:
    """
    Detect faces in a BGR frame.
    Returns a list of (x, y, w, h, confidence) tuples.
    """

    def __init__(self, min_confidence: float = 0.85):
        self.min_confidence = min_confidence
        self._dnn: Optional[cv2.dnn.Net] = None
        self._haar: Optional[cv2.CascadeClassifier] = None
        self._mode = "none"
        self._init()

    def _init(self):
        # Try DNN first (most accurate)
        if not _PROTOTXT.exists():
            _download(_PROTOTXT_URL, _PROTOTXT)
        if not _CAFFEMODEL.exists():
            _download(_CAFFEMODEL_URL, _CAFFEMODEL)

        if _PROTOTXT.exists() and _CAFFEMODEL.exists():
            try:
                self._dnn = cv2.dnn.readNetFromCaffe(str(_PROTOTXT), str(_CAFFEMODEL))
                self._mode = "dnn"
                logger.info("Face detector: DNN (OpenCV Caffe)")
                return
            except Exception as exc:
                logger.warning("DNN load failed: %s", exc)

        # Haar cascade fallback
        haar_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        if os.path.exists(haar_path):
            self._haar = cv2.CascadeClassifier(haar_path)
            if not self._haar.empty():
                self._mode = "haar"
                logger.info("Face detector: Haar cascade (fallback)")
                return

        logger.error("No face detector available — detection disabled.")

    @property
    def mode(self) -> str:
        return self._mode

    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
        """Return [(x, y, w, h, confidence), ...]"""
        if self._mode == "dnn":
            return self._detect_dnn(frame)
        if self._mode == "haar":
            return self._detect_haar(frame)
        return []

    def _detect_dnn(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 1.0,
            (300, 300), (104.0, 177.0, 123.0)
        )
        self._dnn.setInput(blob)
        detections = self._dnn.forward()
        results = []
        for i in range(detections.shape[2]):
            conf = float(detections[0, 0, i, 2])
            if conf < self.min_confidence:
                continue
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            x1, y1, x2, y2 = box.astype(int)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            bw, bh = x2 - x1, y2 - y1
            if bw > 20 and bh > 20:
                results.append((x1, y1, bw, bh, conf))
        return results

    def _detect_haar(self, frame: np.ndarray):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._haar.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
        return [(x, y, w, h, 0.9) for (x, y, w, h) in faces]

    def extract_face_roi(
        self, frame: np.ndarray, x: int, y: int, w: int, h: int,
        padding: float = 0.15
    ) -> np.ndarray:
        """Crop face with padding, returns BGR patch."""
        fh, fw = frame.shape[:2]
        px, py = int(w * padding), int(h * padding)
        x0 = max(0, x - px)
        y0 = max(0, y - py)
        x1 = min(fw, x + w + px)
        y1 = min(fh, y + h + py)
        return frame[y0:y1, x0:x1].copy()
