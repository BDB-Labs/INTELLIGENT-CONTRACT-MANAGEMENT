from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.contract_intelligence.domain.enums import (
    AnalysisPerspective,
    DocumentType,
    Recommendation,
    Severity,
)
from apps.contract_intelligence.domain.models import (
    ContextProfile,
    ContextSignal,
    DecisionSummary,
    EvidenceRef,
    Finding,
    Obligation,
    OutcomeEvent,
    OutcomeEvidenceBundle,
    ProcurementProfile,
    ProjectDocumentRecord,
)
from apps.contract_intelligence.ingestion.document_classifier import (
    REQUIRED_BID_REVIEW_DOCUMENTS,
    missing_required_documents,
)
from apps.contract_intelligence.ingestion.project_loader import (
    ClauseSpan,
    LoadedDocument,
    iter_project_documents,
)
from apps.contract_intelligence.paths import (
    resolve_existing_directory,
    resolve_output_directory,
)
from apps.contract_intelligence.storage import FileSystemCaseStore


SEVERITY_ORDER = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Confidence score constants for finding and decision calculations
_SINGLE_EVIDENCE_CONFIDENCE = 0.68
_MULTI_EVIDENCE_CONFIDENCE = 0.78
_MAX_FINDING_CONFIDENCE = 0.90
_PUBLIC_OVERLAY_CONFIDENCE = 0.72
_NO_OVERLAY_CONFIDENCE = 0.56
_BASE_DECISION_CONFIDENCE = 0.84
_MISSING_DOC_PENALTY = 0.08
_UNREADABLE_DOC_PENALTY = 0.04
_HIGH_FINDING_PENALTY = 0.08
_MAX_UNREADABLE_PENALTY_COUNT = 3
_MIN_DECISION_CONFIDENCE = 0.35


_AGENCY_FINDING_OVERRIDES: dict[str, dict[str, str]] = {
    "payment_terms": {
        "title": "Contingent payment language is likely to draw contractor resistance",
        "summary": "Payment appears conditioned on upstream funding or owner payment, which may drive pricing pressure or negotiation friction.",
        "recommended_action": "Decide whether this allocation is intentional and defensible, or whether fixed timing for undisputed amounts would preserve competition.",
    },
    "indemnity": {
        "title": "Broad indemnity language may create negotiation and enforceability risk",
        "summary": "The package appears to require expansive defense and indemnity obligations that contractors are likely to challenge.",
        "recommended_action": "Confirm the intended negligence allocation and whether a narrower negligence-based standard would preserve protection without depressing bidder appetite.",
    },
    "delay_exposure": {
        "title": "No-damages-for-delay language may increase claim and pricing pressure",
        "summary": "Delay remedies appear limited to time extensions, which contractors are likely to challenge on owner-caused delay scenarios.",
        "recommended_action": "Decide whether the clause is a hard policy requirement or whether targeted relief for owner-caused delay would better preserve competition.",
    },
    "change_orders": {
        "title": "Strict written change authorization may impair field flexibility",
        "summary": "Compensation appears limited to written authorization issued before work proceeds, which can create field-dispute risk.",
        "recommended_action": "Preserve notice discipline but consider a practical emergency-direction path so valid changes do not turn into claims posture.",
    },
    "termination": {
        "title": "Termination-for-convenience language may need clearer recovery boundaries",
        "summary": "Owner termination rights appear broad and may leave contractor recovery language open to dispute.",
        "recommended_action": "Clarify compensable closeout costs and excluded damages so the clause stays predictable and defensible.",
    },
    "additional_insured": {
        "title": "Additional-insured wording may be broader than necessary",
        "summary": "The package appears to require owner-side additional-insured language that contractors may price or resist depending on form.",
        "recommended_action": "Confirm the exact endorsement objective and limit the requirement to the coverage the agency actually needs.",
    },
    "waiver_subrogation": {
        "title": "Waiver-of-subrogation wording may increase pricing pressure",
        "summary": "The package includes waiver-of-subrogation requirements that may be treated as cost or carrier-availability issues by bidders.",
        "recommended_action": "Confirm whether the waiver is essential across all lines or whether it can be narrowed to preserve marketability.",
    },
    "primary_noncontributory": {
        "title": "Primary and noncontributory wording may be broader than market forms support",
        "summary": "The insurance stack appears to require primary/noncontributory positioning that contractors may challenge if forms are limited.",
        "recommended_action": "Keep the intended priority of coverage clear, but avoid endorsement wording the market may not support cleanly.",
    },
    "completed_operations": {
        "title": "Completed-operations duration may price higher than expected",
        "summary": "The package appears to impose completed-operations requirements that can create longer-tail cost and negotiation friction.",
        "recommended_action": "Verify that the duration and limits are truly necessary and align them with market-available forms where possible.",
    },
    "davis_bacon": {
        "title": "Federal wage requirements appear material to bid-stage compliance",
        "summary": "The package references federal wage requirements that must be complete and administrable before issue or award.",
        "recommended_action": "Confirm wage determinations, flow-down language, and payroll administration requirements are complete and audit-ready.",
    },
    "certified_payroll": {
        "title": "Certified payroll workflow should be explicit at intake",
        "summary": "The package appears to require recurring payroll reporting that should be clear and administrable for bidders.",
        "recommended_action": "Make the reporting cadence and owner review workflow explicit so the requirement is enforceable and predictable.",
    },
    "buy_america": {
        "title": "Domestic sourcing rules may need clearer procurement administration",
        "summary": "The package appears to include domestic content obligations that can constrain supplier selection and bid confidence.",
        "recommended_action": "Confirm affected materials, certification expectations, and any waiver path so bidders can price the requirement accurately.",
    },
    "dbe_participation": {
        "title": "DBE obligations should be fully specified before issue or award",
        "summary": "The package references disadvantaged-business participation or reporting requirements that need precise bid-stage instructions.",
        "recommended_action": "Ensure participation, documentation, and tracking expectations are explicit enough to survive protest or audit review.",
    },
    "cmgc_offramp": {
        "title": "CMGC off-ramp language may price preconstruction participation",
        "summary": "The package appears to let the owner reject GMP pricing or decline later construction award, which contractors will likely price carefully.",
        "recommended_action": "Be explicit about preconstruction compensation and the later award decision path so bidders can assess the offramp honestly.",
    },
    "appropriation_limit": {
        "title": "Appropriation contingency appears necessary but may need clearer recovery terms",
        "summary": "Public funding language appears to limit enforceability to appropriated or available funds, which may trigger contractor concern if recovery is vague.",
        "recommended_action": "Preserve statutory funding limits, but make the contractor's recovery path clear for work performed and orderly demobilization.",
    },
    "conflict_of_interest": {
        "title": "Conflict-of-interest language may affect bidder confidence if cure paths are vague",
        "summary": "The package appears to impose conflict-of-interest certification or disclosure obligations tied to award or termination rights.",
        "recommended_action": "Keep the control objective, but make the disclosure workflow and cure consequences specific enough to avoid avoidable bidder drop-off.",
    },
    "umbrella_drop_down": {
        "title": "Umbrella drop-down wording may exceed common market terms",
        "summary": "The package appears to require umbrella or excess coverage to drop down in ways contractors may treat as unusual or costly.",
        "recommended_action": "Confirm whether the drop-down feature is essential and limit it to commercially available forms where possible.",
    },
}


@dataclass(frozen=True)
class FindingRule:
    role: str
    category: str
    severity: Severity
    title: str
    summary: str
    recommended_action: str
    patterns: tuple[str, ...]
    document_types: tuple[DocumentType, ...] = ()


@dataclass(frozen=True)
class BidReviewRunResult:
    project_id: str
    artifacts_dir: Path
    artifact_paths: dict[str, Path]
    decision_summary: DecisionSummary
    case_record_path: Path
    run_record_path: Path


@dataclass(frozen=True)
class LabelRule:
    label: str
    patterns: tuple[str, ...]
    document_types: tuple[DocumentType, ...] = ()


@dataclass(frozen=True)
class ClauseFamilyRule:
    tag: str
    patterns: tuple[str, ...]
    document_types: tuple[DocumentType, ...] = ()


@dataclass(frozen=True)
class OutcomeEventRule:
    event_type: str
    summary: str
    impact_types: tuple[str, ...]
    patterns: tuple[str, ...]
    document_types: tuple[DocumentType, ...] = ()


