"""
Image processing: derivative sizes, orientation-aware metadata/hashes, HEIC and RAW, FFmpeg lookup.
"""

import io
from types import SimpleNamespace

import piexif
import pytest
from PIL import Image

import utils.image_processing as image_processing
from conftest import make_scene, wait_for_task
from utils.image_processing import ImageProcessor, open_image

requires_ffmpeg = pytest.mark.skipif(not ImageProcessor.check_ffmpeg(), reason="FFmpeg not available")


def with_orientation(orientation: int) -> bytes:
    return piexif.dump({"0th": {piexif.ImageIFD.Orientation: orientation}})


def size_of(path):
    with Image.open(path) as img:
        return img.size


@requires_ffmpeg
@pytest.mark.parametrize("source_size,expected", [
    ((600, 400), (300, 200)),  # landscape: width is the long side
    ((400, 600), (200, 300)),  # portrait: height is the long side
    ((120, 80), (120, 80)),    # small: never upscaled
])
def test_thumbnail_fits_long_side(tmp_path, source_size, expected):
    source = tmp_path / "in.jpg"
    Image.new("RGB", source_size, "navy").save(source)

    assert ImageProcessor.generate_thumbnail(source, tmp_path / "thumbs" / "in.jpg")

    assert size_of(tmp_path / "thumbs" / "in.jpg") == expected


@requires_ffmpeg
def test_thumbnail_applies_exif_orientation(tmp_path):
    source = tmp_path / "in.jpg"
    Image.new("RGB", (600, 400), "navy").save(source, exif=with_orientation(6))  # displayed 400x600

    ImageProcessor.generate_thumbnail(source, tmp_path / "out.jpg")

    assert size_of(tmp_path / "out.jpg") == (200, 300)


@requires_ffmpeg
def test_web_version_is_not_upscaled(tmp_path):
    source = tmp_path / "in.jpg"
    Image.new("RGB", (800, 600), "navy").save(source)

    ImageProcessor.generate_web_version(source, tmp_path / "out.jpg", "web")

    assert size_of(tmp_path / "out.jpg") == (800, 600)


def test_image_info_reports_displayed_dimensions(tmp_path):
    source = tmp_path / "in.jpg"
    Image.new("RGB", (600, 400)).save(source, exif=with_orientation(6))

    info = ImageProcessor.get_image_info(source)

    assert (info["width"], info["height"]) == (400, 600)


def test_hashes_ignore_how_orientation_is_stored(tmp_path):
    upright = make_scene()
    upright.save(tmp_path / "upright.jpg", quality=95)
    # Same picture stored sideways, with an EXIF tag saying "rotate 90° clockwise to display"
    upright.transpose(Image.Transpose.ROTATE_90).save(tmp_path / "tagged.jpg", quality=95, exif=with_orientation(6))

    assert ImageProcessor.compute_hashes(tmp_path / "upright.jpg") == ImageProcessor.compute_hashes(tmp_path / "tagged.jpg")


def test_extracts_lens_model(tmp_path):
    exif = piexif.dump({"Exif": {piexif.ExifIFD.LensModel: b"RF 24-105mm F4 L\x00"}})
    Image.new("RGB", (60, 40)).save(tmp_path / "lens.jpg", exif=exif)

    assert ImageProcessor.extract_exif(tmp_path / "lens.jpg")["lens_model"] == "RF 24-105mm F4 L"


def test_photo_without_exif_has_no_metadata(tmp_path):
    Image.new("RGB", (60, 40)).save(tmp_path / "plain.jpg")

    assert ImageProcessor.extract_exif(tmp_path / "plain.jpg") == {}


# --- HEIC -------------------------------------------------------------------

def save_heic(path):
    exif = piexif.dump({
        "0th": {piexif.ImageIFD.Make: b"Phone"},
        "Exif": {piexif.ExifIFD.DateTimeOriginal: b"2023:01:02 03:04:05"},
    })
    make_scene().save(path, format="HEIF", exif=exif)


def test_heic_is_scanned_analyzed_and_served_as_jpeg(client, photo_folder):
    save_heic(photo_folder / "phone.heic")

    scan = client.post("/api/folders/scan", json={"path": str(photo_folder)}).json()
    wait_for_task(client, scan["analysis_task_id"])
    photos = client.get(f"/api/photos/list/{scan['folder_id']}").json()["photos"]
    photo_id = next(p["id"] for p in photos if p["filename"] == "phone.heic")

    details = client.get(f"/api/photos/get/{photo_id}").json()
    assert details["camera_make"] == "Phone"
    assert (details["width"], details["height"]) == (600, 400)

    original = client.get(f"/api/photos/file/{photo_id}")
    assert original.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(original.content)).format == "JPEG"


def test_heic_derivatives_are_jpeg(tmp_path):
    save_heic(tmp_path / "phone.heic")

    assert ImageProcessor.generate_thumbnail(tmp_path / "phone.heic", tmp_path / "thumbs" / "phone.heic")

    with Image.open(tmp_path / "thumbs" / "phone.heic") as thumb:
        assert thumb.format == "JPEG"
        assert thumb.size == (300, 200)


# --- RAW (rawpy is faked: no RAW sample files are available) ----------------

class FakeRaw:
    def __init__(self, flip, preview):
        self.sizes = SimpleNamespace(flip=flip, width=6000, height=4000)
        self._preview = preview

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_thumb(self):
        buffer = io.BytesIO()
        self._preview.save(buffer, format="JPEG")
        return SimpleNamespace(format=image_processing.rawpy.ThumbFormat.JPEG, data=buffer.getvalue())


