# Photo Cleaner - TODO & Roadmap

## ✅ Completed (v1.0)

- [x] Backend API structure (FastAPI)
- [x] Database schema (SQLite + SQLAlchemy)
- [x] Image processing utilities (FFmpeg + Pillow)
- [x] Perceptual hashing for duplicate detection
- [x] EXIF metadata extraction
- [x] Thumbnail generation
- [x] Web version generation (3 modes)
- [x] Frontend structure (React)
- [x] Home page with folder selection
- [x] API client service
- [x] Complete documentation
- [x] Quick start script (Windows)

---

## ✅ Completed (v1.1 & v1.2) - FULL FEATURE SET

### Frontend - Critical Pages ✨ FULLY IMPLEMENTED

- [x] **Gallery Page** - Complete with all features
  - [x] Photo grid with multiple thumbnail strip
  - [x] Large photo viewer with drag-enabled navigation
  - [x] Thumbnail strip at bottom with active indicator
  - [x] Keyboard navigation (← → for photos, F for favorite, D for delete, I for info panel)
  - [x] EXIF sidebar with detailed metadata display
  - [x] Favorite/delete buttons with visual feedback
  - [x] Progress indicator showing current position
  - [x] Generate thumbnails button
  - [x] "Find Duplicates" button linking to Compare mode

- [x] **Compare Mode Page** - Complete with all features
  - [x] Responsive grid layout with photo cards (2-4 columns)
  - [x] Similar photo groups display with automatic analysis
  - [x] Selection interface (1-4 number keys to select photos)
  - [x] Delete selected functionality with confirmation
  - [x] Delete others functionality (keep selected, delete rest)
  - [x] Skip group button (S key or button)
  - [x] Navigation between groups (← → arrow keys)
  - [x] Preview thumbnails in cards with filenames
  - [x] Progress indicator for group progress

### Components Created ✨

- [x] **EXIFPanel.js** - Displays complete photo metadata (21 metadata fields)
- [x] **ProgressBar.js** - Visual progress indicator with count
- [x] **EXIFPanel.css** - Professional styling with scroll support
- [x] **ProgressBar.css** - Gradient styling with animations

### Backend Improvements ✨ IMPLEMENTED

- [x] **FFmpeg Installation** - Automatically installed via winget
- [x] **Metadata Extraction** - EXIF data extracted during folder scan
- [x] **Hash Computation** - Perceptual hashes calculated for duplicate detection
- [x] **Image Info** - Dimensions, format, size extracted automatically
- [x] **Web Version Generation** - Buttons added for web, archive, ultra modes
- [x] **Progress Reporting** - Real-time counters for long operations (FFmpeg, batch jobs)

### Development Setup ✨

- [x] **Git Ignore** - Complete .gitignore with cache/installation folders
- [x] **FFmpeg Integration** - Required for thumbnail/web version generation
- [x] **Metadata Processing** - Automatic EXIF extraction on scan
- [x] **Duplicate Detection** - Hash-based similarity analysis ready

### Features Implemented Above Requirements

- [x] Integrated keyboard shortcuts throughout interface
- [x] Visual feedback for selections (cards highlight on select)
- [x] Smooth animations and transitions
- [x] Responsive design for different screen sizes
- [x] Dark theme with professional color scheme
- [x] Click-to-select and checkbox support
- [x] Batch operations support

---

## ✅ Completed (v1.2) - BACKEND & OPTIMIZATION

### Backend Infrastructure ✨ FULLY IMPLEMENTED

- [x] **Error Handling** - Global exception handler + validation middleware
- [x] **Pagination Optimization** - QueryOptimizer utility for efficient queries
- [x] **Caching Layer** - In-memory cache with TTL support (metadata, stats)
- [x] **Background Task Queue** - Async task processor with queue management
- [x] **Progress Reporting** - Real-time counters for all long operations
- [x] **Batch Operations** - Single endpoint for multi-photo operations
- [x] **Async Endpoints** - Non-blocking operations for FFmpeg/processing
  - `POST /generate-thumbs-async`
  - `POST /generate-web-async`
  - `GET /tasks/{task_id}`

### Frontend Components & Hooks ✨ FULLY CREATED

- [x] **LoadingSpinner** - Animated spinner component (3 sizes)
- [x] **KeyboardShortcuts** - Interactive help overlay (? or H key)
- [x] **useBackgroundTask** - Custom hook for task monitoring

### Frontend Hooks ✨ CREATED

- [x] useBackgroundTask hook (Monitor background tasks)

---

## 🚧 In Progress (v1.3+)

### Components & Hooks

- [x] EXIFPanel component ✨ CREATED
- [x] ProgressBar component ✨ CREATED
- [x] LoadingSpinner component ✨ CREATED
- [x] KeyboardShortcuts help overlay ✨ CREATED
- [x] useBackgroundTask hook ✨ CREATED
- [ ] TaskMonitorPanel component (Display running tasks)
- [ ] PhotoGrid component
- [ ] PhotoViewer component (Extract from Gallery)
- [ ] ThumbnailStrip component (Extract from Gallery)
- [ ] CompareView component (Extract from Compare)

