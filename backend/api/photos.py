"""
Photos API - Get photos, navigate, mark favorites, delete
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
from typing import List, Optional
import logging

from database import get_db, Photo
from utils.image_processing import ImageProcessor, ROTATIONS, FLIPS
from utils.task_queue import task_queue
from utils.photo_files import (
    get_original_path,
    get_thumb_path,
    get_web_path,
    get_favorite_path,
    move_photo_variants,
    refresh_photo_file_state,
    set_favorite,
)
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

def _sync_generated_flags(photo: Photo) -> tuple[bool, bool]:
    """Sync has_thumb/has_web with the filesystem for the current photo."""
    has_thumb = get_thumb_path(photo).exists()
    has_web = get_web_path(photo).exists()
    photo.has_thumb = has_thumb
    photo.has_web = has_web
    return has_thumb, has_web


def _get_missing_generated_photos(db: Session, folder_id: int, variant: str) -> list[Photo]:
    """Return photos missing a generated derivative and sync DB flags."""
    photos = db.query(Photo).filter(
        Photo.folder_id == folder_id,
        Photo.is_deleted == False
    ).all()

    missing = []
    changed = False

    for photo in photos:
        previous_thumb = photo.has_thumb
        previous_web = photo.has_web
        has_thumb, has_web = _sync_generated_flags(photo)
        expected = has_thumb if variant == "thumb" else has_web
        if not expected:
            missing.append(photo)
        changed = changed or previous_thumb != has_thumb or previous_web != has_web

    if changed:
        db.commit()

    return missing


def _get_web_file_details(photo: Photo) -> dict:
    """Return file metadata for the generated web version if it exists."""
    web_path = get_web_path(photo)
    if not web_path.exists():
        return {
            "web_size": None,
            "web_width": None,
            "web_height": None
        }

    web_info = ImageProcessor.get_image_info(web_path) or {}
    return {
        "web_size": web_info.get("size", web_path.stat().st_size),
        "web_width": web_info.get("width"),
        "web_height": web_info.get("height")
    }


def _serialize_photo(photo: Photo) -> dict:
    """Serialize a photo model for API responses."""
    has_thumb, has_web = _sync_generated_flags(photo)
    web_details = _get_web_file_details(photo) if has_web else {
        "web_size": None,
        "web_width": None,
        "web_height": None
    }

    return {
        "id": photo.id,
        "filename": photo.filename,
        "filepath": photo.filepath,
        "width": photo.width,
        "height": photo.height,
        "size": photo.size,
        "format": getattr(photo, "format", None),
        "is_favorite": photo.is_favorite,
        "is_deleted": photo.is_deleted,
        "has_thumb": has_thumb,
        "has_web": has_web,
        "date_taken": photo.date_taken.isoformat() if photo.date_taken else None,
        "camera_make": getattr(photo, "camera_make", None),
        "camera_model": photo.camera_model,
        "lens_model": getattr(photo, "lens_model", None),
        "iso": getattr(photo, "iso", None),
        "aperture": getattr(photo, "aperture", None),
        "shutter_speed": getattr(photo, "shutter_speed", None),
        "focal_length": getattr(photo, "focal_length", None),
        "gps_latitude": getattr(photo, "gps_latitude", None),
        "gps_longitude": getattr(photo, "gps_longitude", None),
        **web_details,
    }


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
            "photos": [_serialize_photo(p) for p in photos]
        }
        
    except HTTPException:
        raise
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
        
        return _serialize_photo(photo)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file/{photo_id}")
async def get_photo_file(photo_id: int, thumb: bool = False, prefer_web: bool = False, db: Session = Depends(get_db)):
    """Serve the actual photo file or thumbnail"""
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        
        if thumb:
            thumb_path = get_thumb_path(photo)
            if thumb_path.exists():
                return FileResponse(thumb_path)
            else:
                raise HTTPException(status_code=404, detail="Thumbnail not found")
        else:
            if prefer_web:
                web_path = get_web_path(photo)
                if web_path.exists():
                    return FileResponse(web_path)
            
            original_path = get_original_path(photo)
            if original_path.exists():
                return FileResponse(original_path)
            else:
                raise HTTPException(status_code=404, detail="Photo file not found")
        
    except HTTPException:
        raise
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
        
        set_favorite(photo, not photo.is_favorite)
        logger.info(f"{'Added to' if photo.is_favorite else 'Removed from'} favorites: {photo.filename}")

        db.commit()
        
        return {
            "id": photo.id,
            "is_favorite": photo.is_favorite
        }
        
    except HTTPException:
        raise
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
        
        move_photo_variants(photo, True)
        logger.info(f"Moved to deleted: {photo.filename}")
        
        db.commit()
        
        return {
            "id": photo.id,
            "is_deleted": photo.is_deleted
        }
        
    except HTTPException:
        raise
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
        
        move_photo_variants(photo, False)
        logger.info(f"Restored photo: {photo.filename}")
        
        db.commit()
        
        return {
            "id": photo.id,
            "is_deleted": photo.is_deleted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-thumbs/{folder_id}")
async def generate_thumbnails(folder_id: int, db: Session = Depends(get_db)):
    """Generate thumbnails for all photos in folder"""
    try:
        photos = _get_missing_generated_photos(db, folder_id, "thumb")
        
        if not photos:
            return {
                "total": 0,
                "success": 0,
                "errors": 0,
                "message": "All thumbnails have already been created"
            }
        
        processor = ImageProcessor()
        success_count = 0
        error_count = 0
        
        logger.info(f"Starting thumbnail generation for {len(photos)} photos in folder {folder_id}")
        
        for i, photo in enumerate(photos, 1):
            original_path = Path(photo.filepath)
            thumb_path = get_thumb_path(photo)
            
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
        
    except HTTPException:
        raise
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
        photos = _get_missing_generated_photos(db, folder_id, "web")
        
        if not photos:
            return {
                "total": 0,
                "success": 0,
                "errors": 0,
                "mode": mode,
                "message": "All web versions have already been created"
            }
        
        processor = ImageProcessor()
        success_count = 0
        error_count = 0
        
        logger.info(f"Starting web version generation ({mode} mode) for {len(photos)} photos in folder {folder_id}")
        
        for i, photo in enumerate(photos, 1):
            original_path = Path(photo.filepath)
            web_path = get_web_path(photo)
            
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
        
    except HTTPException:
        raise
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
                    set_favorite(photo, True)
                    logger.info(f"[{i}/{len(photos)}] Marked favorite: {photo.filename}")

                elif request.operation == 'unfavorite':
                    set_favorite(photo, False)
                    logger.info(f"[{i}/{len(photos)}] Unmarked favorite: {photo.filename}")
                
                elif request.operation == 'delete':
                    move_photo_variants(photo, True)
                    logger.info(f"[{i}/{len(photos)}] Deleted: {photo.filename}")
                
                elif request.operation == 'restore':
                    move_photo_variants(photo, False)
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


@router.post("/generate-thumbs-async/{folder_id}")
async def generate_thumbnails_async(folder_id: int, db: Session = Depends(get_db)):
    """Generate thumbnails asynchronously (background task)"""
    try:
        missing_photos = _get_missing_generated_photos(db, folder_id, "thumb")
        if not missing_photos:
            return {
                "task_id": None,
                "message": "All thumbnails have already been created",
                "status": "already_exists"
            }

        # Define async task function
        async def generate_thumbs_task(task=None):
            """Task function for thumbnail generation"""
            db_local = get_db().__next__()
            try:
                photos = _get_missing_generated_photos(db_local, folder_id, "thumb")
                
                processor = ImageProcessor()
                success_count = 0
                error_count = 0
                
                total = len(photos)

                for i, photo in enumerate(photos, 1):
                    try:
                        original_path = Path(photo.filepath)
                        thumb_path = get_thumb_path(photo)
                        
                        if processor.generate_thumbnail(original_path, thumb_path):
                            photo.has_thumb = True
                            success_count += 1
                        else:
                            error_count += 1

                        if task and total > 0:
                            task.progress = int(i / total * 100)
                        
                        if i % 10 == 0:
                            db_local.commit()
                    
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error generating thumb: {e}")
                
                db_local.commit()
                return {
                    "total": len(photos),
                    "success": success_count,
                    "errors": error_count
                }
            
            finally:
                db_local.close()
        
        # Enqueue task
        task_id = task_queue.enqueue(
            f"Generate thumbnails for folder {folder_id}",
            generate_thumbs_task
        )
        
        return {
            "task_id": task_id,
            "message": f"Thumbnail generation started in background",
            "status_url": f"/api/photos/tasks/{task_id}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enqueuing thumbnail task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-web-async/{folder_id}")
async def generate_web_async(
    folder_id: int,
    mode: str = 'web',
    db: Session = Depends(get_db)
):
    """Generate web versions asynchronously (background task)"""
    try:
        missing_photos = _get_missing_generated_photos(db, folder_id, "web")
        if not missing_photos:
            return {
                "task_id": None,
                "message": f"All web versions ({mode}) have already been created",
                "status": "already_exists"
            }

        # Define async task function
        async def generate_web_task(task=None):
            """Task function for web version generation"""
            db_local = get_db().__next__()
            try:
                photos = _get_missing_generated_photos(db_local, folder_id, "web")
                
                processor = ImageProcessor()
                success_count = 0
                error_count = 0
                
                total = len(photos)

                for i, photo in enumerate(photos, 1):
                    try:
                        original_path = Path(photo.filepath)
                        web_path = get_web_path(photo)
                        
                        if processor.generate_web_version(original_path, web_path, mode):
                            photo.has_web = True
                            success_count += 1
                        else:
                            error_count += 1

                        if task and total > 0:
                            task.progress = int(i / total * 100)
                        
                        if i % 10 == 0:
                            db_local.commit()
                    
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error generating web version: {e}")
                
                db_local.commit()
                return {
                    "total": len(photos),
                    "success": success_count,
                    "errors": error_count,
                    "mode": mode
                }
            
            finally:
                db_local.close()
        
        # Enqueue task
        task_id = task_queue.enqueue(
            f"Generate web versions ({mode}) for folder {folder_id}",
            generate_web_task
        )
        
        return {
            "task_id": task_id,
            "message": f"Web version generation ({mode}) started in background",
            "status_url": f"/api/photos/tasks/{task_id}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enqueuing web task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a background task"""
    try:
        task_status = task_queue.get_task_status(task_id)
        
        if not task_status:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        return task_status
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks")
async def list_tasks(status: Optional[str] = None):
    """List all background tasks"""
    try:
        tasks = task_queue.list_tasks()
        
        return {
            "total": len(tasks),
            "tasks": tasks
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _transform_photo(photo: Photo, op) -> None:
    """
    Rotate/flip a photo without touching the original's pixels: the original
    (and its preferite/ copy) only get a new EXIF Orientation tag, while the
    generated thumb/web versions are re-encoded.
    """
    original_path = get_original_path(photo)
    if not original_path.exists():
        raise HTTPException(status_code=404, detail="Photo file not found")

    if original_path.suffix.lower() not in ('.jpg', '.jpeg'):
        raise HTTPException(status_code=400, detail="Rotate/flip is only supported for JPEG photos")

    if not ImageProcessor.transform_original(original_path, op):
        raise HTTPException(status_code=500, detail="Failed to update photo orientation")

    favorite_path = get_favorite_path(photo)
    if favorite_path.exists():
        ImageProcessor.transform_original(favorite_path, op)

    for derivative_path in (get_thumb_path(photo), get_web_path(photo)):
        if derivative_path.exists() and not ImageProcessor.transform_derivative(derivative_path, op):
            # Derivatives can be regenerated: drop it rather than keep a wrongly oriented one
            derivative_path.unlink(missing_ok=True)

    refresh_photo_file_state(photo)


@router.post("/rotate/{photo_id}")
async def rotate_photo(
    photo_id: int,
    degrees: int = 90,
    db: Session = Depends(get_db)
):
    """
    Rotate a photo (JPEG only, lossless on the original)
    
    Parameters:
    - degrees: Rotation angle (90, -90, 180, 270)
    """
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        
        if degrees not in ROTATIONS:
            raise HTTPException(status_code=400, detail="Invalid rotation angle")
        
        _transform_photo(photo, ROTATIONS[degrees])
        db.commit()
        logger.info(f"Rotated photo {photo.id} by {degrees}°")
        
        return {
            "id": photo.id,
            "filename": photo.filename,
            "rotation": degrees,
            "message": f"Photo rotated {degrees}°"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rotating photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flip/{photo_id}")
async def flip_photo(
    photo_id: int,
    direction: str = 'horizontal',
    db: Session = Depends(get_db)
):
    """
    Flip a photo (JPEG only, lossless on the original)
    
    Parameters:
    - direction: 'horizontal' or 'vertical'
    """
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        
        if direction not in FLIPS:
            raise HTTPException(status_code=400, detail="Invalid flip direction")
        
        _transform_photo(photo, FLIPS[direction])
        db.commit()
        logger.info(f"Flipped photo {photo.id} ({direction})")
        
        return {
            "id": photo.id,
            "filename": photo.filename,
            "direction": direction,
            "message": f"Photo flipped {direction}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error flipping photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))
