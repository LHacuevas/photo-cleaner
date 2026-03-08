"""
Metadata API - Search and filter photos by EXIF data
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, between
from typing import List, Optional
from datetime import datetime, date
import logging

from database import get_db, Photo
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class MetadataFilter(BaseModel):
    folder_id: int
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    min_iso: Optional[int] = None
    max_iso: Optional[int] = None
    min_aperture: Optional[float] = None
    max_aperture: Optional[float] = None
    has_gps: Optional[bool] = None
    only_favorites: Optional[bool] = False
    only_deleted: Optional[bool] = False


@router.post("/search")
async def search_photos(filters: MetadataFilter, db: Session = Depends(get_db)):
    """
    Search photos with multiple filters
    """
    try:
        query = db.query(Photo).filter(Photo.folder_id == filters.folder_id)
        
        # Date range filter
        if filters.date_from:
            query = query.filter(Photo.date_taken >= filters.date_from)
        
        if filters.date_to:
            query = query.filter(Photo.date_taken <= filters.date_to)
        
        # Camera filters
        if filters.camera_make:
            query = query.filter(Photo.camera_make.like(f"%{filters.camera_make}%"))
        
        if filters.camera_model:
            query = query.filter(Photo.camera_model.like(f"%{filters.camera_model}%"))
        
        # ISO range
        if filters.min_iso:
            query = query.filter(Photo.iso >= filters.min_iso)
        
        if filters.max_iso:
            query = query.filter(Photo.iso <= filters.max_iso)
        
        # Aperture range
        if filters.min_aperture:
            query = query.filter(Photo.aperture >= filters.min_aperture)
        
        if filters.max_aperture:
            query = query.filter(Photo.aperture <= filters.max_aperture)
        
        # GPS filter
        if filters.has_gps is not None:
            if filters.has_gps:
                query = query.filter(and_(
                    Photo.gps_latitude != None,
                    Photo.gps_longitude != None
                ))
            else:
                query = query.filter(or_(
                    Photo.gps_latitude == None,
                    Photo.gps_longitude == None
                ))
        
        # Status filters
        if filters.only_favorites:
            query = query.filter(Photo.is_favorite == True)
        
        if filters.only_deleted:
            query = query.filter(Photo.is_deleted == True)
        else:
            query = query.filter(Photo.is_deleted == False)
        
        # Execute query
        photos = query.all()
        
        return {
            "total": len(photos),
            "photos": [
                {
                    "id": p.id,
                    "filename": p.filename,
                    "filepath": p.filepath,
                    "date_taken": p.date_taken.isoformat() if p.date_taken else None,
                    "camera_model": p.camera_model,
                    "iso": p.iso,
                    "aperture": p.aperture,
                    "is_favorite": p.is_favorite,
                    "has_gps": p.gps_latitude is not None and p.gps_longitude is not None
                }
                for p in photos
            ]
        }
        
    except Exception as e:
        logger.error(f"Error searching photos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cameras/{folder_id}")
async def get_camera_list(folder_id: int, db: Session = Depends(get_db)):
    """Get list of unique cameras used in folder"""
    try:
        cameras = db.query(
            Photo.camera_make,
            Photo.camera_model
        ).filter(
            Photo.folder_id == folder_id,
            Photo.camera_model != None
        ).distinct().all()
        
        result = []
        for make, model in cameras:
            if model:
                camera_name = f"{make} {model}" if make else model
                result.append({
                    "make": make,
                    "model": model,
                    "display_name": camera_name
                })
        
        return {
            "total": len(result),
            "cameras": result
        }
        
    except Exception as e:
        logger.error(f"Error getting camera list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/date-range/{folder_id}")
async def get_date_range(folder_id: int, db: Session = Depends(get_db)):
    """Get the date range of photos in folder"""
    try:
        photos_with_dates = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.date_taken != None
        ).all()
        
        if not photos_with_dates:
            return {"min_date": None, "max_date": None}
        
        dates = [p.date_taken for p in photos_with_dates]
        
        return {
            "min_date": min(dates).isoformat(),
            "max_date": max(dates).isoformat(),
            "photos_with_dates": len(photos_with_dates)
        }
        
    except Exception as e:
        logger.error(f"Error getting date range: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{folder_id}")
async def get_metadata_stats(folder_id: int, db: Session = Depends(get_db)):
    """Get statistics about metadata in folder"""
    try:
        total_photos = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.is_deleted == False
        ).count()
        
        photos_with_exif = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.date_taken != None
        ).count()
        
        photos_with_gps = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.gps_latitude != None,
            Photo.gps_longitude != None
        ).count()
        
        unique_cameras = db.query(Photo.camera_model).filter(
            Photo.folder_id == folder_id,
            Photo.camera_model != None
        ).distinct().count()
        
        return {
            "total_photos": total_photos,
            "photos_with_exif": photos_with_exif,
            "photos_with_gps": photos_with_gps,
            "unique_cameras": unique_cameras,
            "exif_coverage": (photos_with_exif / total_photos * 100) if total_photos > 0 else 0,
            "gps_coverage": (photos_with_gps / total_photos * 100) if total_photos > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting metadata stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-month/{folder_id}")
async def get_photos_by_month(folder_id: int, db: Session = Depends(get_db)):
    """Group photos by year and month"""
    try:
        photos = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.date_taken != None,
            Photo.is_deleted == False
        ).all()
        
        # Group by year-month
        from collections import defaultdict
        by_month = defaultdict(list)
        
        for photo in photos:
            if photo.date_taken:
                key = f"{photo.date_taken.year}-{photo.date_taken.month:02d}"
                by_month[key].append({
                    "id": photo.id,
                    "filename": photo.filename,
                    "date_taken": photo.date_taken.isoformat()
                })
        
        # Sort by date
        result = []
        for month_key in sorted(by_month.keys(), reverse=True):
            year, month = month_key.split('-')
            result.append({
                "year": int(year),
                "month": int(month),
                "month_name": datetime(int(year), int(month), 1).strftime("%B %Y"),
                "photo_count": len(by_month[month_key]),
                "photos": by_month[month_key][:10]  # First 10 photos as preview
            })
        
        return {
            "total_months": len(result),
            "months": result
        }
        
    except Exception as e:
        logger.error(f"Error grouping photos by month: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gps-map/{folder_id}")
async def get_gps_locations(folder_id: int, db: Session = Depends(get_db)):
    """Get GPS coordinates for map display"""
    try:
        photos = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.gps_latitude != None,
            Photo.gps_longitude != None,
            Photo.is_deleted == False
        ).all()
        
        locations = []
        for photo in photos:
            locations.append({
                "id": photo.id,
                "filename": photo.filename,
                "latitude": photo.gps_latitude,
                "longitude": photo.gps_longitude,
                "altitude": photo.gps_altitude,
                "date_taken": photo.date_taken.isoformat() if photo.date_taken else None
            })
        
        return {
            "total": len(locations),
            "locations": locations
        }
        
    except Exception as e:
        logger.error(f"Error getting GPS locations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
