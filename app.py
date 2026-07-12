"""
app.py
======
ClinicalIQ — Clinical Chart Intelligence Platform
Cotiviti Intern Assessment POC | Topic 1: Clinical Natural Language Technology

Author:   Principal AI Engineering Team
Date:     2026
Version:  1.1.0-PROD

Architecture: Modular Streamlit application with strict separation of concerns:
  - app.py           → Entry point & orchestration
  - core/            → LLM engine, PDF parser, data models
  - ui/              → Sidebar, chart viewer, insights panel
  - config/          → Settings & constants
  - utils/           → Error handling utilities

Run: streamlit run app.py
"""

# ── Standard Library ──────────────────────────────────────────────────────────
import logging
import sys
import time
from pathlib import Path

# ── Ensure project root is on sys.path ────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Third-Party ───────────────────────────────────────────────────────────────
import streamlit as st

# ── Internal Modules ──────────────────────────────────────────────────────────
from config.settings import (
    APP_TITLE,
    APP_SUBTITLE,
    COMPANY_NAME,
    GEMINI_API_KEY,
    SPINNER_TEXT,
)
from ui.sidebar        import render_sidebar
from ui.chart_viewer   import render_chart_uploader
from ui.insights_panel import render_insights
from utils.error_handler import handle_extraction_error

# ── Logging Configuration ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help":    "https://aistudio.google.com/",
        "Report a bug": None,
        "About": (
            f"**{APP_TITLE}**\n\n"
            f"{APP_SUBTITLE}\n\n"
            f"Cotiviti Technical Assessment POC | Topic 1\n\n"
            "⚠️ Demonstration only. Not for clinical use."
        ),
    },
)


# ═════════════════════════════════════════════════════════════════════════════
#  GLOBAL CSS — Enterprise Dark Theme
# ═════════════════════════════════════════════════════════════════════════════
GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg-primary:      #070d1a;
    --bg-secondary:    #0d1829;
    --bg-card:         #111927;
    --border-subtle:   #1e2d42;
    --border-accent:   #1d4ed8;
    --text-primary:    #f8fafc;
    --text-secondary:  #94a3b8;
    --text-muted:      #475569;
    --accent-blue:     #3b82f6;
    --accent-cyan:     #06b6d4;
    --accent-green:    #10b981;
    --accent-gold:     #f59e0b;
    --accent-red:      #ef4444;
    --font-sans:       'Inter', -apple-system, sans-serif;
    --font-mono:       'JetBrains Mono', monospace;
    --radius-sm:       6px;
    --radius-md:       10px;
    --radius-lg:       16px;
    --shadow-card:     0 4px 24px rgba(0,0,0,0.4);
    --transition:      all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"] {
    font-family: var(--font-sans) !important;
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}

