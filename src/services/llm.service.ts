import { OpenAI } from 'openai';
import { Medication } from '../types/PrescriptionTypes';

const SYSTEM_PROMPT =
  'You are a medical prescription parser. Input is OCR text from a prescription written in Arabic and English. Extract medications into a STRICT JSON array. Each object must contain: drug_name, strength, form, frequency, duration, instructions, confidence (0-1). Return only valid JSON. No explanations.';

const medicationSchema = {
  type: 'object',
  properties: {
    medications: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          drug_name: { type: 'string' },
          strength: { type: 'string' },
          form: { type: 'string' },
          frequency: { type: 'string' },
          duration: { type: 'string' },
          instructions: { type: 'string' },
          confidence: { type: 'number' },
        },
        required: [
          'drug_name',
          'strength',
          'form',
          'frequency',
          'duration',
          'instructions',
          'confidence',
        ],
        additionalProperties: false,
      },
    },
  },
  required: ['medications'],
  additionalProperties: false,
};

export class LlmService {
  private client: OpenAI;
  private model: string;

  constructor(apiKey?: string, model?: string) {
    const key = apiKey || process.env.OPENAI_API_KEY;
    if (!key) {
      throw new Error('Missing OpenAI API key. Set OPENAI_API_KEY in .env.');
    }

    this.client = new OpenAI({ apiKey: key });
    this.model = model || process.env.OPENAI_MODEL || 'gpt-4o-mini';
  }

  async parseMedications(ocrText: string): Promise<Medication[]> {
    try {
      const completion = await this.client.chat.completions.create({
        model: this.model,
        temperature: 0,
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: ocrText },
        ],
        response_format: {
          type: 'json_schema',
          json_schema: { name: 'medication_schema', schema: medicationSchema },
        },
      });

      const content = completion.choices[0]?.message?.content;
      if (!content) {
        throw new Error('LLM returned empty content.');
      }

      const parsed = JSON.parse(content);
      const rawMedications: unknown =
        Array.isArray(parsed) && parsed.length === 0
          ? []
          : parsed.medications ?? parsed;

      if (!Array.isArray(rawMedications)) {
        throw new Error('LLM response is not a medication array.');
      }

      return rawMedications.map(this.normalizeMedication);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Unknown LLM error.';
      throw new Error(`LLM parsing failed: ${message}`);
    }
  }

  private normalizeMedication = (item: any): Medication => ({
    drug_name: item?.drug_name ?? '',
    strength: item?.strength ?? '',
    form: item?.form ?? '',
    frequency: item?.frequency ?? '',
    duration: item?.duration ?? '',
    instructions: item?.instructions ?? '',
    confidence:
      typeof item?.confidence === 'number'
        ? Math.min(Math.max(item.confidence, 0), 1)
        : 0,
  });
}
