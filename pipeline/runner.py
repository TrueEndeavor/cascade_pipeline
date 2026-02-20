"""Evidence Registry pipeline — LangGraph graph builder and CLI runner.

Graph: START → phase0_preliminary → phase1_evidence → registry_checker → phase2_detect → phase3_validate → END
"""

import sys
import os
import json
from dotenv import load_dotenv; load_dotenv()

from langgraph.graph import StateGraph, START, END
from pipeline.state import PipelineState
from pipeline.phase0_preliminary import phase0_preliminary_extract
from pipeline.phase1_evidence import phase1_extract_evidence
from pipeline.registry_checker import validate_registry
from pipeline.phase2_detect import phase2_theme1_detect
from pipeline.phase3_validate import phase3_theme1_validate


def build_evidence_pipeline():
    """Build the 5-node Evidence Registry pipeline."""
    workflow = StateGraph(PipelineState)

    workflow.add_node("phase0_preliminary", phase0_preliminary_extract)
    workflow.add_node("phase1_evidence", phase1_extract_evidence)
    workflow.add_node("registry_checker", validate_registry)
    workflow.add_node("phase2_detect", phase2_theme1_detect)
    workflow.add_node("phase3_validate", phase3_theme1_validate)

    workflow.add_edge(START, "phase0_preliminary")
    workflow.add_edge("phase0_preliminary", "phase1_evidence")
    workflow.add_edge("phase1_evidence", "registry_checker")
    workflow.add_edge("registry_checker", "phase2_detect")
    workflow.add_edge("phase2_detect", "phase3_validate")
    workflow.add_edge("phase3_validate", END)

    return workflow.compile()


def run_evidence_pipeline(pdf_path: str) -> dict:
    """Run the full evidence pipeline and save intermediate outputs."""
    app = build_evidence_pipeline()

    initial_state = PipelineState(
        pdf_path=pdf_path,
        preliminary_extraction="",
        evidence_registry="",
        checker_report="",
        theme1_candidates="",
        theme1_findings="",
        token_usage={},
    )

    print(f"\n{'='*60}")
    print(f"SEC Cascade v2 — Evidence Registry Pipeline")
    print(f"Document: {pdf_path}")
    print(f"Model:    {os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')}")
    print(f"{'='*60}\n")

    result = app.invoke(initial_state)

    # Save intermediate outputs
    output_dir = "output/v2"
    os.makedirs(output_dir, exist_ok=True)

    preliminary_json = result.get("preliminary_extraction", "")
    registry_json = result.get("evidence_registry", "")
    checker_json = result.get("checker_report", "")
    candidates_json = result.get("theme1_candidates", "")
    findings_json = result.get("theme1_findings", "")

    # Pretty-print JSON outputs
    for filename, content in [
        ("0_preliminary_extraction.json", preliminary_json),
        ("0.5_evidence_registry.json", registry_json),
        ("0.75_checker_report.json", checker_json),
        ("1_candidates.json", candidates_json),
        ("2_findings.json", findings_json),
    ]:
        filepath = os.path.join(output_dir, filename)
        try:
            parsed = json.loads(content)
            with open(filepath, "w") as f:
                json.dump(parsed, f, indent=2)
        except (json.JSONDecodeError, TypeError):
            with open(filepath, "w") as f:
                f.write(content or "")

    # Summary
    try:
        prelim = json.loads(preliminary_json)
        n_disclaimers = len(prelim.get("disclaimers", []))
        n_performance = len(prelim.get("performance_data", []))
        n_footnotes = len(prelim.get("footnotes", []))
        prelim_total = sum(
            len(prelim.get(k, []))
            for k in ("disclaimers", "performance_data", "rankings_awards",
                       "definitions", "footnotes", "data_sources",
                       "qualifications", "visual_elements")
            if isinstance(prelim.get(k), list)
        )
    except (json.JSONDecodeError, TypeError):
        n_disclaimers, n_performance, n_footnotes, prelim_total = "?", "?", "?", "?"

    try:
        registry = json.loads(registry_json)
        reg = registry.get("registry", registry)
        n_claims = len(reg.get("claims", []))
        n_contradictions = len(reg.get("contradictions", []))
        n_gaps = len(reg.get("coverage_gaps", []))
    except (json.JSONDecodeError, TypeError):
        n_claims, n_contradictions, n_gaps = "?", "?", "?"

    try:
        checker = json.loads(checker_json)
        coverage = checker.get("coverage_score", "?")
        checker_passed = checker.get("passed", "?")
        n_issues = len(checker.get("issues", []))
    except (json.JSONDecodeError, TypeError):
        coverage, checker_passed, n_issues = "?", "?", "?"

    try:
        candidates = json.loads(candidates_json)
        n_candidates = len(candidates.get("candidates", []))
    except (json.JSONDecodeError, TypeError):
        n_candidates = "?"

    try:
        findings = json.loads(findings_json)
        n_diagnostics = len(findings.get("diagnostics", []))
        n_flagged = sum(1 for d in findings.get("diagnostics", [])
                        if d.get("disposition") == "FLAG")
        n_cleared = sum(1 for d in findings.get("diagnostics", [])
                        if d.get("disposition") == "CLEAR")
        n_sections = len(findings.get("sections", []))
    except (json.JSONDecodeError, TypeError):
        n_diagnostics, n_flagged, n_cleared, n_sections = "?", "?", "?", "?"

    token_usage = result.get("token_usage", {})

    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE")
    print(f"  Phase 0 — Preliminary : {prelim_total} items ({n_disclaimers} disclaimers, {n_performance} perf, {n_footnotes} footnotes)")
    print(f"  Phase 1 — Registry    : {n_claims} claims, {n_contradictions} contradictions, {n_gaps} coverage gaps")
    print(f"  Checker               : coverage={coverage}, passed={checker_passed}, issues={n_issues}")
    print(f"  Phase 2 — Candidates  : {n_candidates}")
    print(f"  Phase 3 — Diagnostics : {n_flagged} FLAG / {n_cleared} CLEAR")
    print(f"  Final findings        : {n_sections}")
    print(f"  Token usage           : {token_usage}")
    print(f"\nOutputs saved to {output_dir}/")
    print(f"{'='*60}\n")

    return result


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = os.getenv("PDF_PATH")

    if not path:
        print("Error: Provide a local PDF path as argument or set PDF_PATH in .env")
        sys.exit(1)

    if not os.path.isfile(path):
        print(f"Error: File not found: {path}")
        sys.exit(1)

    run_evidence_pipeline(path)
