import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  FileImage,
  FlipHorizontal2,
  Loader,
  Map as MapIcon,
  MapPin,
  Monitor,
  RotateCw,
  Search,
  Star,
  Trash2,
  X
} from 'lucide-react';
import { apiErrorMessage, foldersAPI, photosAPI } from '../services/api';
import BatchActionBar from '../components/BatchActionBar';
import PhotoViewer from '../components/PhotoViewer';
import ProgressBar from '../components/ProgressBar';
import ThumbnailStrip from '../components/ThumbnailStrip';
import { useToast } from '../components/Toast';
import useBackgroundTask from '../hooks/useBackgroundTask';
import { NEARBY_RADII_KM, readPositionFilter, toQueryString } from '../utils/geo';
import './Gallery.css';

const PAGE_SIZE = 2000;
const WEB_MODE = 'web';

function Gallery() {
  const { folderId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  // Optional position filter (from the map or "Nearby photos") and photo to open (?photo=ID)
  const positionFilter = readPositionFilter(searchParams);
  const favoritesOnly = searchParams.get('favorites') === '1';
  const filterQuery = toQueryString({
    ...(positionFilter?.params || {}),
    only_favorites: favoritesOnly ? 'true' : null
  });
  const focusId = Number(searchParams.get('photo')) || null;

  const [photos, setPhotos] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [folderStats, setFolderStats] = useState(null);
  const [showWebVersion, setShowWebVersion] = useState(true);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [batchLoading, setBatchLoading] = useState(false);
  const [rotationLoading, setRotationLoading] = useState(false);
  const [taskKind, setTaskKind] = useState(null);
  const [imageRevision, setImageRevision] = useState(0);
  const [deleteNotice, setDeleteNotice] = useState(null);
  const [photoDetails, setPhotoDetails] = useState(null);
  const loadRequestRef = useRef(0);
  const appliedFocusRef = useRef(null);

  const {
    taskId,
    setTaskId,
    status: backgroundStatus,
    progress: backgroundProgress,
    isRunning: backgroundTaskRunning,
    error: backgroundTaskError,
    result: backgroundTaskResult
  } = useBackgroundTask();

  const generatingThumbs = backgroundTaskRunning && taskKind === 'thumbs';
  const generatingWeb = backgroundTaskRunning && taskKind === 'web';
  // The list only has summaries; metadata and web version details come from /get for the current photo
  const currentSummary = photos[currentIndex];
  const currentPhoto = currentSummary && photoDetails?.id === currentSummary.id
    ? { ...photoDetails, ...currentSummary }
    : currentSummary;
  const isShowingWebVersion = Boolean(currentPhoto?.has_web && showWebVersion);
  const mainPhotoSrc = currentPhoto
    ? `${photosAPI.getFile(currentPhoto.id, false, isShowingWebVersion)}&rev=${imageRevision}`
    : '';

  // Loads every page of the folder. `progressive` shows each page as it arrives (first load);
  // reloads swap the list only once complete so the current position is kept.
  const loadPhotos = useCallback(async ({ progressive = false } = {}) => {
    const requestId = ++loadRequestRef.current;
    try {
      setLoading(true);
      let loaded = [];
      let total = null;
      const filterParams = Object.fromEntries(new URLSearchParams(filterQuery));

      while (total === null || loaded.length < total) {
        const response = await photosAPI.list(folderId, { ...filterParams, skip: loaded.length, limit: PAGE_SIZE });
        if (requestId !== loadRequestRef.current) {
          return; // a newer load has started
        }

        const page = response.data.photos || [];
        total = response.data.total;
        loaded = loaded.concat(page);

        if (progressive) {
          setPhotos(loaded);
          setLoading(false);
        }
        if (page.length === 0) {
          break;
        }
      }

      setPhotos(loaded);
      setCurrentIndex((prev) => Math.min(prev, Math.max(0, loaded.length - 1)));
      setSelectedIds(new Set());
    } catch (error) {
      console.error('Error loading photos:', error);
      toast.error(apiErrorMessage(error, 'Error loading photos'));
    } finally {
      if (requestId === loadRequestRef.current) {
        setLoading(false);
      }
    }
  }, [folderId, filterQuery, toast]);

  const loadFolderStats = useCallback(async () => {
    try {
      const response = await foldersAPI.getStats(folderId);
      setFolderStats(response.data);
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  }, [folderId]);

  useEffect(() => {
    setCurrentIndex(0); // a different folder or filter is a different list
    loadPhotos({ progressive: true });
    loadFolderStats();
  }, [loadPhotos, loadFolderStats]);

  // Jump to ?photo=ID once it has been loaded
  useEffect(() => {
    const focusKey = `${filterQuery}|${focusId}`;
    if (!focusId || appliedFocusRef.current === focusKey) {
      return;
    }
    const index = photos.findIndex((photo) => photo.id === focusId);
    if (index >= 0) {
      setCurrentIndex(index);
      appliedFocusRef.current = focusKey;
    }
  }, [photos, focusId, filterQuery]);

  useEffect(() => {
    if (!currentSummary?.id) {
      setPhotoDetails(null);
      return undefined;
    }

    let cancelled = false;
    photosAPI.get(currentSummary.id)
      .then((response) => {
        if (!cancelled) {
          setPhotoDetails(response.data);
        }
      })
      .catch((error) => console.error('Error loading photo details:', error));

    return () => {
      cancelled = true;
    };
  }, [currentSummary?.id, imageRevision]);

  useEffect(() => {
    if (!backgroundTaskResult) {
      return;
    }

    loadPhotos();
    loadFolderStats();
    setTaskKind(null);
  }, [backgroundTaskResult, loadPhotos, loadFolderStats]);

  useEffect(() => {
    if (!backgroundTaskError) {
      return;
    }

    toast.error(`Background task failed: ${backgroundTaskError}`);
    setTaskKind(null);
  }, [backgroundTaskError, toast]);

  const startGeneration = async (kind, request, errorMessage) => {
    try {
      const response = await request();
      if (!response.data.task_id) {
        toast.info(response.data.message);
        loadPhotos();
        loadFolderStats();
        return;
      }
      setTaskKind(kind);
      setTaskId(response.data.task_id);
    } catch (error) {
      console.error(errorMessage, error);
      toast.error(apiErrorMessage(error, errorMessage));
    }
  };

  const handleGenerateWeb = () => startGeneration(
    'web', () => photosAPI.generateWebAsync(folderId, WEB_MODE), 'Error generating web versions'
  );

  const handleGenerateThumbs = () => startGeneration(
    'thumbs', () => photosAPI.generateThumbsAsync(folderId), 'Error generating thumbnails'
  );

  const handleToggleSelection = (photoId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(photoId)) {
        next.delete(photoId);
      } else {
        next.add(photoId);
      }
      return next;
    });
  };

  const handleClearSelection = () => {
    setSelectedIds(new Set());
  };

  const handleBatchFavorite = async () => {
    if (selectedIds.size === 0) {
      return;
    }

    try {
      setBatchLoading(true);
      const response = await photosAPI.batchOperation('favorite', Array.from(selectedIds));
      toast.success(response.data.message);
      setPhotos((prev) => prev.map((photo) => (
        selectedIds.has(photo.id) ? { ...photo, is_favorite: true } : photo
      )));
      setSelectedIds(new Set());
    } catch (error) {
      console.error('Error in batch favorite:', error);
      toast.error(apiErrorMessage(error, 'Error marking favorites'));
    } finally {
      setBatchLoading(false);
    }
  };

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) {
      return;
    }

    if (!window.confirm(`Move ${selectedIds.size} photos to cancellate?`)) {
      return;
    }

    try {
      setBatchLoading(true);
      const response = await photosAPI.batchOperation('delete', Array.from(selectedIds));
      toast.success(response.data.message);
      const updated = photos.filter((photo) => !selectedIds.has(photo.id));
      setPhotos(updated);
      setSelectedIds(new Set());
      setCurrentIndex((prev) => Math.min(prev, Math.max(0, updated.length - 1)));
      loadFolderStats();
    } catch (error) {
      console.error('Error in batch delete:', error);
      toast.error(apiErrorMessage(error, 'Error deleting photos'));
    } finally {
      setBatchLoading(false);
    }
  };

  const handlePrevious = () => {
    setCurrentIndex((prev) => (prev > 0 ? prev - 1 : photos.length - 1));
  };

  const handleNext = () => {
    setCurrentIndex((prev) => (prev < photos.length - 1 ? prev + 1 : 0));
  };

  const handleToggleFavorite = async () => {
    try {
      const photo = photos[currentIndex];
      const response = await photosAPI.toggleFavorite(photo.id);
      if (favoritesOnly && !response.data.is_favorite) {
        // No longer matches the "favorites only" view
        const updated = photos.filter((item) => item.id !== photo.id);
        setPhotos(updated);
        setCurrentIndex((prev) => Math.min(prev, Math.max(0, updated.length - 1)));
        return;
      }
      setPhotos((prev) => prev.map((item) => (
        item.id === photo.id ? { ...item, is_favorite: response.data.is_favorite } : item
      )));
    } catch (error) {
      console.error('Error toggling favorite:', error);
      toast.error(apiErrorMessage(error, 'Error updating favorite'));
    }
  };

  const handleDelete = async () => {
    try {
      const photo = photos[currentIndex];
      await photosAPI.delete(photo.id);
      const updated = photos.filter((_, index) => index !== currentIndex);
      setPhotos(updated);
      setCurrentIndex((prev) => Math.min(prev, Math.max(0, updated.length - 1)));
      setDeleteNotice({
        photoId: photo.id,
        filename: photo.filename
      });
      loadFolderStats();
    } catch (error) {
      console.error('Error deleting photo:', error);
      toast.error(apiErrorMessage(error, 'Error deleting photo'));
    }
  };

  const handleUndoDelete = async () => {
    if (!deleteNotice) {
      return;
    }

    try {
      await photosAPI.restore(deleteNotice.photoId);
      setDeleteNotice(null);
      await loadPhotos();
      await loadFolderStats();
    } catch (error) {
      console.error('Error restoring photo:', error);
      toast.error(apiErrorMessage(error, 'Error restoring photo'));
    }
  };

  const transformCurrentPhoto = async (request, errorMessage) => {
    try {
      setRotationLoading(true);
      const photo = photos[currentIndex];
      await request(photo.id);
      const response = await photosAPI.get(photo.id);
      setPhotos((prev) => prev.map((item) => (item.id === photo.id ? response.data : item)));
      setImageRevision((prev) => prev + 1);
    } catch (error) {
      console.error(errorMessage, error);
      toast.error(apiErrorMessage(error, errorMessage));
    } finally {
      setRotationLoading(false);
    }
  };

  const handleRotate = (degrees = 90) => transformCurrentPhoto(
    (photoId) => photosAPI.rotate(photoId, degrees), 'Error rotating photo'
  );

  const handleFlip = (direction = 'horizontal') => transformCurrentPhoto(
    (photoId) => photosAPI.flip(photoId, direction), 'Error flipping photo'
  );

  const handleToggleImageVersion = () => {
    setShowWebVersion((prev) => !prev);
  };

  const hasLocation = currentPhoto?.gps_latitude != null && currentPhoto?.gps_longitude != null;

  const handleShowOnMap = () => {
    navigate(hasLocation ? `/map/${folderId}?focus=${currentPhoto.id}` : `/map/${folderId}`);
  };

  const showNearby = (latitude, longitude, radiusKm, photoId) => {
    navigate(`/gallery/${folderId}?${toQueryString({
      near_lat: latitude,
      near_lon: longitude,
      radius_km: radiusKm,
      photo: photoId,
      favorites: favoritesOnly ? 1 : null
    })}`);
  };

  const handleShowNearby = () => {
    if (hasLocation) {
      showNearby(currentPhoto.gps_latitude, currentPhoto.gps_longitude, 1, currentPhoto.id);
    }
  };

  const handleToggleFavoritesOnly = () => {
    const next = new URLSearchParams(searchParams);
    if (favoritesOnly) {
      next.delete('favorites');
    } else {
      next.set('favorites', '1');
    }
    setSearchParams(next);
  };

  const handleChangeRadius = (radiusKm) => {
    const { near_lat: latitude, near_lon: longitude } = positionFilter.params;
    showNearby(latitude, longitude, radiusKm, currentPhoto?.id);
  };

  // The listener is registered once and always calls the latest handlers
  const keyHandlersRef = useRef(null);
  keyHandlersRef.current = {
    ArrowRight: handleNext,
    ArrowLeft: handlePrevious,
    f: handleToggleFavorite,
    d: handleDelete,
    Delete: handleDelete,
    h: () => handleFlip('horizontal'),
    r: () => handleRotate(90),
    v: handleToggleImageVersion,
    m: handleShowOnMap
  };

  useEffect(() => {
    const handleKeyPress = (event) => {
      if (event.target.closest?.('input, textarea') || document.querySelector('.keyboard-shortcuts-overlay')) {
        return;
      }
      const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
      keyHandlersRef.current[key]?.();
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, []);

  if (loading) {
    return (
      <div className="gallery-loading">
        <div className="spinner"></div>
        <p>Loading photos...</p>
      </div>
    );
  }

  if (photos.length === 0) {
    return (
      <div className="gallery-empty">
        <h2>No Photos Found</h2>
        {positionFilter || favoritesOnly ? (
          <>
            <p>
              {favoritesOnly && !positionFilter
                ? 'No favorites yet: mark photos with the star (F).'
                : 'No photos match this filter.'}
            </p>
            <button className="btn btn-primary" onClick={() => navigate(`/gallery/${folderId}`)}>
              Show all photos
            </button>
          </>
        ) : (
          <>
            <p>This folder does not contain any photos yet.</p>
            <button className="btn btn-primary" onClick={() => navigate('/')}>
              Back to Home
            </button>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="gallery-page">
      <div className="gallery-header">
        <button className="btn btn-secondary" onClick={() => navigate('/')}>
          <ArrowLeft size={20} />
          Back
        </button>

        <div className="gallery-info">
          <h2>{folderStats?.name || 'Gallery'}</h2>
          <ProgressBar current={currentIndex + 1} total={photos.length} />
          {taskId && (
            <span>
              Task {backgroundStatus || 'pending'} {backgroundTaskRunning ? `(${backgroundProgress}%)` : ''}
            </span>
          )}
        </div>

        <div className="gallery-actions">
          {!folderStats?.has_thumbs && (
            <button
              className="btn btn-primary"
              onClick={handleGenerateThumbs}
              disabled={generatingThumbs}
            >
              {generatingThumbs ? (
                <>
                  <Loader className="animate-spin" size={20} />
                  Generating...
                </>
              ) : (
                'Generate Thumbnails'
              )}
            </button>
          )}

          <button
            className="btn btn-primary"
            onClick={() => navigate(`/compare/${folderId}`)}
            title="Find and remove duplicates"
          >
            <Search size={20} />
            Find Duplicates
          </button>

          <button
            className="btn btn-primary"
            onClick={handleShowOnMap}
            title="Photo map (M)"
          >
            <MapIcon size={20} />
            Map
          </button>

          <button
            className={`btn btn-secondary ${favoritesOnly ? 'btn-filter-active' : ''}`}
            onClick={handleToggleFavoritesOnly}
            title={favoritesOnly ? 'Show all photos' : 'Show only favorites'}
          >
            <Star size={20} fill={favoritesOnly ? 'currentColor' : 'none'} />
            Favorites
          </button>

          <button
            className={`btn ${currentPhoto.is_favorite ? 'btn-warning' : 'btn-secondary'}`}
            onClick={handleToggleFavorite}
            title="Favorite (F)"
          >
            <Star size={20} fill={currentPhoto.is_favorite ? 'currentColor' : 'none'} />
          </button>

          <button
            className="btn btn-secondary"
            onClick={() => handleRotate(90)}
            disabled={rotationLoading}
            title="Rotate 90 deg (R)"
          >
            <RotateCw size={20} />
          </button>

          <button
            className="btn btn-secondary"
            onClick={() => handleFlip('horizontal')}
            disabled={rotationLoading}
            title="Flip Horizontal (H)"
          >
            <FlipHorizontal2 size={20} />
          </button>

          <button
            className="btn btn-info"
            onClick={handleGenerateWeb}
            disabled={generatingWeb}
            title="Generate Web Version"
          >
            {generatingWeb ? <Loader size={20} className="spinning" /> : <Monitor size={20} />}
          </button>

          <button
            className="btn btn-info"
            onClick={handleGenerateThumbs}
            disabled={generatingThumbs}
            title="Generate Thumbnails"
          >
            {generatingThumbs ? <Loader size={20} className="spinning" /> : <FileImage size={20} />}
          </button>

          <button
            className={`btn ${isShowingWebVersion ? 'btn-success' : 'btn-secondary'}`}
            onClick={handleToggleImageVersion}
            title={
              currentPhoto.has_web
                ? (isShowingWebVersion ? 'Show original (V)' : 'Show web version (V)')
                : 'No web version available'
            }
            disabled={!currentPhoto.has_web}
          >
            {isShowingWebVersion ? <Monitor size={20} /> : <FileImage size={20} />}
            {isShowingWebVersion ? 'Web' : 'Original'}
          </button>

          <button
            className="btn btn-danger"
            onClick={handleDelete}
            title="Delete (D or Del)"
          >
            <Trash2 size={20} />
          </button>
        </div>
      </div>

      {(positionFilter || favoritesOnly) && (
        <div className="gallery-filter-bar">
          {positionFilter ? <MapPin size={16} /> : <Star size={16} fill="currentColor" />}
          {!positionFilter && (
            <span>Showing {photos.length} favorite photos</span>
          )}
          {positionFilter?.type === 'area' && (
            <span>Showing {photos.length} {favoritesOnly ? 'favorite ' : ''}photos in the selected map area</span>
          )}
          {positionFilter?.type === 'near' && (
            <span>
              Showing {photos.length} {favoritesOnly ? 'favorite ' : ''}photos within{' '}
              <select
                value={positionFilter.params.radius_km}
                onChange={(event) => handleChangeRadius(Number(event.target.value))}
              >
                {[...new Set([...NEARBY_RADII_KM, positionFilter.params.radius_km])]
                  .sort((a, b) => a - b)
                  .map((radius) => (
                    <option key={radius} value={radius}>{radius} km</option>
                  ))}
              </select>
            </span>
          )}
          {positionFilter?.type === 'area' && (
            <button className="btn btn-secondary" onClick={() => navigate(`/map/${folderId}`)}>
              Back to map
            </button>
          )}
          <button className="btn btn-secondary" onClick={() => navigate(`/gallery/${folderId}`)} title="Show all photos">
            <X size={16} />
            Show all
          </button>
        </div>
      )}

      <div className="gallery-content">
        <PhotoViewer
          photo={currentPhoto}
          src={mainPhotoSrc}
          isShowingWebVersion={isShowingWebVersion}
          onPrevious={handlePrevious}
          onNext={handleNext}
          deleteNotice={deleteNotice}
          onUndoDelete={handleUndoDelete}
          onDismissDeleteNotice={() => setDeleteNotice(null)}
          onShowOnMap={handleShowOnMap}
          onShowNearby={handleShowNearby}
        />
      </div>

      <ThumbnailStrip
        photos={photos}
        currentIndex={currentIndex}
        selectedIds={selectedIds}
        onSelect={setCurrentIndex}
        onToggleSelection={handleToggleSelection}
      />

      <BatchActionBar
        selectedIds={Array.from(selectedIds)}
        total={photos.length}
        onFavorite={handleBatchFavorite}
        onDelete={handleBatchDelete}
        onClear={handleClearSelection}
        isLoading={batchLoading}
      />
    </div>
  );
}

export default Gallery;
