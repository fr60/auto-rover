"""
firmware/rover/motors.py
────────────────────────
DRV8833 PWM motor controller for 4WD mecanum chassis.
 
Two DRV8833 boards, each driving two motors:
  DRV8833 A → Front-Left (FL) + Front-Right (FR)
  DRV8833 B → Rear-Left  (RL) + Rear-Right  (RR)
 
Speed values are floats in range -1.0 (full reverse) to +1.0 (full forward).
GPIO pin numbers are loaded from config/config.yaml.
"""
 
import logging
from dataclasses import dataclass
 
log = logging.getLogger(__name__)
 
# GPIO pin assignments — loaded from config.yaml at runtime
# These match the wiring diagram we designed
DEFAULT_PINS = {
    "FL_IN1": 12,   # DRV8833 A
    "FL_IN2": 13,
    "FR_IN3": 16,
    "FR_IN4": 20,
    "RL_IN1": 24,   # DRV8833 B
    "RL_IN2": 25,
    "RR_IN3": 26,
    "RR_IN4": 27,
}
 
PWM_FREQ = 1000   # Hz
 
 
@dataclass
class WheelSpeeds:
    fl: float = 0.0   # front-left   -1.0 to +1.0
    fr: float = 0.0   # front-right
    rl: float = 0.0   # rear-left
    rr: float = 0.0   # rear-right
 
 
class Motors:
    def __init__(self, pins: dict = None):
        self._pins = pins or DEFAULT_PINS
        self._pwm = {}
        self._setup_gpio()
 
    def _setup_gpio(self):
        import pigpio
        self._pi = pigpio.pi()
        if not self._pi.connected:
            raise RuntimeError("pigpio daemon not running — run: sudo pigpiod")
        for name, pin in self._pins.items():
            self._pi.set_mode(pin, pigpio.OUTPUT)
            self._pi.write(pin, 0)
        log.info(f"Motors initialised on GPIO pins: {self._pins}")
 
    def _set_motor(self, in1_pin: int, in2_pin: int, speed: float):
        """Drive one motor channel. speed -1.0 to +1.0."""
        speed = max(-1.0, min(1.0, speed))   # clamp
        duty  = int(abs(speed) * 255)         # 0-255 for pigpio
 
        if speed > 0:
            self._pi.set_PWM_dutycycle(in1_pin, duty)
            self._pi.set_PWM_dutycycle(in2_pin, 0)
        elif speed < 0:
            self._pi.set_PWM_dutycycle(in1_pin, 0)
            self._pi.set_PWM_dutycycle(in2_pin, duty)
        else:
            self._pi.set_PWM_dutycycle(in1_pin, 0)
            self._pi.set_PWM_dutycycle(in2_pin, 0)
 
    def set(self, speeds: WheelSpeeds):
        """Set all four wheel speeds simultaneously."""
        self._set_motor(self._pins["FL_IN1"], self._pins["FL_IN2"], speeds.fl)
        self._set_motor(self._pins["FR_IN3"], self._pins["FR_IN4"], speeds.fr)
        self._set_motor(self._pins["RL_IN1"], self._pins["RL_IN2"], speeds.rl)
        self._set_motor(self._pins["RR_IN3"], self._pins["RR_IN4"], speeds.rr)
 
    def stop(self):
        self.set(WheelSpeeds())
        log.info("Motors stopped")
 
    # ── Mecanum movement helpers ──────────────────────────────
 
    def forward(self, speed: float = 0.5):
        self.set(WheelSpeeds(fl=speed, fr=speed, rl=speed, rr=speed))
 
    def backward(self, speed: float = 0.5):
        self.set(WheelSpeeds(fl=-speed, fr=-speed, rl=-speed, rr=-speed))
 
    def turn_left(self, speed: float = 0.5):
        self.set(WheelSpeeds(fl=-speed, fr=speed, rl=-speed, rr=speed))
 
    def turn_right(self, speed: float = 0.5):
        self.set(WheelSpeeds(fl=speed, fr=-speed, rl=speed, rr=-speed))
 
    def strafe_left(self, speed: float = 0.5):
        """Mecanum-only: slide directly left."""
        self.set(WheelSpeeds(fl=-speed, fr=speed, rl=speed, rr=-speed))
 
    def strafe_right(self, speed: float = 0.5):
        """Mecanum-only: slide directly right."""
        self.set(WheelSpeeds(fl=speed, fr=-speed, rl=-speed, rr=speed))
 
    def shutdown(self):
        self.stop()
        self._pi.stop()