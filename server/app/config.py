"""Central configuration loaded from the project .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _get_int(key: str, default: int) -> int:
    try:
        return int(_get(key, str(default)))
    except ValueError:
        return default


def _get_float(key: str, default: float) -> float:
    try:
        return float(_get(key, str(default)))
    except ValueError:
        return default


class Settings:
    ROOT = ROOT  # project root (module-level Path)

    # WiFi / flashing (used by scripts, not the hub itself)
    WIFI_SSID = _get("WIFI_SSID")
    WIFI_PASSWORD = _get("WIFI_PASSWORD")

    # Board / flashing
    CAM_BOARD = _get("CAM_BOARD", "ai_thinker")
    SERIAL_PORT = _get("SERIAL_PORT", "COM8")

    # Hub
    HUB_PORT = _get_int("HUB_PORT", 8765)
    CAM_IP = _get("CAM_IP")
    LOCAL_SUBNET = _get("LOCAL_SUBNET")

    # Detection tuning
    MOTION_SENSITIVITY = _get_int("MOTION_SENSITIVITY", 25)
    COOLDOWN_SECONDS = _get_int("COOLDOWN_SECONDS", 15)
    FACE_MATCH_THRESHOLD = _get_float("FACE_MATCH_THRESHOLD", 0.42)

    # Models / data paths
    MODELS_DIR = Path(_get("MODELS_DIR", "./tools/models"))
    DATA_DIR = ROOT / "data"
    SNAPSHOTS_DIR = DATA_DIR / "snapshots"
    DB_PATH = str(DATA_DIR / "doorbell.db")

    # FCM (optional)
    FCM_SERVICE_ACCOUNT = _get("FCM_SERVICE_ACCOUNT")

    TZ_OFFSET_HOURS = _get_int("TZ_OFFSET_HOURS", 0)


settings = Settings()
settings.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
