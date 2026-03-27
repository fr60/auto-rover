"""
dashboard/server.py
────────────────────
FastAPI server running on the Pi.
Serves the dashboard UI and provides:
  - WebSocket  /ws           — pushes rover state + camera frames
  - GET        /stream       — MJPEG camera stream (fallback)
  - POST       /mode/{name}  — switch mode (manual/autopilot/idle)
  - GET/POST   /waypoints    — read/write waypoints.json
  - POST       /command      — send drive command (w/a/s/d/stop)

Start with:
  cd ~/rover-project
  python3 dashboard/server.py

Then open http://<PI_IP>:8000 on your laptop.
"""

import asyncio
import json
import logging
import sys
import time
import cv2
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import uvicorn

from firmware.rover.state import rover_state
from firmware.rover.camera import Camera

log = logging.getLogger("dashboard")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(title="Rover dashboard")

# ── Startup ───────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    from firmware.rover.gps_updater import start_gps_updater
    start_gps_updater()
    log.info("GPS updater started")


# ── Camera — single instance, initialised once ────────────────
_camera = None

def get_camera():
    global _camera
    if _camera is None:
        _camera = Camera()
        rover_state.update(camera_available=_camera.is_available())
    return _camera


# ── Dashboard HTML ────────────────────────────────────────────
DASHBOARD_HTML = Path(__file__).parent / "index.html"

@app.get("/", response_class=HTMLResponse)
async def index():
    if DASHBOARD_HTML.exists():
        return HTMLResponse(DASHBOARD_HTML.read_text())
    return HTMLResponse("<h2>index.html not found</h2>")


# ── Camera helpers ───────────────────────────────────────────
def _capture_jpeg(cam) -> bytes | None:
    """Blocking — runs in thread executor, never in the event loop."""
    frame = cam.frame()
    if frame is None:
        return None
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
    return buf.tobytes() if ok else None


# ── WebSocket ─────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    log.info("Dashboard connected")

    cam = get_camera()
    frame_times = []

    try:
        while True:
            t0 = time.monotonic()

            # 1. Send state as JSON
            await ws.send_text(json.dumps(rover_state.get()))

            # 2. Send camera frame as binary if available
            if cam.is_available():
                loop = asyncio.get_event_loop()
                jpg_bytes = await loop.run_in_executor(None, _capture_jpeg, cam)
                if jpg_bytes:
                    await ws.send_bytes(jpg_bytes)
                    now = time.time()
                    frame_times.append(now)
                    frame_times = [t for t in frame_times if now - t < 1.0]
                    rover_state.update(camera_fps=len(frame_times))

            # 3. Handle incoming command (non-blocking)
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=0.01)
                await _handle_command(json.loads(data))
            except asyncio.TimeoutError:
                pass

            # 4. Maintain target rate — send as fast as camera allows
            elapsed = time.monotonic() - t0
            sleep   = max(0, 0.033 - elapsed)   # target ~30fps
            if sleep > 0:
                await asyncio.sleep(sleep)

    except WebSocketDisconnect:
        log.info("Dashboard disconnected")
    except Exception as e:
        log.warning(f"WebSocket error: {e}")


async def _handle_command(msg: dict):
    cmd = msg.get("cmd")
    if cmd == "mode":
        new_mode = msg.get("mode", "idle")
        rover_state.update(mode=new_mode)
        log.info(f"Mode → {new_mode}")
    elif cmd == "drive":
        _apply_drive(msg.get("key", " "))
    elif cmd == "stop":
        rover_state.update(motor_fl=0, motor_fr=0, motor_rl=0, motor_rr=0)


def _apply_drive(key: str):
    spd = 0.5
    cmds = {
        "w": dict(motor_fl=spd,  motor_fr=spd,  motor_rl=spd,  motor_rr=spd),
        "s": dict(motor_fl=-spd, motor_fr=-spd, motor_rl=-spd, motor_rr=-spd),
        "a": dict(motor_fl=-spd, motor_fr=spd,  motor_rl=-spd, motor_rr=spd),
        "d": dict(motor_fl=spd,  motor_fr=-spd, motor_rl=spd,  motor_rr=-spd),
        "q": dict(motor_fl=-spd, motor_fr=spd,  motor_rl=spd,  motor_rr=-spd),
        "e": dict(motor_fl=spd,  motor_fr=-spd, motor_rl=-spd, motor_rr=spd),
        " ": dict(motor_fl=0,    motor_fr=0,    motor_rl=0,    motor_rr=0),
    }
    if key in cmds:
        rover_state.update(**cmds[key])


# ── MJPEG stream (fallback / direct browser view) ─────────────
def _mjpeg_generator():
    cam = get_camera()
    if not cam.is_available():
        return
    while True:
        frame = cam.frame()
        if frame is None:
            time.sleep(0.033)
            continue
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
        if ok:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buf.tobytes()
                + b"\r\n"
            )
        time.sleep(0.033)


@app.get("/stream")
async def camera_stream():
    return StreamingResponse(
        _mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ── Mode ──────────────────────────────────────────────────────
@app.post("/mode/{name}")
async def set_mode(name: str):
    if name not in ("manual", "autopilot", "idle"):
        return JSONResponse({"error": "invalid mode"}, status_code=400)
    rover_state.update(mode=name)
    return {"mode": name}


# ── Waypoints ─────────────────────────────────────────────────
WAYPOINTS_FILE = ROOT / "config" / "waypoints.json"

@app.get("/waypoints")
async def get_waypoints():
    if WAYPOINTS_FILE.exists():
        return json.loads(WAYPOINTS_FILE.read_text())
    return {"waypoints": []}

@app.post("/waypoints")
async def save_waypoints(data: dict):
    WAYPOINTS_FILE.write_text(json.dumps(data, indent=2))
    return {"saved": True}


# ── State (debug) ─────────────────────────────────────────────
@app.get("/state")
async def get_state():
    return rover_state.get()


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    log.info("Starting rover dashboard...")
    log.info(f"Open http://$(hostname -I | cut -d' ' -f1):8000 on your laptop")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")