"""Gemini 3 Pro Preview service for prescription parsing"""
import json
from pathlib import Path
from typing import Dict, Any, Union
import google.generativeai as genai
from PIL import Image

from app.core.config import Config
from app.types.prescription import ParsedPrescription
from app.services.image_processor import ImageProcessor


class GeminiService:
    """Service for interacting with Gemini API"""
    
    def __init__(self, api_key: str = None, model: str = None, system_prompt: str = None, use_optimized_prompts: bool = None):
        """Initialize Gemini service"""
        api_key = api_key or Config.GEMINI_API_KEY
        model = model or Config.GEMINI_MODEL
        
        # Check if we should use optimized prompts
        if use_optimized_prompts is None:
            use_optimized_prompts = Config.get("optimization", "use_optimized_prompts", default=False)
        self.use_optimized_prompts = use_optimized_prompts
        
        # Load prompts from config file
        # Priority: 1. Provided parameter, 2. Environment variable, 3. Config file
        if system_prompt:
            self.system_prompt = system_prompt
        else:
            prompts_config = Config.load_prompts_config()
            if self.use_optimized_prompts and prompts_config.get("system_prompt_optimized"):
                self.system_prompt = prompts_config["system_prompt_optimized"]
            else:
                self.system_prompt = Config.get_system_prompt()
            
            if not self.system_prompt:
                raise ValueError(
                    "System prompt not found. Set GEMINI_SYSTEM_PROMPT in .env or "
                    f"configure it in {Config.PROMPTS_CONFIG_PATH}"
                )
        
        # Load user prompt template from config
        prompts_config = Config.load_prompts_config()
        if self.use_optimized_prompts and prompts_config.get("user_prompt_template_optimized"):
            self.user_prompt_template = prompts_config["user_prompt_template_optimized"]
        else:
            self.user_prompt_template = Config.get_user_prompt_template()
        
        if not self.user_prompt_template:
            raise ValueError(
                f"User prompt template not found in {Config.PROMPTS_CONFIG_PATH}"
            )
        
        # Image optimization settings
        self.optimize_images = Config.get("optimization", "optimize_images", default=True)
        self.max_image_width = Config.get("optimization", "max_image_width", default=2048)
        self.max_image_height = Config.get("optimization", "max_image_height", default=2048)
        self.image_quality = Config.get("optimization", "image_quality", default=85)
        
        if not api_key:
            raise ValueError("Gemini API key is required")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        self.model_name = model
    
    def parse_prescription_from_image(
        self, 
        image_path: Union[Path, str],
        display_name: str = None
    ) -> ParsedPrescription:
        """
        Parse prescription from image using Gemini
        
        Args:
            image_path: Path to the image file
            display_name: Optional display name for the file
            
        Returns:
            ParsedPrescription object with OCR text and medications
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        # Load and optimize image
        try:
            if self.optimize_images:
                # Use optimized image
                img = ImageProcessor.optimize_image(
                    image_path,
                    max_width=self.max_image_width,
                    max_height=self.max_image_height,
                    quality=self.image_quality
                )
            else:
                # Use original image
                img = Image.open(image_path)
                img.verify()  # Verify it's a valid image
                img = Image.open(image_path)  # Reopen after verify
        except Exception as e:
            raise ValueError(f"Invalid image file: {e}")
        
        # Build user prompt
        user_prompt = self._build_user_prompt(display_name or image_path.name)
        
        # Prepare content for Gemini (image + text)
        full_prompt = f"{self.system_prompt}\n\n{user_prompt}"
        
        # Call Gemini API with structured output (with retry)
        max_retries = Config.get("gemini", "max_retries", default=2)
        response = None
        
        for attempt in range(max_retries + 1):
            try:
                # Try structured output first (for models that support it)
                try:
                    generation_config = genai.types.GenerationConfig(
                        temperature=Config.get("gemini", "temperature", default=0),
                        response_mime_type=Config.get("gemini", "response_mime_type", default="application/json"),
                        response_schema=self._get_response_schema()
                    )
                    
                    response = self.model.generate_content(
                        [full_prompt, img],
                        generation_config=generation_config
                    )
                except (AttributeError, TypeError):
                    # Fallback for models that don't support structured output
                    # Request JSON in the prompt instead
                    json_fallback = Config.get("gemini", "json_fallback_prompt", default="IMPORTANT: Return ONLY valid JSON.")
                    json_prompt = f"{full_prompt}\n\n{json_fallback}"
                    response = self.model.generate_content(
                        [json_prompt, img],
                        generation_config=genai.types.GenerationConfig(
                            temperature=Config.get("gemini", "temperature", default=0)
                        )
                    )
                
                # Break if we got a response
                break
                
            except Exception as e:
                if attempt < max_retries:
                    continue  # Retry
                else:
                    raise RuntimeError(f"Gemini API error after {max_retries + 1} attempts: {e}")
        
        if not response:
            raise RuntimeError("Failed to get response from Gemini API")
        
        # Parse response - handle both structured and text responses
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Try to parse JSON with better error handling
        try:
            result = self._parse_json_response(response_text, display_name or image_path.name)
            
            # Normalize and validate
            return self._normalize_response(result, display_name or image_path.name)
        except json.JSONDecodeError as e:
            # Save the raw response for debugging
            self._save_debug_response(response_text, display_name or image_path.name, str(e))
            raise ValueError(f"Invalid JSON response from Gemini: {e}")
    
    def _parse_json_response(self, response_text: str, source_file: str) -> Dict[str, Any]:
        """Parse JSON response with error recovery"""
        import re
        
        # First, try direct parsing
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from the response (in case there's extra text)
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Try to fix common JSON issues
        fixed_text = self._fix_json_issues(response_text)
        try:
            return json.loads(fixed_text)
        except json.JSONDecodeError as e:
            # If all else fails, raise with the original error
            raise json.JSONDecodeError(
                f"Could not parse JSON even after repair attempts. Original error: {e.msg}",
                e.doc,
                e.pos
            )
    
    def _fix_json_issues(self, text: str) -> str:
        """Try to fix common JSON issues"""
        import re
        
        # Fix unescaped quotes in strings (basic attempt)
        # This is a simple heuristic - may not catch all cases
        fixed = text
        
        # Try to fix unterminated strings by finding the end of the object/array
        # Find the last complete JSON structure
        brace_count = 0
        bracket_count = 0
        in_string = False
        escape_next = False
        last_valid_pos = -1
        
        for i, char in enumerate(text):
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and bracket_count == 0:
                        last_valid_pos = i
                elif char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if brace_count == 0 and bracket_count == 0:
                        last_valid_pos = i
        
        # If we found a complete structure, use it
        if last_valid_pos > 0:
            fixed = text[:last_valid_pos + 1]
        
        return fixed
    
    def _save_debug_response(self, response_text: str, source_file: str, error: str):
        """Save raw response for debugging"""
        from pathlib import Path
        from datetime import datetime
        
        debug_subdir = Config.get("directories", "debug", default="debug")
        debug_dir = Path(Config.LOG_DIR) / debug_subdir
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        truncate_limit = Config.get("limits", "string_truncation_ocr_name", default=50)
        safe_name = "".join(c for c in source_file if c.isalnum() or c in "._-")[:truncate_limit]
        debug_suffix = Config.get("files", "debug_suffix", default="_error.json")
        debug_file = debug_dir / f"{timestamp}_{safe_name}{debug_suffix}"
        
        debug_data = {
            "error": error,
            "source_file": source_file,
            "timestamp": datetime.now().isoformat(),
            "raw_response": response_text[:Config.get("limits", "debug_response_size", default=5000)]
        }
        
        try:
            json_indent = Config.get("defaults", "json_indent", default=2)
            with open(debug_file, "w", encoding="utf-8") as f:
                json.dump(debug_data, f, indent=json_indent, ensure_ascii=False)
        except Exception:
            pass  # Don't fail if we can't save debug info
    
    def _build_user_prompt(self, filename: str) -> str:
        """Build user instruction prompt from template"""
        return self.user_prompt_template.format(filename=filename)
    
    def _get_response_schema(self) -> Dict[str, Any]:
        """Get JSON schema for structured output"""
        return {
            "type": "object",
            "properties": {
                "prescription_meta": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string"},
                        "doctor_name": {"type": "string"},
                        "patient_name": {"type": "string"},
                        "patient_weight": {"type": "string"}
                    }
                },
                "medicines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "identity": {
                                "type": "object",
                                "properties": {
                                    "brand_name": {"type": "string"},
                                    "generic_name": {"type": "string"},
                                    "form": {"type": "string"},
                                    "strength": {"type": "string"}
                                },
                                "required": ["generic_name", "form", "strength"]
                            },
                            "instructions": {
                                "type": "object",
                                "properties": {
                                    "route": {"type": "string"},
                                    "dose_quantity": {"type": "string"},
                                    "frequency": {"type": "string"},
                                    "duration": {"type": "string"},
                                    "special_instructions": {"type": "string"}
                                },
                                "required": ["route", "dose_quantity", "frequency", "duration"]
                            },
                            "dispensing": {
                                "type": "object",
                                "properties": {
                                    "total_quantity": {"type": "string"},
                                    "refills": {"type": "number"},
                                    "substitution_allowed": {"type": "boolean"}
                                }
                            }
                        },
                        "required": ["identity", "instructions", "dispensing"]
                    }
                },
                "ocr_text": {"type": "string"},
                "languages_detected": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["prescription_meta", "medicines"]
        }
    
    def _normalize_response(
        self, 
        result: Dict[str, Any], 
        source_file: str
    ) -> ParsedPrescription:
        """Normalize and validate Gemini response"""
        from app.types.prescription import (
            ParsedPrescription, 
            PrescriptionMeta, 
            Medicine, 
            MedicineIdentity, 
            MedicineInstructions, 
            MedicineDispensing
        )
        
        # Extract prescription meta
        meta_data = result.get("prescription_meta", {})
        
        # Handle case where prescription_meta might be a string (malformed response)
        if isinstance(meta_data, str):
            raise ValueError(
                f"Invalid response format: prescription_meta is a string '{meta_data}' "
                f"instead of an object. This may indicate the model returned malformed JSON. "
                f"Try disabling optimized prompts or check the prompt configuration."
            )
        
        if not isinstance(meta_data, dict):
            meta_data = {}
        
        prescription_meta = PrescriptionMeta(
            date=meta_data.get("date"),
            doctor_name=meta_data.get("doctor_name"),
            patient_name=meta_data.get("patient_name"),
            patient_weight=meta_data.get("patient_weight")
        )
        
        # Extract medicines
        raw_medicines = result.get("medicines", [])
        medicines = []
        
        for med in raw_medicines:
            try:
                # Extract identity
                identity_data = med.get("identity", {})
                identity = MedicineIdentity(
                    brand_name=identity_data.get("brand_name"),
                    generic_name=identity_data.get("generic_name", ""),
                    form=identity_data.get("form", ""),
                    strength=identity_data.get("strength", "")
                )
                
                # Extract instructions
                instructions_data = med.get("instructions", {})
                instructions = MedicineInstructions(
                    route=instructions_data.get("route", Config.get("defaults", "route_default", default="Oral")),
                    dose_quantity=instructions_data.get("dose_quantity", ""),
                    frequency=instructions_data.get("frequency", ""),
                    duration=instructions_data.get("duration", ""),
                    special_instructions=instructions_data.get("special_instructions")
                )
                
                # Extract dispensing
                dispensing_data = med.get("dispensing", {})
                dispensing = MedicineDispensing(
                    total_quantity=dispensing_data.get("total_quantity"),
                    refills=int(dispensing_data.get("refills", Config.get("defaults", "refills_default", default=0))),
                    substitution_allowed=bool(dispensing_data.get("substitution_allowed", Config.get("defaults", "substitution_allowed_default", default=True)))
                )
                
                medicines.append(Medicine(
                    identity=identity,
                    instructions=instructions,
                    dispensing=dispensing
                ))
            except Exception as e:
                # Skip invalid medicines but log
                print(f"Warning: Skipping invalid medicine: {e}")
                continue
        
        # Extract other fields
        ocr_text = result.get("ocr_text")
        languages = result.get("languages_detected", [])
        
        return ParsedPrescription(
            prescription_meta=prescription_meta,
            medicines=medicines,
            ocr_text=ocr_text,
            source_file=source_file,
            languages_detected=languages
        )
    

