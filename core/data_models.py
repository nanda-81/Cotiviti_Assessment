"""
core/data_models.py
===================
Pydantic v2 data models for all structured output from the Gemini LLM.
Using strict models ensures the AI output is always well-typed before
reaching the Streamlit UI layer.

Refocused per Production Review:
  - Adds status classification (CONFIRMED / SUSPECTED / INFERRED).
  - Enforces verbatim evidence snippets for diagnoses and medications.
  - Adds structured processing metrics.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class PatientDemographics(BaseModel):
    """Extracted patient-level identifiers and basic information."""
    patient_name:        str           = Field(description="Full name as it appears in the record")
    age:                 Optional[str] = Field(None, description="Age or Date of Birth")
    sex:                 Optional[str] = Field(None, description="Patient sex/gender")
    mrn:                 Optional[str] = Field(None, description="Medical Record Number (MRN)")
    insurance:           Optional[str] = Field(None, description="Insurance payer and plan")
    encounter_date:      Optional[str] = Field(None, description="Date of the clinical encounter")
    attending_physician: Optional[str] = Field(None, description="Attending or treating physician")
    encounter_type:      Optional[str] = Field(None, description="Type of encounter (e.g., Office Visit)")


class Diagnosis(BaseModel):
    """A single extracted clinical diagnosis with associated ICD-10 code and evidence."""
    condition:           str           = Field(description="Clinical condition or diagnosis name")
    icd10_code:          str           = Field(description="Best-fit ICD-10 code (e.g., E11.65)")
    icd10_description:   str           = Field(description="Official ICD-10 code description")
    status:              str           = Field("CONFIRMED", description="Verification status: CONFIRMED | SUSPECTED | INFERRED")
    confidence:          str           = Field(description="Extraction confidence: HIGH | MEDIUM | LOW")
    supporting_evidence: str           = Field(description="Verbatim quote or specific text snippet from the note supporting this diagnosis")
    coding_notes:        Optional[str] = Field(None, description="Nuances, specificity notes, or coding rationale")


class Medication(BaseModel):
    """A single medication entry from the medication reconciliation list."""
    drug_name:           str           = Field(description="Medication name (brand and/or generic)")
    dose:                Optional[str] = Field(None, description="Dose and unit (e.g., 10 mg)")
    route:               Optional[str] = Field(None, description="Route of administration (e.g., PO, SQ)")
    frequency:           Optional[str] = Field(None, description="Frequency (e.g., QDay, BID, TID)")
    indication:          Optional[str] = Field(None, description="Clinical indication for this medication")
    supporting_evidence: Optional[str] = Field(None, description="Verbatim text snippet supporting this drug or dosage")
    flag:                Optional[str] = Field(None, description="Any clinical concern or flag (e.g., renal dosing)")


class Anomaly(BaseModel):
    """A flagged anomaly, gap, or clinical concern detected in the chart."""
    category:       str = Field(description="Category: CODING_GAP | DRUG_SAFETY | PREVENTIVE_GAP | MISSING_DATA | CLINICAL_ALERT")
    description:    str = Field(description="Clear, actionable description of the anomaly")
    severity:       str = Field(description="Severity: CRITICAL | HIGH | MEDIUM | LOW")
    recommendation: str = Field(description="Recommended action to address this anomaly")


class ProcessingMetrics(BaseModel):
    """Execution performance and extraction quantitative metrics."""
    extraction_time_seconds: float = Field(0.0, description="Total NLP extraction time in seconds")
    total_diagnoses:         int   = Field(0, description="Count of extracted diagnoses")
    total_medications:       int   = Field(0, description="Count of extracted medications")
    total_anomalies:         int   = Field(0, description="Count of flagged anomalies")
    characters_processed:    int   = Field(0, description="Total characters in raw source text")


class ClinicalSummary(BaseModel):
    """Top-level structured output from the Gemini clinical chart extraction."""
    patient_demographics:      PatientDemographics
    diagnoses:                 list[Diagnosis]
    medications:               list[Medication]  = Field(default_factory=list)
    anomalies:                 list[Anomaly]     = Field(default_factory=list)
    chief_complaint:           Optional[str] = Field(None, description="Primary reason for the visit")
    coding_summary:            Optional[str] = Field(
        None,
        description="Overall medical coding summary and quality of the documentation"
    )
    hcc_risk_score_commentary: Optional[str] = Field(
        None,
        description="Downstream application note: Hierarchical Condition Category (HCC) risk adjustment commentary"
    )
    processing_metrics:        Optional[ProcessingMetrics] = Field(None, description="Performance and volume metrics")
