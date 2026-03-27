from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

runner = importlib.import_module("apps.contract_intelligence.orchestration.bid_review_runner")

run_bid_review = runner.run_bid_review


def test_bid_review_runner_emits_core_artifacts(tmp_path: Path) -> None:
    project_dir = tmp_path / "riverside-bridge"
    project_dir.mkdir()
    (project_dir / "Prime Contract Agreement.md").write_text(
        "\n".join(
            [
                "Owner may terminate for convenience.",
                "Subcontractor shall be paid on a pay-if-paid basis.",
                "No damages for delay shall be allowed.",
                "Notice of claim must be provided within 7 calendar days.",
            ]
        ),
        encoding="utf-8",
    )
    (project_dir / "General Conditions.txt").write_text(
        "Contractor shall defend, indemnify, and hold harmless the owner.",
        encoding="utf-8",
    )
    (project_dir / "Insurance Requirements.md").write_text(
        "\n".join(
            [
                "Additional insured status is required.",
                "Coverage shall be primary and noncontributory.",
                "Waiver of subrogation applies.",
                "Certificates of insurance are required before starting work.",
            ]
        ),
        encoding="utf-8",
    )
    (project_dir / "Funding Memo.md").write_text(
        "\n".join(
            [
                "This project uses federal aid and Davis-Bacon prevailing wage requirements.",
                "Certified payroll must be submitted weekly.",
                "DBE participation goals apply.",
            ]
        ),
        encoding="utf-8",
    )

    result = run_bid_review(project_dir)

    assert result.decision_summary.recommendation.value == "go_with_conditions"
    assert result.decision_summary.human_review_required is True

    inventory = json.loads((result.artifacts_dir / "document_inventory.json").read_text())
    assert inventory["project_id"] == "riverside-bridge"
    assert inventory["missing_required_documents"] == []
    assert len(inventory["documents"]) == 4

    risk_findings = json.loads((result.artifacts_dir / "risk_findings.json").read_text())
    assert any(item["category"] == "payment_terms" for item in risk_findings)
    assert any(item["category"] == "delay_exposure" for item in risk_findings)

    insurance_findings = json.loads((result.artifacts_dir / "insurance_findings.json").read_text())
    assert any(item["category"] == "additional_insured" for item in insurance_findings)

    compliance_findings = json.loads((result.artifacts_dir / "compliance_findings.json").read_text())
    assert any(item["category"] == "davis_bacon" for item in compliance_findings)

    obligations = json.loads((result.artifacts_dir / "obligations_register.json").read_text())
    assert any(item["obligation_type"] == "notice_deadline" for item in obligations)
    assert any(item["title"] == "Submit certified payroll reports" for item in obligations)

    procurement_profile = json.loads((result.artifacts_dir / "procurement_profile.json").read_text())
    assert procurement_profile["project_id"] == "riverside-bridge"

    context_profile = json.loads((result.artifacts_dir / "context_profile.json").read_text())
    assert context_profile["project_id"] == "riverside-bridge"
    assert context_profile["internal_only"] is True

    outcome_evidence = json.loads((result.artifacts_dir / "outcome_evidence.json").read_text())
    assert outcome_evidence["outcome_status"] == "unknown_publicly_documented"


def test_bid_review_runner_flags_missing_required_documents(tmp_path: Path) -> None:
    project_dir = tmp_path / "missing-insurance-package"
    project_dir.mkdir()
    (project_dir / "Prime Contract Agreement.md").write_text(
        "Subcontractor shall be paid on a pay-if-paid basis.",
        encoding="utf-8",
    )

    result = run_bid_review(project_dir)
    decision = json.loads((result.artifacts_dir / "decision_summary.json").read_text())
    challenges = json.loads((result.artifacts_dir / "review_challenges.json").read_text())

    assert decision["human_review_required"] is True
    assert decision["recommendation"] == "no_go"
    assert any("general_conditions" in item for item in challenges["missed_hazards"])
    assert any("insurance_requirements" in item for item in challenges["missed_hazards"])


def test_bid_review_runner_escalates_multiple_high_findings_to_no_go(tmp_path: Path) -> None:
    project_dir = tmp_path / "multi-high-no-go"
    project_dir.mkdir()
    (project_dir / "Prime Contract Agreement.md").write_text(
        "\n".join(
            [
                "Subcontractor shall be paid on a pay-if-paid basis.",
                "No damages for delay shall be allowed.",
                "Contractor shall defend, indemnify, and hold harmless the owner.",
            ]
        ),
        encoding="utf-8",
    )
    (project_dir / "General Conditions.md").write_text(
        "Notice of claim must be provided within 7 calendar days.",
        encoding="utf-8",
    )
    (project_dir / "Insurance Requirements.pdf").write_bytes(b"%PDF-1.4\x00\x00corrupt")
    (project_dir / "Board Resolution.md").write_text(
        "Resolution approving Change Order No. 7 because of scope revisions and cost escalation.",
        encoding="utf-8",
    )

    result = run_bid_review(project_dir)
    decision = json.loads((result.artifacts_dir / "decision_summary.json").read_text())

    assert decision["recommendation"] == "no_go"


