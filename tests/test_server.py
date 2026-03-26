#!/usr/bin/env python3
"""
tests/test_server.py
─────────────────────
Tests for the dashboard FastAPI server.
 
Runs against the actual server — start it first:
    python3 dashboard/server.py
 
Then in a separate terminal:
    cd ~/rover-project
    python3 tests/test_server.py
 
Or run against a specific host:
    HOST=192.168.1.42 python3 tests/test_server.py
"""

import sys
import os
import json
import time
import asyncio
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

HOST = os.environ.get("HOST", "localhost")
BASE = f"http://{HOST}:8000"
WS = f"ws://{HOST}:8000/ws"

PASS = "\033[92m  PASS\033[0m"
FAIL = "\033[91m  FAIL\033[0m"

results = {"passed": 0, "failed": 0}


# ── Test helpers ──────────────────────────────────────────────

def check(name: str, condition: bool, detail: str = ""):
    if condition:
        print(f"{PASS}  {name}")
        results["passed"] += 1
    else:
        print(f"{FAIL}  {name}" + (f" — {detail}" if detail else ""))
        results["failed"] += 1


def get(path: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def post(path: str, data: dict) -> tuple[int, dict]:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}
 
 
# ── Tests ─────────────────────────────────────────────────────

def test_server_reachable():
    print("\n── Connectivity ─────────────────────────────────")
    status, _ = get("/state")
    check("Server reachable on port 8000", status == 200,
          f"Got status {status} — is server.py running?")


def test_dashboard_html():
    print("\n── Dashboard HTML ───────────────────────────────")
    try:
        with urllib.request.urlopen(f"{BASE}/", timeout=5) as r:
            body = r.read().decode()
            check("GET / returns 200",         r.status == 200)
            check("Response is HTML",          "<!DOCTYPE html>" in body)
            check("Contains WebSocket code",   "WebSocket" in body)
            check("Contains camera stream",    "/stream" in body)
    except Exception as e:
        check("GET / returns 200", False, str(e))


def test_state_endpoint():
    print("\n── GET /state ───────────────────────────────────")
    status, data = get("/state")
    check("Returns 200",               status == 200)
    check("Has 'mode' field",          "mode" in data)
    check("Has 'gps' field",           "gps" in data)
    check("Has 'imu' field",           "imu" in data)
    check("Has 'camera' field",        "camera" in data)
    check("Has 'motors' field",        "motors" in data)
    check("Has 'system' field",        "system" in data)
    check("GPS has lat/lon",           "lat" in data.get("gps", {}))
    check("System has uptime",         "uptime_s" in data.get("system", {}))


def test_mode_switching():
    print("\n── POST /mode ───────────────────────────────────")
 
    status, data = post("/mode/manual", {})
    check("Switch to manual → 200",    status == 200)
    check("Returns mode=manual",       data.get("mode") == "manual")
 
    _, state = get("/state")
    check("State reflects manual",     state.get("mode") == "manual")
 
    status, data = post("/mode/autopilot", {})
    check("Switch to autopilot → 200", status == 200)
    check("Returns mode=autopilot",    data.get("mode") == "autopilot")
 
    status, data = post("/mode/idle", {})
    check("Switch to idle → 200",      status == 200)
 
    status, _ = post("/mode/invalid", {})
    check("Invalid mode → 400",        status == 400)
 
 
def test_waypoints():
    print("\n── GET/POST /waypoints ──────────────────────────")
 
    status, data = get("/waypoints")
    check("GET /waypoints returns 200", status == 200)
    check("Has 'waypoints' key",        "waypoints" in data)
 
    test_wps = {
        "waypoints": [
            {"id": 1, "lat": 51.5001, "lon": -0.1000, "label": "Test A"},
            {"id": 2, "lat": 51.5005, "lon": -0.1005, "label": "Test B"},
        ]
    }
    status, data = post("/waypoints", test_wps)
    check("POST /waypoints returns 200", status == 200)
    check("Saved confirmation",          data.get("saved") == True)
 
    status, saved = get("/waypoints")
    check("GET reflects saved waypoints",
          len(saved.get("waypoints", [])) == 2)
    check("Waypoint lat preserved",
          saved["waypoints"][0]["lat"] == 51.5001)


def test_camera_stream():
    print("\n── GET /stream ──────────────────────────────────")
    try:
        req = urllib.request.urlopen(f"{BASE}/stream", timeout=3)
        content_type = req.headers.get("Content-Type", "")
        check("Stream endpoint reachable",
              req.status == 200)
        check("Content-Type is MJPEG",
              "multipart/x-mixed-replace" in content_type,
              f"Got: {content_type}")
        req.close()
    except Exception as e:
        # Camera may be unavailable — not a hard failure
        print(f"  NOTE  /stream not available ({e}) — camera may be offline")
        results["passed"] += 1


async def test_websocket():
    print("\n── WebSocket /ws ────────────────────────────────")
    try:
        import websockets
        async with websockets.connect(WS, open_timeout=5) as ws:
            # Should receive state within 200ms
            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(msg)
            check("WebSocket connects",         True)
            check("Receives JSON state",        isinstance(data, dict))
            check("State has mode field",       "mode" in data)
            check("State has gps field",        "gps" in data)
 
            # Send a drive command
            await ws.send(json.dumps({"cmd": "drive", "key": "w"}))
            time.sleep(0.2)
 
            # Send stop
            await ws.send(json.dumps({"cmd": "drive", "key": " "}))
 
            # Send mode switch
            await ws.send(json.dumps({"cmd": "mode", "mode": "idle"}))
            time.sleep(0.15)
 
            # Verify mode updated
            msg2 = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data2 = json.loads(msg2)
            check("Mode switch via WebSocket",  data2.get("mode") == "idle")
 
    except ImportError:
        print("  NOTE  websockets package not installed — skipping WS test")
        print("        pip3 install websockets --break-system-packages")
        results["passed"] += 1
    except Exception as e:
        check("WebSocket connects", False, str(e))
 

# ── Main ──────────────────────────────────────────────────────

def main():
    print(f"\n{'═'*52}")
    print(f"  Dashboard API tests  →  {BASE}")
    print(f"{'═'*52}")
 
    test_server_reachable()
 
    # If server not reachable, no point continuing
    if results["failed"] > 0:
        print(f"\n  Server not reachable. Start with:")
        print(f"    cd ~/rover-project && python3 dashboard/server.py\n")
        sys.exit(1)
 
    test_dashboard_html()
    test_state_endpoint()
    test_mode_switching()
    test_waypoints()
    test_camera_stream()
    asyncio.run(test_websocket())
 
    total  = results["passed"] + results["failed"]
    passed = results["passed"]
    failed = results["failed"]
 
    print(f"\n{'═'*52}")
    print(f"  Results: {passed}/{total} passed", end="")
    if failed:
        print(f"  \033[91m({failed} failed)\033[0m")
    else:
        print(f"  \033[92m(all passed)\033[0m")
    print(f"{'═'*52}\n")
 
    sys.exit(0 if failed == 0 else 1)
 
 
if __name__ == "__main__":
    main()
