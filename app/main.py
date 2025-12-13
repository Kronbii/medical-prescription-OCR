"""FastAPI application main entry point"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Config
from app.api.routes import router

# Validate configuration
Config.validate()
Config.ensure_directories()

# Create FastAPI app
app = FastAPI(
    title=Config.get("api", "title", default="Medical Prescription OCR API"),
    description=Config.get("api", "description", default="AI-powered prescription image processing"),
    version=Config.get("api", "version", default="1.0.0")
)

# Add CORS middleware
cors_config = Config.load_app_config().get("api", {}).get("cors", {})
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_config.get("allow_origins", ["*"]),
    allow_credentials=cors_config.get("allow_credentials", True),
    allow_methods=cors_config.get("allow_methods", ["*"]),
    allow_headers=cors_config.get("allow_headers", ["*"]),
)

# Include routes
app.include_router(router)

@app.get("/")
async def root():
    """Root endpoint"""
    endpoints = Config.get("api", "endpoints", default={})
    return {
        "message": Config.get("api", "title", default="Medical Prescription OCR API"),
        "version": Config.get("api", "version", default="1.0.0"),
        "docs": endpoints.get("docs", "/docs"),
        "health": endpoints.get("health", "/health")
    }