def test_bid_review_runner_surfaces_outcome_contradictions(tmp_path: Path) -> None:
    project_dir = tmp_path / "outcome-contradictions"
    project_dir.mkdir()
    (project_dir / "Prime Contract Agreement.md").write_text(
        "Section 1 Scope\nContractor shall perform the work shown in the plans.",
        encoding="utf-8",
    )
    (project_dir / "General Conditions.md").write_text(
        "Section 2 Coordination\nProject meetings will occur weekly.",
        encoding="utf-8",
    )
    (project_dir / "Insurance Requirements.md").write_text(
        "Certificates of insurance are required before starting work.",
        encoding="utf-8",
    )
    (project_dir / "Board Resolution.md").write_text(
        "Resolution approving Change Order No. 4 because of cost escalation and scope revisions.",
        encoding="utf-8",
    )

    result = run_bid_review(project_dir)
    challenges = json.loads((result.artifacts_dir / "review_challenges.json").read_text())

    assert any("Public outcome evidence indicates delivery or governance stress" in item for item in challenges["contradictions"])


def test_bid_review_runner_profiles_transport_procurement_and_outcomes(tmp_path: Path) -> None:
    project_dir = tmp_path / "caltrans-cmgc"
    project_dir.mkdir()
    (project_dir / "Prime Contract Agreement.md").write_text(
        "\n".join(
            [
                "Section 1 Delivery Method",
                "This Construction Manager/General Contractor (CMGC) Preconstruction Services Contract does not obligate the owner to award construction services.",
                "If the guaranteed maximum price is not accepted, the owner may re-advertise the work.",
                "Section 2 Funding",
                "This agreement is subject to availability of funds appropriated through the Budget Act.",
                "Section 3 Open Book",
                "Contractor shall maintain open-book cost model records. If the agency receives a Public Records Act request, it shall notify contractor.",
                "Section 4 Estimate Reconciliation",
                "Owner may retain an Independent Cost Estimator (ICE) to reconcile estimates.",
                "Section 5 Reporting",
                "Contractor shall provide monthly progress reports by Work Breakdown Structure (WBS).",
            ]
        ),
        encoding="utf-8",
    )
    (project_dir / "General Conditions.md").write_text(
        "Notice of claim must be provided within 10 business days.",
        encoding="utf-8",
    )
    (project_dir / "Insurance Requirements.md").write_text(
        "\n".join(
            [
                "Additional insured status is required.",
                "Umbrella coverage shall drop down if primary insurance is exhausted.",
                "Certificates of insurance are required before starting work.",
            ]
        ),
        encoding="utf-8",
    )
    (project_dir / "RFQ Procurement Package.md").write_text(
        "Qualifications-based selection under RFQ for this bridge rehabilitation project.",
        encoding="utf-8",
    )
    (project_dir / "Board Resolution.md").write_text(
        "Resolution approving Change Order No. 4 and settlement agreement because of cost escalation and budget shortfall.",
        encoding="utf-8",
    )
    (project_dir / "Proposed Budget FY2027.md").write_text(
        "Capital budget reflects accelerated delivery expectations, grant deadline pressure, and phased funding tied to reimbursements.",
        encoding="utf-8",
    )
    (project_dir / "Project Status Dashboard.md").write_text(
        "Project awarded in 2025. Estimated completion 2026. 45 percent complete.",
        encoding="utf-8",
    )

    result = run_bid_review(project_dir)

    risk_findings = json.loads((result.artifacts_dir / "risk_findings.json").read_text())
    assert any(item["category"] == "cmgc_offramp" for item in risk_findings)
    assert any(item["category"] == "appropriation_limit" for item in risk_findings)

    insurance_findings = json.loads((result.artifacts_dir / "insurance_findings.json").read_text())
    assert any(item["category"] == "umbrella_drop_down" for item in insurance_findings)

    procurement_profile = json.loads((result.artifacts_dir / "procurement_profile.json").read_text())
    assert procurement_profile["agreement_type"] == "cmgc_preconstruction_services"
    assert procurement_profile["procurement_method"] == "qbs_or_rfq"
    assert "gmp_offramp" in procurement_profile["detected_clause_families"]
    assert "reporting_wbs" in procurement_profile["detected_clause_families"]
    assert "board_minutes" in procurement_profile["governance_artifacts_present"]

    outcome_evidence = json.loads((result.artifacts_dir / "outcome_evidence.json").read_text())
    event_types = {item["event_type"] for item in outcome_evidence["events"]}
    assert outcome_evidence["outcome_status"] == "scope_rescope"
    assert "change_order" in event_types
    assert "scope_change" in event_types
    assert "project_status_update" in event_types

    obligations = json.loads((result.artifacts_dir / "obligations_register.json").read_text())
    assert any(item["title"] == "Submit monthly progress reports by work breakdown structure" for item in obligations)

    context_profile = json.loads((result.artifacts_dir / "context_profile.json").read_text())
    assert context_profile["funding_flexibility"] == "low"
    assert context_profile["schedule_pressure"] == "high"
    assert context_profile["oversight_intensity"] == "high"
    assert context_profile["internal_only"] is True


