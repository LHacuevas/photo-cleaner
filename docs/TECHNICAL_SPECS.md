# Photo Cleaner - Technical Specifications

## 🏗️ Architecture Overview

### Tech Stack

**Backend:**
- **Framework**: FastAPI (Python 3.9+)
- **Database**: SQLite with SQLAlchemy ORM
- **Image Processing**: FFmpeg + Pillow + ImageHash
- **Server**: Uvicorn ASGI server

**Frontend:**
- **Framework**: React 18
- **Routing**: React Router v6
- **HTTP Client**: Axios
- **Icons**: Lucide React
- **Build**: Create React App

**Communication:**
- REST API (JSON)
- CORS enabled for local development
- Proxy setup in package.json

---

## 📊 Database Schema

### Photos Table

```sql
CREATE TABLE photos (
    id INTEGER PRIMARY KEY,
    filename VARCHAR NOT NULL,
    filepath VARCHAR NOT NULL UNIQUE,
    folder_id INTEGER FOREIGN KEY,
    
    -- File Info
    size INTEGER,
    width INTEGER,
    height INTEGER,
    format VARCHAR,
    
    -- Status
    is_favorite BOOLEAN DEFAULT FALSE,
    is_deleted BOOLEAN DEFAULT FALSE,
    
    -- Hashes
    phash VARCHAR,  -- Perceptual hash
    dhash VARCHAR,  -- Difference hash
    
    -- EXIF Metadata
    date_taken DATETIME,
    camera_make VARCHAR,
    camera_model VARCHAR,
    lens_model VARCHAR,
    iso INTEGER,
    aperture FLOAT,
    shutter_speed VARCHAR,
    focal_length FLOAT,
    
    -- GPS
    gps_latitude FLOAT,
    gps_longitude FLOAT,
    gps_altitude FLOAT,
    
    -- Processing Status
    has_thumb BOOLEAN DEFAULT FALSE,
    has_web BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at DATETIME,
    updated_at DATETIME
);
```

### Folders Table

```sql
CREATE TABLE folders (
    id INTEGER PRIMARY KEY,
    path VARCHAR NOT NULL UNIQUE,
    name VARCHAR NOT NULL,
    
    -- Statistics
    total_photos INTEGER DEFAULT 0,
    favorites_count INTEGER DEFAULT 0,
    deleted_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at DATETIME,
    last_scanned DATETIME
);
```

### Similar Groups Table

```sql
CREATE TABLE similar_groups (
    id INTEGER PRIMARY KEY,
    folder_id INTEGER FOREIGN KEY,
    
    similarity_score FLOAT,
    group_type VARCHAR,  -- 'duplicate', 'burst', 'similar'
    
    is_reviewed BOOLEAN DEFAULT FALSE,
    selected_photo_id INTEGER,
    
    created_at DATETIME
);
```

### Photo-Similar Groups Association

```sql
CREATE TABLE photo_similar_groups (
    photo_id INTEGER FOREIGN KEY,
    group_id INTEGER FOREIGN KEY,
    PRIMARY KEY (photo_id, group_id)
);
```

---

## 🔧 Image Processing Pipeline

### 1. Thumbnail Generation

**Command:**
```bash
ffmpeg -i input.jpg -vf scale=300:-1 -q:v 5 thumbs/output.jpg
```

**Parameters:**
- `-vf scale=300:-1`: Scale to 300px width, maintain aspect ratio
- `-q:v 5`: JPEG quality (1-31, lower is better)
- Target size: 10-30 KB

**Performance:** ~50-100 photos/second

### 2. Web Version Generation

**Modes:**

**Web (Default):**
```bash
ffmpeg -i input.jpg -vf scale=2048:-1 -q:v 3 -map_metadata 0 web/output.jpg
```

**Archive:**
```bash
ffmpeg -i input.jpg -vf scale=1600:-1 -q:v 5 -map_metadata 0 web/output.jpg
```

**Ultra:**
```bash
ffmpeg -i input.jpg -vf scale=1200:-1 -q:v 7 -map_metadata 0 web/output.jpg
```

**Parameters:**
- `-map_metadata 0`: Preserve EXIF data
- Quality values: 3 (high), 5 (medium), 7 (lower)

### 3. Perceptual Hashing

**Algorithm:** pHash (Perceptual Hash)

**Process:**
1. Resize image to 32x32
2. Convert to grayscale
3. Compute DCT (Discrete Cosine Transform)
4. Keep low frequency components
5. Generate 64-bit hash

**Properties:**
- Similar images → Similar hashes
- Small changes → Small hash differences
- Rotation/crop resistant

**Comparison:**
- Hamming distance between hashes
- 0-5: Nearly identical
- 6-10: Very similar
- 11-15: Similar
- 16+: Different

---

## 🌐 API Endpoints

### Folders

```
POST   /api/folders/scan          - Scan folder and create structure
GET    /api/folders/stats/{id}    - Get folder statistics
GET    /api/folders/list          - List all folders
```

### Photos

