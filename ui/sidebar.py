"""
ui/sidebar.py
=============
Sidebar component: Credential input, live connection status, and architecture explainer.

Refocused per Production Review:
  - Architecture explainer highlights Clinical Natural Language Processing & Understanding.
  - Badges reflect NLP technologies (Gemini Flash, ICD-10 Extraction, Document Intelligence).
  - Clearly positions payment integrity as a downstream consumer of extracted insights.
"""

from __future__ import annotations
import streamlit as st
from config.settings import APP_VERSION, GEMINI_MODEL, COMPANY_NAME


# Cache the connection test result for the duration of the session
# so we don't re-probe Google on every Streamlit rerun.
_AUTH_CACHE_KEY = "_auth_result_cache"


def render_sidebar() -> str | None:
    """
    Render the sidebar panel and return the effective credential.
    """
    with st.sidebar:

        # ── Header ────────────────────────────────────────────────────────────
        st.markdown(
            """
            <div style="text-align:center; padding: 1rem 0 0.5rem 0;">
                <div style="font-size: 2.5rem;">🏥</div>
                <div style="font-size: 1.25rem; font-weight: 800; color: #f8fafc;
                            letter-spacing: 0.04em;">ClinicalIQ</div>
                <div style="font-size: 0.75rem; color: #38bdf8; font-weight: 600; margin-top: 2px;">
                    Clinical NLP & Chart Intelligence
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""<div style="text-align:center; margin-bottom: 1rem;">
                <span style="font-size:0.65rem; color:#64748b;
                             background:#1e293b; padding:2px 8px;
                             border-radius:999px;">v{APP_VERSION}</span>
            </div>""",
            unsafe_allow_html=True,
        )

        st.divider()

        # ── Credential Input ───────────────────────────────────────────────────
        st.markdown("#### 🔑 Gemini API Credential")
        st.markdown(
            "<span style='font-size:0.75rem; color:#94a3b8;'>"
            "Free tier · Stateless & HIPAA-safe demo</span>",
            unsafe_allow_html=True,
        )

        # Pull env key
        from config.settings import GEMINI_API_KEY as ENV_KEY

        # Sidebar input
        sidebar_input = st.text_input(
            label="Paste your Gemini API credential",
            type="password",
            placeholder="Paste credential from Google AI Studio",
            help=(
                "Paste your Gemini API credential from Google AI Studio. "
                "All credential formats issued by Google are supported. "
                "Your credential is sent only to Google's API — never stored."
            ),
            label_visibility="collapsed",
        )

        effective_credential = (sidebar_input.strip() or "").strip() or (ENV_KEY or "").strip()

        # ── Connection Status Badge ────────────────────────────────────────────
        if effective_credential:
            _render_connection_status(effective_credential)
        else:
            st.markdown(
                """
                <div style="background: rgba(71,85,105,0.2);
                            border: 1px solid #334155;
                            border-radius: 8px; padding: 10px 12px;
                            margin-bottom: 8px; font-size:0.78rem; color:#64748b;">
                    ⚪ No credential supplied
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(
            "[🔗 Get a free credential at Google AI Studio]"
            "(https://aistudio.google.com/app/apikey)",
        )

        st.divider()

        # ── Engine & Tech Badges ───────────────────────────────────────────────
        st.markdown("#### 🛠️ Implemented Technologies")
        st.markdown(
            """
            <div style="display:flex; flex-wrap:wrap; gap:6px; margin-bottom:10px;">
                <span style="font-size:0.7rem; background:#0f172a; color:#38bdf8; border:1px solid #0369a1; padding:2px 8px; border-radius:4px;">Clinical NLP</span>
                <span style="font-size:0.7rem; background:#0f172a; color:#a855f7; border:1px solid #7e22ce; padding:2px 8px; border-radius:4px;">Gemini LLM</span>
                <span style="font-size:0.7rem; background:#0f172a; color:#10b981; border:1px solid #047857; padding:2px 8px; border-radius:4px;">ICD-10 Mapping</span>
                <span style="font-size:0.7rem; background:#0f172a; color:#f59e0b; border:1px solid #b45309; padding:2px 8px; border-radius:4px;">OCR / Vision</span>
                <span style="font-size:0.7rem; background:#0f172a; color:#ec4899; border:1px solid #be185d; padding:2px 8px; border-radius:4px;">Structured JSON</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        # ── Architecture Explainer ─────────────────────────────────────────────
        with st.expander("🏗️ System Architecture", expanded=False):
            st.markdown(
                """
                **Clinical NLP Intelligence Pipeline:**

                ```
                Upload Clinical Chart (PDF/TXT)
                          ↓
                Multi-Stage Document Parsing
                (pdfplumber OCR + PyPDF2)
                          ↓
                  Raw Clinical Text
                          ↓
                 Google Gemini LLM
                (Medical Entity Extraction)
                          ↓
                Structured Medical Intelligence
                (Diagnoses, Evidence, Meds)
                          ↓
                Interactive Clinical Dashboard
                ```

                **Downstream Applications:**
                Extracted clinical intelligence MAY support:
                - • Payment Accuracy
                - • Risk Adjustment (HCC)
                - • Clinical Auditing
                - • Population Health
                """
            )

        # ── Research Context ───────────────────────────────────────────────────
        with st.expander("📚 Topic 1 Assessment Focus", expanded=False):
            st.markdown(
                """
                **Cotiviti Topic 1 Objectives:**
                *Clinical Natural Language Technology for Health Care: Past, Present, & Future Approaches*

                - **Core Paradigms:** Rule-based NLP vs Statistical ML vs Modern LLMs/LMMs.
                - **Clinical Challenges:** Abbreviations, negation detection, temporal reasoning, PHI de-identification.
                - **Demonstrated Value:** Automated entity recognition, high-confidence ICD-10 coding, verbatim evidence capture.
                """
            )

        st.divider()

        # ── Footer ────────────────────────────────────────────────────────────
        st.markdown(
            f"""
            <div style="text-align:center; font-size:0.65rem; color:#475569;">
                Cotiviti Technical Assessment POC<br>
                <b>Topic 1: Clinical Natural Language Technology</b><br>
                Powered by Google Gemini · Built with Streamlit
            </div>
            """,
            unsafe_allow_html=True,
        )

    return effective_credential or None


# ─────────────────────────────────────────────────────────────────────────────
# Connection Status Renderer
# ─────────────────────────────────────────────────────────────────────────────

def _render_connection_status(credential: str) -> None:
    from core.auth import CredentialManager

    cache_key_credential = hash(credential)
    cached = st.session_state.get(_AUTH_CACHE_KEY)

    if cached is None or cached.get("credential_hash") != cache_key_credential:
        with st.spinner("🔍 Probing Gemini NLP endpoint…"):
            manager = CredentialManager(credential)
            result  = manager.validate()

        st.session_state[_AUTH_CACHE_KEY] = {
            "credential_hash": cache_key_credential,
            "result":          result,
        }
    else:
        result = cached["result"]

    if result.is_healthy:
        latency = f" · {result.latency_ms:.0f}ms" if result.latency_ms else ""
        st.markdown(
            f"""
            <div style="background: rgba(16,185,129,0.1);
                        border: 1px solid rgba(16,185,129,0.4);
                        border-radius: 8px; padding: 10px 12px;
                        margin-bottom: 6px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:1.1rem;">✅</span>
                    <div>
                        <div style="font-size:0.8rem; font-weight:700;
                                    color:#4ade80;">NLP Engine Online</div>
                        <div style="font-size:0.68rem; color:#64748b; margin-top:1px;">
                            Gemini endpoint verified{latency}
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif result.status.name == "NETWORK_ERROR":
        st.markdown(
            """
            <div style="background: rgba(234,179,8,0.08);
                        border: 1px solid rgba(234,179,8,0.4);
                        border-radius: 8px; padding: 10px 12px; margin-bottom:6px;">
                <div style="font-size:0.8rem; font-weight:700; color:#facc15;">
                    🌐 Network Offline
                </div>
                <div style="font-size:0.7rem; color:#94a3b8; margin-top:3px;">
                    Cannot reach Google API. Check internet connection.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:
        http_label = f"HTTP {result.http_status}" if result.http_status else "Auth Error"
        st.markdown(
            f"""
            <div style="background: rgba(239,68,68,0.08);
                        border: 1px solid rgba(239,68,68,0.4);
                        border-radius: 8px; padding: 10px 12px; margin-bottom:6px;">
                <div style="font-size:0.8rem; font-weight:700; color:#f87171;">
                    ❌ {http_label} — Endpoint Error
                </div>
                <div style="font-size:0.7rem; color:#94a3b8; margin-top:3px;
                            line-height:1.5;">
                    {result.message[:200]}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
