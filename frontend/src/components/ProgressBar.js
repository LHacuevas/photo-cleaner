import React from 'react';
import './ProgressBar.css';

function ProgressBar({ current, total }) {
  const percentage = (current / total) * 100;
  
  return (
    <div className="progress-bar-container">
      <div className="progress-bar-track">
        <div 
          className="progress-bar-fill"
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
      <div className="progress-text">
        {current} / {total}
      </div>
    </div>
  );
}

export default ProgressBar;
