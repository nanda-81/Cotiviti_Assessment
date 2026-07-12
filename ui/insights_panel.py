"""
ui/insights_panel.py
====================
Right-column component: Renders structured AI output in a rich, interactive
Clinical Natural Language Intelligence dashboard format.

Refocused per Production Review:
  - Primary Identity: Clinical Chart Intelligence Platform.
  - Tabs: Human-Readable Report | Structured JSON | Export Hub | Downstream Applications.
  - Highlights NLP Confidence Scores & Verbatim Evidence Capture.
  - Distinguishes CONFIRMED vs SUSPECTED/INFERRED conditions.
  - Includes Processing Metrics bar (Latency, Entity counts, Volume).
  - Multi-format Export (JSON, Markdown, CSV).
"""

from __future__ import annotations
import csv
import io
import json
import streamlit as st
from core.data_models import ClinicalSummary


# ─────────────────────────────────────────────────────────────────────────────
# Colour Palettes & Icons
# ─────────────────────────────────────────────────────────────────────────────

SEVERITY_COLOURS = {
    "CRITICAL": ("#ff4444", "#2d0000"),
    "HIGH":     ("#f97316", "#2d1200"),
    "MEDIUM":   ("#eab308", "#2d2000"),
    "LOW":      ("#22c55e", "#002d0e"),
}

CONFIDENCE_COLOURS = {
    "HIGH":   "#4ade80",
    "MEDIUM": "#facc15",
    "LOW":    "#f87171",
}

STATUS_COLOURS = {
    "CONFIRMED": ("#38bdf8", "#0c2e4e"),
    "SUSPECTED": ("#fb923c", "#3b1704"),
    "INFERRED":  ("#c084fc", "#2e1065"),
}

CATEGORY_ICONS = {
    "CODING_GAP":     "🔍",
    "DRUG_SAFETY":    "💊",
    "PREVENTIVE_GAP": "🛡️",
    "MISSING_DATA":   "📋",
    "CLINICAL_ALERT": "🚨",
}


