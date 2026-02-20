"""Deterministic post-extraction validator for the Evidence Registry.

Runs after Phase 1 (no LLM). The extractor is aggressive; the checker is skeptical.
Produces an auditable coverage report without blocking the pipeline.
"""

import json
import re
import fitz  # PyMuPDF
from pipeline.state import PipelineState


# Standard disclaimer phrases expected in financial marketing documents.
# If a phrase appears in the source PDF, it should be captured in the registry.
STANDARD_DISCLAIMERS = [
    "past performance",
    "no guarantee",
    "not FDIC insured",
    "may lose value",
    "subject to change",
    "not a deposit",
    "not insured by any federal government agency",
    "prospectus",
    "read the prospectus",
    "investment return and principal value",
]

# Canonical BDC/SEC statutory disclaimer fragments.
# Used for negation checking — these phrases MUST contain negation words.
NEGATION_CRITICAL_PHRASES = [
    {
        "canonical": "neither the securities and exchange commission nor any state securities regulator has approved or disapproved",
        "required_negations": ["neither", "nor"],
        "description": "SEC/FINRA statutory disclaimer",
    },
    {
        "canonical": "has not approved or disapproved",
        "required_negations": ["not"],
        "description": "SEC approval negation",
    },
    {
        "canonical": "no guarantee",
        "required_negations": ["no"],
        "description": "No-guarantee language",
    },
]

# Regex patterns for extracting numbers from text
NUMBER_PATTERNS = [
    r'\d+\.?\d*\s*%',           # percentages: 5%, 11.4%
    r'\$\s*[\d,]+\.?\d*',       # dollar amounts: $50B, $1,000
    r'\d{1,2}/\d{1,2}/\d{2,4}', # dates: 12/31/2024
    r'\b\d{4}\b',               # years: 2024
    r'\d+\.?\d*\s*(?:bps|bp)',  # basis points: 50 bps
    r'\d+\.?\d*x',              # multiples: 1.5x
]


def _extract_pdf_text_by_page(pdf_path: str) -> dict[int, str]:
    """Extract text from each page of the PDF using PyMuPDF."""
    pages = {}
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        pages[i + 1] = page.get_text()
    doc.close()
    return pages


