import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import './KeyboardShortcuts.css';

function KeyboardShortcuts() {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const handleKeyPress = (e) => {
      // Open on '?' ('h' is the gallery's flip shortcut)
      if (e.key === '?' && !isOpen) {
        e.preventDefault();
        setIsOpen(true);
      }
      // Close on Escape
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="keyboard-shortcuts-overlay" onClick={() => setIsOpen(false)}>
      <div className="keyboard-shortcuts-modal" onClick={(e) => e.stopPropagation()}>
        <div className="shortcuts-header">
          <h2>⌨️ Keyboard Shortcuts</h2>
          <button className="close-btn" onClick={() => setIsOpen(false)}>
            <X size={24} />
          </button>
        </div>

        <div className="shortcuts-content">
          <div className="shortcuts-section">
            <h3>Gallery Navigation</h3>
            <div className="shortcuts-list">
              <div className="shortcut-item">
                <kbd>←</kbd>
                <span>Previous photo</span>
              </div>
              <div className="shortcut-item">
                <kbd>→</kbd>
                <span>Next photo</span>
              </div>
              <div className="shortcut-item">
                <kbd>F</kbd>
                <span>Toggle favorite</span>
              </div>
              <div className="shortcut-item">
                <kbd>D</kbd>
                <span>Delete photo (also Del)</span>
              </div>
              <div className="shortcut-item">
                <kbd>R</kbd>
                <span>Rotate 90° clockwise</span>
              </div>
              <div className="shortcut-item">
                <kbd>H</kbd>
                <span>Flip horizontally</span>
              </div>
              <div className="shortcut-item">
                <kbd>V</kbd>
                <span>Switch original / web version</span>
              </div>
              <div className="shortcut-item">
                <kbd>Ctrl+Click</kbd>
                <span>Select thumbnails for batch actions</span>
              </div>
            </div>
          </div>

          <div className="shortcuts-section">
            <h3>Compare Mode</h3>
            <div className="shortcuts-list">
              <div className="shortcut-item">
                <kbd>1-9</kbd>
                <span>Select photo by number</span>
              </div>
              <div className="shortcut-item">
                <kbd>S</kbd>
                <span>Skip to next group</span>
              </div>
              <div className="shortcut-item">
                <kbd>←</kbd>
                <span>Previous group</span>
              </div>
              <div className="shortcut-item">
                <kbd>→</kbd>
                <span>Next group</span>
              </div>
            </div>
          </div>

          <div className="shortcuts-section">
            <h3>General</h3>
            <div className="shortcuts-list">
              <div className="shortcut-item">
                <kbd>?</kbd>
                <span>Show this help</span>
              </div>
              <div className="shortcut-item">
                <kbd>Esc</kbd>
                <span>Close help</span>
              </div>
            </div>
          </div>
        </div>

        <div className="shortcuts-footer">
          <p>Press <kbd>?</kbd> anytime to show this help</p>
        </div>
      </div>
    </div>
  );
}

export default KeyboardShortcuts;
