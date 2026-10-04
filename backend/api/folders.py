"""
Folders API - Scan folders, create structure, get folder stats
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from pathlib import Path
from typing import List
import logging
import os

from database import get_db, utcnow, Folder, Photo, PhotoSimilarGroup
from api.similar import clear_pending_groups
from utils.analysis import enqueue_folder_analysis
from utils.image_processing import HEIF_EXTENSIONS, RAW_EXTENSIONS
from utils.photo_files import get_original_path
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tif', '.tiff', '.webp'} | HEIF_EXTENSIONS | RAW_EXTENSIONS
WORKING_SUBFOLDERS = ['thumbs', 'web', 'cancellate', 'preferite']


def _find_images(folder_path: Path, recursive: bool = False) -> List[Path]:
    """
    Images in the folder (and its subfolders if `recursive`).
    Working subfolders (thumbs/, web/...) are skipped at any depth.
    """
    if not recursive:
        candidates = folder_path.iterdir()
    else:
        candidates = []
        for directory, subdirectories, files in os.walk(folder_path):
            subdirectories[:] = [d for d in subdirectories if d not in WORKING_SUBFOLDERS]
            candidates.extend(Path(directory) / name for name in files)

    return sorted(
        entry for entry in candidates
        if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS
    )


def _remove_missing_photos(db: Session, folder_id: int) -> int:
    """Forget photos whose file no longer exists on disk (in the folder or in cancellate/)"""
    missing_ids = [
        photo.id for photo in db.query(Photo).filter(Photo.folder_id == folder_id)
        if not get_original_path(photo).exists()
    ]
    if missing_ids:
        db.query(PhotoSimilarGroup).filter(PhotoSimilarGroup.photo_id.in_(missing_ids)).delete(synchronize_session=False)
        db.query(Photo).filter(Photo.id.in_(missing_ids)).delete(synchronize_session=False)
        db.commit()
    return len(missing_ids)


def _same_path(a: str, b: str) -> bool:
    """Same folder despite case (Windows), trailing separators or relative segments"""
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _count_photos(db: Session, folder_id: int, *conditions) -> int:
    return db.query(func.count(Photo.id)).filter(Photo.folder_id == folder_id, *conditions).scalar()


class FolderCreate(BaseModel):
    path: str
    recursive: bool = False


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
        
        # Check if folder already in database (C:\Fotos, c:\fotos\ and C:/Fotos are the same folder)
        existing_folder = next(
            (f for f in db.query(Folder).all() if _same_path(f.path, str(folder_path))),
            None
        )
        
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
        
        removed_photos = _remove_missing_photos(db, folder_obj.id)
        if removed_photos:
            logger.info(f"Removed {removed_photos} photos no longer on disk from {folder_path}")

        # Register new images quickly; metadata and hashes are computed in the background.
        # `filename` is the path relative to the folder, so subfolder photos keep their
        # structure inside thumbs/, web/, cancellate/ and preferite/.
        # Every registered file, in any folder: a photo already indexed through another
        # (parent or child) folder is not registered twice
        known_paths = {
            os.path.normcase(filepath) for (filepath,) in db.query(Photo.filepath)
        }
        new_photos = [
            Photo(
                filename=img_file.relative_to(folder_path).as_posix(),
                filepath=str(img_file),
                folder_id=folder_obj.id,
                size=img_file.stat().st_size
            )
            for img_file in _find_images(folder_path, folder.recursive)
            if os.path.normcase(str(img_file)) not in known_paths
        ]
        db.add_all(new_photos)
        folder_obj.last_scanned = utcnow()
        db.commit()

        # Groups proposed before this scan may reference removed photos or miss new ones
        if new_photos or removed_photos:
            clear_pending_groups(db, folder_obj.id)
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
            "removed_photos": removed_photos,
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
        
        # All counts but `deleted_count` are over the photos still in the folder
        active = Photo.is_deleted == False
        total_photos = _count_photos(db, folder_id, active)
        thumbs_count = _count_photos(db, folder_id, active, Photo.has_thumb == True)
        web_count = _count_photos(db, folder_id, active, Photo.has_web == True)
        favorites_count = _count_photos(db, folder_id, active, Photo.is_favorite == True)
        deleted_count = _count_photos(db, folder_id, Photo.is_deleted == True)

        return {
            "id": folder.id,
            "name": folder.name,
            "path": folder.path,
            "total_photos": total_photos,
            "favorites_count": favorites_count,
            "deleted_count": deleted_count,
            "thumbs_count": thumbs_count,
            "web_count": web_count,
            "has_thumbs": thumbs_count == total_photos,
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
                "total_photos": _count_photos(db, folder.id, Photo.is_deleted == False),
                "favorites_count": _count_photos(db, folder.id, Photo.is_deleted == False, Photo.is_favorite == True),
                "deleted_count": _count_photos(db, folder.id, Photo.is_deleted == True),
                "created_at": folder.created_at.isoformat() if folder.created_at else None,
                "last_scanned": folder.last_scanned.isoformat() if folder.last_scanned else None
            })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))
