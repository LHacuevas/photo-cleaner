"""
Photos API - Get photos, navigate, mark favorites, delete
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from pathlib import Path
from typing import List, Optional
import shutil
import logging

from database import get_db, Photo, Folder
from utils.image_processing import ImageProcessor
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class PhotoResponse(BaseModel):
    id: int
    filename: str
    filepath: str
    width: Optional[int]
    height: Optional[int]
    size: int
    is_favorite: bool
    is_deleted: bool
    has_thumb: bool
    has_web: bool
    date_taken: Optional[str]
    camera_model: Optional[str]
    
    class Config:
        from_attributes = True

class BatchOperationRequest(BaseModel):
    """Batch operation request"""
    operation: str  # 'favorite', 'unfavorite', 'delete', 'restore'
    photo_ids: List[int]


class BatchOperationResponse(BaseModel):
    """Batch operation response"""
    operation: str
    total: int
    success: int
    errors: int
    failed_ids: List[int] = []
    message: str

@router.get("/list/{folder_id}")
async def list_photos(
    folder_id: int,
    skip: int = 0,
    limit: int = 100,
    only_favorites: bool = False,
    only_deleted: bool = False,
    db: Session = Depends(get_db)
):
    """
    List photos in a folder with pagination
    """
    try:
        query = db.query(Photo).filter(Photo.folder_id == folder_id)
        
        if only_favorites:
            query = query.filter(Photo.is_favorite == True)
        
        if only_deleted:
            query = query.filter(Photo.is_deleted == True)
        else:
            query = query.filter(Photo.is_deleted == False)
        
        # Order by filename
        query = query.order_by(Photo.filename)
        
        total = query.count()
        photos = query.offset(skip).limit(limit).all()
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "photos": [
                {
                    "id": p.id,
                    "filename": p.filename,
                    "filepath": p.filepath,
                    "width": p.width,
                    "height": p.height,
                    "size": p.size,
                    "is_favorite": p.is_favorite,
                    "is_deleted": p.is_deleted,
                    "has_thumb": p.has_thumb,
                    "has_web": p.has_web,
                    "date_taken": p.date_taken.isoformat() if p.date_taken else None,
                    "camera_model": p.camera_model
                }
                for p in photos
            ]
        }
        
    except Exception as e:
        logger.error(f"Error listing photos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get/{photo_id}")
async def get_photo(photo_id: int, db: Session = Depends(get_db)):
    """Get detailed info for a single photo"""
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        
        return {
            "id": photo.id,
            "filename": photo.filename,
            "filepath": photo.filepath,
            "width": photo.width,
            "height": photo.height,
            "size": photo.size,
            "format": photo.format,
            "is_favorite": photo.is_favorite,
            "is_deleted": photo.is_deleted,
            "has_thumb": photo.has_thumb,
            "has_web": photo.has_web,
            "date_taken": photo.date_taken.isoformat() if photo.date_taken else None,
            "camera_make": photo.camera_make,
            "camera_model": photo.camera_model,
            "lens_model": photo.lens_model,
            "iso": photo.iso,
            "aperture": photo.aperture,
            "shutter_speed": photo.shutter_speed,
            "focal_length": photo.focal_length,
            "gps_latitude": photo.gps_latitude,
            "gps_longitude": photo.gps_longitude
        }
        
    except Exception as e:
        logger.error(f"Error getting photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file/{photo_id}")
async def get_photo_file(photo_id: int, thumb: bool = False, db: Session = Depends(get_db)):
    """Serve the actual photo file or thumbnail"""
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        
        if thumb:
            # Serve thumbnail
            thumb_path = Path(photo.filepath).parent / 'thumbs' / Path(photo.filepath).name
            if thumb_path.exists():
                return FileResponse(thumb_path)
            else:
                raise HTTPException(status_code=404, detail="Thumbnail not found")
        else:
            # Serve original
            if Path(photo.filepath).exists():
                return FileResponse(photo.filepath)
            else:
                raise HTTPException(status_code=404, detail="Photo file not found")
        
    except Exception as e:
        logger.error(f"Error serving photo file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/favorite/{photo_id}")
async def toggle_favorite(photo_id: int, db: Session = Depends(get_db)):
    """Toggle favorite status and copy/move to preferite folder"""
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        
        photo.is_favorite = not photo.is_favorite
        
        # Copy to/from preferite folder
        original_path = Path(photo.filepath)
        favorite_path = original_path.parent / 'preferite' / original_path.name
        
        if photo.is_favorite:
            # Copy to preferite
            shutil.copy2(original_path, favorite_path)
            logger.info(f"Copied to favorites: {photo.filename}")
        else:
            # Remove from preferite
            if favorite_path.exists():
                favorite_path.unlink()
                logger.info(f"Removed from favorites: {photo.filename}")
        
        db.commit()
        
        return {
            "id": photo.id,
            "is_favorite": photo.is_favorite
        }
        
    except Exception as e:
        logger.error(f"Error toggling favorite: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete/{photo_id}")
async def delete_photo(photo_id: int, db: Session = Depends(get_db)):
    """Move photo to cancellate folder (non-destructive delete)"""
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        
        photo.is_deleted = True
        
        # Move to cancellate folder
        original_path = Path(photo.filepath)
        deleted_path = original_path.parent / 'cancellate' / original_path.name
        
        if original_path.exists():
            shutil.move(str(original_path), str(deleted_path))
            photo.filepath = str(deleted_path)
            logger.info(f"Moved to deleted: {photo.filename}")
        
        db.commit()
        
        return {
            "id": photo.id,
            "is_deleted": photo.is_deleted
        }
        
    except Exception as e:
        logger.error(f"Error deleting photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restore/{photo_id}")
async def restore_photo(photo_id: int, db: Session = Depends(get_db)):
    """Restore photo from cancellate folder"""
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        
        if not photo.is_deleted:
            return {"message": "Photo is not deleted"}
        
        photo.is_deleted = False
        
        # Move back from cancellate folder
        deleted_path = Path(photo.filepath)
        original_path = deleted_path.parent.parent / deleted_path.name
        
        if deleted_path.exists():
            shutil.move(str(deleted_path), str(original_path))
            photo.filepath = str(original_path)
            logger.info(f"Restored photo: {photo.filename}")
        
        db.commit()
        
        return {
            "id": photo.id,
            "is_deleted": photo.is_deleted
        }
        
    except Exception as e:
        logger.error(f"Error restoring photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-thumbs/{folder_id}")
async def generate_thumbnails(folder_id: int, db: Session = Depends(get_db)):
    """Generate thumbnails for all photos in folder"""
    try:
        photos = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.has_thumb == False,
            Photo.is_deleted == False
        ).all()
        
        if not photos:
            return {
                "total": 0,
                "success": 0,
                "errors": 0,
                "message": "No photos need thumbnails"
            }
        
        processor = ImageProcessor()
        success_count = 0
        error_count = 0
        
        logger.info(f"Starting thumbnail generation for {len(photos)} photos in folder {folder_id}")
        
        for i, photo in enumerate(photos, 1):
            original_path = Path(photo.filepath)
            thumb_path = original_path.parent / 'thumbs' / original_path.name
            
            if processor.generate_thumbnail(original_path, thumb_path):
                photo.has_thumb = True
                success_count += 1
                logger.info(f"[{i}/{len(photos)}] Thumbnail generated: {photo.filename}")
            else:
                error_count += 1
                logger.warning(f"[{i}/{len(photos)}] Failed to generate thumbnail: {photo.filename}")
            
            # Commit every 10 photos to show progress
            if i % 10 == 0:
                db.commit()
                logger.info(f"Progress: {i}/{len(photos)} photos processed ({success_count} success, {error_count} errors)")
        
        db.commit()
        logger.info(f"Thumbnail generation completed: {success_count} success, {error_count} errors")
        
        return {
            "total": len(photos),
            "success": success_count,
            "errors": error_count,
            "message": f"Generated {success_count} thumbnails, {error_count} failed"
        }
        
    except Exception as e:
        logger.error(f"Error generating thumbnails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-web/{folder_id}")
async def generate_web_versions(
    folder_id: int,
    mode: str = 'web',
    db: Session = Depends(get_db)
):
    """Generate web-optimized versions for all photos"""
    try:
        photos = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.is_deleted == False
        ).all()
        
        if not photos:
            return {
                "total": 0,
                "success": 0,
                "errors": 0,
                "mode": mode,
                "message": "No photos found"
            }
        
        processor = ImageProcessor()
        success_count = 0
        error_count = 0
        
        logger.info(f"Starting web version generation ({mode} mode) for {len(photos)} photos in folder {folder_id}")
        
        for i, photo in enumerate(photos, 1):
            original_path = Path(photo.filepath)
            web_path = original_path.parent / 'web' / original_path.name
            
            if processor.generate_web_version(original_path, web_path, mode):
                photo.has_web = True
                success_count += 1
                logger.info(f"[{i}/{len(photos)}] Web version generated ({mode}): {photo.filename}")
            else:
                error_count += 1
                logger.warning(f"[{i}/{len(photos)}] Failed to generate web version ({mode}): {photo.filename}")
            
            # Commit every 10 photos to show progress
            if i % 10 == 0:
                db.commit()
                logger.info(f"Progress: {i}/{len(photos)} photos processed ({success_count} success, {error_count} errors)")
        
        db.commit()
        logger.info(f"Web version generation completed: {success_count} success, {error_count} errors")
        
        return {
            "total": len(photos),
            "success": success_count,
            "errors": error_count,
            "mode": mode,
            "message": f"Generated {success_count} web versions ({mode}), {error_count} failed"
        }
        
    except Exception as e:
        logger.error(f"Error generating web versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-operation")
async def batch_operation(
    request: BatchOperationRequest,
    db: Session = Depends(get_db)
):
    """
    Perform batch operations on multiple photos
    
    Operations:
    - favorite: Mark photos as favorite
    - unfavorite: Unmark photos as favorite
    - delete: Move photos to deleted
    - restore: Restore photos from deleted
    """
    try:
        if not request.photo_ids:
            raise HTTPException(status_code=400, detail="No photo IDs provided")
        
        if request.operation not in ['favorite', 'unfavorite', 'delete', 'restore']:
            raise HTTPException(status_code=400, detail=f"Unknown operation: {request.operation}")
        
        # Get all photos first
        photos = db.query(Photo).filter(Photo.id.in_(request.photo_ids)).all()
        photo_ids_found = {p.id for p in photos}
        failed_ids = [pid for pid in request.photo_ids if pid not in photo_ids_found]
        
        success_count = 0
        error_count = len(failed_ids)
        
        logger.info(f"Starting batch {request.operation} for {len(photos)} photos")
        
        for i, photo in enumerate(photos, 1):
            try:
                if request.operation == 'favorite':
                    photo.is_favorite = True
                    logger.info(f"[{i}/{len(photos)}] Marked favorite: {photo.filename}")
                
                elif request.operation == 'unfavorite':
                    photo.is_favorite = False
                    logger.info(f"[{i}/{len(photos)}] Unmarked favorite: {photo.filename}")
                
                elif request.operation == 'delete':
                    photo.is_deleted = True
                    original_path = Path(photo.filepath)
                    deleted_path = original_path.parent / 'cancellate' / original_path.name
                    
                    if original_path.exists():
                        deleted_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(original_path), str(deleted_path))
                        photo.filepath = str(deleted_path)
                    
                    logger.info(f"[{i}/{len(photos)}] Deleted: {photo.filename}")
                
                elif request.operation == 'restore':
                    photo.is_deleted = False
                    deleted_path = Path(photo.filepath)
                    original_path = deleted_path.parent.parent / deleted_path.name
                    
                    if deleted_path.exists():
                        original_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(deleted_path), str(original_path))
                        photo.filepath = str(original_path)
                    
                    logger.info(f"[{i}/{len(photos)}] Restored: {photo.filename}")
                
                success_count += 1
                
                # Commit every 25 operations
                if i % 25 == 0:
                    db.commit()
                    logger.info(f"Progress: {i}/{len(photos)} photos processed")
            
            except Exception as e:
                error_count += 1
                failed_ids.append(photo.id)
                logger.error(f"Error in batch {request.operation} for {photo.filename}: {e}")
        
        db.commit()
        logger.info(f"Batch {request.operation} completed: {success_count} success, {error_count} errors")
        
        return {
            "operation": request.operation,
            "total": len(request.photo_ids),
            "success": success_count,
            "errors": error_count,
            "failed_ids": failed_ids,
            "message": f"Batch {request.operation}: {success_count} success, {error_count} failed"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