@pytest.mark.parametrize("flip,expected_size", [(0, (600, 400)), (6, (400, 600)), (5, (400, 600)), (3, (600, 400))])
def test_raw_preview_is_made_upright(monkeypatch, tmp_path, flip, expected_size):
    monkeypatch.setattr(image_processing.rawpy, "imread", lambda path: FakeRaw(flip, make_scene()))
    raw_path = tmp_path / "shot.nef"
    raw_path.write_bytes(b"not really raw")

    with open_image(raw_path) as img:
        assert img.size == expected_size
    info = ImageProcessor.get_image_info(raw_path)
    assert (info["width"], info["height"]) == ((4000, 6000) if flip in (5, 6) else (6000, 4000))
    assert info["format"] == "NEF"


# --- FFmpeg lookup ------------------------------------------------------------

def test_ffmpeg_path_from_config(monkeypatch, tmp_path):
    fake = tmp_path / "ffmpeg.exe"
    fake.write_bytes(b"")
    monkeypatch.setattr(image_processing.config, "FFMPEG_PATH", str(fake))
    image_processing.find_ffmpeg.cache_clear()
    try:
        assert ImageProcessor.get_ffmpeg_path() == str(fake)
    finally:
        image_processing.find_ffmpeg.cache_clear()


# --- Review fixes ---------------------------------------------------------------

def test_tiff_based_raw_is_never_rotated(client, photo_folder):
    # Pillow opens TIFF-based RAW (NEF, DNG...) as TIFF: re-saving would destroy the camera data
    raw_path = photo_folder / "camera.nef"
    make_scene().save(raw_path, format="TIFF")
    before = raw_path.read_bytes()
    scan = client.post("/api/folders/scan", json={"path": str(photo_folder)}).json()
    wait_for_task(client, scan["analysis_task_id"])
    photos = client.get(f"/api/photos/list/{scan['folder_id']}").json()["photos"]
    photo_id = next(p["id"] for p in photos if p["filename"] == "camera.nef")

    response = client.post(f"/api/photos/rotate/{photo_id}", params={"degrees": 90})

    assert response.status_code == 400
    assert raw_path.read_bytes() == before


def test_tiff_derivatives_are_jpeg_and_rotate_with_the_original(client, photo_folder):
    make_scene().save(photo_folder / "scan.tif", format="TIFF", compression="tiff_lzw")
    scan = client.post("/api/folders/scan", json={"path": str(photo_folder)}).json()
    wait_for_task(client, scan["analysis_task_id"])
    photos = client.get(f"/api/photos/list/{scan['folder_id']}").json()["photos"]
    photo_id = next(p["id"] for p in photos if p["filename"] == "scan.tif")
    thumb = photo_folder / "thumbs" / "scan.tif"
    assert ImageProcessor.generate_thumbnail(photo_folder / "scan.tif", thumb)

    assert client.get(f"/api/photos/file/{photo_id}", params={"thumb": True}).headers["content-type"] == "image/jpeg"
    assert client.post(f"/api/photos/rotate/{photo_id}", params={"degrees": 90}).status_code == 200

    with Image.open(thumb) as img:
        assert img.format == "JPEG"
        assert img.size == (200, 300)
    with Image.open(photo_folder / "scan.tif") as img:
        assert img.format == "TIFF"
        assert img.info.get("compression") == "tiff_lzw"


@requires_ffmpeg
def test_web_version_keeps_exif_with_upright_orientation(tmp_path):
    exif = piexif.dump({
        "0th": {piexif.ImageIFD.Make: b"TestCam", piexif.ImageIFD.Orientation: 6},
        "Exif": {piexif.ExifIFD.DateTimeOriginal: b"2024:05:01 10:00:00"},
    })
    Image.new("RGB", (600, 400), "navy").save(tmp_path / "in.jpg", exif=exif)

    assert ImageProcessor.generate_web_version(tmp_path / "in.jpg", tmp_path / "web.jpg")

    with Image.open(tmp_path / "web.jpg") as img:
        assert img.size == (400, 600)  # pixels already rotated by FFmpeg...
        web_exif = piexif.load(img.info["exif"])
    assert web_exif["0th"][piexif.ImageIFD.Orientation] == 1  # ...so no second rotation
    assert web_exif["Exif"][piexif.ExifIFD.DateTimeOriginal] == b"2024:05:01 10:00:00"


@pytest.mark.parametrize("output_name,expected_quality", [("out.webp", "81"), ("out.jpg", "5")])
def test_ffmpeg_quality_matches_output_format(monkeypatch, tmp_path, output_name, expected_quality):
    # libwebp's -q:v is 0..100 (higher is better), JPEG's is 2..31 (lower is better)
    calls = []
    monkeypatch.setattr(image_processing.subprocess, "run",
                        lambda cmd, **kwargs: calls.append(cmd) or SimpleNamespace(returncode=0, stderr=""))

    ImageProcessor.generate_thumbnail(tmp_path / "in.webp", tmp_path / output_name)

    command = calls[0]
    assert command[command.index("-q:v") + 1] == expected_quality


def test_gps_altitude_below_sea_level(tmp_path):
    exif = piexif.dump({"GPS": {piexif.GPSIFD.GPSAltitude: (28, 1), piexif.GPSIFD.GPSAltitudeRef: 1}})
    Image.new("RGB", (60, 40)).save(tmp_path / "dead_sea.jpg", exif=exif)

    assert ImageProcessor.extract_exif(tmp_path / "dead_sea.jpg")["gps_altitude"] == -28
