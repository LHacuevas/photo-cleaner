#!/usr/bin/env python3
"""
Script to update existing photos with metadata and hashes
Run this after implementing metadata extraction
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from database import SessionLocal, Photo
from utils.image_processing import ImageProcessor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_photo_metadata(photo: Photo, processor: ImageProcessor) -> bool:
    """Update a single photo with metadata and hashes"""
    try:
        img_path = Path(photo.filepath)

        if not img_path.exists():
            logger.warning(f"Photo file not found: {photo.filepath}")
            return False

        # Get basic image info
        image_info = processor.get_image_info(img_path)

        # Extract EXIF metadata
        exif_data = processor.extract_exif(img_path)

        # Compute perceptual hashes
        hashes = processor.compute_hashes(img_path)

        # Update photo record
        if image_info:
            photo.width = image_info.get('width')
            photo.height = image_info.get('height')
            photo.size = image_info.get('size')
            photo.format = image_info.get('format')

        # Hashes for duplicate detection
        if hashes:
            photo.phash = hashes.get('phash')
            photo.dhash = hashes.get('dhash')

        # EXIF metadata
        if exif_data:
            photo.date_taken = exif_data.get('date_taken')
            photo.camera_make = exif_data.get('camera_make')
            photo.camera_model = exif_data.get('camera_model')
            photo.lens_model = exif_data.get('lens_model')
            photo.iso = exif_data.get('iso')
            photo.aperture = exif_data.get('aperture')
            photo.shutter_speed = exif_data.get('shutter_speed')
            photo.focal_length = exif_data.get('focal_length')
            photo.gps_latitude = exif_data.get('gps_latitude')
            photo.gps_longitude = exif_data.get('gps_longitude')
            photo.gps_altitude = exif_data.get('gps_altitude')

        logger.info(f"Updated metadata for: {photo.filename}")
        return True

    except Exception as e:
        logger.error(f"Error updating {photo.filename}: {e}")
        return False

def main():
    """Update all photos without metadata"""
    db = SessionLocal()
    processor = ImageProcessor()

    try:
        # Get photos without camera_model (indicating no metadata) and check if file exists
        all_photos = db.query(Photo).filter(Photo.camera_model.is_(None)).all()
        
        # Filter photos that still exist on disk
        photos_to_update = []
        for photo in all_photos:
            if Path(photo.filepath).exists():
                photos_to_update.append(photo)
            else:
                logger.warning(f"Skipping non-existent file: {photo.filepath}")

        if not photos_to_update:
            logger.info("No photos need metadata update")
            return

        logger.info(f"Updating metadata for {len(photos_to_update)} photos...")

        updated_count = 0
        error_count = 0

        for i, photo in enumerate(photos_to_update):
            if update_photo_metadata(photo, processor):
                updated_count += 1
            else:
                error_count += 1
            
            # Commit every 50 photos to avoid memory issues
            if (i + 1) % 50 == 0:
                db.commit()
                logger.info(f"Progress: {i + 1}/{len(photos_to_update)} processed")

        # Final commit
        db.commit()
        logger.info(f"Metadata update complete: {updated_count} updated, {error_count} errors")

    except Exception as e:
        logger.error(f"Error during metadata update: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()