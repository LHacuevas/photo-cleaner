"""
Folders API - Scan folders, create structure, get folder stats
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pathlib import Path
from typing import List
import logging

from database import get_db, Folder, Photo
from utils.image_processing import ImageProcessor
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class FolderCreate(BaseModel):
    path: str


class FolderStats(BaseModel):
    id: int
    name: str
    path: str
    total_photos: int
    favorites_count: int
    deleted_count: int
    has_thumbs: bool
    has_web: bool


@router.post("/scan")
async def scan_folder(folder: FolderCreate, db: Session = Depends(get_db)):
    """
    Scan a folder and create necessary subfolders
    Returns folder ID and initial stats
    """
    try:
        folder_path = Path(folder.path)
        
        # Check if folder exists
        if not folder_path.exists() or not folder_path.is_dir():
            raise HTTPException(status_code=400, detail="Folder does not exist")
        
        # Create subfolders
        subfolders = ['thumbs', 'web', 'cancellate', 'preferite']
        for subfolder in subfolders:
            (folder_path / subfolder).mkdir(exist_ok=True)
        
        logger.info(f"Created subfolders in {folder_path}")
        
        # Check if folder already in database
        existing_folder = db.query(Folder).filter(Folder.path == str(folder_path)).first()
        
        if existing_folder:
            folder_obj = existing_folder
        else:
            # Create folder in database
            folder_obj = Folder(
                path=str(folder_path),
                name=folder_path.name
            )
            db.add(folder_obj)
            db.commit()
            db.refresh(folder_obj)
        
        # Scan for images
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        image_files = []
        
        for ext in image_extensions:
            image_files.extend(folder_path.glob(f"*{ext}"))
            image_files.extend(folder_path.glob(f"*{ext.upper()}"))
        
        # Add photos to database if not already there
        new_photos = 0
        for img_file in image_files:
            # Skip if in subfolders
            if any(sub in img_file.parts for sub in subfolders):
                continue
            
            # Check if already in DB
            existing_photo = db.query(Photo).filter(Photo.filepath == str(img_file)).first()
            if not existing_photo:
                try:
                    # Extract image info and metadata
                    processor = ImageProcessor()
                    
                    # Get basic image info
                    image_info = processor.get_image_info(img_file)
                    
                    # Extract EXIF metadata
                    exif_data = processor.extract_exif(img_file)
                    
                    # Compute perceptual hashes
                    hashes = processor.compute_hashes(img_file)
                    
                    # Create photo record with all metadata
                    photo = Photo(
                        filename=img_file.name,
                        filepath=str(img_file),
                        folder_id=folder_obj.id,
                        # Image dimensions
                        width=image_info.get('width') if image_info else None,
                        height=image_info.get('height') if image_info else None,
                        size=image_info.get('size') if image_info else img_file.stat().st_size,
                        format=image_info.get('format') if image_info else None,
                        # Hashes for duplicate detection
                        phash=hashes.get('phash'),
                        dhash=hashes.get('dhash'),
                        # EXIF metadata
                        date_taken=exif_data.get('date_taken'),
                        camera_make=exif_data.get('camera_make'),
                        camera_model=exif_data.get('camera_model'),
                        lens_model=exif_data.get('lens_model'),
                        iso=exif_data.get('iso'),
                        aperture=exif_data.get('aperture'),
                        shutter_speed=exif_data.get('shutter_speed'),
                        focal_length=exif_data.get('focal_length'),
                        gps_latitude=exif_data.get('gps_latitude'),
                        gps_longitude=exif_data.get('gps_longitude'),
                        gps_altitude=exif_data.get('gps_altitude')
                    )
                    db.add(photo)
                    new_photos += 1
                    logger.info(f"Added photo with metadata: {img_file.name}")
                    
                except Exception as e:
                    logger.warning(f"Skipping photo with error: {img_file.name} - {e}")
                    continue

            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Error committing photos: {e}")
        
        # Update folder stats
        folder_obj.total_photos = db.query(Photo).filter(
            Photo.folder_id == folder_obj.id,
            Photo.is_deleted == False
        ).count()
        
        db.commit()
        
        return {
            "folder_id": folder_obj.id,
            "name": folder_obj.name,
            "path": str(folder_path),
            "total_photos": folder_obj.total_photos,
            "new_photos": new_photos,
            "subfolders_created": True
        }
        
    except Exception as e:
        logger.error(f"Error scanning folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{folder_id}")
async def get_folder_stats(folder_id: int, db: Session = Depends(get_db)):
    """Get detailed stats for a folder"""
    try:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()
        
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")
        
        # Count photos with thumbs
        thumbs_count = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.has_thumb == True
        ).count()
        
        # Count photos with web versions
        web_count = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.has_web == True
        ).count()
        
        # Favorites
        favorites_count = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.is_favorite == True
        ).count()
        
        # Deleted
        deleted_count = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.is_deleted == True
        ).count()
        
        return {
            "id": folder.id,
            "name": folder.name,
            "path": folder.path,
            "total_photos": folder.total_photos,
            "favorites_count": favorites_count,
            "deleted_count": deleted_count,
            "thumbs_count": thumbs_count,
            "web_count": web_count,
            "has_thumbs": thumbs_count == folder.total_photos,
            "has_web": web_count > 0
        }
        
    except Exception as e:
        logger.error(f"Error getting folder stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_folders(db: Session = Depends(get_db)):
    """List all folders in database"""
    try:
        folders = db.query(Folder).all()
        
        result = []
        for folder in folders:
            result.append({
                "id": folder.id,
                "name": folder.name,
                "path": folder.path,
                "total_photos": folder.total_photos,
                "created_at": folder.created_at.isoformat() if folder.created_at else None
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error listing folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))
