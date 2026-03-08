import React from 'react';
import './EXIFPanel.css';

function EXIFPanel({ photo }) {
  if (!photo || !photo.metadata) {
    return (
      <div className="exif-panel">
        <h3>Photo Details</h3>
        <p className="no-data">No metadata available</p>
      </div>
    );
  }

  const metadata = photo.metadata;
  
  return (
    <div className="exif-panel">
      <h3>📋 Photo Details</h3>
      
      <div className="exif-section">
        <h4>File Info</h4>
        <div className="exif-row">
          <span className="label">Name:</span>
          <span className="value">{photo.filename}</span>
        </div>
        <div className="exif-row">
          <span className="label">Size:</span>
          <span className="value">{formatFileSize(photo.file_size)}</span>
        </div>
        <div className="exif-row">
          <span className="label">Created:</span>
          <span className="value">{new Date(photo.created_at).toLocaleDateString()}</span>
        </div>
      </div>

      {metadata.width && metadata.height && (
        <div className="exif-section">
          <h4>Image</h4>
          <div className="exif-row">
            <span className="label">Resolution:</span>
            <span className="value">{metadata.width} × {metadata.height}</span>
          </div>
          {metadata.color_space && (
            <div className="exif-row">
              <span className="label">Color Space:</span>
              <span className="value">{metadata.color_space}</span>
            </div>
          )}
        </div>
      )}

      {metadata.camera_model && (
        <div className="exif-section">
          <h4>Camera</h4>
          <div className="exif-row">
            <span className="label">Model:</span>
            <span className="value">{metadata.camera_model}</span>
          </div>
          {metadata.lens_model && (
            <div className="exif-row">
              <span className="label">Lens:</span>
              <span className="value">{metadata.lens_model}</span>
            </div>
          )}
        </div>
      )}

      {(metadata.focal_length || metadata.aperture || metadata.iso || metadata.shutter_speed) && (
        <div className="exif-section">
          <h4>Exposure</h4>
          {metadata.focal_length && (
            <div className="exif-row">
              <span className="label">Focal Length:</span>
              <span className="value">{metadata.focal_length}</span>
            </div>
          )}
          {metadata.aperture && (
            <div className="exif-row">
              <span className="label">Aperture:</span>
              <span className="value">f/{metadata.aperture}</span>
            </div>
          )}
          {metadata.shutter_speed && (
            <div className="exif-row">
              <span className="label">Shutter:</span>
              <span className="value">{metadata.shutter_speed}</span>
            </div>
          )}
          {metadata.iso && (
            <div className="exif-row">
              <span className="label">ISO:</span>
              <span className="value">{metadata.iso}</span>
            </div>
          )}
        </div>
      )}

      {metadata.taken_at && (
        <div className="exif-section">
          <h4>Taken</h4>
          <div className="exif-row">
            <span className="label">Date:</span>
            <span className="value">{new Date(metadata.taken_at).toLocaleString()}</span>
          </div>
        </div>
      )}

      {metadata.gps_latitude && metadata.gps_longitude && (
        <div className="exif-section">
          <h4>Location</h4>
          <div className="exif-row">
            <span className="label">GPS:</span>
            <span className="value">{metadata.gps_latitude.toFixed(4)}, {metadata.gps_longitude.toFixed(4)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function formatFileSize(bytes) {
  if (!bytes) return 'N/A';
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${sizes[i]}`;
}

export default EXIFPanel;
