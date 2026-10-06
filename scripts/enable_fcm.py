#!/usr/bin/env python3
"""Interactive helper to enable Firebase Cloud Messaging push.

Steps it guides you through:
  1. create a Firebase project at https://console.firebase.google.com
  2. add an Android app with package `com.doorbellcam.app`
  3. download `google-services.json` into app/android/app/
  4. generate a service-account key (Project settings ▸ Service accounts)
     and save it as firebase-service-account.json next to .env
  5. this script wires the path into .env so the hub picks it up on restart
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print(__doc__)
    sa = input("\nPath to your service-account JSON: ").strip().strip('"')
    p = Path(sa)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        print("File not found:", p)
        return 1

    env = ROOT / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    lines = [l for l in lines if not l.startswith("FCM_SERVICE_ACCOUNT=")]
    lines.append(f"FCM_SERVICE_ACCOUNT={p}")
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote FCM_SERVICE_ACCOUNT={p} to .env")
    print("Restart the hub to activate FCM push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
