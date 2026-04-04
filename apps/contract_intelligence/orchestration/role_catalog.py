from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainRole:
    key: str
    purpose: str
    output_artifact: str
    output_schema: str
    prompt_file: str
    stage: str


BID_REVIEW_ROLE_CATALOG: tuple[DomainRole, ...] = (
    DomainRole(
        key="document_intake_analyst",
        purpose="Classify uploaded documents, extract metadata, and identify missing inputs.",
        output_artifact="document_inventory.json",
        output_schema="document_inventory.schema.json",
        prompt_file="document_intake_analyst.md",
        stage="intake",
    ),
    DomainRole(
        key="contract_risk_analyst",
        purpose="Identify contractor-side commercial, claims, schedule, and liability risk.",
        output_artifact="risk_findings.json",
        output_schema="finding.schema.json",
        prompt_file="contract_risk_analyst.md",
        stage="analysis",
    ),
    DomainRole(
        key="insurance_requirements_analyst",
        purpose="Flag abnormal coverage limits, endorsements, and insured requirements.",
        output_artifact="insurance_findings.json",
        output_schema="insurance_anomaly.schema.json",
        prompt_file="insurance_requirements_analyst.md",
        stage="analysis",
    ),
    DomainRole(
        key="funding_compliance_analyst",
        purpose="Detect public-funding overlays and resulting operational obligations.",
        output_artifact="compliance_findings.json",
        output_schema="finding.schema.json",
        prompt_file="funding_compliance_analyst.md",
        stage="analysis",
    ),
    DomainRole(
        key="relationship_strategy_analyst",
        purpose="Assess negotiation posture, owner sensitivity, and stakeholder dynamics.",
        output_artifact="relationship_strategy.json",
        output_schema="relationship_strategy.schema.json",
        prompt_file="relationship_strategy_analyst.md",
        stage="analysis",
    ),
    DomainRole(
        key="relationship_advisor",
        purpose="Provide long-term relationship impact assessment and negotiation strategy guidance based on historical patterns and entity-specific context.",
        output_artifact="relationship_advice.json",
        output_schema="relationship_advice.schema.json",
        prompt_file="relationship_advisor.md",
        stage="advisory",
    ),
    DomainRole(
        key="context_intelligence_analyst",
        purpose="Extract internal-only budget, oversight, schedule, and public-visibility signals from context documents.",
        output_artifact="context_profile.json",
        output_schema="context_profile.schema.json",
        prompt_file="context_intelligence_analyst.md",
        stage="analysis",
    ),
    DomainRole(
        key="procurement_structure_analyst",
        purpose="Profile delivery method, procurement method, payment mechanism, and governance traces in the package.",
        output_artifact="procurement_profile.json",
        output_schema="procurement_profile.schema.json",
        prompt_file="procurement_structure_analyst.md",
        stage="analysis",
    ),
    DomainRole(
        key="outcome_evidence_analyst",
        purpose="Extract governance and outcome evidence signals such as awards, change orders, audits, closeout, and terminations.",
        output_artifact="outcome_evidence.json",
        output_schema="outcome_evidence.schema.json",
        prompt_file="outcome_evidence_analyst.md",
        stage="analysis",
    ),
    DomainRole(
        key="bid_decision_analyst",
        purpose="Produce the executive recommendation and key pursue conditions.",
        output_artifact="decision_summary.json",
        output_schema="decision_summary.schema.json",
        prompt_file="bid_decision_analyst.md",
        stage="synthesis",
    ),
    DomainRole(
        key="negotiation_strategist",
        purpose="Synthesize all technical, contextual, and relationship insights into actionable negotiation recommendations with implementation roadmap.",
        output_artifact="negotiation_strategy.json",
        output_schema="negotiation_strategy.schema.json",
        prompt_file="negotiation_strategist.md",
        stage="synthesis",
    ),
    DomainRole(
        key="obligation_register_builder",
        purpose="Convert contract terms into trackable obligations and notice triggers.",
        output_artifact="obligations_register.json",
        output_schema="obligation.schema.json",
        prompt_file="obligation_register_builder.md",
        stage="synthesis",
    ),
    DomainRole(
        key="adversarial_reviewer",
        purpose="Challenge optimistic assumptions and surface contradictions or missed hazards.",
        output_artifact="review_challenges.json",
        output_schema="review_challenges.schema.json",
        prompt_file="adversarial_reviewer.md",
        stage="challenge",
    ),
)


def role_keys() -> tuple[str, ...]:
    return tuple(role.key for role in BID_REVIEW_ROLE_CATALOG)


def artifact_contract() -> dict[str, str]:
    return {
        role.output_artifact: role.output_schema for role in BID_REVIEW_ROLE_CATALOG
    }
