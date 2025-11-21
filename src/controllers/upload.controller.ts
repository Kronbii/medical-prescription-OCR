import { Request, Response } from 'express';
import fs from 'fs/promises';
import path from 'path';
import { VisionService } from '../services/vision.service';
import { LlmService } from '../services/llm.service';
import { Medication } from '../types/PrescriptionTypes';

const visionService = new VisionService();
const llmService = new LlmService();
const LOG_DIR = process.env.LOG_DIR || path.join(process.cwd(), 'logs');

export const handleUpload = async (
  req: Request,
  res: Response
): Promise<void> => {
  try {
    if (!req.file) {
      res.status(400).json({ success: false, error: 'No file uploaded.' });
      return;
    }

    const filePath = req.file.path;
    const ocrText = await visionService.extractText(filePath);
    const medications: Medication[] = await llmService.parseMedications(ocrText);

    try {
      await persistOutputs(ocrText, medications, req.file.originalname);
    } catch (persistError) {
      console.warn('Failed to persist outputs', persistError);
    }

    res.json({
      success: true,
      ocr_text: ocrText,
      medications,
    });
  } catch (error) {
    // Log error server-side while returning generic message.
    console.error('Upload processing failed', error);
    res.status(500).json({
      success: false,
      error:
        error instanceof Error ? error.message : 'Failed to process prescription.',
    });
  }
};

const persistOutputs = async (
  ocrText: string,
  medications: Medication[],
  originalName?: string
): Promise<void> => {
  const safeName = (originalName || 'upload').replace(/[^a-z0-9]/gi, '_').toLowerCase();
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');

  const ocrDir = path.join(LOG_DIR, 'ocr');
  const llmDir = path.join(LOG_DIR, 'llm');
  await fs.mkdir(ocrDir, { recursive: true });
  await fs.mkdir(llmDir, { recursive: true });

  const ocrPath = path.join(ocrDir, `${timestamp}-${safeName}.txt`);
  const llmPath = path.join(llmDir, `${timestamp}-${safeName}.json`);

  await fs.writeFile(ocrPath, ocrText, 'utf8');
  await fs.writeFile(
    llmPath,
    JSON.stringify(
      {
        created_at: new Date().toISOString(),
        source_file: originalName,
        ocr_text: ocrText,
        medications,
      },
      null,
      2
    ),
    'utf8'
  );
};
