"""
File dates (modified and, on Windows, created) survive derived files and rewrites.
"""

import os
from pathlib import Path

import pytest
from PIL import Image

from conftest import make_scene
from utils.file_times import _set_windows_creation_time, apply_file_times
from utils.image_processing import ImageProcessor

requires_ffmpeg = pytest.mark.skipif(not ImageProcessor.check_ffmpeg(), reason="FFmpeg not available")
on_windows = pytest.mark.skipif(os.name != "nt", reason="creation time is only settable on Windows")

OLD_NS = 1_600_000_000 * 10**9  # 2020-09-13
OLDER_NS = 1_500_000_000 * 10**9  # 2017-07-14


def age(path: Path):
    """Make `path` look like an old file: modified in 2020, created in 2017 (Windows)."""
    os.utime(path, ns=(OLD_NS, OLD_NS))
    if os.name == "nt":
        _set_windows_creation_time(path, OLDER_NS)


def dates(path: Path):
    stat = path.stat()
    created = getattr(stat, "st_birthtime_ns", None) if os.name == "nt" else None
    return stat.st_mtime_ns, created


def expected_dates():
    return OLD_NS, (OLDER_NS if os.name == "nt" else None)


@on_windows
def test_windows_creation_time_can_be_set(tmp_path):
    path = tmp_path / "f.txt"
    path.write_text("x")

    _set_windows_creation_time(path, OLDER_NS)

    assert path.stat().st_birthtime_ns == OLDER_NS


def test_apply_file_times_never_raises(tmp_path):
    stat = (tmp_path).stat()
    apply_file_times(tmp_path / "missing.jpg", stat)  # only logs a warning


@requires_ffmpeg
def test_web_version_inherits_original_dates(tmp_path):
    original = tmp_path / "in.jpg"
    make_scene().save(original)
    age(original)

    ImageProcessor.generate_web_version(original, tmp_path / "web" / "in.jpg")

    assert dates(tmp_path / "web" / "in.jpg") == expected_dates()


@pytest.mark.parametrize("filename", ["a.jpg", "d.png"])  # EXIF-tag rotation and lossless re-save
def test_rotating_keeps_original_dates(client, scanned, filename):
    folder, _, ids = scanned
    age(folder / filename)

    assert client.post(f"/api/photos/rotate/{ids[filename]}", params={"degrees": 90}).status_code == 200

    assert dates(folder / filename) == expected_dates()


def test_favorite_copy_keeps_original_dates(client, scanned):
    folder, _, ids = scanned
    age(folder / "c.jpg")

    client.post(f"/api/photos/favorite/{ids['c.jpg']}")

    assert dates(folder / "preferite" / "c.jpg") == expected_dates()


def test_thumbnails_are_unaffected(tmp_path):
    # Thumbnails are app-internal: they keep their own (generation) dates and no EXIF
    original = tmp_path / "in.jpg"
    make_scene().save(original)
    age(original)
    thumb = tmp_path / "thumbs" / "in.jpg"
    if ImageProcessor.generate_thumbnail(original, thumb):
        assert thumb.stat().st_mtime_ns != OLD_NS
        with Image.open(thumb) as img:
            assert "exif" not in img.info
