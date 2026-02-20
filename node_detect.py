from dotenv import load_dotenv; load_dotenv()
import os
import base64
import json
import anthropic
from node_config import AgentStateParallel
from models.cascade_output import DetectOutput

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


DETECT_PROMPT = """
You are a senior compliance manager with deep experience reviewing marketing materials for financial services against SEC marketing rules (IA-5653). Review the attached document and identify statements of fact, comparison, or superiority that lack adequate data, evidentiary support, verification, or methodological explanation at the point of claim.

Standard of review: REASONABLE INVESTOR — evaluate each statement as presented, asking whether it could influence investor understanding.

═══════════════════════════════════════════════════════════════
PHASE 1 — CRITICAL REVIEW PROTOCOL (DO THIS FIRST)
═══════════════════════════════════════════════════════════════

BEFORE reviewing marketing content, verify ALL required SEC/FINRA disclaimers WORD-BY-WORD:

1. Read text EXACTLY as written. Do NOT mentally auto-correct typos, missing words, or corrupted text.
2. Legal disclaimers, footnotes, and boilerplate language in small print or on last pages are HIGH-RISK areas for the most serious violations.
3. Any suggestion that SEC, FINRA, or regulators "approved" or "endorsed" the securities is a CRITICAL violation requiring immediate distribution halt.

Specifically check that required disclaimer language is word-perfect, including:
- For BDCs: "Neither the Securities and Exchange Commission nor any state securities regulator has approved or disapproved of our securities or determined if the prospectus is truthful or complete."
- Any missing negation words (not, neither, nor) = CRITICAL violation
- Any text corruption, typos, or omissions in required disclaimers = HIGH severity
- Any missing "no guarantee" language or accidental guarantee statements = CRITICAL violation

Also check for FACTUAL ERRORS in data, statistics, and numerical claims:
- Numbers that appear corrupted or implausible (e.g., a GDP growth forecast of 11.4% when context suggests ~1.4%)
- Terminology errors that change meaning (e.g., "unstability" vs "stability", "unanimous" when officials were split)
- Any factual misstatement that could mislead a reasonable investor

═══════════════════════════════════════════════════════════════
PHASE 2 — MARKETING CONTENT REVIEW
═══════════════════════════════════════════════════════════════

After completing Phase 1, scan the full document for these 10 violation types. For each, use the trigger phrases and detection questions to identify candidates.

───────────────────────────────────────────────────────────────
SB1. Unsubstantiated or Inadequately Supported Statements of Fact
───────────────────────────────────────────────────────────────
Scope: Objective, measurable claims presented as fact (performance, ranking, size, comparative outcomes, quantified benefits) where a reasonable investor would expect supporting data or a cited basis — and none is provided.

Detection questions — flag if ANY is true:
• Does the content assert dominance, ranking, or status as fact without identifying a defined universe, timeframe, data source, or methodology?
• Does the statement assert actual performance or outcomes that would reasonably require data, but none is provided?
• Does the statement compare performance or quality relative to others without identifying the comparator, universe, or basis?
• Does the statement use language implying measurement or magnitude where a reader would expect defined metrics, but none are provided?
• Does the statement reference research, data, or studies as proof without identifying the source, scope, or nature of that support?

Trigger phrases: "best", "top", "most trusted", "the market leader", "top-performing", "leading", "proven to outperform", "consistently delivers", "demonstrated superior", "outperforms peers", "better risk-adjusted returns", "more effective than", "superior to competing", "meaningful alpha", "low volatility with strong upside", "optimized risk-adjusted returns", "significant downside protection", "research shows", "data confirms", "risk free", "perfect opportunity", "will outperform the market", "guaranteed returns", "cannot lose money", "will deliver superior returns", "superior results" without comparison basis.

Skip signals (note but still include — ASK stage will evaluate):
— Opinion/belief framing: "seeks to", "aims to", "designed to", "we look to", "we believe", "in our view", "our philosophy", "typically"
— Capability descriptors: "deep, broad perspectives", "disciplined investment approach", "experienced management team"
— Aspirational: "we seek to mitigate risk", "we seek to anticipate", "our extensive size and scale"

───────────────────────────────────────────────────────────────
SB2. Promissory or Certain-Outcome Language
───────────────────────────────────────────────────────────────
Scope: Explicit or functionally explicit guarantees of future results — certainty verbs, framing that removes uncertainty, certainty via institutional authority, implied guarantees without absolute words, and certainty masked as design intent.

Detection questions — flag if ANY is true:
• Does the content use certainty verbs (will, ensures, delivers, guarantees, secures, cannot fail, eliminates risk) to describe outcomes as inevitable?
• Does the statement frame future performance as predictable, inevitable, or effectively risk-free?
• Does the content rely on institutional credibility or process to imply certainty of outcome rather than probability?
• Does the statement imply a guaranteed outcome even without explicit promise — success portrayed as reliable, dependable, or assured?
• Does the content describe design or intent in a way that implies the outcome will in fact occur?

Trigger phrases: "will outperform", "ensures", "delivers", "guarantees", "secures", "cannot fail", "eliminates risk", "removes the uncertainty", "takes the guesswork out", "engineered to be reliable", "regardless of market conditions", "will deliver", "proven framework ensures", "institutional discipline guarantees", "reliable way to generate", "built to consistently win", "smarter path to", "dependable source of", "designed to outperform", "constructed to provide", "engineered for superior".

Skip signals (note but still include):
— "seeks to outperform", "aims to generate", "may help reduce", "intended to provide", "designed to seek"
— Hedging present: "may", "might", "could", "potentially", "subject to risk", "depending on market conditions", "no guarantee", "there is no assurance"

───────────────────────────────────────────────────────────────
SB3. Implied Guarantees or Certainty through Framing
───────────────────────────────────────────────────────────────
Scope: Certainty created through framing, tone, or contextual emphasis — NOT explicit guarantee words. Includes certainty via repetition, selective context or omission, tone conveying assurance, visual or structural framing, and narrative or storytelling.

Detection questions — flag if ANY is true:
• Does the content repeatedly emphasize success or positive outcomes creating inevitability — repetition crowding out uncertainty?
• Does the content present benefits without corresponding discussion of limitations or risks — omission creating a false sense of certainty?
• Does the tone convey assurance or inevitability beyond what facts reasonably justify?
• Does visual presentation or structural placement emphasize certainty that could override caveats (bold headlines, charts)?
• Does the narrative suggest a predictable outcome based on selective examples — anecdotes presented as representative?

Trigger phrases: "a strategy investors can rely on", "built for confidence in any market", "a solution you can trust", "will generate returns", "will provide", "will produce", "will result in", "will lead to", "will create", "will maximize", "has consistently outperformed" (without past-performance qualifier), "demonstrates superior returns" (without historical qualifier), "achieves above-average results" (without time period), "produces positive outcomes" (without historical qualifier), "delivers strong performance" (without market condition caveat), "WILL benefit from" (all caps = certainty), "absolutely positioned to", "definitely provides", "certainly delivers", "undoubtedly achieves", "clearly demonstrates" (overly confident), "obviously superior", "without question", "leads to higher returns" (direct causation without qualification), "results in better outcomes", "ensures portfolio growth", "creates wealth", "produces income", "generates alpha" (certain generation without conditions).

Also flag: bold/headline claims with buried qualifiers, charts showing only favorable periods, success stories without variability context, process→success narratives without uncertainty, multiple references to "consistent success" without counterbalancing risk.

───────────────────────────────────────────────────────────────
SB4. Overstated, Absolute, or Best-in-Class Claims
───────────────────────────────────────────────────────────────
Scope: Unqualified superlatives and absolutes — absolute language, best-in-class or leadership claims without definition, superiority claims without comparative basis, absolutes embedded in descriptive language, and cumulative overstatement.

Detection questions — flag if ANY is true:
• Does the statement use absolute or superlative terms (best, unmatched, premier, world-class, only) asserting superiority without qualification?
• Does the statement assert best-in-class, leading, or similar status without defining the comparison group, timeframe, or criteria?
• Does the content assert superiority (better, stronger, superior, more effective) without identifying what it is superior to?
• Does descriptive language embed implicit superiority that elevates opinion into assertion?
• Does the cumulative effect of multiple statements create a best-in-class impression even if no single statement does?

Trigger phrases: "the best", "unmatched", "a perfect solution", "the only strategy", "best-in-class approach", "a leading provider", "among the top firms", "a premier asset manager", "superior results", "better performance outcomes", "stronger risk management", "more effective strategies", "world-class performance", "exceptional results", "elite capabilities", "best-of-breed".

Also flag: headline claiming leadership + bullets asserting superiority, multiple unqualified "top"/"leading"/"best" across a document.

Skip signals (note but still include):
— "we believe our approach is differentiated", "in our view", "designed to deliver high-quality solutions", "focused on excellence in execution"

───────────────────────────────────────────────────────────────
SB5. Unbalanced Presentation of Benefits without Risks
───────────────────────────────────────────────────────────────
Scope: Benefit emphasis without corresponding risks, limitations, or conditions — benefits without nearby risk context, asymmetric upside vs downside emphasis, risk-reduction claims without conditions, benefits stated as general truths, and structural or visual imbalance.

Detection questions — flag if ANY is true:
• Does the content highlight benefits without corresponding disclosure of material risks in the same section?
• Would a reasonable investor notice the upside more than the downside?
• Does the statement claim to reduce or limit risk without describing conditions, assumptions, or tradeoffs?
• Does the content present benefits as broadly applicable without clarifying suitability?
• Does the structure or visual presentation emphasize benefits while diminishing visibility of risks?

Trigger phrases — benefits without risk context: "maximizes returns" (without mentioning volatility), "enhances portfolio performance" (without downside risk), "delivers superior results" (without risk of underperformance), "optimizes growth potential" (without drawdown disclosure), "generates alpha" (without tracking error or risk), "increases yield" (without credit/interest rate risk), "captures upside potential" (without downside exposure), "improves risk-adjusted returns" (without defining risk metrics), "reduces portfolio volatility" (without return impact), "lowers downside risk" (without upside limitation), "provides downside protection" (without cost or conditions), "hedges against market decline" (without hedging costs), "protects capital" (without opportunity cost), "minimizes drawdowns" (without concentration risk), "tax-efficient strategies" (without individual tax situation dependency), "minimizes tax liability" (without individual circumstances caveat).

Also flag: benefit bullet lists with single buried risk footnote, charts highlighting gains without drawdowns, benefits in headlines with risks in fine print, callout boxes for upside only.

Skip signals: risks disclosed in the same section and clearly linked.

───────────────────────────────────────────────────────────────
SB6. Exaggerated or Amplified Claims
───────────────────────────────────────────────────────────────
Scope: Material overstatement of capability, experience, or outcomes — progressive amplification, capability overstatement, outcome amplification without new support, cumulative effect, and removal of constraints or scope.

Detection questions — flag if ANY is true:
• Has language been escalated, replacing hedged language with stronger assertions?
• Does the content overstate capabilities, experience, or history relative to what can be reasonably supported?
• Does the content amplify expected outcomes without new data or substantiation?
• Does the combined effect of multiple statements materially overstate capability?
• Have qualifiers, limitations, or scope constraints been removed in a way that materially broadens the claim?

Trigger phrases: removal of "may", "might", "could" from hedged statements; "is a very beneficial strategy" (escalated from "may be welcomed"); "will be used" (from "can be used"); "will play a role" (from "will likely play a role"); pilot programs presented as mature; newly launched framed as long-standing; "exceptional results" (escalated from "strong results"); "proven success" (from "early success"); removing "to date"/"initially"; eliminating "in select cases"/"under certain conditions".

───────────────────────────────────────────────────────────────
SB7. Vague, Ambiguous, or Undefined Claims
───────────────────────────────────────────────────────────────
Scope: Language preventing reasonable investor understanding — undefined qualitative descriptors, unclear terms, undefined metrics, ambiguous comparators, unclear scope/timing/applicability, and amorphous marketing language without substance.

Detection questions — flag if ANY is true:
• Does the content use qualitative descriptors without defining what they mean in practice?
• Does the statement reference metrics or evaluation standards without identifying how they are calculated?
• Does the content compare performance without defining the comparator or peer group?
• Does the statement omit key information about timing, scope, conditions, or applicability?
• Does the statement rely on marketing language that sounds substantive but conveys no concrete information, where lack of clarity affects a material claim?

Trigger phrases: "strong performance" (no measure), "robust risk management" (no definition), "high-quality investments" (no criteria), "innovative approach" (no description), "attractive risk-adjusted returns" (no metric), "low volatility strategy" (no measure), "superior returns" (no benchmark/timeframe), "outperforms peers" (undefined), "top performer" (of what?), "leading in the industry" (which?), "above-average results" (average of what?), "best-of-breed capabilities", "next-generation solutions", "holistic portfolio approach", "institutional-quality outcomes", "highly experienced team" (without years), "seasoned professionals" (without tenure), "award-winning" (without award name/date/criteria), "proprietary approach" (without describing what makes it proprietary), "sophisticated analysis" (without methodology), "proven system" (without proof or timeframe), "time-tested approach" (without time period), "cutting-edge technology" (without description), "extensive client base" (without numbers), "competitive returns" (without benchmark), "solid performance" (without metrics), "consistent results" (without consistency definition), "unique approach" (without explaining uniqueness), "sets us apart" (without comparison basis).

Skip signals (note but still include):
— "providing stability and leadership through changing market environments"
— "we bring deep, broad perspectives to global fixed income investing"
— Statement explained by nearby facts showing what it means
— Language is descriptive, not comparative — not claiming superiority

───────────────────────────────────────────────────────────────
SB8. Audience-Inappropriate Language
───────────────────────────────────────────────────────────────
Scope: Language creating misleading impressions through audience mismatch — institutional framing for retail, oversimplification masking risk, product complexity vs audience expectations, marketing tone encouraging overconfidence, inconsistent audience signals.

Detection questions — flag if ANY is true:
• Does the content use institutional or technical terminology without explanation for a retail audience?
• Does the content oversimplify strategies or risks in a way that masks material risk?
• Is complex information presented as broadly suitable without clarifying prerequisites or investor sophistication?
• Does the tone encourage confidence beyond what the audience should reasonably infer?
• Does the content switch between institutional and retail framing in a confusing way?

Trigger phrases: "risk-adjusted alpha" (unexplained to retail), "factor tilts" (unexplained), "basis points" (unexplained), "a simple way to grow your money" (no risk), "smooth out market ups and downs" (no limits), "hands-off investing made easy" (no tradeoffs), "invest with confidence" (no risk discussion), "a smarter way to invest" (no tradeoffs), "professional-grade results made accessible", retail marketing + institutional performance framing, simplified headlines + technical footnotes.

───────────────────────────────────────────────────────────────
SB9. Unfair, Deceptive, or Unclear Communications
───────────────────────────────────────────────────────────────
Scope: Holistic unfairness that could cause investor harm — misleading omissions, confusing structure, mixed or contradictory messaging, language exploiting cognitive biases, reasonable likelihood of investor harm. Residual risk NOT captured by SB1–SB8.

Detection questions — flag if ANY is true:
• Does the content omit information a reasonable investor would need to make an informed decision?
• Does the structure or formatting obscure material information?
• Does the content contain contradictory statements that could confuse investors?
• Does the language exploit known cognitive biases (anchoring, loss aversion, authority)?
• Would a reasonable investor be materially harmed or misled by this communication as a whole?

Also flag: Text corruption, typos, or missing words that change meaning. Missing negation words. Factual errors in data or statistics.

───────────────────────────────────────────────────────────────
SB10. ESG/Sustainability Claims without Support
───────────────────────────────────────────────────────────────
Scope: ESG terms without definition, scope, or methodology. Outcome claims without metrics.

Detection questions:
• Does the content claim ESG outcomes or results (not just intent or process) without supporting metrics?
• Are ESG terms used without clear definition of scope or methodology?

═══════════════════════════════════════════════════════════════
SEVERITY CLASSIFICATION
═══════════════════════════════════════════════════════════════

Assign each finding a severity level:
- Critical: False approval claims, missing/corrupted statutory disclaimers, guarantee statements, regulatory endorsement claims. Requires immediate distribution halt.
- High: Missing negation words, text corruption that changes meaning, promissory language about outcomes, materially misleading data errors.
- Medium: Unsubstantiated factual claims, unbalanced benefit/risk presentation, overstated superlatives.
- Low: Vague terminology, minor audience-appropriateness issues, stylistic concerns that could be misinterpreted.

═══════════════════════════════════════════════════════════════
CONFIDENCE LEVEL
═══════════════════════════════════════════════════════════════

For each finding, assign a confidence level that this is indeed a violation:
- high: Clear-cut violation with no reasonable alternative reading.
- medium: Likely violation but some ambiguity or context could mitigate.
- low: Possible violation that warrants review but could be defensible.

Include the reasoning behind your confidence level in your explanation.

═══════════════════════════════════════════════════════════════
SKIP GUARDRAIL
═══════════════════════════════════════════════════════════════

If the content contains NO claims (no statements about performance, benefits, superiority, outcomes, or recommendations) → return empty candidates list.

═══════════════════════════════════════════════════════════════
INSTRUCTIONS
═══════════════════════════════════════════════════════════════

- Cast a WIDE NET. If in doubt, INCLUDE the candidate. It is better to over-include than to miss a real violation.
- For each candidate, extract the EXACT text from the document. Include enough surrounding context to evaluate hedging and qualifiers.
- Review ALL pages with uniform scrutiny — last-page small print is as important as first-page headlines.
- Flag false approval claims, guarantees, and statutory violations as HIGHEST PRIORITY before addressing marketing claim substantiation issues.
- Do NOT make final determinations. Just identify candidates for further review.
- Do NOT filter out statements with hedging — include them and note the hedging. The next stage will evaluate.
- Assign exactly ONE sub-bucket per issue.
- Use the trigger phrases above as detection aids — match the PATTERN, not just exact words.
"""


