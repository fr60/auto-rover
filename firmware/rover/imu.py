"""
firmware/rover/imu.py
─────────────────────
BNO085 IMU reader via SPI with null-object fallback.
Returns NullIMU if sensor not connected or SPI fails.
"""

import logging
from dataclasses import dataclass
from typing import Optional
 
log = logging.getLogger(__name__)
 

@dataclass
class IMUReading:
    heading: float      # degrees 0-360, magnetic north
    pitch:   float      # degrees
    roll:    float      # degrees
 
 
class NullIMU:
    def is_available(self) -> bool:
        return False
 
    def heading(self) -> Optional[float]:
        return None
 
    def reading(self) -> Optional[IMUReading]:
        return None
 
    def __repr__(self):
        return "NullIMU(unavailable)"
 
 
class _RealIMU:
    def __init__(self):
        import board
        import busio
        from digitalio import DigitalInOut
        import adafruit_bno08x
        from adafruit_bno08x.spi import BNO08X_SPI
 
        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        cs  = DigitalInOut(board.CE0)
        self._bno = BNO08X_SPI(spi, cs)
        self._bno.enable_feature(adafruit_bno08x.BNO_REPORT_ROTATION_VECTOR)
        log.info("IMU (BNO085) initialised via SPI")
 
    def is_available(self) -> bool:
        return True
 
    def heading(self) -> Optional[float]:
        r = self.reading()
        return r.heading if r else None
 
    def reading(self) -> Optional[IMUReading]:
        try:
            quat = self._bno.quaternion
            if quat is None:
                return None
            # Convert quaternion to yaw/pitch/roll
            import math
            x, y, z, w = quat
            heading = math.degrees(
                math.atan2(2*(w*z + x*y), 1 - 2*(y*y + z*z))
            ) % 360
            pitch = math.degrees(math.asin(2*(w*y - z*x)))
            roll  = math.degrees(
                math.atan2(2*(w*x + y*z), 1 - 2*(x*x + y*y))
            )
            return IMUReading(heading=heading, pitch=pitch, roll=roll)
        except Exception as e:
            log.warning(f"IMU read error: {e}")
            return None
 
    def __repr__(self):
        return "IMU(BNO085, SPI)"
 
 
def IMU() -> "_RealIMU | NullIMU":
    try:
        imu = _RealIMU()
        log.info(f"IMU initialised: {imu}")
        return imu
    except Exception as e:
        log.warning(f"IMU unavailable ({e}) — using NullIMU fallback")
        return NullIMU()
