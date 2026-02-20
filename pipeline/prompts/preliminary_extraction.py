"""Phase 0: Preliminary Evidence Extraction prompt (Prompt A).

Broad 10-category extraction: disclaimers, performance_data, rankings_awards,
definitions, footnotes, data_sources, qualifications, audience_indicators,
temporal_context, visual_elements.

This runs BEFORE the Evidence Registry Builder (Prompt B) and feeds into it.
"""

PRELIMINARY_EXTRACTION_PROMPT = """
PHASE 1: EVIDENCE REGISTRY BUILDER
Purpose: Extract all substantiation, disclosures, and context BEFORE violation detection

You are a senior compliance analyst conducting a comprehensive document intelligence scan. Your job is to extract ALL evidence that could potentially substantiate or qualify claims in the document - creating a complete "Evidence Registry" that will be used by subsequent violation detection phases.

CRITICAL: This is an EXTRACTION task, not a COMPLIANCE REVIEW task. Do not flag violations. Simply catalog what exists.

═══════════════════════════════════════════════════════════════════════════════
EXTRACTION REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

Extract the following information systematically:

## 1. LEGAL DISCLAIMERS & RISK WARNINGS

For EACH disclaimer or risk warning, record:
- Page number
- Location on page (header, footer, body, sidebar)
- Full text of disclaimer
- Type: (SEC approval, FDIC, past performance, no guarantee, risk of loss, etc.)
- Prominence: (Large font, small print, bold, regular, buried)

## 2. PERFORMANCE SUBSTANTIATION

For EACH performance claim or data point, record:
- Page number
- Performance figure (return, percentage, ranking)
- Time period (specific dates or "as of" date)
- Net vs Gross specification
- Benchmark or comparison basis
- Data source (if cited)
- Footnote reference (if any)

## 3. RANKINGS, RATINGS & AWARDS

For EACH ranking, rating, or award mention, record:
- Page number
- Claim text (what is being claimed)
- Award/ranking name
- Awarding organization
- Date/year received
- Methodology or criteria (if stated)
- Universe or category (if stated)
- Footnote reference (if any)

## 4. DEFINITIONS & EXPLANATIONS

For EACH technical term, metric, or concept that is DEFINED in the document:
- Page number
- Term being defined
- Definition provided
- Context (where used)

## 5. FOOTNOTES & ENDNOTES

For EACH footnote or endnote:
- Footnote number/symbol
- Page where reference appears
- Page where footnote content appears
- Full footnote text
- What it substantiates (claim it refers to)

## 6. DATA SOURCES & CITATIONS

For EACH external data source cited:
- Page number
- Source name (Morningstar, Bloomberg, etc.)
- What data it supports
- Date/time period of data
- Accessibility note (proprietary, public, etc.)

## 7. QUALIFICATIONS & HEDGING LANGUAGE

For EACH section with material qualifications:
- Page number
- Section title/topic
- Qualification language ("may," "seeks to," "no assurance," etc.)
- What is being qualified
- Proximity to claim (same sentence, same paragraph, same section, different page)

## 8. AUDIENCE INDICATORS

Record indicators of intended audience:
- Document title/header language
- Explicit audience statements ("For Institutional Investors Only")
- Terminology level (retail-friendly vs technical)
- Distribution restrictions noted

## 9. TEMPORAL CONTEXT

Record "as of" dates and time references:
- Document date
- Data as-of dates
- Performance period dates
- "Last updated" dates
- Copyright or version dates

## 10. VISUAL ELEMENTS WITH SUBSTANTIATION

For charts, tables, graphs:
- Page number
- Visual type (chart, table, graph)
- What it shows
- Data source noted
- Legends, labels, footnotes attached
- Time periods displayed

═══════════════════════════════════════════════════════════════════════════════
CRITICAL REMINDERS
═══════════════════════════════════════════════════════════════════════════════

1. **EXTRACT EVERYTHING** - Better to over-extract than under-extract
2. **PRECISE PAGE NUMBERS** - Phase 2 needs exact locations
3. **VERBATIM TEXT** - Copy exact text, don't paraphrase
4. **NO ANALYSIS** - Don't evaluate quality or adequacy, just extract
5. **PROXIMITY MATTERS** - Note where substantiation appears relative to claims
6. **COMPLETENESS** - Empty arrays are fine if category doesn't exist in document

VERBATIM EXTRACTION WARNING — HIGHEST PRIORITY
═══════════════════════════════════════════════════════════════════════════════

You MUST extract text EXACTLY as it appears in the document, character for character.
Do NOT correct, normalize, or "fix" any text — even if it appears to contain errors.

This is CRITICAL for regulatory disclaimers. If the document says:
  "The Securities and Exchange Commission and FINRA has approved our securities"
You must capture EXACTLY that text — NOT the standard canonical version.

Common extraction errors to AVOID:
- Replacing garbled disclaimer text with the standard correct version
- Adding "not" or "neither" to disclaimers that are missing negation words
- Fixing grammatical errors in regulatory statements
- Normalizing capitalization or punctuation in quoted text

The downstream compliance analysis DEPENDS on detecting text corruption.
If you "fix" garbled text, the corruption becomes invisible and undetectable.

Begin your evidence registry extraction now.
"""


PRELIMINARY_EXTRACTION_JSON_INSTRUCTION = """
IMPORTANT: You must respond with ONLY valid JSON matching this exact schema, with no additional text, preamble, or markdown formatting:

{
  "document_metadata": {
    "document_date": "string or null",
    "total_pages": 0,
    "document_type": "string",
    "intended_audience": "string"
  },
  "disclaimers": [
    {
      "id": "DISCLAIMER_001",
      "page": 0,
      "location": "string",
      "text": "full disclaimer text",
      "type": "string",
      "prominence": "string"
    }
  ],
  "performance_data": [
    {
      "id": "PERFORMANCE_001",
      "page": 0,
      "claim": "string",
      "time_period": "string or null",
      "net_gross": "string or null",
      "benchmark": "string or null",
      "as_of_date": "string or null",
      "source": "string or null",
      "footnote": "string or null"
    }
  ],
  "rankings_awards": [
    {
      "id": "RANKING_001",
      "page": 0,
      "claim": "string",
      "organization": "string or null",
      "year": "string or null",
      "methodology": "string or null",
      "category": "string or null"
    }
  ],
  "definitions": [
    {
      "id": "DEFINITION_001",
      "page": 0,
      "term": "string",
      "definition": "string"
    }
  ],
  "footnotes": [
    {
      "id": "FOOTNOTE_001",
      "number": "string",
      "ref_page": 0,
      "content_page": 0,
      "text": "full footnote text",
      "substantiates": "string"
    }
  ],
  "data_sources": [
    {
      "id": "SOURCE_001",
      "page": 0,
      "source": "string",
      "supports": "string",
      "date": "string or null"
    }
  ],
  "qualifications": [
    {
      "id": "QUALIFICATION_001",
      "page": 0,
      "section": "string",
      "language": "string",
      "qualifies": "string",
      "proximity": "string"
    }
  ],
  "audience_indicators": {
    "explicit_statement": "string or null",
    "terminology_level": "string or null",
    "distribution_restrictions": "string or null"
  },
  "temporal_context": {
    "document_date": "string or null",
    "performance_as_of": "string or null",
    "data_as_of": "string or null"
  },
  "visual_elements": [
    {
      "id": "VISUAL_001",
      "page": 0,
      "type": "string",
      "shows": "string",
      "source": "string or null",
      "footnotes": "string or null"
    }
  ]
}

Do not include any text before or after the JSON object. Do not wrap it in code fences.
"""
