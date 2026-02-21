"""
SEC Cascade — Evidence Registry Review
Upload a PDF → extract all claims → validate coverage.
Team members use this to review extraction quality.

Run: streamlit run app_registry.py
Deploy: Set main file to app_registry.py on Streamlit Cloud
"""

import streamlit as st
import os
import json
import html
import tempfile
from dotenv import load_dotenv; load_dotenv()

# Bridge Streamlit Cloud secrets → env vars
try:
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "MONGODB_URI"):
        if key in st.secrets and key not in os.environ:
            os.environ[key] = st.secrets[key]
except FileNotFoundError:
    pass

from pipeline.phase0_preliminary import phase0_preliminary_extract
from pipeline.phase1_evidence import phase1_extract_evidence
from pipeline.registry_checker import validate_registry
from pipeline.state import PipelineState
from pipeline.ground_truth import (
    extract_tc_id, fetch_ground_truth, match_claims_to_ground_truth,
)
from langgraph.graph import StateGraph, START, END

st.set_page_config(page_title="Evidence Registry Review", layout="wide")

# ─── CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
/* Narrow sidebar, maximize content area */
[data-testid="stSidebar"] { min-width: 200px !important; max-width: 240px !important; }
[data-testid="stSidebar"] .block-container { padding: 1rem 0.75rem; }

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
.sec-table .cell-text { max-width: 400px; }
.sec-table .cell-narrow { max-width: 100px; }
.sec-table .cell-med { max-width: 200px; }

