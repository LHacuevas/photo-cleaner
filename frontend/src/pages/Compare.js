import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ChevronLeft, ChevronRight, FileImage, Loader, Monitor, SkipForward, Trash2 } from 'lucide-react';
import { photosAPI, similarAPI } from '../services/api';
import ProgressBar from '../components/ProgressBar';
import './Compare.css';

function Compare() {
  const { folderId } = useParams();
  const navigate = useNavigate();

  const [groups, setGroups] = useState([]);
  const [currentGroupIdx, setCurrentGroupIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedPhotos, setSelectedPhotos] = useState([]);
  const [photoVersions, setPhotoVersions] = useState({});

  useEffect(() => {
    loadGroups();
  }, [folderId]);

  const loadGroups = async () => {
    try {
      setLoading(true);
      await similarAPI.analyze(folderId);
      const groupsResponse = await similarAPI.getGroups(folderId, false);
      const groupSummaries = groupsResponse.data.groups || [];
      const detailResponses = await Promise.all(
        groupSummaries.map((group) => similarAPI.getGroup(group.id))
      );
      const nextGroups = detailResponses.map((response) => response.data);
      setGroups(nextGroups);
      setCurrentGroupIdx(0);
      setSelectedPhotos([]);
      setPhotoVersions({});
    } catch (error) {
      console.error('Error loading groups:', error);
      alert('Error loading similar photos. Make sure to analyze first.');
    } finally {
      setLoading(false);
    }
  };

  const currentGroup = groups[currentGroupIdx];

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

    alert('All groups reviewed!');
    navigate(`/gallery/${folderId}`);
  };

  const handleDeleteSelected = async () => {
    if (selectedPhotos.length === 0) {
      alert('Please select at least one photo to delete');
      return;
    }

    if (!window.confirm(`Delete ${selectedPhotos.length} selected photo(s)?`)) {
      return;
    }

    try {
      await Promise.all(selectedPhotos.map((photoId) => photosAPI.delete(photoId)));
      moveToNextGroup();
    } catch (error) {
      console.error('Error deleting photos:', error);
      alert('Error deleting photos');
    }
  };

  const handleDeleteOthers = async () => {
    const othersToDelete = currentGroup.photos
      .filter((photo) => !selectedPhotos.includes(photo.id))
      .map((photo) => photo.id);

    if (othersToDelete.length === 0) {
      alert('No other photos to delete');
      return;
    }

    if (!window.confirm(`Delete ${othersToDelete.length} other photo(s)?`)) {
      return;
    }

    try {
      await Promise.all(othersToDelete.map((photoId) => photosAPI.delete(photoId)));
      moveToNextGroup();
    } catch (error) {
      console.error('Error deleting photos:', error);
      alert('Error deleting photos');
    }
  };

  const handleSkipGroup = async () => {
    try {
      await similarAPI.skipGroup(currentGroup.id);
      moveToNextGroup();
    } catch (error) {
      console.error('Error skipping group:', error);
    }
  };

  useEffect(() => {
    const handleKeyPress = (event) => {
      if (loading || groups.length === 0) {
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

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [currentGroup, currentGroupIdx, groups, loading, selectedPhotos]);

  if (loading) {
    return (
      <div className="compare-loading">
        <Loader className="spinner" size={48} />
        <p>Analyzing photos for similarities...</p>
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
