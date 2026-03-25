"""
firmware/rover/gps.py
────────────
F9P GPS reader with null-object fallback.
 
If the F9P is not connected or ser2net is not running, the module
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
import socket
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
    """Reads from ser2net which forwards F9P serial data over TCP."""

    # Fix quality codes from NMEA GGA
    FIX_NONE     = 0
    FIX_GPS      = 1
    FIX_DGPS     = 2
    FIX_PPS      = 3
    FIX_RTK_FIX  = 4
    FIX_RTK_FLT  = 5

    def __init__(self, host="localhost", port=3002):
        self._host = host
        self._port = port
        self._buffer = ""
        log.info(f"GPS connecting to ser2net at {host}:{port}")

    def is_available(self) -> bool:
        try:
            with socket.create_connection((self._host, self._port), timeout=2):
                return True
        except Exception:
            return False

    def has_fix(self) -> bool:
        pos = self.position()
        return pos is not None and pos.fix_quality > 0

    def position(self) -> Optional[GPSPosition]:
        try:
            with socket.create_connection((self._host, self._port), timeout=5) as sock:
                buffer = ""
                # Read multiple chunks to get complete sentences
                for _ in range(5):  # Try up to 5 reads
                    data = sock.recv(4096).decode(errors='ignore')
                    buffer += data
                    
                    # Process complete lines
                    lines = buffer.split('\n')
                    buffer = lines[-1]  # Keep incomplete line for next iteration
                    
                    for line in lines[:-1]:
                        line = line.strip()
                        if line.startswith('$GNGGA') or line.startswith('$GPGGA'):
                            result = self._parse_gga(line)
                            if result:
                                return result
                
                return None
        except Exception as e:
            log.warning(f"GPS read error: {e}")
            return None

    def _parse_gga(self, sentence: str) -> Optional[GPSPosition]:
        """Parse NMEA GGA sentence."""
        try:
            parts = sentence.split(',')
            if len(parts) < 15:
                return None

            # Extract fix quality
            fix_quality = int(parts[6]) if parts[6] else 0
            if fix_quality == 0:
                return None

            # Parse latitude
            lat_raw = parts[2]
            lat_dir = parts[3]
            lat = self._nmea_to_decimal(lat_raw, lat_dir)

            # Parse longitude
            lon_raw = parts[4]
            lon_dir = parts[5]
            lon = self._nmea_to_decimal(lon_raw, lon_dir)

            # Parse other fields
            num_sats = int(parts[7]) if parts[7] else 0
            hdop = float(parts[8]) if parts[8] else 99.9
            altitude = float(parts[9]) if parts[9] else 0.0

            return GPSPosition(
                lat=lat,
                lon=lon,
                alt=altitude,
                fix_quality=fix_quality,
                speed=0.0,  # GGA doesn't have speed, need RMC for that
                heading=0.0,  # GGA doesn't have heading
                satellites=num_sats,
                hdop=hdop,
                timestamp=time.time(),
            )
        except Exception as e:
            log.debug(f"Failed to parse GGA: {sentence[:50]}, error: {e}")
            return None

    def _parse_rmc(self, sentence: str) -> Optional[GPSPosition]:
        """Parse NMEA RMC sentence (Recommended Minimum)."""
        try:
            parts = sentence.split(',')
            if len(parts) < 12:
                return None
            
            # Check status (A = active, V = void)
            if parts[2] != 'A':
                return None
            
            # Parse latitude
            lat = self._nmea_to_decimal(parts[3], parts[4])
            # Parse longitude
            lon = self._nmea_to_decimal(parts[5], parts[6])
            # Speed in knots, convert to m/s
            speed = float(parts[7]) * 0.514444 if parts[7] else 0.0
            # Track angle
            heading = float(parts[8]) if parts[8] else 0.0
            
            return GPSPosition(
                lat=lat,
                lon=lon,
                alt=0.0,
                fix_quality=1,  # RMC doesn't specify quality, assume GPS fix
                speed=speed,
                heading=heading,
                satellites=0,
                hdop=99.9,
                timestamp=time.time(),
            )
        except Exception as e:
            log.debug(f"Failed to parse RMC: {sentence[:50]}, error: {e}")
            return None

    def _nmea_to_decimal(self, coord: str, direction: str) -> float:
        """Convert NMEA coordinate to decimal degrees."""
        if not coord:
            return 0.0
        
        # NMEA format: DDMM.MMMM (lat) or DDDMM.MMMM (lon)
        # Find the decimal point to figure out where degrees end
        dot_pos = coord.find('.')
        if dot_pos == -1:
            return 0.0
        
        # For latitude: DDMM.MMMM (2 digits for degrees)
        # For longitude: DDDMM.MMMM (3 digits for degrees)
        if len(coord) < 10:  # Latitude
            degrees = float(coord[:2])
            minutes = float(coord[2:])
        else:  # Longitude
            degrees = float(coord[:3])
            minutes = float(coord[3:])
        
        decimal = degrees + (minutes / 60.0)
        
        if direction in ['S', 'W']:
            decimal = -decimal
        
        return decimal

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


