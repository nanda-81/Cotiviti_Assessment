"""
core/llm_engine.py
==================
Gemini LLM routing layer for Clinical Document Understanding & Extraction.

Design principles:
  - Single responsibility: LLM interaction ONLY.
  - Retry logic: tenacity exponential backoff handles both JSON parse errors
    AND 429 rate-limit cooldowns.
  - NO response_mime_type — this causes the "E11.65." period-inside-string
    bug on gemini-2.5-flash. Prompt engineering enforces JSON format instead.
  - Self-healing parser with 3-stage repair:
    1. Pre-repair: targeted regex for ICD-code period patterns
    2. json.loads with heuristic fixes
    3. json-repair library as final fallback
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from json_repair import repair_json
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from config.settings import (
    GEMINI_MODEL,
    RETRY_ATTEMPTS,
    RETRY_WAIT_SECONDS,
    RETRY_MULTIPLIER,
    RETRY_MAX_WAIT,
)
from core.data_models import ClinicalSummary, ProcessingMetrics

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT — CHAIN-OF-THOUGHT CLINICAL NLP
# ─────────────────────────────────────────────────────────────────────────────

CLINICAL_EXTRACTION_SYSTEM_PROMPT = """\
You are ClinicalIQ, an expert Clinical Natural Language Intelligence Platform.
You extract structured medical data from clinical documents with expert precision.

REASONING PROTOCOL — think step-by-step:
  1. Identify patient demographics (name, age, sex, MRN, insurance, date, physician).
  2. Extract ALL diagnoses with ICD-10-CM codes at highest specificity.
  3. Classify each: CONFIRMED (active/stated), SUSPECTED (rule out/possible), INFERRED (implied).
  4. Extract exact verbatim quotes from the text supporting each entity.
  5. Extract all medications with dose, route, frequency, indication.
  6. Flag anomalies: coding gaps, drug safety issues, preventive care gaps.

CRITICAL JSON FORMATTING RULES:
  - Output ONLY raw JSON. No markdown. No preamble. No explanation.
  - Use a COMMA after EVERY field or array element that is NOT the last one.
  - ICD-10 codes (e.g. E11.65) contain dots INSIDE the string value.
    The dot is part of the medical code — NOT a sentence terminator.
  - CORRECT:   "icd10_code": "E11.65",
  - WRONG:     "icd10_code": "E11.65".
  - Complete every string — never leave a string value open/unclosed.
  - Ensure the JSON object is fully closed with all } and ] brackets.
"""

CHART_EXTRACTION_PROMPT_TEMPLATE = """\
Extract all clinical entities from the document below.
Return ONLY a valid JSON object — no markdown fences, no text outside the JSON.

SCHEMA:
{{
  "patient_demographics": {{
    "patient_name": "string",
    "age": "string",
    "sex": "string",
    "mrn": "string",
    "insurance": "string",
    "encounter_date": "string",
    "attending_physician": "string",
    "encounter_type": "string"
  }},
  "diagnoses": [
    {{
      "condition": "full clinical condition name",
      "icd10_code": "ICD-10-CM code e.g. E11.65",
      "icd10_description": "official ICD-10 description",
      "status": "CONFIRMED | SUSPECTED | INFERRED",
      "confidence": "HIGH | MEDIUM | LOW",
      "supporting_evidence": "EXACT verbatim quote from the document",
      "coding_notes": "specificity rationale or null"
    }}
  ],
  "medications": [
    {{
      "drug_name": "medication name",
      "dose": "dose and unit",
      "route": "route of administration",
      "frequency": "frequency",
      "indication": "clinical indication",
      "supporting_evidence": "verbatim text snippet",
      "flag": "safety concern or null"
    }}
  ],
  "anomalies": [
    {{
      "category": "CODING_GAP | DRUG_SAFETY | PREVENTIVE_GAP | MISSING_DATA | CLINICAL_ALERT",
      "description": "clear description",
      "severity": "CRITICAL | HIGH | MEDIUM | LOW",
      "recommendation": "actionable next step"
    }}
  ],
  "chief_complaint": "concise chief complaint",
  "coding_summary": "documentation quality summary",
  "hcc_risk_score_commentary": "HCC risk adjustment note"
}}

