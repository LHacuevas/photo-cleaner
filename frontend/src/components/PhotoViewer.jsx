import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Info, LocateFixed, MapPin, X } from 'lucide-react';
import { formatFileSize } from '../utils/format';

const MAP_MARGIN_DEGREES = 0.02;

function mapUrls(latitude, longitude) {
  const bbox = [
    longitude - MAP_MARGIN_DEGREES,
    latitude - MAP_MARGIN_DEGREES,
    longitude + MAP_MARGIN_DEGREES,
    latitude + MAP_MARGIN_DEGREES
  ].join('%2C');

  return {
    embed: `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${latitude}%2C${longitude}`,
    link: `https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=14/${latitude}/${longitude}`
  };
}

// Wheel to zoom, drag to pan. Give it a `key` per image so zoom resets when the image changes.
function ZoomableImage({ src, alt }) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef({ x: 0, y: 0, panX: 0, panY: 0 });
  const stageRef = useRef(null);

  // React's onWheel is passive (preventDefault is ignored), so listen natively
  useEffect(() => {
    const stage = stageRef.current;
    const handleWheel = (event) => {
      event.preventDefault();
      const delta = event.deltaY > 0 ? -0.15 : 0.15;
      setZoom((prev) => {
        const next = Math.min(8, Math.max(1, +(prev + delta).toFixed(2)));
        if (next === 1) {
          setPan({ x: 0, y: 0 });
        }
        return next;
      });
    };

    stage.addEventListener('wheel', handleWheel, { passive: false });
    return () => stage.removeEventListener('wheel', handleWheel);
  }, []);

  const handlePointerDown = (event) => {
    if (zoom <= 1) {
      return;
    }

    event.preventDefault();
    setIsPanning(true);
    panStartRef.current = { x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
  };

  const handlePointerMove = (event) => {
    if (!isPanning) {
      return;
    }

    setPan({
      x: panStartRef.current.panX + event.clientX - panStartRef.current.x,
      y: panStartRef.current.panY + event.clientY - panStartRef.current.y
    });
  };

  const stopPanning = () => setIsPanning(false);

  return (
    <div
      ref={stageRef}
      className={`main-photo-stage ${zoom > 1 ? 'is-zoomed' : ''} ${isPanning ? 'is-panning' : ''}`}
      onPointerMove={handlePointerMove}
      onPointerUp={stopPanning}
      onPointerLeave={stopPanning}
    >
      <img
        src={src}
        alt={alt}
        className="main-photo"
        onPointerDown={handlePointerDown}
        draggable={false}
        style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
      />
    </div>
  );
}

// Main photo with its collapsible info panel (metadata, map, undo-delete notice)
function PhotoViewer({
  photo,
  src,
  isShowingWebVersion,
  onPrevious,
  onNext,
  deleteNotice,
  onUndoDelete,
  onDismissDeleteNotice,
  onShowOnMap,
  onShowNearby
}) {
  const [infoCollapsed, setInfoCollapsed] = useState(false);

  const displayedWidth = isShowingWebVersion ? (photo.web_width || photo.width) : photo.width;
  const displayedHeight = isShowingWebVersion ? (photo.web_height || photo.height) : photo.height;
  const displayedSize = isShowingWebVersion ? (photo.web_size || photo.size) : photo.size;
  const hasGpsCoordinates = photo.gps_latitude != null && photo.gps_longitude != null;
  const map = hasGpsCoordinates ? mapUrls(photo.gps_latitude, photo.gps_longitude) : null;

  return (
    <div className="gallery-viewer">
      <button className="nav-btn nav-prev" onClick={onPrevious}>
        <ChevronLeft size={32} />
      </button>

      <div className="photo-container">
        <div className="viewer-layout">
          <div className={`photo-info ${infoCollapsed ? 'is-collapsed' : ''}`}>
            <button
              className="photo-info-toggle"
              onClick={() => setInfoCollapsed((prev) => !prev)}
              title={infoCollapsed ? 'Show info' : 'Hide info'}
            >
              <Info size={16} />
              <span>{infoCollapsed ? 'Info' : 'Hide'}</span>
            </button>

            {!infoCollapsed && (
              <>
                <h3>{photo.filename}</h3>
                <span className="version-indicator">
                  Showing: {isShowingWebVersion ? 'Web version' : 'Original'}
                </span>
                <span className="photo-meta">
                  Resolution: {displayedWidth || '?'} x {displayedHeight || '?'}
                </span>
                <span className="photo-meta">
                  Size: {formatFileSize(displayedSize)}
                </span>
                {photo.camera_model && (
                  <span className="photo-meta">
                    Camera: {photo.camera_model}
                  </span>
                )}
                {photo.lens_model && (
                  <span className="photo-meta">
                    Lens: {photo.lens_model}
                  </span>
                )}
                {photo.date_taken && (
                  <span className="photo-meta">
                    Date: {new Date(photo.date_taken).toLocaleString()}
                  </span>
                )}
                {hasGpsCoordinates && (
                  <>
                    <span className="photo-meta">
                      Location: {photo.gps_latitude}, {photo.gps_longitude}
                    </span>
                    <div className="photo-map">
                      <iframe
                        title={`Map for ${photo.filename}`}
                        src={map.embed}
                        className="photo-map-frame"
                        loading="lazy"
                        referrerPolicy="no-referrer-when-downgrade"
                      />
                      <div className="photo-map-actions">
                        <button className="btn btn-secondary" onClick={onShowOnMap} title="Show on the photo map (M)">
                          <MapPin size={14} />
                          View on map
                        </button>
                        <button className="btn btn-secondary" onClick={onShowNearby} title="Photos taken within 1 km">
                          <LocateFixed size={14} />
                          Nearby photos
                        </button>
                      </div>
                      <a href={map.link} target="_blank" rel="noreferrer" className="photo-map-link">
                        Open in OpenStreetMap
                      </a>
                    </div>
                  </>
                )}
              </>
            )}

            {/* Outside the collapsible part: Undo must stay reachable with the panel hidden */}
            {deleteNotice && (
              <div className="delete-notice">
                <div className="delete-notice-text">
                  <span>{deleteNotice.filename} moved to cancellate.</span>
                </div>
                <div className="delete-notice-actions">
                  <button className="btn btn-secondary" onClick={onUndoDelete}>
                    Undo
                  </button>
                  <button className="delete-notice-close" onClick={onDismissDeleteNotice} title="Close">
                    <X size={16} />
                  </button>
                </div>
              </div>
            )}
          </div>

          <ZoomableImage key={src} src={src} alt={photo.filename} />
        </div>
      </div>

      <button className="nav-btn nav-next" onClick={onNext}>
        <ChevronRight size={32} />
      </button>
    </div>
  );
}

export default PhotoViewer;
