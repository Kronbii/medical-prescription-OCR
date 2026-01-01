"""Output service for saving results"""
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from app.core.config import Config
from app.types.prescription import ProcessingResult, ParsedPrescription


class OutputService:
    """Service for saving processing results"""
    
    @staticmethod
    def _get_safe_image_name(source_file: Optional[str]) -> str:
        """Get safe directory name from image filename"""
        unknown_fallback = Config.get("defaults", "unknown_fallback", default="unknown")
        if not source_file:
            return unknown_fallback
        
        # Remove extension and sanitize
        name = Path(source_file).stem
        truncate_limit = Config.get("limits", "string_truncation_safe_name", default=100)
        safe_name = "".join(c for c in name if c.isalnum() or c in "._-")[:truncate_limit]
        return safe_name or unknown_fallback
    
    @staticmethod
    def save_result(
        result: ProcessingResult,
        output_dir: Path = None,
        image_name: Optional[str] = None
    ) -> Path:
        """
        Save a single processing result to JSON file in image subdirectory
        
        Args:
            result: ProcessingResult to save
            output_dir: Output directory (defaults to Config.OUTPUT_DIR)
            image_name: Optional image name (extracted from source_file if not provided)
            
        Returns:
            Path to saved file
        """
        Config._ensure_initialized()
        output_dir = output_dir or Config.OUTPUT_DIR
        
        # Get image name for subdirectory
        unknown_fallback = Config.get("defaults", "unknown_fallback", default="unknown")
        if not image_name:
            if result.prescription and result.prescription.source_file:
                image_name = result.prescription.source_file
            else:
                image_name = unknown_fallback
        
        # Create subdirectory based on image name
        safe_name = OutputService._get_safe_image_name(image_name)
        image_dir = output_dir / safe_name
        image_dir.mkdir(parents=True, exist_ok=True)
        
        # Save as results.json
        results_filename = Config.get("files", "results_filename", default="results.json")
        output_path = image_dir / results_filename
        
        # Prepare output data - simplified format with only medicine names
        if result.success and result.prescription:
            # Extract only medicine names (from generic_name field where we store them)
            medicine_names = [
                med.identity.generic_name 
                for med in result.prescription.medicines 
                if med.identity.generic_name
            ]
            # Output simplified format: just array of medicine names
            output_data = {
                "medicines": medicine_names
            }
        else:
            output_data = {
                "success": False,
                "error": result.error,
                "processing_time": result.processing_time,
                "timestamp": datetime.now().isoformat()
            }
        
        # Save to file
        json_indent = Config.get("defaults", "json_indent", default=2)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=json_indent, ensure_ascii=False)
        
        return output_path
    
    @staticmethod
    def save_image_summary(
        result: ProcessingResult,
        output_dir: Path = None,
        image_name: Optional[str] = None
    ) -> Path:
        """
        Save summary for a single image in its subdirectory
        
        Args:
            result: ProcessingResult to save summary for
            output_dir: Output directory (defaults to Config.OUTPUT_DIR)
            image_name: Optional image name (extracted from source_file if not provided)
            
        Returns:
            Path to summary file
        """
        Config._ensure_initialized()
        output_dir = output_dir or Config.OUTPUT_DIR
        
        # Get image name for subdirectory
        unknown_fallback = Config.get("defaults", "unknown_fallback", default="unknown")
        if not image_name:
            if result.prescription and result.prescription.source_file:
                image_name = result.prescription.source_file
            else:
                image_name = unknown_fallback
        
        # Create subdirectory based on image name
        safe_name = OutputService._get_safe_image_name(image_name)
        image_dir = output_dir / safe_name
        image_dir.mkdir(parents=True, exist_ok=True)
        
        # Save as summary.json
        summary_filename = Config.get("files", "summary_filename", default="summary.json")
        summary_path = image_dir / summary_filename
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "success": result.success,
            "source_file": result.prescription.source_file if result.prescription else None,
            "error": result.error,
            "processing_time": result.processing_time,
            "medicines_count": len(result.prescription.medicines) if result.prescription else 0
        }
        
        json_indent = Config.get("defaults", "json_indent", default=2)
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=json_indent, ensure_ascii=False)
        
        return summary_path
    
    @staticmethod
    def save_batch_summary(
        results: List[ProcessingResult],
        output_dir: Path = None,
        summary_filename: str = None
    ) -> Path:
        """
        Save batch processing summary
        
        Args:
            results: List of processing results
            output_dir: Output directory
            summary_filename: Name of summary file
            
        Returns:
            Path to summary file
        """
        Config._ensure_initialized()
        output_dir = output_dir or Config.OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if not summary_filename:
            summary_filename = Config.get("files", "summary_filename", default="summary.json")
        summary_path = output_dir / summary_filename
        
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(results) if results else 0,
            "results": [
                {
                    "success": r.success,
                    "source_file": r.prescription.source_file if r.prescription else None,
                    "error": r.error,
                    "processing_time": r.processing_time,
                    "medicines_count": len(r.prescription.medicines) if r.prescription else 0
                }
                for r in results
            ]
        }
        
        json_indent = Config.get("defaults", "json_indent", default=2)
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=json_indent, ensure_ascii=False)
        
        return summary_path
    
    @staticmethod
    def save_ocr_text(
        prescription: ParsedPrescription,
        log_dir: Path = None
    ) -> Path:
        """
        Save OCR text to log directory
        
        Args:
            prescription: Parsed prescription
            log_dir: Log directory (defaults to Config.LOG_DIR/ocr)
            
        Returns:
            Path to saved file
        """
        Config._ensure_initialized()
        ocr_subdir = Config.get("directories", "ocr", default="ocr")
        log_dir = log_dir or (Config.LOG_DIR / ocr_subdir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unknown_fallback = Config.get("defaults", "unknown_fallback", default="unknown")
        source = prescription.source_file or unknown_fallback
        truncate_limit = Config.get("limits", "string_truncation_ocr_name", default=50)
        safe_name = "".join(c for c in source if c.isalnum() or c in "._-")[:truncate_limit]
        ocr_extension = Config.get("files", "ocr_extension", default=".txt")
        filename = f"{timestamp}_{safe_name}{ocr_extension}"
        
        output_path = log_dir / filename
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(prescription.ocr_text or "")
        
        return output_path

