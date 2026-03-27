"""
dashboard/server.py
────────────────────
FastAPI server running on the Pi.
Serves the dashboard UI and provides:
  - WebSocket  /ws           — pushes rover state at 10Hz
  - GET        /stream       — MJPEG camera stream
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
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from firmware.rover.state import rover_state
from firmware.rover.camera import Camera

log = logging.getLogger("dashboard")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

# ── App ───────────────────────────────────────────────────────
app = FastAPI(title="Rover dashboard")


@app.on_event("startup")
async def startup():
    """Start background sensor updater threads when server boots."""
    from firmware.rover.gps_updater import start_gps_updater
    start_gps_updater()
    start_camera()
    log.info("GPS updater and camera thread started")

# ── Camera frame buffer ───────────────────────────────────────
# Background thread captures + encodes frames continuously.
# WebSocket just grabs the latest pre-encoded frame — no blocking.
import threading as _threading

_latest_frame: bytes | None = None
_frame_lock   = _threading.Lock()
_camera       = None


def _camera_capture_loop():
    import cv2
    global _latest_frame, _camera

    _camera = Camera()
    rover_state.update(camera_available=_camera.is_available())

    if not _camera.is_available():
        log.warning("Camera not available — frame buffer idle")
        return

    frame_times = []
    log.info("Camera capture thread started")

    while True:
        frame = _camera.frame()
        if frame is None:
            time.sleep(0.01)
            continue

        ok, buf = cv2.imencode(
            ".jpg", frame,
            [cv2.IMWRITE_JPEG_QUALITY, 70]
        )
        if ok:
            with _frame_lock:
                _latest_frame = buf.tobytes()

        now = time.time()
        frame_times.append(now)
        frame_times = [t for t in frame_times if now - t < 1.0]
        rover_state.update(camera_fps=len(frame_times))

        time.sleep(0.033)  # ~30fps cap


def get_latest_frame() -> bytes | None:
    with _frame_lock:
        return _latest_frame


def start_camera():
    t = _threading.Thread(
        target=_camera_capture_loop,
        daemon=True,
        name="camera-capture"
    )
    t.start()


# ── Dashboard HTML page ───────────────────────────────────────
DASHBOARD_HTML = Path(__file__).parent / "index.html"

@app.get("/", response_class=HTMLResponse)
async def index():
    if DASHBOARD_HTML.exists():
        return HTMLResponse(DASHBOARD_HTML.read_text())
    return HTMLResponse("<h2>Dashboard HTML not found.</h2>")


# ── WebSocket — state push at 10Hz ────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        log.info(f"Dashboard connected ({len(self.active)} clients)")

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)
        log.info(f"Dashboard disconnected ({len(self.active)} clients)")

    async def broadcast(self, data: dict):
        msg = json.dumps(data)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Push state as JSON at 10Hz
            await ws.send_text(json.dumps(rover_state.get()))

            # Push latest pre-encoded frame every tick (~20fps over WiFi)
            frame_bytes = _get_frame_bytes()
            if frame_bytes:
                await ws.send_bytes(frame_bytes)

            # Handle incoming commands (non-blocking)
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=0.05)
                await handle_command(json.loads(data))
            except asyncio.TimeoutError:
                pass

            await asyncio.sleep(0.05)  # 20Hz

    except WebSocketDisconnect:
        manager.disconnect(ws)


async def handle_command(msg: dict):
    """Handle commands sent from the dashboard."""
    cmd = msg.get("cmd")

    if cmd == "mode":
        new_mode = msg.get("mode", "idle")
        rover_state.update(mode=new_mode)
        log.info(f"Mode → {new_mode}")

    elif cmd == "drive":
        key = msg.get("key")
        _apply_drive_command(key)

    elif cmd == "stop":
        rover_state.update(
            mode="idle",
            motor_fl=0, motor_fr=0, motor_rl=0, motor_rr=0
        )


def _apply_drive_command(key: str):
    """Map WASD keys to motor speeds in state."""
    spd = 0.5
    cmds = {
        "w": dict(motor_fl=spd,  motor_fr=spd,  motor_rl=spd,  motor_rr=spd),
        "s": dict(motor_fl=-spd, motor_fr=-spd, motor_rl=-spd, motor_rr=-spd),
        "a": dict(motor_fl=-spd, motor_fr=spd,  motor_rl=-spd, motor_rr=spd),
        "d": dict(motor_fl=spd,  motor_fr=-spd, motor_rl=spd,  motor_rr=-spd),
        "q": dict(motor_fl=-spd, motor_fr=spd,  motor_rl=spd,  motor_rr=-spd),  # strafe left
        "e": dict(motor_fl=spd,  motor_fr=-spd, motor_rl=-spd, motor_rr=spd),   # strafe right
        " ": dict(motor_fl=0,    motor_fr=0,    motor_rl=0,    motor_rr=0),      # stop
    }
    if key in cmds:
        rover_state.update(**cmds[key])


# ── Frame encoder (shared by WebSocket and MJPEG) ────────────────
def _get_frame_bytes() -> bytes | None:
    """Return the latest pre-encoded frame from the capture thread."""
    return get_latest_frame()


# ── MJPEG camera stream (kept as fallback) ────────────────────
def _mjpeg_generator():
    import cv2
    cam = get_camera()
    if not cam.is_available():
        return

    frame_times = []

    while True:
        frame = cam.frame()
        if frame is None:
            time.sleep(0.033)
            continue

        # Track FPS
        now = time.time()
        frame_times.append(now)
        frame_times = [t for t in frame_times if now - t < 1.0]
        rover_state.update(camera_fps=len(frame_times))

        # Encode to JPEG
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not ok:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + buf.tobytes()
            + b"\r\n"
        )
        time.sleep(0.033)  # ~30fps cap


@app.get("/stream")
async def camera_stream():
    return StreamingResponse(
        _mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ── Mode endpoint (REST fallback) ─────────────────────────────
@app.post("/mode/{name}")
async def set_mode(name: str):
    if name not in ("manual", "autopilot", "idle"):
        return JSONResponse({"error": "invalid mode"}, status_code=400)
    rover_state.update(mode=name)
    log.info(f"Mode → {name}")
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
    log.info(f"Waypoints saved ({len(data.get('waypoints', []))} points)")
    return {"saved": True}


# ── State endpoint (REST, for debugging) ──────────────────────
@app.get("/state")
async def get_state():
    return rover_state.get()


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    log.info("Starting rover dashboard server...")
    log.info("Open http://<PI_IP>:8000 on your laptop")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")