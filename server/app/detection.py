"""Detection worker: motion -> person -> face recognition pipeline.

Runs in its own thread, consuming JPEG frames pushed by the MJPEG client.
Motion gating keeps the expensive DNN passes idle when nothing changes.
"""
import logging
import threading
import time
from typing import Optional

import cv2
import numpy as np

from . import state, store
from .config import settings

log = logging.getLogger("doorbell.detection")

PERSON_IDX = 15  # COCO class index for "person" in MobileNet-SSD
CLASSES = ("background", "aeroplane", "bicycle", "bird", "boat", "bottle",
           "bus", "car", "cat", "chair", "cow", "diningtable", "dog",
           "horse", "motorbike", "person", "pottedplant", "sheep", "sofa",
           "train", "tvmonitor")


class Detector:
    def __init__(self) -> None:
        self.motion_prev: Optional[np.ndarray] = None
        self.last_event_ts = 0.0
        self.cool_until = 0.0
        self.net = None
        self.face_detector = None
        self.face_recog = None
        self.known_faces: dict[str, list[float]] = {}
        self._load_models()

    # ------------------------------------------------------------ models
    def _load_models(self) -> None:
        models = settings.MODELS_DIR
        proto = models / "MobileNetSSD_deploy.prototxt"
        weights = models / "MobileNetSSD_deploy.caffemodel"
        if proto.exists() and weights.exists():
            try:
                self.net = cv2.dnn.readNetFromCaffe(str(proto), str(weights))
                log.info("Loaded MobileNet-SSD person detector")
            except Exception as e:  # noqa: BLE001
                log.warning("Failed to load MobileNet-SSD: %s", e)

        yunet = models / "face_detection_yunet_2023mar.onnx"
        sface = models / "face_recognition_sface_2021dec.onnx"
        if yunet.exists() and sface.exists():
            try:
                self.face_detector = cv2.FaceDetectorYN.create(str(yunet), "", (320, 320), 0.6)
                self.face_recog = cv2.FaceRecognizerSF.create(str(sface), "")
                log.info("Loaded YuNet + SFace models")
            except Exception as e:  # noqa: BLE001
                log.warning("Failed to load face models: %s", e)

        self.refresh_known_faces()

    def refresh_known_faces(self) -> None:
        try:
            self.known_faces = store.get_face_embeddings()
        except Exception as e:  # noqa: BLE001
            log.warning("Could not load face embeddings: %s", e)

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _jpeg_to_bgr(jpeg: bytes) -> Optional[np.ndarray]:
        arr = np.frombuffer(jpeg, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def _motion_level(self, frame: np.ndarray) -> float:
        small = cv2.resize(frame, (160, 120))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        if self.motion_prev is None:
            self.motion_prev = gray
            return 0.0
        diff = cv2.absdiff(gray, self.motion_prev)
        self.motion_prev = gray
        _, thresh = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)
        level = float(np.count_nonzero(thresh)) / thresh.size * 100.0
        return level

    def _detect_persons(self, frame: np.ndarray) -> list[dict]:
        if self.net is None:
            return []
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)),
                                     0.007843, (300, 300), 127.5)
        self.net.setInput(blob)
        out = self.net.forward()[0, 0]
        conf_threshold = state.tuning["person_confidence"]
        results = []
        for det in out:
            conf = float(det[2])
            cls = int(det[1])
            if cls == PERSON_IDX and conf >= conf_threshold:
                box = [int(det[i] * w) for i in (3, 4)] + \
                      [int(det[i] * w) for i in (5, 6)]
                results.append({"box": box, "confidence": conf, "label": "person"})
        return results

    def _detect_faces(self, frame: np.ndarray) -> list[dict]:
        if self.face_detector is None:
            return []
        h, w = frame.shape[:2]
        self.face_detector.setInputSize((w, h))
        _, faces = self.face_detector.detect(frame)
        out = []
        if faces is not None:
            for f in faces:
                x, y, bw, bh = [int(v) for v in f[:4]]
                out.append({"box": [x, y, bw, bh], "confidence": float(f[14])})
        return out

    def _recognize(self, frame: np.ndarray, face_box: list[int]) -> tuple[Optional[str], float]:
        if self.face_recog is None:
            return None, 0.0
        x, y, w, h = face_box
        crop = frame[max(0, y):y + h, max(0, x):x + w]
        if crop.size == 0:
            return None, 0.0
        aligned = cv2.resize(crop, (112, 112))
        # cv2.FaceRecognizerSF wants the aligned BGR image directly
        emb = self.face_recog.feature(aligned).flatten()
        if emb is None or emb.size == 0:
            return None, 0.0
        best_name, best_sim = None, 0.0
        for name, known in self.known_faces.items():
            known_arr = np.array(known, dtype=np.float32)
            sim = float(np.dot(emb, known_arr) /
                        (np.linalg.norm(emb) * np.linalg.norm(known_arr) + 1e-8))
            if sim > best_sim:
                best_name, best_sim = name, sim
        if best_sim >= state.tuning["face_match_threshold"]:
            return best_name, best_sim
        return None, best_sim

    # ------------------------------------------------------------ main loop
    def process_frame(self, jpeg: bytes) -> None:
        frame = self._jpeg_to_bgr(jpeg)
        if frame is None:
            return

        level = self._motion_level(frame)
        with state.state_lock:
            state.state["motion_level"] = round(level, 2)
            state.state["last_frame_ts"] = time.time()
        state.note_motion(level)

        now = time.time()
        gate = now < self.cool_until
        persons: list[dict] = []
        faces: list[dict] = []

        # Motion gate: only run DNN when something moves (or every 5s idle sweep)
        if not gate or (now - self.last_event_ts) > 5:
            persons = self._detect_persons(frame)
            if persons:
                faces = self._detect_faces(frame)

        with state.state_lock:
            state.state["person_count"] = len(persons)
            state.state["faces"] = faces
            state.state["detections"] = persons + [
                {**f, "label": "face"} for f in faces]
            state.state["detections_ts"] = now

        if persons or faces:
            self._maybe_fire_event(persons, faces, frame, level)

    def _maybe_fire_event(self, persons, faces, frame, level) -> None:
        now = time.time()
        cooldown = state.tuning["cooldown_seconds"]
        if now < self.cool_until:
            return

        named = [(f, None) for f in faces]
        if named:
            for f in faces:
                name, sim = self._recognize(frame, f["box"])
                if name:
                    f["name"] = name
                    f["similarity"] = round(sim, 3)

        kind = "face" if any("name" in f for f in faces) else "person"
        label = ", ".join(f["name"] for f in faces if "name" in f)
        conf = max([p["confidence"] for p in persons], default=0.0)

        snap_path = self._save_snapshot(frame, kind)
        event_id = store.add_event(kind=kind, confidence=round(conf, 3),
                                   label=label, snapshot=snap_path,
                                   boxes=state.state["detections"])
        self.cool_until = now + cooldown
        self.last_event_ts = now

        event = {
            "id": event_id, "kind": kind, "label": label,
            "confidence": round(conf, 3), "snapshot": snap_path,
            "ts": now, "person_count": len(persons),
            "faces": [{"name": f.get("name"), "similarity": f.get("similarity")}
                      for f in faces],
        }
        with state.state_lock:
            state.state["last_event"] = event

        # fan out: websockets + FCM (both implemented in notify.py)
        from .notify import push_event
        push_event(event)

    def _save_snapshot(self, frame, kind) -> str:
        ts = time.strftime("%Y%m%d-%H%M%S")
        path = settings.SNAPSHOTS_DIR / f"{kind}-{ts}.jpg"
        cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        return str(path.relative_to(settings.DATA_DIR))
