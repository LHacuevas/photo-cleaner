"""
Photos API - Get photos, navigate, mark favorites, delete
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import os

from database import get_db, SessionLocal, Photo
from utils.image_processing import ImageProcessor, ROTATIONS, FLIPS, needs_jpeg_preview
from utils.task_queue import task_queue, TaskStatus
from utils.photo_files import (
    get_original_path,
    get_thumb_path,
    get_web_path,
    get_web_file_details,
    get_favorite_path,
    move_photo_variants,
    refresh_photo_file_state,
    set_favorite,
)
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_PAGE_SIZE = 5000

# FFmpeg is an external process, so threads are enough to use several cores
GENERATION_WORKERS = max(2, (os.cpu_count() or 4) // 2)

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


def _serialize_photo(photo: Photo) -> dict:
    """Serialize a photo model for API responses."""
    has_thumb, has_web = _sync_generated_flags(photo)
    web_details = get_web_file_details(photo) if has_web else {
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


def _serialize_photo_summary(photo: Photo) -> dict:
    """Lightweight serialization for listings: DB fields only, no filesystem access."""
    return {
        "id": photo.id,
        "filename": photo.filename,
        "is_favorite": photo.is_favorite,
        "is_deleted": photo.is_deleted,
        "has_thumb": photo.has_thumb,
        "has_web": photo.has_web,
    }


class BatchOperationRequest(BaseModel):
    """Batch operation request"""
    operation: str  # 'favorite', 'unfavorite', 'delete', 'restore'
    photo_ids: List[int]


def _filter_by_position(query, min_lat, max_lat, min_lon, max_lon, near_lat, near_lon, radius_km):
    area = (min_lat, max_lat, min_lon, max_lon)
    near = (near_lat, near_lon, radius_km)

    if any(value is not None for value in area):
        if None in area:
            raise HTTPException(status_code=400, detail="Area filter needs min_lat, max_lat, min_lon and max_lon")
        if min_lat > max_lat:
            raise HTTPException(status_code=400, detail="min_lat must not be greater than max_lat")
        query = query.filter(Photo.gps_latitude.between(min_lat, max_lat))
        if min_lon <= max_lon:
            query = query.filter(Photo.gps_longitude.between(min_lon, max_lon))
        else:
            # The area crosses the antimeridian (e.g. 170 -> -170)
            query = query.filter(or_(Photo.gps_longitude >= min_lon, Photo.gps_longitude <= max_lon))

    if any(value is not None for value in near):
        if None in near:
            raise HTTPException(status_code=400, detail="Radius filter needs near_lat, near_lon and radius_km")
        query = query.filter(
            Photo.gps_latitude != None,
            func.distance_km(Photo.gps_latitude, Photo.gps_longitude, near_lat, near_lon) <= radius_km
        )

    return query


@router.get("/list/{folder_id}")
def list_photos(
    folder_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=MAX_PAGE_SIZE),
    only_favorites: bool = False,
    only_deleted: bool = False,
    min_lat: Optional[float] = Query(None, ge=-90, le=90),
    max_lat: Optional[float] = Query(None, ge=-90, le=90),
    min_lon: Optional[float] = Query(None, ge=-180, le=180),
    max_lon: Optional[float] = Query(None, ge=-180, le=180),
    near_lat: Optional[float] = Query(None, ge=-90, le=90),
    near_lon: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: Optional[float] = Query(None, gt=0, le=20000),
    db: Session = Depends(get_db)
):
    """
    List photos in a folder with pagination.
    Returns summaries only; use /get/{photo_id} for metadata and web version details.

    Position filters (only photos with GPS match them):
    - area: min_lat, max_lat, min_lon, max_lon (min_lon > max_lon crosses the antimeridian)
    - radius: near_lat, near_lon, radius_km
    """
    try:
        query = db.query(Photo).filter(Photo.folder_id == folder_id)
        query = _filter_by_position(
            query, min_lat, max_lat, min_lon, max_lon, near_lat, near_lon, radius_km
        )
        
        if only_favorites:
            query = query.filter(Photo.is_favorite == True)
        
        if only_deleted:
            query = query.filter(Photo.is_deleted == True)
        else:
            query = query.filter(Photo.is_deleted == False)
        
        # Order by filename (id breaks ties so pages never overlap)
        query = query.order_by(Photo.filename, Photo.id)
        
        total = query.count()
        photos = query.offset(skip).limit(limit).all()
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "photos": [_serialize_photo_summary(p) for p in photos]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing photos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get/{photo_id}")
def get_photo(photo_id: int, db: Session = Depends(get_db)):
    """Get detailed info for a single photo"""
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")

        details = _serialize_photo(photo)
        db.commit()  # keep has_thumb/has_web synced with the filesystem
        return details
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file/{photo_id}")
def get_photo_file(photo_id: int, thumb: bool = False, prefer_web: bool = False, db: Session = Depends(get_db)):
    """Serve the actual photo file or thumbnail"""
    try:
        photo = db.query(Photo).filter(Photo.id == photo_id).first()
        
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        
        # Derivatives of TIFF/HEIC/RAW are JPEG files that keep the original name
        derivative_type = "image/jpeg" if needs_jpeg_preview(photo.filename) else None

        if thumb:
            thumb_path = get_thumb_path(photo)
            if thumb_path.exists():
                return FileResponse(thumb_path, media_type=derivative_type)
            else:
                raise HTTPException(status_code=404, detail="Thumbnail not found")
        else:
            web_path = get_web_path(photo)
            if web_path.exists() and (prefer_web or derivative_type):
                return FileResponse(web_path, media_type=derivative_type)

            original_path = get_original_path(photo)
            if not original_path.exists():
                raise HTTPException(status_code=404, detail="Photo file not found")

            if derivative_type:
                # Browsers can't display TIFF/HEIC/RAW: render a JPEG preview on the fly
                return Response(ImageProcessor.render_jpeg(original_path), media_type="image/jpeg")

            return FileResponse(original_path)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving photo file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/favorite/{photo_id}")
def toggle_favorite(photo_id: int, db: Session = Depends(get_db)):
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
def delete_photo(photo_id: int, db: Session = Depends(get_db)):
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
def restore_photo(photo_id: int, db: Session = Depends(get_db)):
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


def _generate_variants(db: Session, folder_id: int, variant: str, mode: str = 'web', task=None) -> dict:
    """
    Generate the missing thumbs ("thumb") or web versions ("web") of a folder.
    FFmpeg runs in parallel worker threads; all DB writes stay in the calling thread.
    """
    photos = _get_missing_generated_photos(db, folder_id, variant)

    if variant == "thumb":
        generate = ImageProcessor.generate_thumbnail
        get_target_path = get_thumb_path
    else:
        generate = lambda source, target: ImageProcessor.generate_web_version(source, target, mode)
        get_target_path = get_web_path

    # Resolve paths up front: ORM objects must not be touched from worker threads
    jobs = [(photo, get_original_path(photo), get_target_path(photo)) for photo in photos]
    success_count = 0
    error_count = 0

    logger.info(f"Generating {variant} for {len(jobs)} photos in folder {folder_id} ({GENERATION_WORKERS} workers)")

    with ThreadPoolExecutor(max_workers=GENERATION_WORKERS) as pool:
        futures = {pool.submit(generate, source, target): photo for photo, source, target in jobs}

        for done, future in enumerate(as_completed(futures), 1):
            photo = futures[future]
            if future.result():
                if variant == "thumb":
                    photo.has_thumb = True
                else:
                    photo.has_web = True
                success_count += 1
            else:
                error_count += 1

            if done % 50 == 0:
                db.commit()
                logger.info(f"Progress: {done}/{len(jobs)} ({success_count} success, {error_count} errors)")

            if task:
                task.set_progress(done, len(jobs))
                if task.is_cancelled:
                    pool.shutdown(cancel_futures=True)
                    break

    db.commit()
    logger.info(f"Generation of {variant} finished: {success_count} success, {error_count} errors")

    return {
        "total": len(jobs),
        "success": success_count,
        "errors": error_count,
    }


def _enqueue_generation(name: str, folder_id: int, variant: str, mode: str = 'web') -> str:
    def run(task):
        db = SessionLocal()
        try:
            result = _generate_variants(db, folder_id, variant, mode, task)
            return {**result, "mode": mode} if variant == "web" else result
        finally:
            db.close()

    return task_queue.enqueue(name, run)


@router.post("/generate-thumbs/{folder_id}")
def generate_thumbnails(folder_id: int, db: Session = Depends(get_db)):
    """Generate thumbnails for all photos in folder (blocks until done)"""
    try:
        result = _generate_variants(db, folder_id, "thumb")
        
        if result["total"] == 0:
            return {**result, "message": "All thumbnails have already been created"}
        
        return {**result, "message": f"Generated {result['success']} thumbnails, {result['errors']} failed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating thumbnails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-web/{folder_id}")
def generate_web_versions(
    folder_id: int,
    mode: str = 'web',
    db: Session = Depends(get_db)
):
    """Generate web-optimized versions for all photos (blocks until done)"""
    try:
        result = {**_generate_variants(db, folder_id, "web", mode), "mode": mode}
        
        if result["total"] == 0:
            return {**result, "message": "All web versions have already been created"}
        
        return {**result, "message": f"Generated {result['success']} web versions ({mode}), {result['errors']} failed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating web versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-operation")
def batch_operation(
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
def generate_thumbnails_async(folder_id: int, db: Session = Depends(get_db)):
    """Generate thumbnails asynchronously (background task)"""
    try:
        if not _get_missing_generated_photos(db, folder_id, "thumb"):
            return {
                "task_id": None,
                "message": "All thumbnails have already been created",
                "status": "already_exists"
            }

        task_id = _enqueue_generation(f"Generate thumbnails for folder {folder_id}", folder_id, "thumb")
        
        return {
            "task_id": task_id,
            "message": "Thumbnail generation started in background",
            "status_url": f"/api/photos/tasks/{task_id}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enqueuing thumbnail task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-web-async/{folder_id}")
def generate_web_async(
    folder_id: int,
    mode: str = 'web',
    db: Session = Depends(get_db)
):
    """Generate web versions asynchronously (background task)"""
    try:
        if not _get_missing_generated_photos(db, folder_id, "web"):
            return {
                "task_id": None,
                "message": f"All web versions ({mode}) have already been created",
                "status": "already_exists"
            }

        task_id = _enqueue_generation(f"Generate web versions ({mode}) for folder {folder_id}", folder_id, "web", mode)
        
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
def get_task_status(task_id: str):
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


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    """Cancel a pending or running background task"""
    if not task_queue.get_task(task_id):
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return {"id": task_id, "cancelled": task_queue.cancel_task(task_id)}


@router.get("/tasks")
def list_tasks(status: Optional[TaskStatus] = None):
    """List all background tasks, optionally only those with `status`"""
    try:
        tasks = task_queue.list_tasks(status)
        
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
    Rotate/flip a photo without losing data: JPEG originals (and their preferite/
    copy) only get a new EXIF Orientation tag; lossless formats are re-saved with
    the exact same pixels. Generated thumb/web versions are re-encoded.
    """
    original_path = get_original_path(photo)
    if not original_path.exists():
        raise HTTPException(status_code=404, detail="Photo file not found")

    if original_path.suffix.lower() in ('.jpg', '.jpeg'):
        transform_original = ImageProcessor.transform_original
    elif ImageProcessor.can_transform_losslessly(original_path):
        transform_original = ImageProcessor.transform_lossless
    else:
        raise HTTPException(
            status_code=400,
            detail="Rotate/flip is only supported for JPEG and lossless still images (PNG, BMP, TIFF, GIF, lossless WebP)"
        )

    if not transform_original(original_path, op):
        raise HTTPException(status_code=500, detail="Failed to update photo orientation")

    favorite_path = get_favorite_path(photo)
    if favorite_path.exists():
        transform_original(favorite_path, op)

    for derivative_path in (get_thumb_path(photo), get_web_path(photo)):
        if derivative_path.exists() and not ImageProcessor.transform_derivative(derivative_path, op):
            # Derivatives can be regenerated: drop it rather than keep a wrongly oriented one
            derivative_path.unlink(missing_ok=True)

    # Hashes and dimensions describe the photo as displayed, which just changed
    info = ImageProcessor.get_image_info(original_path)
    if info:
        photo.width, photo.height = info['width'], info['height']
    hashes = ImageProcessor.compute_hashes(original_path)
    photo.phash, photo.dhash = hashes['phash'], hashes['dhash']

    refresh_photo_file_state(photo)


@router.post("/rotate/{photo_id}")
def rotate_photo(
    photo_id: int,
    degrees: int = 90,
    db: Session = Depends(get_db)
):
    """
    Rotate a photo without losing data (JPEG and lossless still formats, see _transform_photo)
    
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
def flip_photo(
    photo_id: int,
    direction: str = 'horizontal',
    db: Session = Depends(get_db)
):
    """
    Flip a photo without losing data (JPEG and lossless still formats, see _transform_photo)
    
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
