from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

bid_runner = importlib.import_module("apps.contract_intelligence.orchestration.bid_review_runner")
commit_runner = importlib.import_module("apps.contract_intelligence.orchestration.commit_runner")
monitoring_runner = importlib.import_module("apps.contract_intelligence.monitoring.runner")

run_bid_review = bid_runner.run_bid_review
commit_contract = commit_runner.commit_contract
monitor_contract = monitoring_runner.monitor_contract


def _write_project_package(project_dir: Path) -> None:
    project_dir.mkdir()
    (project_dir / "Prime Contract Agreement.md").write_text(
        "\n".join(
            [
                "Owner may terminate for convenience.",
                "Subcontractor shall be paid on a pay-if-paid basis.",
                "No damages for delay shall be allowed.",
            ]
        ),
        encoding="utf-8",
    )
    (project_dir / "General Conditions.md").write_text(
        "Notice of claim must be provided within 5 calendar days.",
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


def test_monitor_contract_persists_snapshot_and_alerts(tmp_path: Path) -> None:
    project_dir = tmp_path / "monitoring-bridge"
    _write_project_package(project_dir)
    bid_result = run_bid_review(project_dir)
    dispositions_path = _write_finding_dispositions(bid_result, tmp_path / "finding_dispositions.json")
    commit_contract(project_dir, finding_dispositions_file=dispositions_path)
    obligations = json.loads(
        (project_dir / ".contract_intelligence" / "monitoring-bridge" / "obligations" / "current.json").read_text()
    )
    by_title = {item["title"]: item["id"] for item in obligations}

    status_inputs = tmp_path / "status_inputs.json"
    status_inputs.write_text(
        json.dumps(
            [
                {
                    "obligation_id": by_title["Submit certified payroll reports"],
                    "status": "late",
                    "summary": "Certified payroll was not submitted for the latest weekly cycle.",
                    "notes": ["Escalate to payroll compliance owner."],
                },
                {
                    "obligation_id": by_title["Provide certificates of insurance before starting work"],
                    "status": "satisfied",
                    "last_satisfied_at": "2026-03-27T09:00:00Z",
                    "summary": "Certificates were delivered before mobilization.",
                },
            ]
        ),
        encoding="utf-8",
    )

    result = monitor_contract(project_dir, status_inputs_file=status_inputs)

    monitoring_snapshot = json.loads(result.monitoring_snapshot_path.read_text())
    alerts = json.loads(result.alerts_path.read_text())
    case_record = json.loads((project_dir / ".contract_intelligence" / "monitoring-bridge" / "case_record.json").read_text())

    assert monitoring_snapshot["project_id"] == "monitoring-bridge"
    assert monitoring_snapshot["source_commit_id"] == case_record["latest_commit_id"]
    statuses = {item["obligation_id"]: item["status"] for item in monitoring_snapshot["monitored_obligations"]}
    assert statuses[by_title["Submit certified payroll reports"]] == "late"
    assert statuses[by_title["Provide certificates of insurance before starting work"]] == "satisfied"
    assert alerts[0]["alert_type"] == "late"
    assert case_record["latest_monitoring_run_id"] == result.run_id
    assert case_record["total_monitoring_runs"] == 1


def test_monitor_contract_reruns_without_losing_history(tmp_path: Path) -> None:
    project_dir = tmp_path / "monitoring-tunnel"
    _write_project_package(project_dir)
    bid_result = run_bid_review(project_dir)
    dispositions_path = _write_finding_dispositions(bid_result, tmp_path / "finding_dispositions.json")
    commit_contract(project_dir, finding_dispositions_file=dispositions_path)

    first = monitor_contract(project_dir)
    second = monitor_contract(project_dir)

    case_record = json.loads((project_dir / ".contract_intelligence" / "monitoring-tunnel" / "case_record.json").read_text())

    assert first.run_id != second.run_id
    assert case_record["total_monitoring_runs"] == 2
    assert len(case_record["monitoring_history"]) == 2
    assert case_record["latest_monitoring_run_id"] == second.run_id


def test_monitor_contract_preserves_alert_identity_for_same_open_condition(tmp_path: Path) -> None:
    project_dir = tmp_path / "monitoring-stable-alerts"
    _write_project_package(project_dir)
    bid_result = run_bid_review(project_dir)
    dispositions_path = _write_finding_dispositions(bid_result, tmp_path / "finding_dispositions.json")
    commit_contract(project_dir, finding_dispositions_file=dispositions_path)
    obligations = json.loads(
        (project_dir / ".contract_intelligence" / "monitoring-stable-alerts" / "obligations" / "current.json").read_text()
    )
    by_title = {item["title"]: item["id"] for item in obligations}

    status_inputs = tmp_path / "status_inputs.json"
    status_inputs.write_text(
        json.dumps(
            [
                {
                    "obligation_id": by_title["Submit certified payroll reports"],
                    "next_due_at": "2026-03-26T09:00:00Z",
                }
            ]
        ),
        encoding="utf-8",
    )

    first = monitor_contract(project_dir, status_inputs_file=status_inputs, as_of_date=__import__("datetime").date(2026, 3, 27))
    second = monitor_contract(project_dir, status_inputs_file=status_inputs, as_of_date=__import__("datetime").date(2026, 3, 27))

    alerts_history_dir = project_dir / ".contract_intelligence" / "monitoring-stable-alerts" / "alerts" / "history"
    first_alerts = json.loads((alerts_history_dir / f"{first.run_id}.json").read_text())
    second_alerts = json.loads((alerts_history_dir / f"{second.run_id}.json").read_text())

    assert first_alerts[0]["alert_id"] == second_alerts[0]["alert_id"]


def test_monitor_contract_computes_due_and_late_from_schedule_inputs(tmp_path: Path) -> None:
    project_dir = tmp_path / "monitoring-schedule"
    _write_project_package(project_dir)
    bid_result = run_bid_review(project_dir)
    dispositions_path = _write_finding_dispositions(bid_result, tmp_path / "finding_dispositions.json")
    commit_contract(project_dir, finding_dispositions_file=dispositions_path)
    obligations = json.loads(
        (project_dir / ".contract_intelligence" / "monitoring-schedule" / "obligations" / "current.json").read_text()
    )
    by_title = {item["title"]: item["id"] for item in obligations}

    status_inputs = tmp_path / "scheduled_status_inputs.json"
    status_inputs.write_text(
        json.dumps(
            [
                {
                    "obligation_id": by_title["Submit certified payroll reports"],
                    "next_due_at": "2026-03-26T09:00:00Z",
                },
                {
                    "obligation_id": by_title["Provide certificates of insurance before starting work"],
                    "next_due_at": "2026-03-27T09:00:00Z",
                },
            ]
        ),
        encoding="utf-8",
    )

    result = monitor_contract(project_dir, status_inputs_file=status_inputs, as_of_date=__import__("datetime").date(2026, 3, 27))
    monitoring_snapshot = json.loads(result.monitoring_snapshot_path.read_text())
    statuses = {item["obligation_id"]: item["status"] for item in monitoring_snapshot["monitored_obligations"]}

    assert statuses[by_title["Submit certified payroll reports"]] == "late"
    assert statuses[by_title["Provide certificates of insurance before starting work"]] == "due"


def test_monitor_contract_rejects_invalid_status_inputs(tmp_path: Path) -> None:
    project_dir = tmp_path / "monitoring-invalid-status"
    _write_project_package(project_dir)
    bid_result = run_bid_review(project_dir)
    dispositions_path = _write_finding_dispositions(bid_result, tmp_path / "finding_dispositions.json")
    commit_contract(project_dir, finding_dispositions_file=dispositions_path)
    obligations = json.loads(
        (project_dir / ".contract_intelligence" / "monitoring-invalid-status" / "obligations" / "current.json").read_text()
    )

    invalid_status_inputs = tmp_path / "invalid_status_inputs.json"
    invalid_status_inputs.write_text(
        json.dumps(
            [
                {
                    "obligation_id": obligations[0]["id"],
                    "status": "stale",
                }
            ]
        ),
        encoding="utf-8",
    )

    try:
        monitor_contract(project_dir, status_inputs_file=invalid_status_inputs)
    except ValueError as exc:
        assert "status must be one of pending, due, late, or satisfied" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("monitor_contract should fail for invalid status values.")
