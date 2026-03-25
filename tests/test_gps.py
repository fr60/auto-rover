#!/usr/bin/env python3

"""
test_gps.py
───────────
Run this on the Pi to verify the F9P is working.

    python3 test_gps.py

You should see:
  - GPS status (available / NullGPS)
  - Fix quality updating as satellites are acquired
  - Lat/lon once a fix is obtained (takes 30-90s outdoors)
"""

import sys
import time
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

sys.path.insert(0, "/home/pi/rover")   # adjust if your path differs

from rover.gps import GPS

def main():
    print("\n── Rover GPS test ─────────────────────────────")
    gps = GPS()
    print(f"GPS object: {gps}")
    print(f"Available:  {gps.is_available()}")
    print("───────────────────────────────────────────────\n")

    if not gps.is_available():

        print("GPS is not available (NullGPS).")
        print("Check:")
        print("  1. F9P is plugged into a USB port")
        print("  2. gpsd is running:  sudo systemctl status gpsd")
        print("  3. Device detected:  ls /dev/ttyACM*")
        return

    print("Waiting for fix — take the Pi outside or near a window.")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            pos = gps.position()
            if pos is None:
                fix_modes = {0: "no fix", 2: "2D fix", 3: "3D fix",
                             4: "RTK fixed", 5: "RTK float"}
                print("  Searching for satellites...", end="\r")

            else:
                quality = {0:"no fix", 1:"GPS", 2:"DGPS",
                           4:"RTK fixed", 5:"RTK float"}.get(pos.fix_quality, "?")
                print(
                    f"  Lat: {pos.lat:+.7f}  "
                    f"Lon: {pos.lon:+.7f}  "
                    f"Alt: {pos.alt:.1f}m  "
                    f"Fix: {quality}  "
                    f"Sats: {pos.satellites}  "
                    f"HDOP: {pos.hdop:.1f}  "
                    f"Speed: {pos.speed:.2f}m/s"
                )
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopped.")

if __name__ == "__main__":
    main()