CONTRACT_RISK_RULES: tuple[FindingRule, ...] = (
    FindingRule(
        role="contract_risk_analyst",
        category="payment_terms",
        severity=Severity.HIGH,
        title="Pay-if-paid structure shifts collection risk downstream",
        summary="Payment appears conditioned on owner payment to the prime contractor.",
        recommended_action="Seek pay-when-paid language or an outside payment deadline.",
        patterns=(r"pay[-\s]+if[-\s]+paid", r"conditioned upon.*receipt of payment"),
        document_types=(
            DocumentType.PRIME_CONTRACT,
            DocumentType.GENERAL_CONDITIONS,
            DocumentType.SPECIAL_PROVISIONS,
        ),
    ),
    FindingRule(
        role="contract_risk_analyst",
        category="indemnity",
        severity=Severity.HIGH,
        title="Broad indemnity language may exceed reasonable contractor risk",
        summary="The package appears to require expansive defense and indemnity obligations.",
        recommended_action="Seek negligence-based limits and remove duty-to-defend language where possible.",
        patterns=(
            r"defend,?\s+indemnify,?\s+and\s+hold harmless",
            r"indemnify.*whether.*caused in part",
        ),
        document_types=(
            DocumentType.PRIME_CONTRACT,
            DocumentType.GENERAL_CONDITIONS,
            DocumentType.SPECIAL_PROVISIONS,
        ),
    ),
    FindingRule(
        role="contract_risk_analyst",
        category="delay_exposure",
        severity=Severity.HIGH,
        title="No-damages-for-delay language compresses schedule recovery options",
        summary="Delay remedies appear limited to time extensions rather than monetary recovery.",
        recommended_action="Preserve compensation rights for owner-caused delay, disruption, or resequencing.",
        patterns=(r"no damages? for delay", r"sole remedy.*extension of time"),
        document_types=(
            DocumentType.PRIME_CONTRACT,
            DocumentType.GENERAL_CONDITIONS,
            DocumentType.SPECIAL_PROVISIONS,
        ),
    ),
    FindingRule(
        role="contract_risk_analyst",
        category="change_orders",
        severity=Severity.MEDIUM,
        title="Strict written change authorization may bar valid field-change recovery",
        summary="Compensation may be limited to changes approved in writing before work proceeds.",
        recommended_action="Allow written notice plus later pricing when urgent field direction occurs.",
        patterns=(
            r"written change order",
            r"no extra compensation unless authorized in writing",
        ),
        document_types=(
            DocumentType.PRIME_CONTRACT,
            DocumentType.GENERAL_CONDITIONS,
            DocumentType.SPECIAL_PROVISIONS,
        ),
    ),
    FindingRule(
        role="contract_risk_analyst",
        category="termination",
        severity=Severity.MEDIUM,
        title="Termination-for-convenience rights may leave recovery ambiguous",
        summary="Owner termination rights appear broad and may limit contractor recovery to narrow cost buckets.",
        recommended_action="Clarify recovery for demobilization, committed costs, and reasonable overhead.",
        patterns=(r"termination for convenience",),
        document_types=(
            DocumentType.PRIME_CONTRACT,
            DocumentType.GENERAL_CONDITIONS,
            DocumentType.SPECIAL_PROVISIONS,
        ),
    ),
)


INSURANCE_RULES: tuple[FindingRule, ...] = (
    FindingRule(
        role="insurance_requirements_analyst",
        category="additional_insured",
        severity=Severity.HIGH,
        title="Additional-insured requirement needs broker review",
        summary="The package appears to require owner-side additional-insured coverage language.",
        recommended_action="Confirm endorsement form and limit the requirement to ongoing/completed operations as appropriate.",
        patterns=(r"additional insured",),
        document_types=(
            DocumentType.INSURANCE_REQUIREMENTS,
            DocumentType.SPECIAL_PROVISIONS,
            DocumentType.PRIME_CONTRACT,
        ),
    ),
    FindingRule(
        role="insurance_requirements_analyst",
        category="waiver_subrogation",
        severity=Severity.MEDIUM,
        title="Waiver-of-subrogation language may exceed current program assumptions",
        summary="The package includes waiver-of-subrogation requirements that can affect program cost and claims posture.",
        recommended_action="Confirm carrier availability and price impact before bid submission.",
        patterns=(r"waiver of subrogation",),
        document_types=(
            DocumentType.INSURANCE_REQUIREMENTS,
            DocumentType.SPECIAL_PROVISIONS,
        ),
    ),
    FindingRule(
        role="insurance_requirements_analyst",
        category="primary_noncontributory",
        severity=Severity.MEDIUM,
        title="Primary and noncontributory wording should be confirmed against available endorsements",
        summary="The insurance stack appears to require primary/noncontributory positioning.",
        recommended_action="Confirm exact endorsement wording and whether it is available on required lines.",
        patterns=(r"primary and noncontributory",),
        document_types=(
            DocumentType.INSURANCE_REQUIREMENTS,
            DocumentType.SPECIAL_PROVISIONS,
        ),
    ),
    FindingRule(
        role="insurance_requirements_analyst",
        category="completed_operations",
        severity=Severity.MEDIUM,
        title="Completed-operations duration may carry longer-tail cost than expected",
        summary="The package appears to impose completed-operations coverage requirements after project completion.",
        recommended_action="Confirm duration, limits, and compatibility with current carrier terms.",
        patterns=(r"completed operations",),
        document_types=(
            DocumentType.INSURANCE_REQUIREMENTS,
            DocumentType.SPECIAL_PROVISIONS,
        ),
    ),
)


COMPLIANCE_RULES: tuple[FindingRule, ...] = (
    FindingRule(
        role="funding_compliance_analyst",
        category="davis_bacon",
        severity=Severity.HIGH,
        title="Davis-Bacon obligations likely apply",
        summary="The package references federal wage requirements that can materially affect payroll administration.",
        recommended_action="Confirm wage determinations, certified payroll workflow, and subcontractor compliance readiness.",
        patterns=(r"davis[-\s]+bacon", r"prevailing wage"),
        document_types=(
            DocumentType.FUNDING_DOCUMENT,
            DocumentType.PROCUREMENT_DOCUMENT,
            DocumentType.SPECIAL_PROVISIONS,
        ),
    ),
    FindingRule(
        role="funding_compliance_analyst",
        category="certified_payroll",
        severity=Severity.MEDIUM,
        title="Certified payroll administration appears required",
        summary="The package appears to require recurring payroll reporting.",
        recommended_action="Assign payroll compliance ownership and confirm weekly reporting capability before bid submission.",
        patterns=(r"certified payroll",),
        document_types=(
            DocumentType.FUNDING_DOCUMENT,
            DocumentType.PROCUREMENT_DOCUMENT,
            DocumentType.SPECIAL_PROVISIONS,
        ),
    ),
    FindingRule(
        role="funding_compliance_analyst",
        category="buy_america",
        severity=Severity.MEDIUM,
        title="Domestic sourcing rules may constrain procurement flexibility",
        summary="The package appears to include Buy America or similar domestic content obligations.",
        recommended_action="Confirm affected materials, waiver path, and supplier certification process.",
        patterns=(r"buy america", r"buy american", r"domestic content"),
        document_types=(
            DocumentType.FUNDING_DOCUMENT,
            DocumentType.PROCUREMENT_DOCUMENT,
            DocumentType.SPECIAL_PROVISIONS,
        ),
    ),
    FindingRule(
        role="funding_compliance_analyst",
        category="dbe_participation",
        severity=Severity.MEDIUM,
        title="DBE participation and documentation may require bid-stage planning",
        summary="The package references disadvantaged-business participation or reporting requirements.",
        recommended_action="Confirm bid-stage documentation and post-award tracking expectations.",
        patterns=(r"\bdbe\b", r"disadvantaged business"),
        document_types=(
            DocumentType.FUNDING_DOCUMENT,
            DocumentType.PROCUREMENT_DOCUMENT,
            DocumentType.SPECIAL_PROVISIONS,
        ),
    ),
)


TRANSPORT_CONTRACT_RISK_RULES: tuple[FindingRule, ...] = (
    FindingRule(
        role="contract_risk_analyst",
        category="cmgc_offramp",
        severity=Severity.HIGH,
        title="CMGC pricing off-ramp may leave preconstruction effort stranded",
        summary="The package appears to let the owner reject GMP pricing or decline a later construction award.",
        recommended_action="Clarify recovery if the GMP is rejected and confirm that preconstruction services are fully compensable on their own.",
        patterns=(
            r"(?:guaranteed maximum price|\bgmp\b)[\s\S]{0,180}(?:not accepted|re-?advertis|not obligated to award)",
            r"no promise of construction award",
        ),
        document_types=(
            DocumentType.PRIME_CONTRACT,
            DocumentType.PROCUREMENT_DOCUMENT,
            DocumentType.ADDENDUM,
        ),
    ),
    FindingRule(
        role="contract_risk_analyst",
        category="appropriation_limit",
        severity=Severity.MEDIUM,
        title="Appropriation contingency can trigger downscope or cancellation risk",
        summary="Public funding language appears to limit enforceability to appropriated or available funds.",
        recommended_action="Tie any non-appropriation exit to payment for work performed, demobilization, and orderly scope reduction.",
        patterns=(
            r"subject to availability of funds",
            r"funds are appropriated",
            r"non-appropriation",
            r"budget act",
        ),
        document_types=(
            DocumentType.PRIME_CONTRACT,
            DocumentType.FUNDING_DOCUMENT,
            DocumentType.PROCUREMENT_DOCUMENT,
        ),
    ),
)


TRANSPORT_COMPLIANCE_RULES: tuple[FindingRule, ...] = (
    FindingRule(
        role="funding_compliance_analyst",
        category="conflict_of_interest",
        severity=Severity.MEDIUM,
        title="Conflict-of-interest disclosures may create bid-stage eligibility risk",
        summary="The package appears to impose conflict-of-interest certification or disclosure obligations tied to award or termination rights.",
        recommended_action="Confirm the disclosure workflow, affected affiliates, and any cure period before bid submission.",
        patterns=(r"conflict of interest", r"organizational conflict"),
        document_types=(
            DocumentType.PROCUREMENT_DOCUMENT,
            DocumentType.PRIME_CONTRACT,
            DocumentType.ADDENDUM,
        ),
    ),
)


TRANSPORT_INSURANCE_RULES: tuple[FindingRule, ...] = (
    FindingRule(
        role="insurance_requirements_analyst",
        category="umbrella_drop_down",
        severity=Severity.MEDIUM,
        title="Umbrella drop-down wording may exceed standard market terms",
        summary="The package appears to require umbrella or excess coverage to drop down if primary limits are impaired or exhausted.",
        recommended_action="Confirm market availability, price impact, and whether the drop-down feature can be limited to commercially available forms.",
        patterns=(r"drop[-\s]+down", r"umbrella", r"exhausted"),
        document_types=(
            DocumentType.INSURANCE_REQUIREMENTS,
            DocumentType.PRIME_CONTRACT,
            DocumentType.SPECIAL_PROVISIONS,
        ),
    ),
)


