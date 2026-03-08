import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Folder, Image, Star, Trash2, Loader } from 'lucide-react';
import { foldersAPI } from '../services/api';
import './Home.css';

function Home() {
  const navigate = useNavigate();
  const [folderPath, setFolderPath] = useState('');
  const [folders, setFolders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    loadFolders();
  }, []);

  const loadFolders = async () => {
    try {
      setLoading(true);
      const response = await foldersAPI.list();
      setFolders(response.data);
    } catch (error) {
      console.error('Error loading folders:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleScanFolder = async () => {
    if (!folderPath.trim()) {
      alert('Please enter a folder path');
      return;
    }

    try {
      setScanning(true);
      const response = await foldersAPI.scan(folderPath);
      
      alert(`✅ Folder scanned successfully!\n\nPhotos found: ${response.data.total_photos}\nNew photos: ${response.data.new_photos}`);
      
      // Navigate to gallery
      navigate(`/gallery/${response.data.folder_id}`);
    } catch (error) {
      console.error('Error scanning folder:', error);
      alert('❌ Error scanning folder. Please check the path and try again.');
    } finally {
      setScanning(false);
    }
  };

  const handleOpenFolder = (folderId) => {
    navigate(`/gallery/${folderId}`);
  };

  return (
    <div className="home-page">
      <div className="header">
        <h1>📸 Photo Cleaner</h1>
        <div className="header-stats">
          <span>{folders.length} projects</span>
        </div>
      </div>

      <div className="home-content">
        <div className="hero-section">
          <h2>Organize Your Photos Like a Pro</h2>
          <p>Fast, local, and powerful photo management for massive archives</p>
        </div>

        <div className="scan-section card">
          <h3>
            <Folder size={24} />
            Start New Project
          </h3>
          <div className="scan-input-group">
            <input
              type="text"
              className="input"
              placeholder="Enter folder path (e.g., C:\Photos\Vacation2024)"
              value={folderPath}
              onChange={(e) => setFolderPath(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleScanFolder()}
            />
            <button
              className="btn btn-primary"
              onClick={handleScanFolder}
              disabled={scanning}
            >
              {scanning ? (
                <>
                  <Loader className="animate-spin" size={20} />
                  Scanning...
                </>
              ) : (
                'Scan Folder'
              )}
            </button>
          </div>
          <p className="hint">
            💡 The app will create subfolders: thumbs, web, cancellate, preferite
          </p>
        </div>

        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading projects...</p>
          </div>
        ) : folders.length > 0 ? (
          <div className="projects-section">
            <h3>Recent Projects</h3>
            <div className="projects-grid">
              {folders.map((folder) => (
                <div
                  key={folder.id}
                  className="project-card card"
                  onClick={() => handleOpenFolder(folder.id)}
                >
                  <div className="project-header">
                    <Folder size={32} />
                    <h4>{folder.name}</h4>
                  </div>
                  <div className="project-stats">
                    <div className="stat">
                      <Image size={16} />
                      <span>{folder.total_photos} photos</span>
                    </div>
                    <div className="stat">
                      <Star size={16} />
                      <span>{folder.favorites_count || 0} favorites</span>
                    </div>
                    <div className="stat">
                      <Trash2 size={16} />
                      <span>{folder.deleted_count || 0} deleted</span>
                    </div>
                  </div>
                  <div className="project-path">{folder.path}</div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="empty-state card">
            <Folder size={64} opacity={0.3} />
            <h3>No Projects Yet</h3>
            <p>Start by scanning a folder containing your photos</p>
          </div>
        )}

        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon">⚡</div>
            <h4>Lightning Fast</h4>
            <p>Handle 50,000+ photos with smooth navigation</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">🔍</div>
            <h4>Smart Detection</h4>
            <p>Find duplicates and similar photos automatically</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">⭐</div>
            <h4>Non-Destructive</h4>
            <p>Nothing is permanently deleted until you want it</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">🌐</div>
            <h4>Web Optimization</h4>
            <p>Generate lightweight versions for sharing</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Home;
