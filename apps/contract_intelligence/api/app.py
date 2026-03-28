from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ValidationError

from apps.contract_intelligence.domain.enums import AnalysisPerspective
from apps.contract_intelligence.domain.models import AlertRecord, ReviewActionRecord
from apps.contract_intelligence.monitoring.runner import monitor_contract
from apps.contract_intelligence.orchestration.bid_review_runner import _project_id, run_bid_review
from apps.contract_intelligence.orchestration.commit_runner import commit_contract
from apps.contract_intelligence.paths import (
    resolve_guarded_existing_directory,
    resolve_guarded_existing_file,
    resolve_guarded_optional_existing_directory,
    resolve_guarded_output_directory,
    validate_allowed_roots_configured,
)
from apps.contract_intelligence.storage import FileSystemCaseStore


def _docs_enabled() -> bool:
    return os.getenv("CONTRACT_INTELLIGENCE_EXPOSE_DOCS", "").strip().lower() in {"1", "true", "yes", "on"}


@asynccontextmanager
async def _lifespan(_: FastAPI):
    validate_allowed_roots_configured()
    yield


app = FastAPI(
    title="Contract Intelligence API",
    version="0.1.0",
    lifespan=_lifespan,
    docs_url="/docs" if _docs_enabled() else None,
    redoc_url="/redoc" if _docs_enabled() else None,
    openapi_url="/openapi.json" if _docs_enabled() else None,
)


class AnalyzeProjectRequest(BaseModel):
    project_dir: str
    artifacts_dir: str | None = None
    analysis_perspective: AnalysisPerspective = AnalysisPerspective.VENDOR


class CommitProjectRequest(BaseModel):
    project_dir: str
    committed_contract_dir: str | None = None
    finding_dispositions_file: str | None = None
    accepted_risks_file: str | None = None
    negotiated_changes_file: str | None = None


class MonitorProjectRequest(BaseModel):
    project_dir: str
    status_inputs_file: str | None = None


class ReviewActionUpsertRequest(BaseModel):
    project_dir: str
    kind: str
    ui_id: str
    title: str
    disposition: str
    owner: str = ""
    note: str = ""
    source_run_id: str | None = None
    source_commit_id: str | None = None


class ReviewActionClearRequest(BaseModel):
    project_dir: str
    kind: str
    ui_id: str


def _validated_project_path(project_dir: str | Path) -> Path:
    try:
        project_path = resolve_guarded_existing_directory(project_dir, label="Project directory")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail="Project directory does not exist.") from exc
    except ValueError as exc:
        status = 403 if "outside the configured allowed roots" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return project_path


def _validated_directory(path: str | Path | None, *, label: str) -> str | None:
    if path is None:
        return None
    try:
        resolved = resolve_guarded_optional_existing_directory(path, label=label)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"{label} does not exist.") from exc
    except ValueError as exc:
        status = 403 if "outside the configured allowed roots" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    if resolved is None:
        return None
    return str(resolved)


def _validated_output_dir(path: str | Path | None, *, label: str) -> str | None:
    if path is None:
        return None
    try:
        resolved = resolve_guarded_output_directory(path, label=label)
    except ValueError as exc:
        status = 403 if "outside the configured allowed roots" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return str(resolved)


def _validated_input_file(file_path: str | Path | None, *, label: str) -> str | None:
    if not file_path:
        return None
    path = Path(file_path).expanduser().resolve()
    try:
        return str(resolve_guarded_existing_file(path, label=label))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"{label} does not exist.") from exc
    except ValueError as exc:
        status = 403 if "outside the configured allowed roots" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


def _store_for(project_dir: str | Path) -> tuple[FileSystemCaseStore, str]:
    project_path = _validated_project_path(project_dir)
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
    project_path = _validated_project_path(request.project_dir)
    result = run_bid_review(
        project_dir=project_path,
        artifacts_dir=_validated_output_dir(request.artifacts_dir, label="Artifacts directory"),
        analysis_perspective=request.analysis_perspective,
    )
    return {
        "project_id": result.project_id,
        "analysis_perspective": request.analysis_perspective.value,
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
            project_dir=_validated_project_path(request.project_dir),
            committed_contract_dir=_validated_directory(request.committed_contract_dir, label="Committed contract directory"),
            finding_dispositions_file=_validated_input_file(
                request.finding_dispositions_file,
                label="Finding dispositions file",
            ),
            accepted_risks_file=_validated_input_file(request.accepted_risks_file, label="Accepted risks file"),
            negotiated_changes_file=_validated_input_file(
                request.negotiated_changes_file, label="Negotiated changes file"
            ),
        )
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
            project_dir=_validated_project_path(request.project_dir),
            status_inputs_file=_validated_input_file(request.status_inputs_file, label="Status inputs file"),
        )
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
    try:
        return [AlertRecord.model_validate(item).model_dump(mode="json") for item in payload]
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail="Alert snapshot failed validation.") from exc


@app.get("/projects/review-actions")
def current_review_actions(
    project_dir: str = Query(..., description="Absolute or relative path to the project folder"),
) -> list[dict[str, object]]:
    store, project_id = _store_for(project_dir)
    try:
        return [item.model_dump(mode="json") for item in store.load_current_review_actions(project_id)]
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/projects/review-actions")
def upsert_review_action(request: ReviewActionUpsertRequest) -> dict[str, object]:
    store, project_id = _store_for(request.project_dir)
    now = datetime.now(timezone.utc)
    record = ReviewActionRecord(
        kind=request.kind,
        ui_id=request.ui_id,
        title=request.title,
        disposition=request.disposition,
        owner=request.owner,
        note=request.note,
        source_run_id=request.source_run_id,
        source_commit_id=request.source_commit_id,
        created_at=now,
        updated_at=now,
    )
    persisted = store.persist_review_action(project_id=project_id, review_action=record)
    return persisted.model_dump(mode="json")


@app.post("/projects/review-actions/clear")
def clear_review_action(request: ReviewActionClearRequest) -> dict[str, object]:
    store, project_id = _store_for(request.project_dir)
    cleared = store.clear_review_action(project_id, kind=request.kind, ui_id=request.ui_id)
    if not cleared:
        raise _not_found(
            f"No persisted review action exists for '{request.kind}:{request.ui_id}' in project '{project_id}'."
        )
    return {"project_id": project_id, "kind": request.kind, "ui_id": request.ui_id, "status": "cleared"}
