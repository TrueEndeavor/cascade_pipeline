"""Phase 2: Theme 1 Detection — works against Evidence Registry (no PDF)."""

from dotenv import load_dotenv; load_dotenv()
import os
import json
import anthropic
from pipeline.state import PipelineState
from pipeline.prompts.theme1_detect import (
    THEME1_DETECT_PROMPT,
    THEME1_DETECT_JSON_INSTRUCTION,
)

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# Flags that are relevant to Theme 1 regardless of claim_type
THEME1_RELEVANT_FLAGS = {
    "GUARANTEED_LANGUAGE",
    "REGULATORY_ERROR",
    "NO_SUPPORT",
    "INTERNAL_CONTRADICTION",
    "MISSING_SOURCE",
    "PROXIMITY_FAIL",
    "PEER_SET_UNDEFINED",
    "STALE_DATA",
    "WINNER_VS_FINALIST",
    "FEE_WAIVER_IMPACT",
    "VISUAL_IMPLICATION",
    "PLACEHOLDER_DATA",
}


def _filter_claims_for_theme1(registry: dict) -> tuple[list[dict], list[dict]]:
    """Filter registry claims relevant to Theme 1.

    Returns:
        (filtered_claims, relevant_contradictions)
    """
    claims = registry.get("claims", [])
    contradictions = registry.get("contradictions", [])

    # Primary: claims typed as misleading_exaggerated
    # Secondary: claims from any type that carry Theme 1-relevant flags
    filtered = []
    filtered_ids = set()

    for claim in claims:
        claim_type = claim.get("claim_type", "")
        flags = set(claim.get("flags", []) or [])

        if claim_type == "misleading_exaggerated":
            filtered.append(claim)
            filtered_ids.add(claim["claim_id"])
        elif flags & THEME1_RELEVANT_FLAGS:
            filtered.append(claim)
            filtered_ids.add(claim["claim_id"])

    # Include contradictions that reference any filtered claim
    relevant_contradictions = []
    for con in contradictions:
        con_claim_ids = set(con.get("claim_ids", []))
        if con_claim_ids & filtered_ids:
            relevant_contradictions.append(con)

    return filtered, relevant_contradictions


def phase2_theme1_detect(state: PipelineState) -> dict:
    """Detect Theme 1 violations from Evidence Registry.

    Filters claims relevant to Theme 1, sends them with the detection
    prompt to Claude (text only, no PDF).
    """
    registry_json = state.get("evidence_registry", "")
    if not registry_json:
        print("[PHASE 2] No evidence registry — skipping detection")
        return {"theme1_candidates": '{"candidates": []}'}

    try:
        registry_data = json.loads(registry_json)
    except (json.JSONDecodeError, TypeError):
        print("[PHASE 2] Could not parse evidence registry JSON")
        return {"theme1_candidates": '{"candidates": []}'}

    registry = registry_data.get("registry", registry_data)
    filtered_claims, relevant_contradictions = _filter_claims_for_theme1(registry)

    if not filtered_claims:
        print("[PHASE 2] No claims relevant to Theme 1")
        return {"theme1_candidates": '{"candidates": []}'}

    # Build the input payload for the prompt
    claims_input = {
        "meta": registry.get("meta", {}),
        "claims": filtered_claims,
        "contradictions": relevant_contradictions,
    }
    claims_text = json.dumps(claims_input, indent=2)

    prompt = f"""{THEME1_DETECT_PROMPT}

═══════════════════════════════════════════════════════════════
EVIDENCE REGISTRY CLAIMS (Theme 1 relevant)
═══════════════════════════════════════════════════════════════

{claims_text}

{THEME1_DETECT_JSON_INSTRUCTION}"""

    client = anthropic.Anthropic()

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=8192,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        artifact = response.content[0].text
        json.loads(artifact)  # validate JSON
        print(f"[PHASE 2] Theme 1 candidates identified")
    except json.JSONDecodeError:
        print("[PHASE 2] Warning: Response was not valid JSON, attempting extraction")
        raw = response.content[0].text
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            artifact = raw[start:end]
        else:
            artifact = '{"candidates": []}'
    except Exception as e:
        print(f"[PHASE 2] Error: {e}")
        return {"theme1_candidates": '{"candidates": []}'}

    # Accumulate token tracking
    prev_tokens = state.get("token_usage") or {}
    token_usage = {
        **prev_tokens,
        "phase2_input": response.usage.input_tokens,
        "phase2_output": response.usage.output_tokens,
    }

    return {
        "theme1_candidates": artifact,
        "token_usage": token_usage,
    }
