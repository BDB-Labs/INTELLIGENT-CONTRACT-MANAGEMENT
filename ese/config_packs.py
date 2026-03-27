"""Shipped config-pack registry for opinionated ESE installations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PackRoleDefinition:
    key: str
    responsibility: str
    prompt: str
    temperature: float = 0.2


@dataclass(frozen=True)
class ConfigPackDefinition:
    key: str
    title: str
    summary: str
    preset: str
    goal_profile: str
    roles: tuple[PackRoleDefinition, ...]


_CONSTRUCTION_ROLES = (
    PackRoleDefinition(
        key="document_intake_analyst",
        responsibility="Classify uploaded contract package documents, identify missing required inputs, and produce the document inventory summary.",
        prompt=(
            "You are the document_intake_analyst for a contractor-side construction bid review. "
            "Classify the supplied package, identify missing expected documents, and summarize package quality. "
            "Use findings for intake gaps and ambiguity, artifacts for document_inventory.json, and next_steps for concrete follow-up requests."
        ),
    ),
    PackRoleDefinition(
        key="contract_risk_analyst",
        responsibility="Evaluate payment, indemnity, delay, claims, schedule, change-order, termination, and liability risk in the contract package.",
        prompt=(
            "You are the contract_risk_analyst for a contractor-side construction bid review. "
            "Focus on payment, indemnity, delay, claims, change-order, termination, flow-down, and liability risk. "
            "Use findings for material contract issues, cite clause locations when possible, and contribute to risk_findings.json."
        ),
    ),
    PackRoleDefinition(
        key="insurance_requirements_analyst",
        responsibility="Flag abnormal insurance limits, endorsements, additional insured requirements, waivers, and primary/noncontributory burdens.",
        prompt=(
            "You are the insurance_requirements_analyst for a contractor-side construction bid review. "
            "Focus on additional insured wording, waiver of subrogation, primary and noncontributory language, completed operations, unusual limits, and endorsements. "
            "Use findings for insurance anomalies and contribute to insurance_findings.json."
        ),
    ),
    PackRoleDefinition(
        key="funding_compliance_analyst",
        responsibility="Identify public funding overlays and the resulting labor, procurement, sourcing, reporting, or documentation obligations.",
        prompt=(
            "You are the funding_compliance_analyst for a contractor-side construction bid review. "
            "Identify federal, state, or local funding overlays such as Davis-Bacon, certified payroll, DBE, domestic sourcing, and procurement conditions. "
            "Use findings for compliance issues and contribute to compliance_findings.json."
        ),
    ),
    PackRoleDefinition(
        key="relationship_strategy_analyst",
        responsibility="Assess owner posture, negotiation sensitivity, political constraints, and leverage points that affect how hard to push on terms.",
        prompt=(
            "You are the relationship_strategy_analyst for a contractor-side construction bid review. "
            "Assess owner posture, negotiation sensitivity, politically rigid issues, and leverage points. "
            "Use findings for material relationship risks and next_steps for negotiation posture guidance."
        ),
    ),
    PackRoleDefinition(
        key="context_intelligence_analyst",
        responsibility="Extract internal-only budget, oversight, schedule, and visibility signals from context documents in the package.",
        prompt=(
            "You are the context_intelligence_analyst for a public-infrastructure contract review. "
            "Assess funding flexibility, schedule pressure, oversight intensity, and public visibility from budgets, board records, audits, and status materials. "
            "Use findings only for evidence gaps and contribute to context_profile.json."
        ),
    ),
    PackRoleDefinition(
        key="procurement_structure_analyst",
        responsibility="Profile delivery method, procurement method, payment mechanism, governance traces, and transport-procurement clause families in the package.",
        prompt=(
            "You are the procurement_structure_analyst for a public-infrastructure contract review. "
            "Identify delivery method, procurement method, payment mechanism, governance artifacts, and clause families such as GMP off-ramps, appropriation limits, Public Records Act handling, ICE, and WBS reporting. "
            "Use findings for metadata ambiguity and contribute to procurement_profile.json."
        ),
    ),
    PackRoleDefinition(
        key="outcome_evidence_analyst",
        responsibility="Extract outcome and governance evidence such as awards, status updates, change orders, settlements, audits, closeout, and terminations.",
        prompt=(
            "You are the outcome_evidence_analyst for a public-infrastructure contract review. "
            "Look for award, status, change-order, settlement, audit, litigation, closeout, termination, takeover, or bankruptcy signals. "
            "Do not invent outcomes; make missing evidence explicit and contribute to outcome_evidence.json."
        ),
    ),
    PackRoleDefinition(
        key="adversarial_reviewer",
        responsibility="Challenge optimistic assumptions, surface contradictions across analysts, and hunt for missed hazards before a bid decision is made.",
        prompt=(
            "You are the adversarial_reviewer for a contractor-side construction bid review. "
            "Challenge optimistic assumptions, hunt for missed hazards, and surface contradictions across analysts. "
            "Use findings for missed risks and contradictions, and use next_steps to require human review when needed."
        ),
        temperature=0.6,
    ),
    PackRoleDefinition(
        key="bid_decision_analyst",
        responsibility="Produce the go, go-with-conditions, or no-go recommendation with executive rationale and must-fix items.",
        prompt=(
            "You are the bid_decision_analyst for a contractor-side construction bid review. "
            "Produce an executive recommendation of go, go-with-conditions, or no-go, and make the rationale explicit. "
            "Use findings for supporting reasons and contribute to decision_summary.json."
        ),
    ),
    PackRoleDefinition(
        key="obligation_register_builder",
        responsibility="Convert clauses into trackable notice deadlines, reporting duties, pre-start requirements, and other post-award obligations.",
        prompt=(
            "You are the obligation_register_builder for a contractor-side construction bid review. "
            "Identify notice deadlines, reporting duties, pre-start requirements, and other trackable obligations. "
            "Use findings for obligations that could be missed operationally and contribute to obligations_register.json."
        ),
    ),
)


_PACKS: dict[str, ConfigPackDefinition] = {
    "construction-contract-intelligence": ConfigPackDefinition(
        key="construction-contract-intelligence",
        title="Construction Contract Intelligence",
        summary="Fixed contractor-side bid-review pack for construction and infrastructure contract evaluation.",
        preset="strict",
        goal_profile="high-quality",
        roles=_CONSTRUCTION_ROLES,
    ),
}


def list_config_packs() -> list[ConfigPackDefinition]:
    return list(_PACKS.values())


def get_config_pack(key: str) -> ConfigPackDefinition:
    clean_key = (key or "").strip().lower()
    pack = _PACKS.get(clean_key)
    if pack is None:
        available = ", ".join(sorted(_PACKS))
        raise KeyError(f"Unknown config pack '{key}'. Choose one of: {available}")
    return pack
