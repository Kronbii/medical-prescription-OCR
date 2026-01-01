# Codebase Analysis: Medical Prescription OCR

## Overview

This is a Python-based AI-powered medical prescription OCR system that extracts structured medication information from prescription images. It supports Arabic, English, and French languages, uses Google Gemini 3 Pro Preview for processing, and can be deployed as both a CLI tool and a FastAPI web service.

## Architecture

### High-Level Structure

```
medical-prescription-OCR/
├── app/                    # Main application package
│   ├── main.py            # FastAPI application entry point
│   ├── core/              # Core business logic
│   │   ├── agent.py       # Main AI agent orchestrator
│   │   ├── config.py      # Configuration management
│   │   └── gemini_service.py  # Gemini API integration
│   ├── api/               # API layer
│   │   ├── routes.py      # FastAPI routes/endpoints
│   │   └── schemas.py     # Pydantic request/response models
│   ├── services/          # Service layer
│   │   ├── image_processor.py  # Image optimization & validation
│   │   └── output_service.py   # Result saving & file management
│   └── types/             # Data models
│       └── prescription.py # Pydantic prescription models
├── cli/                   # CLI tool
│   └── main.py            # Command-line interface
├── config/                # Configuration files
│   ├── app_config.yaml    # Application configuration
│   └── prompts.json       # AI prompts configuration
└── test/                  # Test prescription images (66 images)
```

## Key Components

### 1. Configuration System (`app/core/config.py`)

**Purpose**: Centralized configuration management with priority hierarchy:
1. Environment variables (`.env`) - Highest priority
2. YAML config (`config/app_config.yaml`) - Default values
3. Code defaults - Fallback

**Key Features**:
- Loads app config from YAML
- Loads prompts from JSON
- Validates required settings (e.g., `GEMINI_API_KEY`)
- Ensures directory structure exists
- Provides `get()` method for nested config access

**Configuration Categories**:
- API settings (title, version, endpoints, CORS)
- Gemini settings (retries, temperature, safety filters)
- File/directory paths and naming
- Processing limits and defaults
- Optimization settings (prompts, images)

### 2. Gemini Service (`app/core/gemini_service.py`)

**Purpose**: Handles all interactions with Google Gemini API

**Key Features**:
- Supports optimized and standard prompts
- Image optimization (resize/compress) before API calls
- Structured JSON output with schema validation
- Retry logic (configurable, default 2 retries)
- JSON parsing with error recovery
- Debug response saving for failed parses
- Safety filters disabled for medical content

**Processing Flow**:
1. Load/optimize image
2. Build prompts (system + user template)
3. Call Gemini API with structured output
4. Parse and normalize JSON response
5. Convert to `ParsedPrescription` model

**Error Handling**:
- JSON parsing failures trigger debug file creation
- Malformed responses are logged
- Validation errors are caught and reported

### 3. Prescription Agent (`app/core/agent.py`)

**Purpose**: High-level orchestrator for processing prescription images

**Responsibilities**:
- Wraps `GeminiService` with error handling
- Tracks processing time
- Returns `ProcessingResult` with success/failure status
- Handles exceptions gracefully

### 4. API Layer (`app/api/`)

#### Routes (`routes.py`)

**Endpoints**:
- `GET /health` - Health check
- `POST /api/v1/process` - Process single image
- `POST /api/v1/process-batch` - Process multiple images

**Features**:
- File upload validation
- Temporary file handling
- Result persistence via `OutputService`
- Batch processing with summary generation
- Automatic cleanup of temp files

**⚠️ BUG FOUND**: Routes reference undefined variables:
- `_health_endpoint` (line 17)
- `_process_endpoint` (line 26)
- `_process_batch_endpoint` (line 88)

These should be loaded from config:
```python
_health_endpoint = Config.get("api", "endpoints", "health", default="/health")
_process_endpoint = Config.get("api", "endpoints", "process", default="/api/v1/process")
_process_batch_endpoint = Config.get("api", "endpoints", "process_batch", default="/api/v1/process-batch")
```

#### Schemas (`schemas.py`)

Pydantic models for API responses:
- `ProcessImageResponse` - Single image processing result
- `ProcessBatchResponse` - Batch processing results with statistics
- `HealthResponse` - Health check response

