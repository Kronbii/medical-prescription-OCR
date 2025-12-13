# Configuration Guide

All configuration is now externalized to YAML and JSON files. No hardcoded values remain in the code.

## Configuration Files

### 1. `config/app_config.yaml`
Main application configuration file containing:
- API settings (title, version, endpoints, CORS)
- Gemini settings (retries, temperature, prompts)
- File names and directory paths
- Limits and defaults
- Conversion constants

### 2. `config/prompts.json`
Prompts configuration:
- `system_prompt`: System prompt for Gemini
- `user_prompt_template`: User prompt template (use `{filename}` placeholder)

### 3. `.env`
Environment variables (highest priority):
- `GEMINI_API_KEY`: Required
- `GEMINI_MODEL`: Model name
- `GEMINI_SYSTEM_PROMPT`: Override system prompt (optional)
- Other settings (see README)

## Configuration Priority

1. **Environment variables** (`.env`) - Highest priority
2. **YAML config file** (`config/app_config.yaml`) - Default values
3. **Code defaults** - Fallback if config missing

## System Prompts

System prompts are **NOT hardcoded**. They are loaded from:
1. `GEMINI_SYSTEM_PROMPT` environment variable (if set)
2. `config/prompts.json` → `system_prompt` field
3. Error if neither is found

User prompt template is loaded from:
- `config/prompts.json` → `user_prompt_template` field

## All Configurable Values

### API Configuration
- Title, description, version
- Endpoint paths (`/api/v1/process`, etc.)
- CORS settings
- Health check status

### Gemini Configuration
- Max retries
- Temperature
- Response MIME type
- JSON fallback prompt

### File/Directory Names
- `results.json`, `summary.json`
- `debug`, `ocr`, `llm` subdirectories
- Temp directory path
- File extensions

### Limits
- String truncation limits
- Debug response size
- JSON indentation

### Defaults
- Unknown fallback value
- Default route ("Oral")
- Default refills (0)
- Default substitution_allowed (true)

## Customization

Edit `config/app_config.yaml` to customize any setting. Changes take effect on application restart.

