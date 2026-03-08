import React from 'react';
import { Trash2, Star, X } from 'lucide-react';
import './BatchActionBar.css';

function BatchActionBar({ selectedIds, total, onFavorite, onDelete, onClear, isLoading }) {
  if (selectedIds.length === 0) {
    return null;
  }

  return (
    <div className="batch-action-bar">
      <div className="batch-info">
        <span className="batch-count">
          {selectedIds.length} selected
        </span>
      </div>

      <div className="batch-actions">
        <button
          className="batch-btn batch-btn-favorite"
          onClick={onFavorite}
          disabled={isLoading}
          title="Add to favorites"
        >
          <Star size={18} />
          <span>Favorite</span>
        </button>

        <button
          className="batch-btn batch-btn-delete"
          onClick={onDelete}
          disabled={isLoading}
          title="Delete selected photos"
        >
          <Trash2 size={18} />
          <span>Delete</span>
        </button>

        <button
          className="batch-btn batch-btn-clear"
          onClick={onClear}
          disabled={isLoading}
          title="Clear selection"
        >
          <X size={18} />
          <span>Clear</span>
        </button>
      </div>

      {isLoading && (
        <div className="batch-loading">
          <div className="spinner"></div>
          <span>Processing...</span>
        </div>
      )}
    </div>
  );
}

export default BatchActionBar;