AGREEMENT_TYPE_RULES: tuple[LabelRule, ...] = (
    LabelRule("predevelopment_agreement", (r"predevelopment agreement",)),
    LabelRule(
        "cmgc_preconstruction_services",
        (
            r"construction manager/general contractor",
            r"\bcmgc\b",
            r"preconstruction services contract",
        ),
    ),
    LabelRule(
        "progressive_design_build",
        (r"progressive design[-\s]+build", r"phase one[\s\S]{0,80}design[-\s]+build"),
    ),
    LabelRule("design_build", (r"design[-\s]+build",)),
    LabelRule(
        "toll_concession", (r"toll concession", r"facility concession", r"toll revenue")
    ),
    LabelRule(
        "dbfom_availability_payment",
        (r"\bdbfom\b", r"availability payment[\s\S]{0,120}(?:operate|maintain)"),
    ),
    LabelRule("dbfm_availability_payment", (r"\bdbfm\b", r"availability payment")),
    LabelRule("on_call", (r"on[-\s]+call", r"task order")),
    LabelRule(
        "design_bid_build", (r"low bid", r"sealed bid", r"lowest responsible bidder")
    ),
)


PROJECT_SECTOR_RULES: tuple[LabelRule, ...] = (
    LabelRule("bridges", (r"bridge", r"viaduct")),
    LabelRule(
        "roads_highways",
        (r"highway", r"road", r"interchange", r"managed lanes", r"street", r"pavement"),
    ),
    LabelRule("stormwater", (r"storm drain", r"stormwater")),
    LabelRule("wastewater", (r"wastewater", r"sewer")),
    LabelRule(
        "transit", (r"transit", r"bus", r"rail", r"yard modernization", r"station")
    ),
    LabelRule("water_utilities", (r"water main", r"reservoir", r"outlet tower")),
    LabelRule("parking", (r"parking structure", r"parking")),
    LabelRule("buildings_facilities", (r"facility", r"building")),
)


PAYMENT_MECHANISM_RULES: tuple[LabelRule, ...] = (
    LabelRule("toll_revenue", (r"toll revenue", r"toll concession")),
    LabelRule(
        "availability_payment", (r"availability payment", r"availability deductions")
    ),
    LabelRule(
        "reimbursable_rates", (r"reimbursable", r"hourly rates", r"actual costs")
    ),
    LabelRule("guaranteed_maximum_price", (r"guaranteed maximum price", r"\bgmp\b")),
    LabelRule("phased_funding", (r"phased funding",)),
    LabelRule("milestone_payments", (r"milestone payment", r"progress milestone")),
    LabelRule("unit_price", (r"unit price",)),
    LabelRule("lump_sum", (r"lump sum", r"fixed price")),
)


PROCUREMENT_METHOD_RULES: tuple[LabelRule, ...] = (
    LabelRule("qbs_or_rfq", (r"\brfq\b", r"qualifications[-\s]+based", r"\bqbs\b")),
    LabelRule("best_value", (r"best value",)),
    LabelRule("low_bid", (r"low bid", r"sealed bid", r"lowest responsible bidder")),
    LabelRule("negotiated", (r"negotiated", r"sole source")),
)


CLAUSE_FAMILY_RULES: tuple[ClauseFamilyRule, ...] = (
    ClauseFamilyRule(
        "gmp_offramp",
        (
            r"(?:guaranteed maximum price|\bgmp\b)[\s\S]{0,180}(?:not accepted|re-?advertis|not obligated to award)",
            r"no promise of construction award",
        ),
        (
            DocumentType.PRIME_CONTRACT,
            DocumentType.PROCUREMENT_DOCUMENT,
            DocumentType.ADDENDUM,
        ),
    ),
    ClauseFamilyRule(
        "appropriation_limit",
        (
            r"subject to availability of funds",
            r"funds are appropriated",
            r"non-appropriation",
            r"budget act",
        ),
        (
            DocumentType.PRIME_CONTRACT,
            DocumentType.FUNDING_DOCUMENT,
            DocumentType.PROCUREMENT_DOCUMENT,
        ),
    ),
    ClauseFamilyRule(
        "open_book_cost_model",
        (r"open[-\s]+book", r"cost model", r"gmp documentation"),
        (
            DocumentType.PRIME_CONTRACT,
            DocumentType.PROCUREMENT_DOCUMENT,
            DocumentType.ADDENDUM,
        ),
    ),
    ClauseFamilyRule(
        "public_records_handling",
        (r"public records request", r"public records act"),
        (
            DocumentType.PRIME_CONTRACT,
            DocumentType.PROCUREMENT_DOCUMENT,
            DocumentType.ADDENDUM,
        ),
    ),
    ClauseFamilyRule(
        "independent_cost_estimator",
        (r"independent cost estimator", r"\bice\b"),
        (DocumentType.PRIME_CONTRACT, DocumentType.PROCUREMENT_DOCUMENT),
    ),
    ClauseFamilyRule(
        "reporting_wbs",
        (r"monthly progress report", r"work breakdown structure", r"\bwbs\b"),
        (DocumentType.PRIME_CONTRACT, DocumentType.PROCUREMENT_DOCUMENT),
    ),
    ClauseFamilyRule(
        "change_order_dispute_use",
        (
            r"change order[\s\S]{0,100}(?:resolve|dispute|claim)",
            r"dispute[\s\S]{0,100}change order",
        ),
        (
            DocumentType.PRIME_CONTRACT,
            DocumentType.GENERAL_CONDITIONS,
            DocumentType.CHANGE_ORDER,
            DocumentType.BOARD_RECORD,
        ),
    ),
    ClauseFamilyRule(
        "availability_deductions",
        (r"availability payment", r"performance deductions", r"unavailability"),
        (DocumentType.PRIME_CONTRACT, DocumentType.PROCUREMENT_DOCUMENT),
    ),
    ClauseFamilyRule(
        "community_benefits_schedule",
        (r"community benefits",),
        (
            DocumentType.PRIME_CONTRACT,
            DocumentType.PROCUREMENT_DOCUMENT,
            DocumentType.AMENDMENT,
        ),
    ),
    ClauseFamilyRule(
        "sustainability_schedule",
        (r"sustainability", r"energy management"),
        (
            DocumentType.PRIME_CONTRACT,
            DocumentType.PROCUREMENT_DOCUMENT,
            DocumentType.AMENDMENT,
        ),
    ),
)


OUTCOME_EVENT_RULES: tuple[OutcomeEventRule, ...] = (
    OutcomeEventRule(
        "award",
        "Award activity appears documented in the supplied package.",
        (),
        (r"contract award", r"notice of award", r"\bawarded\b"),
        (
            DocumentType.BOARD_RECORD,
            DocumentType.PROJECT_STATUS,
            DocumentType.AMENDMENT,
        ),
    ),
    OutcomeEventRule(
        "project_status_update",
        "A project status or progress update appears documented in the supplied package.",
        (),
        (
            r"percent complete",
            r"estimated completion",
            r"status update",
            r"progress report",
        ),
        (DocumentType.PROJECT_STATUS, DocumentType.BOARD_RECORD),
    ),
    OutcomeEventRule(
        "change_order",
        "Change-order activity appears documented in the supplied package.",
        ("scope_change",),
        (r"change order",),
        (DocumentType.CHANGE_ORDER, DocumentType.BOARD_RECORD, DocumentType.AMENDMENT),
    ),
    OutcomeEventRule(
        "settlement",
        "Settlement or release activity appears documented in the supplied package.",
        ("scope_change", "cost_overrun"),
        (r"settlement agreement", r"\bsettlement\b", r"\brelease\b", r"mediation"),
        (DocumentType.BOARD_RECORD, DocumentType.LITIGATION_RECORD),
    ),
    OutcomeEventRule(
        "closeout",
        "Closeout or final acceptance activity appears documented in the supplied package.",
        (),
        (r"closeout", r"final acceptance", r"substantial completion", r"\bcompleted\b"),
        (DocumentType.PROJECT_STATUS, DocumentType.BOARD_RECORD),
    ),
    OutcomeEventRule(
        "termination",
        "Termination activity appears documented in the supplied package.",
        ("scope_change",),
        (r"termination", r"\bterminated\b"),
        (
            DocumentType.BOARD_RECORD,
            DocumentType.LITIGATION_RECORD,
            DocumentType.AMENDMENT,
        ),
    ),
    OutcomeEventRule(
        "takeover",
        "Takeover or step-in activity appears documented in the supplied package.",
        ("governance_noncompliance",),
        (r"takeover", r"step[-\s]+in"),
        (DocumentType.BOARD_RECORD, DocumentType.LITIGATION_RECORD),
    ),
    OutcomeEventRule(
        "bankruptcy",
        "Bankruptcy or insolvency activity appears documented in the supplied package.",
        ("financing_refinance",),
        (r"bankruptcy", r"insolvenc"),
        (DocumentType.LITIGATION_RECORD, DocumentType.BOARD_RECORD),
    ),
    OutcomeEventRule(
        "scope_change",
        "Rescoping or cost-escalation activity appears documented in the supplied package.",
        ("scope_change", "cost_overrun"),
        (r"rescoped?", r"scope change", r"cost escalation", r"budget shortfall"),
        (DocumentType.BOARD_RECORD, DocumentType.AUDIT_REPORT, DocumentType.AMENDMENT),
    ),
    OutcomeEventRule(
        "audit_finding",
        "Audit or oversight findings appear documented in the supplied package.",
        ("governance_noncompliance",),
        (r"audit finding", r"internal control", r"overrun", r"finding"),
        (DocumentType.AUDIT_REPORT,),
    ),
)


NOTICE_DEADLINE_PATTERN = re.compile(
    r"(?P<context>(?:notice|claim|request)[^.:\n]{0,80}?within\s+(?P<days>\d+)\s+(?P<unit>business|calendar)?\s*days)",
    re.IGNORECASE,
)


def compute_project_id(project_dir: Path) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", project_dir.name.lower()).strip("-")
    return clean or "contract-project"


