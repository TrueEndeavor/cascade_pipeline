from typing import List
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class ComplianceCategory(str, Enum):
    MISLEADING = "Misleading or Unsubstantiated Claims"
    PERFORMANCE = "Performance Presentation & Reporting Violations"
    DISCLOSURES = "Inadequate or Missing Disclosures"
    TESTIMONIALS = "Improper Use of Testimonials & Endorsements"
    DIGITAL_SOCIAL = "Digital & Distribution Controls"
    COMPARISONS = "False or Misleading Comparisons Rankings"
    RANKINGS_RATINGS = "Ratings & Data Context Validation"
    THIRD_PARTY_OPINION = "Improper Use of Third-Party Content & Intellectual Property"
    EDITORIAL = "Editorial (Non-Regulatory)"


class VisualCoordinate(BaseModel):
    x1: float = Field(..., description="Left X-coordinate of the bounding box (in pixels).")
    y1: float = Field(..., description="Top Y-coordinate of the bounding box (in pixels).")
    x2: float = Field(..., description="Right X-coordinate of the bounding box (in pixels).")
    y2: float = Field(..., description="Bottom Y-coordinate of the bounding box (in pixels).")
    width: float = Field(..., description="Width of the page or image where the finding was detected.")
    height: float = Field(..., description="Height of the page or image where the finding was detected.")


class ComplianceSection(BaseModel):
    section_title: str = Field(..., description="Logical section name or heading where the issue was found.")
    sentence: str = Field(..., description="Exact sentence or phrase from the document that triggered the compliance finding.")
    page_number: int = Field(..., description="Page number where the sentence or issue appears.")
    observations: str = Field(..., description="Detailed explanation of why the sentence is problematic from a compliance or regulatory perspective.")
    rule_citation: str = Field(..., description="Specific regulatory rule or statute that the finding violates (e.g., SEC rule citation).")
    recommendations: str = Field(..., description="Suggested remediation or rewording to make the content compliant.")
    category: ComplianceCategory = Field(..., description="High-level classification of the compliance issue.")
    sub_bucket: str = Field(..., description="This is the sub category that the violation has raised.")
    visual_coordinates: VisualCoordinate = Field(..., description="Visual bounding boxes pointing to where the issue appears in the document.")
    summary: str = Field(..., description="This is the summary of the entire violation in a concise way")
    accept: bool = Field(False, description="This is to be filled by user, never by AI")
    accept_with_changes: bool = Field(False, description="This is to be filled by user, never by AI")
    accept_with_changes_reason: str = Field(..., description="This is to be filled by user, never by AI")
    reject: bool = Field(False, description="This is to be filled by user, never by AI")
    reject_reason: str = Field(..., description="This is to be filled by user, never by AI")


class ComplianceJSON(BaseModel):
    sections: List[ComplianceSection] = Field(
        ...,
        description="List of all compliance findings identified in the document."
    )
    model_config = ConfigDict(extra="forbid", frozen=False, populate_by_name=True)