.q-adequate { color: #2e7d32; }
.q-partial { color: #f9a825; }
.q-weak { color: #e65100; }
.q-contradictory { color: #d32f2f; }
.q-absent { color: #616161; }

.flag-tag { background: #ffcdd2; color: #b71c1c; padding: 1px 5px; border-radius: 3px; font-size: 0.75rem; margin-right: 3px; display: inline-block; margin-bottom: 2px; }
.cat-tag { background: #e3f2fd; color: #0d47a1; padding: 1px 5px; border-radius: 3px; font-size: 0.75rem; }

/* Ground truth match — green row */
.sec-table tr.gt-match { background: #c8e6c9 !important; }
.sec-table tr.gt-match:hover { background: #a5d6a7 !important; }
.sec-table tr.gt-miss { background: #ffcdd2 !important; }
.gt-badge { background: #2e7d32; color: #fff; padding: 1px 6px; border-radius: 3px; font-size: 0.72rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


def _esc(text):
    return html.escape(str(text)) if text else ""


def _quality_dot(quality):
    q = str(quality).lower()
    css = {"adequate": "q-adequate", "partial": "q-partial", "weak": "q-weak",
           "contradictory": "q-contradictory", "absent": "q-absent"}.get(q, "q-absent")
    return f'<span class="{css}">●</span> {_esc(quality)}'


def _flag_tags(flags):
    if not flags:
        return "—"
    return " ".join(f'<span class="flag-tag">{_esc(f)}</span>' for f in flags)


def _build_registry_pipeline():
    """Build a 3-node pipeline: Phase 0 → Phase 1 → Checker (no detect/validate)."""
    workflow = StateGraph(PipelineState)
    workflow.add_node("phase0_preliminary", phase0_preliminary_extract)
    workflow.add_node("phase1_evidence", phase1_extract_evidence)
    workflow.add_node("registry_checker", validate_registry)
    workflow.add_edge(START, "phase0_preliminary")
    workflow.add_edge("phase0_preliminary", "phase1_evidence")
    workflow.add_edge("phase1_evidence", "registry_checker")
    workflow.add_edge("registry_checker", END)
    return workflow.compile()


# ─── Header ──────────────────────────────────────────────
st.title("Evidence Registry Review")
st.caption("EXTRACT → REGISTRY → CHECKER")

# ─── Sidebar ─────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    model = st.text_input(
        "Model",
        value=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
    )
    if model:
        os.environ["ANTHROPIC_MODEL"] = model

    st.divider()
    st.markdown("**What this does**")
    st.markdown(
        "1. **Preliminary Scan** — Broad 10-category extraction from PDF\n"
        "2. **Evidence Registry** — Restructures into claims with support quality + flags\n"
        "3. **Checker** — Validates extraction coverage (deterministic)\n\n"
        "Your job: **review the claims table** and verify the extraction is complete and accurate."
    )

# ─── Upload + Run ────────────────────────────────────────
uploaded_file = st.file_uploader("Upload a PDF document", type=["pdf"])

if uploaded_file and st.button("Extract Evidence Registry", type="primary"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    # Fetch ground truth
    tc_id = extract_tc_id(uploaded_file.name)
    ground_truth = fetch_ground_truth(tc_id) if tc_id else []
    if ground_truth:
        st.info(f"Found **{len(ground_truth)}** ground truth entries for **{tc_id}**")
    elif tc_id:
        st.warning(f"No ground truth found for **{tc_id}** in MongoDB")

    app = _build_registry_pipeline()
    initial_state = PipelineState(
        pdf_path=tmp_path,
        preliminary_extraction="",
        evidence_registry="",
        checker_report="",
        theme1_candidates="",
        theme1_findings="",
        token_usage={},
    )

    progress = st.progress(0, text="Step 1/3: Scanning PDF (broad extraction)...")

    try:
        result = app.invoke(initial_state)
        progress.progress(100, text="Extraction complete!")
    except Exception as e:
        st.error(f"Pipeline error: {e}")
        os.unlink(tmp_path)
        st.stop()

    os.unlink(tmp_path)

    # ─── Parse outputs ───────────────────────────────────

    try:
        prelim = json.loads(result.get("preliminary_extraction", "{}"))
    except (json.JSONDecodeError, TypeError):
        prelim = {}

    try:
        registry_raw = json.loads(result.get("evidence_registry", "{}"))
        registry = registry_raw.get("registry", registry_raw)
    except (json.JSONDecodeError, TypeError):
        registry = {"meta": {}, "claims": [], "contradictions": []}

    try:
        checker = json.loads(result.get("checker_report", "{}"))
    except (json.JSONDecodeError, TypeError):
        checker = {}

    token_usage = result.get("token_usage") or {}
    claims = registry.get("claims", [])
    contradictions = registry.get("contradictions", [])
    coverage_gaps = registry.get("coverage_gaps", [])
    n_claims = len(claims)
    n_contradictions = len(contradictions)
    n_flagged_claims = sum(1 for c in claims if c.get("flags"))
    n_gaps = len(coverage_gaps)

    # Preliminary extraction counts
    prelim_total = sum(
        len(prelim.get(k, []))
        for k in ("disclaimers", "performance_data", "rankings_awards",
                   "definitions", "footnotes", "data_sources",
                   "qualifications", "visual_elements")
        if isinstance(prelim.get(k), list)
    )

    # ─── Ground truth matching ───────────────────────────

    gt_result = match_claims_to_ground_truth(claims, ground_truth) if ground_truth else None
    matched_claim_ids = gt_result["matched_claim_ids"] if gt_result else set()
    gt_coverage = gt_result["coverage"] if gt_result else None

    # ─── Summary metrics ─────────────────────────────────

    st.divider()
    if ground_truth:
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Preliminary Items", prelim_total)
        c2.metric("Final Claims", n_claims)
        c3.metric("With Flags", n_flagged_claims)
        c4.metric("Contradictions", n_contradictions)
        c5.metric("Coverage Gaps", n_gaps)
        c6.metric("GT Coverage", f"{gt_coverage:.0%}" if gt_coverage is not None else "—")
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Preliminary Items", prelim_total)
        c2.metric("Final Claims", n_claims)
        c3.metric("With Flags", n_flagged_claims)
        c4.metric("Contradictions", n_contradictions)
        c5.metric("Coverage Gaps", n_gaps)

    total_in = sum(v for k, v in token_usage.items() if k.endswith("_input") and isinstance(v, (int, float)))
    total_out = sum(v for k, v in token_usage.items() if k.endswith("_output") and isinstance(v, (int, float)))
    if total_in:
        st.caption(f"Tokens: {total_in + total_out:,} total ({total_in:,} input / {total_out:,} output)")

    # ─── Tabs ────────────────────────────────────────────

    tab_reg, tab_prelim, tab_chk, tab_json = st.tabs([
        f"Evidence Registry ({n_claims} claims)",
        f"Preliminary Scan ({prelim_total} items)",
        f"Checker ({checker.get('coverage_score', 0):.0%} coverage)",
        "Raw JSON",
    ])

    # ─── Evidence Registry (main review tab) ─────────────

    with tab_reg:
        st.subheader("Claims Registry")
        if ground_truth and gt_result:
            n_gt = len(ground_truth)
            n_matched = len(gt_result["matched_claim_ids"])
            st.markdown(
                f"**Ground Truth Coverage: {gt_coverage:.0%}** "
                f"({n_matched}/{n_gt} expected items found) — "
                f"Green rows = matched to ground truth"
            )
        st.markdown("Review each claim below. Verify: exact text matches the PDF, support is correctly linked, flags are appropriate.")

        meta = registry.get("meta", {})
        docs = meta.get("documents", [])
        if docs:
            doc = docs[0]
            st.markdown(
                f"**Document:** {doc.get('name', 'Unknown')}  |  "
                f"**Type:** {doc.get('type', '')}  |  "
                f"**Pages:** {doc.get('pages', '?')}  |  "
                f"**As of:** {doc.get('as_of_date', '?')}"
            )

        # Filter controls
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            show_flagged_only = st.checkbox("Show only flagged claims", value=False)
        with filter_col2:
            claim_types = sorted(set(c.get("claim_type", "") for c in claims))
            selected_type = st.selectbox("Filter by claim type", ["All"] + claim_types)

        filtered_claims = claims
        if show_flagged_only:
            filtered_claims = [c for c in filtered_claims if c.get("flags")]
        if selected_type != "All":
            filtered_claims = [c for c in filtered_claims if c.get("claim_type") == selected_type]

        # Claims table grouped by page
        claims_by_page = {}
        for claim in filtered_claims:
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
                support_type = _esc(support.get("type", "")) if support.get("exists") else ""
                claim_id = claim.get("claim_id", "")
                is_match = claim_id in matched_claim_ids
                row_class = ' class="gt-match"' if is_match else ""
                gt_label = ' <span class="gt-badge">GT</span>' if is_match else ""

                rows += f"""<tr{row_class}>
                    <td class="cell-narrow"><strong>{_esc(claim_id)}</strong>{gt_label}</td>
                    <td class="cell-narrow"><span class="cat-tag">{_esc(claim.get('claim_type', ''))}</span></td>
                    <td class="cell-text">{_esc(claim.get('exact_text', ''))}</td>
                    <td class="cell-narrow">{_esc(claim.get('location', ''))}</td>
                    <td class="cell-text">{support_text}</td>
                    <td class="cell-narrow">{support_type}</td>
                    <td class="cell-narrow">{support_loc}</td>
                    <td class="cell-narrow">{_quality_dot(quality)}</td>
                    <td class="cell-med">{_flag_tags(flags)}</td>
                </tr>"""

            st.markdown(f"""
            <table class="sec-table">
                <thead><tr>
                    <th>ID</th><th>Type</th><th>Claim Text</th><th>Location</th>
                    <th>Support Text</th><th>Sup. Type</th><th>Sup. Location</th>
                    <th>Quality</th><th>Flags</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
            """, unsafe_allow_html=True)

        # Contradictions
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

        # Coverage gaps
        if coverage_gaps:
            st.markdown("#### Coverage Gaps")
            st.warning(f"{n_gaps} item(s) from the preliminary extraction were not represented in the final registry:")
            rows = ""
            for gap in coverage_gaps:
                rows += f"""<tr>
                    <td class="cell-narrow">{_esc(gap.get('preliminary_id', ''))}</td>
                    <td class="cell-narrow">{_esc(gap.get('category', ''))}</td>
                    <td class="cell-text">{_esc(gap.get('reason', ''))}</td>
                </tr>"""
            st.markdown(f"""
            <table class="sec-table">
                <thead><tr><th>Preliminary ID</th><th>Category</th><th>Reason</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
            """, unsafe_allow_html=True)

        # Missed ground truth
        if gt_result and gt_result["missed_gt"]:
            st.markdown("#### Missed Ground Truth")
            st.error(f"{len(gt_result['missed_gt'])} ground truth item(s) NOT found in the registry:")
            rows = ""
            for gt in gt_result["missed_gt"]:
                rows += f"""<tr class="gt-miss">
                    <td class="cell-text">{_esc(gt.get('sentence', ''))}</td>
                    <td class="cell-narrow">{_esc(gt.get('TC Id', ''))}</td>
                </tr>"""
            st.markdown(f"""
            <table class="sec-table">
                <thead><tr><th>Expected Sentence</th><th>TC ID</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
            """, unsafe_allow_html=True)

    # ─── Preliminary Scan ────────────────────────────────

    with tab_prelim:
        st.subheader("Preliminary Extraction (Phase 0)")
        st.markdown("Raw 10-category extraction from the first pass. This fed into the Evidence Registry builder.")

        for category, label in [
            ("disclaimers", "Disclaimers"),
            ("performance_data", "Performance Data"),
            ("rankings_awards", "Rankings & Awards"),
            ("definitions", "Definitions"),
            ("footnotes", "Footnotes"),
            ("data_sources", "Data Sources"),
            ("qualifications", "Qualifications"),
            ("visual_elements", "Visual Elements"),
        ]:
            items = prelim.get(category, [])
            if not items:
                continue
            st.markdown(f"#### {label} ({len(items)})")
            rows = ""
            for item in items:
                # Build columns dynamically from item keys (skip 'id')
                item_id = item.get("id", "")
                page = item.get("page", "?")
                # Get the main text field (varies by category)
                text = (item.get("text") or item.get("claim") or
                        item.get("definition") or item.get("language") or
                        item.get("shows") or item.get("term") or "")
                detail = (item.get("type") or item.get("source") or
                          item.get("organization") or item.get("section") or
                          item.get("substantiates") or "")
                rows += f"""<tr>
                    <td class="cell-narrow">{_esc(item_id)}</td>
                    <td class="cell-narrow" style="text-align:center">{_esc(page)}</td>
                    <td class="cell-text">{_esc(text)}</td>
                    <td class="cell-med">{_esc(detail)}</td>
                </tr>"""
            st.markdown(f"""
            <table class="sec-table">
                <thead><tr><th>ID</th><th>Page</th><th>Text</th><th>Detail</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
            """, unsafe_allow_html=True)

        # Non-array items
        for key in ("audience_indicators", "temporal_context"):
            data = prelim.get(key, {})
            if data and isinstance(data, dict):
                st.markdown(f"#### {key.replace('_', ' ').title()}")
                rows = ""
                for k, v in data.items():
                    if v:
                        rows += f"<tr><td class='cell-narrow'><strong>{_esc(k)}</strong></td><td class='cell-text'>{_esc(v)}</td></tr>"
                if rows:
                    st.markdown(f"""
                    <table class="sec-table">
                        <thead><tr><th>Field</th><th>Value</th></tr></thead>
                        <tbody>{rows}</tbody>
                    </table>
                    """, unsafe_allow_html=True)

    # ─── Checker ─────────────────────────────────────────

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

    # ─── Raw JSON ────────────────────────────────────────

    with tab_json:
        r1, r2, r3 = st.tabs(["preliminary.json", "registry.json", "checker.json"])
        with r1:
            st.json(prelim)
        with r2:
            st.json(registry)
        with r3:
            st.json(checker)
