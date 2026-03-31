from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.contract_intelligence.api import app
from apps.contract_intelligence.demo import build_demo_assets


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


def _write_finding_dispositions(project_dir: Path, destination: Path) -> Path:
    project_id = project_dir.name
    artifact_root = project_dir / "artifacts"
    dispositions: list[dict[str, str]] = []
    for artifact_name in ("risk_findings.json", "insurance_findings.json", "compliance_findings.json"):
        payload = json.loads((artifact_root / artifact_name).read_text())
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
                    "rationale": f"API test disposition for {project_id}.",
                }
            )
    destination.write_text(json.dumps(dispositions), encoding="utf-8")
    return destination


def test_contract_intelligence_api_wraps_full_local_lifecycle(tmp_path: Path) -> None:
    project_dir = tmp_path / "api-bridge"
    _write_project_package(project_dir)

    analyze_response = client.post(
        "/projects/analyze",
        json={"project_dir": str(project_dir), "analysis_perspective": "agency"},
    )
    assert analyze_response.status_code == 200
    analyze_payload = analyze_response.json()
    assert analyze_payload["project_id"] == "api-bridge"
    assert analyze_payload["analysis_perspective"] == "agency"

    dispositions_path = _write_finding_dispositions(project_dir, tmp_path / "finding_dispositions.json")
    commit_response = client.post(
        "/projects/commit",
        json={"project_dir": str(project_dir), "finding_dispositions_file": str(dispositions_path)},
    )
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
    assert state_response.json()["latest_analysis_perspective"] == "agency"
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


def test_contract_intelligence_api_rejects_forbidden_artifacts_dir(monkeypatch, tmp_path: Path) -> None:
    project_dir = tmp_path / "api-artifacts-boundary"
    _write_project_package(project_dir)
    monkeypatch.setenv("CONTRACT_INTELLIGENCE_ALLOWED_ROOTS", str(tmp_path.resolve()))

    forbidden = tmp_path.parent / "outside-artifacts"
    response = client.post(
        "/projects/analyze",
        json={"project_dir": str(project_dir), "artifacts_dir": str(forbidden)},
    )
    assert response.status_code == 403


def test_contract_intelligence_api_rejects_missing_committed_contract_dir(tmp_path: Path) -> None:
    project_dir = tmp_path / "api-missing-commit-dir"
    _write_project_package(project_dir)
    analyze_response = client.post("/projects/analyze", json={"project_dir": str(project_dir)})
    assert analyze_response.status_code == 200

    dispositions_path = _write_finding_dispositions(project_dir, tmp_path / "finding_dispositions.json")
    missing_dir = tmp_path / "missing-final"
    commit_response = client.post(
        "/projects/commit",
        json={
            "project_dir": str(project_dir),
            "committed_contract_dir": str(missing_dir),
            "finding_dispositions_file": str(dispositions_path),
        },
    )
    assert commit_response.status_code == 400


def test_contract_intelligence_api_persists_review_actions(tmp_path: Path) -> None:
    project_dir = tmp_path / "api-review-actions"
    _write_project_package(project_dir)

    analyze_response = client.post("/projects/analyze", json={"project_dir": str(project_dir)})
    assert analyze_response.status_code == 200

    upsert_response = client.put(
        "/projects/review-actions",
        json={
            "project_dir": str(project_dir),
            "kind": "finding",
            "ui_id": "finding_001",
            "title": "Pay-if-paid cash flow exposure",
            "disposition": "needs_legal",
            "owner": "Legal",
            "note": "Escalate before bid submission.",
        },
    )
    assert upsert_response.status_code == 200
    assert upsert_response.json()["disposition"] == "needs_legal"

    get_response = client.get("/projects/review-actions", params={"project_dir": str(project_dir)})
    assert get_response.status_code == 200
    assert get_response.json()[0]["title"] == "Pay-if-paid cash flow exposure"

    clear_response = client.post(
        "/projects/review-actions/clear",
        json={"project_dir": str(project_dir), "kind": "finding", "ui_id": "finding_001"},
    )
    assert clear_response.status_code == 200

    get_after_clear = client.get("/projects/review-actions", params={"project_dir": str(project_dir)})
    assert get_after_clear.status_code == 200
    assert get_after_clear.json() == []