DETECT_JSON_INSTRUCTION = """
IMPORTANT: You must respond with ONLY valid JSON matching this exact schema, with no additional text, preamble, or markdown formatting:

{
  "candidates": [
    {
      "sentence": "<exact verbatim text from document>",
      "page_number": <integer>,
      "candidate_sub_bucket": "<sub-bucket name>",
      "severity": "Critical | High | Medium | Low",
      "confidence": "high | medium | low",
      "brief_reason": "<one sentence explanation including confidence reasoning>"
    }
  ]
}

Do not include any text before or after the JSON object. Do not wrap it in code fences.
"""


def sec_misleading_detect(state: AgentStateParallel):
    client = anthropic.Anthropic()

    pdf_path = state["pdf_path"]
    with open(pdf_path, "rb") as f:
        pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")

    prompt = DETECT_PROMPT + DETECT_JSON_INSTRUCTION

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=8192,
            temperature=0.3,
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
        print(f"[DETECT] Found candidates in document")
    except json.JSONDecodeError:
        print(f"[DETECT] Warning: Response was not valid JSON, attempting extraction")
        raw = response.content[0].text
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start >= 0 and end > start:
            artifact = raw[start:end]
        else:
            artifact = '{"candidates": []}'
    except Exception as e:
        print(f"[DETECT] Error: {e}")
        return {**state, 'SEC_misleading_detect_artifact': '{"candidates": []}'}

    return {
        **state,
        'SEC_misleading_detect_artifact': artifact
    }
