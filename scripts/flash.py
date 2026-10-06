#!/usr/bin/env python3
"""Compile + flash the ESP32-CAM firmware using credentials from .env.

Steps:
  1. regenerate firmware/doorbell_cam/secrets.h from .env
  2. compile with arduino-cli for the selected board
  3. upload to SERIAL_PORT
"""
import subprocess
import sys
import time
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


def detect_serial_port() -> str:
    """Auto-detect the USB-serial programmer (never guess a fixed port).

    Prefer USB CDC/CH340/CP210x/FTDI devices; never return COM1 (that is the
    motherboard header, not a programmer). A hardcoded SERIAL_PORT in .env
    is still honored as an override.
    """
    fixed = env_value("SERIAL_PORT", "")
    if fixed and fixed.upper() not in ("COM1", "AUTO"):
        return fixed

    import re
    try:
        out = subprocess.check_output(
            ["powershell.exe", "-NoProfile", "-Command",
             "Get-CimInstance Win32_PnPEntity | "
             "Where-Object { $_.Name -match 'COM\\d+' } | "
             "Select-Object -ExpandProperty Name"],
            text=True, stderr=subprocess.DEVNULL)
    except Exception:
        out = ""

    ports = sorted(set(re.findall(r"\(COM\d+\)", out)))
    ports = [p.strip("()") for p in ports]

    # heuristic: names naming a USB chip win over generic 'Communications Port'
    usb_like = [p for p in ports
                if any(k in out.split(p)[0][-120:].lower()
                       for k in ("ch340", "ch341", "cp210", "ftdi", "ft232",
                                 "usb", "uart"))]
    chosen = (usb_like or [p for p in ports if p.upper() != "COM1"] or [None])[0]
    if chosen is None:
        print("ERROR: no USB serial programmer found. Plug in the ESP32-CAM "
              "adapter (or set SERIAL_PORT in .env to override).")
        sys.exit(1)
    if len(ports) > 1:
        print(f"Multiple serial ports found: {ports} -> using {chosen}")
    return chosen


def main() -> int:
    if gen_secrets() != 0:
        return 1

    board = env_value("CAM_BOARD", "ai_thinker").lower()
    port = detect_serial_port()
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
    r = 1
    for attempt in range(1, 5):
        print(f"-- upload attempt {attempt}/4")
        r = subprocess.call(common + ["upload", "-p", port, "--fqbn", fqbn,
                                      str(SKETCH)])
        if r == 0:
            break
        # CH340 links are flaky: re-enumerate and retry
        time.sleep(2)
        try:
            port = detect_serial_port()
        except SystemExit:
            pass
    if r != 0:
        print("Upload FAILED after retries — swap the USB cable for a data "
              "cable and/or try a different USB port, then run again.")
        return r
    print("\nDone! Watch it boot: scripts/monitor.py (Ctrl+C to exit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
