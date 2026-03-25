#!/usr/bin/env python3
"""
tests/test_motors.py
─────────────────────
Test each motor direction individually.
Run BEFORE mounting on chassis — hold motors in hand.
 
Run on the Pi:
    sudo pigpiod          (must be running)
    cd ~/rover-project
    python3 tests/test_motors.py
"""
 
import sys
import time
 
sys.path.insert(0, "firmware")
 
from firmware.rover.motors import Motors, WheelSpeeds
 
def pause(msg, secs=1.5):
    print(f"  {msg}")
    time.sleep(secs)
 
def main():
    print("\n── Motor test ─────────────────────────────────")
    print("  Make sure pigpiod is running: sudo pigpiod")
    print("  Hold motors safely before proceeding.\n")
    input("  Press Enter to start...")
 
    m = Motors()
 
    try:
        pause("Forward...")
        m.forward(0.4)
        time.sleep(1.5)
        m.stop()
        pause("Stop.", 0.5)
 
        pause("Backward...")
        m.backward(0.4)
        time.sleep(1.5)
        m.stop()
        pause("Stop.", 0.5)
 
        pause("Turn left...")
        m.turn_left(0.4)
        time.sleep(1.5)
        m.stop()
        pause("Stop.", 0.5)
 
        pause("Turn right...")
        m.turn_right(0.4)
        time.sleep(1.5)
        m.stop()
        pause("Stop.", 0.5)
 
        pause("Strafe left (mecanum)...")
        m.strafe_left(0.4)
        time.sleep(1.5)
        m.stop()
        pause("Stop.", 0.5)
 
        pause("Strafe right (mecanum)...")
        m.strafe_right(0.4)
        time.sleep(1.5)
        m.stop()
 
        print("\n  All movements complete.")
 
    except KeyboardInterrupt:
        print("\n  Interrupted.")
    finally:
        m.shutdown()
        print("  Motors shut down.")
 
if __name__ == "__main__":
    main()