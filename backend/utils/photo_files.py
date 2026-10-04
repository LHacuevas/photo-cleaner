"""
Filesystem layout of a photo and its derivatives (thumbs, web, preferite, cancellate)
"""

from pathlib import Path
from typing import Optional
import shutil

from database import Photo
from utils.file_times import copy_file_times
from utils.image_processing import ImageProcessor


def get_folder_root(photo: Photo) -> Path:
    if photo.folder and photo.folder.path:
        return Path(photo.folder.path)
    return Path(photo.filepath).parent.parent if Path(photo.filepath).parent.name == 'cancellate' else Path(photo.filepath).parent


def _get_base(photo: Photo, deleted: Optional[bool]) -> Path:
    root = get_folder_root(photo)
    target_deleted = photo.is_deleted if deleted is None else deleted
    return root / 'cancellate' if target_deleted else root


def get_original_path(photo: Photo, deleted: Optional[bool] = None) -> Path:
    return _get_base(photo, deleted) / photo.filename


def get_thumb_path(photo: Photo, deleted: Optional[bool] = None) -> Path:
    return _get_base(photo, deleted) / 'thumbs' / photo.filename


def get_web_path(photo: Photo, deleted: Optional[bool] = None) -> Path:
    return _get_base(photo, deleted) / 'web' / photo.filename


def get_favorite_path(photo: Photo, deleted: Optional[bool] = None) -> Path:
    return _get_base(photo, deleted) / 'preferite' / photo.filename


def _ensure_variant_folders(root: Path):
    for subfolder in ['thumbs', 'web', 'preferite']:
        (root / subfolder).mkdir(parents=True, exist_ok=True)


def _move_if_exists(source: Path, destination: Path):
    if not source.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return True


def refresh_photo_file_state(photo: Photo):
    photo.filepath = str(get_original_path(photo))
    photo.has_thumb = get_thumb_path(photo).exists()
    photo.has_web = get_web_path(photo).exists()


def move_photo_variants(photo: Photo, target_deleted: bool):
    """Move the original and all its derivatives in or out of cancellate/ (non-destructive delete/restore)."""
    source_deleted = photo.is_deleted
    _ensure_variant_folders(_get_base(photo, target_deleted))

    for get_path in (get_original_path, get_thumb_path, get_web_path, get_favorite_path):
        _move_if_exists(get_path(photo, deleted=source_deleted), get_path(photo, deleted=target_deleted))

    photo.is_deleted = target_deleted
    refresh_photo_file_state(photo)


def set_favorite(photo: Photo, is_favorite: bool):
    """Mark/unmark a favorite, keeping the copy in preferite/ in sync."""
    favorite_path = get_favorite_path(photo)

    if is_favorite:
        favorite_path.parent.mkdir(parents=True, exist_ok=True)
        original_path = get_original_path(photo)
        shutil.copy2(original_path, favorite_path)
        copy_file_times(original_path, favorite_path)  # copy2 doesn't keep the creation date on Windows
    elif favorite_path.exists():
        favorite_path.unlink()

    photo.is_favorite = is_favorite


def get_web_file_details(photo: Photo) -> dict:
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