### Backend Improvements ✨ ALL COMPLETED

- [x] Progress reporting for long operations
- [x] Batch operations endpoint
- [x] Error handling improvements (Global middleware + validation)
- [x] Pagination optimization (QueryOptimizer utility)
- [x] Caching layer (In-memory cache with TTL)
- [x] Background task queue (Async task processing)
- [x] Async endpoints for long operations (thumbnails, web versions)

---

## 📋 Backlog (v1.3+)

### Features

**Photo Management:**
- [ ] Batch favorite/delete
- [ ] Photo rotation
- [ ] EXIF editing
- [ ] Batch rename
- [ ] Drag & drop sorting
- [ ] Collections/albums

**Search & Filters:**
- [ ] Advanced search UI
- [ ] Saved searches
- [ ] Smart collections
- [ ] Color search
- [ ] Duplicate finder UI improvements

**Visualization:**
- [ ] Timeline view
- [ ] Calendar view
- [ ] Map view (GPS photos)
- [ ] Statistics dashboard
- [ ] Photo quality analysis

**Export & Sharing:**
- [ ] Create ZIP archives
- [ ] Slideshow mode
- [ ] Email sharing
- [ ] Export to specific formats
- [ ] Watermarking

### Technical Improvements

**Performance:**
- [ ] Multi-threading for image processing
- [ ] GPU acceleration (optional)
- [ ] Progressive image loading
- [ ] Virtual scrolling for large lists
- [ ] Service worker for offline support

**Database:**
- [ ] Database migrations system
- [ ] Backup/restore functionality
- [ ] Import/export database
- [ ] Database optimization tools

**Testing:**
- [ ] Unit tests (backend)
- [ ] Integration tests
- [ ] E2E tests (frontend)
- [ ] Performance benchmarks

**Distribution:**
- [ ] Electron wrapper
- [ ] Windows installer
- [ ] macOS app bundle
- [ ] Linux AppImage
- [ ] Auto-update system

---

## 🔮 Future Ideas (v2.0+)

### AI & Machine Learning

- [ ] **Face Detection**
  - Detect faces in photos
  - Group photos by person
  - Auto-tag portraits
  - Face recognition (optional)

- [ ] **Object Recognition**
  - Auto-tag objects (beach, mountain, food, etc.)
  - Scene detection
  - Activity recognition

- [ ] **Quality Scoring**
  - Auto-detect blurry photos
  - Exposure analysis
  - Composition scoring
  - Suggest best photo in burst

- [ ] **Smart Sorting**
  - AI-powered photo selection
  - Auto-create "best of" collections
  - Suggest photos to delete

### Advanced Features

- [ ] **RAW File Support**
  - Read RAW formats (CR2, NEF, ARW)
  - Extract embedded JPEG
  - RAW preview
  - RAW conversion

- [ ] **Video Support**
  - Video thumbnails
  - Video playback
  - Extract frames
  - Video metadata

- [ ] **Plugins System**
  - Plugin API
  - Community plugins
  - Custom processors

- [ ] **Cloud Integration** (Optional)
  - Google Photos sync
  - Dropbox backup
  - iCloud integration
  - Amazon Photos

### UI/UX Enhancements

- [ ] Dark/light theme toggle
- [ ] Customizable keyboard shortcuts
- [ ] Multi-language support
- [ ] Accessibility improvements
- [ ] Mobile/tablet support
- [ ] Touch gestures
- [ ] Customizable layouts

---

## 🐛 Known Issues

### High Priority
- [ ] None yet (initial release)

### Medium Priority
- [ ] Add error boundary in React
- [ ] Improve error messages
- [ ] Add loading states everywhere

### Low Priority
- [ ] Code refactoring opportunities
- [ ] Optimize bundle size
- [ ] Add more comments

---

## 💡 Community Requests

*Add user-requested features here*

---

## 🎯 Development Milestones

### Milestone 1: MVP Complete ✅
- Core functionality working
- Basic UI
- Documentation

### Milestone 2: Full UI (Target: 2 weeks)
- Gallery page complete
- Compare mode complete
- All features accessible via UI

### Milestone 3: Polish (Target: 1 month)
- Bug fixes
- Performance optimization
- User testing feedback

### Milestone 4: Distribution (Target: 2 months)
- Standalone executables
- Installers
- Auto-update

---

## 🤝 Contributing

Want to help? Pick an item from the TODO list!

**Easy tasks** (good for beginners):
- Add loading spinners
- Improve error messages
- Write tests
- Update documentation

**Medium tasks:**
- Implement Gallery page
- Add search UI
- Create new components

**Hard tasks:**
- Video support
- Face detection
- Performance optimization

---

## 📝 Notes

- Keep documentation updated
- Follow existing code style
- Write tests for new features
- Update CHANGELOG.md

---

**Last Updated:** 2024-03-08
