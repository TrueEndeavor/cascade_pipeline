from dotenv import load_dotenv; load_dotenv()
import os
import base64
import json
import anthropic
from node_config import AgentStateParallel
from datetime import datetime, timezone
from models.compliance_output import ComplianceJSON

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


FLAG_PROMPT = """
You are a senior SEC compliance examiner producing final compliance findings for Theme 1: Misleading, Exaggerated, or Unsubstantiated Claims.

Below are verified compliance violations that have survived detection and diagnostic review. For each verified violation, produce the final structured output.

═══════════════════════════════════════════════════════════════
PRIORITY ORDERING
═══════════════════════════════════════════════════════════════

Order findings by severity within each page:
1. CRITICAL: False approval claims, corrupted/missing statutory disclaimers, accidental guarantee statements. These require immediate distribution halt.
2. HIGH: Missing negation words in disclaimers, materially misleading data errors, promissory outcome language.
3. MEDIUM: Unsubstantiated factual claims, unbalanced benefit/risk presentation, overstated superlatives.
4. LOW: Vague terminology, minor audience-appropriateness issues.

═══════════════════════════════════════════════════════════════
RULES FOR EACH FINDING
═══════════════════════════════════════════════════════════════

1. SENTENCE: Must be the exact verbatim text from the document — read it EXACTLY as written, including any typos, corrupted text, or missing words. Include enough surrounding context to show whether hedging or qualifiers are present.

2. SUB_BUCKET: Assign exactly ONE sub-bucket from this list:
   - "1. Unsubstantiated or inadequately supported statements of fact"
   - "2. Promissory or certain-outcome language implying guaranteed results"
   - "3. Implied guarantees or certainty created through framing, tone, or contextual emphasis"
   - "4. Overstated, absolute, or best-in-class type claims lacking appropriate qualification"
   - "5. Unbalanced presentation of benefits without corresponding risks, limitations, or conditions"
   - "6. Exaggerated or amplified claims that materially overstate capability, experience, or outcomes"
   - "7. Vague, ambiguous, or undefined claims that prevent reasonable investor understanding"
   - "8. Audience-inappropriate language or complexity that creates a misleading impression"
   - "9. Unfair, deceptive, or unclear communications that could reasonably result in consumer or investor harm"
   - "10. ESG, impact, sustainability, or qualitative claims lacking clear definitions, scope, or evidentiary support"

3. CATEGORY: Must be "Misleading or Unsubstantiated Claims"

4. OBSERVATIONS: Must follow this structure:
   (a) What impression the statement creates for a reasonable investor
   (b) Why that impression is misleading, unsubstantiated, or unbalanced
   (c) What specific information is missing, overstated, corrupted, or factually incorrect
   For disclaimer/statutory violations: explicitly state the expected correct text vs. the actual text found.
   PROHIBITED phrases in observations: "marketing best practice", "tone issue", "sounds promotional", "could be clearer", "better phrasing"

5. RULE_CITATION: Cite the specific SEC Marketing Rule provision:
   - SB1: "SEC Marketing Rule 206(4)-1(a)(2)"
   - SB2: "SEC Marketing Rule 206(4)-1(a)(1)"
   - SB3: "SEC Marketing Rule 206(4)-1(a)(3)"
   - SB4: "SEC Marketing Rule 206(4)-1(a)(1)"
   - SB5: "SEC Marketing Rule 206(4)-1(a)(4)"
   - SB6: "SEC Marketing Rule 206(4)-1(a)(3)"
   - SB7: "SEC Marketing Rule 206(4)-1(a)(7)"
   - SB8: "SEC Marketing Rule 206(4)-1(a)(7)"
   - SB9: "SEC Marketing Rule 206(4)-1(a)(7)"
   - SB10: "SEC Marketing Rule 206(4)-1(a)(2)"

6. RECOMMENDATIONS: Each must state:
   (a) What's wrong — name the specific issue (e.g., "missing negation word 'no'", "corrupted growth figure", "certainty language about future Fed action")
   (b) Why it matters — tie to the regulatory concern
   (c) How to fix — a concrete, actionable edit with the exact corrected text

7. SUMMARY: One concise sentence describing the violation and its severity level (Critical/High/Medium/Low).

8. VISUAL COORDINATES: Use normalized 0-1000 scale for x/y. Tightly wrap the violating text.

If the verified findings list is empty, return {"sections": []}.

VERIFIED VIOLATIONS TO FINALIZE:
"""


