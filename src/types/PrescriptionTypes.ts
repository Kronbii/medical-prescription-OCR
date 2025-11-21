export interface Medication {
  drug_name: string;
  strength: string;
  form: string;
  frequency: string;
  duration: string;
  instructions: string;
  confidence: number;
}

export interface ParsedPrescription {
  ocrText: string;
  medications: Medication[];
}

export interface ServiceResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}