# NOTE: This function is duplicated from ese_bridge.py._normalize_analysis_perspective
# to avoid a circular import (ese_bridge imports from this module).
# Keep both implementations in sync if either changes.
def _normalize_analysis_perspective(
    value: str | AnalysisPerspective,
) -> AnalysisPerspective:
    if isinstance(value, AnalysisPerspective):
        return value
    normalized = str(value).strip().lower()
    try:
        return AnalysisPerspective(normalized)
    except ValueError as exc:
        raise ValueError(
            "analysis_perspective must be either 'vendor' or 'agency'."
        ) from exc


def _clause_evidence(
    document: LoadedDocument, clause: ClauseSpan, match: re.Match[str]
) -> EvidenceRef:
    clause_text = clause.text
    start = max(0, match.start() - 100)
    end = min(len(clause_text), match.end() + 100)
    excerpt = " ".join(clause_text[start:end].split())
    return EvidenceRef(
        document_id=document.document_id,
        location=clause.location,
        excerpt=excerpt,
    )


def _finding_text(
    rule: FindingRule, perspective: AnalysisPerspective
) -> tuple[str, str, str]:
    if perspective is AnalysisPerspective.AGENCY:
        override = _AGENCY_FINDING_OVERRIDES.get(rule.category)
        if override:
            return (
                override["title"],
                override["summary"],
                override["recommended_action"],
            )
        return (
            f"{rule.title} from the agency perspective",
            f"{rule.summary} Contractors or proposers are likely to evaluate this term closely during negotiations.",
            "Confirm whether this clause is required policy or legacy boilerplate before holding it as a hard position.",
        )
    return rule.title, rule.summary, rule.recommended_action


def _finding_from_rule(
    rule: FindingRule,
    documents: list[LoadedDocument],
    *,
    analysis_perspective: AnalysisPerspective,
) -> Finding | None:
    evidence: list[EvidenceRef] = []
    for document in documents:
        if rule.document_types and document.document_type not in rule.document_types:
            continue
        if not document.text_available:
            continue
        clauses = document.clauses or ()
        if not clauses:
            continue
        for clause in clauses:
            for pattern in rule.patterns:
                match = re.search(pattern, clause.text, flags=re.IGNORECASE)
                if match:
                    evidence.append(_clause_evidence(document, clause, match))
                    break
            if evidence:
                break
    if not evidence:
        return None

    confidence = (
        _SINGLE_EVIDENCE_CONFIDENCE
        if len(evidence) == 1
        else _MULTI_EVIDENCE_CONFIDENCE
    )
    confidence = min(confidence, _MAX_FINDING_CONFIDENCE)
    title, summary, recommended_action = _finding_text(rule, analysis_perspective)
    return Finding(
        id=f"{rule.role}:{rule.category}",
        analysis_perspective=analysis_perspective,
        role=rule.role,
        category=rule.category,
        severity=rule.severity,
        title=title,
        summary=summary,
        recommended_action=recommended_action,
        confidence=confidence,
        evidence=evidence[:3],
        uncertainty_notes=[],
    )


def _find_clause_match(
    document: LoadedDocument,
    patterns: tuple[str, ...],
) -> tuple[ClauseSpan, re.Match[str]] | None:
    if not document.text_available:
        return None
    for clause in document.clauses:
        for pattern in patterns:
            match = re.search(pattern, clause.text, flags=re.IGNORECASE)
            if match:
                return clause, match
    return None


def _iter_readable_documents(
    documents: list[LoadedDocument],
    allowed_types: tuple[DocumentType, ...] = (),
) -> list[LoadedDocument]:
    return [
        document
        for document in documents
        if document.text_available
        and (not allowed_types or document.document_type in allowed_types)
    ]


def _first_label_match(
    documents: list[LoadedDocument], rules: tuple[LabelRule, ...], default: str
) -> str:
    for rule in rules:
        for document in _iter_readable_documents(documents, rule.document_types):
            combined = f"{document.relative_path}\n{document.text}"
            if any(
                re.search(pattern, combined, flags=re.IGNORECASE)
                for pattern in rule.patterns
            ):
                return rule.label
    return default


def _governance_artifacts_present(documents: list[LoadedDocument]) -> list[str]:
    artifacts: set[str] = set()
    for document in documents:
        if document.document_type is DocumentType.AMENDMENT:
            artifacts.add("amendments")
        if document.document_type is DocumentType.CHANGE_ORDER:
            artifacts.add("change_orders")
        if document.document_type is DocumentType.BOARD_RECORD:
            artifacts.add("board_minutes")
            if re.search(r"settlement|resolution", document.text, flags=re.IGNORECASE):
                artifacts.add("settlement_resolution")
        if document.document_type is DocumentType.AUDIT_REPORT:
            artifacts.add("audit_report")
        if document.document_type is DocumentType.LITIGATION_RECORD:
            artifacts.add("litigation_record")
        if document.document_type is DocumentType.PROJECT_STATUS:
            artifacts.add("project_status")
    return sorted(artifacts)


def _public_text_quality(documents: list[LoadedDocument]) -> str:
    available_count = sum(1 for document in documents if document.text_available)
    if documents and available_count == len(documents):
        return "structured_or_searchable"
    if available_count:
        return "mixed"
    return "portal_only_or_scanned"


def _detect_clause_families(
    documents: list[LoadedDocument],
) -> tuple[list[str], list[EvidenceRef]]:
    detected: list[str] = []
    evidence: list[EvidenceRef] = []
    seen_locations: set[tuple[str, str]] = set()

    for rule in CLAUSE_FAMILY_RULES:
        for document in _iter_readable_documents(documents, rule.document_types):
            result = _find_clause_match(document, rule.patterns)
            if result is None:
                continue
            clause, match = result
            detected.append(rule.tag)
            ref = _clause_evidence(document, clause, match)
            key = (ref.document_id, ref.location)
            if key not in seen_locations:
                evidence.append(ref)
                seen_locations.add(key)
            break

    return sorted(set(detected)), evidence[:6]


def _procurement_profile(
    project_id: str, documents: list[LoadedDocument]
) -> ProcurementProfile:
    agreement_type = _first_label_match(
        documents, AGREEMENT_TYPE_RULES, "unknown_agreement_type"
    )
    project_sector = _first_label_match(
        documents, PROJECT_SECTOR_RULES, "unknown_project_sector"
    )
    payment_mechanism = _first_label_match(
        documents, PAYMENT_MECHANISM_RULES, "unknown_payment_mechanism"
    )
    procurement_method = _first_label_match(
        documents, PROCUREMENT_METHOD_RULES, "unknown_procurement_method"
    )
    governance_artifacts = _governance_artifacts_present(documents)
    clause_families, evidence = _detect_clause_families(documents)

    notes: list[str] = []
    if governance_artifacts:
        notes.append(
            "Package includes governance or status records that can support outcome-aware contract analysis."
        )
    if not governance_artifacts:
        notes.append(
            "No board, change-order, audit, or project-status artifacts were supplied with the contract package."
        )
    if agreement_type == "cmgc_preconstruction_services":
        notes.append(
            "CMGC-style preconstruction language was detected; later GMP and construction-award decisions should be tracked separately."
        )

    return ProcurementProfile(
        project_id=project_id,
        agreement_type=agreement_type,
        project_sector=project_sector,
        payment_mechanism=payment_mechanism,
        procurement_method=procurement_method,
        public_text_quality=_public_text_quality(documents),
        governance_artifacts_present=governance_artifacts,
        detected_clause_families=clause_families,
        evidence=evidence,
        notes=notes,
    )


def _intensity_score(value: str) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get(value, 0)


def _max_intensity(current: str, candidate: str) -> str:
    return (
        candidate
        if _intensity_score(candidate) > _intensity_score(current)
        else current
    )


def _find_first_context_signal(
    documents: list[LoadedDocument],
    *,
    signal_type: str,
    intensity: str,
    summary: str,
    patterns: tuple[str, ...],
    document_types: tuple[DocumentType, ...],
) -> ContextSignal | None:
    for document in _iter_readable_documents(documents, document_types):
        result = _find_clause_match(document, patterns)
        if result is None:
            continue
        clause, match = result
        return ContextSignal(
            signal_type=signal_type,
            intensity=intensity,
            summary=summary,
            evidence=[_clause_evidence(document, clause, match)],
        )
    return None


