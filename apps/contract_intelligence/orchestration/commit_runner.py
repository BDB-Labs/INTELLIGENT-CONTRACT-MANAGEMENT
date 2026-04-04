from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from apps.contract_intelligence.domain.models import (
    AcceptedRisk,
    FindingDisposition,
    NegotiatedChange,
    ProjectDocumentRecord,
)
from apps.contract_intelligence.ingestion.document_classifier import (
    REQUIRED_BID_REVIEW_DOCUMENTS,
)
from apps.contract_intelligence.ingestion.project_loader import iter_project_documents
from apps.contract_intelligence.orchestration.bid_review_runner import (
    _extract_obligations,
    compute_project_id,
)
from apps.contract_intelligence.paths import resolve_existing_directory
from apps.contract_intelligence.storage import FileSystemCaseStore
from ese.constants import read_json


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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json_list(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = read_json(Path(path).expanduser().resolve())
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}.")
    invalid_items = [
        index
        for index, item in enumerate(payload, start=1)
        if not isinstance(item, dict)
    ]
    if invalid_items:
        joined = ", ".join(str(item) for item in invalid_items[:5])
        raise ValueError(
            f"Expected object items in {path}; invalid entries at positions {joined}."
        )
    return [item for item in payload if isinstance(item, dict)]


def _validate_json_models(
    items: list[dict[str, Any]], *, model: type, label: str
) -> list[Any]:
    validated: list[Any] = []
    for index, item in enumerate(items, start=1):
        try:
            validated.append(model.model_validate(item))
        except ValidationError as exc:
            raise ValueError(f"{label} item {index} is invalid: {exc}") from exc
    return validated


