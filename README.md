# Medical Prescription OCR

Extract medicine names from prescription images using Google Gemini AI. Supports Arabic, English, and French.

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Set API key
echo "GEMINI_API_KEY=your_key_here" > .env

# Process an image
python -m cli.main image.jpg
```

## Usage

### CLI

```bash
# Single image
python -m cli.main prescription.jpg

# Directory
python -m cli.main ./prescriptions/ --output ./results/

# Options
python -m cli.main ./prescriptions/ --parallel 5 --recursive
```

### API

```bash
# Start server
uvicorn app.main:app --reload

# Process image
curl -X POST http://localhost:8000/api/v1/process -F "file=@prescription.jpg"
```

API docs: `http://localhost:8000/docs`

## Output

Results saved to `results/{image_name}/results.json`:

```json
{
  "medicines": ["Paracetamol", "Ibuprofen", "Amoxicillin"]
}
```

## Medicine Database (Optional)

Add a database to check if medicines are in stock:

1. Create `data/medicines.json`:
```json
["Paracetamol", "Ibuprofen", "Amoxicillin"]
```

2. Update `config/app_config.yaml`:
```yaml
medicine_db:
  db_path: "./data/medicines.json"
  match_threshold: 0.75
```

The system uses fuzzy matching to find closest matches, even with typos.

## Configuration

Main config: `config/app_config.yaml`

Environment variables (`.env`):
- `GEMINI_API_KEY` (required)
- `GEMINI_MODEL` (default: `gemini-2.0-flash-exp`)

## Requirements

- Python 3.9+
- Google Gemini API key

## License

MIT
