"""Prescription data models"""
from typing import List, Optional
from pydantic import BaseModel, Field


class MedicineIdentity(BaseModel):
    """Medicine identity information"""
    brand_name: Optional[str] = Field(None, description="Brand name of the medication")
    generic_name: str = Field(..., description="Generic name of the medication")
    form: str = Field(..., description="Form of medication (e.g., 'Capsule', 'Tablet', 'Syrup', 'Injection')")
    strength: str = Field(..., description="Dosage strength (e.g., '500 mg', '10 mg/ml')")


class MedicineInstructions(BaseModel):
    """Medicine administration instructions"""
    route: str = Field(..., description="Route of administration (e.g., 'Oral', 'Topical', 'Intravenous')")
    dose_quantity: str = Field(..., description="Quantity per dose (e.g., '1', '2 tablets', '5 ml')")
    frequency: str = Field(..., description="How often to take (e.g., 'Every 8 hours', '3 times daily', 'Once daily')")
    duration: str = Field(..., description="How long to take (e.g., '7 days', '2 weeks', 'As needed')")
    special_instructions: Optional[str] = Field(None, description="Special instructions (e.g., 'Take with food', 'Before meals')")


class MedicineDispensing(BaseModel):
    """Medicine dispensing information"""
    total_quantity: Optional[str] = Field(None, description="Total quantity to dispense (e.g., '21 capsules', '30 tablets')")
    refills: int = Field(0, description="Number of refills allowed")
    substitution_allowed: bool = Field(True, description="Whether generic substitution is allowed")


class Medicine(BaseModel):
    """Complete medicine information"""
    identity: MedicineIdentity
    instructions: MedicineInstructions
    dispensing: MedicineDispensing


class PrescriptionMeta(BaseModel):
    """Prescription metadata"""
    date: Optional[str] = Field(None, description="Prescription date (YYYY-MM-DD format)")
    doctor_name: Optional[str] = Field(None, description="Doctor's name")
    patient_name: Optional[str] = Field(None, description="Patient's name")
    patient_weight: Optional[str] = Field(None, description="Patient's weight (e.g., '75kg', '150 lbs')")


class ParsedPrescription(BaseModel):
    """Complete parsed prescription data"""
    prescription_meta: PrescriptionMeta
    medicines: List[Medicine] = Field(default_factory=list, description="List of medicines")
    ocr_text: Optional[str] = Field(None, description="Full transcribed text from the prescription image (for reference)")
    source_file: Optional[str] = Field(None, description="Original filename if available")
    languages_detected: Optional[List[str]] = Field(default_factory=list, description="Languages detected (ar, en, fr)")


class ProcessingResult(BaseModel):
    """Result of processing a prescription image"""
    success: bool
    prescription: Optional[ParsedPrescription] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None  # seconds

