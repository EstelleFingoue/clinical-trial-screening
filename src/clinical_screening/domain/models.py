from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(StrEnum):
    ANAPATH = "anapath"
    BILAN = "bilan"
    RCP = "rcp"
    CONSULTATION = "consultation"
    COURRIER = "courrier"


class DecisionLabel(StrEnum):
    ELIGIBLE = "eligible"
    NON_ELIGIBLE = "non_eligible"
    INDETERMINABLE = "indeterminable"


class ExtractionMethod(StrEnum):
    REGEX = "regex"
    LLM = "llm"
    PRECOMPUTED = "precomputed"


class OCRDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    text: str
    page_count: int = Field(ge=1, le=5)
    source_id: str = Field(description="Identifiant technique non nominatif")


class VariableResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: Any = None
    confidence: str
    method: ExtractionMethod
    evidence: str = ""
    document_type: DocumentType | None = None
    alternatives: list[Any] = Field(default_factory=list)


class PatientProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str
    variables: dict[str, VariableResult]
    conflicts: list[str] = Field(default_factory=list)


class TrialDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trial: str
    decision: DecisionLabel
    reason: str
    criteria: dict[str, bool | None]
    human_review: list[str] = Field(default_factory=list)


class PipelineReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str
    provider: str
    provider_mode: str
    documents: list[OCRDocument]
    profile: PatientProfile
    decisions: dict[str, TrialDecision]
    warnings: list[str] = Field(default_factory=list)


class ScenarioSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    category: str
    description: str
    document_types: list[DocumentType]
    expected: dict[str, DecisionLabel]


class ProviderStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    model: str
    configured: bool
    live: bool


class LLMVariableAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str | int | float | bool | None
    citation: str = ""


class LLMExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variables: dict[str, LLMVariableAnswer]
