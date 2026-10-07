# DoorbellCam — Technical Guide

For makers and developers. The customer-facing overview lives in the root
`README.md`; this file covers installation, architecture, and maintenance.

## Contents

- [1. What you need](#1-what-you-need)
- [2. First-time setup](#2-first-time-setup)
- [3. Running the hub](#3-running-the-hub)
- [4. How the pieces fit](#4-how-the-pieces-fit)
- [5. Configuration reference (`.env`)](#5-configuration-reference-env)
- [6. Phone app](#6-phone-app)
- [7. Remote access & push notifications](#7-remote-access--push-notifications)
- [8. Docker](#8-docker)
- [9. Troubleshooting](#9-troubleshooting)
- [10. Repository layout](#10-repository-layout)

---

## 1. What you need

- AI-Thinker ESP32-CAM + MB USB adapter (CH340).
- A computer on the same 2.4 GHz WiFi network (Windows / macOS / Linux),
  or any always-on box — this runs the hub.
- Optional: Android phone for the companion app.
- Optional: physical doorbell button wired to GPIO13 (active-LOW, to GND).

> The ESP32-CAM only sees 2.4 GHz networks. If your router merges bands
> under one name, confirm the module can see the SSID or create a dedicated
> 2.4 GHz SSID.

## 2. First-time setup

```bash
# 1. Configure (first time only)
cp .env.example .env      # then edit: WiFi SSID/password, serial port

# 2. One-time setup: toolchains, Python deps, models, firmware secrets
python scripts/setup.py

# 3. Flash the camera (ESP32-CAM plugged in via USB)
python scripts/flash.py

# 4. Run the hub + dashboard  →  http://localhost:8765
python scripts/run.py
#    (or: cd server && uvicorn app.main:app --host 0.0.0.0 --port 8765)

# 5. Android app
flutter run                # from the app/ directory
```

Script reference:

| Script | Purpose |
|---|---|
| `scripts/setup.py` | Installs Python deps, arduino-cli + ESP32 core, downloads detection models (MobileNet-SSD, YuNet, SFace), creates `.env` from template |
| `scripts/gen_secrets.py` | Generates `firmware/doorbell_cam/secrets.h` from `.env` (WiFi credentials never committed) |
| `scripts/flash.py` | Regenerates secrets, auto-detects the USB programmer (never COM1), compiles + uploads with retries |
| `scripts/monitor.py` | Serial console at 115200 baud (wraps `detect_serial_port`) |
| `scripts/run.py` | Launches uvicorn on `HUB_PORT` from `.env` |
| `scripts/enable_fcm.py` | Interactive helper that wires a Firebase service-account path into `.env` |

## 3. Running the hub

- Native: `python scripts/run.py`, dashboard at `http://localhost:8765`
  (use the PC's LAN IP from a phone, e.g. `http://192.168.1.10:8765`).
- The hub auto-discovers the camera: mDNS `_doorbellcam._tcp` browse →
  `doorbellcam.local` resolve → /24 subnet probe for `/api/whoami` →
  pinned `CAM_IP` fallback.
- Detection pipeline per frame: motion gate → MobileNet-SSD person pass
  (default confidence 0.7) → YuNet face detect → SFace recognition against
  enrolled embeddings. Events persist to SQLite (`data/doorbell.db`) with
  JPEG snapshots in `data/snapshots/`.
- Live tuning persists via `GET/POST /api/settings` (backed by the
  `settings` table, coerced to live types on boot).

## 4. How the pieces fit

```
ESP32-CAM ──WiFi──▶ Hub (FastAPI + OpenCV) ──WebSocket/REST──▶ Web dashboard + Android app
```

| Path | What it is |
|---|---|
| `firmware/doorbell_cam/doorbell_cam.ino` | Camera firmware: WiFi + setup AP, MJPEG stream task (port 81), CameraWebServer-compatible `/control` + `/status`, `/api/whoami` identity, GPIO13 doorbell latch |
| `firmware/cam_diag/cam_diag.ino` | SCCB bus-scan diagnostic for "camera init FAILED" boards |
| `server/app/` | Hub: `main.py` (FastAPI + lifespan), `detection.py` (motion→person→face), `discovery.py`, `stream.py` (MJPEG client + fan-out), `store.py` (SQLite), `state.py` (shared state), `notify.py` (WS + FCM), `config.py` (`.env` loader) |
| `webui/` | React + Vite dashboard (Live, Events, Faces, Settings) |
| `app/` | Flutter companion app (auto-discovery, live view, notifications) — see `app/README.md` |

## 5. Configuration reference (`.env`)

All keys are documented in `.env.example`. Highlights:

| Key | Default | Notes |
|---|---|---|
| `WIFI_SSID` / `WIFI_PASSWORD` | — | 2.4 GHz network for the camera |
| `CAM_BOARD` | `ai_thinker` | `ai_thinker \| wrover_kit \| esp_wrover_kit \| esp32cam_probe` |
| `SERIAL_PORT` | `AUTO` | Auto-detects CH340/CP210x/FTDI; pin only with several devices |
| `HUB_PORT` | `8765` | Hub + dashboard port |
| `CAM_IP` | empty | Pinned camera IP — tried first; **required** under Docker |
| `LOCAL_SUBNET` | empty | e.g. `192.168.1.0/24`; auto-detected if empty |
| `MOTION_SENSITIVITY` | `25` | 0–100, higher = more sensitive |
| `COOLDOWN_SECONDS` | `15` | Minimum gap between events |
| `FACE_MATCH_THRESHOLD` | `0.42` | SFace cosine-similarity threshold |
| `MODELS_DIR` | `./tools/models` | Anchored to project root |
| `FCM_SERVICE_ACCOUNT` | empty | Path to Firebase service-account JSON (optional push) |
| `TZ_OFFSET_HOURS` | `0` | Event timestamp offset |

Secrets (`.env`, `firmware/doorbell_cam/secrets.h`, `*.key.json`,
`*service-account*`, `google-services.json`) are gitignored — see
`.gitignore`. Never commit real credentials.

## 6. Phone app

Build once and let the hub serve it:

```bash
cd app && flutter build apk --release
cp build/app/outputs/flutter-apk/app-release.apk ../data/downloads/
```

The dashboard header's **Get the app** button downloads
`http://<hub-ip>:8765/downloads/app-release.apk` — open it on the phone to
install. The app finds the hub via mDNS (`doorbellhub.local`, advertised by
the hub with zeroconf) → subnet probe for `/api/hub-info` → remembered
manual entry. Details in `app/README.md`.

## 7. Remote access & push notifications

- **Away from home:** install Tailscale on the hub PC and the phone; the app
  reaches the hub over the tailnet and alerts use the same WebSocket.
- **FCM (optional cloud push):** off by default. Run
  `python scripts/enable_fcm.py` and follow the printed steps (create a
  Firebase project, add Android app `com.doorbellcam.app`, place
  `google-services.json` in `app/android/app/`, save the service-account
  JSON, restart the hub). The backend (`notify.py`) picks it up
  automatically; per-client toggles live under Settings
  (`notify_websocket`, `notify_fcm`).

## 8. Docker

Set `CAM_IP=<camera-ip>` in `.env`, stop any natively-running hub (port
clash), then:

```bash
docker compose up --build -d
```

Bridge networking publishes 8765 to the host; container mDNS cannot see the
LAN, so `CAM_IP` is how the container finds the camera (tried first when
set). `data/` and `tools/models` are mounted, so events and the APK route
work as natively. `docker compose down` stops it. See `docker-compose.yml`
and `server/Dockerfile` (multi-stage: builds webui, then runs uvicorn).

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `camera init FAILED` on serial | Flash `firmware/cam_diag/cam_diag.ino`, open the serial monitor (`python scripts/monitor.py`): expect ACK at `0x30`. No ACKs = reseat/check power to the sensor |
| Flash upload fails | Swap to a data USB cable / different port, rerun `python scripts/flash.py` (auto-retries 4×, re-detects port) |
| Camera offline in dashboard | Check camera power + 2.4 GHz WiFi; set `CAM_IP` in `.env`; the watchdog re-discovers every 10 s |
| False "person" alerts | Raise Settings → Person confidence (0.7 default; static vertical objects scored ~0.5 in testing) |
| APK download 404 | Copy the built APK to `data/downloads/app-release.apk` (section 6) |
| Port 8765 in use | Stop the native hub before `docker compose up`, or change `HUB_PORT` |

## 10. Repository layout

```
firmware/doorbell_cam/  camera firmware (secrets.h is generated, gitignored)
firmware/cam_diag/      SCCB diagnostic sketch
server/app/             hub (FastAPI + OpenCV pipeline)
server/Dockerfile       multi-stage hub image
server/requirements.txt pinned Python deps
webui/src/              React dashboard (api.ts, App.tsx, pages/, components/)
app/lib/                Flutter app (discovery, client, screens)
scripts/                setup / flash / run / monitor / gen_secrets / enable_fcm
docs/                   this guide + API reference
data/                   gitignored runtime state (db, snapshots, logs, APK)
tools/                  gitignored toolchains + downloaded models
```

Video never leaves your network. Events and face data stay in `data/` on
your machine. See `docs/API.md` for the full REST + WebSocket reference.
