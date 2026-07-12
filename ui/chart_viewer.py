"""
ui/chart_viewer.py
==================
Left-column component: File uploader, raw text viewer, and document stats.
Handles file validation and extraction display only — no LLM calls.
"""

from __future__ import annotations
import streamlit as st
from config.settings import MAX_PDF_SIZE_MB


def render_chart_uploader() -> tuple[object | None, str | None, str | None]:
    """
    Render the file uploader and extracted text panel.

    Returns
    -------
    tuple[UploadedFile | None, str | None, str | None]
        (uploaded_file, extracted_text, extraction_method)
        All None if no file uploaded or extraction failed.
    """
    st.markdown(
        """
        <div class="section-header">
            <span class="section-icon">📋</span>
            <span>Clinical Document</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── File Uploader ─────────────────────────────────────────────────────────
    uploaded_file = st.file_uploader(
        label="Upload Clinical Chart",
        type=["pdf", "txt"],
        help=f"Supported formats: PDF, TXT. Max size: {MAX_PDF_SIZE_MB} MB.",
        label_visibility="collapsed",
    )

    if uploaded_file is None:
        # ── Empty State ────────────────────────────────────────────────────────
        st.markdown(
            """
            <div class="upload-placeholder">
                <div style="font-size: 3rem; margin-bottom: 0.5rem;">📁</div>
                <div style="font-size: 1rem; font-weight: 600; color: #cbd5e1;">
                    Drop a Clinical Chart Here
                </div>
                <div style="font-size: 0.8rem; color: #64748b; margin-top: 0.4rem;">
                    PDF or TXT — max 10 MB
                </div>
                <div style="font-size: 0.75rem; color: #475569; margin-top: 1rem;">
                    💡 Use the sample note in <code>data/sample_note.txt</code><br>
                    for a quick demo without a real clinical document.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return None, None, None

    # ── File Size Check ───────────────────────────────────────────────────────
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > MAX_PDF_SIZE_MB:
        st.error(
            f"❌ File too large ({file_size_mb:.1f} MB). "
            f"Maximum allowed: {MAX_PDF_SIZE_MB} MB.",
            icon="❌",
        )
        return None, None, None

    # ── Extract Text ──────────────────────────────────────────────────────────
    from core.pdf_parser import extract_text
    from utils.error_handler import handle_extraction_error

    extracted_text: str | None   = None
    extraction_method: str | None = None

    try:
        extracted_text, extraction_method = extract_text(uploaded_file)
    except Exception as exc:
        handle_extraction_error(exc, context="PDF Extraction")
        return uploaded_file, None, None

    # ── Document Stats Banner ─────────────────────────────────────────────────
    word_count = len(extracted_text.split())
    char_count = len(extracted_text)
    page_count = extracted_text.count("--- Page ")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("📄 Pages", page_count if page_count > 0 else "1")
    with col_b:
        st.metric("📝 Words", f"{word_count:,}")
    with col_c:
        st.metric("🔤 Characters", f"{char_count:,}")

    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:6px; 
                    margin: 0.5rem 0; padding: 6px 10px;
                    background: #0f2027; border-radius: 6px; 
                    border: 1px solid #1e3a5f;">
            <span style="color:#38bdf8; font-size:0.75rem;">⚙️ Parser:</span>
            <span style="color:#e2e8f0; font-size:0.75rem; font-weight:600;">
                {extraction_method}
            </span>
            <span style="color:#4ade80; font-size:0.75rem; margin-left:auto;">
                ✓ Extraction Successful
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Raw Text Expander ─────────────────────────────────────────────────────
    with st.expander("🔍 View Extracted Raw Text", expanded=False):
        st.markdown(
            f"""
            <div style="background:#0a0e1a; border:1px solid #1e293b; 
                        border-radius:8px; padding:1rem; 
                        font-family:'Courier New', monospace; font-size:0.72rem; 
                        color:#94a3b8; white-space:pre-wrap; 
                        max-height:400px; overflow-y:auto; line-height:1.6;">
{extracted_text[:8000]}{'...[truncated for display]' if len(extracted_text) > 8000 else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )

    return uploaded_file, extracted_text, extraction_method
