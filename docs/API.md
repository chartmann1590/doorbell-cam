# DoorbellCam — API Reference

Base URL: `http://<hub-ip>:8765`. All JSON unless noted. The web dashboard
(`webui/src/api.ts`) and phone app (`app/lib/hub_client.dart`) are the
reference clients.

## Hub

| Method | Path | Description |
|---|---|---|
| GET | `/api/hub-info` | Hub identity: `product`, `version`, `camera_ip`, `camera_online`, `uptime_s`, `fcm` — used by app auto-discovery |
| GET | `/api/status` | Full live state: camera IP/online, motion %, person count, faces, last event, tuning, camera sensor block |
| GET | `/` | Serves the built dashboard (`webui/dist/index.html`) or a fallback hint |

## Camera (proxied to the ESP32)

| Method | Path | Description |
|---|---|---|
| GET | `/api/camera/stream` | MJPEG multipart fan-out shared by all viewers |
| GET | `/api/camera/snapshot` | Latest frame as `image/jpeg` (503 if none yet) |
| POST | `/api/camera/control?var=<name>&val=<n>` | Sensor control (framesize, quality, brightness, contrast, saturation, special_effect, vflip, hmirror, awb, agc, aec, dcw, raw_gma, lenc, flash) |
| GET | `/api/camera/status` | Raw sensor state from the camera (`/status`) |

Camera-native endpoints (hit the ESP32 directly, port 80 unless noted):

| Method | Path | Description |
|---|---|---|
| GET | `/api/whoami` | Identity marker `{"product":"doorbellcam",…}` — discovery probe target |
| GET | `/status` | Sensor + WiFi + doorbell state |
| GET | `/control?var=&val=` | Same vars as above, CameraWebServer-compatible |
| GET | `/capture` | Single JPEG capture |
| GET | `/api/doorbell` | `{"doorbell":0/1}` latch polled by the hub every second |
| GET | `:81/api/stream` | Raw MJPEG stream (hub relays it as `/api/camera/stream`) |

## Events

| Method | Path | Description |
|---|---|---|
| GET | `/api/events?limit=100&offset=0&kind=` | Newest-first list; `kind` filters `person \| face \| motion \| doorbell` |
| DELETE | `/api/events/{id}` | Delete one event |
| DELETE | `/api/events` | Delete all events |
| GET | `/api/events/{id}/snapshot` | Event snapshot as `image/jpeg` (404 if none/missing) |

Event object:

```json
{
  "id": 12, "ts": 1728234567.0, "kind": "face",
  "confidence": 0.93, "label": "Alice",
  "snapshot": "snapshots/face-20241006-120101.jpg",
  "boxes": []
}
```

## Faces

| Method | Path | Description |
|---|---|---|
| GET | `/api/faces` | Enrolled people: `[{id, name, created_at, updated_at}]` |
| POST | `/api/faces` | Enroll: multipart form `name` + `image` (needs a detectable face; 400 otherwise) |
| DELETE | `/api/faces/{name}` | Remove enrollment |

## Settings

| Method | Path | Description |
|---|---|---|
| GET | `/api/settings` | Merged live + persisted tuning |
| POST | `/api/settings` | JSON patch of known keys; unknown keys ignored; values persist to SQLite |

Known keys: `motion_sensitivity` (1–100), `cooldown_seconds` (2–120),
`person_confidence` (0.1–0.95), `face_match_threshold` (0.2–0.8),
`notify_websocket` (bool), `notify_fcm` (bool).

## WebSocket (`/api/ws`)

Connect to `ws://<hub-ip>:8765/api/ws`. The server sends
`{"type":"hello","hub":"doorbellhub","camera_online":…}` on connect, then one
JSON message per detection event:

```json
{
  "id": 12, "kind": "face", "label": "Alice", "confidence": 0.93,
  "snapshot": "snapshots/face-20241006-120101.jpg",
  "ts": 1728234567.0, "person_count": 1,
  "faces": [{"name": "Alice", "similarity": 0.71}]
}
```

Clients auto-reconnect with backoff (dashboard: 2 s; app: stream re-subscribes
on rebuild). Set `notify_websocket: false` to mute socket fan-out.

## Downloads

| Method | Path | Description |
|---|---|---|
| GET/HEAD | `/downloads/app-release.apk` | Android APK copied to `data/downloads/` (404 until built — see `docs/TECHNICAL.md`) |
