#!/usr/bin/env python3
"""Launch the DoorbellCam hub (uvicorn) with .env-provided port."""
import os
import sys
import uvicorn

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from app.config import settings  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.HUB_PORT,
                log_level="info", access_log=False)
