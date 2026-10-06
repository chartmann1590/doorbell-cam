"""DoorbellCam hub — FastAPI application.

Serves:
  - REST API for events, faces, settings, camera control proxy
  - /api/ws          WebSocket for live events
  - /api/camera/stream  MJPEG fanout of the camera feed
  - /webui/dist      React dashboard (production)
"""
import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

import cv2
import numpy as np
import requests
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
import zeroconf
from zeroconf import ServiceInfo, Zeroconf

from . import notify, state, store
from .config import settings
from .detection import Detector
from .discovery import discover_camera
from .stream import MjpegClient, broadcaster

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("doorbell.main")

detector: Detector = None
cam_ip: str = None
mjpeg: MjpegClient = None
zc: Zeroconf = None

camera_control_lock = asyncio.Lock()
_stream_recycled_at = 0.0


# ------------------------------------------------------------------ lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    global detector, cam_ip, mjpeg, zc
    notify.loop = asyncio.get_running_loop()

    # start discovery
    log.info("Discovering camera…")
    cam_ip = discover_camera()
    if cam_ip:
        log.info("Camera found at %s", cam_ip)
        state.state["camera_ip"] = cam_ip
        state.state["camera_online"] = True
    else:
        log.warning("Camera not found — will retry in background")

    detector = Detector()
    detector.refresh_known_faces()
    load_persisted_tuning()

    if cam_ip:
        mjpeg = MjpegClient(cam_ip, on_frame=on_frame)
        mjpeg.start()

    _register_mdns()

    # background camera watchdog + doorbell poller
    task = asyncio.create_task(camera_watchdog())
    db_task = asyncio.create_task(doorbell_poller())
    yield
    task.cancel()
    db_task.cancel()
    if mjpeg:
        mjpeg.stop()
    if zc:
        zc.unregister_service(info)
        zc.close()


info: ServiceInfo = None


def _register_mdns() -> None:
    global zc, info
    try:
        zc = Zeroconf()
        local_ip = _get_lan_ip()
        info = ServiceInfo(
            "_doorbellhub._http._tcp.local.",
            "doorbellhub._doorbellhub._http._tcp.local.",
            parsed_addresses=[local_ip],
            port=settings.HUB_PORT,
            properties={"product": "doorbellhub", "path": "/api/hub-info"},
        )
        zc.register_service(info)
        log.info("mDNS: doorbellhub.local advertised on %s:%d", local_ip,
                 settings.HUB_PORT)
    except Exception as e:  # noqa: BLE001
        log.warning("mDNS registration failed: %s", e)


def _get_lan_ip() -> str:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:  # noqa: BLE001
        return "127.0.0.1"
    finally:
        s.close()


def on_frame(jpeg: bytes) -> None:
    """Called from the MJPEG client thread for every camera frame."""
    state.set_frame(jpeg)
    broadcaster.publish(jpeg)
    try:
        detector.process_frame(jpeg)
    except Exception:  # noqa: BLE001
        log.exception("detection error")


async def camera_watchdog() -> None:
    """Re-discover the camera if the stream dies."""
    global cam_ip, mjpeg, _stream_recycled_at
    while True:
        await asyncio.sleep(10)
        with state.state_lock:
            online = (time.time() - state.state["last_frame_ts"]) < 15
        if online:
            state.state["camera_online"] = True
            continue

        client_alive = bool(mjpeg and mjpeg._thread and mjpeg._thread.is_alive())

        # Stream silent — but is the camera itself still up? A quick /status
        # probe separates "the stream client needs a fresh connection" (stay
        # online, just recycle) from a genuine outage (full rediscovery).
        reachable = False
        if cam_ip:
            try:
                r = await asyncio.to_thread(
                    requests.get, f"http://{cam_ip}/status", timeout=2.0)
                reachable = r.ok
            except Exception:  # noqa: BLE001
                reachable = False

        if reachable:
            state.state["camera_online"] = True
            # Recycle at most once per ~20 s so a genuinely wedged client is
            # retried without hammering the camera's single-core web server.
            if not client_alive or time.time() - _stream_recycled_at > 20:
                log.info("Stream silent — recycling stream client for %s", cam_ip)
                _stream_recycled_at = time.time()
                if mjpeg:
                    mjpeg.stop()
                mjpeg = MjpegClient(cam_ip, on_frame=on_frame)
                mjpeg.start()
            continue

        state.state["camera_online"] = False
        if client_alive and cam_ip:
            # client thread runs but yields no frames — camera likely rebooted
            # into the same IP; recycle the client so it reconnects.
            log.info("Stream silent — recycling stream client for %s", cam_ip)
            mjpeg.stop()
            mjpeg = None

        log.info("Camera offline — rediscovering…")
        try:
            ip = await asyncio.to_thread(discover_camera)
        except Exception:  # noqa: BLE001
            log.exception("rediscovery failed")
            continue
        if not ip:
            continue

        # Recreate the client if it is missing, its thread has died, or the
        # camera moved to a new IP. (A dead client with an unchanged IP used
        # to fall through both branches and was never replaced.)
        client_dead = (mjpeg is None
                       or not (mjpeg._thread and mjpeg._thread.is_alive()))
        if client_dead or ip != cam_ip:
            if mjpeg:
                mjpeg.stop()
            cam_ip = ip
            state.state["camera_ip"] = ip
            mjpeg = MjpegClient(ip, on_frame=on_frame)
            mjpeg.start()


