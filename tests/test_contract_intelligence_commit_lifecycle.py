from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

bid_runner = importlib.import_module("apps.contract_intelligence.orchestration.bid_review_runner")
commit_runner = importlib.import_module("apps.contract_intelligence.orchestration.commit_runner")

run_bid_review = bid_runner.run_bid_review
commit_contract = commit_runner.commit_contract
load_committed_obligations = commit_runner.load_committed_obligations


def _write_project_package(project_dir: Path) -> None:
    project_dir.mkdir()
    (project_dir / "Prime Contract Agreement.md").write_text(
        "\n".join(
            [
                "Owner may terminate for convenience.",
                "Subcontractor shall be paid on a pay-if-paid basis.",
                "No damages for delay shall be allowed.",
                "This agreement is subject to availability of funds appropriated through the Budget Act.",
            ]
        ),
        encoding="utf-8",
    )
    (project_dir / "General Conditions.md").write_text(
        "Notice of claim must be provided within 7 calendar days.",
        encoding="utf-8",
    )
    (project_dir / "Insurance Requirements.md").write_text(
        "Certificates of insurance are required before starting work.",
        encoding="utf-8",
    )
    (project_dir / "Funding Memo.md").write_text(
        "Certified payroll must be submitted weekly.",
        encoding="utf-8",
    )


def _write_finding_dispositions(result, destination: Path) -> Path:
    dispositions: list[dict[str, str]] = []
    for artifact_name in ("risk_findings.json", "insurance_findings.json", "compliance_findings.json"):
        payload = json.loads(result.artifact_paths[artifact_name].read_text())
        for item in payload:
            dispositions.append(
                {
                    "source_finding_id": item["id"],
                    "role": item["role"],
                    "category": item["category"],
                    "title": item["title"],
                    "severity": item["severity"],
                    "recommended_action": item["recommended_action"],
                    "disposition": "accepted" if item["severity"] in {"high", "critical"} else "priced",
                    "rationale": "Test fixture explicitly dispositioned this finding at commit time.",
                }
            )
    destination.write_text(json.dumps(dispositions), encoding="utf-8")
    return destination


def test_commit_contract_creates_committed_record_and_obligation_snapshot(tmp_path: Path) -> None:
    project_dir = tmp_path / "committed-bridge"
    _write_project_package(project_dir)

    bid_result = run_bid_review(project_dir)
    dispositions_path = _write_finding_dispositions(bid_result, tmp_path / "finding_dispositions.json")
    commit_result = commit_contract(project_dir, finding_dispositions_file=dispositions_path)

    case_record = json.loads(commit_result.case_record_path.read_text())
    commit_record = json.loads(commit_result.commit_record_path.read_text())
    obligations = json.loads(commit_result.obligations_path.read_text())

    assert case_record["project_id"] == "committed-bridge"
    assert case_record["latest_commit_id"] == commit_result.commit_id
    assert case_record["total_commits"] == 1
    assert case_record["latest_obligations_count"] == len(obligations)

    assert commit_record["project_id"] == "committed-bridge"
    assert commit_record["source_run_id"] == json.loads(bid_result.run_record_path.read_text())["run_id"]
    assert commit_record["obligations_count"] == len(obligations)
    assert commit_record["accepted_risks"]
    assert commit_record["finding_dispositions"]
    assert any(item["title"] == "Submit certified payroll reports" for item in obligations)


def test_commit_contract_accepts_negotiated_changes_and_extracts_current_obligations(tmp_path: Path) -> None:
    project_dir = tmp_path / "committed-tunnel"
    _write_project_package(project_dir)
    bid_result = run_bid_review(project_dir)
    dispositions_path = _write_finding_dispositions(bid_result, tmp_path / "finding_dispositions.json")

    negotiated_changes_path = tmp_path / "negotiated_changes.json"
    negotiated_changes_path.write_text(
        json.dumps(
            [
                {
                    "change_id": "chg_001",
                    "title": "Delay relief carveout",
                    "summary": "Owner-caused delay compensation carveout was added to the final agreement.",
                    "status": "accepted",
                    "source_reference": "Section 8.6",
                }
            ]
        ),
        encoding="utf-8",
    )

    commit_result = commit_contract(
        project_dir,
        finding_dispositions_file=dispositions_path,
        negotiated_changes_file=negotiated_changes_path,
    )
    commit_record = json.loads(commit_result.commit_record_path.read_text())
    assert commit_record["negotiated_changes"][0]["title"] == "Delay relief carveout"

    exported_obligations = tmp_path / "exported_obligations.json"
    extract_result = load_committed_obligations(project_dir, output_path=exported_obligations)
    exported_payload = json.loads(exported_obligations.read_text())

    assert extract_result.obligations_path == exported_obligations
    assert extract_result.obligations_count == len(exported_payload)
    assert any(item["title"] == "Provide certificates of insurance before starting work" for item in exported_payload)


def test_commit_contract_rejects_unresolved_high_findings_without_dispositions(tmp_path: Path) -> None:
    project_dir = tmp_path / "unresolved-bridge"
    _write_project_package(project_dir)
    run_bid_review(project_dir)

    try:
        commit_contract(project_dir)
    except ValueError as exc:
        assert "HIGH/CRITICAL findings remain unresolved" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("commit_contract should fail when high findings are left unresolved.")


def test_commit_contract_rejects_missing_committed_contract_directory(tmp_path: Path) -> None:
    project_dir = tmp_path / "missing-commit-dir"
    _write_project_package(project_dir)
    bid_result = run_bid_review(project_dir)
    dispositions_path = _write_finding_dispositions(bid_result, tmp_path / "finding_dispositions.json")

    missing_dir = tmp_path / "does-not-exist"
    try:
        commit_contract(
            project_dir,
            committed_contract_dir=missing_dir,
            finding_dispositions_file=dispositions_path,
        )
    except FileNotFoundError as exc:
        assert "Committed contract directory does not exist" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("commit_contract should fail for a nonexistent committed contract directory.")


def test_commit_contract_rejects_malformed_accepted_risks_payload(tmp_path: Path) -> None:
    project_dir = tmp_path / "bad-accepted-risks"
    _write_project_package(project_dir)
    run_bid_review(project_dir)

    accepted_risks_path = tmp_path / "accepted_risks.json"
    accepted_risks_path.write_text(json.dumps([{"source_finding_id": "finding_001"}]), encoding="utf-8")

    try:
        commit_contract(project_dir, accepted_risks_file=accepted_risks_path)
    except ValueError as exc:
        assert "Accepted risks item 1 is invalid" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("commit_contract should fail for malformed accepted-risk payloads.")


def test_commit_contract_rejects_malformed_negotiated_change_payload(tmp_path: Path) -> None:
    project_dir = tmp_path / "bad-negotiated-changes"
    _write_project_package(project_dir)
    bid_result = run_bid_review(project_dir)
    dispositions_path = _write_finding_dispositions(bid_result, tmp_path / "finding_dispositions.json")

    negotiated_changes_path = tmp_path / "negotiated_changes.json"
    negotiated_changes_path.write_text(json.dumps([{"change_id": "chg_001"}]), encoding="utf-8")

    try:
        commit_contract(
            project_dir,
            finding_dispositions_file=dispositions_path,
            negotiated_changes_file=negotiated_changes_path,
        )
    except ValueError as exc:
        assert "Negotiated changes item 1 is invalid" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("commit_contract should fail for malformed negotiated-change payloads.")
