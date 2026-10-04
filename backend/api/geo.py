"""
Geo API - Place name search (OpenStreetMap Nominatim) for the map view.

This is the only endpoint that reaches the internet: it sends the typed text,
never photos or their locations.
"""

from functools import lru_cache
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter()

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy asks clients to identify themselves
USER_AGENT = "PhotoCleaner/1.0 (local photo organizer)"
MAX_RESULTS = 5


@lru_cache(maxsize=256)
def _search_places(query: str) -> tuple:
    """Raw Nominatim results for `query` (cached: identical searches are not repeated)"""
    params = urllib.parse.urlencode({"q": query, "format": "jsonv2", "limit": MAX_RESULTS})
    request = urllib.request.Request(f"{NOMINATIM_URL}?{params}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=10) as response:
        return tuple(json.loads(response.read().decode("utf-8")))


@router.get("/search")
def search_places(q: str = Query(..., min_length=2, max_length=200)):
    """Find places by name; each result has its center and bounding box"""
    try:
        results = _search_places(q.strip())
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        logger.warning(f"Place search failed for {q!r}: {e}")
        raise HTTPException(status_code=502, detail="Place search is unavailable (no internet connection?)")

    places = []
    for result in results:
        south, north, west, east = (float(value) for value in result["boundingbox"])
        places.append({
            "name": result.get("display_name", ""),
            "latitude": float(result["lat"]),
            "longitude": float(result["lon"]),
            "bbox": {"south": south, "north": north, "west": west, "east": east},
        })

    return {"total": len(places), "places": places}
