#!/usr/bin/env python3
"""Serial monitor for the ESP32-CAM (Ctrl+C to exit)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def env_value(key: str, default: str = "") -> str:
    env_file = ROOT / ".env"
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default


def main() -> int:
    port = env_value("SERIAL_PORT", "COM8")
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
