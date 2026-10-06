# DoorbellCam — ESP32-CAM wireless doorbell with person & face detection

A privacy-first, self-hosted smart doorbell: an AI-Thinker **ESP32-CAM** streams over your
WiFi to a local **hub** (FastAPI + OpenCV) that detects **motion → people → faces**,
stores **events with snapshots**, pushes **instant notifications** to a **Flutter** Android
app and a polished **React** web dashboard — with zero cloud dependencies.

```
ESP32-CAM ──WiFi──▶ Hub (this PC / NAS) ──WebSocket/REST──▶ Web dashboard + Android app
```

## What you need
- ESP32-CAM (AI-Thinker) with the MB USB adapter (CH340)
- A computer on the same WiFi network (Windows / macOS / Linux) — or any always-on box
- Optional: Android phone for the companion app

## Quickstart
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

## Layout
| Path | What it is |
|---|---|
| `firmware/doorbell_cam` | Arduino sketch: WiFi, mDNS, MJPEG stream, camera settings API |
| `server/app/` | FastAPI hub: discovery, stream fanout, detection, events, WebSocket, FCM |
| `webui/` | React + Vite dashboard (live view, events, faces, settings) |
| `app/` | Flutter companion app (auto-discovery, live view, notifications, settings) |
| `scripts/` | `setup.py`, `flash.py`, `gen_secrets.py`, `run.py`, `enable_fcm.py` |
| `.env` | Your secrets (WiFi, serial port) — **gitignored** |
| `.env.example` | Committed template with documentation |

## How auto-discovery works
1. **Camera → hub:** firmware advertises `doorbellcam.local` (mDNS `_doorbellcam._tcp`).
   Hub tries mDNS browse → parallel HTTP probe of the /24 for `/api/whoami` → `.env` fallback.
2. **App → hub:** hub advertises `doorbellhub.local` (mDNS `_doorbellhub._http._tcp`).
   App uses Bonsoir (mDNS) → subnet probe for `/api/hub-info` → manual entry (remembered).

## Remote access (away from home)
Zero-config with Tailscale: install on the PC running the hub and on your phone, then the
app reaches the hub over the tailnet. Notifications use the same persistent WebSocket.

## FCM (optional cloud push)
Off by default. Run `python scripts/enable_fcm.py` and follow the printed steps
(create a Firebase project, add an Android app, place `google-services.json` and a
service-account JSON). The backend reads it automatically on next restart.

## Docker (Linux/NAS deployment)
`docker compose up --build` — uses `network_mode: host` so mDNS works. On Windows, run the
hub natively (Docker Desktop's VM cannot participate in LAN multicast; subnet-scan discovery
still works from a container but mDNS does not).

## Privacy
Video never leaves your network. Events and face encodings stay in `data/` on your machine.
