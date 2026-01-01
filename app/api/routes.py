"""FastAPI routes"""
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from app.core.agent import PrescriptionAgent
from app.services.image_processor import ImageProcessor
from app.services.output_service import OutputService
from app.api.schemas import ProcessImageResponse, ProcessBatchResponse, HealthResponse
from app.core.config import Config

router = APIRouter()
agent = PrescriptionAgent()

# Load endpoint paths from config
_health_endpoint = Config.get("api", "endpoints", "health", default="/health")
_process_endpoint = Config.get("api", "endpoints", "process", default="/api/v1/process")
_process_batch_endpoint = Config.get("api", "endpoints", "process_batch", default="/api/v1/process-batch")


@router.get(_health_endpoint, response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status=Config.get("api", "health_status", default="ok"),
        model=Config.GEMINI_MODEL
    )


@router.post(_process_endpoint, response_model=ProcessImageResponse)
async def process_image(file: UploadFile = File(...)):
    """
    Process a single prescription image
    
    Args:
        file: Image file to process
        
    Returns:
        Processed prescription data
    """
    # Validate file type
    Config._ensure_initialized()
    if not ImageProcessor.is_image_file(Path(file.filename or "")):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Supported: {', '.join(Config.SUPPORTED_FORMATS)}"
            )
    
    # Save uploaded file temporarily
    temp_dir = Path(Config.get("directories", "temp", default="/tmp/prescription-ocr"))
    temp_dir.mkdir(exist_ok=True)
    temp_path = temp_dir / file.filename
    
    try:
        # Save uploaded file
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Validate image
        is_valid, error = ImageProcessor.validate_image(temp_path)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)
        
        # Process image
        result = agent.process_image(temp_path, file.filename)
        
        # Save results and summary
        OutputService.save_result(result, image_name=file.filename)
        OutputService.save_image_summary(result, image_name=file.filename)
        
        # Save OCR text to logs if successful
        if result.success and result.prescription:
            OutputService.save_ocr_text(result.prescription)
        
        return ProcessImageResponse(
            success=result.success,
            prescription=result.prescription,
            error=result.error,
            processing_time=result.processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()


@router.post(_process_batch_endpoint, response_model=ProcessBatchResponse)
async def process_batch(files: List[UploadFile] = File(...)):
    """
    Process multiple prescription images
    
    Args:
        files: List of image files to process
        
    Returns:
        Batch processing results
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    temp_dir = Path(Config.get("directories", "temp", default="/tmp/prescription-ocr"))
    temp_dir.mkdir(exist_ok=True)
    
    results = []
    temp_files = []
    
    try:
        # Process each file
        for file in files:
            if not ImageProcessor.is_image_file(Path(file.filename or "")):
                results.append(ProcessImageResponse(
                    success=False,
                    error=f"Invalid file type: {file.filename}"
                ))
                continue
            
            temp_path = temp_dir / file.filename
            temp_files.append(temp_path)
            
            try:
                # Save uploaded file
                with open(temp_path, "wb") as f:
                    content = await file.read()
                    f.write(content)
                
                # Validate and process
                is_valid, error = ImageProcessor.validate_image(temp_path)
                if not is_valid:
                    results.append(ProcessImageResponse(
                        success=False,
                        error=error
                    ))
                    continue
                
                result = agent.process_image(temp_path, file.filename)
                
                # Save results and summary
                OutputService.save_result(result, image_name=file.filename)
                OutputService.save_image_summary(result, image_name=file.filename)
                
                # Save OCR text if successful
                if result.success and result.prescription:
                    OutputService.save_ocr_text(result.prescription)
                
                results.append(ProcessImageResponse(
                    success=result.success,
                    prescription=result.prescription,
                    error=result.error,
                    processing_time=result.processing_time
                ))
                
            except Exception as e:
                results.append(ProcessImageResponse(
                    success=False,
                    error=f"Processing failed: {str(e)}"
                ))
        
        # Save summary
        summary_path = None
        if results:
            # Convert to ProcessingResult for summary
            from app.types.prescription import ProcessingResult
            processing_results = [
                ProcessingResult(
                    success=r.success,
                    prescription=r.prescription,
                    error=r.error,
                    processing_time=r.processing_time
                )
                for r in results
            ]
            summary_path_obj = OutputService.save_batch_summary(processing_results)
            summary_path = str(summary_path_obj)
        
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        return ProcessBatchResponse(
            total=len(results),
            successful=successful,
            failed=failed,
            results=results,
            summary_path=summary_path
        )
        
    finally:
        # Clean up temp files
        for temp_file in temp_files:
            if temp_file.exists():
                temp_file.unlink()

