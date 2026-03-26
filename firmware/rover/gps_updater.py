"""
firmware/rover/gps_updater.py
──────────────────────────────
Background thread that continuously reads the F9P
and writes position data into the shared RoverState.
 
Usage:
    from firmware.rover.gps_updater import start_gps_updater
    start_gps_updater()   # call once at startup
"""

import threading
import time
import logging
from firmware.rover.gps import GPS
from firmware.rover.state import rover_state

log = logging.getLogger(__name__)

FIX_MAP = {0: "none", 1: "gps", 2: "dgps", 4: "rtk_fixed", 5: "rtk_float"}


def _gps_loop(gps):
    while True:
        try:
            pos = gps.position()
            if pos:
                rover_state.update(
                    gps_available   = True,
                    gps_fix         = FIX_MAP.get(pos.fix_quality, "gps"),
                    gps_lat         = pos.lat,
                    gps_lon         = pos.lon,
                    gps_alt         = pos.alt,
                    gps_speed       = pos.speed,
                    gps_heading     = pos.heading,
                    gps_satellites  = pos.satellites,
                    gps_hdop        = pos.hdop,
                )
            else:
                rover_state.update(gps_available=True, gps_fix="none")
        except Exception as e:
            log.warning(f"GPS updater error: {e}")
            rover_state.update(gps_available=False)
        time.sleep(0.1)  # 10Hz
 
 
def start_gps_updater():
    gps = GPS()
    rover_state.update(gps_available=gps.is_available())
    if not gps.is_available():
        log.warning("GPS not available — state will show gps_available=False")
        return
    t = threading.Thread(target=_gps_loop, args=(gps,), daemon=True, name="gps-updater")
    t.start()
    log.info("GPS updater thread started")