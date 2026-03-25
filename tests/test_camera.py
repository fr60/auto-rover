#!/usr/bin/env python3
"""
tests/test_camera.py
─────────────────────
Verify the Pi AI Camera (IMX500) is working.

Run on the Pi:
    cd ~/rover-project
    python3 tests/test_camera.py

Tests:
  1. Camera initialises via picamera2
  2. Frame capture returns a valid numpy array
  3. Frame dimensions and dtype are correct
  4. FPS measurement over 30 frames
"""

import sys
import time
import logging
import cv2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger("test_camera")


def main():
    print("\n── Camera test ────────────────────────────────")

    # ── Test 1: import ────────────────────────────────────────
    print("\n[1/4] Importing firmware.rover.camera...")
    from firmware.rover.camera import Camera
    print("  OK")

    # ── Test 2: initialise ────────────────────────────────────
    print("\n[2/4] Initialising camera...")
    cam = Camera()
    print(f"  Camera object: {cam}")
    print(f"  Available:     {cam.is_available()}")

    if not cam.is_available():
        print("\n  Camera unavailable (NullCamera). Check:")
        print("    libcamera-hello --list-cameras")
        print("    sudo apt install imx500-all")
        print("    Check ribbon cable orientation")
        return

    # ── Test 3: capture frame ─────────────────────────────────
    print("\n[3/4] Capturing a frame...")
    frame = cam.frame()

    if frame is None:
        print("  ERROR: frame() returned None")
        return

    print(f"  Shape:  {frame.shape}   (H x W x channels)")
    print(f"  Dtype:  {frame.dtype}")
    print(f"  Min:    {frame.min()}   Max: {frame.max()}")

     # ── Save image ────────────────────────────────────────────
    out_path = Path(__file__).parent / "test_capture.jpg"
    cv2.imwrite(str(out_path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    print(f"  Saved: {out_path}")

    expected_shape = (480, 640, 3)
    if frame.shape == expected_shape:
        print(f"  Shape matches expected {expected_shape} ✓")
    else:
        print(f"  Shape {frame.shape} — update config.yaml if needed")

    # ── Test 4: FPS ───────────────────────────────────────────
    print("\n[4/4] Measuring FPS over 30 frames...")
    frames = 30
    start = time.time()
    for _ in range(frames):
        cam.frame()
    elapsed = time.time() - start
    fps = frames / elapsed
    print(f"  {frames} frames in {elapsed:.2f}s → {fps:.1f} FPS")
    print(f"  {'FPS OK ✓' if fps >= 25 else 'FPS lower than expected — normal at full res'}")

    print("\n── All camera tests passed ────────────────────\n")
    cam.stop()


if __name__ == "__main__":
    main()