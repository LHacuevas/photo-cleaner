"""
Image processing utilities
Thumbnail generation, resizing, hash computation
"""

import subprocess
import shutil
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image, ImageOps
import imagehash
import piexif
import logging
import io
import os
from datetime import datetime

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


class ImageProcessor:
    """Handles all image processing operations"""
    
    THUMB_SIZE = 300  # px
    WEB_SIZES = {
        'web': 2048,
        'archive': 1600,
        'ultra': 1200
    }
    
    @staticmethod
    def get_ffmpeg_path() -> str:
        """Get FFmpeg executable path"""
        # Try common installation paths
        possible_paths = [
            r"C:\Program Files\FFmpeg\bin\ffmpeg.exe",
            r"C:\Users\{}\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe".format(Path.home().name),
            "ffmpeg"  # Fallback to PATH
        ]
        
        for path in possible_paths:
            if Path(path).exists() or shutil.which(path):
                return path
        
        return "ffmpeg"  # Last resort
    
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
    def generate_thumbnail(input_path: Path, output_path: Path) -> bool:
        """
        Generate thumbnail using FFmpeg
        300px long side, JPEG format, 10-30 KB
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            ffmpeg_path = ImageProcessor.get_ffmpeg_path()
            
            # FFmpeg command for high-quality thumbnail
            cmd = [
                ffmpeg_path,
                '-i', str(input_path),
                '-vf', f'scale={ImageProcessor.THUMB_SIZE}:-1',
                '-q:v', '5',  # Quality (1-31, lower is better)
                '-y',  # Overwrite
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Thumbnail created: {output_path.name}")
                return True
            else:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error generating thumbnail: {e}")
            return False
    
    @staticmethod
    def generate_web_version(input_path: Path, output_path: Path, mode: str = 'web') -> bool:
        """
        Generate web-optimized version using FFmpeg
        
        Modes:
        - web: 2048px, high quality (500-900 KB)
        - archive: 1600px, medium quality (300-600 KB)
        - ultra: 1200px, lower quality (150-400 KB)
        """
        try:
            size = ImageProcessor.WEB_SIZES.get(mode, 2048)
            quality = {'web': 3, 'archive': 5, 'ultra': 7}.get(mode, 3)
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            ffmpeg_path = ImageProcessor.get_ffmpeg_path()
            
            # FFmpeg command with metadata preservation
            cmd = [
                ffmpeg_path,
                '-i', str(input_path),
                '-vf', f'scale={size}:-1',
                '-q:v', str(quality),
                '-map_metadata', '0',  # Preserve EXIF
                '-y',
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Web version created: {output_path.name} ({mode})")
                return True
            else:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error generating web version: {e}")
            return False
    
    @staticmethod
    def compute_hashes(image_path: Path) -> dict:
        """
        Compute perceptual hashes for duplicate detection
        
        Returns:
            dict with phash and dhash as strings
        """
        try:
            with Image.open(image_path) as img:
                # Perceptual hash (best for finding similar images)
                phash = str(imagehash.phash(img, hash_size=8))
                
                # Difference hash (good for rotations/crops)
                dhash = str(imagehash.dhash(img, hash_size=8))
            
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
        Get basic image information
        
        Returns:
            dict with width, height, format, size
        """
        try:
            # Ensure it's a Path object
            if isinstance(image_path, str):
                image_path = Path(image_path)
            
            with Image.open(image_path) as img:
                return {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'size': image_path.stat().st_size
                }
            
        except Exception as e:
            logger.error(f"Error getting image info for {image_path}: {e}")
            return None
    
    @staticmethod
    def extract_exif(image_path: Path) -> dict:
        """
        Extract EXIF metadata from image
        
        Returns:
            dict with camera info, settings, GPS, date taken
        """
        try:
            with Image.open(image_path) as img:
                exif_bytes = img.info.get('exif')
            if not exif_bytes:
                return {}
            exif_dict = piexif.load(exif_bytes)
            
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
            
            # Photo settings
            if piexif.ExifIFD.ISOSpeedRatings in exif:
                result['iso'] = exif[piexif.ExifIFD.ISOSpeedRatings]
            
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
                    result['gps_altitude'] = alt[0] / alt[1] if isinstance(alt, tuple) else alt
            
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
    def transform_derivative(image_path: Path, op: Image.Transpose) -> bool:
        """Rotate/flip a generated thumb/web version by re-encoding its pixels"""
        try:
            with Image.open(image_path) as img:
                transformed = ImageOps.exif_transpose(img).transpose(op)
            transformed.save(image_path, quality=90)
            return True

        except Exception as e:
            logger.error(f"Error transforming {image_path}: {e}")
            return False

    @staticmethod
    def compare_hashes(hash1: str, hash2: str) -> int:
        """
        Compare two perceptual hashes
        
        Returns:
            Hamming distance (0 = identical, lower = more similar)
        """
        try:
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)
            return h1 - h2
        except:
            return 999  # Very different
