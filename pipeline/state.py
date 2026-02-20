"""LangGraph state definition for the Evidence Registry pipeline."""

from typing import TypedDict, Any, Annotated


def _replace(current: str, new: str) -> str:
    return new or current


def _replace_any(current: Any, new: Any) -> Any:
    return new if new is not None else current


class PipelineState(TypedDict):
    pdf_path: Annotated[str, _replace]
    preliminary_extraction: Annotated[str, _replace]   # Phase 0 JSON (10-category extraction)
    evidence_registry: Annotated[str, _replace]        # Phase 1 JSON output (claims + contradictions)
    checker_report: Annotated[str, _replace]            # Registry checker report JSON
    theme1_candidates: Annotated[str, _replace]         # Phase 2 JSON output
    theme1_findings: Annotated[str, _replace]           # Phase 3 JSON output (ComplianceJSON)
    token_usage: Annotated[Any, _replace_any]           # Cumulative token tracking
