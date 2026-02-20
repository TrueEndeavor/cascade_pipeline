"""Phase 0: Preliminary Evidence Extraction — broad 10-category scan.

Runs the teammate's extraction prompt (Prompt A) against the PDF.
Produces structured JSON with: disclaimers, performance_data, rankings_awards,
definitions, footnotes, data_sources, qualifications, audience_indicators,
temporal_context, visual_elements.

This output feeds into Phase 1 (Evidence Registry Builder) as a foundation.
"""

from dotenv import load_dotenv; load_dotenv()
import os
import base64
import json
import anthropic
from pipeline.state import PipelineState
from pipeline.prompts.preliminary_extraction import (
    PRELIMINARY_EXTRACTION_PROMPT,
    PRELIMINARY_EXTRACTION_JSON_INSTRUCTION,
)

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


def phase0_preliminary_extract(state: PipelineState) -> dict:
    """Run broad 10-category extraction against the PDF (Prompt A).

    This is the first node to touch the PDF. Its output is consumed by
    Phase 1 (Evidence Registry Builder) alongside the same PDF.
    """
    client = anthropic.Anthropic()

    pdf_path = state["pdf_path"]
    with open(pdf_path, "rb") as f:
        pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")

    prompt = PRELIMINARY_EXTRACTION_PROMPT + PRELIMINARY_EXTRACTION_JSON_INSTRUCTION

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=16384,
            temperature=0,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    }
                ]
            }]
        )
        artifact = response.content[0].text
        json.loads(artifact)  # validate JSON
        print("[PHASE 0] Preliminary extraction completed successfully")
    except json.JSONDecodeError:
        print("[PHASE 0] Warning: Response was not valid JSON, attempting extraction")
        raw = response.content[0].text
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            artifact = raw[start:end]
        else:
            artifact = '{"document_metadata": {}, "disclaimers": [], "performance_data": [], "rankings_awards": [], "definitions": [], "footnotes": [], "data_sources": [], "qualifications": [], "audience_indicators": {}, "temporal_context": {}, "visual_elements": []}'
    except Exception as e:
        print(f"[PHASE 0] Error: {e}")
        return {
            "preliminary_extraction": '{"document_metadata": {}, "disclaimers": [], "performance_data": [], "rankings_awards": [], "definitions": [], "footnotes": [], "data_sources": [], "qualifications": [], "audience_indicators": {}, "temporal_context": {}, "visual_elements": []}',
            "token_usage": {},
        }

    token_usage = {}
    if hasattr(response, "usage") and response.usage is not None:
        token_usage = {
            "phase0_input": response.usage.input_tokens,
            "phase0_output": response.usage.output_tokens,
        }

    return {
        "preliminary_extraction": artifact,
        "token_usage": token_usage,
    }
