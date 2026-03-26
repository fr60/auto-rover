"""
firmware/rover/state.py
───────────────────────
Thread-safe shared state.
Written by firmware modules (gps, imu, motors, arbiter).
Read by the dashboard server to push to the browser.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RoverState:
    # ── Mode ──────────────────────────────────────────────────
    mode: str = "idle"              # "manual", "autopilot", "idle"

    # ── GPS ───────────────────────────────────────────────────
    gps_available: bool = False
    gps_fix: str = "none"          # "none", "gps", "dgps", "rtk_float", "rtk_fixed"
    gps_lat: float = 0.0
    gps_lon: float = 0.0
    gps_alt: float = 0.0
    gps_speed: float = 0.0
    gps_heading: float = 0.0
    gps_satellites: int = 0
    gps_hdop: float = 99.9

    # ── IMU ───────────────────────────────────────────────────
    imu_available: bool = False
    imu_heading: float = 0.0
    imu_pitch: float = 0.0
    imu_roll: float = 0.0

    # ── Camera ────────────────────────────────────────────────
    camera_available: bool = False
    camera_fps: float = 0.0

    # ── Motors ────────────────────────────────────────────────
    motors_armed: bool = False
    motor_fl: float = 0.0
    motor_fr: float = 0.0
    motor_rl: float = 0.0
    motor_rr: float = 0.0

    # ── Autopilot ─────────────────────────────────────────────
    waypoint_index: int = 0
    waypoint_total: int = 0
    distance_to_waypoint: float = 0.0
    bearing_to_waypoint: float = 0.0

    # ── System ────────────────────────────────────────────────
    uptime: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)


class SharedState:
    """
    Thread-safe wrapper around RoverState.
    Use .get() to read a snapshot, .update() to write fields.
    """
    
    def __init__(self):
        self._state = RoverState()
        self._lock = threading.Lock()

    def update(self, **kwargs):
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
                else:
                    raise AttributeError(f"RoverState has no field '{key}'")
            self._state.last_update = time.time()
 
    def get(self) -> dict:
        with self._lock:
            s = self._state
            return {
                "mode":                 s.mode,
                "gps": {
                    "available":        s.gps_available,
                    "fix":              s.gps_fix,
                    "lat":              round(s.gps_lat, 7),
                    "lon":              round(s.gps_lon, 7),
                    "alt":              round(s.gps_alt, 1),
                    "speed":            round(s.gps_speed, 2),
                    "heading":          round(s.gps_heading, 1),
                    "satellites":       s.gps_satellites,
                    "hdop":             round(s.gps_hdop, 1),
                },
                "imu": {
                    "available":        s.imu_available,
                    "heading":          round(s.imu_heading, 1),
                    "pitch":            round(s.imu_pitch, 1),
                    "roll":             round(s.imu_roll, 1),
                },
                "camera": {
                    "available":        s.camera_available,
                    "fps":              round(s.camera_fps, 1),
                },
                "motors": {
                    "armed":            s.motors_armed,
                    "fl":               round(s.motor_fl, 2),
                    "fr":               round(s.motor_fr, 2),
                    "rl":               round(s.motor_rl, 2),
                    "rr":               round(s.motor_rr, 2),
                },
                "autopilot": {
                    "waypoint_index":   s.waypoint_index,
                    "waypoint_total":   s.waypoint_total,
                    "distance_m":       round(s.distance_to_waypoint, 2),
                    "bearing_deg":      round(s.bearing_to_waypoint, 1),
                },
                "system": {
                    "uptime_s":         round(time.time() - s.uptime),
                    "last_update":      round(s.last_update, 3),
                },
            }
 
 
# ── Singleton — imported by all modules ───────────────────────
rover_state = SharedState()
