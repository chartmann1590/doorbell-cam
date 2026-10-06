#!/usr/bin/env python3
"""One-time setup: installs Python deps, checks toolchains, downloads models.

Safe to re-run. Never touches secrets; run scripts/flash.py to flash firmware.
"""
import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
AC_DIR = TOOLS / "arduino-cli"
AC = AC_DIR / "arduino-cli.exe"

MODEL_URLS = {
    "MobileNetSSD_deploy.prototxt":
        "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt",
    "MobileNetSSD_deploy.caffemodel":
        "https://github.com/chuanqi305/MobileNet-SSD/raw/master/mobilenet_iter_73000.caffemodel",
    "face_detection_yunet_2023mar.onnx":
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx":
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}

AC_VERSION = "1.5.1"
AC_URL = (f"https://github.com/arduino/arduino-cli/releases/download/"
          f"v{AC_VERSION}/arduino-cli_{AC_VERSION}_Windows_64bit.zip")

# Portable, gitignored toolchain data dir (absolute so any CWD works)
AC_DATA = AC_DIR / "data"
AC_DOWNLOADS = AC_DIR / "downloads"
AC_USER = AC_DIR / "user"


def write_ac_config() -> Path:
    AC_DIR.mkdir(parents=True, exist_ok=True)
    cfg = AC_DIR / "arduino-cli.yaml"
    cfg.write_text(
        "board_manager:\n"
        "  additional_urls:\n"
        "    - https://espressif.github.io/arduino-esp32/package_esp32_index.json\n"
        "directories:\n"
        f"  data: {AC_DATA.as_posix()}\n"
        f"  downloads: {AC_DOWNLOADS.as_posix()}\n"
        f"  user: {AC_USER.as_posix()}\n",
        encoding="utf-8")
    return cfg


def run(cmd: list[str]) -> int:
    print("$", " ".join(cmd), flush=True)
    return subprocess.call(cmd)


def install_python_deps() -> None:
    print("\n== Python dependencies ==")
    run([sys.executable, "-m", "pip", "install", "--quiet",
         "-r", str(ROOT / "server" / "requirements.txt")])


def ensure_arduino_cli() -> Path:
    print("\n== arduino-cli ==")
    if AC.exists():
        print("already installed:", AC)
        return AC
    print("downloading arduino-cli…")
    AC_DIR.mkdir(parents=True, exist_ok=True)
    tmp = TOOLS / "ac.zip"
    urllib.request.urlretrieve(AC_URL, tmp)
    with zipfile.ZipFile(tmp) as z:
        z.extractall(AC_DIR)
    tmp.unlink()
    print("installed:", AC)
    return AC


def ensure_esp32_core(ac: Path) -> None:
    print("\n== ESP32 Arduino core ==")
    cfg = ac.parent / "arduino-cli.yaml"
    write_ac_config()
    if (AC_DATA / "packages" / "esp32").exists():
        print("ESP32 core already present ✔")
    run([str(ac), "--config-file", str(cfg), "core", "update-index"])
    run([str(ac), "--config-file", str(cfg), "core", "install", "esp32:esp32"])


def ensure_models() -> None:
    print("\n== Detection models ==")
    models_dir = TOOLS / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    for name, url in MODEL_URLS.items():
        dest = models_dir / name
        if dest.exists() and dest.stat().st_size > 10_000:
            print("have:", name)
            continue
        print("downloading:", name)
        urllib.request.urlretrieve(url, dest)


def ensure_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        print("\n== .env ==")
        env.write_bytes((ROOT / ".env.example").read_bytes())
        print("Created .env from template — EDIT IT with your WiFi credentials.")
    else:
        print("\n== .env == exists ✔")


def main() -> int:
    ensure_env()
    install_python_deps()
    ensure_models()
    try:
        ac = ensure_arduino_cli()
        ensure_esp32_core(ac)
    except Exception as e:  # noqa: BLE001
        print(f"Arduino toolchain setup skipped/failed: {e}")
        print("(The hub still runs without it — you just can't flash.)")
    print("\nSetup complete. Next: python scripts/flash.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