def _context_profile(
    project_id: str, documents: list[LoadedDocument]
) -> ContextProfile:
    funding_flexibility = "medium"
    schedule_pressure = "medium"
    oversight_intensity = "low"
    public_visibility = "low"
    signals: list[ContextSignal] = []

    signal_definitions = (
        (
            "funding_flexibility",
            "high",
            "Budget or funding language suggests constrained financial flexibility or reimbursement dependence.",
            (
                r"budget shortfall",
                r"subject to availability of funds",
                r"appropriat",
                r"phased funding",
                r"reimbursement",
                r"deficit",
                r"grant deadline",
            ),
            (
                DocumentType.BUDGET_DOCUMENT,
                DocumentType.FUNDING_DOCUMENT,
                DocumentType.BOARD_RECORD,
            ),
        ),
        (
            "schedule_pressure",
            "high",
            "Status or budget materials suggest accelerated delivery expectations or deadline pressure.",
            (
                r"accelerated delivery",
                r"expedite",
                r"deadline",
                r"use[-\s]+it[-\s]+or[-\s]+lose[-\s]+it",
                r"estimated completion",
                r"critical path",
            ),
            (
                DocumentType.BUDGET_DOCUMENT,
                DocumentType.PROJECT_STATUS,
                DocumentType.BOARD_RECORD,
            ),
        ),
        (
            "oversight_intensity",
            "high",
            "Audit, board, or oversight materials suggest heightened review or governance sensitivity.",
            (
                r"audit finding",
                r"inspector general",
                r"internal control",
                r"settlement",
                r"board resolution",
                r"finding",
            ),
            (
                DocumentType.AUDIT_REPORT,
                DocumentType.BOARD_RECORD,
                DocumentType.LITIGATION_RECORD,
            ),
        ),
        (
            "public_visibility",
            "medium",
            "Board, agenda, or public status materials indicate a visible project with external reporting cadence.",
            (
                r"board",
                r"council",
                r"agenda",
                r"status update",
                r"percent complete",
            ),
            (
                DocumentType.BOARD_RECORD,
                DocumentType.PROJECT_STATUS,
                DocumentType.BUDGET_DOCUMENT,
            ),
        ),
    )

    for signal_type, intensity, summary, patterns, document_types in signal_definitions:
        signal = _find_first_context_signal(
            documents,
            signal_type=signal_type,
            intensity=intensity,
            summary=summary,
            patterns=patterns,
            document_types=document_types,
        )
        if signal is None:
            continue
        signals.append(signal)
        if signal_type == "funding_flexibility":
            funding_flexibility = "low" if intensity == "high" else funding_flexibility
        elif signal_type == "schedule_pressure":
            schedule_pressure = _max_intensity(schedule_pressure, intensity)
        elif signal_type == "oversight_intensity":
            oversight_intensity = _max_intensity(oversight_intensity, intensity)
        elif signal_type == "public_visibility":
            public_visibility = _max_intensity(public_visibility, intensity)

    notes: list[str] = []
    if not signals:
        notes.append(
            "No budget, board, audit, or status materials supplied enough evidence for a distinct internal-only context signal."
        )
    else:
        notes.append(
            "Context profile is internal-only and should inform strategy without being exposed directly in shareable reports."
        )
    if any(
        document.document_type is DocumentType.BUDGET_DOCUMENT for document in documents
    ):
        notes.append(
            "Budget materials were supplied and incorporated into internal negotiation-context scoring."
        )

    return ContextProfile(
        project_id=project_id,
        funding_flexibility=funding_flexibility,
        schedule_pressure=schedule_pressure,
        oversight_intensity=oversight_intensity,
        public_visibility=public_visibility,
        signals=signals,
        notes=notes,
    )


def _evidence_source_type(document_type: DocumentType) -> str:
    mapping = {
        DocumentType.BOARD_RECORD: "council_resolution",
        DocumentType.PROJECT_STATUS: "project_dashboard",
        DocumentType.AUDIT_REPORT: "audit_report",
        DocumentType.LITIGATION_RECORD: "litigation_record",
        DocumentType.CHANGE_ORDER: "change_order_record",
        DocumentType.AMENDMENT: "agency_contract_record",
    }
    return mapping.get(document_type, "contract_document")


def _outcome_events(documents: list[LoadedDocument]) -> list[OutcomeEvent]:
    events: list[OutcomeEvent] = []
    seen: set[tuple[str, str]] = set()

    for rule in OUTCOME_EVENT_RULES:
        for document in _iter_readable_documents(documents, rule.document_types):
            result = _find_clause_match(document, rule.patterns)
            if result is None:
                continue
            clause, match = result
            key = (rule.event_type, clause.location)
            if key in seen:
                continue
            seen.add(key)
            events.append(
                OutcomeEvent(
                    event_type=rule.event_type,
                    impact_types=list(rule.impact_types),
                    summary=rule.summary,
                    confidence=_PUBLIC_OVERLAY_CONFIDENCE
                    if document.document_type
                    in {
                        DocumentType.BOARD_RECORD,
                        DocumentType.PROJECT_STATUS,
                        DocumentType.AUDIT_REPORT,
                    }
                    else _NO_OVERLAY_CONFIDENCE,
                    source_document_type=document.document_type.value,
                    evidence_source_type=_evidence_source_type(document.document_type),
                    evidence=[_clause_evidence(document, clause, match)],
                )
            )
            break

    return events


def _outcome_status(events: list[OutcomeEvent]) -> str:
    event_types = {event.event_type for event in events}
    if {"termination", "takeover"} & event_types:
        return "termination_takeover"
    if "bankruptcy" in event_types:
        return "bankruptcy_restructuring"
    if "scope_change" in event_types:
        return "scope_rescope"
    if {"settlement", "change_order"} & event_types:
        return "dispute_or_change_documented"
    if "closeout" in event_types:
        return "completion_documented"
    if "project_status_update" in event_types:
        return "active_delivery_documented"
    if "award" in event_types:
        return "award_documented"
    return "unknown_publicly_documented"


def _monitoring_recommendations(
    procurement_profile: ProcurementProfile,
    outcome_status: str,
    governance_artifacts: list[str],
) -> list[str]:
    recommendations: list[str] = []
    if outcome_status == "unknown_publicly_documented":
        recommendations.append(
            "Collect at least one board action, project status, or audit source so the package has a documented public outcome baseline."
        )
    if procurement_profile.agreement_type == "cmgc_preconstruction_services":
        recommendations.append(
            "Track GMP acceptance, independent cost-estimate reconciliation, and any owner decision to re-advertise or defer construction award."
        )
    if procurement_profile.payment_mechanism == "availability_payment":
        recommendations.append(
            "Track availability deductions, performance notices, and amendment activity throughout operations and maintenance."
        )
    if "change_orders" not in governance_artifacts:
        recommendations.append(
            "Preserve later change-order and settlement records because those documents are often the best public evidence of delivery stress."
        )
    return recommendations[:4]


def _outcome_evidence_bundle(
    project_id: str,
    documents: list[LoadedDocument],
    procurement_profile: ProcurementProfile,
) -> OutcomeEvidenceBundle:
    governance_artifacts = procurement_profile.governance_artifacts_present
    events = _outcome_events(documents)
    coverage_gaps: list[str] = []

    if not governance_artifacts:
        coverage_gaps.append(
            "No governance or status documents were supplied, so public outcome evidence is incomplete."
        )

    unreadable_governance_docs = [
        document.relative_path
        for document in documents
        if not document.text_available
        and document.document_type
        in {
            DocumentType.AMENDMENT,
            DocumentType.CHANGE_ORDER,
            DocumentType.BOARD_RECORD,
            DocumentType.PROJECT_STATUS,
            DocumentType.AUDIT_REPORT,
            DocumentType.LITIGATION_RECORD,
        }
    ]
    coverage_gaps.extend(
        f"Outcome source supplied but unreadable: {path}"
        for path in unreadable_governance_docs[:3]
    )

    status = _outcome_status(events)
    return OutcomeEvidenceBundle(
        project_id=project_id,
        outcome_status=status,
        governance_artifacts_present=governance_artifacts,
        events=events,
        coverage_gaps=coverage_gaps,
        monitoring_recommendations=_monitoring_recommendations(
            procurement_profile, status, governance_artifacts
        ),
    )


@dataclass(frozen=True)
class RelationshipAdvice:
    """Relationship impact assessment and negotiation strategy guidance."""

    project_id: str
    relationship_impact_score: float
    negotiation_strategy: str
    key_considerations: list[dict[str, str]]
    monitoring_recommendations: list[str]
    confidence: str = "medium"
    relationship_factors: dict[str, Any] | None = None
    entity_interaction_history: list[str] | None = None
    long_term_risk_assessment: str | None = None


@dataclass(frozen=True)
class NegotiationStrategy:
    """Synthesized negotiation strategy with prioritized action items."""

    project_id: str
    overall_approach: str
    priority_matrix: list[dict[str, Any]]
    phase_roadmap: list[dict[str, Any]]
    trade_off_analysis: list[dict[str, Any]]
    next_steps: list[dict[str, str]]
    executive_summary: str = ""
    confidence: str = "medium"
    relationship_alignment_score: float | None = None


