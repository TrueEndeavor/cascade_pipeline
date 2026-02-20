"""
SEC Cascade v2 — Evidence Registry Pipeline UI
Upload a PDF and see results: REGISTRY → CHECKER → DETECT → VALIDATE

Run: streamlit run app_v2.py
"""

import streamlit as st
import os
import json
import html
import tempfile
from dotenv import load_dotenv; load_dotenv()

# Bridge Streamlit Cloud secrets → env vars (works both locally and deployed)
try:
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"):
        if key in st.secrets and key not in os.environ:
            os.environ[key] = st.secrets[key]
except FileNotFoundError:
    pass  # no secrets file — rely on .env or sidebar input

from pipeline.runner import build_evidence_pipeline
from pipeline.state import PipelineState

st.set_page_config(page_title="SEC Cascade v2", layout="wide")

# ─── Global table CSS ─────────────────────────────────────
st.markdown("""
<style>
.sec-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    line-height: 1.4;
    margin-bottom: 1rem;
}
.sec-table th {
    background: #262730;
    color: #fafafa;
    padding: 8px 10px;
    text-align: left;
    border: 1px solid #444;
    white-space: nowrap;
    position: sticky;
    top: 0;
}
.sec-table td {
    padding: 8px 10px;
    border: 1px solid #ddd;
    vertical-align: top;
    word-wrap: break-word;
    overflow-wrap: break-word;
}
.sec-table tr:nth-child(even) { background: #f8f9fa; }
.sec-table tr:hover { background: #e8ecf1; }
.sec-table .cell-text { max-width: 350px; }
.sec-table .cell-narrow { max-width: 100px; }
.sec-table .cell-med { max-width: 200px; }

/* Severity badges */
.sev-critical { background: #d32f2f; color: #fff; padding: 2px 6px; border-radius: 3px; font-weight: 600; font-size: 0.78rem; }
.sev-high { background: #e65100; color: #fff; padding: 2px 6px; border-radius: 3px; font-weight: 600; font-size: 0.78rem; }
.sev-medium { background: #1565c0; color: #fff; padding: 2px 6px; border-radius: 3px; font-weight: 600; font-size: 0.78rem; }
.sev-low { background: #757575; color: #fff; padding: 2px 6px; border-radius: 3px; font-weight: 600; font-size: 0.78rem; }

/* Disposition badges */
.disp-flag { background: #d32f2f; color: #fff; padding: 2px 8px; border-radius: 3px; font-weight: 700; }
.disp-clear { background: #2e7d32; color: #fff; padding: 2px 8px; border-radius: 3px; font-weight: 700; }

/* Quality dots */
.q-adequate { color: #2e7d32; }
.q-partial { color: #f9a825; }
.q-weak { color: #e65100; }
.q-contradictory { color: #d32f2f; }
.q-absent { color: #616161; }

.flag-tag { background: #ffcdd2; color: #b71c1c; padding: 1px 5px; border-radius: 3px; font-size: 0.75rem; margin-right: 3px; display: inline-block; margin-bottom: 2px; }
</style>
""", unsafe_allow_html=True)


def _esc(text):
    """HTML-escape text for safe table rendering."""
    return html.escape(str(text)) if text else ""


def _sev_badge(severity):
    s = str(severity).lower()
    css = {"critical": "sev-critical", "high": "sev-high", "medium": "sev-medium", "low": "sev-low"}.get(s, "sev-medium")
    return f'<span class="{css}">{_esc(severity)}</span>'


def _disp_badge(disposition):
    css = "disp-flag" if disposition == "FLAG" else "disp-clear"
    return f'<span class="{css}">{_esc(disposition)}</span>'


def _quality_dot(quality):
    q = str(quality).lower()
    css = {"adequate": "q-adequate", "partial": "q-partial", "weak": "q-weak",
           "contradictory": "q-contradictory", "absent": "q-absent"}.get(q, "q-absent")
    symbols = {"adequate": "●", "partial": "●", "weak": "●",
               "contradictory": "●", "absent": "●"}
    return f'<span class="{css}">{symbols.get(q, "●")}</span> {_esc(quality)}'