FLAG_JSON_INSTRUCTION = """
IMPORTANT: You must respond with ONLY valid JSON matching this exact schema, with no additional text, preamble, or markdown formatting:

{
  "sections": [
    {
      "section_title": "<string>",
      "sentence": "<string>",
      "page_number": <integer>,
      "observations": "<string>",
      "rule_citation": "<string>",
      "recommendations": "<string>",
      "category": "Misleading or Unsubstantiated Claims",
      "sub_bucket": "<string>",
      "visual_coordinates": {
        "x1": <number>, "y1": <number>,
        "x2": <number>, "y2": <number>,
        "width": <number>, "height": <number>
      },
      "summary": "<string>",
      "accept": false,
      "accept_with_changes": false,
      "accept_with_changes_reason": "",
      "reject": false,
      "reject_reason": ""
    }
  ]
}

For user-action fields (accept, accept_with_changes, accept_with_changes_reason, reject, reject_reason), always use the default values shown above.
The "category" field must be one of: "Misleading or Unsubstantiated Claims", "Performance Presentation & Reporting Violations", "Inadequate or Missing Disclosures", "Improper Use of Testimonials & Endorsements", "Digital & Distribution Controls", "False or Misleading Comparisons Rankings", "Ratings & Data Context Validation", "Improper Use of Third-Party Content & Intellectual Property", "Editorial (Non-Regulatory)".

Do not include any text before or after the JSON object. Do not wrap it in code fences.
"""


NULL_TOKEN_DATA = {
    "total_token_count": None,
    "prompt_token_count": None,
    "thoughts_token_count": None,
    "candidate_token_count": None
}


def sec_misleading_flag(state: AgentStateParallel):
    ask_artifact = state.get("SEC_misleading_ask_artifact", "")
    if not ask_artifact or ask_artifact == '{"results": []}':
        print("[FLAG] No verified findings to finalize")
        return {
            **state,
            'SEC_misleading_artifact': '{"sections": []}',
            'SEC_misleading_token_data': NULL_TOKEN_DATA
        }

    # Filter to only FLAG dispositions before sending to the final node
    try:
        ask_data = json.loads(ask_artifact)
        flagged_only = [r for r in ask_data.get("results", []) if r.get("disposition") == "FLAG"]
        if not flagged_only:
            print("[FLAG] All candidates were CLEARed — no violations")
            return {
                **state,
                'SEC_misleading_artifact': '{"sections": []}',
                'SEC_misleading_token_data': NULL_TOKEN_DATA
            }
        flagged_json = json.dumps({"verified_findings": flagged_only}, indent=2)
    except (json.JSONDecodeError, TypeError):
        flagged_json = ask_artifact

    client = anthropic.Anthropic()

    pdf_path = state["pdf_path"]
    with open(pdf_path, "rb") as f:
        pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")

    prompt = f"""{FLAG_PROMPT}

{flagged_json}

### Todays date: {datetime.now(timezone.utc)}

{FLAG_JSON_INSTRUCTION}"""

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=8192,
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
        json.loads(artifact)

        if response.usage is not None:
            token_data = {
                "total_token_count": response.usage.input_tokens + response.usage.output_tokens,
                "prompt_token_count": response.usage.input_tokens,
                "thoughts_token_count": None,
                "candidate_token_count": response.usage.output_tokens
            }
        else:
            token_data = NULL_TOKEN_DATA

        print(f"[FLAG] Final findings produced")
    except json.JSONDecodeError:
        print(f"[FLAG] Warning: Response was not valid JSON, attempting extraction")
        raw = response.content[0].text
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            artifact = raw[start:end]
        else:
            artifact = '{"sections": []}'
        token_data = {
            "total_token_count": (response.usage.input_tokens + response.usage.output_tokens) if response.usage else None,
            "prompt_token_count": response.usage.input_tokens if response.usage else None,
            "thoughts_token_count": None,
            "candidate_token_count": response.usage.output_tokens if response.usage else None
        }
    except Exception as e:
        print(f"[FLAG] Error: {e}")
        return {
            **state,
            'SEC_misleading_artifact': '{"sections": []}',
            'SEC_misleading_token_data': NULL_TOKEN_DATA
        }

    return {
        **state,
        'SEC_misleading_artifact': artifact,
        'SEC_misleading_token_data': token_data
    }
