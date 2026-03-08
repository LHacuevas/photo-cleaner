# Photo Cleaner - User Guide

## 📖 Complete Workflow

This guide walks you through the complete process of organizing your photos with Photo Cleaner.

---

## 🎯 Step 1: Prepare Your Photos

Before starting, organize your photos in a folder:

```
MyVacation2024/
├── IMG_001.jpg
├── IMG_002.jpg
├── IMG_003.jpg
├── ...
```

**Important Notes:**
- Keep all photos in one folder (not in subfolders)
- Supported formats: JPG, JPEG, PNG, GIF, BMP, TIFF, WEBP
- No size limit - the app can handle 50,000+ photos

---

## 🚀 Step 2: Scan Your Folder

1. Open Photo Cleaner
2. Enter your folder path (e.g., `C:\Photos\MyVacation2024`)
3. Click "Scan Folder"

**What happens:**
- App creates 4 subfolders automatically:
  - `thumbs/` - Miniatures (300px)
  - `web/` - Web versions (2048px)
  - `cancellate/` - Deleted photos (recoverable)
  - `preferite/` - Favorite photos
- All original photos remain untouched
- Photo metadata is indexed in database

**Result:**
```
MyVacation2024/
├── IMG_001.jpg        ← Originals (unchanged)
├── IMG_002.jpg
├── thumbs/            ← Created automatically
├── web/               ← Created automatically
├── cancellate/        ← Created automatically
└── preferite/         ← Created automatically
```

---

## 🖼️ Step 3: Generate Thumbnails

**Why:** Thumbnails allow super-fast navigation through thousands of photos

1. Click "Generate Thumbnails" button
2. Wait for processing (shows progress)
3. Takes ~1-2 seconds per 100 photos

**Technical Details:**
- Size: 300px on longest side
- Weight: 10-30 KB each
- Quality: Optimized JPEG
- Total size: ~1% of original photos

**Example:**
- 10,000 photos (25 GB) → Thumbnails: 250 MB

---

## 🔍 Step 4: Detect Similar Photos (Optional but Recommended)

**Why:** Automatically find duplicates and photo bursts to clean 10× faster

### 4A. Analyze Photos

1. Click "Analyze Similar Photos"
2. App computes perceptual hashes (background task)
3. Takes ~30 seconds per 1000 photos

**What it does:**
- Computes unique "fingerprint" for each photo
- Also extracts ALL EXIF metadata
- Stores in database for fast comparison

### 4B. Group Similar Photos

1. Click "Group Similar Photos"
2. Choose threshold:
   - **0-5**: Nearly identical (duplicates/burst shots) ⭐ Recommended
   - **6-10**: Very similar
   - **11-15**: Similar scenes

3. App groups photos automatically

**Example Result:**
```
Group 1 (Burst): 5 photos
├── IMG_101.jpg
├── IMG_102.jpg
├── IMG_103.jpg
├── IMG_104.jpg
└── IMG_105.jpg

Group 2 (Duplicate): 2 photos
├── IMG_201.jpg
└── IMG_201_copy.jpg
```

---

## 🎮 Step 5: Navigate and Clean Photos

### Normal View

**Keyboard Shortcuts:**
- `→` - Next photo
- `←` - Previous photo
- `F` - Add to favorites ⭐
- `D` - Delete (move to cancellate)
- `Space` - Switch to Compare Mode

**What you see:**
- Large photo preview
- Strip of thumbnails below
- Photo info sidebar (EXIF data)

### Compare Mode (For Similar Photos)

**Purpose:** Quickly choose the best photo from a burst or similar group

**Layout:**
```
┌─────────┬─────────┬─────────┬─────────┐
│ Photo 1 │ Photo 2 │ Photo 3 │ Photo 4 │
└─────────┴─────────┴─────────┴─────────┘
```

**Keyboard Shortcuts:**
- `1`, `2`, `3`, `4` - Select best photo
- `D` - Delete others (non-destructive)
- `S` - Skip this group
- `Esc` - Back to normal view

**Workflow:**
1. App shows group of similar photos
2. You press `2` (Photo 2 is best)
3. Press `D` to delete others
4. Photos 1, 3, 4 move to `cancellate/`
5. Photo 2 stays as original
6. Next group appears automatically

**Speed:** You can clean 100+ photo groups in 5-10 minutes!

---

## ⭐ Step 6: Mark Favorites

**Purpose:** Identify your best photos

1. View photo in normal mode
2. Press `F` to favorite
3. Photo is **copied** to `preferite/` folder

**Important:** 
- Original stays in main folder
- You get a copy in `preferite/`
- Easy to share or create albums later

---

## 🗑️ Step 7: Delete Unwanted Photos

**Non-Destructive Deletion:**

1. Press `D` on any photo
2. Photo **moves** to `cancellate/` folder
3. Original is NOT deleted from disk
4. You can restore it later!

