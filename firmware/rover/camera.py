"""
firmware/rover/camera.py
────────────────────────
Raspberry Pi AI Camera (IMX500) reader with null-object fallback.
Returns NullCamera if camera not connected or picamera2 fails.
"""
 
import logging
from typing import Optional
 
log = logging.getLogger(__name__)
 
 
class NullCamera:
    def is_available(self) -> bool:
        return False
 
    def frame(self):
        return None
 
    def __repr__(self):
        return "NullCamera(unavailable)"
 
 
class _RealCamera:
    def __init__(self):
        from picamera2 import Picamera2
        self._cam = Picamera2()
        config = self._cam.create_preview_configuration(
            main={"size": (640, 480), "format": "RGB888"}
        )
        self._cam.configure(config)
        self._cam.start()
        log.info("Camera (IMX500) initialised")
 
    def is_available(self) -> bool:
        return True
 
    def frame(self):
        """Returns the latest frame as a numpy array (H, W, 3)."""
        try:
            return self._cam.capture_array()
        except Exception as e:
            log.warning(f"Camera read error: {e}")
            return None
 
    def stop(self):
        self._cam.stop()
 
    def __repr__(self):
        return "Camera(IMX500)"
 
 
def Camera() -> "_RealCamera | NullCamera":
    try:
        cam = _RealCamera()
        log.info(f"Camera initialised: {cam}")
        return cam
    except Exception as e:
        log.warning(f"Camera unavailable ({e}) — using NullCamera fallback")
        return NullCamera()