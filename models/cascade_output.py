from typing import List
from pydantic import BaseModel, Field


class DetectCandidate(BaseModel):
    """A single candidate finding from the DETECT stage."""
    sentence: str = Field(
        ...,
        description="Exact verbatim text from the document that may be a violation. Include enough surrounding context to evaluate hedging or qualifiers."
    )
    page_number: int = Field(
        ...,
        description="Page number where the sentence appears."
    )
    candidate_sub_bucket: str = Field(
        ...,
        description="The most likely sub-bucket name this candidate falls under."
    )
    severity: str = Field(
        ...,
        description="Violation severity: Critical, High, Medium, or Low."
    )
    confidence: str = Field(
        ...,
        description="Confidence that this is a real violation: high, medium, or low."
    )
    brief_reason: str = Field(
        ...,
        description="One sentence explaining why this was flagged as a candidate, including the reason behind the confidence level."
    )


class DetectOutput(BaseModel):
    """Output from the DETECT stage — broad net of candidate violations."""
    candidates: List[DetectCandidate] = Field(
        ...,
        description="All candidate compliance issues identified in the document."
    )


class AskVerifyResult(BaseModel):
    """A single finding after ASK + VERIFY diagnostic review."""
    sentence: str = Field(
        ...,
        description="Exact verbatim text from the document."
    )
    page_number: int = Field(
        ...,
        description="Page number where the sentence appears."
    )
    disposition: str = Field(
        ...,
        description="FLAG if the issue survives verification, CLEAR if it does not."
    )
    sub_bucket: str = Field(
        ...,
        description="Assigned sub-bucket name if FLAG, 'NONE' if CLEAR."
    )
    reasoning: str = Field(
        ...,
        description="Explanation of why this was flagged or cleared, referencing specific checks applied."
    )


class AskVerifyOutput(BaseModel):
    """Output from the ASK + VERIFY stage — filtered and diagnosed candidates."""
    results: List[AskVerifyResult] = Field(
        ...,
        description="All candidates after diagnostic review, with dispositions."
    )
