import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader, Trash2, SkipForward, ChevronLeft, ChevronRight } from 'lucide-react';
import { similarAPI, photosAPI } from '../services/api';
import ProgressBar from '../components/ProgressBar';
import './Compare.css';

function Compare() {
  const { folderId } = useParams();
  const navigate = useNavigate();

  const [groups, setGroups] = useState([]);
  const [currentGroupIdx, setCurrentGroupIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [selectedPhotos, setSelectedPhotos] = useState([]);

  useEffect(() => {
    loadGroups();
  }, [folderId]);

  const loadGroups = async () => {
    try {
      setLoading(true);
      // First, analyze for similar photos
      await similarAPI.analyze(folderId);
      // Then get grouped results
      const response = await similarAPI.getGroups(folderId, false);
      setGroups(response.data.groups || []);
      setSelectedPhotos([]);
    } catch (error) {
      console.error('Error loading groups:', error);
      alert('Error loading similar photos. Make sure to analyze first.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPhoto = (photoId) => {
    if (selectedPhotos.includes(photoId)) {
      setSelectedPhotos(selectedPhotos.filter(id => id !== photoId));
    } else {
      setSelectedPhotos([...selectedPhotos, photoId]);
    }
  };

  const handleSelectByNumber = (number) => {
    const current = currentGroup;
    if (number > 0 && number <= current.photos.length) {
      handleSelectPhoto(current.photos[number - 1].id);
    }
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
      // Delete selected photos
      await Promise.all(
        selectedPhotos.map(photoId => photosAPI.delete(photoId))
      );
      
      // Move to next group
      handleSkipGroup();
    } catch (error) {
      console.error('Error deleting photos:', error);
      alert('Error deleting photos');
    }
  };

  const handleDeleteOthers = async () => {
    const current = currentGroup;
    const othersToDelete = current.photos
      .filter(p => !selectedPhotos.includes(p.id))
      .map(p => p.id);

    if (othersToDelete.length === 0) {
      alert('No other photos to delete');
      return;
    }

    if (!window.confirm(`Delete ${othersToDelete.length} other photo(s)?`)) {
      return;
    }

    try {
      // Delete other photos
      await Promise.all(
        othersToDelete.map(photoId => photosAPI.delete(photoId))
      );
      
      // Move to next group
      handleSkipGroup();
    } catch (error) {
      console.error('Error deleting photos:', error);
      alert('Error deleting photos');
    }
  };

  const handleSkipGroup = async () => {
    try {
      const current = currentGroup;
      await similarAPI.skipGroup(current.id);
      
      if (currentGroupIdx < groups.length - 1) {
        setCurrentGroupIdx(currentGroupIdx + 1);
        setSelectedPhotos([]);
      } else {
        alert('✅ All groups reviewed!');
        navigate(`/gallery/${folderId}`);
      }
    } catch (error) {
      console.error('Error skipping group:', error);
    }
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e) => {
      if (loading || groups.length === 0) return;

      // Numbers 1-4 for selecting photos
      if (e.key >= '1' && e.key <= '4') {
        handleSelectByNumber(parseInt(e.key));
      }

      // Arrow keys for navigation
      switch(e.key) {
        case 'ArrowLeft':
          if (currentGroupIdx > 0) setCurrentGroupIdx(currentGroupIdx - 1);
          setSelectedPhotos([]);
          break;
        case 'ArrowRight':
          if (currentGroupIdx < groups.length - 1) setCurrentGroupIdx(currentGroupIdx + 1);
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
  }, [currentGroupIdx, groups, loading]);

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

  const currentGroup = groups[currentGroupIdx];
  const progressPercentage = ((currentGroupIdx + 1) / groups.length) * 100;

  return (
    <div className="compare-page">
      <div className="compare-header">
        <button className="btn btn-secondary" onClick={() => navigate(`/gallery/${folderId}`)}>
          <ArrowLeft size={20} />
          Back
        </button>

        <div className="compare-info">
          <h2>🔍 Find & Remove Duplicates</h2>
          <ProgressBar current={currentGroupIdx + 1} total={groups.length} />
        </div>

        <div className="compare-stats">
          <span>{currentGroup.photos.length} similar photos</span>
        </div>
      </div>

      <div className="compare-content">
        <div className="photos-grid">
          {currentGroup.photos.map((photo, idx) => (
            <div
              key={photo.id}
              className={`photo-card ${selectedPhotos.includes(photo.id) ? 'selected' : ''}`}
              onClick={() => handleSelectPhoto(photo.id)}
            >
              <div className="card-number">{idx + 1}</div>
              <img
                src={photosAPI.getFile(photo.id, true) || photosAPI.getFile(photo.id, false)}
                alt={photo.filename}
                className="card-image"
              />
              <div className="card-info">
                <div className="filename">{photo.filename}</div>
                <div className="checkbox">
                  <input
                    type="checkbox"
                    checked={selectedPhotos.includes(photo.id)}
                    onChange={(e) => {
                      e.stopPropagation();
                      handleSelectPhoto(photo.id);
                    }}
                  />
                </div>
              </div>
            </div>
          ))}
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
          <span>← → Navigate groups</span>
          <span>S Skip</span>
          <span>Delete/Delete others</span>
        </div>
      </div>
    </div>
  );
}

export default Compare;