def test_bid_review_runner_rejects_missing_project_directory(tmp_path: Path) -> None:
    missing_dir = tmp_path / "does-not-exist"
    try:
        run_bid_review(missing_dir)
    except FileNotFoundError as exc:
        assert "Project directory does not exist" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("run_bid_review should fail for a missing project directory.")


def test_bid_review_obligations_are_stable_and_traceable(tmp_path: Path) -> None:
    project_dir = tmp_path / "stable-obligations"
    project_dir.mkdir()
    (project_dir / "Prime Contract Agreement.md").write_text(
        "\n".join(
            [
                "Section 5.1 Payment",
                "Certified payroll must be submitted weekly.",
                "Section 5.2 Insurance",
                "Certificates of insurance are required before starting work.",
                "Section 5.3 Claims",
                "Notice of claim must be provided within 7 calendar days.",
            ]
        ),
        encoding="utf-8",
    )
    (project_dir / "General Conditions.md").write_text(
        "No damages for delay shall be allowed.",
        encoding="utf-8",
    )
    (project_dir / "Insurance Requirements.md").write_text(
        "Additional insured status is required.",
        encoding="utf-8",
    )

    first = run_bid_review(project_dir)
    second = run_bid_review(project_dir)

    first_obligations = json.loads((first.artifacts_dir / "obligations_register.json").read_text())
    second_obligations = json.loads((second.artifacts_dir / "obligations_register.json").read_text())

    first_by_title = {item["title"]: item for item in first_obligations}
    second_by_title = {item["title"]: item for item in second_obligations}

    assert first_by_title["Submit certified payroll reports"]["id"] == second_by_title["Submit certified payroll reports"]["id"]
    assert "::" in first_by_title["Submit certified payroll reports"]["source_clause"]
    assert first_by_title["Submit certified payroll reports"]["source_document_id"]
    assert first_by_title["Submit certified payroll reports"]["source_excerpt"]


def test_bid_review_preserves_distinct_obligations_with_repeated_wording(tmp_path: Path) -> None:
    project_dir = tmp_path / "distinct-obligations"
    project_dir.mkdir()
    (project_dir / "Prime Contract Agreement.md").write_text(
        "\n".join(
            [
                "Section 5.1 Claims",
                "Notice of claim must be provided within 7 calendar days.",
                "Section 5.2 Utility Delays",
                "Notice of claim must be provided within 7 calendar days.",
                "Section 5.3 Payroll",
                "Certified payroll must be submitted weekly.",
            ]
        ),
        encoding="utf-8",
    )
    (project_dir / "General Conditions.md").write_text(
        "No damages for delay shall be allowed.",
        encoding="utf-8",
    )
    (project_dir / "Insurance Requirements.md").write_text(
        "Certificates of insurance are required before starting work.",
        encoding="utf-8",
    )

    result = run_bid_review(project_dir)
    obligations = json.loads((result.artifacts_dir / "obligations_register.json").read_text())
    notice_obligations = [item for item in obligations if item["obligation_type"] == "notice_deadline"]

    assert len(notice_obligations) == 2
    assert len({item["id"] for item in notice_obligations}) == 2
    assert len({item["source_clause"] for item in notice_obligations}) == 2


def test_bid_review_runner_persists_case_and_run_records(tmp_path: Path) -> None:
    project_dir = tmp_path / "persisted-case"
    project_dir.mkdir()
    (project_dir / "Prime Contract Agreement.md").write_text(
        "\n".join(
            [
                "Owner may terminate for convenience.",
                "Subcontractor shall be paid on a pay-if-paid basis.",
                "This agreement is subject to availability of funds appropriated through the Budget Act.",
            ]
        ),
        encoding="utf-8",
    )
    (project_dir / "General Conditions.md").write_text(
        "Notice of claim must be provided within 5 business days.",
        encoding="utf-8",
    )
    (project_dir / "Insurance Requirements.md").write_text(
        "Certificates of insurance are required before starting work.",
        encoding="utf-8",
    )
    (project_dir / "Board Resolution.md").write_text(
        "Board resolution documents change order activity and status update.",
        encoding="utf-8",
    )

    first = run_bid_review(project_dir)

    case_record = json.loads(first.case_record_path.read_text())
    run_record = json.loads(first.run_record_path.read_text())

    assert case_record["project_id"] == "persisted-case"
    assert case_record["latest_run_id"] == run_record["run_id"]
    assert case_record["total_runs"] == 1
    assert case_record["latest_agreement_type"] == "unknown_agreement_type"
    assert run_record["procurement_profile"]["project_id"] == "persisted-case"
    assert run_record["outcome_evidence"]["outcome_status"] == "dispute_or_change_documented"
    assert run_record["artifact_paths"]["decision_summary.json"].endswith("decision_summary.json")

    second = run_bid_review(project_dir)
    case_record_after_second_run = json.loads(second.case_record_path.read_text())

    assert case_record_after_second_run["total_runs"] == 2
    assert case_record_after_second_run["latest_run_id"] != case_record["latest_run_id"]
    assert len(case_record_after_second_run["run_history"]) == 2
