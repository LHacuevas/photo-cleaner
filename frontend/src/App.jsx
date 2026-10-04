import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import Gallery from './pages/Gallery';
import Compare from './pages/Compare';
import KeyboardShortcuts from './components/KeyboardShortcuts';
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <KeyboardShortcuts />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/gallery/:folderId" element={<Gallery />} />
          <Route path="/compare/:folderId" element={<Compare />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
