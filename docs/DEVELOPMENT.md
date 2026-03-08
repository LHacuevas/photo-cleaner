# Photo Cleaner - Development Guide

## 🚀 Quick Start

### Prerequisites

**Required Software:**
- Python 3.9+ ([download](https://www.python.org/downloads/))
- Node.js 16+ ([download](https://nodejs.org/))
- FFmpeg ([download](https://ffmpeg.org/download.html))

**Installing FFmpeg on Windows:**
1. Download FFmpeg from https://www.gyan.dev/ffmpeg/builds/
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to PATH
4. Verify: open CMD and run `ffmpeg -version`

---

## 📦 Installation

### 1. Clone or Download Project

```bash
git clone https://github.com/yourusername/photo-cleaner.git
cd photo-cleaner
```

### 2. Setup Backend

```bash
cd backend

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Setup Frontend

```bash
cd frontend

# Install dependencies
npm install
```

---

## 🏃 Running the Application

### Terminal 1 - Start Backend

```bash
cd backend
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

python main.py
```

Backend will run on: **http://localhost:8000**

You can test it by visiting: http://localhost:8000 in your browser

### Terminal 2 - Start Frontend

```bash
cd frontend

npm start
```

Frontend will automatically open in your browser at: **http://localhost:3000**

---

## 🗂️ Project Structure

```
photo-cleaner/
│
├── backend/                 # Python FastAPI backend
│   ├── api/                # API routes
│   │   ├── folders.py     # Folder scanning & management
│   │   ├── photos.py      # Photo operations (favorite, delete, etc.)
│   │   ├── similar.py     # Duplicate/similar detection
│   │   └── metadata.py    # EXIF search & filtering
│   │
│   ├── utils/             # Utilities
│   │   └── image_processing.py  # FFmpeg & image hashing
│   │
│   ├── database.py        # SQLAlchemy models
│   ├── main.py           # FastAPI app entry point
│   └── requirements.txt  # Python dependencies
│
├── frontend/              # React frontend
│   ├── public/
│   │   └── index.html
│   │
│   ├── src/
│   │   ├── components/   # Reusable components
│   │   ├── pages/        # Page components
│   │   │   ├── Home.js
│   │   │   ├── Gallery.js
│   │   │   └── Compare.js
│   │   │
│   │   ├── services/
│   │   │   └── api.js    # API client
│   │   │
│   │   ├── App.js        # Main app component
│   │   ├── App.css
│   │   ├── index.js
│   │   └── index.css
│   │
│   └── package.json      # Node dependencies
│
└── docs/                 # Documentation
```

---

## 🛠️ Development Workflow

### Adding New Features

1. **Backend API Endpoint:**
   - Add route in appropriate file in `backend/api/`
   - Use SQLAlchemy for database operations
   - Follow existing patterns

2. **Frontend Integration:**
   - Add API call to `frontend/src/services/api.js`
   - Create/update React components
   - Use hooks for state management

### Database Changes

The database is SQLite and located at `backend/photo_cleaner.db`

To reset the database:
```bash
cd backend
rm photo_cleaner.db
python main.py  # Will recreate tables
```

### Testing API Endpoints

Use tools like:
- **Browser**: http://localhost:8000/docs (FastAPI Swagger UI)
- **Postman**: Import endpoints from Swagger
- **cURL**: Command-line testing

Example:
```bash
curl http://localhost:8000/api/health
```

---

## 🐛 Common Issues & Solutions

### Issue: FFmpeg not found

**Solution:**
- Install FFmpeg and add to PATH
- Restart terminal after installation
- Verify with `ffmpeg -version`

### Issue: Port 8000 already in use

**Solution:**
```bash
# Change port in backend/main.py
uvicorn.run("main:app", port=8001)  # Use different port
```

### Issue: CORS errors in browser

**Solution:**
- Check backend is running on http://localhost:8000
- Verify CORS settings in `backend/main.py`
- Frontend proxy is set in `frontend/package.json`

### Issue: Module not found errors

**Solution Backend:**
```bash
cd backend
pip install -r requirements.txt
```

**Solution Frontend:**
```bash
cd frontend
rm -rf node_modules
npm install
```

---

## 📊 Database Schema

### Tables

**photos**
- Stores photo metadata, EXIF, hashes
- Tracks favorites, deleted status
- Links to folder

**folders**
- Project/folder information
- Statistics (photo counts)

**similar_groups**
- Groups of similar/duplicate photos
- Similarity scores and types

**photo_similar_groups**
- Many-to-many relationship table

---

## 🔧 Configuration

### Environment Variables

Create `.env` file in backend directory:

```env
# Database
DATABASE_URL=sqlite:///./photo_cleaner.db

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:3001

# Image Processing
THUMB_SIZE=300
WEB_SIZE=2048
```

### Frontend Config

Create `.env` file in frontend directory:

```env
REACT_APP_API_URL=http://localhost:8000/api
```

---

## 🚢 Production Deployment

### Backend

1. Install production dependencies:
```bash
pip install gunicorn
```

2. Run with Gunicorn:
```bash
gunicorn main:app --bind 0.0.0.0:8000 --workers 4
```

### Frontend

1. Build production version:
```bash
npm run build
```

2. Serve the `build` folder with any static file server

---

## 📝 API Documentation

Once backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

---

## 📄 License

MIT License - see LICENSE file for details

---

## 🆘 Getting Help

- Open an issue on GitHub
- Check existing issues for solutions
- Read the API documentation
