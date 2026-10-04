import { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import Gallery from './pages/Gallery';
import Compare from './pages/Compare';
import ErrorBoundary from './components/ErrorBoundary';
import KeyboardShortcuts from './components/KeyboardShortcuts';
import { ToastProvider } from './components/Toast';
import './App.css';

// Leaflet is only downloaded when the map is opened
const MapView = lazy(() => import('./pages/MapView'));

function App() {
  return (
    <Router>
      <ToastProvider>
        <div className="App">
          <KeyboardShortcuts />
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/gallery/:folderId" element={<Gallery />} />
              <Route path="/compare/:folderId" element={<Compare />} />
              <Route
                path="/map/:folderId"
                element={(
                  <Suspense fallback={<div className="gallery-loading"><div className="spinner"></div></div>}>
                    <MapView />
                  </Suspense>
                )}
              />
            </Routes>
          </ErrorBoundary>
        </div>
      </ToastProvider>
    </Router>
  );
}

export default App;
