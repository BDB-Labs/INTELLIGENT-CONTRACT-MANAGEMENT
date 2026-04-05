from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

bid_runner = importlib.import_module("apps.contract_intelligence.orchestration.bid_review_runner")
commit_runner = importlib.import_module("apps.contract_intelligence.orchestration.commit_runner")
monitoring_runner = importlib.import_module("apps.contract_intelligence.monitoring.runner")
dashboard = importlib.import_module("apps.contract_intelligence.ui.dashboard")

run_bid_review = bid_runner.run_bid_review
commit_contract = commit_runner.commit_contract
monitor_contract = monitoring_runner.monitor_contract
render_project_dashboard = dashboard.render_project_dashboard


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


def test_render_project_dashboard_outputs_html_snapshot(tmp_path: Path) -> None:
    project_dir = tmp_path / "ui-bridge"
    _write_project_package(project_dir)
    bid_result = run_bid_review(project_dir)
    dispositions_path = _write_finding_dispositions(bid_result, tmp_path / "finding_dispositions.json")
    commit_contract(project_dir, finding_dispositions_file=dispositions_path)

    obligations = json.loads(
        (project_dir / ".contract_intelligence" / "ui-bridge" / "obligations" / "current.json").read_text()
    )
    status_inputs = tmp_path / "status_inputs.json"
    status_inputs.write_text(
        json.dumps(
            [
                {
                    "obligation_id": obligations[0]["id"],
                    "status": "late",
                    "summary": "Operational follow-up is overdue.",
                }
            ]
        ),
        encoding="utf-8",
    )
    monitor_contract(project_dir, status_inputs_file=status_inputs)

    output_path = tmp_path / "dashboard.html"
    dashboard_path = render_project_dashboard(project_dir, output_path=output_path)
    html = dashboard_path.read_text(encoding="utf-8")

    assert dashboard_path == output_path
    assert "A project command surface for review decisions, committed baselines, internal context," in html
    assert "Audience-Aware Surface" in html
    assert "Human Review Board" in html
    assert "Selected Finding" in html
    assert "Selected Obligation" in html
    assert "Findings Workspace" in html
    assert "Lifecycle Timeline" in html
    assert "Relationship Advice" in html
    assert "Negotiation Playbook" in html
    assert "go_with_conditions" in html
    assert '"analysis_perspective": "vendor"' in html


def test_render_project_dashboard_external_mode_omits_internal_payload(tmp_path: Path) -> None:
    project_dir = tmp_path / "ui-external"
    _write_project_package(project_dir)
    bid_result = run_bid_review(project_dir)
    dispositions_path = _write_finding_dispositions(bid_result, tmp_path / "finding_dispositions.json")
    commit_contract(project_dir, finding_dispositions_file=dispositions_path)

    output_path = tmp_path / "dashboard-external.html"
    dashboard_path = render_project_dashboard(project_dir, output_path=output_path, report_mode="external")
    html = dashboard_path.read_text(encoding="utf-8")

    assert dashboard_path == output_path
    assert "Internal mode keeps strategy-only signals" not in html
    assert str(project_dir.resolve()) not in html
    assert "source_project_dir" not in html
    assert "storage_dir" not in html
    assert "Internal-only context is intentionally omitted from the external artifact." in html
    report_mode_copy = html.split("const reportModeCopy = ", 1)[1].split(";\n\n    const uiState", 1)[0]
    assert json.loads(report_mode_copy) == {
        "external": {
            "lead": "A shareable contract-operating summary for decision posture, committed obligations, procurement structure, and current project readiness.",
            "caption": "External mode suppresses internal strategy panels and leaves a cleaner client-facing operational surface.",
        }
    }


def test_render_project_dashboard_surfaces_artifact_diagnostics_and_cache_controls(tmp_path: Path) -> None:
    project_dir = tmp_path / "ui-diagnostics"
    _write_project_package(project_dir)
    bid_result = run_bid_review(project_dir)
    dispositions_path = _write_finding_dispositions(bid_result, tmp_path / "finding_dispositions.json")
    commit_contract(project_dir, finding_dispositions_file=dispositions_path)

    bid_result.artifact_paths["risk_findings.json"].unlink()

    output_path = tmp_path / "dashboard-diagnostics.html"
    dashboard_path = render_project_dashboard(project_dir, output_path=output_path)
    html = dashboard_path.read_text(encoding="utf-8")

    assert "Artifact Diagnostics" in html
    assert "Artifact file missing for risk findings" in html
    assert "local-cache-warning" in html
    assert "data-reset-local-review-cache" in html
