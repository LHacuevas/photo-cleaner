import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  FileImage,
  FlipHorizontal2,
  Loader,
  Monitor,
  RotateCw,
  Search,
  Star,
  Trash2,
  X
} from 'lucide-react';
import { foldersAPI, photosAPI } from '../services/api';
import ProgressBar from '../components/ProgressBar';
import useBackgroundTask from '../hooks/useBackgroundTask';
import './Gallery.css';

function Gallery() {
  const { folderId } = useParams();
  const navigate = useNavigate();

  const [photos, setPhotos] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [folderStats, setFolderStats] = useState(null);
  const [webMode] = useState('web');
  const [showWebVersion, setShowWebVersion] = useState(true);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [batchLoading, setBatchLoading] = useState(false);
  const [rotationLoading, setRotationLoading] = useState(false);
  const [taskKind, setTaskKind] = useState(null);
  const [imageRevision, setImageRevision] = useState(0);
  const [deleteNotice, setDeleteNotice] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const thumbnailStripRef = useRef(null);
  const thumbnailRefs = useRef({});
  const panStartRef = useRef({ x: 0, y: 0, panX: 0, panY: 0 });

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
  const currentPhoto = photos[currentIndex];
  const isShowingWebVersion = Boolean(currentPhoto?.has_web && showWebVersion);
  const mainPhotoSrc = currentPhoto
    ? `${photosAPI.getFile(currentPhoto.id, false, isShowingWebVersion)}&rev=${imageRevision}`
    : '';
  const displayedWidth = isShowingWebVersion
    ? (currentPhoto?.web_width || currentPhoto?.width)
    : currentPhoto?.width;
  const displayedHeight = isShowingWebVersion
    ? (currentPhoto?.web_height || currentPhoto?.height)
    : currentPhoto?.height;
  const displayedSize = isShowingWebVersion
    ? (currentPhoto?.web_size || currentPhoto?.size)
    : currentPhoto?.size;

  useEffect(() => {
    loadPhotos();
    loadFolderStats();
  }, [folderId]);

  useEffect(() => {
    if (!backgroundTaskResult) {
      return;
    }

    loadPhotos();
    loadFolderStats();
    setTaskKind(null);
  }, [backgroundTaskResult]);

  useEffect(() => {
    if (!backgroundTaskError) {
      return;
    }

    alert('Background task failed');
    setTaskKind(null);
  }, [backgroundTaskError]);

  useEffect(() => {
    const strip = thumbnailStripRef.current;
    const activeThumbnail = thumbnailRefs.current[currentPhoto?.id];

    if (!strip || !activeThumbnail) {
      return;
    }

    const targetScrollLeft =
      activeThumbnail.offsetLeft - (strip.clientWidth / 2) + (activeThumbnail.clientWidth / 2);

    strip.scrollTo({
      left: Math.max(0, targetScrollLeft),
      behavior: 'smooth'
    });
  }, [currentIndex, currentPhoto?.id]);

  useEffect(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setIsPanning(false);
  }, [currentPhoto?.id, isShowingWebVersion]);

  const formatFileSize = (bytes) => {
    if (!bytes) {
      return 'N/A';
    }

    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const exponent = Math.min(
      Math.floor(Math.log(bytes) / Math.log(1024)),
      units.length - 1
    );
    const value = bytes / (1024 ** exponent);
    return `${value.toFixed(value >= 10 || exponent === 0 ? 0 : 1)} ${units[exponent]}`;
  };

  const loadPhotos = async () => {
    try {
      setLoading(true);
      const response = await photosAPI.list(folderId, { limit: 1000 });
      const nextPhotos = response.data.photos || [];
      setPhotos(nextPhotos);
      setCurrentIndex((prev) => Math.min(prev, Math.max(0, nextPhotos.length - 1)));
      setSelectedIds(new Set());
    } catch (error) {
      console.error('Error loading photos:', error);
      alert('Error loading photos');
    } finally {
      setLoading(false);
    }
  };

  const loadFolderStats = async () => {
    try {
      const response = await foldersAPI.getStats(folderId);
      setFolderStats(response.data);
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  };

  const handleGenerateWeb = async () => {
    try {
      const response = await photosAPI.generateWebAsync(folderId, webMode);
      if (!response.data.task_id) {
        alert(response.data.message);
        loadPhotos();
        loadFolderStats();
        return;
      }
      setTaskKind('web');
      setTaskId(response.data.task_id);
    } catch (error) {
      console.error('Error generating web versions:', error);
      alert('Error generating web versions');
    }
  };

  const handleGenerateThumbs = async () => {
    try {
      const response = await photosAPI.generateThumbsAsync(folderId);
      if (!response.data.task_id) {
        alert(response.data.message);
        loadPhotos();
        loadFolderStats();
        return;
      }
      setTaskKind('thumbs');
      setTaskId(response.data.task_id);
    } catch (error) {
      console.error('Error generating thumbnails:', error);
      alert('Error generating thumbnails');
    }
  };

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
      alert(response.data.message);
      setPhotos((prev) => prev.map((photo) => (
        selectedIds.has(photo.id) ? { ...photo, is_favorite: true } : photo
      )));
      setSelectedIds(new Set());
    } catch (error) {
      console.error('Error in batch favorite:', error);
      alert('Error marking favorites');
    } finally {
      setBatchLoading(false);
    }
  };

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) {
      return;
    }

    if (!window.confirm(`Delete ${selectedIds.size} photos?`)) {
      return;
    }

    try {
      setBatchLoading(true);
      const response = await photosAPI.batchOperation('delete', Array.from(selectedIds));
      alert(response.data.message);
      const updated = photos.filter((photo) => !selectedIds.has(photo.id));
      setPhotos(updated);
      setSelectedIds(new Set());
      setCurrentIndex((prev) => Math.min(prev, Math.max(0, updated.length - 1)));
      loadFolderStats();
    } catch (error) {
      console.error('Error in batch delete:', error);
      alert('Error deleting photos');
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
      await photosAPI.toggleFavorite(photo.id);
      setPhotos((prev) => {
        const updated = [...prev];
        updated[currentIndex] = {
          ...updated[currentIndex],
          is_favorite: !updated[currentIndex].is_favorite
        };
        return updated;
      });
    } catch (error) {
      console.error('Error toggling favorite:', error);
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
      alert('Error restoring photo');
    }
  };

  const handleRotate = async (degrees = 90) => {
    try {
      setRotationLoading(true);
      const photo = photos[currentIndex];
      await photosAPI.rotate(photo.id, degrees);
      const response = await photosAPI.get(photo.id);
      setPhotos((prev) => {
        const updated = [...prev];
        updated[currentIndex] = response.data;
        return updated;
      });
      setImageRevision((prev) => prev + 1);
    } catch (error) {
      console.error('Error rotating photo:', error);
      alert('Error rotating photo');
    } finally {
      setRotationLoading(false);
    }
  };

  const handleFlip = async (direction = 'horizontal') => {
    try {
      setRotationLoading(true);
      const photo = photos[currentIndex];
      await photosAPI.flip(photo.id, direction);
      const response = await photosAPI.get(photo.id);
      setPhotos((prev) => {
        const updated = [...prev];
        updated[currentIndex] = response.data;
        return updated;
      });
      setImageRevision((prev) => prev + 1);
    } catch (error) {
      console.error('Error flipping photo:', error);
      alert('Error flipping photo');
    } finally {
      setRotationLoading(false);
    }
  };

  const handleToggleImageVersion = () => {
    setShowWebVersion((prev) => !prev);
  };

  const handleWheelZoom = (event) => {
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

  const handlePointerDown = (event) => {
    if (zoom <= 1) {
      return;
    }

    event.preventDefault();
    setIsPanning(true);
    panStartRef.current = {
      x: event.clientX,
      y: event.clientY,
      panX: pan.x,
      panY: pan.y
    };
  };

  const handlePointerMove = (event) => {
    if (!isPanning) {
      return;
    }

    const deltaX = event.clientX - panStartRef.current.x;
    const deltaY = event.clientY - panStartRef.current.y;
    setPan({
      x: panStartRef.current.panX + deltaX,
      y: panStartRef.current.panY + deltaY
    });
  };

  const handlePointerUp = () => {
    setIsPanning(false);
  };

  useEffect(() => {
    const handleKeyPress = (event) => {
      switch (event.key) {
        case 'ArrowRight':
          handleNext();
          break;
        case 'ArrowLeft':
          handlePrevious();
          break;
        case 'f':
        case 'F':
          handleToggleFavorite();
          break;
        case 'd':
        case 'D':
        case 'Delete':
          handleDelete();
          break;
        case 'h':
        case 'H':
          handleFlip('horizontal');
          break;
        case 'r':
        case 'R':
          handleRotate(90);
          break;
        case 'v':
        case 'V':
          handleToggleImageVersion();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [currentIndex, photos]);

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
        <p>This folder doesn't contain any photos yet.</p>
        <button className="btn btn-primary" onClick={() => navigate('/')}>
          Back to Home
        </button>
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
                ? (isShowingWebVersion ? 'Mostra originale' : 'Mostra versione web')
                : 'Versione web non disponibile'
            }
            disabled={!currentPhoto.has_web}
          >
            {isShowingWebVersion ? <Monitor size={20} /> : <FileImage size={20} />}
            {isShowingWebVersion ? 'Web' : 'Originale'}
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

      <div className="gallery-content">
        <div className="gallery-viewer">
          <button className="nav-btn nav-prev" onClick={handlePrevious}>
            <ChevronLeft size={32} />
          </button>

          <div className="photo-container" key={`${currentPhoto.id}-${isShowingWebVersion ? 'web' : 'original'}`}>
            <div className="photo-info">
              <h3>{currentPhoto.filename}</h3>
              <span className="version-indicator">
                Visualizzazione: {isShowingWebVersion ? 'Web' : 'Originale'}
              </span>
              <span className="photo-meta">
                Risoluzione: {displayedWidth || '?'} x {displayedHeight || '?'}
              </span>
              <span className="photo-meta">
                Dimensione: {formatFileSize(displayedSize)}
              </span>
              {currentPhoto.camera_model && (
                <span className="photo-meta">
                  Fotocamera: {currentPhoto.camera_model}
                </span>
              )}
              {currentPhoto.date_taken && (
                <span className="photo-meta">
                  Data: {new Date(currentPhoto.date_taken).toLocaleString()}
                </span>
              )}
              {(currentPhoto.gps_latitude || currentPhoto.gps_longitude) && (
                <span className="photo-meta">
                  Posizione: {currentPhoto.gps_latitude ?? '?'}, {currentPhoto.gps_longitude ?? '?'}
                </span>
              )}
              {deleteNotice && (
                <div className="delete-notice">
                  <div className="delete-notice-text">
                    <span>{deleteNotice.filename} moved to cancellate.</span>
                  </div>
                  <div className="delete-notice-actions">
                    <button className="btn btn-secondary" onClick={handleUndoDelete}>
                      Undo
                    </button>
                    <button
                      className="delete-notice-close"
                      onClick={() => setDeleteNotice(null)}
                      title="Close"
                    >
                      <X size={16} />
                    </button>
                  </div>
                </div>
              )}
            </div>
            <div
              className={`main-photo-stage ${zoom > 1 ? 'is-zoomed' : ''} ${isPanning ? 'is-panning' : ''}`}
              onWheel={handleWheelZoom}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
              onPointerLeave={handlePointerUp}
            >
              <img
                key={mainPhotoSrc}
                src={mainPhotoSrc}
                alt={currentPhoto.filename}
                className="main-photo"
                onPointerDown={handlePointerDown}
                draggable={false}
                style={{
                  transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`
                }}
              />
            </div>
          </div>

          <button className="nav-btn nav-next" onClick={handleNext}>
            <ChevronRight size={32} />
          </button>
        </div>

      </div>

      <div className="thumbnail-strip" ref={thumbnailStripRef}>
        {photos.map((photo, index) => (
          <div
            key={photo.id}
            ref={(node) => {
              if (node) {
                thumbnailRefs.current[photo.id] = node;
              } else {
                delete thumbnailRefs.current[photo.id];
              }
            }}
            className={`thumbnail ${index === currentIndex ? 'active' : ''} ${selectedIds.has(photo.id) ? 'selected' : ''}`}
            onClick={(event) => {
              if (event.ctrlKey || event.metaKey) {
                handleToggleSelection(photo.id);
                return;
              }
              setCurrentIndex(index);
            }}
            title={selectedIds.has(photo.id) ? 'Ctrl+Click to deselect' : 'Ctrl+Click to select'}
          >
            <img
              src={photo.has_thumb ? photosAPI.getFile(photo.id, true) : photosAPI.getFile(photo.id)}
              alt={photo.filename}
            />
            {photo.is_favorite && <Star className="fav-badge" size={16} />}
            {selectedIds.has(photo.id) && <div className="selection-badge">OK</div>}
          </div>
        ))}
      </div>

    </div>
  );
}

export default Gallery;
