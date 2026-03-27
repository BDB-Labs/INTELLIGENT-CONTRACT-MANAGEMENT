from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.contract_intelligence.api import app


client = TestClient(app)


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


def test_contract_intelligence_api_wraps_full_local_lifecycle(tmp_path: Path) -> None:
    project_dir = tmp_path / "api-bridge"
    _write_project_package(project_dir)

    analyze_response = client.post("/projects/analyze", json={"project_dir": str(project_dir)})
    assert analyze_response.status_code == 200
    analyze_payload = analyze_response.json()
    assert analyze_payload["project_id"] == "api-bridge"

    commit_response = client.post("/projects/commit", json={"project_dir": str(project_dir)})
    assert commit_response.status_code == 200
    commit_payload = commit_response.json()
    assert commit_payload["obligations_count"] >= 1

    obligations_response = client.get("/projects/obligations", params={"project_dir": str(project_dir)})
    assert obligations_response.status_code == 200
    obligations_payload = obligations_response.json()
    by_title = {item["title"]: item["id"] for item in obligations_payload}

    status_inputs = tmp_path / "status_inputs.json"
    status_inputs.write_text(
        json.dumps(
            [
                {
                    "obligation_id": by_title["Submit certified payroll reports"],
                    "status": "late",
                    "summary": "Certified payroll is overdue.",
                }
            ]
        ),
        encoding="utf-8",
    )

    monitor_response = client.post(
        "/projects/monitor",
        json={"project_dir": str(project_dir), "status_inputs_file": str(status_inputs)},
    )
    assert monitor_response.status_code == 200
    assert monitor_response.json()["alerts_count"] == 1

    state_response = client.get("/projects/state", params={"project_dir": str(project_dir)})
    latest_commit_response = client.get("/projects/commits/latest", params={"project_dir": str(project_dir)})
    latest_monitoring_response = client.get("/projects/monitoring/latest", params={"project_dir": str(project_dir)})
    alerts_response = client.get("/projects/alerts", params={"project_dir": str(project_dir)})

    assert state_response.status_code == 200
    assert latest_commit_response.status_code == 200
    assert latest_monitoring_response.status_code == 200
    assert alerts_response.status_code == 200
    assert state_response.json()["latest_commit_id"] == latest_commit_response.json()["commit_id"]
    assert state_response.json()["latest_monitoring_run_id"] == latest_monitoring_response.json()["run_id"]
    assert any(item["alert_type"] == "late" for item in alerts_response.json())


def test_contract_intelligence_api_rejects_missing_project_directory(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing-project"
    response = client.post("/projects/analyze", json={"project_dir": str(missing_dir)})
    assert response.status_code == 400
    assert response.json()["detail"] == "Project directory does not exist."


def test_contract_intelligence_api_hides_docs_by_default() -> None:
    response = client.get("/docs")
    assert response.status_code == 404
