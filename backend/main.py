"""
Photo Cleaner - Backend API
Main FastAPI application
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import List, Optional
import uvicorn
import logging

from api import photos, folders, metadata, similar
from database import init_db

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI App
app = FastAPI(
    title="Photo Cleaner API",
    description="Backend API for photo management and organization",
    version="1.0.0"
)

# CORS - Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(photos.router, prefix="/api/photos", tags=["photos"])
app.include_router(folders.router, prefix="/api/folders", tags=["folders"])
app.include_router(metadata.router, prefix="/api/metadata", tags=["metadata"])
app.include_router(similar.router, prefix="/api/similar", tags=["similar"])


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Starting Photo Cleaner Backend...")
    await init_db()
    logger.info("Database initialized")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "app": "Photo Cleaner API",
        "version": "1.0.0"
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "ffmpeg": "available"  # TODO: check if ffmpeg is actually available
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
