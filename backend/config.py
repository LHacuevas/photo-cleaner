"""
Runtime configuration, read from environment variables or backend/.env
(see .env.example). Real environment variables take precedence over .env.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent

load_dotenv(BACKEND_DIR / ".env")

# Local only by default: the API reads any folder on disk. Use 0.0.0.0 to expose it on the LAN.
HOST = os.getenv("PHOTO_CLEANER_HOST", "127.0.0.1")
PORT = int(os.getenv("PHOTO_CLEANER_PORT", "8000"))

DATABASE_URL = os.getenv(
    "PHOTO_CLEANER_DATABASE_URL",
    f"sqlite:///{BACKEND_DIR / 'photo_cleaner.db'}"
)

# Comma-separated list of allowed frontend origins. Empty: any localhost/127.0.0.1 port.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("PHOTO_CLEANER_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
LOCALHOST_ORIGIN_REGEX = r"http://(localhost|127\.0\.0\.1)(:\d+)?"

# Explicit FFmpeg executable; otherwise it is looked up on PATH and in common install folders
FFMPEG_PATH = os.getenv("PHOTO_CLEANER_FFMPEG") or None
