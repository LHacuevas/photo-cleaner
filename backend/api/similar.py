"""
Similar Photos API - Detect duplicates and similar photos using perceptual hashing
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pathlib import Path
from typing import List, Dict
import logging
from collections import defaultdict

from database import get_db, Photo, SimilarGroup, PhotoSimilarGroup, Folder
from utils.image_processing import ImageProcessor
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_web_file_details(photo: Photo) -> dict:
    web_path = Path(photo.filepath).parent / 'web' / Path(photo.filepath).name
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


class SimilarGroupResponse(BaseModel):
    id: int
    photo_count: int
    similarity_score: float
    group_type: str
    is_reviewed: bool
    photos: List[int]  # Photo IDs


@router.post("/analyze/{folder_id}")
async def analyze_similar_photos(
    folder_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Analyze photos in folder and detect similar/duplicate images
    This is a long-running task, runs in background
    """
    try:
        # Get all photos without hashes
        photos = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.is_deleted == False,
            Photo.phash == None
        ).all()
        
        if not photos:
            return {"message": "All photos already analyzed"}
        
        # Add background task to compute hashes
        background_tasks.add_task(compute_photo_hashes, photos, db)
        
        return {
            "status": "started",
            "photos_to_analyze": len(photos),
            "message": "Analysis started in background"
        }
        
    except Exception as e:
        logger.error(f"Error starting analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def compute_photo_hashes(photos: List[Photo], db: Session):
    """Background task to compute hashes for photos"""
    processor = ImageProcessor()
    
    for photo in photos:
        try:
            hashes = processor.compute_hashes(Path(photo.filepath))
            
            if hashes['phash']:
                photo.phash = hashes['phash']
                photo.dhash = hashes['dhash']
                
                # Also extract image info and EXIF if not already done
                if not photo.width:
                    info = processor.get_image_info(Path(photo.filepath))
                    if info:
                        photo.width = info['width']
                        photo.height = info['height']
                        photo.format = info['format']
                        photo.size = info['size']
                
                if not photo.date_taken:
                    exif = processor.extract_exif(Path(photo.filepath))
                    if exif:
                        photo.date_taken = exif.get('date_taken')
                        photo.camera_make = exif.get('camera_make')
                        photo.camera_model = exif.get('camera_model')
                        photo.lens_model = exif.get('lens_model')
                        photo.iso = exif.get('iso')
                        photo.aperture = exif.get('aperture')
                        photo.shutter_speed = exif.get('shutter_speed')
                        photo.focal_length = exif.get('focal_length')
                        photo.gps_latitude = exif.get('gps_latitude')
                        photo.gps_longitude = exif.get('gps_longitude')
                        photo.gps_altitude = exif.get('gps_altitude')
                
                db.commit()
                logger.info(f"Computed hashes for {photo.filename}")
                
        except Exception as e:
            logger.error(f"Error computing hashes for {photo.filename}: {e}")
            continue


@router.post("/group/{folder_id}")
async def group_similar_photos(
    folder_id: int,
    threshold: int = 5,
    db: Session = Depends(get_db)
):
    """
    Group similar photos based on perceptual hash similarity
    
    threshold: Hamming distance (0-64)
        0-5: Nearly identical (duplicates/burst)
        6-10: Very similar
        11-15: Similar
    """
    try:
        # Get all photos with hashes
        photos = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.is_deleted == False,
            Photo.phash != None
        ).all()
        
        if len(photos) < 2:
            return {"message": "Not enough photos to compare"}
        
        processor = ImageProcessor()
        
        # Compare all pairs and group similar ones
        groups = []
        processed = set()
        
        for i, photo1 in enumerate(photos):
            if photo1.id in processed:
                continue
            
            similar_photos = [photo1]
            
            for photo2 in photos[i+1:]:
                if photo2.id in processed:
                    continue
                
                distance = processor.compare_hashes(photo1.phash, photo2.phash)
                
                if distance <= threshold:
                    similar_photos.append(photo2)
                    processed.add(photo2.id)
            
            if len(similar_photos) > 1:
                groups.append(similar_photos)
                processed.add(photo1.id)
        
        # Save groups to database
        saved_groups = []
        
        for group_photos in groups:
            # Determine group type based on similarity
            avg_distance = 0
            comparisons = 0
            
            for i, p1 in enumerate(group_photos):
                for p2 in group_photos[i+1:]:
                    avg_distance += processor.compare_hashes(p1.phash, p2.phash)
                    comparisons += 1
            
            avg_distance = avg_distance / comparisons if comparisons > 0 else 0
            
            # Classify group
            if avg_distance <= 3:
                group_type = 'duplicate'
            elif avg_distance <= 5:
                group_type = 'burst'
            else:
                group_type = 'similar'
            
            # Create group in database
            similar_group = SimilarGroup(
                folder_id=folder_id,
                similarity_score=avg_distance,
                group_type=group_type
            )
            db.add(similar_group)
            db.commit()
            db.refresh(similar_group)
            
            # Add photos to group
            for photo in group_photos:
                assoc = PhotoSimilarGroup(
                    photo_id=photo.id,
                    group_id=similar_group.id
                )
                db.add(assoc)
            
            db.commit()
            
            saved_groups.append({
                "id": similar_group.id,
                "photo_count": len(group_photos),
                "similarity_score": avg_distance,
                "group_type": group_type
            })
        
        return {
            "groups_found": len(saved_groups),
            "photos_grouped": len(processed),
            "groups": saved_groups
        }
        
    except Exception as e:
        logger.error(f"Error grouping similar photos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/groups/{folder_id}")
