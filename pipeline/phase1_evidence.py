"""Phase 1: Evidence Registry Builder — assessment + linking pass.

Receives the PDF AND the Phase 0 preliminary extraction JSON.
Sends both to Claude with modified Prompt B to produce the final
claims-based evidence registry.
"""

from dotenv import load_dotenv; load_dotenv()
import os
import base64
import json
import anthropic
from pipeline.state import PipelineState
from pipeline.prompts.evidence_registry import (
    EVIDENCE_REGISTRY_PROMPT,
    EVIDENCE_REGISTRY_JSON_INSTRUCTION,
)

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


def phase1_extract_evidence(state: PipelineState) -> dict:
    """Produce the final Evidence Registry by cross-referencing the PDF
    with the Phase 0 preliminary extraction.

    Sends THREE content blocks to Claude:
      1. The PDF document (base64)
      2. The preliminary extraction JSON (labeled text block)
      3. The modified Prompt B instructions
    """
    client = anthropic.Anthropic()

    pdf_path = state["pdf_path"]
    with open(pdf_path, "rb") as f:
        pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")

    preliminary = state.get("preliminary_extraction", "")

    # Build the prompt: Prompt B instructions + JSON output instruction
    prompt_text = EVIDENCE_REGISTRY_PROMPT + EVIDENCE_REGISTRY_JSON_INSTRUCTION

    # Construct message content blocks
    content_blocks = [
        # Block 1: Source PDF
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": pdf_data,
            },
        },
    ]

    # Block 2: Preliminary extraction (if available)
    if preliminary and preliminary.strip():
        content_blocks.append({
            "type": "text",
            "text": (
                "═══════════════════════════════════════════════════════════════\n"
                "PRELIMINARY EXTRACTION (from prior pass — INPUT 2)\n"
                "═══════════════════════════════════════════════════════════════\n\n"
                + preliminary
            ),
        })

    # Block 3: The assessment + linking prompt
    content_blocks.append({
        "type": "text",
        "text": prompt_text,
    })

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=16384,
            temperature=0,
            messages=[{
                "role": "user",
                "content": content_blocks,
            }]
        )
        artifact = response.content[0].text
        json.loads(artifact)  # validate JSON
        print("[PHASE 1] Evidence Registry built successfully (2-input pass)")
    except json.JSONDecodeError:
        print("[PHASE 1] Warning: Response was not valid JSON, attempting extraction")
        raw = response.content[0].text
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            artifact = raw[start:end]
        else:
            artifact = '{"registry": {"meta": {}, "claims": [], "contradictions": [], "coverage_gaps": []}}'
    except Exception as e:
        print(f"[PHASE 1] Error: {e}")
        return {
            "evidence_registry": '{"registry": {"meta": {}, "claims": [], "contradictions": [], "coverage_gaps": []}}',
            "token_usage": state.get("token_usage", {}),
        }

    # Merge token usage with Phase 0 data
    existing_usage = state.get("token_usage", {}) or {}
    if hasattr(response, "usage") and response.usage is not None:
        existing_usage["phase1_input"] = response.usage.input_tokens
        existing_usage["phase1_output"] = response.usage.output_tokens

    return {
        "evidence_registry": artifact,
        "token_usage": existing_usage,
    }
