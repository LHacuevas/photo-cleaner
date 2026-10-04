"""
Folder scan: registers photos with metadata and creates the working subfolders.
"""

from datetime import datetime

import pytest

from conftest import make_scene, make_thumb, wait_for_task
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


def test_recursive_scan_keeps_subfolder_structure(client, photo_folder):
    (photo_folder / "trip").mkdir()
    (photo_folder / "c.jpg").rename(photo_folder / "trip" / "c.jpg")
    (photo_folder / "trip" / "thumbs").mkdir()
    make_scene().save(photo_folder / "trip" / "thumbs" / "ignored.jpg")

    flat = client.post("/api/folders/scan", json={"path": str(photo_folder)}).json()
    assert flat["new_photos"] == 3

    deep = client.post("/api/folders/scan", json={"path": str(photo_folder), "recursive": True}).json()
    wait_for_task(client, deep["analysis_task_id"])
    photos = client.get(f"/api/photos/list/{deep['folder_id']}").json()["photos"]
    assert deep["new_photos"] == 1
    assert sorted(p["filename"] for p in photos) == ["a.jpg", "b.jpg", "d.png", "trip/c.jpg"]

    # Derivatives and the non-destructive delete mirror the subfolder
    nested_id = next(p["id"] for p in photos if p["filename"] == "trip/c.jpg")
    client.post(f"/api/photos/generate-thumbs/{deep['folder_id']}")
    client.post(f"/api/photos/delete/{nested_id}")
    assert (photo_folder / "cancellate" / "trip" / "c.jpg").exists()
    if ImageProcessor.check_ffmpeg():
        assert (photo_folder / "cancellate" / "thumbs" / "trip" / "c.jpg").exists()


def test_rescan_forgets_photos_deleted_from_disk(client, scanned):
    folder, folder_id, ids = scanned
    client.post(f"/api/photos/delete/{ids['b.jpg']}")
    (folder / "c.jpg").unlink()
    (folder / "cancellate" / "b.jpg").unlink()

    response = client.post("/api/folders/scan", json={"path": str(folder)}).json()

    assert response["removed_photos"] == 2
    assert client.get(f"/api/photos/get/{ids['c.jpg']}").status_code == 404
    remaining = client.get(f"/api/photos/list/{folder_id}").json()["photos"]
    assert sorted(p["filename"] for p in remaining) == ["a.jpg", "d.png"]


def test_folder_list_reports_live_counts(client, scanned):
    folder, folder_id, ids = scanned
    client.post(f"/api/photos/favorite/{ids['a.jpg']}")
    client.post(f"/api/photos/delete/{ids['c.jpg']}")

    listed = next(f for f in client.get("/api/folders/list").json() if f["id"] == folder_id)

    assert (listed["total_photos"], listed["favorites_count"], listed["deleted_count"]) == (3, 1, 1)
    assert listed["last_scanned"]


def test_has_thumbs_ignores_deleted_photos(client, scanned):
    folder, folder_id, ids = scanned
    for name in ("a.jpg", "b.jpg", "c.jpg", "d.png"):
        make_thumb(folder, name)
    client.post(f"/api/photos/delete/{ids['d.png']}")
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        client.get(f"/api/photos/get/{ids[name]}")  # syncs has_thumb with the filesystem

    stats = client.get(f"/api/folders/stats/{folder_id}").json()

    assert stats["thumbs_count"] == stats["total_photos"] == 3
    assert stats["has_thumbs"] is True


def test_same_folder_written_differently_is_not_duplicated(client, scanned):
    folder, folder_id, _ = scanned

    again = client.post("/api/folders/scan", json={"path": str(folder).upper() + "\\"}).json()

    assert again["folder_id"] == folder_id
    assert again["new_photos"] == 0


def test_scanning_parent_folder_skips_photos_indexed_through_child(client, photo_folder):
    child = photo_folder / "trip"
    child.mkdir()
    make_scene(5).save(child / "x.jpg")
    client.post("/api/folders/scan", json={"path": str(child)})

    parent = client.post("/api/folders/scan", json={"path": str(photo_folder), "recursive": True})

    assert parent.status_code == 200
    assert parent.json()["new_photos"] == 4  # a, b, c, d; trip/x.jpg already belongs to the child folder


def test_scan_with_changes_forgets_pending_groups(client, scanned):
    folder, folder_id, _ = scanned
    assert client.post(f"/api/similar/group/{folder_id}").json()["groups_found"] == 1
    make_scene(1).save(folder / "e.jpg")

    client.post("/api/folders/scan", json={"path": str(folder)})

    pending = client.get(f"/api/similar/groups/{folder_id}", params={"only_unreviewed": True}).json()
    assert pending["total_groups"] == 0  # Compare will regroup including e.jpg
