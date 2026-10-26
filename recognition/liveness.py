"""
recognition/liveness.py
Liveness / anti-spoofing placeholder.

InsightFace does not ship a ready-to-use liveness model in its open release.
This module documents the limitation and provides a structural hook so that
a real liveness model can be plugged in without changing the rest of the code.
"""

import logging

logger = logging.getLogger(__name__)


class LivenessChecker:
    """
    LIMITATION: No production liveness model is bundled with this release.
    The check always returns True (live assumed) with a warning on first use.

    To integrate a real anti-spoofing model:
    1. Place the ONNX model at data/models/liveness.onnx
    2. Replace the `check` method body with actual inference.
    3. Remove the warning log.

    Known liveness solutions that can be integrated:
    - Silent-Face-Anti-Spoofing (MinivisionTech) — local ONNX
    - FAS-SGTD — research-grade, ONNX-exportable
    """

    _warned = False

    def __init__(self):
        if not LivenessChecker._warned:
            logger.warning(
                "Liveness detection is DISABLED. "
                "Attendance fraud using photographs is possible. "
                "Integrate a liveness model to harden security."
            )
            LivenessChecker._warned = True

    def check(self, bgr_face_roi) -> tuple[bool, float]:
        """
        Returns (is_live, confidence).
        Currently always returns (True, 1.0) — no real check performed.
        """
        return True, 1.0
