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


def test_render_project_dashboard_outputs_html_snapshot(tmp_path: Path) -> None:
    project_dir = tmp_path / "ui-bridge"
    _write_project_package(project_dir)
    run_bid_review(project_dir)
    commit_contract(project_dir)

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
    assert "go_with_conditions" in html