#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none !important; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #080f1e 0%, #0a1322 60%, #060c18 100%) !important;
    border-right: 1px solid var(--border-subtle) !important;
}
[data-testid="stSidebar"] * { color: var(--text-secondary) !important; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h4 { color: var(--text-primary) !important; }

.main .block-container {
    padding: 1.5rem 2rem !important;
    max-width: 1600px !important;
}

.app-header {
    background: linear-gradient(135deg, #0f2044 0%, #071930 50%, #0a1f3a 100%);
    border: 1px solid #1d3a6e;
    border-radius: var(--radius-lg);
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow-card);
}
.app-header-title {
    font-size: 1.85rem;
    font-weight: 800;
    background: linear-gradient(135deg, #60a5fa, #38bdf8, #818cf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.02em;
    line-height: 1.2;
}
.app-header-subtitle {
    font-size: 0.9rem;
    color: var(--text-secondary);
    margin-top: 0.3rem;
}
.app-header-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(56, 189, 248, 0.1);
    border: 1px solid rgba(56, 189, 248, 0.3);
    color: #38bdf8;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 999px;
    margin-top: 0.85rem;
}

.status-bar {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    margin-bottom: 1.25rem;
}
.status-pill {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 999px;
    padding: 5px 14px;
    font-size: 0.75rem;
    color: var(--text-secondary);
}
.status-pill.active {
    border-color: var(--accent-green);
    color: #4ade80;
    background: rgba(16, 185, 129, 0.05);
}
.status-pill.warning {
    border-color: var(--accent-gold);
    color: var(--accent-gold);
    background: rgba(245, 158, 11, 0.05);
}

.stTextInput input, .stTextInput textarea {
    background: #0d1829 !important;
    border: 1px solid #1e2d42 !important;
    color: var(--text-primary) !important;
    border-radius: var(--radius-sm) !important;
    font-family: var(--font-mono) !important;
}
.stButton > button {
    background: linear-gradient(135deg, #0284c7, #0369a1) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 700 !important;
    font-size: 0.92rem !important;
    padding: 0.65rem 1.5rem !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(2,132,199,0.4) !important;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 12px;
    background: var(--bg-secondary);
    padding: 6px 12px;
    border-radius: 10px;
    border: 1px solid var(--border-subtle);
}
.stTabs [data-baseweb="tab"] {
    height: 36px;
    white-space: nowrap;
    border-radius: 6px;
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text-secondary);
}
.stTabs [aria-selected="true"] {
    background-color: #1e293b !important;
    color: #38bdf8 !important;
}
</style>
"""


# ═════════════════════════════════════════════════════════════════════════════
#  SESSION STATE INITIALISATION
# ═════════════════════════════════════════════════════════════════════════════

def _init_session_state() -> None:
    defaults = {
        "clinical_summary":  None,
        "extract_triggered": False,
        "last_file_name":    None,
        "extraction_count":  0,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION ENTRYPOINT
# ═════════════════════════════════════════════════════════════════════════════

def main() -> None:
    # ── Inject Global CSS ─────────────────────────────────────────────────────
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    # ── Initialise Session State ──────────────────────────────────────────────
    _init_session_state()

    # ── Sidebar — API Key ─────────────────────────────────────────────────────
    sidebar_api_key   = render_sidebar()
    effective_api_key = sidebar_api_key or GEMINI_API_KEY

    # ── Application Header ────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div class="app-header">
            <div class="app-header-title">🏥 ClinicalIQ</div>
            <div class="app-header-subtitle">
                {APP_SUBTITLE}
            </div>
            <div class="app-header-badge">
                ✦ Cotiviti Assessment POC · Topic 1: Clinical Natural Language Technology
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Status Bar ────────────────────────────────────────────────────────────
    api_status = "active" if effective_api_key else "warning"
    api_label  = "NLP Engine Online" if effective_api_key else "Credential Required"
    api_icon   = "🟢" if effective_api_key else "🟡"

    st.markdown(
        f"""
        <div class="status-bar">
            <div class="status-pill {api_status}">{api_icon} {api_label}</div>
            <div class="status-pill">🤖 Gemini Flash</div>
            <div class="status-pill">🩺 ICD-10 Entity Coder</div>
            <div class="status-pill">🔒 Stateless · No PHI Stored</div>
            <div class="status-pill {'active' if st.session_state.extraction_count > 0 else ''}">
                ✅ {st.session_state.extraction_count} Chart{'s' if st.session_state.extraction_count != 1 else ''} Processed
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not effective_api_key:
        st.warning(
            "**🔑 Credential Required** — Paste your Gemini API credential in the sidebar "
            "to enable automated chart extraction. "
            "[Get a free credential at Google AI Studio →](https://aistudio.google.com/)",
            icon="🔑",
        )

    # ── Main Layout ───────────────────────────────────────────────────────────
    left_col, right_col = st.columns([1, 1.3], gap="large")

    # ── LEFT COLUMN: Document Upload & Raw Text ───────────────────────────────
    with left_col:
        uploaded_file, extracted_text, extraction_method = render_chart_uploader()

        if uploaded_file is not None and extracted_text is not None:
            if st.session_state.last_file_name != uploaded_file.name:
                st.session_state.clinical_summary  = None
                st.session_state.extract_triggered = False
                st.session_state.last_file_name    = uploaded_file.name

            st.markdown("<br>", unsafe_allow_html=True)
            extract_btn = st.button(
                "🧠  Extract Clinical Intelligence  →",
                type="primary",
                disabled=(not effective_api_key),
                use_container_width=True,
            )

            if extract_btn:
                st.session_state.extract_triggered = True
                st.session_state.clinical_summary  = None

    # ── RIGHT COLUMN: AI Dashboard ────────────────────────────────────────────
    with right_col:
        if st.session_state.extract_triggered and extracted_text is not None:

            if st.session_state.clinical_summary is None:
                with st.spinner(SPINNER_TEXT):
                    try:
                        from core.llm_engine import ClinicalLLMEngine
                        engine  = ClinicalLLMEngine(api_key=effective_api_key)
                        summary = engine.extract_clinical_data(
                            clinical_text = extracted_text,
                            char_count    = len(extracted_text),
                        )

                        st.session_state.clinical_summary  = summary
                        st.session_state.extraction_count += 1
                    except Exception as exc:
                        handle_extraction_error(exc, context="LLM Extraction")
                        st.session_state.extract_triggered = False

            if st.session_state.clinical_summary is not None:
                render_insights(st.session_state.clinical_summary)

        else:
            st.markdown(
                """
                <div style="display:flex; flex-direction:column; align-items:center;
                            justify-content:center; height:580px; text-align:center;
                            background: #070d1a; border: 1px dashed #1e2d42;
                            border-radius: 12px;">
                    <div style="font-size: 3.5rem; margin-bottom: 1rem; opacity: 0.4;">🏥</div>
                    <div style="font-size: 1.15rem; font-weight: 700; color: #64748b; margin-bottom: 0.5rem;">
                        Clinical NLP Dashboard Idle
                    </div>
                    <div style="font-size: 0.82rem; color: #475569; max-width: 320px; line-height: 1.6;">
                        Upload a clinical document on the left and click
                        <strong style="color:#38bdf8;">Extract Clinical Intelligence →</strong>
                        to perform entity extraction and document understanding.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="text-align:center; font-size:0.68rem; color:#475569; padding: 1.5rem 0 0.5rem 0;">
            ⚠️ Cotiviti Technical Assessment POC · Topic 1: Clinical Natural Language Technology | 
            Demonstration purposes only. Not for medical decision-making. | ClinicalIQ v1.1.0-PROD
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
