# Medical Prescription OCR - AI Agent

Python-based AI agent for extracting structured medication information from prescription images. Supports Arabic, English, and French languages. Can be used as a CLI tool or deployed as a web API (Shopify-ready).

## Features

- 🤖 **AI-Powered**: Uses Google Gemini 3 Pro Preview for accurate extraction
- 🌍 **Multilingual**: Supports Arabic, English, and French
- 📦 **Batch Processing**: Process single images or entire directories
- 🚀 **Fast**: Parallel processing with configurable workers
- 🔌 **API Ready**: FastAPI web service for Shopify integration
- 📊 **Structured Output**: JSON format with validated medication data

## Prerequisites

- Python 3.9+
- Google Gemini API key ([Get one here](https://makersuite.google.com/app/apikey))

## Installation

1. **Clone and navigate to the project:**
```bash
cd medical-prescription-OCR
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables:**
```bash
cp .env.example .env
```

Edit `.env` and set:
```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.0-flash-exp  # or gemini-3-pro-preview when available
```

## Usage

### CLI Tool (Batch Processing)

**Process a single image:**
```bash
python -m cli.main image.jpg
```

**Process a directory:**
```bash
python -m cli.main ./prescriptions/
```

**With options:**
```bash
python -m cli.main ./prescriptions/ \
  --output ./results/ \
  --parallel 5 \
  --recursive
```

**Options:**
- `--output, -o`: Output directory (default: `./results`)
- `--parallel, -p`: Number of parallel workers (default: 5)
- `--recursive, -r`: Process subdirectories recursively
- `--summary, -s`: Generate summary file (default: true)

### Web API (Shopify Integration)

**Start the server:**
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

**API Endpoints:**

1. **Health Check:**
```bash
GET /health
```

2. **Process Single Image:**
```bash
POST /api/v1/process
Content-Type: multipart/form-data

curl -X POST http://localhost:8000/api/v1/process \
  -F "file=@prescription.jpg"
```

3. **Process Multiple Images:**
```bash
POST /api/v1/process-batch
Content-Type: multipart/form-data

curl -X POST http://localhost:8000/api/v1/process-batch \
  -F "files=@image1.jpg" \
  -F "files=@image2.jpg"
```

**API Documentation:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Output Format

Each processed image generates a JSON file with the following structure:

```json
{
  "success": true,
  "processing_time": 2.34,
  "timestamp": "2025-01-21T10:30:00",
  "prescription": {
    "ocr_text": "Full transcribed text from image...",
    "medications": [
      {
        "drug_name": "Amoxicillin",
        "strength": "500 mg",
        "form": "capsule",
        "frequency": "3 times daily",
        "duration": "7 days",
        "instructions": "Take after meals",
        "confidence": 0.94
      }
    ],
    "source_file": "prescription.jpg",
    "languages_detected": ["ar", "en"]
  }
}
```

## Project Structure

```
prescription-ocr/
├── app/
│   ├── main.py              # FastAPI application
│   ├── core/
│   │   ├── agent.py         # Main AI agent
│   │   ├── gemini_service.py # Gemini API integration
│   │   └── config.py        # Configuration
│   ├── api/
│   │   ├── routes.py        # API endpoints
│   │   └── schemas.py       # API schemas
│   ├── services/
│   │   ├── image_processor.py
│   │   └── output_service.py
│   └── types/
│       └── prescription.py  # Data models
├── cli/
│   └── main.py              # CLI tool
├── requirements.txt
├── .env.example
└── README.md
```

## Configuration

Environment variables (in `.env`):

- `GEMINI_API_KEY`: Your Gemini API key (required)
- `GEMINI_MODEL`: Model to use (default: `gemini-2.0-flash-exp`)
- `GEMINI_SYSTEM_PROMPT`: Custom system prompt for Gemini (optional, uses default if not set)
- `MAX_IMAGE_SIZE_MB`: Maximum image size in MB (default: 10)
- `MAX_WORKERS`: Default parallel workers (default: 5)
- `OUTPUT_DIR`: Output directory (default: `./results`)
- `LOG_DIR`: Log directory (default: `./logs`)
- `API_HOST`: API host (default: `0.0.0.0`)
- `API_PORT`: API port (default: `8000`)

### Custom Prompts

Prompts are configured in `config/prompts.json`. You can customize:
- **`system_prompt`**: The system prompt that defines the AI's role and behavior
- **`user_prompt_template`**: Template for user prompts (use `{filename}` placeholder)

**Priority order:**
1. Parameter passed programmatically (highest priority)
2. `GEMINI_SYSTEM_PROMPT` environment variable (in `.env`)
3. `system_prompt` in `config/prompts.json` (default)

**Example `config/prompts.json`:**
```json
{
  "system_prompt": "Your custom system prompt here...",
  "user_prompt_template": "File: {filename}\n\nYour custom user prompt..."
}
```

**Note:** Both prompts should instruct the model to return valid JSON matching the schema, otherwise parsing will fail.

## Shopify Integration

This API is designed to be easily integrated with Shopify apps:

1. **Deploy the API** to a hosting service (Heroku, Railway, AWS, etc.)
2. **Add OAuth** (optional) for Shopify authentication
3. **Create Shopify app** that calls the API endpoints
4. **Use webhooks** to process images uploaded in Shopify

Example Shopify app integration:
```javascript
// In your Shopify app
const formData = new FormData();
formData.append('file', imageFile);

const response = await fetch('https://your-api.com/api/v1/process', {
  method: 'POST',
  body: formData
});

const result = await response.json();
```

## Development

**Run in development mode:**
```bash
# API
uvicorn app.main:app --reload

# CLI
python -m cli.main --help
```

## License

MIT
