"""
Metadata search/stats and task listing.
"""

import time

import piexif
from PIL import Image

from conftest import wait_for_task


def test_stats_coverage_ignores_deleted_photos(client, scanned):
    _, folder_id, ids = scanned
    client.post(f"/api/photos/delete/{ids['a.jpg']}")  # the only photo with EXIF/GPS

    stats = client.get(f"/api/metadata/stats/{folder_id}").json()

    assert stats["total_photos"] == 3
    assert stats["photos_with_exif"] == 0
    assert stats["exif_coverage"] == 0


def test_search_date_to_includes_the_whole_day(client, scanned):
    _, folder_id, ids = scanned  # a.jpg taken 2024-05-01 10:00

    found = client.post("/api/metadata/search", json={"folder_id": folder_id, "date_to": "2024-05-01"}).json()
    before = client.post("/api/metadata/search", json={"folder_id": folder_id, "date_to": "2024-04-30"}).json()

    assert [p["id"] for p in found["photos"]] == [ids["a.jpg"]]
    assert before["total"] == 0


def test_search_numeric_filter_zero_is_applied(client, photo_folder):
    exif = piexif.dump({"Exif": {piexif.ExifIFD.ISOSpeedRatings: 100}})
    Image.new("RGB", (60, 40)).save(photo_folder / "iso.jpg", exif=exif)
    scan = client.post("/api/folders/scan", json={"path": str(photo_folder)}).json()
    wait_for_task(client, scan["analysis_task_id"])

    result = client.post("/api/metadata/search", json={"folder_id": scan["folder_id"], "max_iso": 0}).json()

    assert result["total"] == 0  # 0 used to be ignored as "no filter"


def test_task_list_filters_by_status(client, scanned):
    _, folder_id, _ = scanned
    task_id = client.post(f"/api/photos/generate-thumbs-async/{folder_id}").json()["task_id"]
    wait_for_task(client, task_id)
    time.sleep(0.05)

    completed = client.get("/api/photos/tasks", params={"status": "completed"}).json()["tasks"]
    failed = client.get("/api/photos/tasks", params={"status": "failed"}).json()["tasks"]

    assert task_id in [t["id"] for t in completed]
    assert task_id not in [t["id"] for t in failed]
    assert all(t["status"] == "completed" for t in completed)
