"""Extract GPS coordinates and timestamp from image EXIF data."""

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from datetime import datetime
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


def extract_exif_gps_and_time(file_bytes: bytes):
    """Extract GPS coordinates and timestamp from image EXIF data.
    
    Returns tuple (latitude, longitude, datetime) or None if extraction fails.
    """
    try:
        img = Image.open(BytesIO(file_bytes))
        exif_data = img._getexif()
        
        if not exif_data:
            logger.warning("No EXIF data found in image")
            return None
        
        # Extract GPS data
        gps_info = {}
        gps_data = None
        for tag, value in exif_data.items():
            tag_name = TAGS.get(tag, tag)
            if tag_name == "GPSInfo":
                gps_data = value
                break
        
        if not gps_data:
            logger.warning("No GPS data found in EXIF")
            return None
        
        # Parse GPS coordinates
        for key in gps_data.keys():
            name = GPSTAGS.get(key, key)
            gps_info[name] = gps_data[key]
        
        # Convert to decimal degrees
        lat = None
        lon = None
        
        if 'GPSLatitude' in gps_info and 'GPSLatitudeRef' in gps_info:
            lat_data = gps_info['GPSLatitude']
            lat_ref = gps_info['GPSLatitudeRef']
            lat = _convert_to_degrees(lat_data)
            if lat_ref == 'S':
                lat = -lat
        
        if 'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
            lon_data = gps_info['GPSLongitude']
            lon_ref = gps_info['GPSLongitudeRef']
            lon = _convert_to_degrees(lon_data)
            if lon_ref == 'W':
                lon = -lon
        
        if lat is None or lon is None:
            logger.warning("Could not extract GPS coordinates from EXIF")
            return None
        
        # Extract timestamp
        timestamp = None
        datetime_str = exif_data.get(36867) or exif_data.get(306)  # DateTimeOriginal or DateTime
        
        if datetime_str:
            try:
                timestamp = datetime.strptime(datetime_str, '%Y:%m:%d %H:%M:%S')
            except Exception as e:
                logger.warning(f"Could not parse EXIF datetime: {e}")
                timestamp = None
        
        if timestamp is None:
            logger.warning("No timestamp found in EXIF")
            return None
        
        return (lat, lon, timestamp)
        
    except Exception as e:
        logger.exception(f"Error extracting EXIF data: {e}")
        return None


def _convert_to_degrees(value):
    """Convert GPS coordinates to degrees in float format."""
    d = float(value[0])
    m = float(value[1])
    s = float(value[2])
    return d + (m / 60.0) + (s / 3600.0)