def test_contract_intelligence_api_rejects_malformed_alert_snapshots(tmp_path: Path) -> None:
    project_dir = tmp_path / "api-bad-alerts"
    _write_project_package(project_dir)

    analyze_response = client.post("/projects/analyze", json={"project_dir": str(project_dir)})
    assert analyze_response.status_code == 200
    dispositions_path = _write_finding_dispositions(project_dir, tmp_path / "finding_dispositions.json")
    commit_response = client.post(
        "/projects/commit",
        json={"project_dir": str(project_dir), "finding_dispositions_file": str(dispositions_path)},
    )
    assert commit_response.status_code == 200

    alerts_path = project_dir / ".contract_intelligence" / "api-bad-alerts" / "alerts" / "current.json"
    alerts_path.parent.mkdir(parents=True, exist_ok=True)
    alerts_path.write_text(json.dumps([{"alert_type": "late"}]), encoding="utf-8")

    response = client.get("/projects/alerts", params={"project_dir": str(project_dir)})
    assert response.status_code == 500
    assert response.json()["detail"] == "Alert snapshot failed validation."


def test_contract_intelligence_api_serves_reference_manifest_and_dashboard(monkeypatch, tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    case_dir = corpus_dir / "demo-reference"
    inputs_dir = case_dir / "inputs"
    inputs_dir.mkdir(parents=True)
    (case_dir / "expected.json").write_text("{}", encoding="utf-8")
    (inputs_dir / "Prime Contract Agreement.md").write_text(
        "\n".join(
            [
                "Owner may terminate for convenience.",
                "Subcontractor shall be paid on a pay-if-paid basis.",
                "No damages for delay shall be allowed.",
            ]
        ),
        encoding="utf-8",
    )
    (inputs_dir / "General Conditions.md").write_text(
        "Notice of claim must be provided within 5 calendar days.",
        encoding="utf-8",
    )
    (inputs_dir / "Insurance Requirements.md").write_text(
        "Certificates of insurance are required before starting work.",
        encoding="utf-8",
    )
    (inputs_dir / "Funding Memo.md").write_text(
        "Certified payroll must be submitted weekly.",
        encoding="utf-8",
    )

    build_demo_assets(
        corpus_dir=corpus_dir,
        reference_root=tmp_path / "reference-root",
        site_dir=tmp_path / "reference-site",
    )
    monkeypatch.setenv("CONTRACT_INTELLIGENCE_REFERENCE_SITE_DIR", str((tmp_path / "reference-site").resolve()))

    root_response = client.get("/")
    assert root_response.status_code == 200
    assert "ICM on Render" in root_response.text

    manifest_response = client.get("/reference/manifest")
    assert manifest_response.status_code == 200
    assert manifest_response.json()["cases"][0]["case_id"] == "demo-reference"

    dashboard_response = client.get("/reference/cases/demo-reference/dashboard")
    assert dashboard_response.status_code == 200
    assert "Internal-only context is intentionally omitted from the external artifact." in dashboard_response.text


def test_contract_intelligence_api_optional_reference_auth(monkeypatch, tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    case_dir = corpus_dir / "demo-auth"
    inputs_dir = case_dir / "inputs"
    inputs_dir.mkdir(parents=True)
    (case_dir / "expected.json").write_text("{}", encoding="utf-8")
    (inputs_dir / "Prime Contract Agreement.md").write_text(
        "Subcontractor shall be paid on a pay-if-paid basis.",
        encoding="utf-8",
    )
    (inputs_dir / "General Conditions.md").write_text(
        "Notice of claim must be provided within 5 calendar days.",
        encoding="utf-8",
    )
    (inputs_dir / "Insurance Requirements.md").write_text(
        "Certificates of insurance are required before starting work.",
        encoding="utf-8",
    )
    (inputs_dir / "Funding Memo.md").write_text(
        "Certified payroll must be submitted weekly.",
        encoding="utf-8",
    )
    build_demo_assets(
        corpus_dir=corpus_dir,
        reference_root=tmp_path / "reference-root",
        site_dir=tmp_path / "reference-site",
    )
    monkeypatch.setenv("CONTRACT_INTELLIGENCE_REFERENCE_SITE_DIR", str((tmp_path / "reference-site").resolve()))
    monkeypatch.setenv("ICM_REFERENCE_AUTH_USER", "demo")
    monkeypatch.setenv("ICM_REFERENCE_AUTH_PASSWORD", "secret")

    unauthorized = client.get("/reference/manifest")
    assert unauthorized.status_code == 401

    token = base64.b64encode(b"demo:secret").decode("ascii")
    authorized = client.get("/reference/manifest", headers={"Authorization": f"Basic {token}"})
    assert authorized.status_code == 200
    assert authorized.json()["cases"][0]["case_id"] == "demo-auth"

    health_response = client.get("/health")
    assert health_response.status_code == 200