def _relationship_advisor(
    project_id: str,
    documents: list[LoadedDocument],
    procurement_profile: ProcurementProfile,
    context_profile: ContextProfile,
    outcome_evidence: OutcomeEvidenceBundle,
    risk_findings: list[Finding],
    perspective: AnalysisPerspective,
) -> RelationshipAdvice:
    """Assess long-term relationship impact and provide negotiation strategy guidance."""
    # Analyze relationship factors from context profile
    funding_flexibility = context_profile.funding_flexibility
    schedule_pressure = context_profile.schedule_pressure
    oversight_intensity = context_profile.oversight_intensity
    public_visibility = context_profile.public_visibility

    # Calculate relationship impact score based on multiple factors
    impact_score = 0.0

    # Factor in risk findings severity
    high_severity_count = sum(
        1 for f in risk_findings if f.severity in {Severity.HIGH, Severity.CRITICAL}
    )
    medium_severity_count = sum(
        1 for f in risk_findings if f.severity == Severity.MEDIUM
    )
    impact_score -= high_severity_count * 1.5
    impact_score -= medium_severity_count * 0.5

    # Factor in context signals
    if funding_flexibility == "low":
        impact_score -= 1.0  # Tight funding = more adversarial negotiations
    if schedule_pressure == "high":
        impact_score -= 0.5  # High schedule pressure = more contentious
    if oversight_intensity == "high":
        impact_score -= 0.5  # High oversight = more cautious relationship

    # Factor in outcome evidence
    if outcome_evidence.outcome_status in {
        "termination_takeover",
        "bankruptcy_restructuring",
    }:
        impact_score -= 2.0  # Very negative history
    elif outcome_evidence.outcome_status == "completion_documented":
        impact_score += 1.0  # Positive history

    # Normalize to -10 to +10 scale
    impact_score = max(-10.0, min(10.0, impact_score))

    # Determine negotiation strategy
    if impact_score >= 5:
        strategy = "collaborative"
    elif impact_score >= 2:
        strategy = "seek_concession"
    elif impact_score >= -2:
        strategy = "creative_alternative"
    elif impact_score >= -5:
        strategy = "hold_firm"
    else:
        strategy = "walk_away"

    # Generate key considerations
    considerations = []
    if high_severity_count > 0:
        considerations.append(
            {
                "clause_reference": "Multiple high-severity risk findings",
                "impact_description": f"Found {high_severity_count} high-severity issues that could strain the relationship if not addressed proactively.",
                "recommended_action": "Address these issues early in negotiations with collaborative framing.",
            }
        )

    if funding_flexibility == "low":
        considerations.append(
            {
                "clause_reference": "Budget constraints detected",
                "impact_description": "Entity appears to have limited funding flexibility, which may lead to rigid negotiation positions.",
                "recommended_action": "Focus on value-engineering and alternative funding approaches rather than direct concessions.",
            }
        )

    if schedule_pressure == "high":
        considerations.append(
            {
                "clause_reference": "Schedule pressure identified",
                "impact_description": "Entity is under significant schedule pressure, which may create adversarial dynamics around timeline commitments.",
                "recommended_action": "Use schedule flexibility as a negotiation lever while protecting critical path requirements.",
            }
        )

    if not considerations:
        considerations.append(
            {
                "clause_reference": "General contract terms",
                "impact_description": "No significant relationship-impacting issues identified in the current analysis.",
                "recommended_action": "Maintain collaborative approach and monitor for emerging relationship risks.",
            }
        )

    # Generate monitoring recommendations
    monitoring_recs = [
        "Track relationship health through regular check-ins during contract execution.",
        "Monitor for changes in entity leadership or budget priorities that may affect relationship dynamics.",
    ]

    if oversight_intensity == "high":
        monitoring_recs.append(
            "Pay special attention to compliance and reporting requirements due to heightened oversight."
        )
    if outcome_evidence.outcome_status in {
        "termination_takeover",
        "bankruptcy_restructuring",
    }:
        monitoring_recs.append(
            "Given negative historical outcomes, implement enhanced relationship monitoring protocols."
        )

    # Build relationship factors
    relationship_factors = {
        "historical_pattern": outcome_evidence.outcome_status,
        "entity_priorities": [
            f"Funding flexibility: {funding_flexibility}",
            f"Schedule pressure: {schedule_pressure}",
            f"Oversight intensity: {oversight_intensity}",
            f"Public visibility: {public_visibility}",
        ],
        "relationship_value": "strategic" if impact_score >= 0 else "transactional",
    }

    # Entity interaction history from outcome evidence
    entity_history = []
    if outcome_evidence.events:
        for event in outcome_evidence.events[:3]:
            entity_history.append(f"{event.event_type}: {event.summary}")

    return RelationshipAdvice(
        project_id=project_id,
        relationship_impact_score=impact_score,
        negotiation_strategy=strategy,
        key_considerations=considerations,
        monitoring_recommendations=monitoring_recs,
        confidence="high" if len(documents) > 5 else "medium",
        relationship_factors=relationship_factors,
        entity_interaction_history=entity_history if entity_history else None,
        long_term_risk_assessment=_assess_long_term_risk(
            impact_score, outcome_evidence.outcome_status
        ),
    )


def _assess_long_term_risk(impact_score: float, outcome_status: str) -> str:
    """Assess long-term relationship risk based on impact score and historical outcomes."""
    if impact_score >= 5:
        return "Low long-term risk. Relationship appears strong and resilient to typical contract disputes."
    elif impact_score >= 2:
        return "Moderate long-term risk. Relationship is generally positive but may be strained by significant contract issues."
    elif impact_score >= -2:
        return "Moderate long-term risk. Relationship has both positive and negative factors that require active management."
    elif impact_score >= -5:
        return "High long-term risk. Relationship shows signs of strain that could escalate during contract execution."
    else:
        return "Very high long-term risk. Relationship appears fragile and may not survive significant contract disputes."


def _negotiation_strategist(
    project_id: str,
    relationship_advice: RelationshipAdvice,
    risk_findings: list[Finding],
    context_profile: ContextProfile,
    procurement_profile: ProcurementProfile,
    obligations: list[Obligation],
) -> NegotiationStrategy:
    """Synthesize all inputs into a comprehensive negotiation strategy."""
    # Determine overall approach based on relationship advice
    overall_approach = relationship_advice.negotiation_strategy

    # Build priority matrix combining technical risk and relationship impact
    priority_matrix = []
    for finding in risk_findings:
        # Calculate priority score based on severity and relationship impact
        severity_score = {
            Severity.CRITICAL: 10,
            Severity.HIGH: 8,
            Severity.MEDIUM: 5,
            Severity.LOW: 2,
        }.get(finding.severity, 5)

        # Adjust based on relationship impact
        relationship_adjustment = relationship_advice.relationship_impact_score / 10.0
        priority_score = max(1, min(10, severity_score + relationship_adjustment))

        # Determine recommended action
        if priority_score >= 8:
            action = "hold_firm"
        elif priority_score >= 6:
            action = "seek_concession"
        elif priority_score >= 4:
            action = "creative_solution"
        else:
            action = "accept_as_is"

        priority_matrix.append(
            {
                "issue": finding.category,
                "technical_risk": finding.severity.value,
                "relationship_impact": "negative"
                if relationship_advice.relationship_impact_score < 0
                else "positive",
                "priority_score": round(priority_score, 1),
                "recommended_action": action,
            }
        )

    # Sort by priority score descending
    priority_matrix.sort(key=lambda x: x["priority_score"], reverse=True)

    # Build phase roadmap
    phase_roadmap = [
        {
            "phase": "pre_bid",
            "timing": "2-4 weeks before bid deadline",
            "focus_areas": [
                "Document completeness",
                "Risk identification",
                "Entity research",
            ],
            "objectives": [
                "Complete document inventory",
                "Identify all high-severity risks",
                "Understand entity priorities",
            ],
            "success_criteria": [
                "All required documents obtained",
                "Risk findings documented",
                "Entity context profile complete",
            ],
        },
        {
            "phase": "bid_submission",
            "timing": "1-2 weeks before bid deadline",
            "focus_areas": [
                "Pricing strategy",
                "Risk allocation",
                "Relationship positioning",
            ],
            "objectives": [
                "Price risks appropriately",
                "Frame proposal collaboratively",
                "Highlight value-add opportunities",
            ],
            "success_criteria": [
                "Competitive pricing submitted",
                "Collaborative language used",
                "Value propositions clear",
            ],
        },
        {
            "phase": "negotiation",
            "timing": "Post-bid selection",
            "focus_areas": [
                "Priority issues",
                "Trade-off analysis",
                "Relationship preservation",
            ],
            "objectives": [
                "Address high-priority risks",
                "Find creative solutions",
                "Maintain positive relationship",
            ],
            "success_criteria": [
                "Key risks mitigated",
                "Mutually acceptable terms",
                "Relationship intact or improved",
            ],
        },
    ]

    # Build trade-off analysis
    trade_off_analysis = []
    if relationship_advice.key_considerations:
        for consideration in relationship_advice.key_considerations[:3]:
            trade_off_analysis.append(
                {
                    "what_you_gain": "Risk mitigation and contract protection",
                    "what_you_give_up": "Potential relationship friction if handled adversarially",
                    "relationship_cost": -1
                    if relationship_advice.relationship_impact_score < 0
                    else 1,
                    "risk_reduction": 7,
                    "net_value": "positive"
                    if relationship_advice.relationship_impact_score >= 0
                    else "neutral",
                }
            )

    if not trade_off_analysis:
        trade_off_analysis.append(
            {
                "what_you_gain": "Strong contract protections",
                "what_you_give_up": "May create adversarial dynamics",
                "relationship_cost": 0,
                "risk_reduction": 8,
                "net_value": "positive",
            }
        )

    # Generate next steps
    next_steps = [
        {
            "action": "Review and prioritize risk findings with legal team",
            "owner": "Contract Manager",
            "timeline": "Within 1 week",
            "dependencies": ["Complete risk analysis"],
            "success_metric": "Prioritized list of issues to address in negotiation",
        },
        {
            "action": "Research entity's historical negotiation patterns",
            "owner": "Business Development",
            "timeline": "Within 2 weeks",
            "dependencies": ["Access to historical contract data"],
            "success_metric": "Entity negotiation profile document",
        },
        {
            "action": "Develop creative alternatives for high-priority issues",
            "owner": "Negotiation Team",
            "timeline": "Before negotiation phase",
            "dependencies": ["Prioritized risk list", "Entity research complete"],
            "success_metric": "At least 3 creative alternatives documented",
        },
    ]

    # Generate executive summary
    executive_summary = (
        f"Negotiation strategy for project {project_id} recommends a {overall_approach} approach. "
        f"Relationship impact score is {relationship_advice.relationship_impact_score:.1f}/10. "
        f"Priority focus areas: {', '.join([m['issue'] for m in priority_matrix[:3]])}. "
        f"Key recommendation: {relationship_advice.key_considerations[0]['recommended_action'] if relationship_advice.key_considerations else 'Proceed with standard negotiation protocols'}."
    )

    # Calculate relationship alignment score
    relationship_alignment = max(
        0, min(10, 5 + relationship_advice.relationship_impact_score / 2)
    )

    return NegotiationStrategy(
        project_id=project_id,
        overall_approach=overall_approach,
        priority_matrix=priority_matrix,
        phase_roadmap=phase_roadmap,
        trade_off_analysis=trade_off_analysis,
        next_steps=next_steps,
        executive_summary=executive_summary,
        confidence=relationship_advice.confidence,
        relationship_alignment_score=round(relationship_alignment, 1),
    )


