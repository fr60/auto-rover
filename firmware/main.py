"""
firmware/main.py
────────────────
Rover firmware entry point.
Started by systemd rover.service on boot.
 
Modes (explicit switch command):
  MANUAL    — keyboard control over SSH
  AUTOPILOT — GPS waypoint navigation
  IDLE      — motors stopped, sensors running
"""
 
import time
import logging
import sys
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def main():
    log.info("Rover firmware starting...")
 
    # Sensor arbiter decides best available mode
    from firmware.rover.arbiter import Arbiter
    arbiter = Arbiter()
    arbiter.report()
 
    log.info("Ready. Waiting for mode command.")
    log.info("  Type 'manual'   to start keyboard control")
    log.info("  Type 'auto'     to start autopilot")
    log.info("  Type 'idle'     to stop motors")
    log.info("  Type 'status'   to show sensor status")
    log.info("  Type 'quit'     to exit")


    while True:
        try:
            cmd = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            log.info("Shutting down.")
            sys.exit(0)
 
        if cmd == "manual":
            log.info("Switching to MANUAL mode")
            # from rover.manual import run_manual
            # run_manual(arbiter)
            log.info("(manual.py not yet implemented)")
 
        elif cmd in ("auto", "autopilot"):
            log.info("Switching to AUTOPILOT mode")
            # from rover.autopilot import run_autopilot
            # run_autopilot(arbiter)
            log.info("(autopilot.py not yet implemented)")
 
        elif cmd == "idle":
            log.info("IDLE — motors stopped")
 
        elif cmd == "status":
            arbiter.report()
 
        elif cmd == "quit":
            log.info("Shutting down.")
            sys.exit(0)
 
        else:
            log.warning(f"Unknown command: '{cmd}'")
 
 
if __name__ == "__main__":
    main()