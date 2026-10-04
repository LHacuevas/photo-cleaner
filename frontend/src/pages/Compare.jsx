import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ChevronLeft, ChevronRight, FileImage, Loader, Monitor, SkipForward, Trash2 } from 'lucide-react';
import { apiErrorMessage, photosAPI, similarAPI } from '../services/api';
import ProgressBar from '../components/ProgressBar';
import { useToast } from '../components/Toast';
import { formatFileSize } from '../utils/format';
import './Compare.css';

function Compare() {
  const { folderId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();

  const [groups, setGroups] = useState([]);
  const [currentGroupIdx, setCurrentGroupIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedPhotos, setSelectedPhotos] = useState([]);
  const [photoVersions, setPhotoVersions] = useState({});
  const [analysisProgress, setAnalysisProgress] = useState(null);

  const loadGroups = useCallback(async () => {
    const fetchPendingGroups = async () => {
      const groupsResponse = await similarAPI.getGroups(folderId, true);
      const detailResponses = await Promise.all(
        (groupsResponse.data.groups || []).map((group) => similarAPI.getGroup(group.id))
      );
      // Photos deleted from the gallery since grouping are no longer candidates
      return detailResponses
        .map((response) => ({
          ...response.data,
          photos: response.data.photos.filter((photo) => !photo.is_deleted)
        }))
        .filter((group) => group.photos.length > 1);
    };

    // Grouping only sees photos with hashes, so wait for any pending analysis first
    const waitForAnalysis = async () => {
      const response = await similarAPI.analyze(folderId);
      const { task_id: taskId } = response.data;
      if (!taskId) {
        return;
      }

      for (;;) {
        const { data: task } = await photosAPI.getTaskStatus(taskId);
        setAnalysisProgress(task.progress);
        if (['completed', 'failed', 'cancelled'].includes(task.status)) {
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    };

    try {
      setLoading(true);
      let nextGroups = await fetchPendingGroups();
      if (nextGroups.length === 0) {
        await waitForAnalysis();
        await similarAPI.group(folderId);
        nextGroups = await fetchPendingGroups();
      }
      setGroups(nextGroups);
      setCurrentGroupIdx(0);
      setSelectedPhotos([]);
      setPhotoVersions({});
    } catch (error) {
      console.error('Error loading groups:', error);
      toast.error(apiErrorMessage(error, 'Error loading similar photos'));
    } finally {
      setLoading(false);
      setAnalysisProgress(null);
    }
  }, [folderId, toast]);

  useEffect(() => {
    loadGroups();
  }, [loadGroups]);

  const currentGroup = groups[currentGroupIdx];

  const isPhotoUsingWeb = (photo) => Boolean(photo.has_web && photoVersions[photo.id]);

  const getDisplayedDimensions = (photo) => ({
    width: isPhotoUsingWeb(photo) ? (photo.web_width || photo.width) : photo.width,
    height: isPhotoUsingWeb(photo) ? (photo.web_height || photo.height) : photo.height
  });

  const getDisplayedSize = (photo) => (
    isPhotoUsingWeb(photo) ? (photo.web_size || photo.size) : photo.size
  );

  const handleSelectPhoto = (photoId) => {
    setSelectedPhotos((prev) => (
      prev.includes(photoId)
        ? prev.filter((id) => id !== photoId)
        : [...prev, photoId]
    ));
  };

  const handleSelectByNumber = (number) => {
    if (!currentGroup || number < 1 || number > currentGroup.photos.length) {
      return;
    }
    handleSelectPhoto(currentGroup.photos[number - 1].id);
  };

  const handleTogglePhotoVersion = (event, photo) => {
    event.stopPropagation();
    if (!photo.has_web) {
      return;
    }

    setPhotoVersions((prev) => ({
      ...prev,
      [photo.id]: !prev[photo.id]
    }));
  };

  const moveToNextGroup = () => {
    if (currentGroupIdx < groups.length - 1) {
      setCurrentGroupIdx((prev) => prev + 1);
      setSelectedPhotos([]);
      return;
    }

    toast.success('All groups reviewed!');
    navigate(`/gallery/${folderId}`);
  };

  const handleDeleteSelected = async () => {
    if (selectedPhotos.length === 0) {
      toast.info('Select at least one photo to delete');
      return;
    }

    if (!window.confirm(`Delete ${selectedPhotos.length} selected photo(s)?`)) {
      return;
    }

    try {
      await Promise.all(selectedPhotos.map((photoId) => photosAPI.delete(photoId)));
      await similarAPI.skipGroup(currentGroup.id);
      moveToNextGroup();
    } catch (error) {
      console.error('Error deleting photos:', error);
      toast.error(apiErrorMessage(error, 'Error deleting photos'));
    }
  };

  const handleDeleteOthers = async () => {
    const othersToDelete = currentGroup.photos
      .filter((photo) => !selectedPhotos.includes(photo.id))
      .map((photo) => photo.id);

    if (othersToDelete.length === 0) {
      toast.info('No other photos to delete');
      return;
    }

    if (!window.confirm(`Delete ${othersToDelete.length} other photo(s)?`)) {
      return;
    }

    try {
      await Promise.all(othersToDelete.map((photoId) => photosAPI.delete(photoId)));
      await similarAPI.skipGroup(currentGroup.id);
      moveToNextGroup();
    } catch (error) {
      console.error('Error deleting photos:', error);
      toast.error(apiErrorMessage(error, 'Error deleting photos'));
    }
  };

  const handleSkipGroup = async () => {
    try {
      await similarAPI.skipGroup(currentGroup.id);
      moveToNextGroup();
    } catch (error) {
      console.error('Error skipping group:', error);
      toast.error(apiErrorMessage(error, 'Error skipping group'));
    }
  };

  // The listener is registered once and always calls the latest handlers
  const keyHandlerRef = useRef(null);
  keyHandlerRef.current = (event) => {
    if (loading || groups.length === 0 || document.querySelector('.keyboard-shortcuts-overlay')) {
      return;
    }

    if (event.key >= '1' && event.key <= '9') {
      handleSelectByNumber(parseInt(event.key, 10));
    }

    switch (event.key) {
      case 'ArrowLeft':
        setCurrentGroupIdx((prev) => Math.max(0, prev - 1));
        setSelectedPhotos([]);
        break;
      case 'ArrowRight':
        setCurrentGroupIdx((prev) => Math.min(groups.length - 1, prev + 1));
        setSelectedPhotos([]);
        break;
      case 's':
      case 'S':
        handleSkipGroup();
        break;
      default:
        break;
    }
  };

  useEffect(() => {
    const handleKeyPress = (event) => keyHandlerRef.current(event);
    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, []);

  if (loading) {
    return (
      <div className="compare-loading">
        <Loader className="spinner" size={48} />
        <p>
          Analyzing photos for similarities...
          {analysisProgress !== null && ` ${analysisProgress}%`}
        </p>
      </div>
    );
  }

  if (groups.length === 0) {
    return (
      <div className="compare-empty">
        <h2>No Similar Photos Found</h2>
        <p>All photos in this folder appear to be unique!</p>
        <button className="btn btn-primary" onClick={() => navigate(`/gallery/${folderId}`)}>
          Back to Gallery
        </button>
      </div>
    );
  }

  return (
    <div className="compare-page">
      <div className="compare-header">
        <button className="btn btn-secondary" onClick={() => navigate(`/gallery/${folderId}`)}>
          <ArrowLeft size={20} />
          Back
        </button>

        <div className="compare-info">
          <h2>Find and Remove Duplicates</h2>
          <ProgressBar current={currentGroupIdx + 1} total={groups.length} />
        </div>

        <div className="compare-stats">
          <span>{currentGroup.photos.length} similar photos</span>
        </div>
      </div>

      <div className="compare-content">
        <div className="photos-grid">
          {currentGroup.photos.map((photo, index) => {
            const showingWeb = isPhotoUsingWeb(photo);
            const displayedDimensions = getDisplayedDimensions(photo);
            const displayedSize = getDisplayedSize(photo);

            return (
              <div
                key={`${photo.id}-${showingWeb ? 'web' : 'original'}`}
                className={`photo-card ${selectedPhotos.includes(photo.id) ? 'selected' : ''}`}
                onClick={() => handleSelectPhoto(photo.id)}
              >
                <div className="card-number">{index + 1}</div>

                <button
                  className={`card-version-btn ${showingWeb ? 'is-web' : ''}`}
                  onClick={(event) => handleTogglePhotoVersion(event, photo)}
                  disabled={!photo.has_web}
                  title={photo.has_web ? 'Toggle Web/Original' : 'Web version not available'}
                >
                  {showingWeb ? <Monitor size={16} /> : <FileImage size={16} />}
                  {showingWeb ? 'Web' : 'Original'}
                </button>

                <img
                  src={photosAPI.getFile(photo.id, false, showingWeb)}
                  alt={photo.filename}
                  className="card-image"
                />

                <div className="card-info">
                  <div className="card-meta">
                    <div className="filename">{photo.filename}</div>
                    <div className="details">
                      <span>{displayedDimensions.width || '?'} x {displayedDimensions.height || '?'}</span>
                      <span>{formatFileSize(displayedSize)}</span>
                    </div>
                  </div>

                  <div className="checkbox">
                    <input
                      type="checkbox"
                      checked={selectedPhotos.includes(photo.id)}
                      onChange={(event) => {
                        event.stopPropagation();
                        handleSelectPhoto(photo.id);
                      }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="compare-footer">
        <div className="footer-actions">
          <button className="btn btn-secondary" onClick={() => setCurrentGroupIdx(Math.max(0, currentGroupIdx - 1))}>
            <ChevronLeft size={20} />
            Previous
          </button>

          <button className="btn btn-info" onClick={handleSkipGroup}>
            <SkipForward size={20} />
            Skip Group (S)
          </button>

          <button
            className="btn btn-danger"
            onClick={handleDeleteSelected}
            disabled={selectedPhotos.length === 0}
          >
            <Trash2 size={20} />
            Delete Selected ({selectedPhotos.length})
          </button>

          <button
            className="btn btn-warning"
            onClick={handleDeleteOthers}
            disabled={selectedPhotos.length === 0}
          >
            <Trash2 size={20} />
            Delete Others
          </button>

          <button
            className="btn btn-secondary"
            onClick={() => setCurrentGroupIdx(Math.min(groups.length - 1, currentGroupIdx + 1))}
          >
            Next
            <ChevronRight size={20} />
          </button>
        </div>

        <div className="keyboard-hints">
          <span>1-{currentGroup.photos.length} Select photo</span>
          <span>Left/Right Navigate groups</span>
          <span>S Skip</span>
          <span>Web/Original per photo card</span>
        </div>
      </div>
    </div>
  );
}

export default Compare;
