from __future__ import annotations

from datetime import datetime

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


class ProcurementProfile(BaseModel):
    project_id: str
    agreement_type: str
    project_sector: str
    payment_mechanism: str
    procurement_method: str
    public_text_quality: str
    governance_artifacts_present: list[str] = Field(default_factory=list)
    detected_clause_families: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ContextSignal(BaseModel):
    signal_type: str
    intensity: str
    summary: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    internal_only: bool = True


class ContextProfile(BaseModel):
    project_id: str
    funding_flexibility: str
    schedule_pressure: str
    oversight_intensity: str
    public_visibility: str
    internal_only: bool = True
    signals: list[ContextSignal] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class OutcomeEvent(BaseModel):
    event_type: str
    impact_types: list[str] = Field(default_factory=list)
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_document_type: str
    evidence_source_type: str
    evidence: list[EvidenceRef] = Field(default_factory=list)


class OutcomeEvidenceBundle(BaseModel):
    project_id: str
    outcome_status: str
    governance_artifacts_present: list[str] = Field(default_factory=list)
    events: list[OutcomeEvent] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)
    monitoring_recommendations: list[str] = Field(default_factory=list)


class ProjectDocumentRecord(BaseModel):
    document_id: str
    filename: str
    document_type: str
    required_for_bid_review: bool
    text_available: bool = False
    text_source: str = "unavailable"
    clause_count: int = 0


class CaseRunIndexEntry(BaseModel):
    run_id: str
    run_type: str
    created_at: datetime
    recommendation: Recommendation
    overall_risk: Severity
    artifacts_dir: str
    artifact_count: int


class AcceptedRisk(BaseModel):
    source_finding_id: str
    role: str
    category: str
    title: str
    severity: Severity
    recommended_action: str
    carry_forward_reason: str


class NegotiatedChange(BaseModel):
    change_id: str
    title: str
    summary: str
    status: str = "captured"
    source_reference: str | None = None


class ContractCommitIndexEntry(BaseModel):
    commit_id: str
    created_at: datetime
    source_run_id: str
    obligations_count: int
    accepted_risks_count: int
    negotiated_changes_count: int


class MonitoringRunIndexEntry(BaseModel):
    run_id: str
    created_at: datetime
    source_commit_id: str
    alerts_count: int
    due_count: int
    late_count: int
    satisfied_count: int


class BidReviewRunRecord(BaseModel):
    run_id: str
    run_type: str = "bid_review"
    project_id: str
    created_at: datetime
    source_project_dir: str
    artifacts_dir: str
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    document_inventory: dict[str, object]
    decision_summary: DecisionSummary
    context_profile: ContextProfile
    procurement_profile: ProcurementProfile
    outcome_evidence: OutcomeEvidenceBundle
    relationship_strategy: dict[str, object]
    review_challenges: dict[str, object]
    obligations_count: int


class ContractCommitRecord(BaseModel):
    commit_id: str
    project_id: str
    created_at: datetime
    source_project_dir: str
    committed_contract_dir: str
    source_run_id: str
    decision_summary: DecisionSummary
    procurement_profile: ProcurementProfile
    outcome_status: str
    accepted_risks: list[AcceptedRisk] = Field(default_factory=list)
    negotiated_changes: list[NegotiatedChange] = Field(default_factory=list)
    committed_documents: list[ProjectDocumentRecord] = Field(default_factory=list)
    obligations_path: str
    obligations_count: int


class MonitoredObligation(BaseModel):
    obligation_id: str
    title: str
    source_clause: str
    owner_role: str
    severity_if_missed: Severity
    status: str
    summary: str
    next_due_at: datetime | None = None
    last_satisfied_at: datetime | None = None
    notes: list[str] = Field(default_factory=list)


class AlertRecord(BaseModel):
    alert_id: str
    obligation_id: str
    created_at: datetime
    severity: Severity
    alert_type: str
    status: str
    summary: str


class MonitoringRunRecord(BaseModel):
    run_id: str
    project_id: str
    created_at: datetime
    source_commit_id: str
    as_of_date: str
    status_inputs_path: str | None = None
    monitored_obligations: list[MonitoredObligation] = Field(default_factory=list)
    alerts: list[AlertRecord] = Field(default_factory=list)


class CaseRecord(BaseModel):
    project_id: str
    source_project_dir: str
    storage_dir: str
    latest_run_id: str
    latest_recommendation: Recommendation
    latest_overall_risk: Severity
    latest_agreement_type: str
    latest_project_sector: str
    latest_outcome_status: str
    total_runs: int
    run_history: list[CaseRunIndexEntry] = Field(default_factory=list)
    latest_commit_id: str | None = None
    total_commits: int = 0
    latest_obligations_count: int = 0
    commit_history: list[ContractCommitIndexEntry] = Field(default_factory=list)
    latest_monitoring_run_id: str | None = None
    total_monitoring_runs: int = 0
    monitoring_history: list[MonitoringRunIndexEntry] = Field(default_factory=list)
