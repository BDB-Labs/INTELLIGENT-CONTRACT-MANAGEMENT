from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from apps.contract_intelligence.monitoring.runner import monitor_contract
from apps.contract_intelligence.orchestration.bid_review_runner import _project_id, run_bid_review
from apps.contract_intelligence.orchestration.commit_runner import commit_contract
from apps.contract_intelligence.storage import FileSystemCaseStore


app = FastAPI(title="Contract Intelligence API", version="0.1.0")


class AnalyzeProjectRequest(BaseModel):
    project_dir: str
    artifacts_dir: str | None = None


class CommitProjectRequest(BaseModel):
    project_dir: str
    committed_contract_dir: str | None = None
    accepted_risks_file: str | None = None
    negotiated_changes_file: str | None = None


class MonitorProjectRequest(BaseModel):
    project_dir: str
    status_inputs_file: str | None = None


def _store_for(project_dir: str | Path) -> tuple[FileSystemCaseStore, str]:
    project_path = Path(project_dir).expanduser().resolve()
    return FileSystemCaseStore(project_path / ".contract_intelligence"), _project_id(project_path)


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/projects/analyze")
def analyze_project(request: AnalyzeProjectRequest) -> dict[str, object]:
    result = run_bid_review(project_dir=request.project_dir, artifacts_dir=request.artifacts_dir)
    return {
        "project_id": result.project_id,
        "artifacts_dir": str(result.artifacts_dir),
        "case_record_path": str(result.case_record_path),
        "run_record_path": str(result.run_record_path),
        "recommendation": result.decision_summary.recommendation.value,
        "overall_risk": result.decision_summary.overall_risk.value,
    }


@app.post("/projects/commit")
def commit_project(request: CommitProjectRequest) -> dict[str, object]:
    try:
        result = commit_contract(
            project_dir=request.project_dir,
            committed_contract_dir=request.committed_contract_dir,
            accepted_risks_file=request.accepted_risks_file,
            negotiated_changes_file=request.negotiated_changes_file,
        )
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    return {
        "project_id": result.project_id,
        "commit_id": result.commit_id,
        "case_record_path": str(result.case_record_path),
        "commit_record_path": str(result.commit_record_path),
        "obligations_path": str(result.obligations_path),
        "obligations_count": result.obligations_count,
    }


@app.post("/projects/monitor")
def monitor_project(request: MonitorProjectRequest) -> dict[str, object]:
    try:
        result = monitor_contract(
            project_dir=request.project_dir,
            status_inputs_file=request.status_inputs_file,
        )
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    return {
        "project_id": result.project_id,
        "run_id": result.run_id,
        "monitoring_run_path": str(result.monitoring_run_path),
        "monitoring_snapshot_path": str(result.monitoring_snapshot_path),
        "alerts_path": str(result.alerts_path),
        "alerts_count": result.alerts_count,
    }


@app.get("/projects/state")
def project_state(project_dir: str = Query(..., description="Absolute or relative path to the project folder")) -> dict[str, object]:
    store, project_id = _store_for(project_dir)
    try:
        return store.load_case_record(project_id).model_dump(mode="json")
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@app.get("/projects/runs/latest")
def latest_run(project_dir: str = Query(..., description="Absolute or relative path to the project folder")) -> dict[str, object]:
    store, project_id = _store_for(project_dir)
    try:
        return store.load_latest_run_record(project_id).model_dump(mode="json")
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@app.get("/projects/commits/latest")
def latest_commit(project_dir: str = Query(..., description="Absolute or relative path to the project folder")) -> dict[str, object]:
    store, project_id = _store_for(project_dir)
    try:
        return store.load_latest_commit_record(project_id).model_dump(mode="json")
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@app.get("/projects/monitoring/latest")
def latest_monitoring(project_dir: str = Query(..., description="Absolute or relative path to the project folder")) -> dict[str, object]:
    store, project_id = _store_for(project_dir)
    try:
        return store.load_latest_monitoring_run(project_id).model_dump(mode="json")
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@app.get("/projects/obligations")
def current_obligations(project_dir: str = Query(..., description="Absolute or relative path to the project folder")) -> list[dict[str, object]]:
    store, project_id = _store_for(project_dir)
    try:
        return [item.model_dump(mode="json") for item in store.load_current_obligations(project_id)]
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@app.get("/projects/alerts")
def current_alerts(project_dir: str = Query(..., description="Absolute or relative path to the project folder")) -> list[dict[str, object]]:
    store, project_id = _store_for(project_dir)
    path = store.case_dir(project_id) / "alerts" / "current.json"
    if not path.exists():
        raise _not_found(f"No current alert snapshot exists for project '{project_id}'.")
    payload = _read_json(path)
    if not isinstance(payload, list):
        raise HTTPException(status_code=500, detail="Alert snapshot is malformed.")
    return [item for item in payload if isinstance(item, dict)]
