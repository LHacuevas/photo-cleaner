"""
Shared fixtures: a temp SQLite DB for the whole session and synthetic photo folders.
"""

import os
import tempfile
import time
from pathlib import Path

# Must be set before `database` is imported anywhere, so the engine points at the temp DB
_DB_DIR = tempfile.mkdtemp(prefix="photo-cleaner-tests-")
os.environ["PHOTO_CLEANER_DATABASE_URL"] = f"sqlite:///{Path(_DB_DIR) / 'test.db'}"

import piexif
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from main import app
from database import SessionLocal

EXIF_DATE = b"2024:05:01 10:00:00"


def make_scene(shift: int = 0) -> Image.Image:
    """Asymmetric test picture; small `shift` values give near-duplicates."""
    img = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([50 + shift, 50, 300, 350], fill="navy")
    draw.ellipse([350, 100, 550, 300], fill="orange")
    return img


def make_checkerboard() -> Image.Image:
    img = Image.new("RGB", (600, 400), "black")
    draw = ImageDraw.Draw(img)
    for x in range(0, 600, 50):
        for y in range(0, 400, 50):
            if (x // 50 + y // 50) % 2:
                draw.rectangle([x, y, x + 49, y + 49], fill="green")
    return img


def full_exif() -> bytes:
    return piexif.dump({
        "0th": {piexif.ImageIFD.Make: b"TestCam", piexif.ImageIFD.Orientation: 1},
        "Exif": {piexif.ExifIFD.DateTimeOriginal: EXIF_DATE},
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: b"N", piexif.GPSIFD.GPSLatitude: ((41, 1), (23, 1), (0, 1)),
            piexif.GPSIFD.GPSLongitudeRef: b"E", piexif.GPSIFD.GPSLongitude: ((2, 1), (10, 1), (0, 1)),
        },
    })


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def photo_folder(tmp_path):
    """
    A folder with:
    - a.jpg: scene with full EXIF (date, GPS, make)
    - b.jpg: near-duplicate of a.jpg, no EXIF
    - c.jpg: unrelated checkerboard
    - d.png: same scene as a.jpg, PNG
    """
    folder = tmp_path / "photos"
    folder.mkdir()
    make_scene(0).save(folder / "a.jpg", exif=full_exif(), quality=92)
    make_scene(2).save(folder / "b.jpg", quality=92)
    make_checkerboard().save(folder / "c.jpg", quality=92)
    make_scene(0).save(folder / "d.png")
    return folder


@pytest.fixture
def scanned(client, photo_folder):
    """Scan `photo_folder` and return (folder_path, folder_id, {filename: photo_id})."""
    response = client.post("/api/folders/scan", json={"path": str(photo_folder)})
    assert response.status_code == 200, response.text
    folder_id = response.json()["folder_id"]
    wait_for_task(client, response.json()["analysis_task_id"])
    photos = client.get(f"/api/photos/list/{folder_id}").json()["photos"]
    return photo_folder, folder_id, {p["filename"]: p["id"] for p in photos}


def wait_for_task(client, task_id, timeout: float = 30) -> dict:
    """Poll a background task until it finishes; returns its final status."""
    deadline = time.monotonic() + timeout
    while True:
        status = client.get(f"/api/photos/tasks/{task_id}").json()
        if status["status"] in ("completed", "failed", "cancelled"):
            return status
        assert time.monotonic() < deadline, f"task {task_id} did not finish: {status}"
        time.sleep(0.05)


def make_thumb(folder: Path, filename: str, base: str = "") -> Path:
    """Create a thumbnail with Pillow (no FFmpeg needed), like FFmpeg would: oriented pixels, no EXIF."""
    with Image.open(folder / base / filename) as img:
        img.thumbnail((300, 300))
        thumb_path = folder / base / "thumbs" / filename
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(thumb_path)
    return thumb_path
