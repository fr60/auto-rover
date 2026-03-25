#!/usr/bin/env python3
"""
tests/test_gps.py
─────────────────
Verify the F9P is working and getting a fix.
 
Run on the Pi:
    cd ~/rover-project
    python3 tests/test_gps.py
"""
 
import sys
import time
import logging
import socket
from firmware.rover.gps import GPS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
 
 
def main():
    print("\n── GPS test ───────────────────────────────────")
    gps = GPS()
    print(f"GPS object:  {gps}")
    print(f"Available:   {gps.is_available()}")
    print("───────────────────────────────────────────────\n")
 
    if not gps.is_available():
        print("GPS unavailable. Check:")
        print("  1. F9P plugged into USB")
        print("  2. sudo systemctl status gpsd")
        print("  3. ls /dev/ttyACM*")
        return
 
    print("Waiting for fix — go near a window or outside.")
    print("Ctrl+C to stop.\n")
 
    try:
        while True:
            pos = gps.position()
            if pos is None:
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
                    f"HDOP: {pos.hdop:.1f}"
                )
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")

    print("\n── Raw GPS data test ──────────────────────────")
    HOST = "localhost"
    PORT = 3002

    print(f"Reading raw GPS data from {HOST}:{PORT}")
    print("Press Ctrl+C to stop.\n")

    try:
        with socket.create_connection((HOST, PORT), timeout=5) as sock:
            while True:
                data = sock.recv(1024).decode(errors='ignore')
                print(data, end='')
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"Error: {e}")
 
if __name__ == "__main__":
    main()
