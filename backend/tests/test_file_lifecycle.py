"""
Non-destructive file lifecycle: delete/restore/favorite move or copy files, never alter originals.
"""

import hashlib

from conftest import make_thumb


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_delete_moves_original_and_derivatives(client, scanned):
    folder, _, ids = scanned
    make_thumb(folder, "a.jpg")
    original_hash = sha256(folder / "a.jpg")

    response = client.post(f"/api/photos/delete/{ids['a.jpg']}")

    assert response.status_code == 200
    assert response.json()["is_deleted"] is True
    assert not (folder / "a.jpg").exists()
    assert not (folder / "thumbs" / "a.jpg").exists()
    assert sha256(folder / "cancellate" / "a.jpg") == original_hash
    assert (folder / "cancellate" / "thumbs" / "a.jpg").exists()


def test_restore_puts_everything_back_unchanged(client, scanned):
    folder, _, ids = scanned
    make_thumb(folder, "a.jpg")
    original_hash = sha256(folder / "a.jpg")

    client.post(f"/api/photos/delete/{ids['a.jpg']}")
    response = client.post(f"/api/photos/restore/{ids['a.jpg']}")

    assert response.json()["is_deleted"] is False
    assert sha256(folder / "a.jpg") == original_hash
    assert (folder / "thumbs" / "a.jpg").exists()
    assert not (folder / "cancellate" / "a.jpg").exists()
    photo = client.get(f"/api/photos/get/{ids['a.jpg']}").json()
    assert photo["filepath"] == str(folder / "a.jpg")
    assert photo["has_thumb"] is True


def test_deleted_photos_are_listed_separately(client, scanned):
    _, folder_id, ids = scanned
    client.post(f"/api/photos/delete/{ids['c.jpg']}")

    active = client.get(f"/api/photos/list/{folder_id}").json()
    deleted = client.get(f"/api/photos/list/{folder_id}", params={"only_deleted": True}).json()

    assert ids["c.jpg"] not in [p["id"] for p in active["photos"]]
    assert [p["id"] for p in deleted["photos"]] == [ids["c.jpg"]]


def test_toggle_favorite_copies_and_removes(client, scanned):
    folder, _, ids = scanned
    original_hash = sha256(folder / "c.jpg")

    first = client.post(f"/api/photos/favorite/{ids['c.jpg']}")
    assert first.json()["is_favorite"] is True
    assert sha256(folder / "preferite" / "c.jpg") == original_hash

    second = client.post(f"/api/photos/favorite/{ids['c.jpg']}")
    assert second.json()["is_favorite"] is False
    assert not (folder / "preferite" / "c.jpg").exists()
    assert sha256(folder / "c.jpg") == original_hash


def test_favorite_recreates_missing_preferite_folder(client, scanned):
    folder, _, ids = scanned
    (folder / "preferite").rmdir()

    response = client.post(f"/api/photos/favorite/{ids['c.jpg']}")

    assert response.status_code == 200
    assert (folder / "preferite" / "c.jpg").exists()


def test_batch_favorite_behaves_like_single_favorite(client, scanned):
    folder, _, ids = scanned

    response = client.post("/api/photos/batch-operation", json={
        "operation": "favorite", "photo_ids": [ids["c.jpg"], ids["d.png"], 999999]
    }).json()

    assert response["success"] == 2
    assert response["failed_ids"] == [999999]
    assert (folder / "preferite" / "c.jpg").exists()
    assert (folder / "preferite" / "d.png").exists()

    client.post("/api/photos/batch-operation", json={"operation": "unfavorite", "photo_ids": [ids["c.jpg"]]})
    assert not (folder / "preferite" / "c.jpg").exists()


def test_deleting_a_favorite_moves_its_copy_too(client, scanned):
    folder, _, ids = scanned
    client.post(f"/api/photos/favorite/{ids['c.jpg']}")

    client.post(f"/api/photos/delete/{ids['c.jpg']}")
    assert (folder / "cancellate" / "preferite" / "c.jpg").exists()

    client.post(f"/api/photos/restore/{ids['c.jpg']}")
    assert (folder / "preferite" / "c.jpg").exists()


def test_batch_delete_and_restore(client, scanned):
    folder, _, ids = scanned
    targets = [ids["b.jpg"], ids["c.jpg"]]

    deleted = client.post("/api/photos/batch-operation", json={"operation": "delete", "photo_ids": targets}).json()
    assert deleted["success"] == 2
    assert (folder / "cancellate" / "b.jpg").exists() and (folder / "cancellate" / "c.jpg").exists()

    restored = client.post("/api/photos/batch-operation", json={"operation": "restore", "photo_ids": targets}).json()
    assert restored["success"] == 2
    assert (folder / "b.jpg").exists() and (folder / "c.jpg").exists()


def test_unknown_batch_operation_is_rejected(client, scanned):
    _, _, ids = scanned
    response = client.post("/api/photos/batch-operation", json={"operation": "explode", "photo_ids": [ids["a.jpg"]]})
    assert response.status_code == 400


def test_list_paginates_with_summaries(client, scanned):
    _, folder_id, ids = scanned

    first = client.get(f"/api/photos/list/{folder_id}", params={"limit": 3}).json()
    second = client.get(f"/api/photos/list/{folder_id}", params={"skip": 3, "limit": 3}).json()

    assert first["total"] == 4
    listed = [p["id"] for p in first["photos"] + second["photos"]]
    assert sorted(listed) == sorted(ids.values())
    assert set(first["photos"][0]) == {"id", "filename", "is_favorite", "is_deleted", "has_thumb", "has_web"}


def test_list_rejects_oversized_pages(client, scanned):
    _, folder_id, _ = scanned
    assert client.get(f"/api/photos/list/{folder_id}", params={"limit": 100000}).status_code == 422