async def doorbell_poller() -> None:
    """Poll the camera's doorbell button flag and fire events on presses.

    The firmware latches a press (active-LOW GPIO13) and holds it ~2s, so a
    1s poll cannot miss one. Cooldown is applied hub-side as well.
    """
    global cam_ip
    last_press = 0.0
    while True:
        await asyncio.sleep(1)
        if not cam_ip:
            continue
        try:
            r = await asyncio.to_thread(requests.get,
                                        f"http://{cam_ip}/api/doorbell",
                                        timeout=1.0)
            if r.ok and r.json().get("doorbell") == 1 and time.time() - last_press > 10:
                last_press = time.time()
                log.info("Doorbell pressed!")
                snap = None
                frame = state.get_frame()
                if frame:
                    ts = time.strftime("%Y%m%d-%H%M%S")
                    path = settings.SNAPSHOTS_DIR / f"doorbell-{ts}.jpg"
                    await asyncio.to_thread(
                        cv2.imwrite, str(path), cv2.imdecode(
                            np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR))
                    snap = str(path.relative_to(settings.DATA_DIR))
                event_id = store.add_event(kind="doorbell", confidence=1.0,
                                           label="Doorbell pressed", snapshot=snap or "")
                event = {"id": event_id, "kind": "doorbell",
                         "label": "Doorbell pressed", "confidence": 1.0,
                         "snapshot": snap or "", "ts": time.time(),
                         "person_count": 0, "faces": []}
                with state.state_lock:
                    state.state["last_event"] = event
                notify.push_event(event)
        except Exception:  # noqa: BLE001
            pass  # camera momentarily unreachable — next tick retries


# ------------------------------------------------------------------ app
app = FastAPI(title="DoorbellCam Hub", lifespan=lifespan)


@app.get("/api/hub-info")
async def hub_info():
    return {
        "product": "doorbellhub",
        "version": "1.0.0",
        "camera_ip": state.state.get("camera_ip"),
        "camera_online": state.state["camera_online"],
        "uptime_s": int(time.time() - state.state["started_at"]),
        "fcm": notify._fcm_available,
    }


@app.get("/api/status")
async def status():
    with state.state_lock:
        st = dict(state.state)
    st["tuning"] = dict(state.tuning)
    if cam_ip:
        try:
            r = requests.get(f"http://{cam_ip}/status", timeout=1.5)
            if r.ok:
                st["camera"] = r.json()
        except Exception:  # noqa: BLE001
            st["camera"] = None
    return st


# ------------------------------------------------------------------ camera proxy
@app.get("/api/camera/stream")
async def camera_stream():
    """Fan out the camera MJPEG to any number of viewers."""
    async def gen():
        q = broadcaster.register()
        try:
            while True:
                frame = await asyncio.to_thread(q.get)
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       b"%d\r\n\r\n" % len(frame)) + frame + b"\r\n"
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unregister(q)

    return StreamingResponse(gen(),
                             media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/camera/snapshot")
async def camera_snapshot():
    frame = state.get_frame()
    if frame is None:
        raise HTTPException(503, "no frame available")
    return Response(frame, media_type="image/jpeg")


@app.post("/api/camera/control")
async def camera_control(var: str, val: int):
    """Proxy a control command to the camera (CameraWebServer compatible)."""
    global cam_ip
    if not cam_ip:
        raise HTTPException(503, "camera offline")
    async with camera_control_lock:
        try:
            r = await asyncio.to_thread(
                requests.get,
                f"http://{cam_ip}/control?var={var}&val={val}", timeout=2.0)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(502, f"camera unreachable: {e}")
    if not r.ok:
        raise HTTPException(502, f"camera rejected: {r.text}")
    return r.json()


@app.get("/api/camera/status")
async def camera_status():
    if not cam_ip:
        raise HTTPException(503, "camera offline")
    try:
        r = await asyncio.to_thread(requests.get, f"http://{cam_ip}/status",
                                    timeout=2.0)
        return r.json()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"camera unreachable: {e}")


