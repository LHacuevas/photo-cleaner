"""
Rotate/flip: originals keep their pixels and metadata, only the EXIF Orientation tag changes.
"""

import itertools

import piexif
import pytest
from PIL import Image, ImageOps

from conftest import EXIF_DATE, make_thumb
from utils.image_processing import FLIPS, ROTATIONS, _ORIENTATION_TRANSPOSE, _compose_orientation

ALL_OPS = list(ROTATIONS.values()) + list(FLIPS.values())


def displayed(orientation: int, image: Image.Image) -> Image.Image:
    transpose = _ORIENTATION_TRANSPOSE[orientation]
    return image.transpose(transpose) if transpose is not None else image


@pytest.mark.parametrize("orientation,op", list(itertools.product(_ORIENTATION_TRANSPOSE, ALL_OPS)))
def test_compose_orientation_matches_applying_both(orientation, op):
    probe = Image.frombytes("L", (4, 3), bytes(range(12)))

    composed = _compose_orientation(orientation, op)

    assert displayed(composed, probe).tobytes() == displayed(orientation, probe).transpose(op).tobytes()


def test_four_quarter_turns_are_identity():
    orientation = 1
    for _ in range(4):
        orientation = _compose_orientation(orientation, ROTATIONS[90])
    assert orientation == 1


def read_original(path):
    with Image.open(path) as img:
        exif = piexif.load(img.info["exif"]) if "exif" in img.info else None
        return img.tobytes(), exif, ImageOps.exif_transpose(img)


def test_rotate_keeps_original_pixels_and_metadata(client, scanned):
    folder, _, ids = scanned
    pixels_before, _, shown_before = read_original(folder / "a.jpg")

    response = client.post(f"/api/photos/rotate/{ids['a.jpg']}", params={"degrees": 90})

    assert response.status_code == 200
    pixels_after, exif_after, shown_after = read_original(folder / "a.jpg")
    assert pixels_after == pixels_before
    assert exif_after["0th"][piexif.ImageIFD.Orientation] == 6
    assert exif_after["Exif"][piexif.ExifIFD.DateTimeOriginal] == EXIF_DATE
    assert exif_after["0th"][piexif.ImageIFD.Make] == b"TestCam"
    assert piexif.GPSIFD.GPSLatitude in exif_after["GPS"]
    assert shown_after.tobytes() == shown_before.transpose(ROTATIONS[90]).tobytes()
    assert not list(folder.glob("*.tmp"))


def test_rotate_then_flip_displays_both_operations(client, scanned):
    folder, _, ids = scanned
    pixels_before, _, shown_before = read_original(folder / "a.jpg")

    client.post(f"/api/photos/rotate/{ids['a.jpg']}", params={"degrees": 90})
    client.post(f"/api/photos/flip/{ids['a.jpg']}", params={"direction": "horizontal"})

    pixels_after, _, shown_after = read_original(folder / "a.jpg")
    assert pixels_after == pixels_before
    expected = shown_before.transpose(ROTATIONS[90]).transpose(FLIPS["horizontal"])
    assert shown_after.tobytes() == expected.tobytes()


def test_rotate_jpeg_without_exif(client, scanned):
    folder, _, ids = scanned
    pixels_before, _, _ = read_original(folder / "b.jpg")

    response = client.post(f"/api/photos/rotate/{ids['b.jpg']}", params={"degrees": 180})

    assert response.status_code == 200
    pixels_after, exif_after, _ = read_original(folder / "b.jpg")
    assert pixels_after == pixels_before
    assert exif_after["0th"][piexif.ImageIFD.Orientation] == 3


def test_rotate_transforms_thumb_and_favorite_copy(client, scanned):
    folder, _, ids = scanned
    thumb = make_thumb(folder, "a.jpg")
    with Image.open(thumb) as img:
        thumb_size = img.size
    client.post(f"/api/photos/favorite/{ids['a.jpg']}")

    client.post(f"/api/photos/rotate/{ids['a.jpg']}", params={"degrees": -90})

    with Image.open(thumb) as img:
        assert img.size == thumb_size[::-1]
    _, favorite_exif, _ = read_original(folder / "preferite" / "a.jpg")
    assert favorite_exif["0th"][piexif.ImageIFD.Orientation] == 8


def test_rotate_non_jpeg_is_rejected_without_changes(client, scanned):
    folder, _, ids = scanned
    before = (folder / "d.png").read_bytes()

    response = client.post(f"/api/photos/rotate/{ids['d.png']}", params={"degrees": 90})

    assert response.status_code == 400
    assert "JPEG" in response.json()["detail"]
    assert (folder / "d.png").read_bytes() == before


@pytest.mark.parametrize("endpoint,params", [
    ("rotate", {"degrees": 45}),
    ("flip", {"direction": "diagonal"}),
])
def test_invalid_transform_parameters(client, scanned, endpoint, params):
    _, _, ids = scanned
    response = client.post(f"/api/photos/{endpoint}/{ids['a.jpg']}", params=params)
    assert response.status_code == 400
