"""Core AI agent for prescription processing"""
import time
from pathlib import Path
from typing import Optional, Union

from app.core.gemini_service import GeminiService
from app.types.prescription import ParsedPrescription, ProcessingResult


class PrescriptionAgent:
    """Main AI agent for processing prescription images"""
    
    def __init__(self, gemini_api_key: str = None, model: str = None):
        """Initialize the prescription agent"""
        self.gemini_service = GeminiService(gemini_api_key, model)
    
    def process_image(
        self,
        image_path: Union[Path, str],
        display_name: Optional[str] = None
    ) -> ProcessingResult:
        """
        Process a single prescription image
        
        Args:
            image_path: Path to the image file
            display_name: Optional display name for logging
            
        Returns:
            ProcessingResult with parsed prescription or error
        """
        start_time = time.time()
        image_path = Path(image_path)
        
        try:
            prescription = self.gemini_service.parse_prescription_from_image(
                image_path,
                display_name or image_path.name
            )
            
            processing_time = time.time() - start_time
            
            return ProcessingResult(
                success=True,
                prescription=prescription,
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)
            
            return ProcessingResult(
                success=False,
                error=error_msg,
                processing_time=processing_time
            )

