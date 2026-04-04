from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apps.contract_intelligence.evaluation.corpus import default_corpus_dir
from apps.contract_intelligence.monitoring.runner import monitor_contract
from apps.contract_intelligence.orchestration.bid_review_runner import _project_id, run_bid_review
from apps.contract_intelligence.orchestration.commit_runner import commit_contract
from apps.contract_intelligence.storage import FileSystemCaseStore
from apps.contract_intelligence.ui.dashboard import render_project_dashboard


@dataclass(frozen=True)
class DemoCaseExport:
    case_id: str
    title: str
    dashboard_path: Path
    project_id: str
    recommendation: str
    overall_risk: str
    analysis_perspective: str
    findings_count: int
    obligations_count: int
    alerts_count: int
    documents_count: int
    highlights: tuple[str, ...]


@dataclass(frozen=True)
class DemoExportResult:
    generated_at: str
    corpus_dir: Path
    reference_root: Path
    site_dir: Path
    manifest_path: Path
    cases: tuple[DemoCaseExport, ...]


def default_reference_root() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "contract_intelligence_reference"


def default_demo_site_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "demo_site" / "generated"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _titleize_case(case_id: str) -> str:
    return case_id.replace("_", " ").replace("-", " ").strip().title()


def _workspace_root(reference_root: Path) -> Path:
    return reference_root / "projects"


def _artifacts_root(reference_root: Path) -> Path:
    return reference_root / "artifacts"


def _case_working_dir(case_dir: Path, reference_root: Path) -> Path:
    return _workspace_root(reference_root) / case_dir.name


def _copy_inputs(case_dir: Path, destination: Path) -> None:
    inputs_dir = case_dir / "inputs"
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(inputs_dir, destination)


def _finding_dispositions_for_demo(artifact_paths: dict[str, Path]) -> list[dict[str, str]]:
    dispositions: list[dict[str, str]] = []
    for artifact_name in ("risk_findings.json", "insurance_findings.json", "compliance_findings.json"):
        payload = _read_json(artifact_paths[artifact_name])
        for item in payload:
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity", "medium"))
            dispositions.append(
                {
                    "source_finding_id": str(item.get("id", "unknown_finding")),
                    "role": str(item.get("role", "unknown_role")),
                    "category": str(item.get("category", "unknown_category")),
                    "title": str(item.get("title", "Unnamed finding")),
                    "severity": severity,
                    "recommended_action": str(item.get("recommended_action", "")),
                    "disposition": "accepted" if severity in {"high", "critical"} else "priced",
                    "rationale": "Reference-demo disposition generated to show committed-state carry-forward.",
                }
            )
    return dispositions


def _demo_status_inputs(project_dir: Path) -> list[dict[str, str]]:
    store = FileSystemCaseStore(project_dir / ".contract_intelligence")
    project_id = _project_id(project_dir)
    obligations = store.load_current_obligations(project_id)
    if not obligations:
        return []

    statuses: list[dict[str, str]] = []
    for index, obligation in enumerate(obligations):
        if index == 0:
            statuses.append(
                {
                    "obligation_id": obligation.id,
                    "status": "late",
                    "summary": "Reference-demo monitoring marks this obligation as overdue for operator attention.",
                }
            )
        elif index == 1:
            statuses.append(
                {
                    "obligation_id": obligation.id,
                    "status": "due",
                    "summary": "Reference-demo monitoring marks this obligation as currently due.",
                }
            )
        elif index == 2:
            statuses.append(
                {
                    "obligation_id": obligation.id,
                    "status": "satisfied",
                    "summary": "Reference-demo monitoring marks this obligation as satisfied for the current cycle.",
                }
            )
        else:
            break
    return statuses


def _case_highlights(run_record: dict[str, Any], monitoring_record: dict[str, Any] | None) -> tuple[str, ...]:
    decision = dict(run_record.get("decision_summary") or {})
    reasons = [str(item) for item in decision.get("top_reasons", []) if str(item).strip()]
    must_fix = [str(item) for item in decision.get("must_fix_before_bid", []) if str(item).strip()]
    alerts = monitoring_record.get("alerts", []) if monitoring_record else []
    highlights: list[str] = []
    highlights.extend(reasons[:2])
    if must_fix:
        highlights.append(f"Must-fix before bid: {must_fix[0]}")
    if alerts:
        highlights.append(f"Monitoring alert posture: {len(alerts)} open alert(s) in the reference lifecycle snapshot.")
    return tuple(highlights[:4])


