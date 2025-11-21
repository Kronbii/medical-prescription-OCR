# Medical Prescription OCR Backend

Express + TypeScript backend that accepts a prescription image, extracts text with Google Vision OCR, sends the text to an LLM for medication parsing, and returns structured JSON.

## Prerequisites
- Node.js 18+
- Google Cloud service account key for Vision API (`keys/google-vision.json`)
- OpenAI API key (or compatible endpoint)

## Setup
1) Install dependencies:
```bash
npm install
```
2) Copy env template and fill values:
```bash
cp .env.example .env
```
Set:
- `OPENAI_API_KEY` – your key
- `OPENAI_MODEL` – e.g., `gpt-4o-mini`
- `GOOGLE_APPLICATION_CREDENTIALS` – default `./keys/google-vision.json`
- `PORT` – optional, defaults to `4000`
- `LOG_DIR` – optional, defaults to `./logs`; OCR and LLM outputs are saved under `logs/ocr` and `logs/llm`
3) Place your Google Vision credentials JSON into `keys/google-vision.json`.

## Run
- Development (with nodemon + ts-node):
```bash
npm run dev
```
- Production build:
```bash
npm run build
npm start
```

## API
`POST /upload`  
Multipart/form-data with field `file` (image). Returns OCR text and parsed medications.

Sample `curl`:
```bash
curl -X POST http://localhost:4000/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/prescription.jpg"
```

Response shape:
```json
{
  "success": true,
  "ocr_text": "...",
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
  ]
}
```

Each successful `/upload` call also writes the raw OCR text and the parsed medications to `LOG_DIR` (`./logs` by default) under `logs/ocr/*.txt` and `logs/llm/*.json`.

Health check: `GET /health` → `{ "status": "ok" }`
