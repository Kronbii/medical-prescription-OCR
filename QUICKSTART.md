# Quick Start Guide

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

## Usage

### CLI (Batch Processing)

```bash
# Single image
python -m cli.main test2.jpg

# Directory
python -m cli.main ./uploads/ --output ./results/

# With parallel processing
python -m cli.main ./uploads/ --parallel 10 --recursive
```

### Web API

```bash
# Start server
python run.py
# or
uvicorn app.main:app --reload

# Test with curl
curl -X POST http://localhost:8000/api/v1/process \
  -F "file=@test2.jpg"

# View API docs
# Open http://localhost:8000/docs in browser
```

## Output

Results are saved to:
- `./results/` - Individual JSON files per image
- `./results/summary.json` - Batch processing summary
- `./logs/ocr/` - Raw OCR text files
- `./logs/llm/` - Full LLM responses

## Shopify Integration

The API is ready for Shopify integration:

1. Deploy the API to a hosting service
2. Update CORS settings in `app/main.py` for your Shopify domain
3. Call the API from your Shopify app:

```javascript
const formData = new FormData();
formData.append('file', imageFile);

const response = await fetch('https://your-api.com/api/v1/process', {
  method: 'POST',
  body: formData
});

const data = await response.json();
console.log(data.prescription.medications);
```

