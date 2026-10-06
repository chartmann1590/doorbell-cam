#!/usr/bin/env python3
"""Generate firmware/doorbell_cam/secrets.h from .env values.

Reads WIFI_SSID, WIFI_PASSWORD (and optional CAMERA_NAME) from the project
.env so real credentials never get committed to git.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "firmware" / "doorbell_cam" / "secrets.h"


def read_env(path: Path) -> dict:
    vals = {}
    if not path.exists():
        return vals
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def main() -> int:
    env = read_env(ROOT / ".env")
    ssid = env.get("WIFI_SSID", "").strip()
    password = env.get("WIFI_PASSWORD", "").strip()
    name = env.get("CAMERA_NAME", "doorbellcam").strip() or "doorbellcam"

    if not ssid:
        print("ERROR: WIFI_SSID missing from .env (copy .env.example and edit it)")
        return 1

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    body = f'''// Auto-generated from .env by scripts/gen_secrets.py — do not commit.
// This file is gitignored. Real values live in .env.
#ifndef SECRETS_H
#define SECRETS_H

#define WIFI_SSID     "{esc(ssid)}"
#define WIFI_PASSWORD "{esc(password)}"
#define CAMERA_NAME   "{esc(name)}"

#endif
'''
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} (SSID: {ssid})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
