"""
Folder scan: registers photos with metadata and creates the working subfolders.
"""

from datetime import datetime

import pytest

from conftest import wait_for_task
from utils.image_processing import ImageProcessor


def test_scan_registers_photos_and_subfolders(client, scanned):
    folder, folder_id, ids = scanned

    assert set(ids) == {"a.jpg", "b.jpg", "c.jpg", "d.png"}
    for sub in ("thumbs", "web", "cancellate", "preferite"):
        assert (folder / sub).is_dir()
    stats = client.get(f"/api/folders/stats/{folder_id}").json()
    assert stats["total_photos"] == 4


def test_scan_extracts_exif(client, scanned):
    _, _, ids = scanned

    photo = client.get(f"/api/photos/get/{ids['a.jpg']}").json()

    assert photo["camera_make"] == "TestCam"
    assert datetime.fromisoformat(photo["date_taken"]) == datetime(2024, 5, 1, 10, 0, 0)
    assert photo["gps_latitude"] == pytest.approx(41 + 23 / 60)
    assert photo["gps_longitude"] == pytest.approx(2 + 10 / 60)


def test_rescan_does_not_duplicate_photos(client, scanned):
    folder, folder_id, _ = scanned

    response = client.post("/api/folders/scan", json={"path": str(folder)}).json()

    assert response["folder_id"] == folder_id
    assert response["new_photos"] == 0
    assert response["total_photos"] == 4


@pytest.mark.skipif(not ImageProcessor.check_ffmpeg(), reason="FFmpeg not available")
def test_generate_thumbnails_with_ffmpeg(client, scanned):
    folder, folder_id, ids = scanned

    result = client.post(f"/api/photos/generate-thumbs/{folder_id}").json()

    assert result["success"] == 4
    assert (folder / "thumbs" / "a.jpg").exists()
    assert client.get(f"/api/photos/get/{ids['a.jpg']}").json()["has_thumb"] is True


def test_scan_ignores_working_subfolders_and_matches_extensions_case_insensitively(client, photo_folder):
    (photo_folder / "a.jpg").rename(photo_folder / "UPPER.JPG")
    (photo_folder / "thumbs").mkdir()
    (photo_folder / "c.jpg").rename(photo_folder / "thumbs" / "c.jpg")
    (photo_folder / "notes.txt").write_text("not a photo")

    response = client.post("/api/folders/scan", json={"path": str(photo_folder)}).json()
    wait_for_task(client, response["analysis_task_id"])

    names = [p["filename"] for p in client.get(f"/api/photos/list/{response['folder_id']}").json()["photos"]]
    assert sorted(names) == ["UPPER.JPG", "b.jpg", "d.png"]


def test_scan_returns_before_analysis_and_reports_its_task(client, photo_folder):
    response = client.post("/api/folders/scan", json={"path": str(photo_folder)}).json()

    assert response["new_photos"] == 4
    assert response["analysis_task_id"]
    result = wait_for_task(client, response["analysis_task_id"])
    assert result["status"] == "completed"
    assert result["result"] == {"total": 4, "analyzed": 4, "errors": 0}
