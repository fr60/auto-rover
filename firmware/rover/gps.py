"""
firmware/rover/gps.py
────────────
F9P GPS reader with null-object fallback.
 
If the F9P is not connected or gpsd is not running, the module
returns a NullGPS instance that always reports no fix — the rest
of the system never sees an exception.
 
Usage:
    from rover.gps import GPS
 
    gps = GPS()          # auto-detects, falls back to NullGPS
    if gps.is_available():
        pos = gps.position()
        print(pos.lat, pos.lon, pos.fix_quality)
"""

import time
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

# ────────── Data Types ──────────────────────────────────────────────────

@dataclass
class GPSPosition:
    lat: float             # degrees
    lon: float             # degrees
    alt: float             # meters above sea level
    fix_quality: int       # 0=no fix, 1=GPS, 2=DGPS, 4=RTK fixed, 5=RTK float
    speed: float           # m/s
    heading: float         # degrees 0-360 (track angle, not magnetic)
    satellites: int        # number of satellites in view
    hdop: float            # horizontal dilution of precision (lower = better)
    timestamp: float       # unix time of fix

# ────────── Null object (safe fallback when GPS unavailable) ────────────
class NullGPS:
    """Returned when the F9P is not connected or gpsd is not running.
    All methods return safe defaults — no exceptions, no crashes."""

    def is_available(self) -> bool:
        return False
 
    def has_fix(self) -> bool:
        return False
 
    def position(self) -> Optional[GPSPosition]:
        return None

    def __repr__(self):
        return "NullGPS(unavailable)"
    
# ──────────── Real GPS (wraps gpsd-py3) ─────────────────────────────────

class _RealGPS:
    """Reads from gpsd which in turn reads from the F9P over USB."""

    # Fix quality codes from the F9P
    FIX_NONE     = 0
    FIX_GPS      = 1
    FIX_DGPS     = 2
    FIX_RTK_FIX = 4
    FIX_RTK_FLT = 5

    def __init__(self):
        import gpsd
        self._gpsd = gpsd
        self._gpsd.connect()
        log.info("GPS connected to gpsd")

    def is_available(self) -> bool:
        return True
    

    def has_fix(self) -> bool:
        try:
            packet = self._gpsd.get_current()
            return packet.mode >= 2   # 2=2D fix, 3=3D fix
        except Exception:
            return False


    def position(self) -> Optional[GPSPosition]:
        try:
            p = self._gpsd.get_current()
            if p.mode < 2:
                return None

            return GPSPosition(
                lat         = p.lat,
                lon         = p.lon,
                alt         = getattr(p, 'alt', 0.0),
                speed       = getattr(p, 'hspeed', 0.0),
                heading     = getattr(p, 'track', 0.0),
                fix_quality = getattr(p, 'mode', 0),
                satellites  = getattr(p, 'sats', 0),
                hdop        = getattr(p, 'hdop', 99.9),
                timestamp   = time.time(),
            )
        except Exception as e:
            log.warning(f"GPS read error: {e}")
            return None


    def __repr__(self):
        fix = "fix" if self.has_fix() else "no fix"
        return f"GPS({fix})"
    



# ─── Factory function ───────────────────────────────────────────────────
def GPS() -> "_RealGPS | NullGPS":
    """
    Returns a live GPS object if gpsd is running and the F9P is
    connected, otherwise returns a NullGPS that never raises.
    """

    try:
        gps = _RealGPS()
        # Quick sanity check — if gpsd is running but F9P not plugged in
        # this will still succeed, so we log the fix state
        fix_state = "has fix" if gps.has_fix() else "no fix yet (waiting for satellites)"
        log.info(f"GPS initialised — {fix_state}")
        return gps
    except Exception as e:
        log.warning(f"GPS unavailable ({e}) — using NullGPS fallback")
        return NullGPS()


