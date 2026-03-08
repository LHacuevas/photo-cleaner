"""
Query optimization utilities and helpers
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from database import Photo, Folder
import logging

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """Utilities for optimizing database queries"""
    
    @staticmethod
    def get_photos_with_pagination(
        db: Session,
        folder_id: int,
        skip: int = 0,
        limit: int = 100,
        only_favorites: bool = False,
        only_deleted: bool = False,
        sort_by: str = "filename"
    ):
        """
        Get photos with optimized pagination
        
        Args:
            db: Database session
            folder_id: ID of the folder
            skip: Number of photos to skip
            limit: Maximum number of photos to return
            only_favorites: Filter to favorites only
            only_deleted: Filter to deleted only
            sort_by: Field to sort by (filename, date_taken, size)
        
        Returns:
            Tuple of (total_count, photos_list)
        """
        try:
            # Build base query
            query = db.query(Photo).filter(Photo.folder_id == folder_id)
            
            # Apply filters
            if only_favorites:
                query = query.filter(Photo.is_favorite == True)
            
            if only_deleted:
                query = query.filter(Photo.is_deleted == True)
            else:
                query = query.filter(Photo.is_deleted == False)
            
            # Get total before pagination
            total = query.count()
            
            # Apply sorting
            if sort_by == "date_taken":
                query = query.order_by(Photo.date_taken.desc())
            elif sort_by == "size":
                query = query.order_by(Photo.size.desc())
            else:  # filename
                query = query.order_by(Photo.filename)
            
            # Apply pagination
            query = query.offset(skip).limit(limit)
            
            photos = query.all()
            
            logger.info(
                f"Query optimized: folder_id={folder_id}, "
                f"skip={skip}, limit={limit}, total={total}, "
                f"returned={len(photos)}"
            )
            
            return total, photos
        
        except Exception as e:
            logger.error(f"Error in optimized query: {e}")
            raise
    
    @staticmethod
    def get_folder_stats(db: Session, folder_id: int):
        """
        Get folder statistics with optimized queries
        
        Returns:
            Dict with stats
        """
        try:
            folder = db.query(Folder).filter(Folder.id == folder_id).first()
            
            if not folder:
                return None
            
            # Count queries
            total_photos = db.query(func.count(Photo.id)).filter(
                Photo.folder_id == folder_id,
                Photo.is_deleted == False
            ).scalar()
            
            favorites = db.query(func.count(Photo.id)).filter(
                Photo.folder_id == folder_id,
                Photo.is_favorite == True,
                Photo.is_deleted == False
            ).scalar()
            
            deleted = db.query(func.count(Photo.id)).filter(
                Photo.folder_id == folder_id,
                Photo.is_deleted == True
            ).scalar()
            
            # Check for thumbnails and web versions
            has_thumbs = db.query(func.count(Photo.id)).filter(
                Photo.folder_id == folder_id,
                Photo.has_thumb == True
            ).scalar() > 0
            
            has_web = db.query(func.count(Photo.id)).filter(
                Photo.folder_id == folder_id,
                Photo.has_web == True
            ).scalar() > 0
            
            return {
                "id": folder.id,
                "path": folder.path,
                "name": folder.name,
                "total_photos": total_photos or 0,
                "favorites_count": favorites or 0,
                "deleted_count": deleted or 0,
                "has_thumbs": has_thumbs,
                "has_web": has_web,
                "created_at": folder.created_at.isoformat() if folder.created_at else None,
                "last_scanned": folder.last_scanned.isoformat() if folder.last_scanned else None
            }
        
        except Exception as e:
            logger.error(f"Error getting folder stats: {e}")
            raise
    
    @staticmethod
    def validate_pagination_params(skip: int, limit: int, max_limit: int = 500):
        """Validate and sanitize pagination parameters"""
        if skip < 0:
            skip = 0
        
        if limit < 1:
            limit = 100
        
        if limit > max_limit:
            limit = max_limit
            logger.warning(f"Limit {limit} exceeds max {max_limit}, capped")
        
        return skip, limit
