"""
Position search: area and radius filters on the photo list, and place name search.
"""

import io
import json
import urllib.error

import piexif
import pytest
from PIL import Image

import api.geo as geo
from conftest import wait_for_task
from database import distance_km

BARCELONA = (41.3874, 2.1686)
MADRID = (40.4168, -3.7038)
FIJI = (-17.7134, 178.0650)  # next to the antimeridian


def dms(value):
    value = abs(value)
    degrees = int(value)
    minutes = int((value - degrees) * 60)
    seconds = round(((value - degrees) * 60 - minutes) * 60 * 100)
    return ((degrees, 1), (minutes, 1), (seconds, 100))


def save_with_gps(path, lat, lon):
    exif = piexif.dump({"GPS": {
        piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
        piexif.GPSIFD.GPSLatitude: dms(lat),
        piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
        piexif.GPSIFD.GPSLongitude: dms(lon),
    }})
    Image.new("RGB", (60, 40), "navy").save(path, exif=exif)


@pytest.fixture
def geo_folder(client, tmp_path):
    folder = tmp_path / "trips"
    folder.mkdir()
    save_with_gps(folder / "bcn.jpg", *BARCELONA)
    save_with_gps(folder / "mad.jpg", *MADRID)
    save_with_gps(folder / "fiji.jpg", *FIJI)
    Image.new("RGB", (60, 40)).save(folder / "no_gps.jpg")
    scan = client.post("/api/folders/scan", json={"path": str(folder)}).json()
    wait_for_task(client, scan["analysis_task_id"])
    return scan["folder_id"]


def listed(client, folder_id, **params):
    response = client.get(f"/api/photos/list/{folder_id}", params=params)
    assert response.status_code == 200, response.text
    data = response.json()
    names = sorted(p["filename"] for p in data["photos"])
    assert data["total"] == len(names)
    return names


def test_distance_km():
    assert distance_km(*BARCELONA, *MADRID) == pytest.approx(505, abs=5)
    assert distance_km(*BARCELONA, *BARCELONA) == 0
    assert distance_km(None, 0, 0, 0) is None


def test_area_filter(client, geo_folder):
    spain = {"min_lat": 36, "max_lat": 44, "min_lon": -10, "max_lon": 4}
    catalonia = {"min_lat": 40.5, "max_lat": 42.9, "min_lon": 0.1, "max_lon": 3.4}

    assert listed(client, geo_folder, **spain) == ["bcn.jpg", "mad.jpg"]
    assert listed(client, geo_folder, **catalonia) == ["bcn.jpg"]


def test_area_crossing_the_antimeridian(client, geo_folder):
    pacific = {"min_lat": -30, "max_lat": 0, "min_lon": 170, "max_lon": -170}

    assert listed(client, geo_folder, **pacific) == ["fiji.jpg"]


def test_radius_filter(client, geo_folder):
    near_bcn = {"near_lat": BARCELONA[0], "near_lon": BARCELONA[1]}

    assert listed(client, geo_folder, **near_bcn, radius_km=5) == ["bcn.jpg"]
    assert listed(client, geo_folder, **near_bcn, radius_km=600) == ["bcn.jpg", "mad.jpg"]


def test_position_filter_combines_with_pagination(client, geo_folder):
    spain = {"min_lat": 36, "max_lat": 44, "min_lon": -10, "max_lon": 4}

    first = client.get(f"/api/photos/list/{geo_folder}", params={**spain, "limit": 1}).json()

    assert first["total"] == 2
    assert len(first["photos"]) == 1


@pytest.mark.parametrize("params,status", [
    ({"min_lat": 36, "max_lat": 44}, 400),                                    # incomplete area
    ({"near_lat": 41, "near_lon": 2}, 400),                                   # radius missing
    ({"min_lat": 44, "max_lat": 36, "min_lon": -10, "max_lon": 4}, 400),      # inverted latitudes
    ({"near_lat": 95, "near_lon": 2, "radius_km": 1}, 422),                   # out of range
    ({"near_lat": 41, "near_lon": 2, "radius_km": 0}, 422),
])
def test_invalid_position_filters(client, geo_folder, params, status):
    assert client.get(f"/api/photos/list/{geo_folder}", params=params).status_code == status


def test_gps_map_lists_only_photos_with_position(client, geo_folder):
    locations = client.get(f"/api/metadata/gps-map/{geo_folder}").json()["locations"]

    assert sorted(loc["filename"] for loc in locations) == ["bcn.jpg", "fiji.jpg", "mad.jpg"]
    assert all("has_thumb" in loc for loc in locations)


# --- Place search (Nominatim is mocked: tests never reach the internet) -------------------

@pytest.fixture
def fake_nominatim(monkeypatch):
    requests = []

    def urlopen(request, timeout):
        requests.append(request)
        body = json.dumps([{
            "display_name": "Granada, Andalucía, España",
            "lat": "37.1773", "lon": "-3.5986",
            "boundingbox": ["37.13", "37.22", "-3.65", "-3.55"],
        }]).encode()
        return io.BytesIO(body)

    geo._search_places.cache_clear()
    monkeypatch.setattr(geo.urllib.request, "urlopen", urlopen)
    yield requests
    geo._search_places.cache_clear()


def test_place_search(client, fake_nominatim):
    response = client.get("/api/geo/search", params={"q": "Granada"}).json()

    assert response["places"] == [{
        "name": "Granada, Andalucía, España",
        "latitude": 37.1773,
        "longitude": -3.5986,
        "bbox": {"south": 37.13, "north": 37.22, "west": -3.65, "east": -3.55},
    }]
    request = fake_nominatim[0]
    assert "q=Granada" in request.full_url
    assert request.get_header("User-agent").startswith("PhotoCleaner")


def test_place_search_is_cached(client, fake_nominatim):
    client.get("/api/geo/search", params={"q": "Granada"})
    client.get("/api/geo/search", params={"q": "Granada"})

    assert len(fake_nominatim) == 1


def test_place_search_offline(client, monkeypatch):
    def urlopen(request, timeout):
        raise urllib.error.URLError("no network")

    geo._search_places.cache_clear()
    monkeypatch.setattr(geo.urllib.request, "urlopen", urlopen)

    response = client.get("/api/geo/search", params={"q": "Granada"})

    assert response.status_code == 502
    assert "unavailable" in response.json()["detail"]


def test_favorites_filter_combines_with_position(client, geo_folder):
    photos = client.get(f"/api/photos/list/{geo_folder}").json()["photos"]
    ids = {p["filename"]: p["id"] for p in photos}
    client.post(f"/api/photos/favorite/{ids['bcn.jpg']}")
    client.post(f"/api/photos/favorite/{ids['fiji.jpg']}")
    near_bcn = {"near_lat": BARCELONA[0], "near_lon": BARCELONA[1], "radius_km": 600}

    assert listed(client, geo_folder, only_favorites=True) == ["bcn.jpg", "fiji.jpg"]
    assert listed(client, geo_folder, only_favorites=True, **near_bcn) == ["bcn.jpg"]
