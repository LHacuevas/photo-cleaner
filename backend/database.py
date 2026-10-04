"""
Database models and initialization
SQLite database for storing photo metadata, hashes, and relationships
"""

from sqlalchemy import create_engine, event, inspect, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timezone
import math

from alembic import command
from alembic.config import Config

from config import BACKEND_DIR, DATABASE_URL

Base = declarative_base()


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (the format stored in the DB)"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Photo(Base):
    """Main photo model"""
    __tablename__ = "photos"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False, index=True)
    filepath = Column(String, nullable=False, unique=True)
    folder_id = Column(Integer, ForeignKey("folders.id"))
    
    # File info
    size = Column(Integer)  # bytes
    width = Column(Integer)
    height = Column(Integer)
    format = Column(String)  # JPEG, PNG, etc.
    
    # Status
    is_favorite = Column(Boolean, default=False, index=True)
    is_deleted = Column(Boolean, default=False, index=True)
    
    # Hashes for duplicate detection
    phash = Column(String, index=True)  # Perceptual hash
    dhash = Column(String, index=True)  # Difference hash
    
    # EXIF metadata
    date_taken = Column(DateTime, index=True)
    camera_make = Column(String)
    camera_model = Column(String)
    lens_model = Column(String)
    
    # Photo settings
    iso = Column(Integer)
    aperture = Column(Float)
    shutter_speed = Column(String)
    focal_length = Column(Float)
    
    # GPS
    gps_latitude = Column(Float)
    gps_longitude = Column(Float)
    gps_altitude = Column(Float)
    
    # Processing
    has_thumb = Column(Boolean, default=False)
    has_web = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    # Relationships
    folder = relationship("Folder", back_populates="photos")
    similar_groups = relationship("SimilarGroup", secondary="photo_similar_groups", back_populates="photos")


class Folder(Base):
    """Folder/project model"""
    __tablename__ = "folders"
    
    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    
    # Stats
    total_photos = Column(Integer, default=0)
    favorites_count = Column(Integer, default=0)
    deleted_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=utcnow)
    last_scanned = Column(DateTime)
    
    # Relationships
    photos = relationship("Photo", back_populates="folder")


class SimilarGroup(Base):
    """Group of similar photos (duplicates/bursts)"""
    __tablename__ = "similar_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, ForeignKey("folders.id"))
    
    # Group info
    similarity_score = Column(Float)  # Average similarity in group
    group_type = Column(String)  # 'duplicate', 'burst', 'similar'
    
    # Status
    is_reviewed = Column(Boolean, default=False)
    selected_photo_id = Column(Integer)  # The "keeper" photo
    
    created_at = Column(DateTime, default=utcnow)
    
    # Relationships
    photos = relationship("Photo", secondary="photo_similar_groups", back_populates="similar_groups")


class PhotoSimilarGroup(Base):
    """Association table for many-to-many relationship"""
    __tablename__ = "photo_similar_groups"
    
    photo_id = Column(Integer, ForeignKey("photos.id"), primary_key=True)
    group_id = Column(Integer, ForeignKey("similar_groups.id"), primary_key=True)


# Database setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, connection_record):
    # WAL lets readers (gallery) work while background tasks write; busy_timeout waits instead of failing on locks
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
    dbapi_connection.create_function("distance_km", 4, distance_km, deterministic=True)


EARTH_RADIUS_KM = 6371.0


def distance_km(lat1, lon1, lat2, lon2):
    """Great-circle (haversine) distance in km; also available in SQL as distance_km()"""
    if None in (lat1, lon1, lat2, lon2):
        return None
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


SessionLocal = sessionmaker(autoflush=False, bind=engine)

# Revision matching the schema that existed before migrations were introduced
BASELINE_REVISION = "0001"


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def init_db():
    """Bring the database schema up to date by running Alembic migrations"""
    config = _alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        tables = inspect(connection).get_table_names()
        if "photos" in tables and "alembic_version" not in tables:
            # Database created with create_all() before migrations existed
            command.stamp(config, BASELINE_REVISION)
        command.upgrade(config, "head")


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
