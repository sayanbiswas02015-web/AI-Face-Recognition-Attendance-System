"""
recognition/face_recognizer.py
Face recognition using InsightFace (ArcFace) with cosine-similarity matching.
Falls back to a LBPH-based recognizer if InsightFace is not installed.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple

from config import RECOGNITION_THRESHOLD, EMBEDDING_DIM

logger = logging.getLogger(__name__)


# ─── InsightFace backend ──────────────────────────────────────────────────────

class InsightFaceBackend:
    def __init__(self):
        import insightface
        from insightface.app import FaceAnalysis
        self.app = FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        if "detection" in self.app.models:
            self.app.models["detection"].det_thresh = 0.35
        logger.info("InsightFace backend ready (buffalo_sc / ArcFace, det_thresh=0.35)")

    def get_embedding(self, bgr_frame: np.ndarray) -> Optional[np.ndarray]:
        faces = self.app.get(bgr_frame)
        if not faces:
            return None
        # pick largest face
        face = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
        emb = face.embedding
        if emb is None:
            return None
        return emb / (np.linalg.norm(emb) + 1e-8)   # L2 normalise

    def get_all_faces(self, bgr_frame: np.ndarray):
        """Return raw insightface Face objects."""
        return self.app.get(bgr_frame)


# ─── OpenCV DNN + LBPH fallback backend ──────────────────────────────────────

class OpenCVBackend:
    """
    Uses histogram-of-gradients features (HOG) extracted from the face ROI
    as a lightweight substitute for a deep embedding.
    ACCURACY IS SIGNIFICANTLY LOWER than InsightFace.
    """
    def __init__(self):
        logger.warning(
            "InsightFace unavailable — using HOG feature fallback. "
            "Recognition accuracy will be reduced."
        )

    def _hog_embedding(self, bgr: np.ndarray) -> np.ndarray:
        gray = np.array(__import__("cv2").cvtColor(
            __import__("cv2").resize(bgr, (128, 128)),
            __import__("cv2").COLOR_BGR2GRAY
        ), dtype=np.float32)
        # Normalise to zero-mean, unit-std
        gray -= gray.mean()
        std = gray.std()
        if std > 0:
            gray /= std
        # Flatten + L2-normalise → pseudo-embedding
        flat = gray.flatten()
        norm = np.linalg.norm(flat)
        return flat / (norm + 1e-8)

    def get_embedding(self, bgr_frame: np.ndarray) -> Optional[np.ndarray]:
        if bgr_frame is None or bgr_frame.size == 0:
            return None
        return self._hog_embedding(bgr_frame)

    def get_all_faces(self, bgr_frame: np.ndarray):
        return []   # no per-face objects in fallback mode


# ─── Recognizer ──────────────────────────────────────────────────────────────

class FaceRecognizer:
    """
    Maintains a {emp_id: [embedding, ...]} gallery and performs
    cosine-similarity nearest-neighbour matching.
    """

    def __init__(self):
        self._backend = self._load_backend()
        self._gallery: Dict[str, List[np.ndarray]] = {}
        self._backend_name = type(self._backend).__name__

    def _load_backend(self):
        try:
            return InsightFaceBackend()
        except Exception as exc:
            logger.warning("InsightFace load failed (%s), using OpenCV fallback.", exc)
            return OpenCVBackend()

    @property
    def backend_name(self) -> str:
        return self._backend_name

    def uses_insightface(self) -> bool:
        return isinstance(self._backend, InsightFaceBackend)

    # ── Gallery management ──────────────────────────────────────────────────

    def load_gallery(self, gallery: Dict[str, List[np.ndarray]]) -> None:
        """Replace the in-memory gallery with a fresh copy from the DB."""
        self._gallery = {
            emp_id: [e / (np.linalg.norm(e) + 1e-8) for e in embs]
            for emp_id, embs in gallery.items()
        }
        logger.info("Gallery loaded: %d employees", len(self._gallery))

    def add_to_gallery(self, emp_id: str, embeddings: List[np.ndarray]) -> None:
        self._gallery[emp_id] = [e / (np.linalg.norm(e) + 1e-8) for e in embeddings]

    def remove_from_gallery(self, emp_id: str) -> None:
        self._gallery.pop(emp_id, None)

    # ── Recognition ────────────────────────────────────────────────────────

    def get_embedding(self, bgr_frame: np.ndarray) -> Optional[np.ndarray]:
        return self._backend.get_embedding(bgr_frame)

    def get_all_faces(self, bgr_frame: np.ndarray):
        return self._backend.get_all_faces(bgr_frame)

    def identify(
        self, embedding: np.ndarray, threshold: float = RECOGNITION_THRESHOLD
    ) -> Tuple[Optional[str], float]:
        """
        Compare embedding against gallery.
        Returns (emp_id, similarity) or (None, best_sim).
        """
        if not self._gallery:
            return None, 0.0

        best_id, best_sim = None, -1.0
        for emp_id, embs in self._gallery.items():
            for ref in embs:
                sim = float(np.dot(embedding, ref))
                if sim > best_sim:
                    best_sim = sim
                    best_id = emp_id

        if best_sim >= threshold:
            return best_id, best_sim
        return None, best_sim

    def process_frame(
        self, bgr_frame: np.ndarray, threshold: float = RECOGNITION_THRESHOLD
    ) -> List[dict]:
        """
        Full pipeline: detect → embed → identify for all faces in frame.
        Returns list of dicts:
          {x, y, w, h, emp_id, similarity, recognized}
        """
        results = []

        if self.uses_insightface():
            faces = self._backend.get_all_faces(bgr_frame)
            fh, fw = bgr_frame.shape[:2]
            for face in faces:
                x1, y1, x2, y2 = [int(v) for v in face.bbox]
                x1, y1 = max(0, min(fw - 1, x1)), max(0, min(fh - 1, y1))
                x2, y2 = max(0, min(fw, x2)), max(0, min(fh, y2))
                x, y, w, h = x1, y1, max(1, x2 - x1), max(1, y2 - y1)
                emb = face.embedding
                if emb is None:
                    continue
                emb = emb / (np.linalg.norm(emb) + 1e-8)
                emp_id, sim = self.identify(emb, threshold)
                results.append({
                    "x": x, "y": y, "w": w, "h": h,
                    "emp_id": emp_id, "similarity": sim,
                    "recognized": emp_id is not None,
                    "embedding": emb,
                })
        else:
            # Fallback: use FaceDetector separately
            import cv2
            from recognition.face_detector import FaceDetector
            detector = FaceDetector()
            detections = detector.detect(bgr_frame)
            for (x, y, w, h, conf) in detections:
                roi = detector.extract_face_roi(bgr_frame, x, y, w, h)
                emb = self._backend.get_embedding(roi)
                if emb is None:
                    continue
                emp_id, sim = self.identify(emb, threshold)
                results.append({
                    "x": x, "y": y, "w": w, "h": h,
                    "emp_id": emp_id, "similarity": sim,
                    "recognized": emp_id is not None,
                    "embedding": emb,
                })

        return results
