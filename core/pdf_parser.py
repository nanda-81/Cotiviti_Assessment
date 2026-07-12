"""
core/pdf_parser.py
==================
PDF ingestion pipeline with a two-stage extraction strategy:
  1. Primary:  pdfplumber  — layout-aware, table-sensitive, superior accuracy.
  2. Fallback: PyPDF2      — simpler, handles edge cases where pdfplumber fails.

Also supports plain-text (.txt) files for rapid testing.
"""

from __future__ import annotations
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def extract_text(uploaded_file) -> tuple[str, str]:
    """
    Extract plain text from an uploaded file object (Streamlit UploadedFile).

    Parameters
    ----------
    uploaded_file : streamlit.runtime.uploaded_file_manager.UploadedFile
        The file object provided by `st.file_uploader`.

    Returns
    -------
    tuple[str, str]
        (extracted_text, method_used)
        method_used is one of: "pdfplumber", "PyPDF2", "plain-text"

    Raises
    ------
    ValueError
        If the file type is unsupported.
    RuntimeError
        If both PDF extraction methods fail.
    """
    file_name   = uploaded_file.name.lower()
    file_bytes  = uploaded_file.read()

    # ── Plain Text Fast-Path ──────────────────────────────────────────────────
    if file_name.endswith(".txt"):
        logger.info("Plain-text file detected; decoding directly.")
        text = file_bytes.decode("utf-8", errors="replace")
        return text.strip(), "plain-text"

    # ── PDF Processing ────────────────────────────────────────────────────────
    if file_name.endswith(".pdf"):
        # Stage 1: pdfplumber (preferred)
        try:
            text = _extract_with_pdfplumber(file_bytes)
            if len(text.strip()) > 50:
                logger.info("pdfplumber extraction succeeded.")
                return text.strip(), "pdfplumber"
            logger.warning("pdfplumber returned minimal text; trying PyPDF2 fallback.")
        except Exception as exc:
            logger.warning("pdfplumber failed (%s); falling back to PyPDF2.", exc)

        # Stage 2: PyPDF2 (fallback)
        try:
            text = _extract_with_pypdf2(file_bytes)
            if len(text.strip()) > 20:
                logger.info("PyPDF2 fallback extraction succeeded.")
                return text.strip(), "PyPDF2"
        except Exception as exc:
            logger.error("PyPDF2 also failed: %s", exc)

        raise RuntimeError(
            "Both PDF extraction methods (pdfplumber and PyPDF2) failed. "
            "The PDF may be image-only (scanned). OCR support is on the roadmap."
        )

    # ── Unsupported File Type ─────────────────────────────────────────────────
    suffix = Path(file_name).suffix.upper() or "unknown"
    raise ValueError(
        f"Unsupported file type: {suffix}. "
        "Please upload a PDF (.pdf) or plain-text (.txt) file."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Private Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_with_pdfplumber(file_bytes: bytes) -> str:
    """
    Use pdfplumber to extract text from all pages.
    pdfplumber preserves layout better than PyPDF2, especially for
    clinical documents with tables (lab results, medication lists).
    """
    import pdfplumber  # type: ignore

    pages_text: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            pages_text.append(f"--- Page {page_num} ---\n{page_text}")

    return "\n\n".join(pages_text)


def _extract_with_pypdf2(file_bytes: bytes) -> str:
    """
    Use PyPDF2 to extract text from all pages (fallback strategy).
    Less layout-aware but handles a wider range of PDF formats.
    """
    import PyPDF2  # type: ignore

    pages_text: list[str] = []
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    for page_num, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        pages_text.append(f"--- Page {page_num} ---\n{page_text}")

    return "\n\n".join(pages_text)
