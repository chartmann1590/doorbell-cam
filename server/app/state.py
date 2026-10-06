"""Shared state between the FastAPI app and the detection worker thread."""
import threading
import time
from collections import deque
from typing import Optional

# Live detection state (read by API, written by worker)
state_lock = threading.Lock()
state: dict = {
    "camera_ip": None,
    "camera_online": False,
    "last_frame_ts": 0.0,
    "motion_level": 0.0,
    "fps": 0.0,
    "person_count": 0,
    "faces": [],          # [{name, similarity, box}]
    "last_event": None,   # {id, kind, label, ts}
    "detections": [],     # latest frame's detection boxes for overlay
    "detections_ts": 0.0,
    "started_at": time.time(),
}

# Threads waiting for new frames: each gets its own asyncio.Queue
frame_queues: list = []
frame_queues_lock = threading.Lock()

# Detection tuning (runtime-editable via /api/settings)
tuning_lock = threading.Lock()
tuning: dict = {
    "motion_sensitivity": 25,   # 0..100, higher = more sensitive
    "cooldown_seconds": 15,
    "person_confidence": 0.5,
    "face_match_threshold": 0.42,
    "notify_websocket": True,
    "notify_fcm": True,
}

# Latest MJPEG frame (jpeg bytes) + a monotonic counter
frame_lock = threading.Lock()
latest_frame: Optional[bytes] = None
frame_counter: int = 0


def set_frame(jpeg: bytes) -> None:
    global latest_frame, frame_counter
    with frame_lock:
        latest_frame = jpeg
        frame_counter += 1


def get_frame() -> Optional[bytes]:
    with frame_lock:
        return latest_frame


# Small ring buffer of recent detection summaries for the UI sparkline
recent_motion: deque = deque(maxlen=120)


def note_motion(level: float) -> None:
    with state_lock:
        recent_motion.append((time.time(), level))
