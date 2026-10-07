# DoorbellCam App (Android)

The companion phone app for DoorbellCam: watch your front door live, get
instant alerts when someone arrives, and tune the camera — all on your home
network, no cloud account needed.

## What it does

- **Live** — MJPEG door view with camera-online badge and person indicator.
- **Alerts** — event history (person / face / doorbell) with snapshots.
- **Settings** — detection sensitivity + camera picture controls.
- **Auto-connect** — finds the hub via mDNS (`doorbellhub.local`) → subnet
  scan → remembered address; manual IP entry as fallback (saved on device).

## Project layout

| Path | Purpose |
|---|---|
| `lib/main.dart` | Entry point: `ConnectGate` (auto-connect) → `HomeShell` tabs |
| `lib/discovery.dart` | `HubDiscovery`: raw-UDP mDNS query, /24 scan, prefs fallback |
| `lib/hub_client.dart` | Typed REST + WebSocket client (`HubClient`, `HubEvent`, `HubStatus`) |
| `lib/mjpeg.dart` | `MjpegView`: multipart JPEG parser + renderer |
| `lib/notify.dart` | `Notify`: local high-priority alert notifications |
| `lib/screens/` | `live.dart`, `events.dart`, `settings_screen.dart` tab pages |
| `test/widget_test.dart` | Connect-gate smoke test |

## Build & run

```bash
cd app
flutter pub get
flutter run            # debug on a connected device
flutter build apk --release   # outputs app-release.apk
```

Copy the release APK to the hub so the web dashboard can serve it to phones:

```bash
cp build/app/outputs/flutter-apk/app-release.apk ../data/downloads/
```

Then open `http://<hub-ip>:8765` → **Get the app** in the header.

## Push notes

- Foreground alerts arrive over the persistent WebSocket (`/api/ws`).
- Background/away-from-app push needs Firebase (FCM): add
  `android/app/google-services.json` and enable it hub-side with
  `python scripts/enable_fcm.py`. See `docs/TECHNICAL.md`.
