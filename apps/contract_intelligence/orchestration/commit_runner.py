from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.contract_intelligence.domain.models import (
    AcceptedRisk,
    NegotiatedChange,
    Obligation,
    ProjectDocumentRecord,
)
from apps.contract_intelligence.ingestion.document_classifier import REQUIRED_BID_REVIEW_DOCUMENTS
from apps.contract_intelligence.ingestion.project_loader import iter_project_documents
from apps.contract_intelligence.orchestration.bid_review_runner import _extract_obligations, _project_id
from apps.contract_intelligence.storage import FileSystemCaseStore


@dataclass(frozen=True)
class CommitContractResult:
    project_id: str
    commit_id: str
    case_record_path: Path
    commit_record_path: Path
    obligations_path: Path
    obligations_count: int


@dataclass(frozen=True)
class ObligationSnapshotResult:
    project_id: str
    obligations_path: Path
    obligations_count: int


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json_list(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = _read_json(Path(path).expanduser().resolve())
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}.")
    return [item for item in payload if isinstance(item, dict)]


def _latest_findings_payloads(artifact_paths: dict[str, str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name in ("risk_findings.json", "insurance_findings.json", "compliance_findings.json"):
        path = artifact_paths.get(name)
        if not path:
            continue
        payload = _read_json(Path(path))
        if isinstance(payload, list):
            findings.extend(item for item in payload if isinstance(item, dict))
    return findings


def _default_accepted_risks(artifact_paths: dict[str, str]) -> list[AcceptedRisk]:
    accepted: list[AcceptedRisk] = []
    for finding in _latest_findings_payloads(artifact_paths):
        accepted.append(
            AcceptedRisk(
                source_finding_id=str(finding.get("id", "unknown_finding")),
                role=str(finding.get("role", "unknown_role")),
                category=str(finding.get("category", "unknown_category")),
                title=str(finding.get("title", "Unnamed finding")),
                severity=str(finding.get("severity", "medium")),
                recommended_action=str(finding.get("recommended_action", "")),
                carry_forward_reason=(
                    "Carried forward from the latest bid-review run as part of the committed contract baseline."
                ),
            )
        )
    return accepted


def _committed_document_inventory(project_dir: Path) -> list[ProjectDocumentRecord]:
    inventory: list[ProjectDocumentRecord] = []
    for document in iter_project_documents(project_dir):
        inventory.append(
            ProjectDocumentRecord(
                document_id=document.document_id,
                filename=document.relative_path,
                document_type=document.document_type.value,
                required_for_bid_review=document.document_type in REQUIRED_BID_REVIEW_DOCUMENTS,
                text_available=document.text_available,
                text_source=document.text_source,
                clause_count=len(document.clauses),
            )
        )
    return inventory


def commit_contract(
    project_dir: str | Path,
    *,
    committed_contract_dir: str | Path | None = None,
    accepted_risks_file: str | Path | None = None,
    negotiated_changes_file: str | Path | None = None,
) -> CommitContractResult:
    project_path = Path(project_dir).expanduser().resolve()
    committed_path = Path(committed_contract_dir).expanduser().resolve() if committed_contract_dir else project_path
    project_id = _project_id(project_path)
    store = FileSystemCaseStore(project_path / ".contract_intelligence")

    latest_run = store.load_latest_run_record(project_id)
    documents = iter_project_documents(committed_path)
    obligations = _extract_obligations(documents)

    accepted_risk_payload = _load_optional_json_list(accepted_risks_file)
    accepted_risks = (
        [AcceptedRisk.model_validate(item) for item in accepted_risk_payload]
        if accepted_risk_payload
        else _default_accepted_risks(latest_run.artifact_paths)
    )

    negotiated_change_payload = _load_optional_json_list(negotiated_changes_file)
    negotiated_changes = [NegotiatedChange.model_validate(item) for item in negotiated_change_payload]

    persisted = store.persist_contract_commit(
        project_id=project_id,
        source_project_dir=project_path,
        committed_contract_dir=committed_path,
        source_run_id=latest_run.run_id,
        decision_summary=latest_run.decision_summary,
        procurement_profile=latest_run.procurement_profile,
        outcome_status=latest_run.outcome_evidence.outcome_status,
        accepted_risks=accepted_risks,
        negotiated_changes=negotiated_changes,
        committed_documents=_committed_document_inventory(committed_path),
        obligations=obligations,
    )

    return CommitContractResult(
        project_id=project_id,
        commit_id=persisted.commit_id,
        case_record_path=persisted.case_record_path,
        commit_record_path=persisted.commit_record_path,
        obligations_path=persisted.obligations_path,
        obligations_count=len(obligations),
    )


def load_committed_obligations(
    project_dir: str | Path,
    *,
    output_path: str | Path | None = None,
) -> ObligationSnapshotResult:
    project_path = Path(project_dir).expanduser().resolve()
    project_id = _project_id(project_path)
    store = FileSystemCaseStore(project_path / ".contract_intelligence")
    obligations = store.load_current_obligations(project_id)
    current_path = store.case_dir(project_id) / "obligations" / "current.json"

    if output_path is not None:
        destination = Path(output_path).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps([item.model_dump(mode="json") for item in obligations], indent=2) + "\n",
            encoding="utf-8",
        )
        current_path = destination

    return ObligationSnapshotResult(
        project_id=project_id,
        obligations_path=current_path,
        obligations_count=len(obligations),
    )
