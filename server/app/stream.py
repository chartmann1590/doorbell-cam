"""MJPEG client: pulls frames from the ESP32-CAM and fans them out to clients."""
import logging
import queue
import threading
import time
from typing import Callable, Optional

import requests

from . import state

log = logging.getLogger("doorbell.stream")


class MjpegClient:
    """Connects to http://<ip>:81/api/stream, decodes multipart JPEG frames and
    hands each to a callback. Auto-reconnects with backoff."""

    def __init__(self, ip: str, on_frame: Callable[[bytes], None]):
        self.ip = ip
        self.on_frame = on_frame
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="mjpeg-client")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        backoff = 1.0
        url = f"http://{self.ip}:81/api/stream"
        while not self._stop.is_set():
            try:
                log.info("Connecting to stream %s", url)
                with requests.get(url, stream=True, timeout=(3, 10)) as r:
                    r.raise_for_status()
                    backoff = 1.0
                    buf = bytearray()
                    for chunk in r.iter_content(chunk_size=8192):
                        if self._stop.is_set():
                            break
                        buf.extend(chunk)
                        while True:
                            frame = self._extract_frame(buf)
                            if frame is None:
                                break
                            self.on_frame(frame)
            except Exception as e:  # noqa: BLE001
                log.warning("Stream error (%s); retrying in %.1fs", e, backoff)
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 15.0)

    @staticmethod
    def _extract_frame(buf: bytearray) -> Optional[bytes]:
        start = buf.find(b"\xff\xd8")          # SOI
        if start < 0:
            if len(buf) > 256 * 1024:
                buf.clear()
            return None
        end = buf.find(b"\xff\xd9", start)     # EOI
        if end < 0:
            if start > 0:
                del buf[:start]
            if len(buf) > 2 * 1024 * 1024:
                buf.clear()
            return None
        frame = bytes(buf[start:end + 2])
        del buf[:end + 2]
        return frame


class FrameBroadcaster:
    """Distributes the latest frame to every registered async consumer."""

    def __init__(self):
        self._queues: list[queue.Queue] = []
        self._lock = threading.Lock()

    def register(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=4)
        with self._lock:
            self._queues.append(q)
        return q

    def unregister(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._queues:
                self._queues.remove(q)

    def publish(self, frame: bytes) -> None:
        with self._lock:
            queues = list(self._queues)
        for q in queues:
            try:
                q.put_nowait(frame)
            except queue.Full:
                try:
                    q.get_nowait()      # drop oldest, keep newest
                    q.put_nowait(frame)
                except Exception:  # noqa: BLE001
                    pass


broadcaster = FrameBroadcaster()
