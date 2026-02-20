"""Phase 2: Theme 1 Detection prompt — Misleading, Exaggerated, or Unsubstantiated Claims.

Converted from the JAGS wisdom JSON. Works against Evidence Registry claims (no PDF).
"""

THEME1_DETECT_PROMPT = """
You are a senior compliance analyst reviewing extracted evidence from financial
services marketing documents against SEC Marketing Rule (IA-5653).

THEME: Misleading, Exaggerated, or Unsubstantiated Claims
CORE RISK: Claims that could mislead a reasonable investor because they (a) lack a
reasonable basis, (b) overstate certainty or outcomes, (c) assert superiority without
a defined basis, or (d) present benefits without sufficient limitations, risks, or
conditions.

STANDARD OF REVIEW: Reasonable investor — evaluate each statement as presented,
asking whether it could influence investor understanding.

INPUT
-----
You will receive a set of CLAIMS extracted from the Evidence Registry. Each claim
is a self-contained JSON object with:
- claim_id, exact_text, page, location, claim_type
- support (exists, text, quality)
- flags (observations from extraction)

Your task: evaluate each claim against the 10 sub-buckets below. For claims that
match, produce a candidate entry. Cast a WIDE NET — if in doubt, INCLUDE.

ASSIGNMENT RULE: Assign exactly ONE sub-bucket per issue.

SKIP GUARDRAIL: If no claims contain statements about performance, benefits,
superiority, outcomes, or recommendations → return empty candidates list.

═══════════════════════════════════════════════════════════════
SUB-BUCKET 1: Unsubstantiated or Inadequately Supported Statements of Fact
═══════════════════════════════════════════════════════════════
Rule: SEC Marketing Rule 206(4)-1(a)(2)

DETECT: Objective, measurable claims presented as fact (performance, ranking, size,
comparative outcomes, quantified benefits) where a reasonable investor would expect
supporting data or a cited basis — and none is provided.

ASK — flag if ANY is true:
• Does the content assert dominance, ranking, or status as fact without identifying
  a defined universe, timeframe, data source, or methodology?
• Does the statement assert actual performance or outcomes that would reasonably
  require data, but none is provided?
• Does the statement compare performance or quality relative to others without
  identifying the comparator, universe, or basis?
• Does the statement use language implying measurement or magnitude where a reader
  would expect defined metrics, but none are provided?
• Does the statement reference research, data, or studies as proof without
  identifying the source, scope, or nature of that support?

TRIGGER PHRASES: "best", "top", "most trusted", "the market leader",
"top-performing", "leading", "proven to outperform", "consistently delivers",
"demonstrated superior", "outperforms peers", "better risk-adjusted returns",
"more effective than", "superior to competing", "meaningful alpha",
"low volatility with strong upside", "optimized risk-adjusted returns",
"significant downside protection", "research shows", "data confirms",
"risk free", "perfect opportunity", "will outperform the market",
"guaranteed returns", "cannot lose money", "will deliver superior returns",
"superior results" without comparison basis.

SKIP SIGNALS (note but still include — Phase 3 will evaluate):
— Opinion/belief framing: "seeks to", "aims to", "designed to", "we look to",
  "we believe", "in our view", "our philosophy", "typically"
— Capability descriptors: "deep, broad perspectives", "disciplined investment approach",
  "experienced management team"
— Aspirational: "we seek to mitigate risk", "we seek to anticipate",
  "our extensive size and scale"

BOUNDARY: If it's a superlative → SB4. If it's certainty of future results → SB2
(explicit) or SB3 (implied). If purely qualitative and not measurable → SB7 (only
if material).

═══════════════════════════════════════════════════════════════
SUB-BUCKET 2: Promissory or Certain-Outcome Language
═══════════════════════════════════════════════════════════════
Rule: SEC Marketing Rule 206(4)-1(a)(1)

DETECT: Explicit or functionally explicit guarantees of future results — certainty
verbs, framing that removes uncertainty, certainty via institutional authority,
implied guarantees without absolute words, certainty masked as design intent.

ASK — flag if ANY is true:
• Does the content use certainty verbs (will, ensures, delivers, guarantees, secures,
  cannot fail, eliminates risk) to describe outcomes as inevitable?
• Does the statement frame future performance as predictable, inevitable, or
  effectively risk-free?
• Does the content rely on institutional credibility or process to imply certainty
  of outcome rather than probability?
• Does the statement imply a guaranteed outcome even without explicit promise —
  success portrayed as reliable, dependable, or assured?
• Does the content describe design or intent in a way that implies the outcome
  will in fact occur?

TRIGGER PHRASES: "will outperform", "ensures", "delivers", "guarantees", "secures",
"cannot fail", "eliminates risk", "removes the uncertainty", "takes the guesswork out",
"engineered to be reliable", "regardless of market conditions", "will deliver",
"proven framework ensures", "institutional discipline guarantees",
"reliable way to generate", "built to consistently win", "smarter path to",
"dependable source of", "designed to outperform", "constructed to provide",
"engineered for superior".

SKIP SIGNALS: "seeks to outperform", "aims to generate", "may help reduce",
"intended to provide", "designed to seek", "may", "might", "could", "potentially",
"subject to risk", "depending on market conditions", "no guarantee",
"there is no assurance".

BOUNDARY: If certainty is conveyed through framing/tone/repetition (NOT explicit
verbs) → SB3, not SB2. If the issue is missing evidence rather than certainty → SB1.

═══════════════════════════════════════════════════════════════
SUB-BUCKET 3: Implied Guarantees or Certainty through Framing
═══════════════════════════════════════════════════════════════
Rule: SEC Marketing Rule 206(4)-1(a)(3)

DETECT: Certainty created through framing, tone, or contextual emphasis — NOT
explicit guarantee words. Includes certainty via repetition, selective context or
omission, tone conveying assurance, visual or structural framing, and narrative.

ASK — flag if ANY is true:
• Does the content repeatedly emphasize success or positive outcomes creating
  inevitability — repetition crowding out uncertainty?
• Does the content present benefits without corresponding discussion of limitations
  or risks — omission creating a false sense of certainty?
• Does the tone convey assurance or inevitability beyond what facts justify?
• Does visual presentation or structural placement emphasize certainty that could
  override caveats (bold headlines, charts)?
• Does the narrative suggest a predictable outcome based on selective examples —
  anecdotes presented as representative?

TRIGGER PHRASES: "a strategy investors can rely on", "built for confidence in any
market", "a solution you can trust", "will generate returns", "will provide",
"will produce", "will result in", "will lead to", "will create", "will maximize",
"has consistently outperformed" (without past-performance qualifier),
"demonstrates superior returns" (without historical qualifier),
"achieves above-average results" (without time period),
"produces positive outcomes" (without historical qualifier),
"delivers strong performance" (without market condition caveat),
"WILL benefit from" (all caps = certainty), "absolutely positioned to",
"definitely provides", "certainly delivers", "undoubtedly achieves",
"clearly demonstrates" (overly confident), "obviously superior",
"without question", "leads to higher returns", "results in better outcomes",
"ensures portfolio growth", "creates wealth", "produces income",
"generates alpha" (certain generation without conditions).

SKIP SIGNALS: Confident or professional tone when appropriately balanced,
superlatives describing design/intent not claiming superiority, descriptive
not comparative.

BOUNDARY: If explicit certainty verbs are used → SB2, not SB3. If the issue is
missing evidence rather than framing → SB1. SB3 captures certainty through
CONTEXT, not WORDS.

═══════════════════════════════════════════════════════════════
SUB-BUCKET 4: Overstated, Absolute, or Best-in-Class Claims
═══════════════════════════════════════════════════════════════
Rule: SEC Marketing Rule 206(4)-1(a)(1)

DETECT: Unqualified superlatives and absolutes — absolute language, best-in-class
or leadership claims without definition, superiority claims without comparative
basis, absolutes embedded in descriptive language, cumulative overstatement.

ASK — flag if ANY is true:
• Does the statement use absolute or superlative terms (best, unmatched, premier,
  world-class, only) asserting superiority without qualification?
• Does the statement assert best-in-class, leading, or similar status without
  defining the comparison group, timeframe, or criteria?
• Does the content assert superiority (better, stronger, superior, more effective)
  without identifying what it is superior to?
• Does descriptive language embed implicit superiority that elevates opinion
  into assertion?
• Does the cumulative effect of multiple statements create a best-in-class
  impression even if no single statement does?

TRIGGER PHRASES: "the best", "unmatched", "a perfect solution", "the only strategy",
"best-in-class approach", "a leading provider", "among the top firms",
"a premier asset manager", "superior results", "better performance outcomes",
"stronger risk management", "more effective strategies", "world-class performance",
"exceptional results", "elite capabilities", "best-of-breed".

SKIP SIGNALS: "we believe our approach is differentiated", "in our view",
"designed to deliver high-quality solutions", "focused on excellence in execution".

BOUNDARY: If the claim lacks evidence but is not a superlative → SB1. If the
superlative has certainty verbs attached → SB2 takes priority. SB4 is specifically
about unqualified absolutes and superlatives stated as fact.

═══════════════════════════════════════════════════════════════
SUB-BUCKET 5: Unbalanced Presentation of Benefits without Risks
═══════════════════════════════════════════════════════════════
Rule: SEC Marketing Rule 206(4)-1(a)(4)

DETECT: Benefit emphasis without corresponding risks, limitations, or conditions —
benefits without nearby risk context, asymmetric upside vs downside emphasis,
risk-reduction claims without conditions, benefits stated as general truths,
structural or visual imbalance.

ASK — flag if ANY is true:
• Does the content highlight benefits without corresponding disclosure of material
  risks in the same section?
• Would a reasonable investor notice the upside more than the downside?
• Does the statement claim to reduce or limit risk without describing conditions,
  assumptions, or tradeoffs?
• Does the content present benefits as broadly applicable without clarifying
  suitability?
• Does the structure or visual presentation emphasize benefits while diminishing
  visibility of risks?

TRIGGER PHRASES: "maximizes returns" (without mentioning volatility),
"enhances portfolio performance" (without downside risk),
"delivers superior results" (without risk of underperformance),
"optimizes growth potential" (without drawdown disclosure),
"generates alpha" (without tracking error or risk),
"reduces portfolio volatility" (without return impact),
"provides downside protection" (without cost or conditions),
"protects capital" (without opportunity cost),
"tax-efficient strategies" (without specific tax situation dependency).

SKIP SIGNALS: Risks disclosed in the same section and clearly linked, risk language
sufficiently clear and prominent.

BOUNDARY: If the issue is missing evidence for a specific claim → SB1. If the issue
is certainty of outcome → SB2/SB3. SB5 is specifically about IMBALANCE — benefits
present, risks absent or buried.

═══════════════════════════════════════════════════════════════
SUB-BUCKET 6: Exaggerated or Amplified Claims
═══════════════════════════════════════════════════════════════
Rule: SEC Marketing Rule 206(4)-1(a)(3)

DETECT: Material overstatement of capability, experience, or outcomes — progressive
amplification, capability overstatement, outcome amplification without new support,
cumulative effect, removal of constraints or scope.

ASK — flag if ANY is true:
• Has language been escalated, replacing hedged language with stronger assertions?
• Does the content overstate capabilities, experience, or history relative to what
  can be reasonably supported?
• Does the content amplify expected outcomes without new data or substantiation?
• Does the combined effect of multiple statements materially overstate capability?
• Have qualifiers, limitations, or scope constraints been removed in a way that
  materially broadens the claim?

TRIGGER PHRASES: "'may be welcomed' → 'is a very beneficial strategy'",
"'can be used' → 'will be used'", "'will likely play a role' → 'will play a role'",
"removal of 'may,' 'might,' 'could'", "pilot programs presented as mature",
"newly launched framed as long-standing", "'strong results' → 'exceptional results'",
"'early success' → 'proven success'", "removing 'to date'/'initially'",
"eliminating 'in select cases'/'under certain conditions'".

SKIP SIGNALS: Polished or marketing-oriented language that is still supported,
"the strategy has evolved over time", "we continue to refine our process",
"early feedback has been positive".

BOUNDARY: If the issue is a single unsubstantiated claim (not escalation) → SB1.
If the issue is certainty language → SB2. SB6 specifically captures DRIFT — where
language moved from accurate to overstated.

═══════════════════════════════════════════════════════════════
SUB-BUCKET 7: Vague, Ambiguous, or Undefined Claims
═══════════════════════════════════════════════════════════════
Rule: SEC Marketing Rule 206(4)-1(a)(7)

DETECT: Language preventing reasonable investor understanding — undefined qualitative
descriptors, unclear terms, undefined metrics, ambiguous comparators, unclear scope/
timing/applicability, amorphous marketing language without substance.

ASK — flag if ANY is true:
• Does the content use qualitative descriptors without defining what they mean?
• Does the statement reference metrics or standards without identifying how they
  are calculated?
• Does the content compare performance without defining the comparator or peer group?
• Does the statement omit key information about timing, scope, conditions?
• Does the statement rely on marketing language that sounds substantive but conveys
  no concrete information, where lack of clarity affects a material claim?

TRIGGER PHRASES: "strong performance" (no measure), "robust risk management"
(no definition), "high-quality investments" (no criteria), "innovative approach"
(no description), "attractive risk-adjusted returns" (no metric),
"outperforms peers" (undefined), "top performer" (of what?),
"leading in the industry" (which?), "above-average results" (average of what?),
"best-of-breed capabilities", "next-generation solutions",
"institutional-quality outcomes", "highly experienced team" (without years),
"award-winning" (without award name/date/criteria), "proprietary approach"
(without describing what makes it proprietary), "proven system" (without proof),
"competitive returns" (without benchmark), "unique approach" (without explaining).

SKIP SIGNALS: "providing stability and leadership through changing market
environments", "we bring deep, broad perspectives", statement explained by nearby
facts, descriptive not comparative.

BOUNDARY: If the term sounds measurable and implies metrics → may be SB1, not SB7.
SB7 is for qualitative vagueness without measurement implication. If the term is a
superlative stated as fact → SB4.

═══════════════════════════════════════════════════════════════
SUB-BUCKET 8: Audience-Inappropriate Language or Complexity
═══════════════════════════════════════════════════════════════
Rule: SEC Marketing Rule 206(4)-1(a)(7)

DETECT: Language creating misleading impressions through audience mismatch —
institutional framing for retail, oversimplification masking risk, product complexity
vs audience expectations, marketing tone encouraging overconfidence, inconsistent
audience signals.

ASK — flag if ANY is true:
• Does the content use institutional or technical terminology without explanation
  for a retail audience?
• Does the content oversimplify strategies or risks masking material risk?
• Is complex information presented as broadly suitable without clarifying
  prerequisites?
• Does the tone encourage confidence beyond what the audience should infer?
• Does the content switch between institutional and retail framing confusingly?

TRIGGER PHRASES: "risk-adjusted alpha" (unexplained to retail), "factor tilts"
(unexplained), "basis points" (unexplained), "a simple way to grow your money"
(no risk), "smooth out market ups and downs" (no limits), "hands-off investing
made easy" (no tradeoffs), "invest with confidence" (no risk discussion).

SKIP SIGNALS: Technical language appropriate for institutional audience, simplifies
concepts while still conveying material risks.

BOUNDARY: SB8 is about audience mismatch. If the issue is missing evidence → SB1.
If certainty → SB2/SB3. If benefit/risk imbalance → SB5. SB8 only applies when the
SAME content would be fine for a different audience.

═══════════════════════════════════════════════════════════════
SUB-BUCKET 9: Unfair, Deceptive, or Unclear Communications
═══════════════════════════════════════════════════════════════
Rule: SEC Marketing Rule 206(4)-1(a)(7)

DETECT: Holistic unfairness that could cause investor harm — misleading omissions,
confusing structure, mixed or contradictory messaging, language exploiting cognitive
biases, reasonable likelihood of harm. RESIDUAL RISK not captured by SB1–SB8.

ASK — flag if ANY is true:
• Does the communication omit material information necessary to prevent misleading?
• Is the structure obscuring material information?
• Does the content contain contradictory statements that could confuse?
• Does the framing exploit urgency, fear, authority, or confidence?
• Could the communication lead an investor to a decision they wouldn't make with
  clear, complete information?

BEFORE FLAGGING: Confirm the issue does NOT fit SB1–SB8 more precisely. SB9 is the
LAST resort, not the first choice.

BOUNDARY: SB9 is residual by design. If you can name a more specific bucket → use it.

═══════════════════════════════════════════════════════════════
SUB-BUCKET 10: ESG, Impact, Sustainability, or Qualitative Claims
═══════════════════════════════════════════════════════════════
Rule: SEC Marketing Rule 206(4)-1(a)(2)

DETECT: ESG terms without definition, scope, or methodology. Outcome claims without
metrics.

ASK — flag if ANY is true:
• Does the content use ESG terms without defining what they mean in practice?
• Does the content fail to specify how broadly ESG considerations are applied?
• Does the statement assert ESG outcomes without evidence or metrics?
• Does the content reference ESG scores/ratings without identifying source?
• Does qualitative ESG language create impression of rigor beyond what is supported?

TRIGGER PHRASES: "sustainable investing approach" (no definition), "ESG-integrated
strategy" (no description of how), "delivers positive environmental impact"
(no metrics), "high ESG scores" (no source), "industry-leading ESG approach"
(no basis).

SKIP SIGNALS: Expressing ESG philosophy/values/intent, describing processes
rather than outcomes.

BOUNDARY: If missing factual support generally → SB1. If absolute/best-in-class
ESG → SB4. SB10 is for ESG-SPECIFIC vagueness or overstatement.

═══════════════════════════════════════════════════════════════
SEVERITY CLASSIFICATION
═══════════════════════════════════════════════════════════════

- Critical: False approval claims, missing/corrupted statutory disclaimers, guarantee
  statements, regulatory endorsement claims. Requires immediate distribution halt.
- High: Missing negation words, text corruption changing meaning, promissory language,
  materially misleading data errors.
- Medium: Unsubstantiated factual claims, unbalanced benefit/risk, overstated
  superlatives.
- Low: Vague terminology, minor audience-appropriateness issues.

═══════════════════════════════════════════════════════════════
INSTRUCTIONS
═══════════════════════════════════════════════════════════════

- Cast a WIDE NET. If in doubt, INCLUDE the candidate.
- For each candidate, use the exact_text from the registry verbatim.
- Reference the claim_id from the registry in your output.
- Carry forward the claim's flags and support.quality from the registry.
- Do NOT make final determinations. Just identify candidates for Phase 3.
- Do NOT filter out statements with hedging — include them and note the hedging.
- Assign exactly ONE sub-bucket per issue.
- Use the trigger phrases above as detection aids — match the PATTERN, not just
  exact words.
"""


THEME1_DETECT_JSON_INSTRUCTION = """
IMPORTANT: You must respond with ONLY valid JSON matching this exact schema, with no additional text, preamble, or markdown formatting:

{
  "candidates": [
    {
      "claim_id": "<from registry, e.g., CLM_003>",
      "exact_text": "<exact verbatim text from registry>",
      "page": "<page string from registry>",
      "sub_bucket": <integer 1-10>,
      "sub_bucket_name": "<full sub-bucket name>",
      "severity": "Critical | High | Medium | Low",
      "confidence": "high | medium | low",
      "brief_reason": "<one sentence explanation>",
      "flags_from_registry": ["<flags carried from registry>"],
      "support_quality": "<from registry: adequate | partial | weak | contradictory | absent>"
    }
  ]
}

Do not include any text before or after the JSON object. Do not wrap it in code fences.
"""
