"""
Cascade Bench — Evaluation Framework for SEC Cascade Pipeline
Fetches test PDFs + ground truth from MongoDB, runs the pipeline,
scores results against ground truth, and stores eval runs.

Collections used (in PO2xNW database):
  READ:   test_documents, ground_truth
  WRITE:  cascade_bench_runs, cascade_bench_results

Usage:
  streamlit run cascade_bench.py
"""

import streamlit as st
import os
import re
import json
import tempfile
from datetime import datetime, timezone
from dotenv import load_dotenv; load_dotenv()
from pymongo import MongoClient
from difflib import SequenceMatcher

from langgraph.graph import StateGraph, START, END
from node_config import AgentStateParallel
from node_detect import sec_misleading_detect
from node_ask import sec_misleading_ask
from node_flag import sec_misleading_flag

# --- Config ---
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://nw-testing-team:Po2Success@po2-baseline.yphkg38.mongodb.net/?appName=po2-baseline",
)
DB_NAME = "PO2xNW"

st.set_page_config(page_title="Cascade Bench", layout="wide")
st.title("Cascade Bench")
st.caption("Evaluate SEC Cascade Pipeline against ground truth")


# --- MongoDB connection ---
@st.cache_resource
def get_db():
    client = MongoClient(MONGODB_URI)
    return client[DB_NAME]


db = get_db()


# --- Helpers ---
def extract_tc_id(filename: str) -> str:
    """Extract TC ID (e.g. 'TC04') from a filename.

    Handles: UPD_TC04_2.pdf, TC 1.pdf, TC1.pdf, tc20_doc.pdf, etc.
    """
    match = re.search(r"TC\s*(\d+)", filename, re.IGNORECASE)
    if match:
        num = int(match.group(1))
        return f"TC{num:02d}"
    return ""


