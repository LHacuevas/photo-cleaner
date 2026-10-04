"""
HTTP status codes: missing resources are 404, not 500.
"""

import pytest


@pytest.mark.parametrize("method,url", [
    ("get", "/api/photos/get/999999"),
    ("get", "/api/photos/file/999999"),
    ("post", "/api/photos/favorite/999999"),
    ("post", "/api/photos/delete/999999"),
    ("post", "/api/photos/restore/999999"),
    ("post", "/api/photos/rotate/999999"),
    ("get", "/api/photos/tasks/does-not-exist"),
    ("get", "/api/folders/stats/999999"),
    ("get", "/api/similar/group/999999"),
    ("post", "/api/similar/group/999999/skip"),
])
def test_missing_resources_return_404(client, method, url):
    assert getattr(client, method)(url).status_code == 404


def test_missing_thumbnail_returns_404(client, scanned):
    _, _, ids = scanned
    assert client.get(f"/api/photos/file/{ids['a.jpg']}", params={"thumb": True}).status_code == 404


def test_scan_nonexistent_folder_returns_400(client, tmp_path):
    response = client.post("/api/folders/scan", json={"path": str(tmp_path / "nope")})
    assert response.status_code == 400