```
GET    /api/photos/list/{folder_id}     - List photos with pagination
GET    /api/photos/get/{photo_id}       - Get photo details
GET    /api/photos/file/{photo_id}      - Serve photo file
POST   /api/photos/favorite/{photo_id}  - Toggle favorite
POST   /api/photos/delete/{photo_id}    - Move to deleted
POST   /api/photos/restore/{photo_id}   - Restore from deleted
POST   /api/photos/generate-thumbs/{folder_id}  - Generate thumbnails
POST   /api/photos/generate-web/{folder_id}     - Generate web versions
```

### Similar Photos

```
POST   /api/similar/analyze/{folder_id}         - Analyze and hash photos
POST   /api/similar/group/{folder_id}           - Group similar photos
GET    /api/similar/groups/{folder_id}          - Get all groups
GET    /api/similar/group/{group_id}            - Get group details
POST   /api/similar/group/{id}/select/{photo}   - Select best photo
POST   /api/similar/group/{id}/skip             - Skip group
```

### Metadata

```
POST   /api/metadata/search             - Search with filters
GET    /api/metadata/cameras/{folder}   - List unique cameras
GET    /api/metadata/date-range/{folder} - Get date range
GET    /api/metadata/stats/{folder}     - Metadata statistics
GET    /api/metadata/by-month/{folder}  - Group by month
GET    /api/metadata/gps-map/{folder}   - GPS locations
```

---

## ⚡ Performance Optimization

### Database

- **Indexes:** On frequently queried fields (phash, filename, is_favorite)
- **Pagination:** Default 100 photos per page
- **Lazy Loading:** Photos loaded on demand

### Frontend

- **Thumbnail Loading:** Load only visible thumbnails
- **Virtualization:** Render only visible items in long lists
- **Prefetch:** Load next photo in background
- **Caching:** Browser cache for thumbnails

### Image Processing

- **Background Tasks:** Long operations run in background
- **Batch Processing:** Process multiple photos at once
- **Parallel Processing:** Use multiple CPU cores (future)

### Expected Performance

| Operation | Time (1000 photos) |
|-----------|-------------------|
| Scan folder | 2-5 seconds |
| Generate thumbnails | 10-20 seconds |
| Compute hashes | 30-60 seconds |
| Generate web versions | 60-120 seconds |
| Group similar photos | 1-3 seconds |

---

## 🔒 Security & Privacy

### Data Storage

- ✅ All data stored locally
- ✅ SQLite database in backend folder
- ✅ No cloud sync
- ✅ No telemetry

### File Operations

- ✅ Read-only access to originals
- ✅ Copies/moves only, never modifies
- ✅ Non-destructive delete
- ✅ Atomic operations

### API Security

- CORS restricted to localhost
- No authentication (local use)
- File path validation
- SQL injection prevention (SQLAlchemy)

---

## 📦 Distribution

### Windows Executable

**Option 1: PyInstaller**
```bash
pyinstaller --onefile --windowed main.py
```

**Option 2: Electron Wrapper**
- Package React app
- Embed Python backend
- Single .exe installer

### Cross-Platform

- **Windows**: .exe installer
- **macOS**: .app bundle
- **Linux**: AppImage or .deb

---

## 🔮 Future Enhancements

### Planned Features

1. **RAW File Support**
   - Read RAW formats (CR2, NEF, ARW)
   - Extract embedded JPEG
   - Preserve RAW originals

2. **Face Detection**
   - Detect faces in photos
   - Group by person
   - Auto-tag portraits

3. **AI Tagging**
   - Auto-tag objects (beach, mountain, food)
   - Scene detection
   - Quality scoring

4. **Advanced Filters**
   - Color palette search
   - Orientation (portrait/landscape)
   - Aspect ratio

5. **Batch Editing**
   - Batch rename
   - Batch rotate
   - EXIF manipulation

6. **Export Options**
   - Create ZIP archives
   - FTP upload
   - Cloud integration (optional)

7. **Performance**
   - GPU acceleration
   - Multi-threading
   - Progressive loading

---

## 🧪 Testing

### Unit Tests

```bash
# Backend tests
cd backend
pytest tests/

# Frontend tests
cd frontend
npm test
```

### Test Coverage

- Image processing functions
- Database operations
- API endpoints
- React components

### Manual Testing Checklist

- [ ] Scan folder with 1000+ photos
- [ ] Generate thumbnails
- [ ] Navigate photos (keyboard)
- [ ] Mark favorites
- [ ] Delete photos
- [ ] Restore photos
- [ ] Detect similar photos
- [ ] Compare mode workflow
- [ ] Search by metadata
- [ ] Generate web versions

---

## 📝 Code Style

### Python

- PEP 8 compliance
- Type hints encouraged
- Docstrings for all functions
- Max line length: 100

### JavaScript/React

- ESLint with react-app config
- Functional components
- Hooks for state management
- CSS modules or styled components

---

## 🤝 Contributing Guidelines

1. Fork repository
2. Create feature branch
3. Write tests
4. Update documentation
5. Submit pull request

**Commit Format:**
```
feat: Add face detection
fix: Thumbnail generation on Windows
docs: Update user guide
refactor: Optimize hash comparison
```

---

## 📄 License

MIT License - see LICENSE file

---

## 🔗 Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [ImageHash Library](https://pypi.org/project/ImageHash/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)

---

**Version:** 1.0.0  
**Last Updated:** 2024  
**Maintainer:** [Your Name]