def _clause_for_match(
    document: LoadedDocument, match: re.Match[str]
) -> ClauseSpan | None:
    if not document.clauses:
        return None
    target_start = match.start()
    search_start = 0
    fallback: ClauseSpan | None = None
    for clause in document.clauses:
        position = document.text.find(clause.text, search_start)
        if position < 0:
            position = document.text.find(clause.text)
        if position < 0:
            continue
        clause_end = position + len(clause.text)
        if fallback is None:
            fallback = clause
        if position <= target_start < clause_end:
            return clause
        search_start = clause_end
    return fallback


def _extract_obligations(documents: list[LoadedDocument]) -> list[Obligation]:
    obligations: list[Obligation] = []
    seen_ids: set[str] = set()

    def add_obligation(
        *,
        document: LoadedDocument,
        clause: ClauseSpan | None,
        title: str,
        obligation_type: str,
        trigger: str,
        due_rule: str,
        owner_role: str,
        severity: Severity,
        match: re.Match[str] | None,
    ) -> None:
        clause_location = clause.location if clause else "document"
        signature = "|".join(
            (
                document.document_id,
                clause_location,
                obligation_type,
                trigger,
                due_rule,
                title,
            )
        )
        obligation_id = (
            f"obl_{hashlib.sha1(signature.encode('utf-8')).hexdigest()[:12]}"
        )
        if obligation_id in seen_ids:
            return
        seen_ids.add(obligation_id)
        evidence = (
            [_clause_evidence(document, clause, match)] if clause and match else []
        )
        obligations.append(
            Obligation(
                id=obligation_id,
                source_clause=f"{document.relative_path}::{clause_location}",
                source_document_id=document.document_id,
                source_excerpt=evidence[0].excerpt if evidence else None,
                title=title,
                obligation_type=obligation_type,
                trigger=trigger,
                due_rule=due_rule,
                owner_role=owner_role,
                severity_if_missed=severity,
                evidence=evidence,
            )
        )

    for document in documents:
        if not document.text_available:
            continue

        for match in NOTICE_DEADLINE_PATTERN.finditer(document.text):
            clause = _clause_for_match(document, match)
            days = match.group("days")
            unit = match.group("unit") or "calendar"
            title = f"Provide required notice within {days} {unit} days"
            add_obligation(
                document=document,
                clause=clause,
                title=title,
                obligation_type="notice_deadline",
                trigger="contractual notice event",
                due_rule=f"within {days} {unit} days",
                owner_role="project_manager",
                severity=Severity.HIGH,
                match=match,
            )

        certified_payroll = re.search(
            r"certified payroll", document.text, flags=re.IGNORECASE
        )
        if certified_payroll:
            clause = _clause_for_match(document, certified_payroll)
            add_obligation(
                document=document,
                clause=clause,
                title="Submit certified payroll reports",
                obligation_type="recurring_reporting",
                trigger="during covered work",
                due_rule="weekly during covered work",
                owner_role="payroll_compliance_manager",
                severity=Severity.HIGH,
                match=certified_payroll,
            )

        certificates = re.search(
            r"certificate[s]? of insurance", document.text, flags=re.IGNORECASE
        )
        if certificates:
            clause = _clause_for_match(document, certificates)
            add_obligation(
                document=document,
                clause=clause,
                title="Provide certificates of insurance before starting work",
                obligation_type="pre_start_requirement",
                trigger="before mobilization or notice to proceed",
                due_rule="before starting work",
                owner_role="risk_manager",
                severity=Severity.HIGH,
                match=certificates,
            )

        progress_reporting = re.search(
            r"(monthly progress report|progress reports?)[\s\S]{0,120}(work breakdown structure|\bwbs\b)",
            document.text,
            flags=re.IGNORECASE,
        )
        if progress_reporting:
            clause = _clause_for_match(document, progress_reporting)
            add_obligation(
                document=document,
                clause=clause,
                title="Submit monthly progress reports by work breakdown structure",
                obligation_type="recurring_reporting",
                trigger="during preconstruction or active delivery",
                due_rule="monthly, mapped to WBS elements when required",
                owner_role="project_controls_manager",
                severity=Severity.MEDIUM,
                match=progress_reporting,
            )

    return obligations


def _relationship_strategy(
    documents: list[LoadedDocument],
    all_findings: list[Finding],
    context_profile: ContextProfile,
    procurement_profile: ProcurementProfile,
    *,
    analysis_perspective: AnalysisPerspective,
) -> dict[str, object]:
    has_public_overlay = any(
        document.document_type
        in {DocumentType.FUNDING_DOCUMENT, DocumentType.PROCUREMENT_DOCUMENT}
        for document in documents
    )
    has_addenda = any(
        document.document_type is DocumentType.ADDENDUM for document in documents
    )
    insurance_pressure = any(
        finding.role == "insurance_requirements_analyst" for finding in all_findings
    )
    governance_material = bool(procurement_profile.governance_artifacts_present)

    sensitive_issues = [
        finding.title
        for finding in all_findings
        if SEVERITY_ORDER[finding.severity] >= SEVERITY_ORDER[Severity.HIGH]
    ][:3]
    leverage_points: list[str] = []
    if analysis_perspective is AnalysisPerspective.VENDOR:
        if has_addenda:
            leverage_points.append(
                "Use pre-bid clarification and addendum channels to resolve ambiguous commercial terms before price lock."
            )
        if insurance_pressure:
            leverage_points.append(
                "Push broker-to-broker on endorsement wording rather than arguing abstract insurance concepts in principal-only terms."
            )
        if has_public_overlay:
            leverage_points.append(
                "Focus negotiation on commercial allocation and notice mechanics rather than statutory funding terms that are likely rigid."
            )
        if context_profile.funding_flexibility == "low":
            leverage_points.append(
                "Budget or reimbursement constraints appear tight, so price cash-flow risk and avoid assuming payment-term flexibility."
            )
        if context_profile.oversight_intensity == "high":
            leverage_points.append(
                "Heightened oversight signals suggest pushing hardest on clarity and administrability, not on public-accountability provisions."
            )
        if context_profile.schedule_pressure == "high":
            leverage_points.append(
                "Schedule pressure appears elevated, so protect delay-cost recovery and notice mechanics instead of challenging milestone urgency directly."
            )
        if procurement_profile.agreement_type == "cmgc_preconstruction_services":
            leverage_points.append(
                "Separate preconstruction compensation from later GMP or construction-award risk so the owner cannot strand unrecovered effort."
            )
        if governance_material:
            leverage_points.append(
                "Use available board, status, or change-order records to understand which terms appear politically or operationally rigid before pushing on them."
            )

        posture = (
            "Expect limited flexibility on funding-driven or public-agency compliance terms; prioritize commercial allocation, notice windows, and insurable-risk cleanup."
            if has_public_overlay
            else "Commercial terms may be negotiable, but the current package still needs structured human review before a bid commitment."
        )
        if context_profile.oversight_intensity == "high":
            posture += " Oversight signals suggest keeping outward-facing negotiation framing operational and evidence-based."
    else:
        if has_addenda:
            leverage_points.append(
                "Use addenda and pre-bid clarification channels to clean up ambiguous boilerplate before bidders price avoidable uncertainty."
            )
        if insurance_pressure:
            leverage_points.append(
                "Separate must-have insurance protections from broker-negotiable endorsement wording to avoid unnecessary premium loading."
            )
        if has_public_overlay:
            leverage_points.append(
                "Keep statutory and funding-driven clauses intact, but distinguish them from legacy commercial language that may be negotiable."
            )
        if context_profile.funding_flexibility == "low":
            leverage_points.append(
                "Tight reimbursement or appropriation conditions suggest bidders will push on payment timing and demobilization recovery."
            )
        if context_profile.oversight_intensity == "high":
            leverage_points.append(
                "Heightened oversight signals favor retaining clear compliance controls, but unsupported aggressiveness may still reduce bidder confidence."
            )
        if context_profile.schedule_pressure == "high":
            leverage_points.append(
                "Schedule pressure appears elevated, so preserve schedule-critical controls while avoiding unnecessary friction on non-critical boilerplate."
            )
        if procurement_profile.agreement_type == "cmgc_preconstruction_services":
            leverage_points.append(
                "Be explicit about preconstruction compensation and later award discretion so bidders can price the CMGC off-ramp honestly."
            )
        if governance_material:
            leverage_points.append(
                "Use available board, status, or change-order records to separate truly constrained clauses from terms that persist only by habit."
            )

        posture = (
            "Preserve statutory and funding-driven protections, but distinguish them from commercial boilerplate that may unnecessarily reduce competition or drive pricing."
            if has_public_overlay
            else "Commercial protections may still be negotiable; use the intake findings to separate real agency requirements from legacy boilerplate."
        )
        if context_profile.oversight_intensity == "high":
            posture += " Outward-facing negotiation framing should stay operational, documented, and tied to enforceability."
    confidence = (
        _PUBLIC_OVERLAY_CONFIDENCE if has_public_overlay else _NO_OVERLAY_CONFIDENCE
    )
    return {
        "analysis_perspective": analysis_perspective.value,
        "negotiation_posture": posture,
        "sensitive_issues": sensitive_issues,
        "leverage_points": leverage_points,
        "confidence": confidence,
    }


