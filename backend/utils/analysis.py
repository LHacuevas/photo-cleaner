"""
Background analysis of photos: dimensions, EXIF metadata and perceptual hashes
"""

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from database import SessionLocal, Photo
from utils.image_processing import ImageProcessor
from utils.photo_files import get_original_path
from utils.task_queue import task_queue, FINISHED_STATUSES

logger = logging.getLogger(__name__)

# PIL releases the GIL while decoding, so threads use several cores
ANALYSIS_WORKERS = os.cpu_count() or 4

# folder_id -> task_id of its pending/running analysis, so a folder is never analyzed twice at once
_folder_tasks: dict[int, str] = {}
_folder_tasks_lock = threading.Lock()


def _analyze_file(path: Path) -> dict:
    """Read everything that gets indexed from one image file (runs in worker threads)"""
    return {
        "info": ImageProcessor.get_image_info(path),
        "exif": ImageProcessor.extract_exif(path),
        "hashes": ImageProcessor.compute_hashes(path),
    }


def _apply_analysis(photo: Photo, data: dict):
    info = data["info"]
    if info:
        photo.width = info["width"]
        photo.height = info["height"]
        photo.format = info["format"]
        photo.size = info["size"]

    for field, value in data["exif"].items():
        setattr(photo, field, value)

    photo.phash = data["hashes"]["phash"]
    photo.dhash = data["hashes"]["dhash"]


def analyze_folder(folder_id: int, task=None) -> dict:
    """Analyze every non-deleted photo of the folder that has no hash yet"""
    db = SessionLocal()
    try:
        photos = db.query(Photo).filter(
            Photo.folder_id == folder_id,
            Photo.is_deleted == False,
            Photo.phash == None
        ).all()

        # Resolve paths up front: ORM objects must not be touched from worker threads
        jobs = [(photo, get_original_path(photo)) for photo in photos]
        analyzed = 0

        with ThreadPoolExecutor(max_workers=ANALYSIS_WORKERS) as pool:
            futures = {pool.submit(_analyze_file, path): photo for photo, path in jobs}

            for done, future in enumerate(as_completed(futures), 1):
                photo = futures[future]
                _apply_analysis(photo, future.result())
                if photo.phash:
                    analyzed += 1

                if done % 100 == 0:
                    db.commit()

                if task:
                    task.set_progress(done, len(jobs))
                    if task.is_cancelled:
                        pool.shutdown(cancel_futures=True)
                        break

        db.commit()
        logger.info(f"Analyzed {analyzed}/{len(jobs)} photos in folder {folder_id}")

        return {
            "total": len(jobs),
            "analyzed": analyzed,
            "errors": len(jobs) - analyzed,
        }
    finally:
        db.close()


def enqueue_folder_analysis(folder_id: int) -> Optional[str]:
    """
    Start analyzing the folder's pending photos in the background.
    Returns the task ID (an already running one if there is), or None if nothing is pending.
    """
    with _folder_tasks_lock:
        running_id = _folder_tasks.get(folder_id)
        running = task_queue.get_task(running_id) if running_id else None
        if running and running.status not in FINISHED_STATUSES:
            return running_id

        db = SessionLocal()
        try:
            pending = db.query(Photo.id).filter(
                Photo.folder_id == folder_id,
                Photo.is_deleted == False,
                Photo.phash == None
            ).count()
        finally:
            db.close()

        if not pending:
            _folder_tasks.pop(folder_id, None)
            return None

        task_id = task_queue.enqueue(
            f"Analyze {pending} photos in folder {folder_id}",
            analyze_folder,
            args=[folder_id]
        )
        _folder_tasks[folder_id] = task_id
        return task_id
