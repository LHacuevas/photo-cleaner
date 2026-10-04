"""
Image processing utilities
Thumbnail generation, resizing, hash computation
"""

import subprocess
import shutil
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Iterator, Optional
from PIL import Image, ImageOps
from PIL.PngImagePlugin import PngInfo
import imagehash
import piexif
import pillow_heif
import rawpy
import logging
import io
import os
from datetime import datetime

import config

pillow_heif.register_heif_opener()

logger = logging.getLogger(__name__)

# User-facing rotations (clockwise degrees) and flips, as Pillow transpose operations
ROTATIONS = {
    90: Image.Transpose.ROTATE_270,
    -90: Image.Transpose.ROTATE_90,
    180: Image.Transpose.ROTATE_180,
    270: Image.Transpose.ROTATE_90,
}
FLIPS = {
    'horizontal': Image.Transpose.FLIP_LEFT_RIGHT,
    'vertical': Image.Transpose.FLIP_TOP_BOTTOM,
}

# Transpose needed to display pixels stored with each EXIF orientation (as ImageOps.exif_transpose)
_ORIENTATION_TRANSPOSE = {
    1: None,
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


ORIENTATION_TAG = piexif.ImageIFD.Orientation

HEIF_EXTENSIONS = {'.heic', '.heif'}
RAW_EXTENSIONS = {'.cr2', '.cr3', '.nef', '.arw', '.dng', '.orf', '.rw2', '.raf'}

# Browsers can't display these: derivatives are made as JPEG with Pillow and originals are
# served as on-the-fly JPEG previews
JPEG_PREVIEW_EXTENSIONS = {'.tif', '.tiff'} | HEIF_EXTENSIONS | RAW_EXTENSIONS

# Formats whose exact pixels can be re-saved after a rotate/flip
LOSSLESS_TRANSFORM_FORMATS = {'PNG', 'BMP', 'TIFF', 'GIF', 'WEBP'}

# LibRaw `sizes.flip` -> transpose that makes an unrotated embedded preview upright
_RAW_FLIP_TRANSPOSE = {
    3: Image.Transpose.ROTATE_180,
    5: Image.Transpose.ROTATE_90,   # 90° counter-clockwise
    6: Image.Transpose.ROTATE_270,  # 90° clockwise
}


def _open_raw_preview(path: Path) -> Image.Image:
    """Embedded JPEG preview of a RAW file (full decode only if there is none), made upright"""
    with rawpy.imread(str(path)) as raw:
        flip = raw.sizes.flip
        try:
            thumb = raw.extract_thumb()
        except (rawpy.LibRawNoThumbnailError, rawpy.LibRawUnsupportedThumbnailError):
            # postprocess() already applies the orientation
            return Image.fromarray(raw.postprocess(use_camera_wb=True))

    if thumb.format == rawpy.ThumbFormat.JPEG:
        img = Image.open(io.BytesIO(thumb.data))
        img.load()
    else:
        img = Image.fromarray(thumb.data)

    # Some previews carry their own EXIF orientation (handled by exif_transpose later)
    transpose = _RAW_FLIP_TRANSPOSE.get(flip)
    if transpose is not None and img.getexif().get(ORIENTATION_TAG, 1) == 1:
        img = img.transpose(transpose)
    return img


@contextmanager
def open_image(path: Path) -> Iterator[Image.Image]:
    """Open any supported photo with Pillow (HEIC via pillow-heif, RAW via its embedded preview)"""
    path = Path(path)
    img = _open_raw_preview(path) if path.suffix.lower() in RAW_EXTENSIONS else Image.open(path)
    try:
        yield img
    finally:
        img.close()


def _webp_is_lossless_still(path: Path) -> bool:
    """True for a single-frame lossless (VP8L) WebP; walks the RIFF chunks"""
    data = path.read_bytes()
    position = 12  # after "RIFF" <size> "WEBP"
    while position + 8 <= len(data):
        fourcc = data[position:position + 4]
        size = int.from_bytes(data[position + 4:position + 8], 'little')
        if fourcc == b'VP8L':
            return True
        if fourcc in (b'VP8 ', b'ANIM'):
            return False
        position += 8 + size + (size & 1)
    return False


def _compose_orientation(orientation: int, op: Image.Transpose) -> int:
    """
    EXIF orientation that displays the image as `orientation` followed by `op`.
    Found by applying both to a tiny asymmetric probe image and matching the result.
    """
    probe = Image.frombytes('L', (3, 2), bytes(range(6)))

    def displayed(o):
        transpose = _ORIENTATION_TRANSPOSE[o]
        return probe.transpose(transpose) if transpose is not None else probe

    target = displayed(orientation).transpose(op)
    for candidate in _ORIENTATION_TRANSPOSE:
        shown = displayed(candidate)
        if shown.size == target.size and shown.tobytes() == target.tobytes():
            return candidate
    raise ValueError(f"No EXIF orientation for {orientation} + {op}")


@lru_cache(maxsize=1)
def find_ffmpeg() -> Optional[str]:
    """
    FFmpeg executable: PHOTO_CLEANER_FFMPEG, then PATH, then common Windows
    install folders (winget, Program Files). None if not found.
    """
    candidates = [config.FFMPEG_PATH, shutil.which("ffmpeg")]

    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            winget_packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
            # Newest version folder first
            candidates += sorted(winget_packages.glob("*FFmpeg*/*/bin/ffmpeg.exe"), reverse=True)
        candidates.append(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "FFmpeg" / "bin" / "ffmpeg.exe")

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return None


def needs_jpeg_preview(path: Path) -> bool:
    """TIFF, HEIC and RAW: browsers can't show them, so derivatives/previews are JPEG (made with Pillow)"""
    return Path(path).suffix.lower() in JPEG_PREVIEW_EXTENSIONS


def _qscale_to_quality(qscale: int) -> int:
    """FFmpeg -q:v for JPEG (2..31, lower is better) -> 0..100 quality (JPEG via Pillow, WebP)"""
    return max(10, 96 - 3 * qscale)


def _fit_long_side(size: int) -> str:
    """FFmpeg scale filter: long side = `size` px, keeping aspect ratio, never upscaling"""
    return (
        f"scale=w='if(gt(iw,ih),min(iw,{size}),-2)'"
        f":h='if(gt(iw,ih),-2,min(ih,{size}))'"
    )


class ImageProcessor:
    """Handles all image processing operations"""
    
    THUMB_SIZE = 300  # px, long side
    THUMB_QUALITY = 5  # FFmpeg -q:v (1-31, lower is better)
    WEB_SIZES = {
        'web': 2048,
        'archive': 1600,
        'ultra': 1200
    }
    WEB_QUALITY = {'web': 3, 'archive': 5, 'ultra': 7}
    
    @staticmethod
    def get_ffmpeg_path() -> str:
        """Get FFmpeg executable path"""
        return find_ffmpeg() or "ffmpeg"
    
    @staticmethod
    def check_ffmpeg() -> bool:
        """Check if FFmpeg is available"""
        ffmpeg_path = ImageProcessor.get_ffmpeg_path()
        try:
            result = subprocess.run([ffmpeg_path, '-version'], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
    
    @staticmethod
    def _run_ffmpeg(input_path: Path, output_path: Path, size: int, qscale: int) -> bool:
        """
        Resize with FFmpeg (it applies the EXIF orientation itself).
        The output format follows the extension, i.e. the original's format.
        """
        if output_path.suffix.lower() == '.webp':
            quality = _qscale_to_quality(qscale)  # libwebp's -q:v is 0..100, higher is better
        else:
            quality = qscale
        cmd = [
            ImageProcessor.get_ffmpeg_path(),
            '-i', str(input_path),
            '-vf', _fit_long_side(size),
            '-q:v', str(quality),
            '-y',  # Overwrite
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg error for {input_path.name}: {result.stderr}")
        return result.returncode == 0
    
    @staticmethod
    def _resize_with_pillow(input_path: Path, output_path: Path, size: int, quality: int, exif: Optional[bytes] = None) -> bool:
        """Resize TIFF/HEIC/RAW (upright, long side = size) and save as JPEG"""
        with open_image(input_path) as img:
            resized = ImageOps.exif_transpose(img)
            resized.thumbnail((size, size))
            params = {"exif": exif} if exif else {}
            resized.convert("RGB").save(output_path, format="JPEG", quality=quality, **params)
        return True

    @staticmethod
    def _upright_exif(image_path: Path) -> Optional[bytes]:
        """
        The original's EXIF for a derivative whose pixels are already upright:
        orientation reset to 1, embedded thumbnail dropped. None if unavailable.
        """
        try:
            exif_dict = ImageProcessor._load_exif_dict(Path(image_path))
            if not exif_dict:
                return None
            exif_dict['0th'][ORIENTATION_TAG] = 1
            exif_dict['1st'] = {}
            exif_dict['thumbnail'] = None
            return piexif.dump(exif_dict)
        except Exception as e:
            logger.warning(f"Could not copy EXIF from {image_path}: {e}")
            return None
    
    @staticmethod
    def generate_thumbnail(input_path: Path, output_path: Path) -> bool:
        """
        Generate thumbnail: 300px long side, JPEG format, 10-30 KB
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if needs_jpeg_preview(input_path):
                created = ImageProcessor._resize_with_pillow(input_path, output_path, ImageProcessor.THUMB_SIZE, 80)
            else:
                created = ImageProcessor._run_ffmpeg(
                    input_path, output_path, ImageProcessor.THUMB_SIZE, ImageProcessor.THUMB_QUALITY
                )
            
            if created:
                logger.info(f"Thumbnail created: {output_path.name}")
            return created
                
        except Exception as e:
            logger.error(f"Error generating thumbnail: {e}")
            return False
    
    @staticmethod
    def generate_web_version(input_path: Path, output_path: Path, mode: str = 'web') -> bool:
        """
        Generate web-optimized version (long side, never upscaled)
        
        Modes:
        - web: 2048px, high quality (500-900 KB)
        - archive: 1600px, medium quality (300-600 KB)
        - ultra: 1200px, lower quality (150-400 KB)
        """
        try:
            size = ImageProcessor.WEB_SIZES.get(mode, 2048)
            quality = ImageProcessor.WEB_QUALITY.get(mode, 3)
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Web versions keep the original's metadata (date, camera, GPS...)
            exif = ImageProcessor._upright_exif(input_path)

            if needs_jpeg_preview(input_path):
                created = ImageProcessor._resize_with_pillow(
                    input_path, output_path, size, _qscale_to_quality(quality), exif
                )
            else:
                created = ImageProcessor._run_ffmpeg(input_path, output_path, size, quality)
                # FFmpeg doesn't write EXIF into JPEG output: copy it afterwards
                if created and exif and output_path.suffix.lower() in ('.jpg', '.jpeg'):
                    piexif.insert(exif, str(output_path))
            
            if created:
                logger.info(f"Web version created: {output_path.name} ({mode})")
            return created
                
        except Exception as e:
            logger.error(f"Error generating web version: {e}")
            return False
    
    @staticmethod
    def render_jpeg(image_path: Path, size: int = 2048) -> bytes:
        """Upright JPEG preview of a file browsers can't display (TIFF/HEIC/RAW without web version)"""
        with open_image(image_path) as img:
            preview = ImageOps.exif_transpose(img)
            preview.thumbnail((size, size))
            buffer = io.BytesIO()
            preview.convert("RGB").save(buffer, format="JPEG", quality=88)
        return buffer.getvalue()
    
    @staticmethod
    def compute_hashes(image_path: Path) -> dict:
        """
        Compute perceptual hashes for duplicate detection, on the image as displayed
        (so the same photo stored with different EXIF orientations still matches)

        Returns:
            dict with phash and dhash as strings
        """
        try:
            with open_image(image_path) as img:
                upright = ImageOps.exif_transpose(img)

                # Perceptual hash (best for finding similar images)
                phash = str(imagehash.phash(upright, hash_size=8))

                # Difference hash (good for rotations/crops)
                dhash = str(imagehash.dhash(upright, hash_size=8))

            return {
                'phash': phash,
                'dhash': dhash
            }

        except Exception as e:
            logger.error(f"Error computing hashes for {image_path}: {e}")
            return {'phash': None, 'dhash': None}

    @staticmethod
    def get_image_info(image_path) -> dict:
        """
        Get basic image information. Width/height are as displayed (EXIF orientation applied).

        Returns:
            dict with width, height, format, size
        """
        try:
            image_path = Path(image_path)

            if image_path.suffix.lower() in RAW_EXTENSIONS:
                with rawpy.imread(str(image_path)) as raw:
                    width, height = raw.sizes.width, raw.sizes.height
                    if raw.sizes.flip in (5, 6):
                        width, height = height, width
                image_format = image_path.suffix.lstrip('.').upper()
            else:
                with Image.open(image_path) as img:
                    width, height = img.size
                    if img.getexif().get(ORIENTATION_TAG, 1) in (5, 6, 7, 8):
                        width, height = height, width
                    image_format = img.format

            return {
                'width': width,
                'height': height,
                'format': image_format,
                'size': image_path.stat().st_size
            }

        except Exception as e:
            logger.error(f"Error getting image info for {image_path}: {e}")
            return None

    @staticmethod
    def _load_exif_dict(image_path: Path) -> Optional[dict]:
        """piexif dict for any supported format, None if the file has no EXIF"""
        if image_path.suffix.lower() in RAW_EXTENSIONS:
            try:
                # Most RAW formats (CR2, NEF, ARW, DNG...) are TIFF containers piexif can read
                return piexif.load(str(image_path))
            except Exception:
                pass  # fall back to the embedded preview's EXIF

        with open_image(image_path) as img:
            exif_bytes = img.info.get('exif')
        return piexif.load(exif_bytes) if exif_bytes else None

    @staticmethod
    def extract_exif(image_path: Path) -> dict:
        """
        Extract EXIF metadata from image

        Returns:
            dict with camera info, settings, GPS, date taken
        """
        try:
            exif_dict = ImageProcessor._load_exif_dict(Path(image_path))
            if not exif_dict:
                return {}

            result = {
                'date_taken': None,
                'camera_make': None,
                'camera_model': None,
                'lens_model': None,
                'iso': None,
                'aperture': None,
                'shutter_speed': None,
                'focal_length': None,
                'gps_latitude': None,
                'gps_longitude': None,
                'gps_altitude': None
            }

            # Extract common fields
            ifd0 = exif_dict.get('0th', {})
            exif = exif_dict.get('Exif', {})
            gps = exif_dict.get('GPS', {})
            
            # Camera info
            if piexif.ImageIFD.Make in ifd0:
                result['camera_make'] = ifd0[piexif.ImageIFD.Make].decode('utf-8', errors='ignore')
            
            if piexif.ImageIFD.Model in ifd0:
                result['camera_model'] = ifd0[piexif.ImageIFD.Model].decode('utf-8', errors='ignore')
            
            if piexif.ExifIFD.LensModel in exif:
                lens = exif[piexif.ExifIFD.LensModel].decode('utf-8', errors='ignore').strip('\x00 ')
                result['lens_model'] = lens or None

            # Photo settings
            if piexif.ExifIFD.ISOSpeedRatings in exif:
                iso = exif[piexif.ExifIFD.ISOSpeedRatings]
                result['iso'] = iso[0] if isinstance(iso, tuple) and iso else iso
            
            if piexif.ExifIFD.FNumber in exif:
                f_num = exif[piexif.ExifIFD.FNumber]
                result['aperture'] = f_num[0] / f_num[1] if isinstance(f_num, tuple) else f_num
            
            if piexif.ExifIFD.ExposureTime in exif:
                exp = exif[piexif.ExifIFD.ExposureTime]
                result['shutter_speed'] = f"{exp[0]}/{exp[1]}" if isinstance(exp, tuple) else str(exp)
            
            if piexif.ExifIFD.FocalLength in exif:
                focal = exif[piexif.ExifIFD.FocalLength]
                result['focal_length'] = focal[0] / focal[1] if isinstance(focal, tuple) else focal
            
            # Date taken
            if piexif.ExifIFD.DateTimeOriginal in exif:
                date_str = exif[piexif.ExifIFD.DateTimeOriginal].decode('utf-8', errors='ignore')
                try:
                    # EXIF format: 'YYYY:MM:DD HH:MM:SS'
                    result['date_taken'] = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                except ValueError:
                    logger.warning(f"Invalid date format: {date_str}")
                    result['date_taken'] = None
            
            # GPS
            if gps:
                # Latitude
                if piexif.GPSIFD.GPSLatitude in gps and piexif.GPSIFD.GPSLatitudeRef in gps:
                    lat = ImageProcessor._convert_gps_to_decimal(gps[piexif.GPSIFD.GPSLatitude])
                    lat_ref = gps[piexif.GPSIFD.GPSLatitudeRef].decode()
                    result['gps_latitude'] = lat if lat_ref == 'N' else -lat
                
                # Longitude
                if piexif.GPSIFD.GPSLongitude in gps and piexif.GPSIFD.GPSLongitudeRef in gps:
                    lon = ImageProcessor._convert_gps_to_decimal(gps[piexif.GPSIFD.GPSLongitude])
                    lon_ref = gps[piexif.GPSIFD.GPSLongitudeRef].decode()
                    result['gps_longitude'] = lon if lon_ref == 'E' else -lon
                
                # Altitude
                if piexif.GPSIFD.GPSAltitude in gps:
                    alt = gps[piexif.GPSIFD.GPSAltitude]
                    altitude = alt[0] / alt[1] if isinstance(alt, tuple) else alt
                    # GPSAltitudeRef 1 = below sea level
                    result['gps_altitude'] = -altitude if gps.get(piexif.GPSIFD.GPSAltitudeRef) == 1 else altitude
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting EXIF from {image_path}: {e}")
            return {}
    
    @staticmethod
    def _convert_gps_to_decimal(gps_coord: tuple) -> float:
        """Convert GPS coordinates from degrees/minutes/seconds to decimal"""
        degrees = gps_coord[0][0] / gps_coord[0][1]
        minutes = gps_coord[1][0] / gps_coord[1][1]
        seconds = gps_coord[2][0] / gps_coord[2][1]
        
        return degrees + (minutes / 60.0) + (seconds / 3600.0)
    
    @staticmethod
    def transform_original(image_path: Path, op: Image.Transpose) -> bool:
        """
        Rotate/flip a JPEG original losslessly: only its EXIF Orientation tag is
        rewritten, pixels and the rest of the metadata are left untouched.
        """
        try:
            data = image_path.read_bytes()
            exif_dict = piexif.load(data)
            current = exif_dict['0th'].get(piexif.ImageIFD.Orientation, 1)
            if current not in _ORIENTATION_TRANSPOSE:
                current = 1
            exif_dict['0th'][piexif.ImageIFD.Orientation] = _compose_orientation(current, op)

            output = io.BytesIO()
            piexif.insert(piexif.dump(exif_dict), data, output)

            # Write to a temp file first so a failure never leaves a truncated original
            tmp_path = image_path.with_name(image_path.name + '.tmp')
            tmp_path.write_bytes(output.getvalue())
            os.replace(tmp_path, image_path)

            logger.info(f"Updated EXIF orientation of {image_path.name}")
            return True

        except Exception as e:
            logger.error(f"Error updating orientation of {image_path}: {e}")
            return False

    @staticmethod
    def can_transform_losslessly(image_path: Path) -> bool:
        """Single-frame images in a lossless format, whose exact pixels can be re-saved"""
        # Pillow can open some RAW files (TIFF-based) and HEIC, but re-saving them would
        # replace the camera data with whatever image Pillow decoded: never edit them
        if Path(image_path).suffix.lower() in HEIF_EXTENSIONS | RAW_EXTENSIONS:
            return False
        try:
            with Image.open(image_path) as img:
                if img.format not in LOSSLESS_TRANSFORM_FORMATS or getattr(img, 'n_frames', 1) > 1:
                    return False
                if img.format == 'TIFF' and img.info.get('compression') in ('jpeg', 'tiff_jpeg'):
                    return False
                if img.format == 'WEBP' and not _webp_is_lossless_still(Path(image_path)):
                    return False
                return True
        except Exception:
            return False

    @staticmethod
    def transform_lossless(image_path: Path, op: Image.Transpose) -> bool:
        """
        Rotate/flip a lossless image (see can_transform_losslessly) by re-saving its exact
        pixels in the same format, keeping ICC profile, EXIF, DPI and PNG text chunks.
        """
        try:
            with Image.open(image_path) as img:
                image_format = img.format
                upright = ImageOps.exif_transpose(img)  # bake any EXIF orientation into the pixels
                transformed = upright.transpose(op)

                params = {}
                for key in ('icc_profile', 'dpi', 'transparency'):
                    if img.info.get(key) is not None:
                        params[key] = img.info[key]
                exif = upright.getexif()  # orientation tag already removed
                if len(exif):
                    params['exif'] = exif.tobytes()
                if image_format == 'PNG' and getattr(img, 'text', None):
                    pnginfo = PngInfo()
                    for key, value in img.text.items():
                        pnginfo.add_text(key, value)
                    params['pnginfo'] = pnginfo
                if image_format == 'TIFF' and img.info.get('compression'):
                    params['compression'] = img.info['compression']
                if image_format == 'WEBP':
                    params.update(lossless=True, exact=True)

            tmp_path = image_path.with_name(image_path.name + '.tmp')
            transformed.save(tmp_path, format=image_format, **params)
            os.replace(tmp_path, image_path)

            logger.info(f"Transformed {image_path.name} losslessly ({image_format})")
            return True

        except Exception as e:
            logger.error(f"Error transforming {image_path}: {e}")
            Path(str(image_path) + '.tmp').unlink(missing_ok=True)
            return False

    @staticmethod
    def transform_derivative(image_path: Path, op: Image.Transpose) -> bool:
        """Rotate/flip a generated thumb/web version by re-encoding its pixels"""
        try:
            with Image.open(image_path) as img:
                # The derivative's real format (TIFF/HEIC/RAW derivatives are JPEG despite their name)
                image_format = img.format
                transformed = ImageOps.exif_transpose(img).transpose(op)
            transformed.save(image_path, format=image_format, quality=90)
            return True

        except Exception as e:
            logger.error(f"Error transforming {image_path}: {e}")
            return False