def _review_challenges(
    *,
    missing_docs: list[DocumentType],
    unreadable_documents: list[LoadedDocument],
    findings: list[Finding],
    outcome_evidence: OutcomeEvidenceBundle | None = None,
) -> dict[str, object]:
    contradictions: list[str] = []
    if not findings:
        contradictions.append(
            "No material findings were generated; verify that the supplied files contain extractable contract text."
        )
    if outcome_evidence is not None:
        outcome_status = outcome_evidence.outcome_status
        high_or_worse = [
            finding
            for finding in findings
            if SEVERITY_ORDER[finding.severity] >= SEVERITY_ORDER[Severity.HIGH]
        ]
        stress_event_types = {
            event.event_type
            for event in outcome_evidence.events
            if event.event_type
            in {
                "change_order",
                "scope_change",
                "settlement",
                "audit_finding",
                "litigation",
                "termination",
            }
        }
        if outcome_status != "unknown_publicly_documented" and not high_or_worse:
            contradictions.append(
                "Public outcome evidence indicates delivery or governance stress, but the current finding set did not surface matching high-severity contract issues."
            )
        if stress_event_types and not any(
            finding.category
            in {
                "change_orders",
                "termination",
                "payment_terms",
                "delay_exposure",
                "appropriation_limit",
            }
            for finding in findings
        ):
            contradictions.append(
                "Outcome evidence shows scope, change-order, or dispute activity, but the current commercial findings do not yet explain the likely contract drivers."
            )
    if missing_docs and findings:
        contradictions.append(
            "Material findings were generated while required source documents are missing; confirm the package is complete before relying on the current posture."
        )

    missed_hazards = [
        f"Missing required bid-review input: {document_type.value}"
        for document_type in missing_docs
    ]
    missed_hazards.extend(
        f"Unreadable source file requires manual review: {document.relative_path}"
        for document in unreadable_documents
    )
    if outcome_evidence is not None:
        missed_hazards.extend(outcome_evidence.coverage_gaps)
    human_review_required = bool(missed_hazards or contradictions) or any(
        SEVERITY_ORDER[finding.severity] >= SEVERITY_ORDER[Severity.HIGH]
        for finding in findings
    )
    return {
        "contradictions": contradictions,
        "missed_hazards": missed_hazards,
        "human_review_required": human_review_required,
    }


def _decision_summary(
    *,
    project_id: str,
    analysis_perspective: AnalysisPerspective,
    findings: list[Finding],
    missing_docs: list[DocumentType],
    unreadable_documents: list[LoadedDocument],
    review_challenges: dict[str, object],
) -> DecisionSummary:
    high_or_worse = [
        finding
        for finding in findings
        if SEVERITY_ORDER[finding.severity] >= SEVERITY_ORDER[Severity.HIGH]
    ]
    critical_findings = [
        finding for finding in findings if finding.severity is Severity.CRITICAL
    ]
    contract_high_or_worse = [
        finding for finding in high_or_worse if finding.role == "contract_risk_analyst"
    ]
    unreadable_required = [
        document
        for document in unreadable_documents
        if document.document_type in REQUIRED_BID_REVIEW_DOCUMENTS
    ]
    contradiction_count = len(review_challenges.get("contradictions", []))
    max_severity = max(
        (SEVERITY_ORDER[finding.severity] for finding in findings),
        default=SEVERITY_ORDER[Severity.LOW],
    )
    overall_risk = next(
        severity
        for severity, score in SEVERITY_ORDER.items()
        if score
        == max(
            max_severity,
            SEVERITY_ORDER[Severity.HIGH] if missing_docs else max_severity,
        )
    )

    confidence = _BASE_DECISION_CONFIDENCE
    confidence -= _MISSING_DOC_PENALTY * len(missing_docs)
    confidence -= _UNREADABLE_DOC_PENALTY * min(
        len(unreadable_documents), _MAX_UNREADABLE_PENALTY_COUNT
    )
    if high_or_worse:
        confidence -= _HIGH_FINDING_PENALTY
    confidence = max(_MIN_DECISION_CONFIDENCE, min(confidence, _MAX_FINDING_CONFIDENCE))

    human_review_required = (
        bool(review_challenges.get("human_review_required")) or confidence < 0.75
    )

    if (
        critical_findings
        or len(missing_docs) >= 2
        or (
            len(high_or_worse) >= 3
            and (missing_docs or unreadable_required or contradiction_count)
        )
        or (
            len(contract_high_or_worse) >= 3
            and (unreadable_required or contradiction_count)
        )
    ):
        recommendation = Recommendation.NO_GO
    elif high_or_worse or missing_docs or unreadable_required or human_review_required:
        recommendation = Recommendation.GO_WITH_CONDITIONS
    else:
        recommendation = Recommendation.GO

    top_reasons = [
        finding.title
        for finding in sorted(
            findings, key=lambda item: SEVERITY_ORDER[item.severity], reverse=True
        )[:3]
    ]
    top_reasons.extend(
        f"Missing required document: {document_type.value}"
        for document_type in missing_docs[:2]
    )

    must_fix_before_bid = [finding.recommended_action for finding in high_or_worse[:4]]
    must_fix_before_bid.extend(
        f"Obtain and review the missing {document_type.value.replace('_', ' ')}."
        for document_type in missing_docs
    )
    must_fix_before_bid.extend(
        str(item) for item in review_challenges.get("contradictions", [])[:2]
    )

    return DecisionSummary(
        project_id=project_id,
        analysis_perspective=analysis_perspective,
        recommendation=recommendation,
        overall_risk=overall_risk,
        confidence=round(confidence, 2),
        top_reasons=top_reasons[:4],
        must_fix_before_bid=must_fix_before_bid[:6],
        human_review_required=human_review_required,
    )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_bid_review(
    project_dir: str | Path,
    artifacts_dir: str | Path | None = None,
    *,
    analysis_perspective: str | AnalysisPerspective = AnalysisPerspective.VENDOR,
) -> BidReviewRunResult:
    project_path = resolve_existing_directory(project_dir, label="Project directory")
    perspective = _normalize_analysis_perspective(analysis_perspective)
    output_dir = (
        resolve_output_directory(artifacts_dir, label="Artifacts directory")
        if artifacts_dir
        else resolve_output_directory(
            project_path / "artifacts", label="Artifacts directory"
        )
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    project_id = compute_project_id(project_path)
    documents = iter_project_documents(project_path)
    missing_docs = missing_required_documents(
        [document.document_type for document in documents]
    )
    unreadable_documents = [
        document for document in documents if not document.text_available
    ]

    document_inventory = {
        "project_id": project_id,
        "analysis_perspective": perspective.value,
        "documents": [
            ProjectDocumentRecord(
                document_id=document.document_id,
                filename=document.relative_path,
                document_type=document.document_type.value,
                required_for_bid_review=document.document_type
                in REQUIRED_BID_REVIEW_DOCUMENTS,
                text_available=document.text_available,
                text_source=document.text_source,
                text_quality=document.text_quality,
                clause_count=len(document.clauses),
            ).model_dump()
            for document in documents
        ],
        "missing_required_documents": [
            document_type.value for document_type in missing_docs
        ],
    }

    risk_findings = [
        finding
        for rule in (*CONTRACT_RISK_RULES, *TRANSPORT_CONTRACT_RISK_RULES)
        if (
            finding := _finding_from_rule(
                rule, documents, analysis_perspective=perspective
            )
        )
    ]
    insurance_findings = [
        finding
        for rule in (*INSURANCE_RULES, *TRANSPORT_INSURANCE_RULES)
        if (
            finding := _finding_from_rule(
                rule, documents, analysis_perspective=perspective
            )
        )
    ]
    compliance_findings = [
        finding
        for rule in (*COMPLIANCE_RULES, *TRANSPORT_COMPLIANCE_RULES)
        if (
            finding := _finding_from_rule(
                rule, documents, analysis_perspective=perspective
            )
        )
    ]
    all_findings = [*risk_findings, *insurance_findings, *compliance_findings]
    context_profile = _context_profile(project_id, documents)
    procurement_profile = _procurement_profile(project_id, documents)
    outcome_evidence = _outcome_evidence_bundle(
        project_id, documents, procurement_profile
    )
    relationship_strategy = _relationship_strategy(
        documents,
        all_findings,
        context_profile,
        procurement_profile,
        analysis_perspective=perspective,
    )
    review_challenges = _review_challenges(
        missing_docs=missing_docs,
        unreadable_documents=unreadable_documents,
        findings=all_findings,
        outcome_evidence=outcome_evidence,
    )
    obligations = _extract_obligations(documents)
    decision_summary = _decision_summary(
        project_id=project_id,
        analysis_perspective=perspective,
        findings=all_findings,
        missing_docs=missing_docs,
        unreadable_documents=unreadable_documents,
        review_challenges=review_challenges,
    )

    artifact_payloads: dict[str, object] = {
        "document_inventory.json": document_inventory,
        "risk_findings.json": [finding.model_dump() for finding in risk_findings],
        "insurance_findings.json": [
            finding.model_dump() for finding in insurance_findings
        ],
        "compliance_findings.json": [
            finding.model_dump() for finding in compliance_findings
        ],
        "relationship_strategy.json": relationship_strategy,
        "context_profile.json": context_profile.model_dump(),
        "procurement_profile.json": procurement_profile.model_dump(),
        "outcome_evidence.json": outcome_evidence.model_dump(),
        "review_challenges.json": review_challenges,
        "decision_summary.json": decision_summary.model_dump(),
        "obligations_register.json": [
            obligation.model_dump() for obligation in obligations
        ],
    }

    artifact_paths: dict[str, Path] = {}
    for filename, payload in artifact_payloads.items():
        path = output_dir / filename
        _write_json(path, payload)
        artifact_paths[filename] = path

    persisted = FileSystemCaseStore(
        project_path / ".contract_intelligence"
    ).persist_bid_review_run(
        project_id=project_id,
        analysis_perspective=perspective.value,
        source_project_dir=project_path,
        artifacts_dir=output_dir,
        artifact_paths=artifact_paths,
        document_inventory=document_inventory,
        decision_summary=decision_summary,
        context_profile=context_profile,
        procurement_profile=procurement_profile,
        outcome_evidence=outcome_evidence,
        relationship_strategy=relationship_strategy,
        review_challenges=review_challenges,
        obligations_count=len(obligations),
    )

    return BidReviewRunResult(
        project_id=project_id,
        artifacts_dir=output_dir,
        artifact_paths=artifact_paths,
        decision_summary=decision_summary,
        case_record_path=persisted.case_record_path,
        run_record_path=persisted.run_record_path,
    )
