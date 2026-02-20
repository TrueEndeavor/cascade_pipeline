"""
SEC Cascade Pipeline — Standalone Runner (LangGraph)

Legacy:   DETECT → ASK → FLAG  (3 PDF uploads)
Evidence: PHASE1 → CHECKER → PHASE2 → PHASE3  (1 PDF upload)

Usage:
    python main.py /path/to/document.pdf                    # legacy pipeline
    python main.py /path/to/document.pdf --pipeline evidence # new pipeline
    python main.py --pipeline evidence                       # uses PDF_PATH from .env
"""

import sys
import os
import json
import argparse
from dotenv import load_dotenv; load_dotenv()

from langgraph.graph import StateGraph, START, END
from node_config import AgentStateParallel
from node_detect import sec_misleading_detect
from node_ask import sec_misleading_ask
from node_flag import sec_misleading_flag


def run_workflow(pdf_path: str):
    workflow = StateGraph(AgentStateParallel)

    # Add cascade nodes
    workflow.add_node('sec_misleading_detect', sec_misleading_detect)
    workflow.add_node('sec_misleading_ask', sec_misleading_ask)
    workflow.add_node('sec_misleading_flag', sec_misleading_flag)

    # Chain: START → detect → ask → flag → END
    workflow.add_edge(START, 'sec_misleading_detect')
    workflow.add_edge('sec_misleading_detect', 'sec_misleading_ask')
    workflow.add_edge('sec_misleading_ask', 'sec_misleading_flag')
    workflow.add_edge('sec_misleading_flag', END)

    app = workflow.compile()

    initial_state = AgentStateParallel(
        pdf_path=pdf_path,
        Metadata={},  # type: ignore
        SEC_misleading_detect_artifact="",
        SEC_misleading_ask_artifact="",
        SEC_misleading_artifact="",
        SEC_misleading_token_data="",
    )

    print(f"\n{'='*60}")
    print(f"SEC Cascade Pipeline (LangGraph)")
    print(f"Document: {pdf_path}")
    print(f"Model:    {os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')}")
    print(f"{'='*60}\n")

    result = app.invoke(initial_state)

    # --- Save intermediate outputs ---
    os.makedirs("output", exist_ok=True)

    detect_json = result.get("SEC_misleading_detect_artifact", "")
    ask_json = result.get("SEC_misleading_ask_artifact", "")
    flag_json = result.get("SEC_misleading_artifact", "")

    with open("output/1_detect.json", "w") as f:
        f.write(detect_json)
    with open("output/2_ask.json", "w") as f:
        f.write(ask_json)
    with open("output/3_flag.json", "w") as f:
        f.write(flag_json)

    # --- Summary ---
    try:
        n_candidates = len(json.loads(detect_json).get("candidates", []))
    except (json.JSONDecodeError, TypeError):
        n_candidates = "?"
    try:
        ask_results = json.loads(ask_json).get("results", [])
        n_flagged = sum(1 for r in ask_results if r.get("disposition") == "FLAG")
        n_cleared = sum(1 for r in ask_results if r.get("disposition") == "CLEAR")
    except (json.JSONDecodeError, TypeError):
        n_flagged, n_cleared = "?", "?"
    try:
        n_findings = len(json.loads(flag_json).get("sections", []))
    except (json.JSONDecodeError, TypeError):
        n_findings = "?"

    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE")
    print(f"  Candidates detected : {n_candidates}")
    print(f"  Survived ASK review : {n_flagged} FLAG / {n_cleared} CLEAR")
    print(f"  Final findings      : {n_findings}")
    print(f"  Token usage         : {result.get('SEC_misleading_token_data')}")
    print(f"\nOutputs saved to output/")
    print(f"{'='*60}\n")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SEC Cascade Compliance Pipeline")
    parser.add_argument("pdf", nargs="?", default=None, help="Path to PDF document")
    parser.add_argument(
        "--pipeline",
        choices=["legacy", "evidence"],
        default="legacy",
        help="Pipeline to run: legacy (detect→ask→flag) or evidence (registry-based)",
    )
    args = parser.parse_args()

    path = args.pdf or os.getenv("PDF_PATH")

    if not path:
        print("Error: Provide a local PDF path as argument or set PDF_PATH in .env")
        sys.exit(1)

    if not os.path.isfile(path):
        print(f"Error: File not found: {path}")
        sys.exit(1)

    if args.pipeline == "evidence":
        from pipeline.runner import run_evidence_pipeline
        run_evidence_pipeline(path)
    else:
        run_workflow(path)