def _latest_findings_payloads(artifact_paths: dict[str, str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name in (
        "risk_findings.json",
        "insurance_findings.json",
        "compliance_findings.json",
    ):
        path = artifact_paths.get(name)
        if not path:
            continue
        payload = read_json(Path(path))
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


def _finding_dispositions_from_payload(
    findings: list[dict[str, Any]],
    *,
    finding_dispositions_file: str | Path | None,
    accepted_risks_file: str | Path | None,
) -> list[FindingDisposition]:
    indexed = {str(item.get("id", "unknown_finding")): item for item in findings}
    if not indexed:
        return []

    if finding_dispositions_file is not None:
        payload = _load_optional_json_list(finding_dispositions_file)
        dispositions = _validate_json_models(
            payload, model=FindingDisposition, label="Finding dispositions"
        )
        seen: set[str] = set()
        duplicates = [
            item.source_finding_id
            for item in dispositions
            if item.source_finding_id in seen or seen.add(item.source_finding_id)
        ]
        if duplicates:
            joined = ", ".join(duplicates[:5])
            raise ValueError(
                f"Finding dispositions contain duplicate finding ids: {joined}"
            )
        unknown = [
            item.source_finding_id
            for item in dispositions
            if item.source_finding_id not in indexed
        ]
        if unknown:
            joined = ", ".join(unknown[:5])
            raise ValueError(
                f"Finding dispositions reference unknown finding ids: {joined}"
            )
        by_id = {item.source_finding_id: item for item in dispositions}
        generated: list[FindingDisposition] = []
        for finding_id, finding in indexed.items():
            if finding_id in by_id:
                generated.append(by_id[finding_id])
                continue
            generated.append(
                FindingDisposition(
                    source_finding_id=finding_id,
                    role=str(finding.get("role", "unknown_role")),
                    category=str(finding.get("category", "unknown_category")),
                    title=str(finding.get("title", "Unnamed finding")),
                    severity=str(finding.get("severity", "medium")),
                    recommended_action=str(finding.get("recommended_action", "")),
                    disposition="unresolved",
                    rationale="No explicit disposition was provided at commit time.",
                )
            )
        return generated

    if accepted_risks_file is not None:
        accepted = _validate_json_models(
            _load_optional_json_list(accepted_risks_file),
            model=AcceptedRisk,
            label="Accepted risks",
        )
        accepted_by_id = {item.source_finding_id: item for item in accepted}
        unknown = [
            finding_id for finding_id in accepted_by_id if finding_id not in indexed
        ]
        if unknown:
            joined = ", ".join(unknown[:5])
            raise ValueError(f"Accepted risks reference unknown finding ids: {joined}")
        return [
            FindingDisposition(
                source_finding_id=finding_id,
                role=str(finding.get("role", "unknown_role")),
                category=str(finding.get("category", "unknown_category")),
                title=str(finding.get("title", "Unnamed finding")),
                severity=str(finding.get("severity", "medium")),
                recommended_action=str(finding.get("recommended_action", "")),
                disposition="accepted"
                if finding_id in accepted_by_id
                else "unresolved",
                rationale=(
                    accepted_by_id[finding_id].carry_forward_reason
                    if finding_id in accepted_by_id
                    else "No explicit disposition was provided at commit time."
                ),
            )
            for finding_id, finding in indexed.items()
        ]

    return [
        FindingDisposition(
            source_finding_id=finding_id,
            role=str(finding.get("role", "unknown_role")),
            category=str(finding.get("category", "unknown_category")),
            title=str(finding.get("title", "Unnamed finding")),
            severity=str(finding.get("severity", "medium")),
            recommended_action=str(finding.get("recommended_action", "")),
            disposition="unresolved",
            rationale="No explicit disposition was provided at commit time.",
        )
        for finding_id, finding in indexed.items()
    ]


def _accepted_risks_from_dispositions(
    dispositions: list[FindingDisposition],
) -> list[AcceptedRisk]:
    accepted: list[AcceptedRisk] = []
    for item in dispositions:
        if item.disposition != "accepted":
            continue
        accepted.append(
            AcceptedRisk(
                source_finding_id=item.source_finding_id,
                role=item.role,
                category=item.category,
                title=item.title,
                severity=item.severity,
                recommended_action=item.recommended_action,
                carry_forward_reason=item.rationale
                or "Explicitly accepted during contract commit.",
            )
        )
    return accepted


def _validate_commit_dispositions(dispositions: list[FindingDisposition]) -> None:
    unresolved_blockers = [
        item.title
        for item in dispositions
        if item.disposition == "unresolved"
        and item.severity.value in {"high", "critical"}
    ]
    if unresolved_blockers:
        joined = ", ".join(unresolved_blockers[:5])
        raise ValueError(
            "Cannot commit while HIGH/CRITICAL findings remain unresolved. "
            f"Resolve, price, negotiate, or explicitly accept: {joined}"
        )


def _committed_document_inventory(project_dir: Path) -> list[ProjectDocumentRecord]:
    inventory: list[ProjectDocumentRecord] = []
    for document in iter_project_documents(project_dir):
        inventory.append(
            ProjectDocumentRecord(
                document_id=document.document_id,
                filename=document.relative_path,
                document_type=document.document_type.value,
                required_for_bid_review=document.document_type
                in REQUIRED_BID_REVIEW_DOCUMENTS,
                text_available=document.text_available,
                text_source=document.text_source,
                text_quality=document.text_quality,
                clause_count=len(document.clauses),
            )
        )
    return inventory


def commit_contract(
    project_dir: str | Path,
    *,
    committed_contract_dir: str | Path | None = None,
    finding_dispositions_file: str | Path | None = None,
    accepted_risks_file: str | Path | None = None,
    negotiated_changes_file: str | Path | None = None,
) -> CommitContractResult:
    project_path = resolve_existing_directory(project_dir, label="Project directory")
    committed_path = resolve_existing_directory(
        committed_contract_dir if committed_contract_dir is not None else project_path,
        label="Committed contract directory",
    )
    project_id = compute_project_id(project_path)
    store = FileSystemCaseStore(project_path / ".contract_intelligence")

    latest_run = store.load_latest_run_record(project_id)
    documents = iter_project_documents(committed_path)
    if not documents:
        raise FileNotFoundError(
            f"Committed contract directory does not contain any files: {committed_path}"
        )
    if not any(document.text_available for document in documents):
        raise ValueError(
            f"Committed contract directory does not contain any readable contract text: {committed_path}"
        )
    obligations = _extract_obligations(documents)

    finding_dispositions = _finding_dispositions_from_payload(
        _latest_findings_payloads(latest_run.artifact_paths),
        finding_dispositions_file=finding_dispositions_file,
        accepted_risks_file=accepted_risks_file,
    )
    _validate_commit_dispositions(finding_dispositions)
    accepted_risks = _accepted_risks_from_dispositions(finding_dispositions)

    negotiated_change_payload = _load_optional_json_list(negotiated_changes_file)
    negotiated_changes = _validate_json_models(
        negotiated_change_payload,
        model=NegotiatedChange,
        label="Negotiated changes",
    )

    persisted = store.persist_contract_commit(
        project_id=project_id,
        analysis_perspective=latest_run.analysis_perspective,
        source_project_dir=project_path,
        committed_contract_dir=committed_path,
        source_run_id=latest_run.run_id,
        decision_summary=latest_run.decision_summary,
        procurement_profile=latest_run.procurement_profile,
        outcome_status=latest_run.outcome_evidence.outcome_status,
        finding_dispositions=finding_dispositions,
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
    project_path = resolve_existing_directory(project_dir, label="Project directory")
    project_id = compute_project_id(project_path)
    store = FileSystemCaseStore(project_path / ".contract_intelligence")
    obligations = store.load_current_obligations(project_id)
    current_path = store.case_dir(project_id) / "obligations" / "current.json"

    if output_path is not None:
        destination = Path(output_path).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps([item.model_dump(mode="json") for item in obligations], indent=2)
            + "\n",
            encoding="utf-8",
        )
        current_path = destination

    return ObligationSnapshotResult(
        project_id=project_id,
        obligations_path=current_path,
        obligations_count=len(obligations),
    )