### 5. Data Models (`app/types/prescription.py`)

**Pydantic Models**:

1. **MedicineIdentity**: Brand name, generic name, form, strength
2. **MedicineInstructions**: Route, dose quantity, frequency, duration, special instructions
3. **MedicineDispensing**: Total quantity, refills, substitution allowed
4. **Medicine**: Complete medicine (identity + instructions + dispensing)
5. **PrescriptionMeta**: Date, doctor name, patient name, patient weight
6. **ParsedPrescription**: Complete prescription with OCR text and languages
7. **ProcessingResult**: Processing outcome with success/failure status

**Validation**:
- Required fields enforced (e.g., `generic_name`, `form`, `strength`)
- Optional fields with defaults (e.g., `refills=0`, `substitution_allowed=True`)
- Type validation (strings, numbers, booleans)

### 6. Image Processor (`app/services/image_processor.py`)

**Purpose**: Image validation and optimization

**Features**:
- Format validation (PNG, JPG, JPEG, WEBP)
- File size validation (default max 10MB)
- Image verification (PIL validation)
- Image optimization:
  - Resize to max dimensions (default 2048x2048)
  - JPEG compression (default quality 85)
  - Format conversion (RGBA → RGB for JPEG)
- Image discovery (find images in directories)
- Recursive directory scanning support

### 7. Output Service (`app/services/output_service.py`)

**Purpose**: Manages result persistence and file organization

**File Organization**:
```
results/
  <image_name>/           # Subdirectory per image
    results.json          # Full prescription data
    summary.json          # Processing summary
results/
  summary.json            # Batch summary (all images)
logs/
  ocr/                    # OCR text files
  debug/                  # Failed parse debug files
```

**Features**:
- Creates subdirectories per image (sanitized filenames)
- Saves structured JSON results
- Generates processing summaries
- Saves OCR text separately
- Batch summary generation with statistics

### 8. CLI Tool (`cli/main.py`)

**Purpose**: Command-line interface for batch processing

**Features**:
- Single image or directory processing
- Recursive directory scanning
- Parallel processing (configurable workers, default 5)
- Progress bars (tqdm)
- Batch summary generation
- Statistics reporting

**Usage**:
```bash
python -m cli.main <input_path> [--output DIR] [--parallel N] [--recursive] [--summary]
```

## Data Flow

### CLI Flow:
```
Image File(s) 
  → CLI Main 
    → PrescriptionAgent.process_image()
      → GeminiService.parse_prescription_from_image()
        → Image Optimization (optional)
        → Gemini API Call
        → JSON Parsing & Normalization
      → ProcessingResult
    → OutputService.save_result()
    → OutputService.save_image_summary()
```

### API Flow:
```
HTTP Request (multipart/form-data)
  → FastAPI Route
    → File Upload Validation
    → Temporary File Save
    → PrescriptionAgent.process_image()
      → [Same as CLI flow]
    → OutputService.save_result()
    → JSON Response
    → Temp File Cleanup
```

## Configuration System

### Priority Order:

1. **Environment Variables** (`.env`):
   - `GEMINI_API_KEY` (required)
   - `GEMINI_MODEL` (default: `gemini-2.0-flash-exp`)
   - `GEMINI_SYSTEM_PROMPT` (optional override)
   - Processing limits, directories, etc.

2. **YAML Config** (`config/app_config.yaml`):
   - API settings
   - Gemini settings
   - File/directory names
   - Defaults and limits

3. **Prompts Config** (`config/prompts.json`):
   - System prompt
   - User prompt template
   - Optimized versions (if enabled)

### Key Configuration Options:

**Optimization**:
- `use_optimized_prompts`: Use shorter prompts (default: true)
- `optimize_images`: Resize/compress images (default: false)
- `max_image_width/height`: Max dimensions (default: 2048)
- `image_quality`: JPEG quality 1-100 (default: 85)

**Gemini**:
- `max_retries`: Retry attempts (default: 2)
- `temperature`: Model temperature (default: 0)
- `response_mime_type`: `application/json`
- Safety filters: All disabled (`BLOCK_NONE`)

