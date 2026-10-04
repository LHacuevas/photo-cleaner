"""
Folders API - Scan folders, create structure, get folder stats
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pathlib import Path
from typing import List
import logging

from database import get_db, Folder, Photo
from utils.analysis import enqueue_folder_analysis
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
WORKING_SUBFOLDERS = ['thumbs', 'web', 'cancellate', 'preferite']


def _find_images(folder_path: Path) -> List[Path]:
    """Images directly inside the folder (working subfolders are not scanned)"""
    return sorted(
        entry for entry in folder_path.iterdir()
        if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS
    )


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
def scan_folder(folder: FolderCreate, db: Session = Depends(get_db)):
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
        for subfolder in WORKING_SUBFOLDERS:
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
        
        # Register new images quickly; metadata and hashes are computed in the background
        known_paths = {
            filepath for (filepath,) in db.query(Photo.filepath).filter(Photo.folder_id == folder_obj.id)
        }
        new_photos = [
            Photo(
                filename=img_file.name,
                filepath=str(img_file),
                folder_id=folder_obj.id,
                size=img_file.stat().st_size
            )
            for img_file in _find_images(folder_path)
            if str(img_file) not in known_paths
        ]
        db.add_all(new_photos)
        db.commit()
        logger.info(f"Registered {len(new_photos)} new photos in {folder_path}")
        
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
            "new_photos": len(new_photos),
            "subfolders_created": True,
            "analysis_task_id": enqueue_folder_analysis(folder_obj.id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scanning folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{folder_id}")
def get_folder_stats(folder_id: int, db: Session = Depends(get_db)):
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting folder stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
def list_folders(db: Session = Depends(get_db)):
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))