def render_insights(summary: ClinicalSummary) -> None:
    """
    Render the full structured ClinicalSummary as a rich Streamlit dashboard.
    """
    # ── Header & Title ────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="display:flex; align-items:center; background:#0f172a; border:1px solid #1e293b; padding:12px 18px; border-radius:10px; margin-bottom:12px;">
            <span style="font-size:1.5rem; margin-right:12px;">🏥</span>
            <div>
                <div style="font-size:1.1rem; font-weight:800; color:#f8fafc;">Clinical Chart Intelligence Dashboard</div>
                <div style="font-size:0.75rem; color:#38bdf8;">Automated Medical Entity Recognition & Document Understanding</div>
            </div>
            <span style="margin-left:auto; font-size:0.72rem; color:#4ade80; background:#052e16; padding:4px 10px; border-radius:999px; border:1px solid #14532d; font-weight:700;">
                ● NLP EXTRACTION COMPLETE
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Processing Metrics Bar ────────────────────────────────────────────────
    if summary.processing_metrics:
        m = summary.processing_metrics
        st.markdown(
            f"""
            <div style="display:grid; grid-template-columns:repeat(5, 1fr); gap:8px; margin-bottom:16px;">
                <div style="background:#1e293b; padding:8px 12px; border-radius:8px; border:1px solid #334155; text-align:center;">
                    <div style="font-size:0.68rem; color:#94a3b8; text-transform:uppercase;">Extraction Time</div>
                    <div style="font-size:1.1rem; font-weight:800; color:#38bdf8;">{m.extraction_time_seconds:.2f}s</div>
                </div>
                <div style="background:#1e293b; padding:8px 12px; border-radius:8px; border:1px solid #334155; text-align:center;">
                    <div style="font-size:0.68rem; color:#94a3b8; text-transform:uppercase;">Diagnoses Found</div>
                    <div style="font-size:1.1rem; font-weight:800; color:#a855f7;">{m.total_diagnoses}</div>
                </div>
                <div style="background:#1e293b; padding:8px 12px; border-radius:8px; border:1px solid #334155; text-align:center;">
                    <div style="font-size:0.68rem; color:#94a3b8; text-transform:uppercase;">Medications Recon</div>
                    <div style="font-size:1.1rem; font-weight:800; color:#10b981;">{m.total_medications}</div>
                </div>
                <div style="background:#1e293b; padding:8px 12px; border-radius:8px; border:1px solid #334155; text-align:center;">
                    <div style="font-size:0.68rem; color:#94a3b8; text-transform:uppercase;">Anomalies Flagged</div>
                    <div style="font-size:1.1rem; font-weight:800; color:#f87171;">{m.total_anomalies}</div>
                </div>
                <div style="background:#1e293b; padding:8px 12px; border-radius:8px; border:1px solid #334155; text-align:center;">
                    <div style="font-size:0.68rem; color:#94a3b8; text-transform:uppercase;">Chart Volume</div>
                    <div style="font-size:1.1rem; font-weight:800; color:#e2e8f0;">{m.characters_processed:,} <span style="font-size:0.7rem; font-weight:400;">chars</span></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Navigation Tabs ───────────────────────────────────────────────────────
    tab_report, tab_json, tab_export, tab_downstream = st.tabs([
        "📄 Human-Readable Report",
        "💻 Structured JSON Viewer",
        "📤 Export Options (CSV/MD/JSON)",
        "📊 Downstream Clinical Applications",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1: HUMAN-READABLE REPORT (Core Clinical NLP Features)
    # ══════════════════════════════════════════════════════════════════════════
    with tab_report:
        _render_demographics(summary)
        _render_diagnoses(summary)
        _render_medications(summary)
        _render_anomalies(summary)
        _render_documentation_quality(summary)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2: STRUCTURED JSON VIEWER
    # ══════════════════════════════════════════════════════════════════════════
    with tab_json:
        st.markdown("#### 💻 Raw Medical Entity Extraction JSON")
        st.markdown(
            "Below is the exact schema-validated structured output generated by the Gemini "
            "Natural Language Processing engine. Payment integrity teams consume this JSON "
            "directly in automated rules engines."
        )
        st.json(summary.model_dump())

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3: EXPORT OPTIONS (JSON, Markdown, CSV)
    # ══════════════════════════════════════════════════════════════════════════
    with tab_export:
        st.markdown("#### 📤 Clinical Data Export Hub")
        st.markdown("Export extracted medical intelligence into standard industry formats.")

        col_e1, col_e2, col_e3 = st.columns(3)
        with col_e1:
            st.markdown("**Structured JSON**")
            st.markdown("<span style='font-size:0.75rem; color:#94a3b8;'>For API pipelines & ETL</span>", unsafe_allow_html=True)
            json_str = summary.model_dump_json(indent=2)
            st.download_button(
                label="⬇️ Download .JSON",
                data=json_str,
                file_name="clinical_chart_extraction.json",
                mime="application/json",
                use_container_width=True,
            )
        with col_e2:
            st.markdown("**Clinical Report**")
            st.markdown("<span style='font-size:0.75rem; color:#94a3b8;'>Formatted Markdown for EHR</span>", unsafe_allow_html=True)
            md_str = _summary_to_markdown(summary)
            st.download_button(
                label="⬇️ Download .MD",
                data=md_str,
                file_name="clinical_chart_report.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col_e3:
            st.markdown("**Tabular CSV Data**")
            st.markdown("<span style='font-size:0.75rem; color:#94a3b8;'>For Excel & SQL databases</span>", unsafe_allow_html=True)
            csv_str = _summary_to_csv(summary)
            st.download_button(
                label="⬇️ Download Diagnoses .CSV",
                data=csv_str,
                file_name="extracted_diagnoses.csv",
                mime="text/csv",
                use_container_width=True,
            )

        st.divider()
        st.markdown("##### 📦 Preview CSV Table (Diagnoses)")
        if summary.diagnoses:
            diag_data = [
                {
                    "Condition": dx.condition,
                    "ICD-10": dx.icd10_code,
                    "Status": dx.status,
                    "Confidence": dx.confidence,
                    "Evidence Snippet": dx.supporting_evidence[:80] + "..." if len(dx.supporting_evidence) > 80 else dx.supporting_evidence
                }
                for dx in summary.diagnoses
            ]
            st.table(diag_data)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4: DOWNSTREAM CLINICAL APPLICATIONS (HCC, Auditing)
    # ══════════════════════════════════════════════════════════════════════════
    with tab_downstream:
        st.markdown("#### 📊 Downstream Business Applications Enablement")
        st.markdown(
            "The extracted clinical intelligence shown in the Report tab can seamlessly enable "
            "downstream payment integrity and risk adjustment operations."
        )
        
        st.info(
            "**💡 Architectural Principle:** Clinical Natural Language Understanding remains the "
            "primary capability. Payment Accuracy, HCC Risk Adjustment, and Clinical Auditing "
            "are downstream business consumers enabled by high-precision entity recognition.",
            icon="ℹ️"
        )

        if summary.hcc_risk_score_commentary:
            st.markdown(
                f"""
                <div style="background:#0f172a; border:1px solid #0284c7; border-radius:10px; padding:16px; margin-top:12px;">
                    <div style="font-size:0.85rem; font-weight:800; color:#38bdf8; margin-bottom:8px;">
                        ⚖️ HIERARCHICAL CONDITION CATEGORY (HCC) COMMENTARY
                    </div>
                    <div style="font-size:0.9rem; color:#e2e8f0; line-height:1.7;">
                        {summary.hcc_risk_score_commentary}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.warning("No HCC risk score commentary generated for this document.")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### 💼 Payment Integrity Enabled Workflows")
        st.markdown(
            """
            - **Pre-Payment Claim Scrubbing:** Cross-referencing billed ICD-10 claims against extracted NLP diagnoses to prevent DRG upcoding.
            - **Clinical DRG Validation:** Verifying that verbatim supporting evidence justifies inpatient admission criteria.
            - **Retrospective Chart Auditing:** Automated detection of missing documentation or uncorroborated diagnoses.
            """
        )


# ─────────────────────────────────────────────────────────────────────────────
# Section Renderers
# ─────────────────────────────────────────────────────────────────────────────

def _render_demographics(summary: ClinicalSummary) -> None:
    d = summary.patient_demographics
    st.markdown("#### 👤 Patient Demographics & Clinical Summary")
    
    fields = {
        "Patient":   d.patient_name,
        "Age / DOB": d.age,
        "Sex":       d.sex,
        "MRN":       d.mrn,
        "Insurance": d.insurance,
        "Encounter": d.encounter_date,
        "Physician": d.attending_physician,
        "Type":      d.encounter_type,
    }

    cols = st.columns(4)
    for idx, (label, value) in enumerate(fields.items()):
        with cols[idx % 4]:
            st.markdown(
                f"""
                <div style="background:#1e293b; padding:8px 10px; border-radius:6px; border:1px solid #334155; margin-bottom:8px;">
                    <div style="font-size:0.68rem; color:#94a3b8; font-weight:600;">{label}</div>
                    <div style="font-size:0.85rem; color:#f8fafc; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{value or '—'}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if summary.chief_complaint:
        st.markdown(
            f"""
            <div style="background:#0f172a; border-left:4px solid #38bdf8; padding:10px 14px; border-radius:6px; margin-top:4px; margin-bottom:12px;">
                <span style="font-weight:700; color:#94a3b8; font-size:0.8rem; text-transform:uppercase;">Chief Complaint: </span>
                <span style="color:#f8fafc; font-weight:600;">{summary.chief_complaint}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.divider()


def _render_diagnoses(summary: ClinicalSummary) -> None:
    diags = summary.diagnoses
    st.markdown(f"#### 🩺 Extracted Diagnoses & ICD-10 Mapping  `{len(diags)} found`")
    
    if not diags:
        st.info("No diagnoses extracted from this document.", icon="ℹ️")
        return

    for i, dx in enumerate(diags, start=1):
        conf_color = CONFIDENCE_COLOURS.get(dx.confidence, "#94a3b8")
        status_fg, status_bg = STATUS_COLOURS.get(dx.status, ("#e2e8f0", "#334155"))

        with st.expander(
            f"**{i}. {dx.condition}** — ICD-10: `{dx.icd10_code}`  "
            f"| Status: {dx.status} | Confidence: {dx.confidence}",
            expanded=(i <= 3)
        ):
            cola, colb = st.columns([1.2, 1.8])
            with cola:
                st.markdown(
                    f"""
                    <div style="background:#1e293b; border:1px solid #334155; border-radius:8px; padding:12px;">
                        <div style="font-size:1.4rem; font-weight:800; color:#38bdf8; font-family:monospace;">{dx.icd10_code}</div>
                        <div style="font-size:0.82rem; color:#e2e8f0; font-weight:600; margin-bottom:10px;">{dx.icd10_description}</div>
                        <div style="display:flex; gap:6px;">
                            <span style="background:{status_bg}; color:{status_fg}; font-size:0.68rem; font-weight:700; padding:2px 8px; border-radius:4px; border:1px solid {status_fg}44;">
                                {dx.status}
                            </span>
                            <span style="background:#0f172a; color:{conf_color}; font-size:0.68rem; font-weight:700; padding:2px 8px; border-radius:4px; border:1px solid {conf_color}44;">
                                ● {dx.confidence} CONF
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with colb:
                st.markdown("**📌 Verbatim Supporting Evidence:**")
                st.markdown(
                    f"""
                    <div style="background:#0f172a; border-left:3px solid #10b981; padding:8px 12px; font-style:italic; font-size:0.85rem; color:#cbd5e1; border-radius:0 6px 6px 0; margin-bottom:8px;">
                        "{dx.supporting_evidence}"
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if dx.coding_notes:
                    st.markdown("**💡 Specificity & Coding Rationale:**")
                    st.markdown(f"<div style='font-size:0.8rem; color:#94a3b8;'>{dx.coding_notes}</div>", unsafe_allow_html=True)
    st.divider()


def _render_medications(summary: ClinicalSummary) -> None:
    meds = summary.medications
    st.markdown(f"#### 💊 Medication Reconciliation  `{len(meds)} active/historical drugs`")

    if not meds:
        st.info("No medications documented.", icon="ℹ️")
        return

    for m in meds:
        flag_badge = f"<span style='color:#f87171; font-weight:700;'>🚩 {m.flag}</span>" if m.flag else "<span style='color:#4ade80;'>✓ Safe</span>"
        ev_text = f"<br><span style='font-size:0.75rem; color:#64748b; font-style:italic;'>Evidence: \"{m.supporting_evidence}\"</span>" if m.supporting_evidence else ""

        st.markdown(
            f"""
            <div style="background:#1e293b; border:1px solid #334155; border-radius:8px; padding:10px 14px; margin-bottom:8px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:800; color:#f8fafc; font-size:0.95rem;">💊 {m.drug_name} <span style="color:#38bdf8; font-weight:600;">{m.dose or ''} {m.route or ''} {m.frequency or ''}</span></span>
                    <span style="font-size:0.8rem;">{flag_badge}</span>
                </div>
                <div style="font-size:0.82rem; color:#cbd5e1; margin-top:4px;">
                    <b>Indication:</b> {m.indication or 'Not documented'} {ev_text}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.divider()


def _render_anomalies(summary: ClinicalSummary) -> None:
    anomalies = summary.anomalies
    critical = [a for a in anomalies if a.severity == "CRITICAL"]
    high     = [a for a in anomalies if a.severity == "HIGH"]
    other    = [a for a in anomalies if a.severity not in ("CRITICAL", "HIGH")]

    st.markdown(
        f"#### 🚨 Documentation Gaps & Clinical Anomalies  "
        f"`{len(anomalies)} detected`",
        unsafe_allow_html=True,
    )

    if not anomalies:
        st.success("✅ Documentation is complete. No clinical or coding anomalies detected.", icon="✅")
        return

    for group, group_label in [
        (critical, "🔴 Critical Document / Clinical Alerts"),
        (high,     "🟠 High Priority Gaps"),
        (other,    "🟡 Medium / Low Notices"),
    ]:
        if not group:
            continue
        st.markdown(f"**{group_label}**")
        for a in group:
            sev_color, sev_bg = SEVERITY_COLOURS.get(a.severity, ("#94a3b8", "#1e293b"))
            icon = CATEGORY_ICONS.get(a.category, "⚠️")
            st.markdown(
                f"""
                <div style="border-left: 4px solid {sev_color}; background: {sev_bg}; padding:12px; border-radius:6px; margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; font-weight:700; color:#f8fafc; font-size:0.88rem;">
                        <span>{icon} {a.category.replace('_', ' ')}</span>
                        <span style="color:{sev_color};">{a.severity}</span>
                    </div>
                    <div style="font-size:0.84rem; color:#e2e8f0; margin:6px 0;">{a.description}</div>
                    <div style="font-size:0.82rem; color:#4ade80;">
                        <strong>→ Actionable Recommendation:</strong> {a.recommendation}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.divider()


def _render_documentation_quality(summary: ClinicalSummary) -> None:
    if summary.coding_summary:
        st.markdown("#### 📋 Documentation Clarity & NLP Quality Assessment")
        st.markdown(
            f"""
            <div style="background:#1e293b; border:1px solid #475569; border-radius:8px; padding:14px; font-size:0.88rem; color:#e2e8f0; line-height:1.6;">
                {summary.coding_summary}
            </div>
            """,
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Export Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _summary_to_markdown(summary: ClinicalSummary) -> str:
    d = summary.patient_demographics
    m = summary.processing_metrics
    metrics_md = f"\n**Extraction Time:** {m.extraction_time_seconds:.2f}s | **Chars Processed:** {m.characters_processed:,}\n" if m else ""

    lines = [
        "# ClinicalIQ — Clinical Chart Extraction Report",
        f"**Automated Clinical NLP Extraction · Cotiviti Assessment POC**{metrics_md}",
        "---",
        "## Patient Demographics",
        f"- **Patient Name:** {d.patient_name}",
        f"- **Age / DOB:** {d.age or '—'}  |  **Sex:** {d.sex or '—'}",
        f"- **MRN:** {d.mrn or '—'}  |  **Insurance:** {d.insurance or '—'}",
        f"- **Encounter Date:** {d.encounter_date or '—'}",
        f"- **Attending Physician:** {d.attending_physician or '—'}",
        f"- **Chief Complaint:** {summary.chief_complaint or 'Not documented'}",
        "",
        "---",
        "## Extracted Diagnoses & ICD-10 Mapping",
    ]

    for i, dx in enumerate(summary.diagnoses, 1):
        lines += [
            f"### {i}. {dx.condition}",
            f"- **ICD-10 Code:** `{dx.icd10_code}` ({dx.icd10_description})",
            f"- **Clinical Status:** {dx.status} | **Coder Confidence:** {dx.confidence}",
            f"- **Verbatim Evidence:** \"{dx.supporting_evidence}\"",
            f"- **Coding Notes:** {dx.coding_notes or 'None'}",
            "",
        ]

    lines += ["---", "## Medication Reconciliation"]
    for m_entry in summary.medications:
        flag = f" [⚠️ FLAG: {m_entry.flag}]" if m_entry.flag else ""
        ev = f" (Evidence: \"{m_entry.supporting_evidence}\")" if m_entry.supporting_evidence else ""
        lines.append(
            f"- **{m_entry.drug_name}** {m_entry.dose or ''} {m_entry.route or ''} "
            f"{m_entry.frequency or ''} — *Indication: {m_entry.indication or 'N/A'}*{flag}{ev}"
        )

    lines += ["", "---", "## Detected Anomalies & Gaps"]
    for a in summary.anomalies:
        lines += [
            f"### [{a.severity}] {a.category}",
            f"- **Description:** {a.description}",
            f"- **Recommendation:** {a.recommendation}",
            "",
        ]

    if summary.hcc_risk_score_commentary:
        lines += [
            "---",
            "## Downstream Application: HCC Risk Adjustment Commentary",
            summary.hcc_risk_score_commentary,
        ]

    return "\n".join(lines)


def _summary_to_csv(summary: ClinicalSummary) -> str:
    """Export extracted diagnoses to a standard CSV format string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Condition Name", "ICD-10 Code", "ICD-10 Description", "Status", "Confidence", "Verbatim Evidence Snippet", "Coding Notes"])
    
    for dx in summary.diagnoses:
        writer.writerow([
            dx.condition,
            dx.icd10_code,
            dx.icd10_description,
            dx.status,
            dx.confidence,
            dx.supporting_evidence,
            dx.coding_notes or ""
        ])
    return output.getvalue()
