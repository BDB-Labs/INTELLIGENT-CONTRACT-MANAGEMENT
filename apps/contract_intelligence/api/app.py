from __future__ import annotations

from contextlib import asynccontextmanager
import base64
import logging
import os
import secrets
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, ValidationError

from apps.contract_intelligence.demo import (
    build_demo_assets,
    default_demo_site_dir,
    default_reference_root,
)
from apps.contract_intelligence.domain.enums import AnalysisPerspective
from apps.contract_intelligence.domain.models import AlertRecord, ReviewActionRecord
from apps.contract_intelligence.evaluation.corpus import (
    default_corpus_dir,
    evaluate_corpus,
)
from apps.contract_intelligence.monitoring.runner import monitor_contract
from apps.contract_intelligence.orchestration.bid_review_runner import (
    compute_project_id,
    run_bid_review,
)
from apps.contract_intelligence.orchestration.commit_runner import (
    commit_contract,
    load_committed_obligations,
)
from apps.contract_intelligence.orchestration.ese_bridge import run_bid_review_with_ese
from apps.contract_intelligence.paths import (
    resolve_guarded_existing_directory,
    resolve_guarded_existing_file,
    resolve_guarded_optional_existing_directory,
    resolve_guarded_output_directory,
    resolve_guarded_output_file,
    validate_allowed_roots_configured,
)
from apps.contract_intelligence.storage import FileSystemCaseStore
from apps.contract_intelligence.ui import render_project_dashboard
from apps.contract_intelligence.ui.workbench import render_workbench_html
from ese.constants import read_json
from ese.logging_config import configure_logging

logger = logging.getLogger(__name__)


def _docs_enabled() -> bool:
    return os.getenv("CONTRACT_INTELLIGENCE_EXPOSE_DOCS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _reference_auth_credentials() -> tuple[str, str] | None:
    user = os.getenv("ICM_REFERENCE_AUTH_USER", "").strip()
    password = os.getenv("ICM_REFERENCE_AUTH_PASSWORD", "").strip()
    if user and password:
        return user, password
    return None


def _unauthorized() -> Response:
    return Response(
        content="Authentication required.",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="ICM Reference"'},
    )


def _authenticated(request: Request) -> bool:
    credentials = _reference_auth_credentials()
    if credentials is None:
        return True
    if request.url.path == "/health":
        return True
    header = request.headers.get("authorization", "")
    if not header.startswith("Basic "):
        return False
    token = header[6:].strip()
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    username, separator, password = decoded.partition(":")
    if not separator:
        return False
    expected_user, expected_password = credentials
    return secrets.compare_digest(username, expected_user) and secrets.compare_digest(
        password, expected_password
    )

_logging_configured = False
_logging_lock = threading.Lock()


def _configure_logging_once() -> None:
    global _logging_configured
    if _logging_configured:
        return
    with _logging_lock:
        if _logging_configured:
            return
        configure_logging(
            level=os.getenv("LOG_LEVEL", "INFO"),
            json_format=os.getenv("JSON_LOGGING", "").lower() in {"1", "true", "yes"},
        )
        _logging_configured = True


@asynccontextmanager
async def _lifespan(_: FastAPI):
    _configure_logging_once()
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


def serve_contract_intelligence_api(*, host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level=os.getenv("LOG_LEVEL", "info").lower())


@app.middleware("http")
async def _reference_auth_middleware(request: Request, call_next):
    if not _authenticated(request):
        return _unauthorized()
    return await call_next(request)


class AnalyzeProjectRequest(BaseModel):
    project_dir: str
    artifacts_dir: str | None = None
    analysis_perspective: AnalysisPerspective = AnalysisPerspective.VENDOR
    async_mode: bool = False


class CommitProjectRequest(BaseModel):
    project_dir: str
    committed_contract_dir: str | None = None
    finding_dispositions_file: str | None = None
    accepted_risks_file: str | None = None
    negotiated_changes_file: str | None = None
    async_mode: bool = False


class MonitorProjectRequest(BaseModel):
    project_dir: str
    status_inputs_file: str | None = None
    async_mode: bool = False


class EnsembleAnalyzeProjectRequest(BaseModel):
    project_dir: str
    provider: str = "local"
    execution_mode: str = "demo"
    artifacts_dir: str | None = "artifacts/contract_intelligence_ese"
    model: str | None = None
    runtime_adapter: str | None = None
    provider_name: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    analysis_perspective: AnalysisPerspective = AnalysisPerspective.VENDOR
    fail_on_high: bool = False
    write_config_path: str | None = None


class ExtractObligationsRequest(BaseModel):
    project_dir: str
    output_path: str | None = None


class RenderDashboardRequest(BaseModel):
    project_dir: str
    mode: str = "internal"
    output_path: str | None = None


class EvaluateCorpusRequest(BaseModel):
    corpus_dir: str = str(default_corpus_dir())
    artifacts_dir: str | None = None


class BuildDemoRequest(BaseModel):
    corpus_dir: str = str(default_corpus_dir())
    reference_root: str = str(default_reference_root())
    site_dir: str = str(default_demo_site_dir())


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
        project_path = resolve_guarded_existing_directory(
            project_dir, label="Project directory"
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400, detail="Project directory does not exist."
        ) from exc
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


def _validated_output_file(path: str | Path | None, *, label: str) -> str | None:
    if path is None:
        return None
    try:
        resolved = resolve_guarded_output_file(path, label=label)
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


def _validated_existing_directory(path: str | Path, *, label: str) -> str:
    try:
        resolved = resolve_guarded_existing_directory(path, label=label)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"{label} does not exist.") from exc
    except ValueError as exc:
        status = 403 if "outside the configured allowed roots" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return str(resolved)


