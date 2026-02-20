from typing import List, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from enum import Enum
from datetime import datetime, timezone


class EventDetails(BaseModel):
    event_name: Literal["Compliance Review Initiated"] = Field(
        ...,
        description="Fixed event name indicating the start of a compliance review."
    )
    timestamp: datetime = Field(
        ...,
        description="UTC timestamp indicating when the compliance review was initiated."
    )
    initiating_user_id: str = Field(
        ...,
        description="Temporary identifier of the user or system initiating the review."
    )
    source_system: Literal["Red Oak"] = Field(
        ...,
        description="Source system that initiated the compliance workflow."
    )

    @field_validator("timestamp")
    @classmethod
    def enforce_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        elif value.tzinfo != timezone.utc:
            return value.astimezone(timezone.utc)
        return value

    model_config = ConfigDict(extra="forbid")


class DocumentMetadata(BaseModel):
    document_id: str = Field(..., description="Temporary unique identifier for the document.")
    document_name: str = Field(..., description="Human-readable name of the document.")
    document_type: str = Field(..., description="Type or classification of the document.")
    file_format: Literal["PDF"] = Field(..., description="File format of the document. Always PDF.")
    model_config = ConfigDict(extra="forbid")


class RegulatoryFramework(str, Enum):
    SEC = "SEC"
    FINRA = "FINRA"


class ComplianceContext(BaseModel):
    audience_classification: str = Field(...)
    product_program_identifiers: str = Field(...)
    regulatory_frameworks: List[RegulatoryFramework] = Field(...)
    material_classification: str = Field(...)
    update_frequency: str = Field(...)

    @field_validator("regulatory_frameworks")
    @classmethod
    def enforce_fixed_frameworks(cls, value: List[RegulatoryFramework]):
        allowed = {RegulatoryFramework.SEC, RegulatoryFramework.FINRA}
        if set(value) != allowed:
            raise ValueError("regulatory_frameworks must contain exactly ['SEC', 'FINRA']")
        return value

    model_config = ConfigDict(extra="forbid")


class Metadata(BaseModel):
    event_details: EventDetails = Field(...)
    document_metadata: DocumentMetadata = Field(...)
    compliance_context: ComplianceContext = Field(...)
    model_config = ConfigDict(extra="forbid")
