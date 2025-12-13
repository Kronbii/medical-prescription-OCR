# Prompts Configuration

This directory contains the prompts configuration file used by the prescription OCR system.

## File: `prompts.json`

This JSON file contains all prompts used by the Gemini API:

- **`system_prompt`**: The system prompt that defines the AI's role and behavior
- **`user_prompt_template`**: Template for user prompts (use `{filename}` placeholder)

## Customization

You can edit `prompts.json` to customize the prompts. The system will automatically load changes on restart.

### Priority Order

1. **Parameter passed to `GeminiService()`** (highest priority)
2. **`GEMINI_SYSTEM_PROMPT` environment variable** (in `.env`)
3. **`system_prompt` in `prompts.json`** (default)

## Example

```json
{
  "system_prompt": "Your custom system prompt here...",
  "user_prompt_template": "File: {filename}\n\nYour custom user prompt template..."
}
```

## Notes

- The `user_prompt_template` must contain `{filename}` placeholder which will be replaced with the actual filename
- Both prompts should instruct the model to return valid JSON matching the schema
- Changes to this file require restarting the application to take effect

