#!/usr/bin/env python3
"""Compile + flash the ESP32-CAM firmware using credentials from .env.

Steps:
  1. regenerate firmware/doorbell_cam/secrets.h from .env
  2. compile with arduino-cli for the selected board
  3. upload to SERIAL_PORT
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from gen_secrets import main as gen_secrets  # noqa: E402

AC = ROOT / "tools" / "arduino-cli" / "arduino-cli.exe"
SKETCH = ROOT / "firmware" / "doorbell_cam"

BOARD_FQBN = {
    "ai_thinker": "esp32:esp32:esp32cam",
    "wrover_kit": "esp32:esp32:esp32",
    "esp_wrover_kit": "esp32:esp32:esp32",
    "esp32cam_probe": "esp32:esp32:esp32cam",
}


def env_value(key: str, default: str = "") -> str:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return default
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default


def main() -> int:
    if gen_secrets() != 0:
        return 1

    board = env_value("CAM_BOARD", "ai_thinker").lower()
    port = env_value("SERIAL_PORT", "COM8")
    fqbn = BOARD_FQBN.get(board, BOARD_FQBN["ai_thinker"])

    if not AC.exists():
        print("arduino-cli not found — run scripts/setup.py first")
        return 1

    cfg = AC.parent / "arduino-cli.yaml"
    common = [str(AC), "--config-file", str(cfg)]

    print(f"\n== Compile ({board}) ==")
    r = subprocess.call(common + ["compile", "--fqbn", fqbn, str(SKETCH)])
    if r != 0:
        print("Compile FAILED")
        return r

    print(f"\n== Upload to {port} ==")
    r = subprocess.call(common + ["upload", "-p", port, "--fqbn", fqbn,
                                  str(SKETCH)])
    if r != 0:
        print("Upload FAILED — is the port right? Close any Serial Monitor.")
        return r
    print("\nDone! Watch it boot: scripts/monitor.py (Ctrl+C to exit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
