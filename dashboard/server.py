"""
dashboard/server.py
────────────────────
FastAPI dashboard server running on the Pi.

Architecture:
- State JSON sent at 10Hz over WebSocket
- Camera frames sent only when previous frame has been drained
  (drop-on-busy — never queue frames, prevents buffer backup)
- Blocking camera capture runs in thread executor
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


# ── Camera ────────────────────────────────────────────────────
_camera = None

def get_camera():
    global _camera
    if _camera is None:
        _camera = Camera()
        rover_state.update(camera_available=_camera.is_available())
    return _camera


def _capture_jpeg(cam) -> bytes | None:
    """Blocking call — always run via run_in_executor."""
    frame = cam.frame()
    if frame is None:
        return None
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
    return buf.tobytes() if ok else None


# ── Dashboard HTML ────────────────────────────────────────────
DASHBOARD_HTML = Path(__file__).parent / "index.html"

@app.get("/", response_class=HTMLResponse)
async def index():
    if DASHBOARD_HTML.exists():
        return HTMLResponse(DASHBOARD_HTML.read_text())
    return HTMLResponse("<h2>index.html not found</h2>")


# ── WebSocket ─────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    log.info("Dashboard connected")

    cam         = get_camera()
    loop        = asyncio.get_event_loop()
    frame_times = []
    frame_busy  = False   # True while a frame send is in flight

    # Tickers
    last_state_send = 0.0
    STATE_INTERVAL  = 0.1    # 10Hz state
    FRAME_INTERVAL  = 0.05   # attempt frame every 50ms (up to 20fps)
    last_frame_attempt = 0.0

    try:
        while True:
            now = time.monotonic()

            # ── State update at 10Hz ──────────────────────────
            if now - last_state_send >= STATE_INTERVAL:
                await ws.send_text(json.dumps(rover_state.get()))
                last_state_send = now

            # ── Camera frame — drop if busy, never queue ──────
            if (cam.is_available()
                    and not frame_busy
                    and now - last_frame_attempt >= FRAME_INTERVAL):

                last_frame_attempt = now
                frame_busy = True

                async def send_frame():
                    nonlocal frame_busy
                    try:
                        jpg = await loop.run_in_executor(
                            None, _capture_jpeg, cam
                        )
                        if jpg:
                            await ws.send_bytes(jpg)
                            t = time.time()
                            frame_times.append(t)
                            # Keep only last 1 second of timestamps
                            while frame_times and t - frame_times[0] > 1.0:
                                frame_times.pop(0)
                            rover_state.update(camera_fps=len(frame_times))
                    except Exception:
                        pass
                    finally:
                        frame_busy = False

                asyncio.ensure_future(send_frame())

            # ── Incoming commands ─────────────────────────────
            try:
                data = await asyncio.wait_for(
                    ws.receive_text(), timeout=0.01
                )
                await _handle_command(json.loads(data))
            except asyncio.TimeoutError:
                pass

            await asyncio.sleep(0.01)  # 100Hz loop, non-blocking

    except WebSocketDisconnect:
        log.info("Dashboard disconnected")
    except Exception as e:
        log.warning(f"WebSocket error: {e}")


async def _handle_command(msg: dict):
    cmd = msg.get("cmd")
    if cmd == "mode":
        rover_state.update(mode=msg.get("mode", "idle"))
        log.info(f"Mode → {msg.get('mode')}")
    elif cmd == "drive":
        _apply_drive(msg.get("key", " "))


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


# ── MJPEG fallback ────────────────────────────────────────────
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
                + buf.tobytes() + b"\r\n"
            )
        time.sleep(0.033)


@app.get("/stream")
async def camera_stream():
    return StreamingResponse(
        _mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ── REST endpoints ────────────────────────────────────────────
@app.post("/mode/{name}")
async def set_mode(name: str):
    if name not in ("manual", "autopilot", "idle"):
        return JSONResponse({"error": "invalid mode"}, status_code=400)
    rover_state.update(mode=name)
    return {"mode": name}


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

@app.get("/state")
async def get_state():
    return rover_state.get()


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    import socket
    ip = socket.gethostbyname(socket.gethostname())
    log.info(f"Dashboard → http://{ip}:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")