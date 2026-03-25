"""
firmware/rover/arbiter.py
─────────────────────────
Polls all sensors at startup and continuously.
Assigns the best available navigation mode based
on what hardware is actually connected and healthy.
 
Priority:
  GPS + IMU   → AUTOPILOT_FULL
  GPS only    → AUTOPILOT_DEGRADED
  Camera only → CAMERA_MANUAL
  Nothing     → MANUAL_PURE
"""
 
import logging
from enum import Enum
 
log = logging.getLogger(__name__)
 
 
class NavMode(Enum):
    AUTOPILOT_FULL      = "autopilot_full"       # GPS + IMU
    AUTOPILOT_DEGRADED  = "autopilot_degraded"   # GPS only
    CAMERA_MANUAL       = "camera_manual"        # camera + manual
    MANUAL_PURE         = "manual_pure"          # always works

class Arbiter:
    def __init__(self):
        log.info("Initialising sensors...")
 
        # Each sensor module returns a real object or a null fallback
        from rover.gps    import GPS
        from rover.imu    import IMU
        from rover.camera import Camera
 
        self.gps    = GPS()
        self.imu    = IMU()
        self.camera = Camera()
 
    @property
    def mode(self) -> NavMode:
        """Returns best available navigation mode right now."""
        if self.gps.is_available() and self.imu.is_available():
            return NavMode.AUTOPILOT_FULL
        elif self.gps.is_available():
            return NavMode.AUTOPILOT_DEGRADED
        elif self.camera.is_available():
            return NavMode.CAMERA_MANUAL
        else:
            return NavMode.MANUAL_PURE
 
    def report(self):
        """Logs current sensor status and assigned mode."""
        log.info("─── Sensor status ───────────────────────")
        log.info(f"  GPS    : {'OK' if self.gps.is_available()    else 'unavailable'}")
        log.info(f"  IMU    : {'OK' if self.imu.is_available()    else 'unavailable'}")
        log.info(f"  Camera : {'OK' if self.camera.is_available() else 'unavailable'}")
        log.info(f"  Mode   : {self.mode.value}")
        log.info("─────────────────────────────────────────")
