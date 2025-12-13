"""Configuration management"""
import os
import json
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration"""
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    PROMPTS_CONFIG_PATH: Path = BASE_DIR / "config" / "prompts.json"
    APP_CONFIG_PATH: Path = BASE_DIR / "config" / "app_config.yaml"
    
    # Load app config
    _app_config: Optional[Dict[str, Any]] = None
    
    # Gemini API
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
    GEMINI_SYSTEM_PROMPT: Optional[str] = os.getenv("GEMINI_SYSTEM_PROMPT", None)
    
    # Processing settings
    MAX_IMAGE_SIZE_MB: int = int(os.getenv("MAX_IMAGE_SIZE_MB", "10"))
    SUPPORTED_FORMATS: list = [".png", ".jpg", ".jpeg", ".webp"]
    
    # Output settings
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "./results"))
    LOG_DIR: Path = Path(os.getenv("LOG_DIR", "./logs"))
    
    # Parallel processing
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "5"))
    
    # API settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    
    @classmethod
    def load_app_config(cls) -> Dict[str, Any]:
        """Load application configuration from YAML file"""
        if cls._app_config is not None:
            return cls._app_config
        
        try:
            if cls.APP_CONFIG_PATH.exists():
                with open(cls.APP_CONFIG_PATH, "r", encoding="utf-8") as f:
                    cls._app_config = yaml.safe_load(f) or {}
                    return cls._app_config
            else:
                # Return empty dict if config file doesn't exist
                return {}
        except (yaml.YAMLError, IOError) as e:
            raise ValueError(f"Failed to load app config from {cls.APP_CONFIG_PATH}: {e}")
    
    @classmethod
    def get(cls, *keys, default=None):
        """Get nested config value using dot notation
        
        Args:
            *keys: Variable number of keys to traverse nested config
            default: Default value if key not found
            
        Example:
            Config.get("api", "endpoints", "process") -> config["api"]["endpoints"]["process"]
        """
        config = cls.load_app_config()
        value = config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        return value if value is not None else default
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration"""
        if not cls.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is required. Set it in .env file or environment variable."
            )
    
    @classmethod
    def ensure_directories(cls) -> None:
        """Ensure output and log directories exist"""
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        (cls.LOG_DIR / cls.get("directories", "ocr", default="ocr")).mkdir(parents=True, exist_ok=True)
        (cls.LOG_DIR / cls.get("directories", "llm", default="llm")).mkdir(parents=True, exist_ok=True)
        (cls.LOG_DIR / cls.get("directories", "debug", default="debug")).mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def load_prompts_config(cls) -> Dict[str, Any]:
        """Load prompts configuration from JSON file"""
        try:
            if cls.PROMPTS_CONFIG_PATH.exists():
                with open(cls.PROMPTS_CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                # Return empty dict if config file doesn't exist
                return {}
        except (json.JSONDecodeError, IOError) as e:
            raise ValueError(f"Failed to load prompts config from {cls.PROMPTS_CONFIG_PATH}: {e}")
    
    @classmethod
    def get_system_prompt(cls) -> str:
        """Get system prompt from config file or environment variable"""
        # Check environment variable first (highest priority)
        if cls.GEMINI_SYSTEM_PROMPT:
            return cls.GEMINI_SYSTEM_PROMPT
        
        # Load from config file
        prompts_config = cls.load_prompts_config()
        if prompts_config.get("system_prompt"):
            return prompts_config["system_prompt"]
        
        # Fallback to empty string (shouldn't happen if config is set up correctly)
        return ""
    
    @classmethod
    def get_user_prompt_template(cls) -> str:
        """Get user prompt template from config file"""
        prompts_config = cls.load_prompts_config()
        return prompts_config.get("user_prompt_template", "")

