"""Image processing and validation utilities"""
from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image
import io

from app.core.config import Config


class ImageProcessor:
    """Utilities for processing and validating images"""
    
    @staticmethod
    def optimize_image(
        image_path: Path,
        max_width: int = 2048,
        max_height: int = 2048,
        quality: int = 85,
        format: str = "JPEG"
    ) -> Image.Image:
        """
        Optimize image by resizing and compressing for faster API processing
        
        Args:
            image_path: Path to image file
            max_width: Maximum width in pixels (default 2048)
            max_height: Maximum height in pixels (default 2048)
            quality: JPEG quality 1-100 (default 85, lower = smaller file)
            format: Output format (JPEG, PNG, WEBP)
            
        Returns:
            Optimized PIL Image object
        """
        img = Image.open(image_path)
        
        # Convert RGBA to RGB if needed (for JPEG)
        if format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
            # Create white background
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = background
        elif img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        
        # Resize if image is too large
        width, height = img.size
        if width > max_width or height > max_height:
            # Calculate new dimensions maintaining aspect ratio
            ratio = min(max_width / width, max_height / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return img
    
    @staticmethod
    def get_optimized_image_bytes(
        image_path: Path,
        max_width: int = 2048,
        max_height: int = 2048,
        quality: int = 85,
        format: str = "JPEG"
    ) -> bytes:
        """
        Get optimized image as bytes for API transmission
        
        Args:
            image_path: Path to image file
            max_width: Maximum width in pixels
            max_height: Maximum height in pixels
            quality: JPEG quality 1-100
            format: Output format (JPEG, PNG, WEBP)
            
        Returns:
            Image bytes
        """
        img = ImageProcessor.optimize_image(
            image_path, max_width, max_height, quality, format
        )
        
        buffer = io.BytesIO()
        save_kwargs = {"format": format}
        if format == "JPEG":
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
        elif format == "PNG":
            save_kwargs["optimize"] = True
        
        img.save(buffer, **save_kwargs)
        return buffer.getvalue()
    
    @staticmethod
    def validate_image(image_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Validate if file is a valid image
        
        Returns:
            (is_valid, error_message)
        """
        if not image_path.exists():
            return False, f"File not found: {image_path}"
        
        # Check extension
        if image_path.suffix.lower() not in Config.SUPPORTED_FORMATS:
            return False, f"Unsupported format. Supported: {', '.join(Config.SUPPORTED_FORMATS)}"
        
        # Check file size
        bytes_to_mb = Config.get("conversion", "bytes_to_mb", default=1048576)
        file_size_mb = image_path.stat().st_size / bytes_to_mb
        if file_size_mb > Config.MAX_IMAGE_SIZE_MB:
            return False, f"File too large: {file_size_mb:.2f}MB (max: {Config.MAX_IMAGE_SIZE_MB}MB)"
        
        # Try to open and verify image
        try:
            with Image.open(image_path) as img:
                img.verify()
            return True, None
        except Exception as e:
            return False, f"Invalid image file: {e}"
    
    @staticmethod
    def find_images(directory: Path, recursive: bool = False) -> List[Path]:
        """
        Find all image files in a directory
        
        Args:
            directory: Directory to search
            recursive: Whether to search recursively
            
        Returns:
            List of image file paths
        """
        directory = Path(directory)
        if not directory.exists():
            return []
        
        images = []
        pattern = "**/*" if recursive else "*"
        
        for ext in Config.SUPPORTED_FORMATS:
            images.extend(directory.glob(f"{pattern}{ext}"))
            images.extend(directory.glob(f"{pattern}{ext.upper()}"))
        
        return sorted(set(images))
    
    @staticmethod
    def is_image_file(file_path: Path) -> bool:
        """Check if file is an image based on extension"""
        return file_path.suffix.lower() in Config.SUPPORTED_FORMATS

