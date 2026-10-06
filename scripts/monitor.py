#!/usr/bin/env python3
"""Serial monitor for the ESP32-CAM (Ctrl+C to exit)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from flash import detect_serial_port  # noqa: E402


def main() -> int:
    port = detect_serial_port()
    py = sys.executable
    try:
        import serial  # noqa: F401
    except ImportError:
        subprocess.call([py, "-m", "pip", "install", "--quiet", "pyserial"])
    r = subprocess.call([py, "-m", "serial.tools.miniterm", port, "115200"])
    return r


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nbye")
