from __future__ import annotations

from dataclasses import dataclass

from apps.contract_intelligence.orchestration.role_catalog import (
    BID_REVIEW_ROLE_CATALOG,
)


@dataclass(frozen=True)
class PipelineStage:
    key: str
    description: str
    roles: tuple[str, ...]
    outputs: tuple[str, ...]


def bid_review_pipeline() -> tuple[PipelineStage, ...]:
    return (
        PipelineStage(
            key="intake",
            description="Classify uploaded material and identify missing expected documents.",
            roles=("document_intake_analyst",),
            outputs=("document_inventory.json",),
        ),
        PipelineStage(
            key="analysis",
            description="Run domain specialists in parallel over the normalized contract package.",
            roles=(
                "contract_risk_analyst",
                "insurance_requirements_analyst",
                "funding_compliance_analyst",
                "relationship_strategy_analyst",
                "context_intelligence_analyst",
                "procurement_structure_analyst",
                "outcome_evidence_analyst",
            ),
            outputs=(
                "risk_findings.json",
                "insurance_findings.json",
                "compliance_findings.json",
                "relationship_strategy.json",
                "context_profile.json",
                "procurement_profile.json",
                "outcome_evidence.json",
            ),
        ),
        PipelineStage(
            key="advisory",
            description="Assess long-term relationship impact and provide entity-specific negotiation guidance.",
            roles=("relationship_advisor",),
            outputs=("relationship_advice.json",),
        ),
        PipelineStage(
            key="challenge",
            description="Apply explicit adversarial review before recommendation synthesis.",
            roles=("adversarial_reviewer",),
            outputs=("review_challenges.json",),
        ),
        PipelineStage(
            key="synthesis",
            description="Assemble the executive packet, negotiation strategy, and obligations preview.",
            roles=(
                "bid_decision_analyst",
                "negotiation_strategist",
                "obligation_register_builder",
            ),
            outputs=(
                "decision_summary.json",
                "negotiation_strategy.json",
                "obligations_register.json",
            ),
        ),
    )


def universal_casework_workflow() -> tuple[str, ...]:
    return (
        "ingest",
        "structure",
        "evaluate",
        "challenge",
        "synthesize",
        "decide",
        "commit",
        "monitor",
    )


def bid_review_artifacts() -> tuple[str, ...]:
    artifacts = {role.output_artifact for role in BID_REVIEW_ROLE_CATALOG}
    return tuple(sorted(artifacts))
