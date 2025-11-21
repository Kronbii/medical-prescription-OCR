import { ImageAnnotatorClient } from '@google-cloud/vision';
import path from 'path';

export class VisionService {
  private client: ImageAnnotatorClient;

  constructor(keyFilePath?: string) {
    const keyFilename =
      keyFilePath ||
      process.env.GOOGLE_APPLICATION_CREDENTIALS ||
      path.join(process.cwd(), 'keys', 'google-vision.json');

    this.client = new ImageAnnotatorClient({
      keyFilename,
    });
  }

  async extractText(filePath: string): Promise<string> {
    try {
      const [result] = await this.client.textDetection(filePath);
      const text =
        result.fullTextAnnotation?.text ||
        result.textAnnotations?.[0]?.description ||
        '';

      if (!text.trim()) {
        throw new Error('No text detected from OCR.');
      }

      return text.trim();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Unknown error during OCR.';
      throw new Error(`Vision OCR failed: ${message}`);
    }
  }
}