def _store_for(project_dir: str | Path) -> tuple[FileSystemCaseStore, str]:
    project_path = _validated_project_path(project_dir)
    return FileSystemCaseStore(
        project_path / ".contract_intelligence"
    ), compute_project_id(project_path)


def _not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _reference_site_root() -> Path:
    explicit = os.getenv("CONTRACT_INTELLIGENCE_REFERENCE_SITE_DIR", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    reference_root = os.getenv("CONTRACT_INTELLIGENCE_REFERENCE_ROOT", "").strip()
    if reference_root:
        return Path(reference_root).expanduser().resolve() / "site"
    return _repo_root() / "demo_site" / "generated"


def _reference_manifest_path() -> Path:
    return _reference_site_root() / "manifest.json"


def _load_reference_manifest() -> dict[str, object]:
    path = _reference_manifest_path()
    if not path.exists():
        raise _not_found(
            "Reference manifest is not available. Build demo assets first with "
            "`uv run python -m apps.contract_intelligence build-demo`."
        )
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="Reference manifest is malformed.")
    return payload


def _reference_landing_html() -> str:
    try:
        manifest = _load_reference_manifest()
        cases = manifest.get("cases", [])
    except HTTPException:
        cases = []

    cards = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        cards.append(
            """
            <article class="case-card">
              <div class="case-head">
                <h2>{title}</h2>
                <span class="badge">{recommendation}</span>
              </div>
              <p class="risk">Overall risk: <strong>{overall_risk}</strong></p>
              <p class="meta">{findings_count} findings · {obligations_count} obligations · {alerts_count} alerts</p>
              <ul>{highlights}</ul>
              <a class="button" href="/reference/cases/{case_id}/dashboard">Open dashboard</a>
            </article>
            """.format(
                title=str(item.get("title", item.get("case_id", "Reference case"))),
                recommendation=str(item.get("recommendation", "unknown")),
                overall_risk=str(item.get("overall_risk", "unknown")),
                findings_count=str(item.get("findings_count", 0)),
                obligations_count=str(item.get("obligations_count", 0)),
                alerts_count=str(item.get("alerts_count", 0)),
                case_id=str(item.get("case_id", "")),
                highlights="".join(
                    f"<li>{str(highlight)}</li>"
                    for highlight in item.get("highlights", [])
                )
                or "<li>Prepared reference lifecycle snapshot.</li>",
            )
        )

    if not cards:
        cards_markup = (
            "<article class='empty-state'><p>No reference cases are available yet. "
            "Run <code>uv run python -m apps.contract_intelligence build-demo</code> "
            "to generate the demo corpus snapshots.</p></article>"
        )
    else:
        cards_markup = "".join(cards)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ICM Reference Implementation</title>
  <style>
    :root {{
      --ink: #112335;
      --muted: #5b6774;
      --bg: #f7f2ea;
      --paper: rgba(255, 255, 255, 0.92);
      --accent: #0f7662;
      --accent-2: #c96b2c;
      --line: rgba(17, 35, 53, 0.12);
      --shadow: 0 22px 55px rgba(17, 35, 53, 0.12);
      --radius: 22px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 0% 0%, rgba(201, 107, 44, 0.14), transparent 28%),
        radial-gradient(circle at 100% 20%, rgba(15, 118, 98, 0.16), transparent 30%),
        linear-gradient(180deg, #fcfaf6, var(--bg));
    }}
    main {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 40px 24px 72px;
    }}
    .hero {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 32px;
      padding: 36px;
      box-shadow: var(--shadow);
      margin-bottom: 28px;
    }}
    .eyebrow {{
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--accent);
      font-size: 0.78rem;
      margin: 0 0 12px;
      font-weight: 700;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(2rem, 4vw, 3.5rem);
      line-height: 1;
    }}
    .lead {{
      max-width: 780px;
      color: var(--muted);
      font-size: 1.05rem;
      line-height: 1.6;
      margin: 18px 0 0;
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 24px;
    }}
    .links a, .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 12px 18px;
      border-radius: 999px;
      text-decoration: none;
      font-weight: 700;
      border: 1px solid transparent;
    }}
    .links a.primary, .button {{
      background: var(--ink);
      color: white;
    }}
    .links a.secondary {{
      border-color: var(--line);
      color: var(--ink);
      background: rgba(255, 255, 255, 0.65);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 18px;
    }}
    .case-card, .empty-state {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 22px;
      box-shadow: var(--shadow);
    }}
    .case-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
    }}
    .case-head h2 {{
      margin: 0;
      font-size: 1.1rem;
    }}
    .badge {{
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 0.76rem;
      font-weight: 700;
      color: white;
      background: linear-gradient(135deg, var(--accent), #164e63);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .risk, .meta {{
      color: var(--muted);
      margin: 12px 0 0;
    }}
    ul {{
      padding-left: 18px;
      color: var(--muted);
      line-height: 1.5;
    }}
    code {{
      background: rgba(17, 35, 53, 0.06);
      padding: 2px 6px;
      border-radius: 6px;
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <p class="eyebrow">Reference Implementation</p>
      <h1>ICM on Render</h1>
      <p class="lead">
        This service hosts the reference implementation of the contract-intelligence runtime.
        It exposes the real FastAPI lifecycle surface and also serves curated reference cases
        built from the shipped public-infrastructure corpus.
      </p>
      <div class="links">
        <a class="primary" href="/reference/manifest">Reference manifest</a>
        <a class="secondary" href="/health">Health</a>
      </div>
    </section>
    <section class="grid">
      {cards_markup}
    </section>
  </main>
</body>
</html>"""


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/health/ready")
def readiness() -> dict[str, object]:
    """Enhanced readiness check that verifies dependencies."""
    checks = {
        "allowed_roots": "ok",
        "storage": "ok",
    }
    try:
        validate_allowed_roots_configured()
    except ValueError as e:
        checks["allowed_roots"] = f"error: {e}"

    storage_root = os.getenv("CONTRACT_INTELLIGENCE_STORAGE_ROOT", "").strip()
    if storage_root:
        try:
            root_path = Path(storage_root).expanduser().resolve()
            if not root_path.exists():
                checks["storage"] = "warning: storage root does not exist"
            elif not os.access(root_path, os.W_OK):
                checks["storage"] = "error: storage root not writable"
        except (OSError, PermissionError) as e:
            checks["storage"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if all_ok else "not_ready",
        "checks": checks,
    }


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return _reference_landing_html()


@app.get("/workbench", response_class=HTMLResponse)
def workbench() -> str:
    return render_workbench_html()


@app.get("/reference", response_class=HTMLResponse)
def reference_home() -> str:
    return _reference_landing_html()


@app.get("/reference/manifest")
def reference_manifest() -> dict[str, object]:
    return _load_reference_manifest()


@app.get("/reference/cases/{case_id}/dashboard")
def reference_case_dashboard(case_id: str) -> FileResponse:
    target = _reference_site_root() / "cases" / case_id / "dashboard.html"
    if not target.exists():
        raise _not_found(f"No reference dashboard exists for case '{case_id}'.")
    return FileResponse(target, media_type="text/html")


@app.post("/evaluation/corpus")
def evaluate_corpus_cases(request: EvaluateCorpusRequest) -> dict[str, object]:
    results = evaluate_corpus(
        corpus_dir=_validated_existing_directory(request.corpus_dir, label="Corpus directory"),
        artifacts_root=_validated_output_dir(request.artifacts_dir, label="Artifacts directory"),
    )
    passed_cases = sum(1 for item in results if item.passed)
    return {
        "corpus_dir": str(request.corpus_dir),
        "passed_cases": passed_cases,
        "total_cases": len(results),
        "results": [
            {
                "case_id": item.case_id,
                "passed": item.passed,
                "failures": list(item.failures),
                "artifacts_dir": str(item.artifacts_dir),
            }
            for item in results
        ],
    }


@app.post("/reference/build-demo")
def build_reference_demo(request: BuildDemoRequest) -> dict[str, object]:
    result = build_demo_assets(
        corpus_dir=_validated_existing_directory(request.corpus_dir, label="Corpus directory"),
        reference_root=_validated_output_dir(request.reference_root, label="Reference root")
        or request.reference_root,
        site_dir=_validated_output_dir(request.site_dir, label="Site directory")
        or request.site_dir,
    )
    return {
        "generated_at": result.generated_at,
        "reference_root": str(result.reference_root),
        "site_dir": str(result.site_dir),
        "manifest_path": str(result.manifest_path),
        "cases": [
            {
                "case_id": case.case_id,
                "title": case.title,
                "dashboard_path": str(case.dashboard_path),
                "project_id": case.project_id,
                "recommendation": case.recommendation,
                "overall_risk": case.overall_risk,
                "analysis_perspective": case.analysis_perspective,
                "findings_count": case.findings_count,
                "obligations_count": case.obligations_count,
                "alerts_count": case.alerts_count,
                "documents_count": case.documents_count,
                "highlights": list(case.highlights),
            }
            for case in result.cases
        ],
    }


def _background_analyze(
    project_dir: str,
    artifacts_dir: str | None,
    analysis_perspective: str,
    job_id: str,
) -> None:
    try:
        result = run_bid_review(
            project_dir=project_dir,
            artifacts_dir=artifacts_dir,
            analysis_perspective=AnalysisPerspective(analysis_perspective),
        )
        logger.info(
            "Background analyze completed",
            extra={
                "job_id": job_id,
                "project_id": result.project_id,
                "recommendation": result.decision_summary.recommendation.value,
            },
        )
    except Exception:
        logger.exception("Background analyze failed", extra={"job_id": job_id})


@app.post("/projects/analyze")
def analyze_project(
    request: AnalyzeProjectRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, object]:
    project_path = _validated_project_path(request.project_dir)
    artifacts_dir = _validated_output_dir(
        request.artifacts_dir, label="Artifacts directory"
    )

    if request.async_mode:
        job_id = uuid.uuid4().hex[:12]
        background_tasks.add_task(
            _background_analyze,
            project_dir=str(project_path),
            artifacts_dir=str(artifacts_dir) if artifacts_dir else None,
            analysis_perspective=request.analysis_perspective.value,
            job_id=job_id,
        )
        return {
            "job_id": job_id,
            "status": "accepted",
            "message": "Analysis started in background",
        }

    result = run_bid_review(
        project_dir=project_path,
        artifacts_dir=artifacts_dir,
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


@app.post("/projects/ensemble-review")
def ensemble_review_project(request: EnsembleAnalyzeProjectRequest) -> dict[str, object]:
    project_path = _validated_project_path(request.project_dir)
    artifacts_dir = _validated_output_dir(
        request.artifacts_dir,
        label="Artifacts directory",
    )
    write_config_path = _validated_output_file(
        request.write_config_path,
        label="Config output path",
    )

    try:
        cfg, summary_path = run_bid_review_with_ese(
            project_dir=project_path,
            provider=request.provider,
            execution_mode=request.execution_mode,
            artifacts_dir=artifacts_dir or "artifacts/contract_intelligence_ese",
            model=request.model,
            api_key_env=request.api_key_env,
            runtime_adapter=request.runtime_adapter,
            provider_name=request.provider_name,
            base_url=request.base_url,
            fail_on_high=request.fail_on_high,
            analysis_perspective=request.analysis_perspective,
            config_path=write_config_path,
        )
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    runtime = dict(cfg.get("provider_runtime") or {})
    return {
        "project_id": compute_project_id(project_path),
        "analysis_perspective": request.analysis_perspective.value,
        "summary_path": str(summary_path),
        "artifacts_dir": str((cfg.get("output") or {}).get("artifacts_dir") or ""),
        "config_path": write_config_path,
        "runtime_adapter": str((cfg.get("runtime") or {}).get("adapter") or ""),
        "provider_runtime": runtime,
    }


def _background_commit(
    project_dir: str,
    committed_contract_dir: str | None,
    finding_dispositions_file: str | None,
    accepted_risks_file: str | None,
    negotiated_changes_file: str | None,
    job_id: str,
) -> None:
    try:
        result = commit_contract(
            project_dir=project_dir,
            committed_contract_dir=committed_contract_dir,
            finding_dispositions_file=finding_dispositions_file,
            accepted_risks_file=accepted_risks_file,
            negotiated_changes_file=negotiated_changes_file,
        )
        logger.info(
            "Background commit completed",
            extra={
                "job_id": job_id,
                "project_id": result.project_id,
                "commit_id": result.commit_id,
            },
        )
    except Exception:
        logger.exception("Background commit failed", extra={"job_id": job_id})


@app.post("/projects/commit")
def commit_project(
    request: CommitProjectRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, object]:
    if request.async_mode:
        job_id = uuid.uuid4().hex[:12]
        background_tasks.add_task(
            _background_commit,
            project_dir=str(_validated_project_path(request.project_dir)),
            committed_contract_dir=_validated_directory(
                request.committed_contract_dir, label="Committed contract directory"
            ),
            finding_dispositions_file=_validated_input_file(
                request.finding_dispositions_file, label="Finding dispositions file"
            ),
            accepted_risks_file=_validated_input_file(
                request.accepted_risks_file, label="Accepted risks file"
            ),
            negotiated_changes_file=_validated_input_file(
                request.negotiated_changes_file, label="Negotiated changes file"
            ),
            job_id=job_id,
        )
        return {
            "job_id": job_id,
            "status": "accepted",
            "message": "Commit started in background",
        }

    try:
        result = commit_contract(
            project_dir=_validated_project_path(request.project_dir),
            committed_contract_dir=_validated_directory(
                request.committed_contract_dir, label="Committed contract directory"
            ),
            finding_dispositions_file=_validated_input_file(
                request.finding_dispositions_file,
                label="Finding dispositions file",
            ),
            accepted_risks_file=_validated_input_file(
                request.accepted_risks_file, label="Accepted risks file"
            ),
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


def _background_monitor(
    project_dir: str,
    status_inputs_file: str | None,
    job_id: str,
) -> None:
    try:
        result = monitor_contract(
            project_dir=project_dir,
            status_inputs_file=status_inputs_file,
        )
        logger.info(
            "Background monitor completed",
            extra={
                "job_id": job_id,
                "project_id": result.project_id,
                "alerts_count": result.alerts_count,
            },
        )
    except Exception:
        logger.exception("Background monitor failed", extra={"job_id": job_id})


@app.post("/projects/monitor")
def monitor_project(
    request: MonitorProjectRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, object]:
    if request.async_mode:
        job_id = uuid.uuid4().hex[:12]
        background_tasks.add_task(
            _background_monitor,
            project_dir=str(_validated_project_path(request.project_dir)),
            status_inputs_file=_validated_input_file(
                request.status_inputs_file, label="Status inputs file"
            ),
            job_id=job_id,
        )
        return {
            "job_id": job_id,
            "status": "accepted",
            "message": "Monitor started in background",
        }

    try:
        result = monitor_contract(
            project_dir=_validated_project_path(request.project_dir),
            status_inputs_file=_validated_input_file(
                request.status_inputs_file, label="Status inputs file"
            ),
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


@app.post("/projects/extract-obligations")
def extract_obligations(request: ExtractObligationsRequest) -> dict[str, object]:
    try:
        result = load_committed_obligations(
            project_dir=_validated_project_path(request.project_dir),
            output_path=_validated_output_file(request.output_path, label="Output path"),
        )
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "project_id": result.project_id,
        "obligations_path": str(result.obligations_path),
        "obligations_count": result.obligations_count,
    }


@app.post("/projects/render-dashboard")
def render_dashboard(request: RenderDashboardRequest) -> dict[str, object]:
    project_path = _validated_project_path(request.project_dir)
    try:
        dashboard_path = render_project_dashboard(
            project_dir=project_path,
            output_path=_validated_output_file(request.output_path, label="Output path"),
            report_mode=request.mode,
        )
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    view_href = "/projects/dashboard/view?" + urlencode(
        {"project_dir": str(project_path), "mode": request.mode}
    )
    return {
        "project_id": compute_project_id(project_path),
        "report_mode": "external" if str(request.mode).lower() == "external" else "internal",
        "dashboard_path": str(dashboard_path),
        "view_href": view_href,
    }


@app.get("/projects/dashboard/view")
def view_project_dashboard(
    project_dir: str = Query(..., description="Absolute or relative path to the project folder"),
    mode: str = Query("internal", description="internal or external dashboard output"),
) -> FileResponse:
    project_path = _validated_project_path(project_dir)
    try:
        dashboard_path = render_project_dashboard(project_dir=project_path, report_mode=mode)
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(dashboard_path, media_type="text/html")


@app.get("/projects/state")
def project_state(
    project_dir: str = Query(
        ..., description="Absolute or relative path to the project folder"
    ),
) -> dict[str, object]:
    store, project_id = _store_for(project_dir)
    try:
        return store.load_case_record(project_id).model_dump(mode="json")
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@app.get("/projects/runs/latest")
def latest_run(
    project_dir: str = Query(
        ..., description="Absolute or relative path to the project folder"
    ),
) -> dict[str, object]:
    store, project_id = _store_for(project_dir)
    try:
        return store.load_latest_run_record(project_id).model_dump(mode="json")
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@app.get("/projects/commits/latest")
def latest_commit(
    project_dir: str = Query(
        ..., description="Absolute or relative path to the project folder"
    ),
) -> dict[str, object]:
    store, project_id = _store_for(project_dir)
    try:
        return store.load_latest_commit_record(project_id).model_dump(mode="json")
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@app.get("/projects/monitoring/latest")
def latest_monitoring(
    project_dir: str = Query(
        ..., description="Absolute or relative path to the project folder"
    ),
) -> dict[str, object]:
    store, project_id = _store_for(project_dir)
    try:
        return store.load_latest_monitoring_run(project_id).model_dump(mode="json")
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@app.get("/projects/obligations")
def current_obligations(
    project_dir: str = Query(
        ..., description="Absolute or relative path to the project folder"
    ),
) -> list[dict[str, object]]:
    store, project_id = _store_for(project_dir)
    try:
        return [
            item.model_dump(mode="json")
            for item in store.load_current_obligations(project_id)
        ]
    except FileNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@app.get("/projects/alerts")
def current_alerts(
    project_dir: str = Query(
        ..., description="Absolute or relative path to the project folder"
    ),
) -> list[dict[str, object]]:
    store, project_id = _store_for(project_dir)
    path = store.case_dir(project_id) / "alerts" / "current.json"
    if not path.exists():
        raise _not_found(
            f"No current alert snapshot exists for project '{project_id}'."
        )
    payload = read_json(path)
    if not isinstance(payload, list):
        raise HTTPException(status_code=500, detail="Alert snapshot is malformed.")
    try:
        return [
            AlertRecord.model_validate(item).model_dump(mode="json") for item in payload
        ]
    except ValidationError as exc:
        raise HTTPException(
            status_code=500, detail="Alert snapshot failed validation."
        ) from exc


@app.get("/projects/review-actions")
def current_review_actions(
    project_dir: str = Query(
        ..., description="Absolute or relative path to the project folder"
    ),
) -> list[dict[str, object]]:
    store, project_id = _store_for(project_dir)
    try:
        return [
            item.model_dump(mode="json")
            for item in store.load_current_review_actions(project_id)
        ]
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
    cleared = store.clear_review_action(
        project_id, kind=request.kind, ui_id=request.ui_id
    )
    if not cleared:
        raise _not_found(
            f"No persisted review action exists for '{request.kind}:{request.ui_id}' in project '{project_id}'."
        )
    return {
        "project_id": project_id,
        "kind": request.kind,
        "ui_id": request.ui_id,
        "status": "cleared",
    }
