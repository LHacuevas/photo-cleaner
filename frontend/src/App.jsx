import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import Gallery from './pages/Gallery';
import Compare from './pages/Compare';
import ErrorBoundary from './components/ErrorBoundary';
import KeyboardShortcuts from './components/KeyboardShortcuts';
import { ToastProvider } from './components/Toast';
import './App.css';

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
            </Routes>
          </ErrorBoundary>
        </div>
      </ToastProvider>
    </Router>
  );
}

export default App;
