"""
firmware/rover/gps_updater.py
──────────────────────────────
Background thread that continuously reads the F9P
and writes position data into the shared RoverState.

Fix persistence: if gpsd returns None between 1Hz fixes,
the last known good position is held for up to 2 seconds
before dropping to "none". This prevents flickering on the
dashboard while still accurately reflecting a real loss of fix.
"""

import threading
import time
import logging
from firmware.rover.gps import GPS
from firmware.rover.state import rover_state

log = logging.getLogger(__name__)

FIX_MAP = {0: "none", 1: "gps", 2: "dgps", 4: "rtk_fixed", 5: "rtk_float"}

# How long to hold the last good fix before dropping to "none"
FIX_HOLD_SECS = 2.0


def _gps_loop(gps):
    last_good_pos = None
    last_good_time = 0.0

    while True:
        try:
            pos = gps.position()

            if pos and pos.fix_quality > 0:
                # Good fix — update state and record time
                last_good_pos  = pos
                last_good_time = time.time()

                rover_state.update(
                    gps_available  = True,
                    gps_fix        = FIX_MAP.get(pos.fix_quality, "gps"),
                    gps_lat        = pos.lat,
                    gps_lon        = pos.lon,
                    gps_alt        = pos.alt,
                    gps_speed      = pos.speed,
                    gps_heading    = pos.heading,
                    gps_satellites = pos.satellites,
                    gps_hdop       = pos.hdop,
                )

            else:
                # No fix from gpsd — hold last good position if recent enough
                age = time.time() - last_good_time

                if last_good_pos and age < FIX_HOLD_SECS:
                    # Still within hold window — keep showing last position
                    # but don't update — just leave state as-is
                    pass
                else:
                    # Truly no fix
                    rover_state.update(
                        gps_available  = True,
                        gps_fix        = "none",
                        gps_satellites = 0,
                        gps_hdop       = 99.9,
                    )

        except Exception as e:
            log.warning(f"GPS updater error: {e}")
            rover_state.update(gps_available=False, gps_fix="none")

        time.sleep(0.1)  # poll at 10Hz, F9P outputs at 1Hz


def start_gps_updater():
    gps = GPS()
    rover_state.update(gps_available=gps.is_available())
    if not gps.is_available():
        log.warning("GPS not available — state will show gps_available=False")
        return
    t = threading.Thread(
        target=_gps_loop, args=(gps,),
        daemon=True, name="gps-updater"
    )
    t.start()
    log.info("GPS updater thread started")