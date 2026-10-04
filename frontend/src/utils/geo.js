// Position filters understood by GET /api/photos/list
const AREA_KEYS = ['min_lat', 'max_lat', 'min_lon', 'max_lon'];
const NEAR_KEYS = ['near_lat', 'near_lon', 'radius_km'];

export const NEARBY_RADII_KM = [0.2, 1, 5, 25, 100];

const round = (value) => Math.round(value * 1e5) / 1e5;
const clampLatitude = (lat) => Math.max(-90, Math.min(90, lat));

// Leaflet lets you pan across world copies (lon 200 is lon -160)
function wrapLongitude(lon) {
  if (lon >= -180 && lon <= 180) {
    return lon;
  }
  return ((((lon + 180) % 360) + 360) % 360) - 180;
}

// Position filter in the URL search params: {type: 'area' | 'near', params} or null
export function readPositionFilter(searchParams) {
  const pick = (keys) => (
    keys.every((key) => searchParams.get(key) !== null)
      ? Object.fromEntries(keys.map((key) => [key, Number(searchParams.get(key))]))
      : null
  );

  const area = pick(AREA_KEYS);
  if (area) {
    return { type: 'area', params: area };
  }
  const near = pick(NEAR_KEYS);
  if (near) {
    return { type: 'near', params: near };
  }
  return null;
}

// Leaflet LatLngBounds -> area filter. min_lon > max_lon means the area crosses the antimeridian.
export function boundsToArea(bounds) {
  const west = bounds.getWest();
  const east = bounds.getEast();
  const wholeWorld = east - west >= 360;

  return {
    min_lat: round(clampLatitude(bounds.getSouth())),
    max_lat: round(clampLatitude(bounds.getNorth())),
    min_lon: round(wholeWorld ? -180 : wrapLongitude(west)),
    max_lon: round(wholeWorld ? 180 : wrapLongitude(east)),
  };
}

// Same rule as the backend filter
export function isInArea(latitude, longitude, area) {
  if (latitude < area.min_lat || latitude > area.max_lat) {
    return false;
  }
  return area.min_lon <= area.max_lon
    ? longitude >= area.min_lon && longitude <= area.max_lon
    : longitude >= area.min_lon || longitude <= area.max_lon;
}

export function toQueryString(params) {
  return new URLSearchParams(
    Object.entries(params).filter(([, value]) => value !== null && value !== undefined)
  ).toString();
}
