"""Gemini 3 Pro Preview service for prescription parsing"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Union, List
import google.generativeai as genai
from PIL import Image

from app.core.config import Config
from app.types.prescription import ParsedPrescription
from app.services.image_processor import ImageProcessor
from app.services.medicine_validator import MedicineValidator


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
        
        # Load prompts from config file (load once)
        prompts_config = Config.load_prompts_config()
        
        # Priority: 1. Provided parameter, 2. Environment variable, 3. Config file
        if system_prompt:
            self.system_prompt = system_prompt
        else:
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
        self.image_format = Config.get("optimization", "image_format", default="JPEG")
        
        # Medicine validation settings
        self.validate_medicine_names = Config.get("optimization", "validate_medicine_names", default=True)
        
        # Initialize medicine validator with database if configured
        db_path_str = Config.get("medicine_db", "db_path", default=None)
        match_threshold = Config.get("medicine_db", "match_threshold", default=0.75)
        
        db_path = None
        if db_path_str:
            db_path = Path(db_path_str)
            if not db_path.is_absolute():
                # Make relative to base directory
                db_path = Config.BASE_DIR / db_path
        
        self.medicine_validator = MedicineValidator(db_path=db_path, match_threshold=match_threshold)
        
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
                # Use optimized image (format from config)
                img = ImageProcessor.optimize_image(
                    image_path,
                    max_width=self.max_image_width,
                    max_height=self.max_image_height,
                    quality=self.image_quality,
                    format=self.image_format
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
        
        # Call Gemini API with prompt-based JSON (no structured output for speed)
        max_retries = Config.get("gemini", "max_retries", default=2)
        response = None
        
        # Add JSON instruction to prompt for faster processing (no schema overhead)
        json_fallback = Config.get("gemini", "json_fallback_prompt", default="Return ONLY valid JSON.")
        json_prompt = f"{full_prompt}\n\n{json_fallback}"
        
        for attempt in range(max_retries + 1):
            try:
                # Use simple generation config without structured output for speed
                # Set lower thinking_level for faster processing (less deep reasoning)
                thinking_level = Config.get("gemini", "thinking_level", default="low")
                temperature = Config.get("gemini", "temperature", default=0)
                
                # Build generation config with thinking_level for faster inference
                # thinking_level can be "low", "medium", or "high" - "low" is fastest
                # This significantly reduces inference time for simpler tasks like OCR
                try:
                    # Try to set thinking_level directly (for Gemini 3 Pro and newer models)
                    generation_config = genai.types.GenerationConfig(
                        temperature=temperature,
                        thinking_level=thinking_level
                    )
                except (TypeError, AttributeError):
                    # Fallback if thinking_level not supported in this SDK version
                    generation_config = genai.types.GenerationConfig(
                        temperature=temperature
                    )
                
                response = self.model.generate_content(
                    [json_prompt, img],
                    generation_config=generation_config
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
        # IMPORTANT: Capture raw response immediately, before any processing
        response_text = None
        try:
            response_text = response.text.strip()
        except Exception as text_error:
            raise ValueError(f"Failed to extract response text: {text_error}")
        
        # Remove markdown code blocks if present
        response_text = self._clean_markdown_response(response_text)
        
        # Try to parse JSON with better error handling
        try:
            result = self._parse_json_response(response_text, display_name or image_path.name)
            
            # Validate medicine names if enabled (post-processing validation)
            if self.validate_medicine_names:
                result = self._validate_medicine_names(result)
            
            # Normalize and validate
            try:
                return self._normalize_response(result, display_name or image_path.name)
            except Exception as normalize_error:
                self._save_debug_response(response_text, display_name or image_path.name, f"Normalization error: {str(normalize_error)}")
                raise ValueError(f"Failed to normalize response: {normalize_error}")
        except (json.JSONDecodeError, KeyError, ValueError, Exception) as e:
            # Save the raw response for debugging (silently)
            self._save_debug_response(response_text, display_name or image_path.name, str(e))
            raise ValueError(f"Invalid JSON response from Gemini: {e}")
    
    def _parse_json_response(self, response_text: str, source_file: str) -> Dict[str, Any]:
        """Parse JSON response with error recovery"""
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
        Config._ensure_initialized()
        debug_subdir = Config.get("directories", "debug", default="debug")
        debug_dir = Path(Config.LOG_DIR) / debug_subdir
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        truncate_limit = Config.get("limits", "string_truncation_ocr_name", default=50)
        safe_name = "".join(c for c in source_file if c.isalnum() or c in "._-")[:truncate_limit]
        debug_suffix = Config.get("files", "debug_suffix", default="_error.json")
        debug_file = debug_dir / f"{timestamp}_{safe_name}{debug_suffix}"
        
        # Also save full response to a separate text file for easier viewing
        debug_txt_file = debug_dir / f"{timestamp}_{safe_name}_raw.txt"
        
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
            
            # Also save full raw response to text file
            with open(debug_txt_file, "w", encoding="utf-8") as f:
                f.write("="*80 + "\n")
                f.write(f"RAW GEMINI RESPONSE\n")
                f.write(f"Source: {source_file}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Error: {error}\n")
                f.write("="*80 + "\n\n")
                f.write(response_text)
            
            # Debug files saved silently
        except Exception:
            pass  # Don't fail if we can't save debug info
    
    def _clean_markdown_response(self, text: str) -> str:
        """Remove markdown code blocks from response text"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
    
    def _build_user_prompt(self, filename: str) -> str:
        """Build user instruction prompt from template"""
        return self.user_prompt_template.format(filename=filename)
    
    def _validate_medicine_names(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and correct medicine names using database or AI
        
        Priority:
        1. If database is available, use fuzzy matching against database
        2. If no database or no match found, fall back to AI validation
        
        For each medicine name:
        1. Check if it's in stock (database) or valid (AI)
        2. If valid/in stock, keep the matched/corrected name
        3. If not in stock (below threshold), mark as "not in stock"
        4. If invalid and no match, use AI to find closest valid name
        
        Args:
            result: Parsed result with medicines array
            
        Returns:
            Result with validated medicine names (only in-stock/valid medicines)
        """
        medicines = result.get("medicines", [])
        if not medicines:
            return result
        
        validated_medicines = []
        not_in_stock = []  # Track medicines not in stock
        
        # First, try database validation if available
        if self.medicine_validator.db_loaded:
            for med in medicines:
                validation_result = self.medicine_validator.validate_medicine(med)
                
                if validation_result['status'] == 'in_stock':
                    # Use the matched name from database (in stock)
                    validated_medicines.append(validation_result['matched_name'])
                elif validation_result['status'] == 'not_in_stock':
                    # Below threshold - not in stock, don't include
                    not_in_stock.append({
                        'detected': med,
                        'best_match_score': validation_result['similarity_score']
                    })
                # If status is 'unknown', shouldn't happen if DB is loaded, but handle it
                elif validation_result['status'] == 'unknown':
                    # DB loaded but validation failed - fall back to AI
                    ai_validated = self._validate_with_ai([med])
                    if ai_validated:
                        validated_medicines.extend(ai_validated)
        else:
            # No database available - use AI validation for all
            ai_validated = self._validate_with_ai(medicines)
            validated_medicines.extend(ai_validated)
        
        # Update result with validated medicines (only in-stock/valid medicines)
        result["medicines"] = validated_medicines
        
        # Store not_in_stock information for reference
        if not_in_stock:
            result["not_in_stock"] = not_in_stock
        
        return result
    
    def _validate_with_ai(self, medicines: List[str]) -> List[str]:
        """
        Validate medicine names using AI (fallback when no database)
        
        Args:
            medicines: List of medicine names to validate
            
        Returns:
            List of validated medicine names
        """
        if not medicines:
            return []
        
        # Build validation prompt
        medicines_list = "\n".join([f"- {med}" for med in medicines])
        validation_prompt = f"""Validate and correct these medicine names extracted from a prescription.

For each medicine name:
1. Check if it's a valid, real medicine name (generic or brand name)
2. If valid, keep the exact name
3. If invalid/typo, find the closest valid medicine name match based on:
   - Name similarity (closest spelling match)
   - Context (consider other medicines in the list)
   - Common medicine names

Medicine names to validate:
{medicines_list}

Return JSON with a 'medicines' key containing an array of VALIDATED medicine name strings.
Only return validated, correct medicine names. If a name is clearly invalid and no close match exists, omit it.
Return valid JSON only."""
        
        try:
            # Call Gemini for validation
            max_retries = Config.get("gemini", "max_retries", default=2)
            temperature = Config.get("gemini", "temperature", default=0)
            
            for attempt in range(max_retries + 1):
                try:
                    generation_config = genai.types.GenerationConfig(temperature=temperature)
                    validation_response = self.model.generate_content(
                        validation_prompt,
                        generation_config=generation_config
                    )
                    
                    validation_text = self._clean_markdown_response(validation_response.text)
                    
                    # Parse validated result
                    validated_result = json.loads(validation_text)
                    validated_medicines = validated_result.get("medicines", [])
                    
                    return validated_medicines
                    
                except Exception as e:
                    if attempt < max_retries:
                        continue
                    # If validation fails, return original medicines
                    print(f"Warning: AI medicine validation failed, using original names: {e}", file=sys.stderr)
                    return medicines
        except Exception as e:
            # If validation fails completely, return original medicines
            print(f"Warning: AI medicine validation error, using original names: {e}", file=sys.stderr)
            return medicines
    
    def _normalize_response(
        self, 
        result: Dict[str, Any], 
        source_file: str
    ) -> ParsedPrescription:
        """Normalize and validate Gemini response - simplified to extract only medicine names"""
        from app.types.prescription import (
            ParsedPrescription, 
            PrescriptionMeta, 
            Medicine, 
            MedicineIdentity, 
            MedicineInstructions, 
            MedicineDispensing
        )
        
        # Extract medicines - now just an array of strings
        raw_medicines = result.get("medicines", [])
        medicines = []
        
        # Handle both string array and old format for backward compatibility
        for med in raw_medicines:
            try:
                if isinstance(med, str):
                    # New simplified format: just a string (medicine name)
                    medicine_name = med.strip()
                    if medicine_name:
                        # Create minimal Medicine object with just the name
                        identity = MedicineIdentity(
                            brand_name=None,
                            generic_name=medicine_name,  # Store name in generic_name field
                            form="",  # Empty for name-only extraction
                            strength=""  # Empty for name-only extraction
                        )
                        # Create minimal instructions and dispensing
                        instructions = MedicineInstructions(
                            route="",
                            dose_quantity="",
                            frequency="",
                            duration="",
                            special_instructions=None
                        )
                        dispensing = MedicineDispensing(
                            total_quantity=None,
                            refills=0,
                            substitution_allowed=True
                        )
                        medicines.append(Medicine(
                            identity=identity,
                            instructions=instructions,
                            dispensing=dispensing
                        ))
                elif isinstance(med, dict):
                    # Old format support (for backward compatibility)
                    identity_data = med.get("identity", {})
                    if isinstance(identity_data, dict):
                        identity = MedicineIdentity(
                            brand_name=identity_data.get("brand_name"),
                            generic_name=identity_data.get("generic_name", ""),
                            form=identity_data.get("form", ""),
                            strength=identity_data.get("strength", "")
                        )
                        instructions_data = med.get("instructions", {})
                        instructions = MedicineInstructions(
                            route=instructions_data.get("route", Config.get("defaults", "route_default", default="Oral")),
                            dose_quantity=instructions_data.get("dose_quantity", ""),
                            frequency=instructions_data.get("frequency", ""),
                            duration=instructions_data.get("duration", ""),
                            special_instructions=instructions_data.get("special_instructions")
                        )
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
        
        # Create minimal prescription meta (empty for name-only extraction)
        prescription_meta = PrescriptionMeta(
            date=None,
            doctor_name=None,
            patient_name=None,
            patient_weight=None
        )
        
        return ParsedPrescription(
            prescription_meta=prescription_meta,
            medicines=medicines,
            ocr_text=None,  # Not extracting OCR text for speed
            source_file=source_file,
            languages_detected=[]  # Not detecting languages for speed
        )
    

