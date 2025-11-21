import fs from 'fs/promises';
import path from 'path';
import { OpenAI } from 'openai';
import { Medication } from '../types/PrescriptionTypes';

const SYSTEM_PROMPT = [
  'You are a medical prescription parser working directly from an image.',
  'Input prescriptions may mix Arabic and English; medication names can be in either language with directions in the other.',
  'Transcribe the text (fix split Arabic letters) and extract medications even if handwriting is messy or abbreviations are used.',
  'Prefer the canonical drug/brand name in English when recognizable; otherwise keep the exact text.',
  'Do not drop medications because of language mix—combine Arabic and English clues for the same line item.',
  'Return JSON that matches the provided schema (ocr_text plus medications array). No explanations.',
].join(' ');

const medicationSchema = {
  type: 'object',
  properties: {
    ocr_text: { type: 'string' },
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
  required: ['ocr_text', 'medications'],
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
    this.model = model || process.env.OPENAI_MODEL || 'gpt-4o';
  }

  async parsePrescriptionFromImage(
    filePath: string,
    displayName?: string
  ): Promise<{ ocrText: string; medications: Medication[] }> {
    try {
      const imageUrl = await this.readImageAsDataUrl(filePath);
      const userText = this.buildUserInstruction(displayName);

      const completion = await this.client.chat.completions.create({
        model: this.model,
        temperature: 0,
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          {
            role: 'user',
            content: [
              { type: 'text', text: userText },
              { type: 'image_url', image_url: { url: imageUrl } },
            ],
          },
        ],
        response_format: {
          type: 'json_schema',
          json_schema: { name: 'image_medication_schema', schema: medicationSchema },
        },
      });

      const content = completion.choices[0]?.message?.content;
      if (!content) {
        throw new Error('LLM returned empty content.');
      }

      const parsed = JSON.parse(content);
      const rawMedications: unknown = parsed?.medications ?? [];

      if (!Array.isArray(rawMedications)) {
        throw new Error('LLM response is not a medication array.');
      }

      return {
        ocrText: typeof parsed?.ocr_text === 'string' ? parsed.ocr_text : '',
        medications: rawMedications.map(this.normalizeMedication),
      };
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Unknown LLM error.';
      throw new Error(`LLM parsing failed: ${message}`);
    }
  }

  private buildUserInstruction(displayName?: string): string {
    const fileLabel = displayName ? `File: ${displayName}` : 'Prescription image attached.';
    return [
      fileLabel,
      'Transcribe all text (Arabic + English) into ocr_text.',
      'Then extract medications with fields: drug_name, strength, form, frequency, duration, instructions, confidence (0-1).',
      'Return JSON only.',
    ].join(' ');
  }

  private async readImageAsDataUrl(filePath: string): Promise<string> {
    const buffer = await fs.readFile(filePath);
    const mime = this.guessMimeType(filePath);
    return `data:${mime};base64,${buffer.toString('base64')}`;
  }

  private guessMimeType(filePath: string): string {
    const ext = path.extname(filePath).toLowerCase();
    if (ext === '.png') return 'image/png';
    if (ext === '.webp') return 'image/webp';
    if (ext === '.jpeg' || ext === '.jpg') return 'image/jpeg';
    return 'image/jpeg';
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
