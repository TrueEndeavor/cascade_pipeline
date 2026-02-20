"""
SEC Cascade Pipeline — Streamlit UI
Upload a PDF and see results from each stage: DETECT → ASK → FLAG
"""

import streamlit as st
import os
import json
import tempfile
from dotenv import load_dotenv; load_dotenv()

from langgraph.graph import StateGraph, START, END
from node_config import AgentStateParallel
from node_detect import sec_misleading_detect
from node_ask import sec_misleading_ask
from node_flag import sec_misleading_flag

st.set_page_config(page_title="SEC Compliance Cascade", layout="wide")
st.title("SEC Compliance Cascade Pipeline")
st.caption("DETECT → ASK → FLAG  |  Powered by Anthropic Claude")

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
        "1. **DETECT** — Wide-net scan for candidate violations\n"
        "2. **ASK** — Diagnostic review: FLAG or CLEAR each candidate\n"
        "3. **FLAG** — Final structured findings for flagged items"
    )

# --- File upload ---
uploaded_file = st.file_uploader("Upload a PDF document", type=["pdf"])

if uploaded_file and st.button("Run Pipeline", type="primary"):
    # Save uploaded file to temp path
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    # Build the graph (same as main.py but we stream node-by-node)
    workflow = StateGraph(AgentStateParallel)
    workflow.add_node('sec_misleading_detect', sec_misleading_detect)
    workflow.add_node('sec_misleading_ask', sec_misleading_ask)
    workflow.add_node('sec_misleading_flag', sec_misleading_flag)
    workflow.add_edge(START, 'sec_misleading_detect')
    workflow.add_edge('sec_misleading_detect', 'sec_misleading_ask')
    workflow.add_edge('sec_misleading_ask', 'sec_misleading_flag')
    workflow.add_edge('sec_misleading_flag', END)
    app = workflow.compile()

    initial_state = AgentStateParallel(
        pdf_path=tmp_path,
        Metadata={},  # type: ignore
        SEC_misleading_detect_artifact="",
        SEC_misleading_ask_artifact="",
        SEC_misleading_artifact="",
        SEC_misleading_token_data="",
    )

    progress = st.progress(0, text="Starting pipeline...")

    # Run the full pipeline
    try:
        result = None
        for i, event in enumerate(app.stream(initial_state, stream_mode="updates")):
            node_name = list(event.keys())[0]
            if node_name == "sec_misleading_detect":
                progress.progress(33, text="DETECT complete — running ASK...")
            elif node_name == "sec_misleading_ask":
                progress.progress(66, text="ASK complete — running FLAG...")
            elif node_name == "sec_misleading_flag":
                progress.progress(100, text="Pipeline complete!")
            result = event[node_name]

        if result is None:
            st.error("Pipeline returned no results.")
            st.stop()

        # Extract artifacts
        detect_json = result.get("SEC_misleading_detect_artifact", "")
        ask_json = result.get("SEC_misleading_ask_artifact", "")
        flag_json = result.get("SEC_misleading_artifact", "")
        token_data = result.get("SEC_misleading_token_data", {})

    except Exception as e:
        st.error(f"Pipeline error: {e}")
        os.unlink(tmp_path)
        st.stop()

    # Clean up temp file
    os.unlink(tmp_path)

    # --- Summary metrics ---
    st.divider()

    try:
        detect_data = json.loads(detect_json)
        n_candidates = len(detect_data.get("candidates", []))
    except (json.JSONDecodeError, TypeError):
        detect_data = {"candidates": []}
        n_candidates = 0

    try:
        ask_data = json.loads(ask_json)
        ask_results = ask_data.get("results", [])
        n_flagged = sum(1 for r in ask_results if r.get("disposition") == "FLAG")
        n_cleared = sum(1 for r in ask_results if r.get("disposition") == "CLEAR")
    except (json.JSONDecodeError, TypeError):
        ask_data = {"results": []}
        n_flagged, n_cleared = 0, 0

    try:
        flag_data = json.loads(flag_json)
        n_findings = len(flag_data.get("sections", []))
    except (json.JSONDecodeError, TypeError):
        flag_data = {"sections": []}
        n_findings = 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Candidates Detected", n_candidates)
    col2.metric("Flagged", n_flagged)
    col3.metric("Cleared", n_cleared)
    col4.metric("Final Findings", n_findings)

    if isinstance(token_data, dict) and token_data.get("total_token_count"):
        st.caption(
            f"Tokens: {token_data['total_token_count']:,} total "
            f"({token_data.get('prompt_token_count', 0):,} input / "
            f"{token_data.get('candidate_token_count', 0):,} output)"
        )

    # --- Stage tabs ---
    tab1, tab2, tab3 = st.tabs([
        f"1. DETECT ({n_candidates} candidates)",
        f"2. ASK ({n_flagged} FLAG / {n_cleared} CLEAR)",
        f"3. FLAG ({n_findings} findings)",
    ])

    with tab1:
        st.subheader("DETECT — Candidate Violations")
        for i, c in enumerate(detect_data.get("candidates", []), 1):
            severity = c.get("severity", "Medium")
            severity_colors = {"Critical": "red", "High": "orange", "Medium": "blue", "Low": "gray"}
            color = severity_colors.get(severity, "blue")
            confidence = c.get("confidence", "")

            with st.expander(
                f"**{i}. [{severity}]** p.{c.get('page_number', '?')} — "
                f"{c.get('candidate_sub_bucket', 'Unknown')} "
                f"(confidence: {confidence})",
                expanded=(severity in ("Critical", "High")),
            ):
                st.markdown(f"> {c.get('sentence', '')}")
                st.markdown(f"**Reason:** {c.get('brief_reason', '')}")

    with tab2:
        st.subheader("ASK — Diagnostic Review")
        flagged_tab, cleared_tab = st.tabs(["Flagged", "Cleared"])
        with flagged_tab:
            flagged = [r for r in ask_data.get("results", []) if r.get("disposition") == "FLAG"]
            if not flagged:
                st.info("No candidates were flagged.")
            for i, r in enumerate(flagged, 1):
                with st.expander(
                    f"**{i}. FLAG** — p.{r.get('page_number', '?')} — {r.get('sub_bucket', '')}",
                    expanded=True,
                ):
                    st.markdown(f"> {r.get('sentence', '')}")
                    st.markdown(f"**Reasoning:** {r.get('reasoning', '')}")
        with cleared_tab:
            cleared = [r for r in ask_data.get("results", []) if r.get("disposition") == "CLEAR"]
            if not cleared:
                st.info("No candidates were cleared.")
            for i, r in enumerate(cleared, 1):
                with st.expander(
                    f"**{i}. CLEAR** — p.{r.get('page_number', '?')}",
                    expanded=False,
                ):
                    st.markdown(f"> {r.get('sentence', '')}")
                    st.markdown(f"**Reasoning:** {r.get('reasoning', '')}")

    with tab3:
        st.subheader("FLAG — Final Findings")
        if not flag_data.get("sections"):
            st.success("No violations found.")
        for i, s in enumerate(flag_data.get("sections", []), 1):
            with st.expander(
                f"**{i}. p.{s.get('page_number', '?')}** — {s.get('sub_bucket', '')}",
                expanded=True,
            ):
                st.markdown(f"**Summary:** {s.get('summary', '')}")
                st.markdown(f"> {s.get('sentence', '')}")
                st.markdown(f"**Observations:** {s.get('observations', '')}")
                st.markdown(f"**Rule Citation:** `{s.get('rule_citation', '')}`")
                st.markdown(f"**Recommendations:** {s.get('recommendations', '')}")

    # --- Raw JSON ---
    with st.expander("Raw JSON Output", expanded=False):
        raw1, raw2, raw3 = st.tabs(["detect.json", "ask.json", "flag.json"])
        with raw1:
            st.json(detect_data)
        with raw2:
            st.json(ask_data)
        with raw3:
            st.json(flag_data)
