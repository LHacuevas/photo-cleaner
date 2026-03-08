import React from 'react';
import { Loader } from 'lucide-react';
import './LoadingSpinner.css';

function LoadingSpinner({ message = 'Loading...', size = 'medium' }) {
  return (
    <div className={`loading-spinner loading-spinner-${size}`}>
      <Loader className="spinner-icon" />
      {message && <p className="spinner-message">{message}</p>}
    </div>
  );
}

export default LoadingSpinner;
