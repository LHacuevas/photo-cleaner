"""
Database models and initialization
SQLite database for storing photo metadata, hashes, and relationships
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()


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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = Column(DateTime, default=datetime.utcnow)
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
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    photos = relationship("Photo", secondary="photo_similar_groups", back_populates="similar_groups")


class PhotoSimilarGroup(Base):
    """Association table for many-to-many relationship"""
    __tablename__ = "photo_similar_groups"
    
    photo_id = Column(Integer, ForeignKey("photos.id"), primary_key=True)
    group_id = Column(Integer, ForeignKey("similar_groups.id"), primary_key=True)


# Database setup
DATABASE_URL = "sqlite:///./photo_cleaner.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


async def init_db():
    """Initialize database - create all tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
