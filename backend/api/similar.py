"""
Similar Photos API - Detect duplicates and similar photos using perceptual hashing
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import List
import logging

import numpy as np

from database import get_db, Photo, SimilarGroup, PhotoSimilarGroup
from utils.analysis import enqueue_folder_analysis
from utils.photo_files import get_web_file_details, move_photo_variants

logger = logging.getLogger(__name__)

router = APIRouter()


def clear_pending_groups(db: Session, folder_id: int):
    """
    Forget the folder's unreviewed groups; Compare regroups when none are pending.
    Called whenever the folder's photos or hashes change, so groups never go stale.
    """
    pending_group_ids = [
        group_id for (group_id,) in db.query(SimilarGroup.id).filter(
            SimilarGroup.folder_id == folder_id,
            SimilarGroup.is_reviewed == False
        )
    ]
    if pending_group_ids:
        db.query(PhotoSimilarGroup).filter(
            PhotoSimilarGroup.group_id.in_(pending_group_ids)
        ).delete(synchronize_session=False)
        db.query(SimilarGroup).filter(
            SimilarGroup.id.in_(pending_group_ids)
        ).delete(synchronize_session=False)
        db.commit()


def _is_valid_hash(phash: str) -> bool:
    try:
        int(phash, 16)
        return True
    except (TypeError, ValueError):
        return False


def _hash_array(photos: List[Photo]) -> np.ndarray:
    """64-bit perceptual hashes as a uint64 array (same order as `photos`)"""
    return np.array([int(photo.phash, 16) for photo in photos], dtype=np.uint64)


def _find_groups(hashes: np.ndarray, threshold: int) -> List[List[int]]:
    """
    Greedy grouping by Hamming distance: each photo not grouped yet collects
    every later ungrouped photo within `threshold` bits. Returns index lists.
    Each row is one vectorized XOR + popcount instead of a Python pair loop.
    """
    available = np.ones(len(hashes), dtype=bool)
    groups = []
    
    for i in range(len(hashes)):
        if not available[i]:
            continue
        
        distances = np.bitwise_count(hashes[i + 1:] ^ hashes[i])
        matches = np.flatnonzero(available[i + 1:] & (distances <= threshold)) + i + 1
        
        if len(matches):
            members = [i, *matches.tolist()]
            available[members] = False
            groups.append(members)
    
    return groups


def _average_distance(hashes: np.ndarray) -> float:
    """Mean pairwise Hamming distance within a group"""
    pairwise = np.bitwise_count(hashes[:, None] ^ hashes[None, :])
    return float(pairwise[np.triu_indices(len(hashes), k=1)].mean())


@router.post("/analyze/{folder_id}")
def analyze_similar_photos(folder_id: int):
    """
    Compute missing hashes/metadata for the folder in the background.
    Returns the task to poll (an already running analysis is reused); group once it finishes.
    """
    try:
        task_id = enqueue_folder_analysis(folder_id)
        
        if not task_id:
            return {"task_id": None, "message": "All photos already analyzed"}
        
        return {
            "status": "started",
            "task_id": task_id,
            "status_url": f"/api/photos/tasks/{task_id}",
            "message": "Analysis started in background"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/group/{folder_id}")
def group_similar_photos(
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
        # Re-grouping replaces the pending (unreviewed) groups instead of piling up duplicates
        clear_pending_groups(db, folder_id)

        # Photos already reviewed in a group are not proposed again
        reviewed_photo_ids = select(PhotoSimilarGroup.photo_id).join(
            SimilarGroup, SimilarGroup.id == PhotoSimilarGroup.group_id
        ).where(
            SimilarGroup.folder_id == folder_id,
            SimilarGroup.is_reviewed == True
        )

        # Get all photos with hashes
        photos = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.is_deleted == False,
            Photo.phash != None,
            Photo.id.not_in(reviewed_photo_ids)
        ).order_by(Photo.filename, Photo.id).all()  # greedy grouping depends on order
        
        photos = [photo for photo in photos if _is_valid_hash(photo.phash)]
        
        if len(photos) < 2:
            return {"message": "Not enough photos to compare"}
        
        hashes = _hash_array(photos)
        groups = _find_groups(hashes, threshold)
        
        # Save groups to database
        saved_groups = []
        
        for members in groups:
            avg_distance = _average_distance(hashes[members])
            
            # Classify group
            if avg_distance <= 3:
                group_type = 'duplicate'
            elif avg_distance <= 5:
                group_type = 'burst'
            else:
                group_type = 'similar'
            
            similar_group = SimilarGroup(
                folder_id=folder_id,
                similarity_score=avg_distance,
                group_type=group_type
            )
            db.add(similar_group)
            db.flush()  # assigns similar_group.id
            
            db.add_all(
                PhotoSimilarGroup(photo_id=photos[i].id, group_id=similar_group.id)
                for i in members
            )
            
            saved_groups.append({
                "id": similar_group.id,
                "photo_count": len(members),
                "similarity_score": avg_distance,
                "group_type": group_type
            })
        
        db.commit()
        
        return {
            "groups_found": len(saved_groups),
            "photos_grouped": sum(len(members) for members in groups),
            "groups": saved_groups
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error grouping similar photos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/groups/{folder_id}")
def get_similar_groups(
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting similar groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/group/{group_id}")
def get_group_details(group_id: int, db: Session = Depends(get_db)):
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
                    **(get_web_file_details(p) if p.has_web else {
                        "web_size": None,
                        "web_width": None,
                        "web_height": None
                    })
                }
                for p in photos
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting group details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/group/{group_id}/select/{photo_id}")
def select_best_photo(
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
        
        group_photo_ids = [
            pid for (pid,) in db.query(PhotoSimilarGroup.photo_id).filter(
                PhotoSimilarGroup.group_id == group_id
            )
        ]
        if photo_id not in group_photo_ids:
            raise HTTPException(status_code=400, detail="Photo does not belong to this group")
        
        # Mark group as reviewed and set selected photo
        group.is_reviewed = True
        group.selected_photo_id = photo_id
        
        deleted_count = 0
        if delete_others:
            photos_to_delete = db.query(Photo).filter(
                Photo.id.in_(group_photo_ids),
                Photo.id != photo_id,
                Photo.is_deleted == False
            ).all()
            
            # Same non-destructive move as the regular delete (original + thumbs/web/preferite)
            for photo in photos_to_delete:
                move_photo_variants(photo, True)
                deleted_count += 1
        
        db.commit()
        
        return {
            "group_id": group_id,
            "selected_photo_id": photo_id,
            "deleted_count": deleted_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error selecting best photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/group/{group_id}/skip")
def skip_group(group_id: int, db: Session = Depends(get_db)):
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error skipping group: {e}")
        raise HTTPException(status_code=500, detail=str(e))
