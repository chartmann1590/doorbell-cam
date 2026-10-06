"""Notification fan-out: WebSocket broadcast + optional FCM push."""
import asyncio
import json
import logging
import threading
from typing import Optional

from . import state
from .config import settings

log = logging.getLogger("doorbell.notify")

# Websocket connections registered by the API layer (asyncio queues)
ws_clients: list = []
ws_lock = threading.Lock()

# Set by main.py once the event loop is running, used to schedule coroutines
loop: Optional[asyncio.AbstractEventLoop] = None

# Optional FCM
_fcm_available = False
_fcm = None

try:
    from firebase_admin import credentials, messaging
    import firebase_admin
    _fcm_mod = True
except ImportError:
    _fcm_mod = False


def init_fcm() -> bool:
    """Initialize firebase_admin if a service-account file is configured."""
    global _fcm_available, _fcm
    if not _fcm_mod or not settings.FCM_SERVICE_ACCOUNT:
        return False
    try:
        cred = credentials.Certificate(settings.FCM_SERVICE_ACCOUNT)
        firebase_admin.initialize_app(cred)
        _fcm_available = True
        log.info("FCM initialized via %s", settings.FCM_SERVICE_ACCOUNT)
    except Exception as e:  # noqa: BLE001
        log.warning("FCM init failed: %s", e)
    return _fcm_available


def register_ws_queue(q) -> None:
    with ws_lock:
        ws_clients.append(q)


def unregister_ws_queue(q) -> None:
    with ws_lock:
        if q in ws_clients:
            ws_clients.remove(q)


async def broadcast_ws(message: dict) -> None:
    """Push a JSON message to every connected websocket client."""
    if not state.tuning["notify_websocket"]:
        return
    with ws_lock:
        clients = list(ws_clients)
    payload = json.dumps(message)
    for q in clients:
        try:
            await q.put(payload)
        except Exception:  # noqa: BLE001
            unregister_ws_queue(q)


def push_event(event: dict) -> None:
    """Called from the detection thread; schedules async fan-out + FCM."""
    if loop is not None:
        asyncio.run_coroutine_threadsafe(broadcast_ws(event), loop)
    if _fcm_available and state.tuning["notify_fcm"]:
        threading.Thread(target=_send_fcm, args=(event,), daemon=True).start()


def _send_fcm(event: dict) -> None:
    try:
        from firebase_admin import messaging
        title = "DoorbellCam"
        body = f"{event['kind'].capitalize()} detected"
        if event.get("label"):
            body += f": {event['label']}"
        messaging.send(messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={"event": json.dumps(event)},
            topic="doorbell",
        ))
        log.info("FCM push sent for event %s", event.get("id"))
    except Exception as e:  # noqa: BLE001
        log.warning("FCM send failed: %s", e)