def _flag_tags(flags):
    if not flags:
        return "—"
    return " ".join(f'<span class="flag-tag">{_esc(f)}</span>' for f in flags)


st.title("SEC Compliance — Evidence Registry Pipeline")
st.caption("REGISTRY → CHECKER → DETECT → VALIDATE  |  Powered by Anthropic Claude")

# --- Sidebar ---
with st.sidebar:
    st.header("Settings")
    model = st.text_input(
        "Model",
        value=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
    )
    api_key = st.text_input(
        "Anthropic API Key",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
        type="password",
    )
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
    if model:
        os.environ["ANTHROPIC_MODEL"] = model

    st.divider()
    st.markdown("**How it works**")
    st.markdown(
        "0. **Extract** — Broad 10-category scan of PDF (Prompt A)\n"
        "1. **Registry** — Assessment + linking pass (Prompt B)\n"
        "2. **Checker** — Validate extraction coverage (deterministic)\n"
        "3. **Detect** — Identify Theme 1 violations from registry\n"
        "4. **Validate** — 6-check diagnostic + final findings"
    )
    st.divider()


# --- File upload ---
uploaded_file = st.file_uploader("Upload a PDF document", type=["pdf"])

if uploaded_file and st.button("Run Pipeline", type="primary"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    app = build_evidence_pipeline()
    initial_state = PipelineState(
        pdf_path=tmp_path,
        preliminary_extraction="",
        evidence_registry="",
        checker_report="",
        theme1_candidates="",
        theme1_findings="",
        token_usage={},
    )

    progress = st.progress(0, text="Phase 0: Preliminary extraction (broad scan)...")

    try:
        result = app.invoke(initial_state)
        progress.progress(100, text="Pipeline complete!")
    except Exception as e:
        st.error(f"Pipeline error: {e}")
        os.unlink(tmp_path)
        st.stop()

    os.unlink(tmp_path)

    # ─── Parse all outputs ───────────────────────────────────

    try:
        registry_raw = json.loads(result.get("evidence_registry", "{}"))
        registry = registry_raw.get("registry", registry_raw)
    except (json.JSONDecodeError, TypeError):
        registry = {"meta": {}, "claims": [], "contradictions": []}

    try:
        checker = json.loads(result.get("checker_report", "{}"))
    except (json.JSONDecodeError, TypeError):
        checker = {}

    try:
        candidates_data = json.loads(result.get("theme1_candidates", "{}"))
    except (json.JSONDecodeError, TypeError):
        candidates_data = {"candidates": []}

    try:
        findings_data = json.loads(result.get("theme1_findings", "{}"))
    except (json.JSONDecodeError, TypeError):
        findings_data = {"diagnostics": [], "sections": []}

    token_usage = result.get("token_usage") or {}
    n_claims = len(registry.get("claims", []))
    n_contradictions = len(registry.get("contradictions", []))
    candidates = candidates_data.get("candidates", [])
    n_candidates = len(candidates)
    diagnostics = findings_data.get("diagnostics", [])
    n_flagged = sum(1 for d in diagnostics if d.get("disposition") == "FLAG")
    n_cleared = sum(1 for d in diagnostics if d.get("disposition") == "CLEAR")
    sections = findings_data.get("sections", [])
    n_findings = len(sections)

    # ─── Summary metrics ─────────────────────────────────────

    st.divider()
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Claims Extracted", n_claims)
    col2.metric("Candidates", n_candidates)
    col3.metric("Flagged", n_flagged)
    col4.metric("Cleared", n_cleared)
    col5.metric("Final Findings", n_findings)

    total_in = sum(v for k, v in token_usage.items() if k.endswith("_input") and isinstance(v, (int, float)))
    total_out = sum(v for k, v in token_usage.items() if k.endswith("_output") and isinstance(v, (int, float)))
    if total_in:
        st.caption(f"Tokens: {total_in + total_out:,} total ({total_in:,} input / {total_out:,} output)")

    # ─── Stage tabs ──────────────────────────────────────────

    tab_reg, tab_chk, tab_det, tab_val, tab_fin = st.tabs([
        f"1. Registry ({n_claims} claims)",
        f"2. Checker",
        f"3. Detect ({n_candidates} candidates)",
        f"4. Validate ({n_flagged} FLAG / {n_cleared} CLEAR)",
        f"5. Findings ({n_findings})",
    ])

    # ─── Tab 1: Evidence Registry ────────────────────────────

    with tab_reg:
        st.subheader("Evidence Registry")

        meta = registry.get("meta", {})
        docs = meta.get("documents", [])
        if docs:
            doc = docs[0]
            st.markdown(
                f"**Document:** {doc.get('name', 'Unknown')}  \n"
                f"**Type:** {doc.get('type', '')}  |  "
                f"**Pages:** {doc.get('pages', '?')}  |  "
                f"**As of:** {doc.get('as_of_date', '?')}"
            )

        # Claims table grouped by page
        claims_by_page = {}
        for claim in registry.get("claims", []):
            page = str(claim.get("page", "?"))
            claims_by_page.setdefault(page, []).append(claim)

        for page in sorted(claims_by_page.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            st.markdown(f"#### Page {page}")
            rows = ""
            for claim in claims_by_page[page]:
                support = claim.get("support") or {}
                quality = support.get("quality", "absent")
                flags = claim.get("flags") or []
                support_text = _esc(support.get("text", "")) if support.get("exists") else "<em>none</em>"
                support_loc = _esc(support.get("location", "")) if support.get("exists") else ""

                rows += f"""<tr>
                    <td class="cell-narrow"><strong>{_esc(claim.get('claim_id', ''))}</strong></td>
                    <td class="cell-narrow">{_esc(claim.get('claim_type', ''))}</td>
                    <td class="cell-text">{_esc(claim.get('exact_text', ''))}</td>
                    <td class="cell-narrow">{_esc(claim.get('location', ''))}</td>
                    <td class="cell-text">{support_text}</td>
                    <td class="cell-narrow">{_quality_dot(quality)}</td>
                    <td class="cell-med">{_flag_tags(flags)}</td>
                </tr>"""

            st.markdown(f"""
            <table class="sec-table">
                <thead><tr>
                    <th>ID</th><th>Type</th><th>Claim Text</th><th>Location</th>
                    <th>Support</th><th>Quality</th><th>Flags</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
            """, unsafe_allow_html=True)

        # Contradictions table
        contradictions = registry.get("contradictions", [])
        if contradictions:
            st.markdown("#### Contradictions")
            rows = ""
            for con in contradictions:
                rows += f"""<tr>
                    <td class="cell-narrow"><strong>{_esc(con.get('contradiction_id', ''))}</strong></td>
                    <td class="cell-narrow">{_esc(con.get('type', ''))}</td>
                    <td class="cell-narrow">{_esc(', '.join(con.get('claim_ids', [])))}</td>
                    <td class="cell-text">{_esc(con.get('text_a', ''))}</td>
                    <td class="cell-text">{_esc(con.get('text_b', ''))}</td>
                </tr>"""
            st.markdown(f"""
            <table class="sec-table">
                <thead><tr>
                    <th>ID</th><th>Type</th><th>Claims</th><th>Text A</th><th>Text B</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
            """, unsafe_allow_html=True)

    # ─── Tab 2: Checker ─────────────────────────────────────

    with tab_chk:
        st.subheader("Registry Checker Report")

        coverage = checker.get("coverage_score", 0)
        passed = checker.get("passed", False)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Coverage Score", f"{coverage:.1%}")
        c2.metric("Status", "PASSED" if passed else "WARNINGS")
        c3.metric("Issues", len(checker.get("issues", [])))
        c4.metric("Total Pages", checker.get("total_pages", "?"))

        summary = checker.get("issue_summary", {})
        if summary:
            st.markdown("**Issue breakdown:**")
            for itype, count in summary.items():
                st.markdown(f"- `{itype}`: {count}")

        issues = checker.get("issues", [])
        non_orphan = [i for i in issues if i["type"] != "ORPHAN_NUMBER"]
        if non_orphan:
            st.markdown("**Non-numerical issues:**")
            rows = ""
            for issue in non_orphan:
                detail = issue.get("phrase") or issue.get("description") or issue.get("claim_id", "")
                rows += f"""<tr>
                    <td class="cell-narrow"><strong>{_esc(issue['type'])}</strong></td>
                    <td class="cell-text">{_esc(detail)}</td>
                </tr>"""
            st.markdown(f"""
            <table class="sec-table">
                <thead><tr><th>Type</th><th>Detail</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
            """, unsafe_allow_html=True)

        orphans = [i for i in issues if i["type"] == "ORPHAN_NUMBER"]
        if orphans:
            st.markdown("**Orphan numbers** (numbers in PDF not in registry):")
            st.code(", ".join(i["number"] for i in orphans))

    # ─── Tab 3: Detect ──────────────────────────────────────

    with tab_det:
        st.subheader("Theme 1 — Candidate Violations")
        if not candidates:
            st.info("No candidates detected.")
        else:
            rows = ""
            for i, c in enumerate(candidates, 1):
                severity = c.get("severity", "Medium")
                flags = c.get("flags_from_registry") or []
                rows += f"""<tr>
                    <td class="cell-narrow" style="text-align:center">{i}</td>
                    <td class="cell-narrow">{_sev_badge(severity)}</td>
                    <td class="cell-narrow" style="text-align:center">p.{_esc(c.get('page', '?'))}</td>
                    <td class="cell-narrow">{_esc(c.get('claim_id', ''))}</td>
                    <td class="cell-narrow">SB{_esc(c.get('sub_bucket', '?'))}</td>
                    <td class="cell-med">{_esc(c.get('sub_bucket_name', ''))}</td>
                    <td class="cell-text">{_esc(c.get('exact_text', ''))}</td>
                    <td class="cell-text">{_esc(c.get('brief_reason', ''))}</td>
                    <td class="cell-med">{_flag_tags(flags)}</td>
                    <td class="cell-narrow">{_quality_dot(c.get('support_quality', 'unknown'))}</td>
                </tr>"""
            st.markdown(f"""
            <table class="sec-table">
                <thead><tr>
                    <th>#</th><th>Severity</th><th>Page</th><th>Claim</th>
                    <th>SB</th><th>Sub-Bucket</th><th>Text</th><th>Reason</th>
                    <th>Registry Flags</th><th>Support</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
            """, unsafe_allow_html=True)

    # ─── Tab 4: Validate ────────────────────────────────────

    with tab_val:
        st.subheader("Diagnostic Review")
        fl_tab, cl_tab = st.tabs(["Flagged", "Cleared"])
        with fl_tab:
            flagged_diag = [d for d in diagnostics if d.get("disposition") == "FLAG"]
            if not flagged_diag:
                st.info("No candidates were flagged.")
            else:
                rows = ""
                for i, d in enumerate(flagged_diag, 1):
                    rows += f"""<tr>
                        <td class="cell-narrow" style="text-align:center">{i}</td>
                        <td class="cell-narrow">{_disp_badge('FLAG')}</td>
                        <td class="cell-narrow">{_esc(d.get('claim_id', ''))}</td>
                        <td class="cell-narrow" style="text-align:center">p.{_esc(d.get('page', '?'))}</td>
                        <td class="cell-med">{_esc(d.get('sub_bucket', ''))}</td>
                        <td class="cell-text">{_esc(d.get('exact_text', ''))}</td>
                        <td class="cell-med">{_esc(d.get('checks_applied', ''))}</td>
                        <td class="cell-text">{_esc(d.get('reasoning', ''))}</td>
                    </tr>"""
                st.markdown(f"""
                <table class="sec-table">
                    <thead><tr>
                        <th>#</th><th>Disp.</th><th>Claim</th><th>Page</th>
                        <th>Sub-Bucket</th><th>Text</th><th>Checks</th><th>Reasoning</th>
                    </tr></thead>
                    <tbody>{rows}</tbody>
                </table>
                """, unsafe_allow_html=True)

        with cl_tab:
            cleared_diag = [d for d in diagnostics if d.get("disposition") == "CLEAR"]
            if not cleared_diag:
                st.info("No candidates were cleared.")
            else:
                rows = ""
                for i, d in enumerate(cleared_diag, 1):
                    rows += f"""<tr>
                        <td class="cell-narrow" style="text-align:center">{i}</td>
                        <td class="cell-narrow">{_disp_badge('CLEAR')}</td>
                        <td class="cell-narrow">{_esc(d.get('claim_id', ''))}</td>
                        <td class="cell-narrow" style="text-align:center">p.{_esc(d.get('page', '?'))}</td>
                        <td class="cell-med">{_esc(d.get('sub_bucket', ''))}</td>
                        <td class="cell-text">{_esc(d.get('exact_text', ''))}</td>
                        <td class="cell-med">{_esc(d.get('checks_applied', ''))}</td>
                        <td class="cell-text">{_esc(d.get('reasoning', ''))}</td>
                    </tr>"""
                st.markdown(f"""
                <table class="sec-table">
                    <thead><tr>
                        <th>#</th><th>Disp.</th><th>Claim</th><th>Page</th>
                        <th>Sub-Bucket</th><th>Text</th><th>Checks</th><th>Reasoning</th>
                    </tr></thead>
                    <tbody>{rows}</tbody>
                </table>
                """, unsafe_allow_html=True)

    # ─── Tab 5: Final Findings ──────────────────────────────

    with tab_fin:
        st.subheader("Final Compliance Findings")
        if not sections:
            st.success("No violations found.")
        else:
            rows = ""
            for i, s in enumerate(sections, 1):
                severity_word = ""
                summary_text = s.get("summary", "")
                for level in ("Critical", "High", "Medium", "Low"):
                    if level.lower() in summary_text.lower():
                        severity_word = level
                        break
                rows += f"""<tr>
                    <td class="cell-narrow" style="text-align:center">{i}</td>
                    <td class="cell-narrow">{_sev_badge(severity_word) if severity_word else '—'}</td>
                    <td class="cell-narrow" style="text-align:center">p.{_esc(s.get('page_number', '?'))}</td>
                    <td class="cell-med">{_esc(s.get('sub_bucket', ''))}</td>
                    <td class="cell-text">{_esc(s.get('sentence', ''))}</td>
                    <td class="cell-text">{_esc(summary_text)}</td>
                    <td class="cell-text">{_esc(s.get('observations', ''))}</td>
                    <td class="cell-narrow"><code>{_esc(s.get('rule_citation', ''))}</code></td>
                    <td class="cell-text">{_esc(s.get('recommendations', ''))}</td>
                </tr>"""
            st.markdown(f"""
            <table class="sec-table">
                <thead><tr>
                    <th>#</th><th>Severity</th><th>Page</th><th>Sub-Bucket</th>
                    <th>Sentence</th><th>Summary</th><th>Observations</th>
                    <th>Rule</th><th>Recommendations</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
            """, unsafe_allow_html=True)

    # ─── Raw JSON ────────────────────────────────────────────

    with st.expander("Raw JSON Output", expanded=False):
        r1, r2, r3, r4 = st.tabs([
            "registry.json", "checker.json", "candidates.json", "findings.json"
        ])
        with r1:
            st.json(registry)
        with r2:
            st.json(checker)
        with r3:
            st.json(candidates_data)
        with r4:
            st.json(findings_data)
