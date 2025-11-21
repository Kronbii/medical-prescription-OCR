# Medical Prescription OCR Backend

Express + TypeScript backend that accepts a prescription image, sends it directly to a Gemini vision model (no external OCR), and returns transcribed text plus structured medications.

## Prerequisites
- Node.js 18+
- Google AI Studio (Gemini) API key with a vision-capable model (e.g., `gemini-1.5-flash`)

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
- `GEMINI_API_KEY` – your Google AI Studio API key
- `GEMINI_MODEL` – e.g., `gemini-2.0-flash` (vision-capable; defaults to `gemini-2.0-flash`; set this to a model from your AI Studio list)
- `GEMINI_API_VERSION` – optional; defaults to `v1beta` (needed for response_schema support)
- `PORT` – optional, defaults to `4000`
- `LOG_DIR` – optional, defaults to `./logs`; OCR and LLM outputs are saved under `logs/ocr` and `logs/llm`

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
