"""
tests/test_recognition.py — Face recognizer unit tests (no camera required)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
import numpy as np
from unittest.mock import MagicMock, patch


class TestFaceRecognizerGallery(unittest.TestCase):
    """Test gallery management and cosine-similarity matching logic
    without requiring a real face model or camera."""

    def _make_recognizer_with_mock_backend(self):
        from recognition.face_recognizer import FaceRecognizer
        rec = FaceRecognizer.__new__(FaceRecognizer)
        rec._gallery = {}
        # Mock backend
        mock_backend = MagicMock()
        mock_backend.get_embedding.return_value = None
        rec._backend = mock_backend
        rec._backend_name = "MockBackend"
        return rec

    def test_gallery_load(self):
        rec = self._make_recognizer_with_mock_backend()
        emb = np.random.rand(512).astype(np.float32)
        emb /= np.linalg.norm(emb)
        rec.load_gallery({"E001": [emb]})
        self.assertIn("E001", rec._gallery)

    def test_gallery_add_and_remove(self):
        rec = self._make_recognizer_with_mock_backend()
        emb = np.random.rand(512).astype(np.float32)
        rec.add_to_gallery("E002", [emb])
        self.assertIn("E002", rec._gallery)
        rec.remove_from_gallery("E002")
        self.assertNotIn("E002", rec._gallery)

    def test_identify_exact_match(self):
        rec = self._make_recognizer_with_mock_backend()
        emb = np.random.rand(512).astype(np.float32)
        emb /= np.linalg.norm(emb)
        rec.load_gallery({"E003": [emb]})
        eid, sim = rec.identify(emb, threshold=0.50)
        self.assertEqual(eid, "E003")
        self.assertAlmostEqual(sim, 1.0, places=5)

    def test_identify_below_threshold(self):
        rec = self._make_recognizer_with_mock_backend()
        emb1 = np.zeros(512, dtype=np.float32); emb1[0] = 1.0
        emb2 = np.zeros(512, dtype=np.float32); emb2[1] = 1.0
        rec.load_gallery({"E004": [emb1]})
        eid, sim = rec.identify(emb2, threshold=0.90)
        self.assertIsNone(eid)

    def test_identify_empty_gallery(self):
        rec = self._make_recognizer_with_mock_backend()
        emb = np.random.rand(512).astype(np.float32)
        eid, sim = rec.identify(emb, threshold=0.50)
        self.assertIsNone(eid)
        self.assertEqual(sim, 0.0)

    def test_multi_employee_picks_best(self):
        rec = self._make_recognizer_with_mock_backend()
        target = np.zeros(512, dtype=np.float32); target[0] = 1.0
        close  = np.zeros(512, dtype=np.float32); close[0] = 0.98; close[1] = 0.2
        close /= np.linalg.norm(close)
        far    = np.zeros(512, dtype=np.float32); far[2] = 1.0
        rec.load_gallery({"CLOSE": [close], "FAR": [far]})
        eid, sim = rec.identify(target, threshold=0.5)
        self.assertEqual(eid, "CLOSE")


class TestFaceDetectorFallback(unittest.TestCase):
    def test_detect_returns_list(self):
        from recognition.face_detector import FaceDetector
        detector = FaceDetector()
        # Blank 480p frame
        import numpy as np
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        results = detector.detect(blank)
        self.assertIsInstance(results, list)

    def test_extract_roi_clamps(self):
        from recognition.face_detector import FaceDetector
        import numpy as np
        detector = FaceDetector()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        roi = detector.extract_face_roi(frame, 0, 0, 100, 100, padding=0.2)
        self.assertEqual(roi.ndim, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
