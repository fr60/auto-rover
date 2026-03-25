"""
firmware/rover/camera.py
────────────────────────
Raspberry Pi AI Camera (IMX500) reader with null-object fallback.
Returns NullCamera if camera not connected or picamera2 fails.
"""

import time
import logging
from typing import Optional

log = logging.getLogger(__name__)


class NullCamera:
    def is_available(self) -> bool:
        return False

    def frame(self):
        return None

    def stop(self):
        pass

    def __repr__(self):
        return "NullCamera(unavailable)"


class _RealCamera:
    def __init__(self):
        from picamera2 import Picamera2
        self._cam = Picamera2()

        # Log camera model for diagnostics
        cam_info = self._cam.camera_properties.get("Model", "unknown")
        log.info(f"Camera model: {cam_info}")

        # Video config for continuous frame capture
        # 640x480 is plenty for obstacle detection on a rover
        config = self._cam.create_video_configuration(
            main={"size": (640, 480), "format": "RGB888"},
            controls={"FrameRate": 30}
        )
        self._cam.configure(config)
        self._cam.start()
        # Allow auto-exposure to settle
        time.sleep(0.5)
        log.info("Camera (IMX500) initialised — 640x480 @ 30fps")

    def is_available(self) -> bool:
        return True

    def frame(self):
        """Returns latest frame as numpy array (H, W, 3) in RGB."""
        try:
            return self._cam.capture_array()
        except Exception as e:
            log.warning(f"Camera read error: {e}")
            return None

    def stop(self):
        try:
            self._cam.stop()
        except Exception:
            pass

    def __repr__(self):
        return "Camera(IMX500, 640x480)"


def Camera() -> "_RealCamera | NullCamera":
    try:
        cam = _RealCamera()
        log.info(f"Camera initialised: {cam}")
        return cam
    except Exception as e:
        log.warning(f"Camera unavailable ({e}) — using NullCamera fallback")
        return NullCamera()