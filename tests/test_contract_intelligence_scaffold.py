from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

enums = importlib.import_module("apps.contract_intelligence.domain.enums")
models = importlib.import_module("apps.contract_intelligence.domain.models")
document_classifier = importlib.import_module("apps.contract_intelligence.ingestion.document_classifier")
pipeline = importlib.import_module("apps.contract_intelligence.orchestration.pipeline")
role_catalog = importlib.import_module("apps.contract_intelligence.orchestration.role_catalog")

DocumentType = enums.DocumentType
Recommendation = enums.Recommendation
Severity = enums.Severity
DecisionSummary = models.DecisionSummary
classify_document = document_classifier.classify_document
missing_required_documents = document_classifier.missing_required_documents
bid_review_pipeline = pipeline.bid_review_pipeline
universal_casework_workflow = pipeline.universal_casework_workflow
artifact_contract = role_catalog.artifact_contract
role_keys = role_catalog.role_keys


def test_role_catalog_exposes_core_bid_review_roles() -> None:
    roles = role_keys()
    assert "document_intake_analyst" in roles
    assert "contract_risk_analyst" in roles
    assert "context_intelligence_analyst" in roles
    assert "procurement_structure_analyst" in roles
    assert "outcome_evidence_analyst" in roles
    assert "bid_decision_analyst" in roles
    assert "adversarial_reviewer" in roles


def test_bid_review_pipeline_has_expected_stage_order() -> None:
    stages = bid_review_pipeline()
    assert [stage.key for stage in stages] == ["intake", "analysis", "challenge", "synthesis"]
    assert "context_profile.json" in stages[1].outputs
    assert "procurement_profile.json" in stages[1].outputs
    assert "outcome_evidence.json" in stages[1].outputs
    assert stages[-1].outputs == ("decision_summary.json", "obligations_register.json")


def test_universal_casework_workflow_is_industry_agnostic() -> None:
    assert universal_casework_workflow() == (
        "ingest",
        "structure",
        "evaluate",
        "challenge",
        "synthesize",
        "decide",
        "commit",
        "monitor",
    )


def test_document_classifier_detects_common_contract_inputs() -> None:
    assert classify_document("Prime_Contract_Agreement.pdf") is DocumentType.PRIME_CONTRACT
    assert classify_document("General-Conditions-AIA-A201.pdf") is DocumentType.GENERAL_CONDITIONS
    assert classify_document("Insurance Requirements Exhibit.docx") is DocumentType.INSURANCE_REQUIREMENTS
    assert classify_document("Board Resolution 2026.pdf") is DocumentType.BOARD_RECORD
    assert classify_document("Proposed Capital Budget FY2027.pdf") is DocumentType.BUDGET_DOCUMENT
    assert classify_document("Agency Audit Report.pdf") is DocumentType.AUDIT_REPORT


def test_missing_required_documents_flags_bid_review_gaps() -> None:
    missing = missing_required_documents([DocumentType.PRIME_CONTRACT, DocumentType.ADDENDUM])
    assert missing == [
        DocumentType.GENERAL_CONDITIONS,
        DocumentType.INSURANCE_REQUIREMENTS,
    ]


def test_decision_summary_model_supports_human_review_flag() -> None:
    summary = DecisionSummary(
        project_id="proj_001",
        recommendation=Recommendation.GO_WITH_CONDITIONS,
        overall_risk=Severity.HIGH,
        confidence=0.74,
        top_reasons=["Aggressive indemnity"],
        must_fix_before_bid=["Cap indemnity"],
        human_review_required=True,
    )
    assert summary.recommendation is Recommendation.GO_WITH_CONDITIONS
    assert summary.human_review_required is True


def test_schema_files_are_valid_json() -> None:
    schemas_dir = Path("apps/contract_intelligence/schemas")
    names = artifact_contract().values()
    for schema_name in names:
        schema_path = schemas_dir / schema_name
        assert schema_path.exists(), f"missing schema: {schema_name}"
        payload = json.loads(schema_path.read_text())
        assert payload["type"] == "object"