**Why this is safe:**
- Nothing is permanently deleted
- You can review `cancellate/` folder later
- Restore any photo with one click
- Only delete permanently when YOU decide

---

## 🌐 Step 8: Generate Web Versions

**Purpose:** Create lightweight versions for sharing, backup, or web use

### Choose Mode:

**Web (Recommended)** ⭐
- Size: 2048px
- Quality: High
- Weight: 500-900 KB
- Use: Instagram, Facebook, email, portfolios

**Archive**
- Size: 1600px
- Quality: Medium
- Weight: 300-600 KB
- Use: Cloud backup, archiving

**Ultra Light**
- Size: 1200px
- Quality: Medium-low
- Weight: 150-400 KB
- Use: Web galleries, quick sharing

### Process:

1. Click "Generate Web Versions"
2. Select mode
3. Wait for processing
4. All photos converted to `web/` folder

**Result:**
```
Original Archive: 25 GB
Web Archive:      ~3 GB (88% smaller!)
```

**Metadata:** 
All EXIF data is preserved (date, GPS, camera info)

---

## 🔎 Step 9: Search and Filter (Advanced)

### Search by Date

- Filter by date range
- View by month/year
- Timeline view

### Search by Camera

- Filter by camera model
- Group by camera
- Compare cameras

### Search by Settings

- ISO range
- Aperture range
- Focal length
- Shutter speed

### GPS Filters

- Photos with GPS
- Photos without GPS
- Map view of locations

---

## 📊 Final Result

After completing all steps:

```
MyVacation2024/
│
├── IMG_001.jpg              ← Originals (kept)
├── IMG_002.jpg
├── IMG_005.jpg
├── ...
│
├── thumbs/                  ← Fast navigation
│   ├── IMG_001.jpg (30 KB)
│   ├── IMG_002.jpg (25 KB)
│   └── ...
│
├── web/                     ← Sharing versions
│   ├── IMG_001.jpg (650 KB)
│   ├── IMG_002.jpg (720 KB)
│   └── ...
│
├── preferite/               ← Your best shots
│   ├── IMG_042.jpg
│   ├── IMG_089.jpg
│   └── ...
│
└── cancellate/              ← Deleted (recoverable)
    ├── IMG_003.jpg (blurry)
    ├── IMG_004.jpg (duplicate)
    └── ...
```

**Storage:**
- Originals: 25 GB
- Thumbnails: 250 MB
- Web versions: 3 GB
- **Total: 28.25 GB (vs 25 GB single copy)**

**Benefits:**
- ✅ Originals safe and untouched
- ✅ Fast browsing with thumbnails
- ✅ Lightweight sharing versions
- ✅ Best photos in one place
- ✅ Deleted photos recoverable
- ✅ Everything local and private

---

## 💡 Pro Tips

### 🚀 Speed Tips

1. **Generate thumbnails first** - Makes everything faster
2. **Use Compare Mode** - 10× faster than one-by-one
3. **Batch operations** - Select multiple favorites at once
4. **Keyboard shortcuts** - Much faster than mouse

### 🎯 Organization Tips

1. **Date-based folders** - Organize by year/month
2. **Event-based** - Separate by trips/events
3. **Tag favorites immediately** - Don't wait
4. **Review deleted weekly** - Permanently delete after review

### 💾 Backup Tips

1. **Keep originals** - Never delete originals
2. **Backup web versions** - Easy to cloud backup (smaller)
3. **Export favorites** - Copy `preferite/` to USB/cloud
4. **Database backup** - Backup `photo_cleaner.db` file

---

## ❓ FAQ

**Q: Will this modify my original photos?**
A: NO! Originals are never modified. Only read for processing.

**Q: What if I delete something by mistake?**
A: No problem! It's in `cancellate/` folder. Restore with one click.

**Q: Can I process RAW files?**
A: Currently JPG/PNG only. RAW support coming soon.

**Q: How many photos can it handle?**
A: Tested up to 50,000 photos. Should work with more.

**Q: Is my data sent online?**
A: NO! Everything is 100% local. Zero cloud, zero tracking.

**Q: Can I use this on multiple computers?**
A: Yes! Just copy the folder and database file.

---

## 🆘 Troubleshooting

### Thumbnails not generating
- Check FFmpeg is installed
- Check disk space
- Check read permissions on photos

### Slow performance
- Generate thumbnails first
- Close other heavy applications
- Use SSD if possible

### Photos not showing
- Check file formats (JPG, PNG supported)
- Check photos not in subfolders
- Rescan folder

---

## 📞 Support

- GitHub Issues: [github.com/yourname/photo-cleaner/issues]
- Documentation: Read DEVELOPMENT.md for technical details
- Community: [Discord/Forum link]

---

**Happy Photo Organizing! 📸✨**