**Processing**:
- `MAX_WORKERS`: Parallel workers (default: 5)
- `MAX_IMAGE_SIZE_MB`: Max file size (default: 10MB)
- Supported formats: `.png`, `.jpg`, `.jpeg`, `.webp`

## Output Format

### Success Response (`results.json`):
```json
{
  "prescription_meta": {
    "date": "2023-01-01",
    "doctor_name": "Dr. Name",
    "patient_name": "Patient Name",
    "patient_weight": "75kg"
  },
  "medicines": [
    {
      "identity": {
        "brand_name": "Brand Name",
        "generic_name": "Generic Name",
        "form": "Tablet",
        "strength": "500 mg"
      },
      "instructions": {
        "route": "Oral",
        "dose_quantity": "1 tablet",
        "frequency": "3 times daily",
        "duration": "7 days",
        "special_instructions": "Take with food"
      },
      "dispensing": {
        "total_quantity": "21 tablets",
        "refills": 0,
        "substitution_allowed": true
      }
    }
  ]
}
```

### Failure Response:
```json
{
  "success": false,
  "error": "Error message",
  "processing_time": 0.01,
  "timestamp": "2025-12-13T22:48:48.836696"
}
```

## Known Issues

### Critical Bugs:

1. **Routes.py - Undefined Variables**:
   - Lines 17, 26, 88 reference `_health_endpoint`, `_process_endpoint`, `_process_batch_endpoint`
   - These variables are not defined
   - Will cause `NameError` at runtime
   - **Fix**: Load from config before decorators

2. **Error Handling**:
   - Results show error `"'generic_name'"` (result 14)
   - Suggests validation error but error message unclear
   - May indicate missing required field handling

### Potential Improvements:

1. **Error Messages**: More descriptive error messages for validation failures
2. **Logging**: Add structured logging (currently uses print statements)
3. **Testing**: No test files found in codebase
4. **Documentation**: API documentation could include more examples
5. **Async Processing**: API routes could use async/await more consistently
6. **Validation**: Add input validation for config values
7. **Monitoring**: No metrics or monitoring hooks

## Dependencies

**Core**:
- `fastapi==0.115.0` - Web framework
- `uvicorn[standard]==0.32.0` - ASGI server
- `pydantic==2.9.2` - Data validation
- `python-dotenv==1.0.1` - Environment variables

**AI**:
- `google-generativeai==0.8.3` - Gemini API client

**Image Processing**:
- `Pillow==11.0.0` - Image manipulation

**CLI**:
- `click==8.1.7` - CLI framework
- `tqdm==4.66.5` - Progress bars

**Other**:
- `aiofiles==24.1.0` - Async file operations
- `pyyaml==6.0.2` - YAML parsing

## Testing

- **Test Images**: 66 prescription images in `test/` directory
- **Results**: 14 processed results in `results/` directory
- **Success Rate**: Need to check summary.json for statistics
- **Unit Tests**: None found
- **Integration Tests**: None found

## Deployment

### CLI Usage:
- Standalone Python script
- Requires `GEMINI_API_KEY` in environment
- Can process local files/directories

### API Deployment:
- FastAPI application
- Run with `uvicorn app.main:app`
- Ready for Shopify integration
- CORS configured (currently allows all origins)
- Health check endpoint available

## Security Considerations

1. **API Key**: Must be set via environment variable (not hardcoded)
2. **File Upload**: Validates file types and sizes
3. **CORS**: Currently allows all origins (should be restricted in production)
4. **Temporary Files**: Created in `/tmp/prescription-ocr` (should use secure temp directory)
5. **Input Validation**: File type and size validation present
6. **Error Messages**: May leak internal details (should sanitize)

## Performance

- **Parallel Processing**: Supports configurable workers (default 5)
- **Image Optimization**: Optional resize/compression before API calls
- **Prompt Optimization**: Shorter prompts reduce token usage
- **Batch Processing**: CLI processes multiple images in parallel
- **API**: Synchronous processing per request (could be improved with async)

## Multilingual Support

- Supports Arabic, English, and French
- Language detection in responses
- Handles mixed-language prescriptions
- Prompts configured for multilingual processing

---

**Analysis Date**: 2025-12-13
**Codebase Version**: Based on current state
**Python Version**: 3.9+ required