def sentence_similarity(a: str, b: str) -> float:
    """Fuzzy match ratio between two sentences."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def match_findings_to_ground_truth(findings: list, ground_truth: list, threshold=0.5):
    """Match pipeline findings to ground truth entries using fuzzy sentence matching.
    Returns (matched_pairs, unmatched_findings, missed_ground_truth).
    """
    matched = []
    used_gt = set()
    used_f = set()

    # First pass: find best matches
    scores = []
    for i, f in enumerate(findings):
        f_sentence = f.get("sentence", "")
        for j, gt in enumerate(ground_truth):
            gt_sentence = gt.get("sentence", "")
            sim = sentence_similarity(f_sentence, gt_sentence)
            scores.append((sim, i, j))

    scores.sort(reverse=True)
    for sim, i, j in scores:
        if i in used_f or j in used_gt:
            continue
        if sim >= threshold:
            matched.append({
                "finding": findings[i],
                "ground_truth": ground_truth[j],
                "similarity": round(sim, 3),
            })
            used_f.add(i)
            used_gt.add(j)

    unmatched_findings = [f for i, f in enumerate(findings) if i not in used_f]
    missed_gt = [gt for j, gt in enumerate(ground_truth) if j not in used_gt]

    return matched, unmatched_findings, missed_gt


def compute_metrics(matched, unmatched_findings, missed_gt, total_gt):
    """Compute precision, recall, F1."""
    tp = len(matched)
    fp = len(unmatched_findings)
    fn = len(missed_gt)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1_score": round(f1, 3),
    }


def build_pipeline():
    """Build and compile the LangGraph pipeline."""
    workflow = StateGraph(AgentStateParallel)
    workflow.add_node('sec_misleading_detect', sec_misleading_detect)
    workflow.add_node('sec_misleading_ask', sec_misleading_ask)
    workflow.add_node('sec_misleading_flag', sec_misleading_flag)
    workflow.add_edge(START, 'sec_misleading_detect')
    workflow.add_edge('sec_misleading_detect', 'sec_misleading_ask')
    workflow.add_edge('sec_misleading_ask', 'sec_misleading_flag')
    workflow.add_edge('sec_misleading_flag', END)
    return workflow.compile()


# --- Sidebar ---
with st.sidebar:
    st.header("Settings")
    model = st.text_input(
        "Model",
        value=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
    )
    api_key = st.text_input(
        "API Key",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
        type="password",
    )
    match_threshold = st.slider(
        "Sentence match threshold",
        min_value=0.3, max_value=0.9, value=0.5, step=0.05,
        help="Fuzzy match threshold for matching findings to ground truth",
    )
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
    if model:
        os.environ["ANTHROPIC_MODEL"] = model

    st.divider()
    st.markdown("**Collections**")
    st.code("READ:  test_documents, ground_truth\nWRITE: cascade_bench_runs,\n       cascade_bench_results", language=None)

# --- Load test documents with ground truth ---
test_docs = list(db["test_documents"].find({}, {"filename": 1, "_id": 1}))
ground_truth_all = list(db["ground_truth"].find({"is_active": True}))

# Build mapping: TC ID -> ground truth entries
gt_by_tc = {}
for gt in ground_truth_all:
    tc = gt.get("TC Id", "")
    gt_by_tc.setdefault(tc, []).append(gt)

# Build list of documents that have ground truth
docs_with_gt = []
for doc in test_docs:
    tc_id = extract_tc_id(doc["filename"])
    if tc_id and tc_id in gt_by_tc:
        docs_with_gt.append({
            "_id": doc["_id"],
            "filename": doc["filename"],
            "tc_id": tc_id,
            "n_expected": len(gt_by_tc[tc_id]),
        })

st.subheader("Test Documents")
st.info(f"{len(docs_with_gt)} documents with ground truth (out of {len(test_docs)} total)")

# Document selection
doc_options = {d["filename"]: d for d in docs_with_gt}
selected_filenames = st.multiselect(
    "Select documents to evaluate",
    options=list(doc_options.keys()),
    default=list(doc_options.keys()),
    format_func=lambda f: f"{doc_options[f]['tc_id']} — {f} ({doc_options[f]['n_expected']} expected)",
)

if selected_filenames and st.button("Run Evaluation", type="primary"):
    pipeline = build_pipeline()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    all_results = []
    overall_tp, overall_fp, overall_fn = 0, 0, 0

    progress = st.progress(0, text="Starting evaluation...")

    for idx, filename in enumerate(selected_filenames):
        doc_info = doc_options[filename]
        tc_id = doc_info["tc_id"]
        progress.progress(
            int((idx / len(selected_filenames)) * 100),
            text=f"Running {tc_id} — {filename}...",
        )

        # Fetch PDF binary from MongoDB
        full_doc = db["test_documents"].find_one({"_id": doc_info["_id"]})
        pdf_bytes = full_doc.get("file_data") or full_doc.get("content")

        if not pdf_bytes:
            st.warning(f"Skipping {filename}: no PDF data found")
            continue

        # Write to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        # Run pipeline
        initial_state = AgentStateParallel(
            pdf_path=tmp_path,
            Metadata={},  # type: ignore
            SEC_misleading_detect_artifact="",
            SEC_misleading_ask_artifact="",
            SEC_misleading_artifact="",
            SEC_misleading_token_data="",
        )

        try:
            result = pipeline.invoke(initial_state)
            detect_json = result.get("SEC_misleading_detect_artifact", "")
            ask_json = result.get("SEC_misleading_ask_artifact", "")
            flag_json = result.get("SEC_misleading_artifact", "")
            token_data = result.get("SEC_misleading_token_data", {})
        except Exception as e:
            st.error(f"Error on {filename}: {e}")
            os.unlink(tmp_path)
            continue

        os.unlink(tmp_path)

        # Parse outputs
        try:
            detect_data = json.loads(detect_json)
        except (json.JSONDecodeError, TypeError):
            detect_data = {"candidates": []}
        try:
            ask_data = json.loads(ask_json)
        except (json.JSONDecodeError, TypeError):
            ask_data = {"results": []}
        try:
            flag_data = json.loads(flag_json)
        except (json.JSONDecodeError, TypeError):
            flag_data = {"sections": []}

        # Get ground truth for this TC
        gt_entries = gt_by_tc.get(tc_id, [])

        # Match DETECT candidates against ground truth
        detect_candidates = detect_data.get("candidates", [])
        detect_matched, detect_extra, detect_missed = match_findings_to_ground_truth(
            detect_candidates, gt_entries, threshold=match_threshold
        )

        # Match final FLAG findings against ground truth
        flag_findings = flag_data.get("sections", [])
        flag_matched, flag_extra, flag_missed = match_findings_to_ground_truth(
            flag_findings, gt_entries, threshold=match_threshold
        )

        detect_metrics = compute_metrics(detect_matched, detect_extra, detect_missed, len(gt_entries))
        flag_metrics = compute_metrics(flag_matched, flag_extra, flag_missed, len(gt_entries))

        overall_tp += flag_metrics["true_positives"]
        overall_fp += flag_metrics["false_positives"]
        overall_fn += flag_metrics["false_negatives"]

        doc_result = {
            "run_id": run_id,
            "tc_id": tc_id,
            "filename": filename,
            "model": run_model,
            "timestamp": datetime.now(timezone.utc),
            "n_ground_truth": len(gt_entries),
            "detect": {
                "n_candidates": len(detect_candidates),
                "metrics": detect_metrics,
                "matched": [
                    {"similarity": m["similarity"], "sentence": m["finding"].get("sentence", "")}
                    for m in detect_matched
                ],
                "missed": [gt.get("sentence", "") for gt in detect_missed],
            },
            "ask": {
                "n_flagged": sum(1 for r in ask_data.get("results", []) if r.get("disposition") == "FLAG"),
                "n_cleared": sum(1 for r in ask_data.get("results", []) if r.get("disposition") == "CLEAR"),
            },
            "flag": {
                "n_findings": len(flag_findings),
                "metrics": flag_metrics,
                "matched": [
                    {"similarity": m["similarity"], "sentence": m["finding"].get("sentence", "")}
                    for m in flag_matched
                ],
                "missed": [gt.get("sentence", "") for gt in flag_missed],
                "extra": [f.get("sentence", "") for f in flag_extra],
            },
            "token_data": token_data if isinstance(token_data, dict) else {},
            "raw_detect": detect_json,
            "raw_ask": ask_json,
            "raw_flag": flag_json,
        }

        all_results.append(doc_result)

        # Store individual result in MongoDB
        db["cascade_bench_results"].insert_one(doc_result.copy())

    progress.progress(100, text="Evaluation complete!")

    # Store run summary
    overall_precision = overall_tp / (overall_tp + overall_fp) if (overall_tp + overall_fp) > 0 else 0
    overall_recall = overall_tp / (overall_tp + overall_fn) if (overall_tp + overall_fn) > 0 else 0
    overall_f1 = 2 * overall_precision * overall_recall / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0

    run_summary = {
        "run_id": run_id,
        "model": run_model,
        "timestamp": datetime.now(timezone.utc),
        "n_documents": len(all_results),
        "match_threshold": match_threshold,
        "overall_metrics": {
            "true_positives": overall_tp,
            "false_positives": overall_fp,
            "false_negatives": overall_fn,
            "precision": round(overall_precision, 3),
            "recall": round(overall_recall, 3),
            "f1_score": round(overall_f1, 3),
        },
    }
    db["cascade_bench_runs"].insert_one(run_summary.copy())

    # --- Display Results ---
    st.divider()
    st.subheader("Overall Results")

    col1, col2, col3 = st.columns(3)
    col1.metric("Precision", f"{overall_precision:.1%}")
    col2.metric("Recall", f"{overall_recall:.1%}")
    col3.metric("F1 Score", f"{overall_f1:.1%}")

    col4, col5, col6 = st.columns(3)
    col4.metric("True Positives", overall_tp)
    col5.metric("False Positives", overall_fp)
    col6.metric("False Negatives", overall_fn)

    st.caption(f"Run ID: `{run_id}` | Model: `{run_model}` | Threshold: {match_threshold}")

    # Per-document breakdown
    st.divider()
    st.subheader("Per-Document Breakdown")

    for r in all_results:
        with st.expander(
            f"**{r['tc_id']}** — {r['filename']}  |  "
            f"Detect: {r['detect']['n_candidates']} → "
            f"Ask: {r['ask']['n_flagged']}F/{r['ask']['n_cleared']}C → "
            f"Flag: {r['flag']['n_findings']}  |  "
            f"F1={r['flag']['metrics']['f1_score']:.0%}",
            expanded=(r['flag']['metrics']['f1_score'] < 1.0),
        ):
            dc, fc = st.columns(2)

            with dc:
                st.markdown("**DETECT Stage**")
                dm = r["detect"]["metrics"]
                st.markdown(f"P={dm['precision']:.0%}  R={dm['recall']:.0%}  F1={dm['f1_score']:.0%}")
                if r["detect"]["missed"]:
                    st.markdown("**Missed by DETECT:**")
                    for s in r["detect"]["missed"]:
                        st.markdown(f"- _{s[:120]}..._" if len(s) > 120 else f"- _{s}_")

            with fc:
                st.markdown("**FLAG Stage (Final)**")
                fm = r["flag"]["metrics"]
                st.markdown(f"P={fm['precision']:.0%}  R={fm['recall']:.0%}  F1={fm['f1_score']:.0%}")
                if r["flag"]["missed"]:
                    st.markdown("**Missed (False Negatives):**")
                    for s in r["flag"]["missed"]:
                        st.markdown(f"- _{s[:120]}..._" if len(s) > 120 else f"- _{s}_")
                if r["flag"]["extra"]:
                    st.markdown("**Extra (False Positives):**")
                    for s in r["flag"]["extra"]:
                        st.markdown(f"- _{s[:120]}..._" if len(s) > 120 else f"- _{s}_")

            # Raw JSON
            with st.expander("Raw JSON", expanded=False):
                t1, t2, t3 = st.tabs(["detect", "ask", "flag"])
                with t1:
                    try:
                        st.json(json.loads(r["raw_detect"]))
                    except Exception:
                        st.code(r["raw_detect"])
                with t2:
                    try:
                        st.json(json.loads(r["raw_ask"]))
                    except Exception:
                        st.code(r["raw_ask"])
                with t3:
                    try:
                        st.json(json.loads(r["raw_flag"]))
                    except Exception:
                        st.code(r["raw_flag"])

# --- Historical runs ---
st.divider()
st.subheader("Previous Runs")
past_runs = list(db["cascade_bench_runs"].find().sort("timestamp", -1).limit(10))
if not past_runs:
    st.info("No previous evaluation runs found.")
else:
    for run in past_runs:
        m = run.get("overall_metrics", {})
        st.markdown(
            f"**{run.get('run_id')}** — {run.get('model')} — "
            f"{run.get('n_documents')} docs — "
            f"P={m.get('precision', 0):.0%} R={m.get('recall', 0):.0%} F1={m.get('f1_score', 0):.0%}"
        )