# ------------------------------------------------------------------ events
@app.get("/api/events")
async def events(limit: int = 100, offset: int = 0, kind: str = None):
    return store.list_events(limit=limit, offset=offset, kind=kind)


@app.delete("/api/events/{event_id}")
async def delete_event(event_id: int):
    store.delete_event(event_id)
    return {"ok": True}


@app.delete("/api/events")
async def clear_events():
    store.clear_events()
    return {"ok": True}


@app.get("/api/events/{event_id}/snapshot")
async def event_snapshot(event_id: int):
    evs = [e for e in store.list_events(limit=1000) if e["id"] == event_id]
    if not evs:
        raise HTTPException(404, "event not found")
    snap = evs[0].get("snapshot")
    if not snap:
        raise HTTPException(404, "no snapshot")
    path = settings.DATA_DIR / snap
    if not path.exists():
        raise HTTPException(404, "snapshot file missing")
    return Response(path.read_bytes(), media_type="image/jpeg")


# ------------------------------------------------------------------ faces
@app.get("/api/faces")
async def faces_list():
    return store.list_faces()


@app.post("/api/faces")
async def faces_enroll(name: str = Form(...), image: UploadFile = File(...)):
    data = await image.read()
    arr = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(400, "invalid image")
    faces = detector._detect_faces(frame) if detector else []
    if not faces:
        raise HTTPException(400, "no face found in image")
    box = faces[0]["box"]
    emb = detector.face_recog.feature(cv2.resize(
        frame[box[1]:box[1]+box[3], box[0]:box[0]+box[2]], (112, 112))).flatten()
    store.upsert_face(name, emb.tolist())
    detector.refresh_known_faces()
    return {"ok": True, "name": name}


@app.delete("/api/faces/{name}")
async def faces_delete(name: str):
    ok = store.delete_face(name)
    if detector:
        detector.refresh_known_faces()
    if not ok:
        raise HTTPException(404, "face not found")
    return {"ok": True}


# ------------------------------------------------------------------ settings
def _coerce_tuning(key: str, value):
    """Convert a stored string back to the type used in state.tuning."""
    ref = state.tuning.get(key)
    try:
        if isinstance(ref, bool):
            return str(value).lower() in ("1", "true", "yes", "on")
        if isinstance(ref, float):
            return float(value)
        if isinstance(ref, int):
            return int(float(value))
    except (TypeError, ValueError):
        pass
    return value


def load_persisted_tuning() -> None:
    """Apply settings stored in SQLite to the live tuning dict (on boot)."""
    for k, v in store.get_all_settings().items():
        if k in state.tuning:
            state.tuning[k] = _coerce_tuning(k, v)


@app.get("/api/settings")
async def get_settings():
    persisted = store.get_all_settings()
    merged = dict(state.tuning)
    for k, v in persisted.items():
        if k in state.tuning:
            merged[k] = _coerce_tuning(k, v)
    return merged


@app.post("/api/settings")
async def update_settings(request: Request):
    body = await request.json()
    for k, v in body.items():
        if k in state.tuning:
            state.tuning[k] = v
            store.set_setting(k, str(v))
    return state.tuning


# ------------------------------------------------------------------ websocket
@app.websocket("/api/ws")
async def ws_endpoint(websocket: WebSocket):
    q = asyncio.Queue()
    notify.register_ws_queue(q)
    try:
        await websocket.accept()
        # send a hello so clients can confirm the connection
        await websocket.send_json({"type": "hello",
                                   "hub": "doorbellhub",
                                   "camera_online": state.state["camera_online"]})
        while True:
            msg = await q.get()
            await websocket.send_text(msg)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        notify.unregister_ws_queue(q)


# ------------------------------------------------------------------ static UI
@app.get("/")
async def index():
    dist = settings.ROOT / "webui" / "dist"
    if (dist / "index.html").exists():
        return HTMLResponse((dist / "index.html").read_text())
    return HTMLResponse("<h1>DoorbellCam hub running</h1>"
                        "<p>Build the dashboard: <code>cd webui && npm ci && npm run build</code></p>")


# mount assets if the dashboard is built
_dist = settings.ROOT / "webui" / "dist"
if (_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="assets")

notify.init_fcm()
