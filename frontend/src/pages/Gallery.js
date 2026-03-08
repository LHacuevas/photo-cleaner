import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Star, Trash2, ChevronLeft, ChevronRight, Loader, Info, Search } from 'lucide-react';
import { photosAPI, foldersAPI } from '../services/api';
import EXIFPanel from '../components/EXIFPanel';
import ProgressBar from '../components/ProgressBar';
import './Gallery.css';

function Gallery() {
  const { folderId } = useParams();
  const navigate = useNavigate();
  
  const [photos, setPhotos] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [folderStats, setFolderStats] = useState(null);
  const [generatingThumbs, setGeneratingThumbs] = useState(false);
  const [generatingWeb, setGeneratingWeb] = useState(false);
  const [webMode, setWebMode] = useState('web');
  const [generatingWeb, setGeneratingWeb] = useState(false);
  const [webMode, setWebMode] = useState('web');
  const [showExif, setShowExif] = useState(true);

  useEffect(() => {
    loadPhotos();
    loadFolderStats();
  }, [folderId]);

  const loadPhotos = async () => {
    try {
      setLoading(true);
      const response = await photosAPI.list(folderId, { limit: 1000 });
      setPhotos(response.data.photos);
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
    if (!window.confirm(`Generate web versions (${webMode} mode) for all photos? This may take several minutes.`)) {
      return;
    }

    try {
      setGeneratingWeb(true);
      const response = await photosAPI.generateWeb(folderId, webMode);
      alert(`✅ ${response.data.message || `Web versions (${webMode}) generated: ${response.data.success} success, ${response.data.errors} failed`}`);
      loadPhotos();
      loadFolderStats();
    } catch (error) {
      console.error('Error generating web versions:', error);
      alert('Error generating web versions');
    } finally {
      setGeneratingWeb(false);
    }
  };

  const handleGenerateThumbs = async () => {
    if (!window.confirm(`Generate thumbnails for all photos without thumbnails? This may take several minutes.`)) {
      return;
    }

    try {
      setGeneratingThumbs(true);
      const response = await photosAPI.generateThumbs(folderId);
      alert(`✅ ${response.data.message || `Thumbnails generated: ${response.data.success} success, ${response.data.errors} failed`}`);
      loadFolderStats();
    } catch (error) {
      console.error('Error generating thumbnails:', error);
      alert('Error generating thumbnails');
    } finally {
      setGeneratingThumbs(false);
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
      
      // Update local state
      const updated = [...photos];
      updated[currentIndex].is_favorite = !updated[currentIndex].is_favorite;
      setPhotos(updated);
    } catch (error) {
      console.error('Error toggling favorite:', error);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Move this photo to deleted folder?')) {
      return;
    }

    try {
      const photo = photos[currentIndex];
      await photosAPI.delete(photo.id);
      
      // Remove from list
      const updated = photos.filter((_, idx) => idx !== currentIndex);
      setPhotos(updated);
      
      if (currentIndex >= updated.length) {
        setCurrentIndex(Math.max(0, updated.length - 1));
      }
    } catch (error) {
      console.error('Error deleting photo:', error);
    }
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e) => {
      switch(e.key) {
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
          handleDelete();
          break;
        case 'i':
        case 'I':
          setShowExif(prev => !prev);
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

  const currentPhoto = photos[currentIndex];

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
            className={`btn ${showExif ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setShowExif(!showExif)}
            title="Toggle EXIF Panel"
          >
            <Info size={20} />
          </button>
          
          <button 
            className={`btn ${currentPhoto.is_favorite ? 'btn-warning' : 'btn-secondary'}`}
            onClick={handleToggleFavorite}
            title="Favorite (F)"
          >
            <Star size={20} fill={currentPhoto.is_favorite ? 'currentColor' : 'none'} />
          </button>
          
          <button 
            className="btn btn-danger"
            onClick={handleDelete}
            title="Delete (D)"
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

          <div className="photo-container">
            <img 
              src={photosAPI.getFile(currentPhoto.id, false)}
              alt={currentPhoto.filename}
              className="main-photo"
            />
            <div className="photo-filename">{currentPhoto.filename}</div>
          </div>

          <button className="nav-btn nav-next" onClick={handleNext}>
            <ChevronRight size={32} />
          </button>
        </div>

        {showExif && (
          <div className="exif-sidebar">
            <EXIFPanel photo={currentPhoto} />
          </div>
        )}
      </div>

      <div className="thumbnail-strip">
        {photos.map((photo, idx) => (
          <div
            key={photo.id}
            className={`thumbnail ${idx === currentIndex ? 'active' : ''}`}
            onClick={() => setCurrentIndex(idx)}
          >
            <img 
              src={photo.has_thumb ? photosAPI.getFile(photo.id, true) : photosAPI.getFile(photo.id, false)}
              alt={photo.filename}
            />
            {photo.is_favorite && <Star className="fav-badge" size={16} />}
          </div>
        ))}
      </div>

      <div className="keyboard-hints">
        <span>← → Navigate</span>
        <span>F Favorite</span>
        <span>D Delete</span>
        <span>I Toggle Info</span>
      </div>
    </div>
  );
}

export default Gallery;