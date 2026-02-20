from dotenv import load_dotenv; load_dotenv()
import os
import base64
import json
import anthropic
from node_config import AgentStateParallel
from models.cascade_output import AskVerifyOutput

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


ASK_VERIFY_PROMPT = """
You are a senior compliance analyst performing diagnostic review of candidate compliance findings against the SEC Marketing Rule (IA-5653).

Below are candidate compliance issues identified in the attached document. For EACH candidate, you must apply the diagnostic checks below and determine: FLAG (real violation) or CLEAR (not a violation).

═══════════════════════════════════════════════════════════════
CRITICAL / HIGH SEVERITY — AUTOMATIC FLAG RULES
═══════════════════════════════════════════════════════════════

The following candidate types MUST be flagged — do NOT apply hedging or opinion checks to clear them:

1. DISCLAIMER / STATUTORY VIOLATIONS: Any missing, corrupted, or altered required regulatory language. Missing negation words (not, neither, nor) in disclaimers. Text that implies SEC/FINRA approval or endorsement. These are ALWAYS material — skip Checks 1-5 and FLAG immediately.

2. FACTUAL DATA ERRORS: Numbers that are implausible or corrupted (e.g., growth forecast of 11.4% when context indicates ~1.4%). Terminology errors that reverse meaning (e.g., "unstability" vs "stability"). These are deceptive communications regardless of hedging — FLAG immediately.

3. GUARANTEE STATEMENTS: Any statement that creates a guarantee (including through accidental omission of "no" before "guarantee"). FLAG immediately.

═══════════════════════════════════════════════════════════════
STANDARD DIAGNOSTIC PROTOCOL — For all other candidates
═══════════════════════════════════════════════════════════════

Apply these checks IN ORDER:

CHECK 1 — HEDGING LANGUAGE (Safe Harbor):
Does the statement contain meaningful hedging: seeks to, aims to, designed to, we believe, in our view, may, might, could, can, potentially, subject to, typically, our philosophy?
- If hedging is present AND not contradicted by the rest of the sentence → CLEAR.
- Exception: Performance superlatives ("seeks to deliver superior performance") — hedging does NOT protect performance outcome claims.

CHECK 2 — SUBSTANTIATION PRESENT:
Is there supporting data, figures, tables, footnotes, or clearly identified sources in the same section or on the same page?
- "Same section" means: same paragraph, same page, or clearly linked footnote (numbered reference).
- "See our ADV" or general end-of-document disclaimers do NOT count as proximate support.
- If adequate support exists → CLEAR.

CHECK 3 — OPINION / CAPABILITY / POSITIONING:
Is the statement framed as opinion, philosophy, organizational capability, or non-measurable positioning?
- Opinion: "We believe...", "In our view..."
- Capability: "Our platform provides access to...", "18-year track record..."
- Positioning: "A leading firm", "Providing stability and leadership"
- Indefinite article puffery: "a leading" (among several) vs "THE leading" (sole dominance)
- If opinion/capability/positioning and NOT asserting specific measurable outcomes → CLEAR.

CHECK 4 — MATERIALITY:
Would a reasonable investor's decision be affected by this issue?
- Stylistic, trivial, or immaterial issues → CLEAR.
- If the issue could influence an investor's understanding of risk, return, or suitability → proceed.

CHECK 5 — CONTEXT BALANCE (for benefit claims):
Does the same section contain proportionate risk disclosure?
- Risk language on the same page or in the same section counts.
- Risk buried 5+ pages away or in fine print does NOT cure.
- If risks are present, visible, and linked to the benefit → CLEAR.

CHECK 6 — DECISIVE TEST:
Apply the appropriate test based on the candidate sub-bucket:
- SB1 (Unsubstantiated): Could this be proven true or false with data? If yes and no data provided → FLAG.
- SB2 (Promissory): Does this remove ALL uncertainty about a future outcome? → FLAG.
- SB3 (Implied Certainty): Would a reasonable investor infer the outcome is guaranteed based on framing alone? → FLAG.
- SB4 (Overstated/Absolute): Is this presented as market fact rather than opinion? → FLAG.
- SB5 (Unbalanced): Would a reasonable investor reading ONLY this section get a skewed impression of risk vs reward? → FLAG.
- SB6 (Exaggerated): Did the claim become substantively stronger without new support? → FLAG.
- SB7 (Vague): Could different reasonable readers interpret this term differently in a way that matters? → FLAG.
- SB8 (Audience): Does the complexity mismatch the audience AND hide risk? → FLAG.
- SB9 (Unfair): Does the issue NOT fit SB1-SB8, AND would a reasonable investor be materially misled? → FLAG.
- SB10 (ESG): Is this claiming ESG outcomes/results (not just intent/process) without metrics? → FLAG.

ROUTING — If the issue is real but wrong sub-bucket:
- If it's a superlative, not an evidence issue → assign SB4, not SB1.
- If it's certainty through explicit verbs → assign SB2, not SB3.
- If it's certainty through framing/tone → assign SB3, not SB2.
- If it sounds measurable and implies metrics → assign SB1, not SB7.
- If it's a disclaimer/statutory/data error → assign SB9 (Unfair, Deceptive, or Unclear Communications).

For standard marketing claims: CLEAR aggressively. Only FLAG when you are confident the issue is material and not cured by context, hedging, or proximate support.
For disclaimer, data, and statutory violations: FLAG aggressively. These are NOT cured by hedging, opinion framing, or context.

CANDIDATES TO REVIEW:
"""


ASK_JSON_INSTRUCTION = """
IMPORTANT: You must respond with ONLY valid JSON matching this exact schema, with no additional text, preamble, or markdown formatting:

{
  "results": [
    {
      "sentence": "<exact verbatim text from document>",
      "page_number": <integer>,
      "disposition": "FLAG or CLEAR",
      "sub_bucket": "<sub-bucket name or NONE>",
      "reasoning": "<explanation referencing specific checks applied>"
    }
  ]
}

Do not include any text before or after the JSON object. Do not wrap it in code fences.
"""


def sec_misleading_ask(state: AgentStateParallel):
    candidates_json = state.get("SEC_misleading_detect_artifact", "")
    if not candidates_json or candidates_json == '{"candidates": []}':
        print("[ASK] No candidates to review")
        return {**state, 'SEC_misleading_ask_artifact': '{"results": []}'}

    client = anthropic.Anthropic()

    pdf_path = state["pdf_path"]
    with open(pdf_path, "rb") as f:
        pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")

    prompt = f"""{ASK_VERIFY_PROMPT}

{candidates_json}

{ASK_JSON_INSTRUCTION}"""

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
        print(f"[ASK] Diagnostic review complete")
    except json.JSONDecodeError:
        print(f"[ASK] Warning: Response was not valid JSON, attempting extraction")
        raw = response.content[0].text
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            artifact = raw[start:end]
        else:
            artifact = '{"results": []}'
    except Exception as e:
        print(f"[ASK] Error: {e}")
        return {**state, 'SEC_misleading_ask_artifact': '{"results": []}'}

    return {
        **state,
        'SEC_misleading_ask_artifact': artifact
    }
