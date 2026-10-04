import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { MapContainer, Rectangle, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet.markercluster';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import { ArrowLeft, Crop, GalleryHorizontal, Loader, Maximize, Search, X } from 'lucide-react';
import { apiErrorMessage, geoAPI, metadataAPI, photosAPI } from '../services/api';
import { useToast } from '../components/Toast';
import { boundsToArea, isInArea, toQueryString } from '../utils/geo';
import './MapView.css';

const FOCUS_ZOOM = 16;

function photoPopup(location, onOpen) {
  const container = document.createElement('div');
  container.className = 'map-popup';

  const image = document.createElement('img');
  image.src = location.has_thumb ? photosAPI.getFile(location.id, true) : photosAPI.getFile(location.id);
  image.alt = location.filename;
  container.appendChild(image);

  const name = document.createElement('div');
  name.className = 'map-popup-name';
  name.textContent = location.filename;
  container.appendChild(name);

  if (location.date_taken) {
    const date = document.createElement('div');
    date.className = 'map-popup-date';
    date.textContent = new Date(location.date_taken).toLocaleString();
    container.appendChild(date);
  }

  const button = document.createElement('button');
  button.className = 'btn btn-primary map-popup-open';
  button.textContent = 'Open in gallery';
  button.onclick = () => onOpen(location.id);
  container.appendChild(button);

  return container;
}

// Clustered markers for every located photo (handles tens of thousands)
function PhotoMarkers({ locations, focusId, onOpen }) {
  const map = useMap();
  const onOpenRef = useRef(onOpen);
  onOpenRef.current = onOpen;
  const initialViewDoneRef = useRef(false);

  useEffect(() => {
    const markers = new Map();
    let disposed = false;

    // Frame the photos once (afterwards the view is the user's), or open the focused one.
    // Runs when the cluster has really added every marker: chunkedLoading adds them asynchronously.
    const showInitialView = () => {
      if (disposed) {
        return;
      }
      const focused = focusId ? markers.get(focusId) : null;
      if (focused) {
        cluster.zoomToShowLayer(focused, () => focused.openPopup());
      } else if (!initialViewDoneRef.current && markers.size > 0) {
        map.fitBounds(cluster.getBounds(), { padding: [40, 40], maxZoom: FOCUS_ZOOM });
      }
      if (markers.size > 0) {
        initialViewDoneRef.current = true;
      }
    };

    const cluster = L.markerClusterGroup({
      chunkedLoading: true,
      maxClusterRadius: 50,
      chunkProgress: (processed, total) => {
        // Called just before the cluster tree is finalized: act on the next tick
        if (processed === total) {
          setTimeout(showInitialView, 0);
        }
      }
    });

    for (const location of locations) {
      const marker = L.circleMarker([location.latitude, location.longitude], {
        radius: 7,
        color: '#ffffff',
        weight: 2,
        fillColor: '#3b82f6',
        fillOpacity: 0.9
      });
      marker.bindPopup(() => photoPopup(location, (id) => onOpenRef.current(id)), { minWidth: 220 });
      markers.set(location.id, marker);
    }
    map.addLayer(cluster);
    cluster.addLayers([...markers.values()]);

    return () => {
      disposed = true;
      map.removeLayer(cluster);
    };
  }, [map, locations, focusId]);

  return null;
}

// While active, dragging on the map draws a rectangle instead of panning
function AreaSelector({ active, onChange, onDone }) {
  const map = useMap();
  const callbacksRef = useRef({ onChange, onDone });
  callbacksRef.current = { onChange, onDone };

  useEffect(() => {
    if (!active) {
      return undefined;
    }

    let start = null;
    const container = map.getContainer();
    map.dragging.disable();
    container.classList.add('is-selecting');

    const handleDown = (event) => {
      start = event.latlng;
    };
    const handleMove = (event) => {
      if (start) {
        callbacksRef.current.onChange(L.latLngBounds(start, event.latlng));
      }
    };
    const handleUp = (event) => {
      if (start) {
        callbacksRef.current.onDone(L.latLngBounds(start, event.latlng));
        start = null;
      }
    };

    map.on('mousedown', handleDown);
    map.on('mousemove', handleMove);
    map.on('mouseup', handleUp);

    return () => {
      map.off('mousedown', handleDown);
      map.off('mousemove', handleMove);
      map.off('mouseup', handleUp);
      map.dragging.enable();
      container.classList.remove('is-selecting');
    };
  }, [map, active]);

  return null;
}

function MapView() {
  const { folderId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();

  const [map, setMap] = useState(null);
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState(false);
  const [selectionBounds, setSelectionBounds] = useState(null);
  const [placeQuery, setPlaceQuery] = useState('');
  const [places, setPlaces] = useState([]);
  const [searchingPlaces, setSearchingPlaces] = useState(false);

  const focusId = Number(searchParams.get('focus')) || null;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    metadataAPI.getGPSLocations(folderId)
      .then((response) => {
        if (!cancelled) {
          setLocations(response.data.locations || []);
        }
      })
      .catch((error) => toast.error(apiErrorMessage(error, 'Error loading photo locations')))
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [folderId, toast]);

  const selectedArea = useMemo(
    () => (selectionBounds ? boundsToArea(selectionBounds) : null),
    [selectionBounds]
  );
  const selectedCount = useMemo(() => (
    selectedArea
      ? locations.filter((loc) => isInArea(loc.latitude, loc.longitude, selectedArea)).length
      : 0
  ), [locations, selectedArea]);

  const openPhoto = useCallback((photoId) => {
    navigate(`/gallery/${folderId}?photo=${photoId}`);
  }, [navigate, folderId]);

  const handleSelectionDone = (bounds) => {
    setSelectionBounds(bounds);
    setSelecting(false);
  };

  const handleUseVisibleArea = () => {
    if (map) {
      setSelectionBounds(map.getBounds());
      setSelecting(false);
    }
  };

  const handleOpenSelection = () => {
    navigate(`/gallery/${folderId}?${toQueryString(selectedArea)}`);
  };

  const handleSearchPlace = async (event) => {
    event.preventDefault();
    if (placeQuery.trim().length < 2) {
      return;
    }

    try {
      setSearchingPlaces(true);
      const response = await geoAPI.searchPlaces(placeQuery.trim());
      setPlaces(response.data.places);
      if (response.data.places.length === 0) {
        toast.info(`No places found for "${placeQuery.trim()}"`);
      }
    } catch (error) {
      toast.error(apiErrorMessage(error, 'Place search failed'));
    } finally {
      setSearchingPlaces(false);
    }
  };

  const handleGoToPlace = (place) => {
    const { south, north, west, east } = place.bbox;
    map?.flyToBounds([[south, west], [north, east]], { maxZoom: FOCUS_ZOOM });
    setPlaces([]);
  };

  return (
    <div className="map-page">
      <div className="map-header">
        <button className="btn btn-secondary" onClick={() => navigate(`/gallery/${folderId}`)}>
          <ArrowLeft size={20} />
          Gallery
        </button>

        <div className="map-title">
          <h2>Photo Map</h2>
          <span>
            {loading ? 'Loading...' : `${locations.length} photos with location`}
          </span>
        </div>

        <form className="map-search" onSubmit={handleSearchPlace}>
          <input
            className="input"
            placeholder="Search a place (e.g. Granada)"
            value={placeQuery}
            onChange={(event) => setPlaceQuery(event.target.value)}
            title="Searches OpenStreetMap Nominatim: only the text you type is sent"
          />
          <button className="btn btn-secondary" type="submit" disabled={searchingPlaces} title="Search place">
            {searchingPlaces ? <Loader size={18} className="spinning" /> : <Search size={18} />}
          </button>
          {places.length > 0 && (
            <ul className="map-search-results">
              {places.map((place) => (
                <li key={`${place.latitude},${place.longitude},${place.name}`}>
                  <button type="button" onClick={() => handleGoToPlace(place)}>{place.name}</button>
                </li>
              ))}
            </ul>
          )}
        </form>

        <div className="map-actions">
          <button
            className={`btn ${selecting ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setSelecting((prev) => !prev)}
            title="Drag on the map to select an area"
          >
            <Crop size={18} />
            {selecting ? 'Drag to select...' : 'Select area'}
          </button>
          <button className="btn btn-secondary" onClick={handleUseVisibleArea} title="Select the area currently visible">
            <Maximize size={18} />
            Use visible area
          </button>
        </div>
      </div>

      <div className="map-body">
        <MapContainer
          ref={setMap}
          className="map-container"
          center={[20, 0]}
          zoom={2}
          worldCopyJump
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <PhotoMarkers
            locations={locations}
            focusId={focusId}
            onOpen={openPhoto}
          />
          <AreaSelector active={selecting} onChange={setSelectionBounds} onDone={handleSelectionDone} />
          {selectionBounds && (
            <Rectangle bounds={selectionBounds} pathOptions={{ color: '#f59e0b', weight: 2, fillOpacity: 0.12 }} />
          )}
        </MapContainer>

        {!loading && locations.length === 0 && (
          <div className="map-empty">
            <h3>No photos with location</h3>
            <p>None of the analyzed photos in this folder have GPS data (yet).</p>
          </div>
        )}

        {selectedArea && (
          <div className="map-selection">
            <span>
              <strong>{selectedCount}</strong> photos in the selected area
            </span>
            <button className="btn btn-primary" onClick={handleOpenSelection} disabled={selectedCount === 0}>
              <GalleryHorizontal size={18} />
              Open in gallery
            </button>
            <button className="btn btn-secondary" onClick={() => setSelectionBounds(null)} title="Clear selection">
              <X size={18} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default MapView;
