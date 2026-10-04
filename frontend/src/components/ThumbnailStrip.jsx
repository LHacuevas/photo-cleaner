import { useEffect, useRef } from 'react';
import { Star } from 'lucide-react';
import { photosAPI } from '../services/api';

// Thumbnails rendered on each side of the current photo (the strip never renders the whole folder)
const STRIP_WINDOW = 60;

// Horizontal strip of thumbnails around the current photo. Ctrl/Cmd+click toggles selection.
function ThumbnailStrip({ photos, currentIndex, selectedIds, onSelect, onToggleSelection }) {
  const stripRef = useRef(null);
  const thumbnailRefs = useRef({});

  const stripStart = Math.max(0, currentIndex - STRIP_WINDOW);
  const stripPhotos = photos.slice(stripStart, currentIndex + STRIP_WINDOW + 1);
  const currentId = photos[currentIndex]?.id;

  // Keep the active thumbnail centered
  useEffect(() => {
    const strip = stripRef.current;
    const activeThumbnail = thumbnailRefs.current[currentId];

    if (!strip || !activeThumbnail) {
      return;
    }

    const targetScrollLeft =
      activeThumbnail.offsetLeft - (strip.clientWidth / 2) + (activeThumbnail.clientWidth / 2);

    strip.scrollTo({
      left: Math.max(0, targetScrollLeft),
      behavior: 'smooth'
    });
  }, [currentIndex, currentId]);

  return (
    <div className="thumbnail-strip" ref={stripRef}>
      {stripPhotos.map((photo, stripIndex) => {
        const index = stripStart + stripIndex;
        const isSelected = selectedIds.has(photo.id);

        return (
          <div
            key={photo.id}
            ref={(node) => {
              if (node) {
                thumbnailRefs.current[photo.id] = node;
              } else {
                delete thumbnailRefs.current[photo.id];
              }
            }}
            className={`thumbnail ${index === currentIndex ? 'active' : ''} ${isSelected ? 'selected' : ''}`}
            onClick={(event) => {
              if (event.ctrlKey || event.metaKey) {
                onToggleSelection(photo.id);
                return;
              }
              onSelect(index);
            }}
            title={isSelected ? 'Ctrl+Click to deselect' : 'Ctrl+Click to select'}
          >
            <img
              src={photo.has_thumb ? photosAPI.getFile(photo.id, true) : photosAPI.getFile(photo.id)}
              alt={photo.filename}
              loading="lazy"
            />
            {photo.is_favorite && <Star className="fav-badge" size={16} />}
            {isSelected && <div className="selection-badge">OK</div>}
          </div>
        );
      })}
    </div>
  );
}

export default ThumbnailStrip;
