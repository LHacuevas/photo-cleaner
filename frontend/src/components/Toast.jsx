import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { X } from 'lucide-react';
import './Toast.css';

const ToastContext = createContext(null);

const DURATION_MS = { info: 4000, success: 4000, error: 7000 };

// Non-blocking notifications (replace window.alert). Use via `const toast = useToast()`.
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const nextIdRef = useRef(0);

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback((message, type) => {
    const id = ++nextIdRef.current;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => dismiss(id), DURATION_MS[type]);
  }, [dismiss]);

  const toast = useMemo(() => ({
    info: (message) => show(message, 'info'),
    success: (message) => show(message, 'success'),
    error: (message) => show(message, 'error'),
  }), [show]);

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="toast-container" aria-live="polite">
        {toasts.map(({ id, message, type }) => (
          <div key={id} className={`toast toast-${type}`} role={type === 'error' ? 'alert' : 'status'}>
            <span className="toast-message">{message}</span>
            <button className="toast-close" onClick={() => dismiss(id)} title="Dismiss">
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