def _extract_numbers(text: str) -> set[str]:
    """Extract all number-like tokens from text."""
    numbers = set()
    for pattern in NUMBER_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            numbers.add(match.group().strip())
    return numbers


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace for fuzzy matching."""
    return re.sub(r'\s+', ' ', text.lower().strip())


def _phrase_in_text(phrase: str, text: str) -> bool:
    """Check if a normalized phrase appears in normalized text."""
    return _normalize(phrase) in _normalize(text)


def _check_structural_coverage(registry: dict, total_pages: int) -> list[dict]:
    """Check that every page has at least one claim."""
    issues = []
    claimed_pages = set()
    for claim in registry.get("claims", []):
        page_str = str(claim.get("page", ""))
        # Handle page ranges like "1-2" or single pages
        for part in re.split(r'[-,]', page_str):
            part = part.strip()
            if part.isdigit():
                claimed_pages.add(int(part))

    for p in range(1, total_pages + 1):
        if p not in claimed_pages:
            issues.append({"type": "MISSING_PAGE", "page": p})

    return issues


def _check_numerical_coverage(page_texts: dict[int, str], registry: dict) -> tuple[list[dict], float]:
    """Extract numbers from source and verify they appear in the registry."""
    issues = []

    # All numbers from source
    source_numbers = set()
    for page_num, text in page_texts.items():
        for num in _extract_numbers(text):
            source_numbers.add(num)

    if not source_numbers:
        return issues, 1.0

    # All numbers from registry claims
    registry_text_parts = []
    for claim in registry.get("claims", []):
        registry_text_parts.append(claim.get("exact_text", "") or "")
        support = claim.get("support", {})
        if support and support.get("text"):
            registry_text_parts.append(support["text"])
    registry_combined = " ".join(registry_text_parts)
    registry_numbers = _extract_numbers(registry_combined)

    # Find orphan numbers
    orphan_numbers = source_numbers - registry_numbers
    for num in orphan_numbers:
        issues.append({"type": "ORPHAN_NUMBER", "number": num})

    coverage = 1.0 - (len(orphan_numbers) / len(source_numbers)) if source_numbers else 1.0
    return issues, coverage


def _check_disclaimer_coverage(page_texts: dict[int, str], registry: dict) -> list[dict]:
    """Check that standard disclaimer phrases from the source are captured."""
    issues = []
    full_source = " ".join(page_texts.values())

    # All text from registry claims
    registry_text_parts = []
    for claim in registry.get("claims", []):
        registry_text_parts.append(claim.get("exact_text", "") or "")
        support = claim.get("support", {})
        if support and support.get("text"):
            registry_text_parts.append(support["text"])
    registry_combined = " ".join(registry_text_parts)

    for phrase in STANDARD_DISCLAIMERS:
        if _phrase_in_text(phrase, full_source):
            if not _phrase_in_text(phrase, registry_combined):
                issues.append({"type": "MISSED_DISCLAIMER", "phrase": phrase})

    return issues


def _check_negation_integrity(page_texts: dict[int, str], registry: dict) -> list[dict]:
    """Check for garbled disclaimers — missing negation words.

    This is the single highest-value check. Corrupted disclaimers with missing
    'not'/'neither'/'nor' have been the most critical findings historically.
    """
    issues = []

    # Collect all disclaimer-type claims from registry
    disclaimer_texts = []
    for claim in registry.get("claims", []):
        if claim.get("claim_type") == "disclosures":
            disclaimer_texts.append(claim.get("exact_text", "") or "")
        support = claim.get("support", {})
        if support and support.get("text"):
            disclaimer_texts.append(support["text"])

    combined_disclaimers = " ".join(disclaimer_texts)

    for check in NEGATION_CRITICAL_PHRASES:
        canonical = check["canonical"]
        # Check if any form of this phrase appears in the source
        full_source = " ".join(page_texts.values())
        source_norm = _normalize(full_source)

        # Look for fragments of the canonical phrase in source (without negation)
        # e.g., "securities and exchange commission" should appear near "approved"
        key_fragments = [w for w in canonical.split() if len(w) > 3
                         and w not in check["required_negations"]]
        fragment_pattern = ".*".join(re.escape(f) for f in key_fragments[:3])

        if re.search(fragment_pattern, source_norm):
            # The phrase exists in the source. Now check if negation words are
            # present in the registry's captured version.
            registry_norm = _normalize(combined_disclaimers)
            for neg_word in check["required_negations"]:
                # Check if the negation appears near the key fragments in registry
                if not _phrase_in_text(neg_word, registry_norm):
                    # Could mean the registry faithfully captured garbled text
                    # (which is correct!) or the registry missed the disclaimer.
                    # Check if it's also missing in source — if so, the registry
                    # correctly captured the garbled version.
                    if _phrase_in_text(neg_word, source_norm):
                        # Negation IS in source but NOT in registry → registry missed it
                        issues.append({
                            "type": "GARBLED_DISCLAIMER",
                            "description": check["description"],
                            "expected_negation": neg_word,
                            "note": "Negation present in source but missing from registry capture",
                        })
                    # If negation is missing from BOTH source and registry,
                    # the registry correctly captured the garbled original.
                    # That's a finding for Phase 2, not a checker issue.

    return issues


def _check_contradiction_consistency(registry: dict) -> list[dict]:
    """Verify flag-contradiction cross-references are consistent."""
    issues = []

    claim_ids = {c["claim_id"] for c in registry.get("claims", [])}
    contradictions = registry.get("contradictions", [])
    contradiction_claim_ids = set()
    for con in contradictions:
        for cid in con.get("claim_ids", []):
            contradiction_claim_ids.add(cid)
            if cid not in claim_ids:
                issues.append({
                    "type": "INVALID_REFERENCE",
                    "contradiction_id": con.get("contradiction_id"),
                    "missing_claim_id": cid,
                })

    # Claims flagged INTERNAL_CONTRADICTION should appear in contradictions
    for claim in registry.get("claims", []):
        flags = claim.get("flags", []) or []
        if "INTERNAL_CONTRADICTION" in flags:
            if claim["claim_id"] not in contradiction_claim_ids:
                issues.append({
                    "type": "ORPHAN_FLAG",
                    "claim_id": claim["claim_id"],
                    "flag": "INTERNAL_CONTRADICTION",
                })

    return issues


def validate_registry(state: PipelineState) -> dict:
    """Run the deterministic registry checker as a LangGraph node.

    Takes the PDF path and evidence_registry from state,
    returns checker_report as JSON string.
    """
    pdf_path = state["pdf_path"]
    registry_json = state.get("evidence_registry", "")

    try:
        registry_data = json.loads(registry_json)
    except (json.JSONDecodeError, TypeError):
        print("[CHECKER] Could not parse evidence registry JSON")
        report = {
            "coverage_score": 0.0,
            "issues": [{"type": "PARSE_ERROR", "detail": "Registry JSON is invalid"}],
            "passed": False,
        }
        return {"checker_report": json.dumps(report, indent=2)}

    registry = registry_data.get("registry", registry_data)

    # Extract PDF text by page
    try:
        page_texts = _extract_pdf_text_by_page(pdf_path)
    except Exception as e:
        print(f"[CHECKER] Could not extract PDF text: {e}")
        report = {
            "coverage_score": 0.0,
            "issues": [{"type": "PDF_EXTRACT_ERROR", "detail": str(e)}],
            "passed": False,
        }
        return {"checker_report": json.dumps(report, indent=2)}

    total_pages = len(page_texts)
    all_issues = []

    # 1. Structural coverage
    all_issues.extend(_check_structural_coverage(registry, total_pages))

    # 2. Numerical audit
    num_issues, coverage_score = _check_numerical_coverage(page_texts, registry)
    all_issues.extend(num_issues)

    # 3. Disclaimer pattern matching
    all_issues.extend(_check_disclaimer_coverage(page_texts, registry))

    # 4. Negation integrity (highest-value check)
    all_issues.extend(_check_negation_integrity(page_texts, registry))

    # 5. Contradiction consistency
    all_issues.extend(_check_contradiction_consistency(registry))

    # Determine pass/fail
    critical_types = {"GARBLED_DISCLAIMER", "PARSE_ERROR", "PDF_EXTRACT_ERROR"}
    has_critical = any(i["type"] in critical_types for i in all_issues)
    passed = coverage_score >= 0.7 and not has_critical

    report = {
        "coverage_score": round(coverage_score, 3),
        "total_pages": total_pages,
        "total_claims": len(registry.get("claims", [])),
        "total_contradictions": len(registry.get("contradictions", [])),
        "issues": all_issues,
        "issue_summary": {},
        "passed": passed,
    }

    # Build issue summary
    for issue in all_issues:
        itype = issue["type"]
        report["issue_summary"][itype] = report["issue_summary"].get(itype, 0) + 1

    status = "PASSED" if passed else "WARNINGS"
    print(f"[CHECKER] {status} — coverage: {coverage_score:.1%}, "
          f"issues: {len(all_issues)}, claims: {report['total_claims']}")

    return {"checker_report": json.dumps(report, indent=2)}