def _build_case_export(case_dir: Path, *, reference_root: Path, site_dir: Path) -> DemoCaseExport:
    workspace_dir = _case_working_dir(case_dir, reference_root)
    artifacts_dir = _artifacts_root(reference_root) / case_dir.name
    _copy_inputs(case_dir, workspace_dir)

    bid_result = run_bid_review(project_dir=workspace_dir, artifacts_dir=artifacts_dir)

    dispositions_path = workspace_dir / ".contract_intelligence" / "demo_finding_dispositions.json"
    dispositions_path.parent.mkdir(parents=True, exist_ok=True)
    dispositions_path.write_text(
        json.dumps(
            _finding_dispositions_for_demo(bid_result.artifact_paths),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    commit_contract(project_dir=workspace_dir, finding_dispositions_file=dispositions_path)

    status_inputs = _demo_status_inputs(workspace_dir)
    if status_inputs:
        status_inputs_path = workspace_dir / ".contract_intelligence" / "demo_status_inputs.json"
        status_inputs_path.write_text(json.dumps(status_inputs, indent=2) + "\n", encoding="utf-8")
        monitor_contract(project_dir=workspace_dir, status_inputs_file=status_inputs_path)

    case_site_dir = site_dir / "cases" / case_dir.name
    case_site_dir.mkdir(parents=True, exist_ok=True)
    dashboard_path = render_project_dashboard(
        workspace_dir,
        output_path=case_site_dir / "dashboard.html",
        report_mode="external",
    )

    store = FileSystemCaseStore(workspace_dir / ".contract_intelligence")
    project_id = _project_id(workspace_dir)
    run_record = store.load_latest_run_record(project_id).model_dump(mode="json")
    case_record = store.load_case_record(project_id).model_dump(mode="json")
    monitoring_record = None
    if case_record.get("latest_monitoring_run_id"):
        monitoring_record = store.load_latest_monitoring_run(project_id).model_dump(mode="json")

    risk_findings = _read_json(bid_result.artifact_paths["risk_findings.json"])
    insurance_findings = _read_json(bid_result.artifact_paths["insurance_findings.json"])
    compliance_findings = _read_json(bid_result.artifact_paths["compliance_findings.json"])
    findings_count = len(risk_findings) + len(insurance_findings) + len(compliance_findings)
    documents_count = len((run_record.get("document_inventory") or {}).get("documents", []))
    obligations_count = int(run_record.get("obligations_count", 0))
    alerts_count = len((monitoring_record or {}).get("alerts", []))
    decision = dict(run_record.get("decision_summary") or {})

    return DemoCaseExport(
        case_id=case_dir.name,
        title=_titleize_case(case_dir.name),
        dashboard_path=dashboard_path,
        project_id=project_id,
        recommendation=str(decision.get("recommendation", "unknown")),
        overall_risk=str(decision.get("overall_risk", "unknown")),
        analysis_perspective=str(decision.get("analysis_perspective", "vendor")),
        findings_count=findings_count,
        obligations_count=obligations_count,
        alerts_count=alerts_count,
        documents_count=documents_count,
        highlights=_case_highlights(run_record, monitoring_record),
    )


def build_demo_assets(
    *,
    corpus_dir: str | Path | None = None,
    reference_root: str | Path | None = None,
    site_dir: str | Path | None = None,
) -> DemoExportResult:
    corpus_path = Path(corpus_dir).expanduser().resolve() if corpus_dir else default_corpus_dir()
    reference_path = Path(reference_root).expanduser().resolve() if reference_root else default_reference_root()
    site_path = Path(site_dir).expanduser().resolve() if site_dir else default_demo_site_dir()

    reference_path.mkdir(parents=True, exist_ok=True)
    site_path.mkdir(parents=True, exist_ok=True)

    cases: list[DemoCaseExport] = []
    for case_dir in sorted(path for path in corpus_path.iterdir() if path.is_dir() and (path / "expected.json").exists()):
        cases.append(_build_case_export(case_dir, reference_root=reference_path, site_dir=site_path))

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest_payload = {
        "generated_at": generated_at,
        "site_title": "ICM Contract Intelligence Demo",
        "summary": "Sanitized public demo cases generated from the contract-intelligence gold corpus.",
        "cases": [
            {
                "case_id": case.case_id,
                "title": case.title,
                "project_id": case.project_id,
                "analysis_perspective": case.analysis_perspective,
                "recommendation": case.recommendation,
                "overall_risk": case.overall_risk,
                "findings_count": case.findings_count,
                "obligations_count": case.obligations_count,
                "alerts_count": case.alerts_count,
                "documents_count": case.documents_count,
                "dashboard_href": f"/generated/cases/{case.case_id}/dashboard.html",
                "highlights": list(case.highlights),
            }
            for case in cases
        ],
    }
    manifest_path = site_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")

    return DemoExportResult(
        generated_at=generated_at,
        corpus_dir=corpus_path,
        reference_root=reference_path,
        site_dir=site_path,
        manifest_path=manifest_path,
        cases=tuple(cases),
    )
