"""Pydantic schemas for API requests/responses"""
from typing import List, Optional
from pydantic import BaseModel, Field

from app.types.prescription import ParsedPrescription


class ProcessImageResponse(BaseModel):
    """Response for single image processing"""
    success: bool
    prescription: Optional[ParsedPrescription] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None


class ProcessBatchResponse(BaseModel):
    """Response for batch processing"""
    total: int
    successful: int
    failed: int
    results: List[ProcessImageResponse]
    summary_path: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    model: str
    version: str = None
    
    def __init__(self, **data):
        from app.core.config import Config
        if "version" not in data or data["version"] is None:
            data["version"] = Config.get("api", "version", default="1.0.0")
        super().__init__(**data)