async def get_similar_groups(
    folder_id: int,
    only_unreviewed: bool = False,
    db: Session = Depends(get_db)
):
    """Get all similar photo groups for a folder"""
    try:
        query = db.query(SimilarGroup).filter(SimilarGroup.folder_id == folder_id)
        
        if only_unreviewed:
            query = query.filter(SimilarGroup.is_reviewed == False)
        
        groups = query.all()
        
        result = []
        for group in groups:
            # Get photos in this group
            photo_ids = db.query(PhotoSimilarGroup.photo_id).filter(
                PhotoSimilarGroup.group_id == group.id
            ).all()
            photo_ids = [pid[0] for pid in photo_ids]
            
            result.append({
                "id": group.id,
                "photo_count": len(photo_ids),
                "similarity_score": group.similarity_score,
                "group_type": group.group_type,
                "is_reviewed": group.is_reviewed,
                "selected_photo_id": group.selected_photo_id,
                "photo_ids": photo_ids
            })
        
        return {
            "total_groups": len(result),
            "groups": result
        }
        
    except Exception as e:
        logger.error(f"Error getting similar groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/group/{group_id}")
async def get_group_details(group_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a specific group"""
    try:
        group = db.query(SimilarGroup).filter(SimilarGroup.id == group_id).first()
        
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        # Get all photos in group
        photo_ids = db.query(PhotoSimilarGroup.photo_id).filter(
            PhotoSimilarGroup.group_id == group_id
        ).all()
        photo_ids = [pid[0] for pid in photo_ids]
        
        photos = db.query(Photo).filter(Photo.id.in_(photo_ids)).all()
        
        return {
            "id": group.id,
            "similarity_score": group.similarity_score,
            "group_type": group.group_type,
            "is_reviewed": group.is_reviewed,
            "selected_photo_id": group.selected_photo_id,
            "photos": [
                {
                    "id": p.id,
                    "filename": p.filename,
                    "filepath": p.filepath,
                    "width": p.width,
                    "height": p.height,
                    "size": p.size,
                    "has_web": p.has_web,
                    "date_taken": p.date_taken.isoformat() if p.date_taken else None,
                    "is_favorite": p.is_favorite,
                    "is_deleted": p.is_deleted,
                    **(_get_web_file_details(p) if p.has_web else {
                        "web_size": None,
                        "web_width": None,
                        "web_height": None
                    })
                }
                for p in photos
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting group details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/group/{group_id}/select/{photo_id}")
async def select_best_photo(
    group_id: int,
    photo_id: int,
    delete_others: bool = False,
    db: Session = Depends(get_db)
):
    """
    Select the best photo from a group
    Optionally delete the others
    """
    try:
        group = db.query(SimilarGroup).filter(SimilarGroup.id == group_id).first()
        
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        # Mark group as reviewed and set selected photo
        group.is_reviewed = True
        group.selected_photo_id = photo_id
        
        if delete_others:
            # Get all photos in group except selected one
            photo_ids = db.query(PhotoSimilarGroup.photo_id).filter(
                PhotoSimilarGroup.group_id == group_id,
                PhotoSimilarGroup.photo_id != photo_id
            ).all()
            photo_ids = [pid[0] for pid in photo_ids]
            
            # Mark them as deleted
            photos_to_delete = db.query(Photo).filter(Photo.id.in_(photo_ids)).all()
            
            for photo in photos_to_delete:
                photo.is_deleted = True
                
                # Move to cancellate folder
                original_path = Path(photo.filepath)
                deleted_path = original_path.parent / 'cancellate' / original_path.name
                
                if original_path.exists():
                    import shutil
                    shutil.move(str(original_path), str(deleted_path))
                    photo.filepath = str(deleted_path)
        
        db.commit()
        
        return {
            "group_id": group_id,
            "selected_photo_id": photo_id,
            "deleted_count": len(photo_ids) if delete_others else 0
        }
        
    except Exception as e:
        logger.error(f"Error selecting best photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/group/{group_id}/skip")
async def skip_group(group_id: int, db: Session = Depends(get_db)):
    """Mark group as reviewed without selecting a photo"""
    try:
        group = db.query(SimilarGroup).filter(SimilarGroup.id == group_id).first()
        
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        group.is_reviewed = True
        db.commit()
        
        return {
            "group_id": group_id,
            "is_reviewed": True
        }
        
    except Exception as e:
        logger.error(f"Error skipping group: {e}")
        raise HTTPException(status_code=500, detail=str(e))
