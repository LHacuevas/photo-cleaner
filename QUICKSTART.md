# ⚡ Photo Cleaner - Quick Start

## 🚀 5-Minute Setup (Windows)

### Step 1: Install Prerequisites (One-Time)

1. **Python 3.9+** → [Download](https://www.python.org/downloads/)
   - During installation, check "Add Python to PATH"

2. **Node.js 16+** → [Download](https://nodejs.org/)
   - Download LTS version
   - Default installation is fine

3. **FFmpeg** → [Download](https://www.gyan.dev/ffmpeg/builds/)
   - Download "ffmpeg-release-essentials.zip"
   - Extract to `C:\ffmpeg`
   - Add `C:\ffmpeg\bin` to PATH:
     - Search "Environment Variables" in Windows
     - Edit "Path" under System Variables
     - Click "New" → Add `C:\ffmpeg\bin`

### Step 2: Run Photo Cleaner

**Double-click:** `start.bat`

That's it! The app will:
- Install dependencies automatically (first time only)
- Start backend server
- Start frontend server
- Open in your browser

---

## 🎮 First Use

1. **Open** http://localhost:3000 (opens automatically)

2. **Enter folder path**
   ```
   Example: C:\Users\YourName\Pictures\Vacation2024
   ```

3. **Click "Scan Folder"**

4. **Click "Generate Thumbnails"**

5. **Start organizing!**
   - Press → and ← to navigate
   - Press F to favorite
   - Press D to delete
   - Press Space for compare mode

---

## 📂 Your Folder Structure After Scan

```
YourFolder/
├── IMG_001.jpg         ← Originals (untouched)
├── IMG_002.jpg
│
├── thumbs/            ← Auto-created
├── web/               ← Auto-created
├── cancellate/        ← Auto-created
└── preferite/         ← Auto-created
```

---

## 🔑 Keyboard Shortcuts

### Navigation
- `→` Next photo
- `←` Previous photo
- `Home` First photo
- `End` Last photo

### Actions
- `F` Toggle favorite
- `D` Delete (non-destructive)
- `Space` Compare mode
- `Esc` Exit compare mode

### Compare Mode
- `1` `2` `3` `4` Select best photo
- `D` Delete others
- `S` Skip group

---

## ❓ Quick Troubleshooting

### "FFmpeg not found"
→ Install FFmpeg and add to PATH (see Step 1.3 above)

### "Python not found"
→ Install Python and check "Add to PATH" (see Step 1.1 above)

### Port already in use
→ Close other applications using ports 8000 or 3000

### Thumbnails not generating
→ Check FFmpeg: open CMD and type `ffmpeg -version`

---

## 📚 Learn More

- **User Guide:** `docs/USER_GUIDE.md` - Complete workflow
- **Development:** `docs/DEVELOPMENT.md` - Technical details
- **API Docs:** http://localhost:8000/docs (when running)

---

## 🆘 Need Help?

- Check `docs/USER_GUIDE.md` for detailed instructions
- Open an issue on GitHub
- Read FAQ in User Guide

---

## ⚡ Power User Tips

1. **Generate thumbnails first** - Makes everything 10× faster
2. **Use compare mode** - Clean photo bursts in seconds
3. **Keyboard shortcuts** - Much faster than clicking
4. **Search by date** - Find specific photo sets quickly
5. **Backup your database** - `backend/photo_cleaner.db`

---

**Happy organizing! 📸✨**
