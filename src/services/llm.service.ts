import fs from 'fs/promises';
import path from 'path';
import {
  GenerativeModel,
  GoogleGenerativeAI,
  Schema,
  SchemaType,
} from '@google/generative-ai';
import { Medication } from '../types/PrescriptionTypes';

const SYSTEM_PROMPT = [
  'You are a medical prescription parser working directly from an image.',
  'Input prescriptions may mix Arabic and English; medication names can be in either language with directions in the other.',
  'Transcribe the text (fix split Arabic letters) and extract medications even if handwriting is messy or abbreviations are used.',
  'Prefer the canonical drug/brand name in English when recognizable; otherwise keep the exact text.',
  'Do not drop medications because of language mix—combine Arabic and English clues for the same line item.',
  'Return JSON that matches the provided schema (ocr_text plus medications array). No explanations.',
].join(' ');

const medicationSchema: Schema = {
  type: SchemaType.OBJECT,
  properties: {
    ocr_text: { type: SchemaType.STRING },
    medications: {
      type: SchemaType.ARRAY,
      items: {
        type: SchemaType.OBJECT,
        properties: {
          drug_name: { type: SchemaType.STRING },
          strength: { type: SchemaType.STRING },
          form: { type: SchemaType.STRING },
          frequency: { type: SchemaType.STRING },
          duration: { type: SchemaType.STRING },
          instructions: { type: SchemaType.STRING },
          confidence: { type: SchemaType.NUMBER },
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
      },
    },
  },
  required: ['ocr_text', 'medications'],
};

export class LlmService {
  private client: GoogleGenerativeAI;
  private modelName: string;
  private apiVersion: string;
  private model: GenerativeModel;

  constructor(apiKey?: string, model?: string) {
    const key = apiKey || process.env.GEMINI_API_KEY;
    if (!key) {
      throw new Error('Missing Gemini API key. Set GEMINI_API_KEY in .env.');
    }

    this.client = new GoogleGenerativeAI(key);
    // Default to a vision-capable model that is widely available.
    this.modelName = model || process.env.GEMINI_MODEL || 'gemini-2.0-flash';
    this.apiVersion = process.env.GEMINI_API_VERSION || 'v1beta';
    this.model = this.client.getGenerativeModel({
      model: this.modelName,
      systemInstruction: { role: 'system', parts: [{ text: SYSTEM_PROMPT }] },
    }, { apiVersion: this.apiVersion });
  }

  async parsePrescriptionFromImage(
    filePath: string,
    displayName?: string
  ): Promise<{ ocrText: string; medications: Medication[] }> {
    try {
      const imagePart = await this.readImageInlineData(filePath);
      const userText = this.buildUserInstruction(displayName);

      const response = await this.model.generateContent({
        contents: [
          {
            role: 'user',
            parts: [{ text: userText }, imagePart],
          },
        ],
        generationConfig: {
          temperature: 0,
          responseMimeType: 'application/json',
          responseSchema: medicationSchema,
        },
      });

      const content = response.response.text();
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
      const message = error instanceof Error ? error.message : 'Unknown LLM error.';
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

  private async readImageInlineData(
    filePath: string
  ): Promise<{ inlineData: { data: string; mimeType: string } }> {
    const buffer = await fs.readFile(filePath);
    const mime = this.guessMimeType(filePath);
    return {
      inlineData: {
        data: buffer.toString('base64'),
        mimeType: mime,
      },
    };
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
