from __future__ import annotations

from pydantic import BaseModel, Field

from apps.contract_intelligence.domain.enums import Recommendation, Severity


class EvidenceRef(BaseModel):
    document_id: str
    location: str
    excerpt: str | None = None


class Finding(BaseModel):
    id: str
    role: str
    category: str
    severity: Severity
    title: str
    summary: str
    recommended_action: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)


class DecisionSummary(BaseModel):
    project_id: str
    recommendation: Recommendation
    overall_risk: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    top_reasons: list[str] = Field(default_factory=list)
    must_fix_before_bid: list[str] = Field(default_factory=list)
    human_review_required: bool = True


class Obligation(BaseModel):
    id: str
    source_clause: str
    title: str
    obligation_type: str
    trigger: str
    due_rule: str
    owner_role: str
    severity_if_missed: Severity
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ProjectDocumentRecord(BaseModel):
    document_id: str
    filename: str
    document_type: str
    required_for_bid_review: bool
    text_available: bool = False
    text_source: str = "unavailable"
    clause_count: int = 0
