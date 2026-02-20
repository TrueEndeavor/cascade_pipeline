"""Phase 3: Validation + Final Report — works against Evidence Registry + candidates (no PDF)."""

from dotenv import load_dotenv; load_dotenv()
import os
import json
import anthropic
from datetime import datetime, timezone
from pipeline.state import PipelineState
from pipeline.prompts.theme1_validate import (
    THEME1_VALIDATE_PROMPT,
    THEME1_VALIDATE_JSON_INSTRUCTION,
)

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


def phase3_theme1_validate(state: PipelineState) -> dict:
    """Validate Theme 1 candidates and produce final structured findings.

    Receives the Evidence Registry and Phase 2 candidates.
    Applies the 6-check diagnostic protocol, then generates final
    ComplianceJSON-compatible output for FLAG dispositions.
    No PDF — works entirely from text.
    """
    candidates_json = state.get("theme1_candidates", "")
    registry_json = state.get("evidence_registry", "")

    if not candidates_json or candidates_json == '{"candidates": []}':
        print("[PHASE 3] No candidates to validate")
        return {
            "theme1_findings": '{"diagnostics": [], "sections": []}',
        }

    # Parse registry to get the claims the candidates reference
    try:
        registry_data = json.loads(registry_json)
        registry = registry_data.get("registry", registry_data)
    except (json.JSONDecodeError, TypeError):
        registry = {"claims": [], "contradictions": []}

    # Build a lookup of claim_id → full claim for the validator
    claim_lookup = {}
    for claim in registry.get("claims", []):
        claim_lookup[claim["claim_id"]] = claim

    # Parse candidates and enrich with full registry entries
    try:
        candidates_data = json.loads(candidates_json)
        candidates = candidates_data.get("candidates", [])
    except (json.JSONDecodeError, TypeError):
        candidates = []

    if not candidates:
        print("[PHASE 3] No candidates after parsing")
        return {
            "theme1_findings": '{"diagnostics": [], "sections": []}',
        }

    # For each candidate, attach the full registry entry so the validator
    # can see support details, flags, etc.
    enriched_candidates = []
    for candidate in candidates:
        claim_id = candidate.get("claim_id", "")
        full_claim = claim_lookup.get(claim_id, {})
        enriched = {
            **candidate,
            "registry_entry": full_claim,
        }
        enriched_candidates.append(enriched)

    enriched_text = json.dumps(enriched_candidates, indent=2)

    # Also include contradictions for context
    contradictions = registry.get("contradictions", [])
    contradictions_text = json.dumps(contradictions, indent=2) if contradictions else "[]"

    prompt = f"""{THEME1_VALIDATE_PROMPT}

═══════════════════════════════════════════════════════════════
CANDIDATES TO VALIDATE (enriched with registry entries)
═══════════════════════════════════════════════════════════════

{enriched_text}

═══════════════════════════════════════════════════════════════
CONTRADICTIONS FROM REGISTRY
═══════════════════════════════════════════════════════════════

{contradictions_text}

### Today's date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}

{THEME1_VALIDATE_JSON_INSTRUCTION}"""

    client = anthropic.Anthropic()

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=8192,
            temperature=0,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        artifact = response.content[0].text
        json.loads(artifact)  # validate JSON
        print("[PHASE 3] Validation and findings complete")
    except json.JSONDecodeError:
        print("[PHASE 3] Warning: Response was not valid JSON, attempting extraction")
        raw = response.content[0].text
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            artifact = raw[start:end]
        else:
            artifact = '{"diagnostics": [], "sections": []}'
    except Exception as e:
        print(f"[PHASE 3] Error: {e}")
        return {
            "theme1_findings": '{"diagnostics": [], "sections": []}',
        }

    # Accumulate token tracking
    prev_tokens = state.get("token_usage") or {}
    token_usage = {
        **prev_tokens,
        "phase3_input": response.usage.input_tokens,
        "phase3_output": response.usage.output_tokens,
    }

    return {
        "theme1_findings": artifact,
        "token_usage": token_usage,
    }