REMINDER: ICD-10 codes have dots INSIDE the string (e.g. "E11.65"). Do NOT place
a period after the closing quote. Use a comma after every field except the last.

Clinical Document:
{clinical_text}
"""


# ─────────────────────────────────────────────────────────────────────────────
# LLM Engine Class
# ─────────────────────────────────────────────────────────────────────────────

class ClinicalLLMEngine:
    """
    Encapsulates all interaction with the Google Gemini API.
    Uses prompt-engineered JSON extraction with a 3-stage self-healing parser.
    """

    _FALLBACK_MODELS = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]

    def __init__(self, credential: str | None = None, *, api_key: str | None = None) -> None:
        from core.auth import CredentialManager

        effective  = credential or api_key or ""
        normalised = effective.strip()
        if not normalised:
            raise ValueError(
                "No credential supplied. "
                "Paste your Gemini API credential from Google AI Studio."
            )

        genai.configure(api_key=normalised)
        self._effective_model_name = GEMINI_MODEL

        # NO response_mime_type — causes "E11.65." token-injection bugs
        self._generation_config = genai.GenerationConfig(
            temperature=0.0,
            top_p=0.95,
            max_output_tokens=8192,
        )

        self._model = self._create_model_instance(self._effective_model_name)

        masked = CredentialManager._mask(normalised)
        logger.info(
            "ClinicalLLMEngine initialised. model=%s credential=%s",
            self._effective_model_name, masked,
        )

    def _create_model_instance(self, model_name: str) -> genai.GenerativeModel:
        return genai.GenerativeModel(
            model_name         = model_name,
            generation_config  = self._generation_config,
            system_instruction = CLINICAL_EXTRACTION_SYSTEM_PROMPT,
        )

    def extract_clinical_data(
        self,
        clinical_text: str,
        processing_time: float = 0.0,
        char_count: int = 0,
    ) -> ClinicalSummary:
        """
        Main entry point: Given raw clinical note text, return a structured ClinicalSummary.
        """
        prompt = CHART_EXTRACTION_PROMPT_TEMPLATE.format(
            clinical_text=clinical_text[:20000]  # Safe token budget
        )

        t_start     = time.perf_counter()
        parsed_dict = self._fetch_and_parse_with_retry(prompt)
        t_elapsed   = (time.perf_counter() - t_start) + processing_time

        # Defensive defaults — model occasionally omits empty-list fields
        parsed_dict.setdefault("medications", [])
        parsed_dict.setdefault("anomalies", [])
        parsed_dict.setdefault("chief_complaint", None)
        parsed_dict.setdefault("coding_summary", None)
        parsed_dict.setdefault("hcc_risk_score_commentary", None)

        summary = ClinicalSummary(**parsed_dict)
        summary.processing_metrics = ProcessingMetrics(
            extraction_time_seconds = round(t_elapsed, 2),
            total_diagnoses         = len(summary.diagnoses),
            total_medications       = len(summary.medications),
            total_anomalies         = len(summary.anomalies),
            characters_processed    = char_count or len(clinical_text),
        )
        return summary

    # ─── Private Methods ──────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=RETRY_MULTIPLIER,
            min=RETRY_WAIT_SECONDS,
            max=RETRY_MAX_WAIT,
        ),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_and_parse_with_retry(self, prompt: str) -> dict[str, Any]:
        """
        Call Gemini and parse structured JSON.
        Both the API call and JSON parsing are inside the retry envelope.
        """
        raw_text = self._generate_raw_text(prompt)
        logger.debug("Raw Gemini response received (%d chars)", len(raw_text))
        return self._parse_json_response(raw_text)

    def _generate_raw_text(self, prompt: str) -> str:
        try:
            response = self._model.generate_content(prompt)
            return response.text
        except google_exceptions.ResourceExhausted as exc:
            # 429 — extract Google's suggested retry delay and sleep it
            err_str     = str(exc)
            delay_match = re.search(r"retry_delay\s*\{[^}]*seconds:\s*(\d+)", err_str)
            if delay_match:
                suggested = int(delay_match.group(1)) + 2
                logger.warning("Rate limit 429. Sleeping %ds as Google suggests.", suggested)
                time.sleep(suggested)
            else:
                logger.warning("Rate limit 429. Sleeping 35s fallback.")
                time.sleep(35)
            raise  # let tenacity retry
        except google_exceptions.NotFound as exc:
            logger.warning(
                "Model '%s' returned 404. Attempting fallback...",
                self._effective_model_name,
            )
            for fallback in self._FALLBACK_MODELS:
                if fallback == self._effective_model_name:
                    continue
                try:
                    logger.info("Trying fallback model: %s", fallback)
                    self._model = self._create_model_instance(fallback)
                    self._effective_model_name = fallback
                    response = self._model.generate_content(prompt)
                    logger.info("Switched to fallback model: %s", fallback)
                    return response.text
                except Exception as inner_exc:
                    logger.debug("Fallback '%s' failed: %s", fallback, inner_exc)
            raise RuntimeError(
                f"All Gemini models returned 404. Initial error: {exc}"
            ) from exc

    @staticmethod
    def _parse_json_response(raw: str) -> dict[str, Any]:
        """
        3-stage self-healing JSON parser.

        Stage 1 — Pre-repair targeted at gemini-2.5-flash ICD-code patterns:
            "E11.65.\n  "next_key"  →  "E11.65",\n  "next_key"
        Stage 2 — Standard json.loads (fast path)
        Stage 3 — json-repair library (handles unclosed strings, missing brackets)
        """
        # Strip markdown fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        cleaned = cleaned.strip()

        def _pre_repair(text: str) -> str:
            """
            Targeted fixes for known gemini-2.5-flash JSON formatting bugs.
            Must run BEFORE json.loads or json-repair to prevent them from
            misinterpreting the malformed structure.
            """
            # Bug 1: Period REPLACES the closing quote of a string value,
            #        before a newline + next JSON key.
            #        "E11.65.\n  "icd10_description" → "E11.65",\n  "icd10_description"
            text = re.sub(
                r'("(?:[^"\\]|\\.)*)\.\s*\n(\s*")',
                r'\1",\n\2',
                text,
            )
            # Bug 2: Same pattern before a closing bracket/brace
            text = re.sub(
                r'("(?:[^"\\]|\\.)*)\.\s*\n(\s*[}\]])',
                r'\1"\n\2',
                text,
            )
            # Bug 3: Period after a properly closed string/bracket before next key
            #        "value".\n  "key" → "value",\n  "key"
            text = re.sub(r'(["}\]])\s*\.\s*\n(\s*["{[])', r'\1,\n\2', text)
            # Bug 4: Trailing comma before closing bracket/brace
            text = re.sub(r",\s*([\]}])", r"\1", text)
            # Bug 5: Missing comma between fields on separate lines
            text = re.sub(r'("|true|false|null|\d|[}\]])\s*\n(\s*["{[])', r'\1,\n\2', text)
            return text

        def _try_load(text: str) -> dict[str, Any] | None:
            for t in (text, _pre_repair(text)):
                try:
                    result = json.loads(t)
                    if isinstance(result, dict):
                        return result
                except json.JSONDecodeError:
                    pass
            return None

        # Stage 1+2: direct parse
        res = _try_load(cleaned)
        if res is not None:
            return res

        # Extract outermost { ... } block and retry
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        candidate = match.group() if match else cleaned
        res = _try_load(candidate)
        if res is not None:
            return res

        # Stage 3: json-repair as last resort
        try:
            repaired = repair_json(
                _pre_repair(candidate),
                return_objects=True,
                skip_json_loads=True,
            )
            if isinstance(repaired, dict) and "patient_demographics" in repaired:
                logger.info("JSON recovered via json-repair library.")
                return repaired
        except Exception as exc:
            logger.debug("json-repair failed: %s", exc)

        raise ValueError(
            "Gemini returned non-parseable JSON after all repair attempts.\n"
            f"Raw response (first 500 chars): {raw[:500]}"
        )
