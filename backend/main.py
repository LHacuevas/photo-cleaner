"""
Photo Cleaner - Backend API
Main FastAPI application
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
import uvicorn
import logging

import config
from api import photos, folders, metadata, similar
from database import init_db, engine
from middleware import (
    global_exception_handler,
    validation_exception_handler,
    LoggingMiddleware,
)
from utils.image_processing import ImageProcessor

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bring the database schema up to date before serving requests"""
    logger.info("Starting Photo Cleaner Backend...")
    init_db()
    logger.info("Database initialized")
    yield


# FastAPI App
app = FastAPI(
    title="Photo Cleaner API",
    description="Backend API for photo management and organization",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(LoggingMiddleware)

# CORS - Allow the local frontend to connect (any port unless PHOTO_CLEANER_CORS_ORIGINS is set)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_origin_regex=None if config.CORS_ORIGINS else config.LOCALHOST_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Include routers
app.include_router(photos.router, prefix="/api/photos", tags=["photos"])
app.include_router(folders.router, prefix="/api/folders", tags=["folders"])
app.include_router(metadata.router, prefix="/api/metadata", tags=["metadata"])
app.include_router(similar.router, prefix="/api/similar", tags=["similar"])


@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "app": "Photo Cleaner API",
        "version": "1.0.0"
    }


@app.get("/api/health")
def health_check():
    """Detailed health check: database reachable and FFmpeg runnable"""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_ok = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        database_ok = False

    ffmpeg_ok = ImageProcessor.check_ffmpeg()

    return {
        "status": "healthy" if database_ok and ffmpeg_ok else "degraded",
        "database": "connected" if database_ok else "unavailable",
        "ffmpeg": "available" if ffmpeg_ok else "missing"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
        log_level="info"
    )
