"""
Photo Cleaner - Backend API
Main FastAPI application
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from pathlib import Path
from typing import List, Optional
import uvicorn
import logging

from api import photos, folders, metadata, similar
from database import init_db
from middleware import (
    global_exception_handler,
    validation_exception_handler,
    LoggingMiddleware,
    ErrorResponse
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI App
app = FastAPI(
    title="Photo Cleaner API",
    description="Backend API for photo management and organization",
    version="1.0.0"
)

# Add middleware
app.add_middleware(LoggingMiddleware)

# CORS - Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001", 
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:3004",
        "http://localhost:3005",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
        "http://127.0.0.1:3003",
    ],
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
