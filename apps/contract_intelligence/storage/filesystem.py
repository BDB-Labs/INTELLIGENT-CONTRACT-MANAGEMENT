from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

logger = logging.getLogger(__name__)

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

from apps.contract_intelligence.domain.models import (
    AcceptedRisk,
    AlertRecord,
    BidReviewRunRecord,
    CaseRecord,
    ContractCommitIndexEntry,
    ContractCommitRecord,
    ContextProfile,
    CaseRunIndexEntry,
    DecisionSummary,
    FindingDisposition,
    MonitoredObligation,
    MonitoringRunIndexEntry,
    MonitoringRunRecord,
    NegotiatedChange,
    Obligation,
    OutcomeEvidenceBundle,
    ProjectDocumentRecord,
    ProcurementProfile,
    ReviewActionEvent,
    ReviewActionRecord,
)
from ese.constants import read_json


@dataclass(frozen=True)
class PersistedCaseState:
    storage_root: Path
    case_dir: Path
    case_record_path: Path
    run_record_path: Path
    run_id: str


@dataclass(frozen=True)
class PersistedCommitState:
    storage_root: Path
    case_dir: Path
    case_record_path: Path
    commit_record_path: Path
    obligations_path: Path
    commit_id: str


@dataclass(frozen=True)
class PersistedMonitoringState:
    storage_root: Path
    case_dir: Path
    case_record_path: Path
    monitoring_run_path: Path
    alerts_path: Path
    monitoring_snapshot_path: Path
    run_id: str


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2) + "\n"
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
        temp_name = handle.name
    os.replace(temp_name, path)


class FileSystemCaseStore:
    """Persist contract-intelligence runs in a lightweight filesystem case store."""

    def __init__(self, storage_root: str | Path) -> None:
        self.storage_root = Path(storage_root).expanduser().resolve()
        self._case_record_cache: dict[str, CaseRecord] = {}
        self._run_record_cache: dict[tuple[str, str], BidReviewRunRecord] = {}
        self._commit_record_cache: dict[tuple[str, str], ContractCommitRecord] = {}

    def case_dir(self, project_id: str) -> Path:
        return self.storage_root / project_id

    def case_record_path(self, project_id: str) -> Path:
        return self.case_dir(project_id) / "case_record.json"

    def _lock_path(self, project_id: str) -> Path:
        return self.case_dir(project_id) / ".case.lock"

    def _lock_case(self, project_id: str, timeout: float = 5.0):
        """Acquire an exclusive lock on the case with timeout."""
        lock_path = self._lock_path(project_id)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+", encoding="utf-8")
        if fcntl is not None:
            start_time = time.monotonic()
            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return handle
                except BlockingIOError:
                    if time.monotonic() - start_time >= timeout:
                        handle.close()
                        raise TimeoutError(
                            f"Failed to acquire lock for project '{project_id}' within {timeout}s"
                        )
                    time.sleep(0.1)
        return handle

    def _unlock_case(self, handle) -> None:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()

    def load_case_record(self, project_id: str) -> CaseRecord:
        if project_id in self._case_record_cache:
            return self._case_record_cache[project_id]
        path = self.case_record_path(project_id)
        record = CaseRecord.model_validate(read_json(path))
        self._case_record_cache[project_id] = record
        return record

    def load_run_record(self, project_id: str, run_id: str) -> BidReviewRunRecord:
        cache_key = (project_id, run_id)
        if cache_key in self._run_record_cache:
            return self._run_record_cache[cache_key]
        path = self.case_dir(project_id) / "runs" / f"{run_id}.json"
        record = BidReviewRunRecord.model_validate(read_json(path))
        self._run_record_cache[cache_key] = record
        return record

    def load_latest_run_record(self, project_id: str) -> BidReviewRunRecord:
        case_record = self.load_case_record(project_id)
        return self.load_run_record(project_id, case_record.latest_run_id)

    def load_commit_record(
        self, project_id: str, commit_id: str
    ) -> ContractCommitRecord:
        cache_key = (project_id, commit_id)
        if cache_key in self._commit_record_cache:
            return self._commit_record_cache[cache_key]
        path = self.case_dir(project_id) / "commits" / f"{commit_id}.json"
        record = ContractCommitRecord.model_validate(read_json(path))
        self._commit_record_cache[cache_key] = record
        return record

    def load_latest_commit_record(self, project_id: str) -> ContractCommitRecord:
        case_record = self.load_case_record(project_id)
        if not case_record.latest_commit_id:
            raise FileNotFoundError(
                f"No committed contract record exists for project '{project_id}'."
            )
        return self.load_commit_record(project_id, case_record.latest_commit_id)

    def load_current_obligations(self, project_id: str) -> list[Obligation]:
        path = self.case_dir(project_id) / "obligations" / "current.json"
        return [Obligation.model_validate(item) for item in read_json(path)]

    def load_latest_monitoring_run(self, project_id: str) -> MonitoringRunRecord:
        case_record = self.load_case_record(project_id)
        if not case_record.latest_monitoring_run_id:
            raise FileNotFoundError(
                f"No monitoring run exists for project '{project_id}'."
            )
        path = (
            self.case_dir(project_id)
            / "monitoring"
            / "runs"
            / f"{case_record.latest_monitoring_run_id}.json"
        )
        return MonitoringRunRecord.model_validate(read_json(path))

    def load_current_review_actions(self, project_id: str) -> list[ReviewActionRecord]:
        path = self.case_dir(project_id) / "review_actions" / "current.json"
        if not path.exists():
            return []
        payload = read_json(path)
        if not isinstance(payload, list):
            raise ValueError(
                f"Review-action snapshot is malformed for project '{project_id}'."
            )
        return [ReviewActionRecord.model_validate(item) for item in payload]

    def persist_review_action(
        self,
        *,
        project_id: str,
        review_action: ReviewActionRecord,
    ) -> ReviewActionRecord:
        case_dir = self.case_dir(project_id)
        current_path = case_dir / "review_actions" / "current.json"
        history_dir = case_dir / "review_actions" / "history"
        event_time = datetime.now(timezone.utc)
        event_id = event_time.strftime("review_%Y%m%dT%H%M%S%fZ")
        action_key = (review_action.kind, review_action.ui_id)

        lock_handle = self._lock_case(project_id)
        try:
            current_actions = self.load_current_review_actions(project_id)
            indexed = {(item.kind, item.ui_id): item for item in current_actions}
            existing = indexed.get(action_key)
            persisted = review_action.model_copy(
                update={
                    "created_at": existing.created_at
                    if existing
                    else review_action.created_at,
                    "updated_at": review_action.updated_at,
                }
            )
            indexed[action_key] = persisted
            ordered = sorted(
                indexed.values(),
                key=lambda item: (item.kind, item.ui_id),
            )
            _write_json(
                current_path, [item.model_dump(mode="json") for item in ordered]
            )
            _write_json(
                history_dir / f"{event_id}.json",
                ReviewActionEvent(
                    event_id=event_id,
                    event_type="upsert",
                    kind=persisted.kind,
                    ui_id=persisted.ui_id,
                    title=persisted.title,
                    disposition=persisted.disposition,
                    owner=persisted.owner,
                    note=persisted.note,
                    source_run_id=persisted.source_run_id,
                    source_commit_id=persisted.source_commit_id,
                    occurred_at=event_time,
                ).model_dump(mode="json"),
            )
        finally:
            self._unlock_case(lock_handle)
        return persisted

    def clear_review_action(self, project_id: str, *, kind: str, ui_id: str) -> bool:
        case_dir = self.case_dir(project_id)
        current_path = case_dir / "review_actions" / "current.json"
        history_dir = case_dir / "review_actions" / "history"
        event_time = datetime.now(timezone.utc)
        event_id = event_time.strftime("review_%Y%m%dT%H%M%S%fZ")
        action_key = (kind.strip().lower(), ui_id)
        removed = False

        lock_handle = self._lock_case(project_id)
        try:
            current_actions = self.load_current_review_actions(project_id)
            remaining: list[ReviewActionRecord] = []
            removed_action: ReviewActionRecord | None = None
            for item in current_actions:
                if (item.kind, item.ui_id) == action_key:
                    removed = True
                    removed_action = item
                    continue
                remaining.append(item)
            if not removed:
                return False
            _write_json(
                current_path, [item.model_dump(mode="json") for item in remaining]
            )
            _write_json(
                history_dir / f"{event_id}.json",
                ReviewActionEvent(
                    event_id=event_id,
                    event_type="clear",
                    kind=action_key[0],
                    ui_id=ui_id,
                    title=removed_action.title if removed_action else None,
                    disposition=removed_action.disposition if removed_action else None,
                    owner=removed_action.owner if removed_action else "",
                    note=removed_action.note if removed_action else "",
                    source_run_id=removed_action.source_run_id
                    if removed_action
                    else None,
                    source_commit_id=removed_action.source_commit_id
                    if removed_action
                    else None,
                    occurred_at=event_time,
                ).model_dump(mode="json"),
            )
        finally:
            self._unlock_case(lock_handle)
        return True

    def persist_bid_review_run(
        self,
        *,
        project_id: str,
        analysis_perspective: str,
        source_project_dir: str | Path,
        artifacts_dir: str | Path,
        artifact_paths: dict[str, str | Path],
        document_inventory: dict[str, object],
        decision_summary: DecisionSummary,
        context_profile: ContextProfile,
        procurement_profile: ProcurementProfile,
        outcome_evidence: OutcomeEvidenceBundle,
        relationship_strategy: dict[str, object],
        relationship_advice: dict[str, object],
        negotiation_strategy: dict[str, object],
        review_challenges: dict[str, object],
        obligations_count: int,
    ) -> PersistedCaseState:
        timestamp = datetime.now(timezone.utc)
        run_id = timestamp.strftime("run_%Y%m%dT%H%M%S%fZ")
        case_dir = self.storage_root / project_id
        runs_dir = case_dir / "runs"
        run_record_path = runs_dir / f"{run_id}.json"
        case_record_path = case_dir / "case_record.json"

        normalized_artifact_paths = {
            name: str(Path(path).expanduser().resolve())
            for name, path in artifact_paths.items()
        }
        source_dir = str(Path(source_project_dir).expanduser().resolve())
        artifacts_dir_str = str(Path(artifacts_dir).expanduser().resolve())

        run_record = BidReviewRunRecord(
            run_id=run_id,
            project_id=project_id,
            analysis_perspective=analysis_perspective,
            created_at=timestamp,
            source_project_dir=source_dir,
            artifacts_dir=artifacts_dir_str,
            artifact_paths=normalized_artifact_paths,
            document_inventory=document_inventory,
            decision_summary=decision_summary,
            context_profile=context_profile,
            procurement_profile=procurement_profile,
            outcome_evidence=outcome_evidence,
            relationship_strategy=relationship_strategy,
            relationship_advice=relationship_advice,
            negotiation_strategy=negotiation_strategy,
            review_challenges=review_challenges,
            obligations_count=obligations_count,
        )
        lock_handle = self._lock_case(project_id)
        try:
            _write_json(run_record_path, run_record.model_dump(mode="json"))

            existing_history: list[CaseRunIndexEntry] = []
            if case_record_path.exists():
                payload = read_json(case_record_path)
                existing_history = [
                    CaseRunIndexEntry.model_validate(item)
                    for item in payload.get("run_history", [])
                ]
                existing_commit_history = [
                    ContractCommitIndexEntry.model_validate(item)
                    for item in payload.get("commit_history", [])
                ]
                latest_commit_id = payload.get("latest_commit_id")
                total_commits = int(payload.get("total_commits", 0))
                latest_obligations_count = int(
                    payload.get("latest_obligations_count", 0)
                )
                latest_monitoring_run_id = payload.get("latest_monitoring_run_id")
                total_monitoring_runs = int(payload.get("total_monitoring_runs", 0))
                monitoring_history = [
                    MonitoringRunIndexEntry.model_validate(item)
                    for item in payload.get("monitoring_history", [])
                ]
            else:
                existing_commit_history = []
                latest_commit_id = None
                total_commits = 0
                latest_obligations_count = 0
                latest_monitoring_run_id = None
                total_monitoring_runs = 0
                monitoring_history = []

            existing_history.append(
                CaseRunIndexEntry(
                    run_id=run_id,
                    run_type="bid_review",
                    analysis_perspective=analysis_perspective,
                    created_at=timestamp,
                    recommendation=decision_summary.recommendation,
                    overall_risk=decision_summary.overall_risk,
                    artifacts_dir=artifacts_dir_str,
                    artifact_count=len(normalized_artifact_paths),
                )
            )

            case_record = CaseRecord(
                project_id=project_id,
                source_project_dir=source_dir,
                storage_dir=str(case_dir),
                latest_run_id=run_id,
                latest_analysis_perspective=analysis_perspective,
                latest_recommendation=decision_summary.recommendation,
                latest_overall_risk=decision_summary.overall_risk,
                latest_agreement_type=procurement_profile.agreement_type,
                latest_project_sector=procurement_profile.project_sector,
                latest_outcome_status=outcome_evidence.outcome_status,
                total_runs=len(existing_history),
                run_history=existing_history[-20:],
                latest_commit_id=latest_commit_id,
                total_commits=total_commits,
                latest_obligations_count=latest_obligations_count,
                commit_history=existing_commit_history[-20:],
                latest_monitoring_run_id=latest_monitoring_run_id,
                total_monitoring_runs=total_monitoring_runs,
                monitoring_history=monitoring_history[-20:],
            )
            _write_json(case_record_path, case_record.model_dump(mode="json"))
        finally:
            self._unlock_case(lock_handle)

        return PersistedCaseState(
            storage_root=self.storage_root,
            case_dir=case_dir,
            case_record_path=case_record_path,
            run_record_path=run_record_path,
            run_id=run_id,
        )

    def persist_contract_commit(
        self,
        *,
        project_id: str,
        analysis_perspective: str,
        source_project_dir: str | Path,
        committed_contract_dir: str | Path,
        source_run_id: str,
        decision_summary: DecisionSummary,
        procurement_profile: ProcurementProfile,
        outcome_status: str,
        finding_dispositions: list[FindingDisposition],
        accepted_risks: list[AcceptedRisk],
        negotiated_changes: list[NegotiatedChange],
        committed_documents: list[ProjectDocumentRecord],
        obligations: list[Obligation],
    ) -> PersistedCommitState:
        timestamp = datetime.now(timezone.utc)
        commit_id = timestamp.strftime("commit_%Y%m%dT%H%M%S%fZ")
        case_dir = self.case_dir(project_id)
        case_record_path = self.case_record_path(project_id)
        commit_record_path = case_dir / "commits" / f"{commit_id}.json"
        obligations_path = case_dir / "obligations" / "by_commit" / f"{commit_id}.json"
        current_obligations_path = case_dir / "obligations" / "current.json"
        lock_handle = self._lock_case(project_id)
        try:
            _write_json(
                obligations_path, [item.model_dump(mode="json") for item in obligations]
            )
            _write_json(
                current_obligations_path,
                [item.model_dump(mode="json") for item in obligations],
            )

            commit_record = ContractCommitRecord(
                commit_id=commit_id,
                project_id=project_id,
                analysis_perspective=analysis_perspective,
                created_at=timestamp,
                source_project_dir=str(Path(source_project_dir).expanduser().resolve()),
                committed_contract_dir=str(
                    Path(committed_contract_dir).expanduser().resolve()
                ),
                source_run_id=source_run_id,
                decision_summary=decision_summary,
                procurement_profile=procurement_profile,
                outcome_status=outcome_status,
                finding_dispositions=finding_dispositions,
                accepted_risks=accepted_risks,
                negotiated_changes=negotiated_changes,
                committed_documents=committed_documents,
                obligations_path=str(obligations_path),
                obligations_count=len(obligations),
            )
            _write_json(commit_record_path, commit_record.model_dump(mode="json"))

            case_record = self.load_case_record(project_id)
            commit_history = list(case_record.commit_history)
            commit_history.append(
                ContractCommitIndexEntry(
                    commit_id=commit_id,
                    analysis_perspective=analysis_perspective,
                    created_at=timestamp,
                    source_run_id=source_run_id,
                    obligations_count=len(obligations),
                    accepted_risks_count=len(accepted_risks),
                    negotiated_changes_count=len(negotiated_changes),
                )
            )
            updated_case_record = case_record.model_copy(
                update={
                    "latest_commit_id": commit_id,
                    "latest_analysis_perspective": analysis_perspective,
                    "total_commits": len(commit_history),
                    "latest_obligations_count": len(obligations),
                    "commit_history": commit_history[-20:],
                }
            )
            _write_json(case_record_path, updated_case_record.model_dump(mode="json"))
        finally:
            self._unlock_case(lock_handle)

        return PersistedCommitState(
            storage_root=self.storage_root,
            case_dir=case_dir,
            case_record_path=case_record_path,
            commit_record_path=commit_record_path,
            obligations_path=current_obligations_path,
            commit_id=commit_id,
        )

    def persist_monitoring_run(
        self,
        *,
        project_id: str,
        source_commit_id: str,
        as_of_date: str,
        monitored_obligations: list[MonitoredObligation],
        alerts: list[AlertRecord],
        status_inputs_path: str | None = None,
    ) -> PersistedMonitoringState:
        timestamp = datetime.now(timezone.utc)
        run_id = timestamp.strftime("monitor_%Y%m%dT%H%M%S%fZ")
        case_dir = self.case_dir(project_id)
        case_record_path = self.case_record_path(project_id)
        monitoring_run_path = case_dir / "monitoring" / "runs" / f"{run_id}.json"
        monitoring_snapshot_path = case_dir / "monitoring" / "current.json"
        alerts_path = case_dir / "alerts" / "current.json"
        alerts_history_path = case_dir / "alerts" / "history" / f"{run_id}.json"

        monitoring_run = MonitoringRunRecord(
            run_id=run_id,
            project_id=project_id,
            created_at=timestamp,
            source_commit_id=source_commit_id,
            as_of_date=as_of_date,
            status_inputs_path=status_inputs_path,
            monitored_obligations=monitored_obligations,
            alerts=alerts,
        )
        run_payload = monitoring_run.model_dump(mode="json")
        lock_handle = self._lock_case(project_id)
        try:
            _write_json(monitoring_run_path, run_payload)
            _write_json(monitoring_snapshot_path, run_payload)
            _write_json(alerts_path, [item.model_dump(mode="json") for item in alerts])
            _write_json(
                alerts_history_path, [item.model_dump(mode="json") for item in alerts]
            )

            case_record = self.load_case_record(project_id)
            monitoring_history = list(case_record.monitoring_history)
            due_count = sum(1 for item in monitored_obligations if item.status == "due")
            late_count = sum(
                1 for item in monitored_obligations if item.status == "late"
            )
            satisfied_count = sum(
                1 for item in monitored_obligations if item.status == "satisfied"
            )
            monitoring_history.append(
                MonitoringRunIndexEntry(
                    run_id=run_id,
                    created_at=timestamp,
                    source_commit_id=source_commit_id,
                    alerts_count=len(alerts),
                    due_count=due_count,
                    late_count=late_count,
                    satisfied_count=satisfied_count,
                )
            )
            updated_case_record = case_record.model_copy(
                update={
                    "latest_monitoring_run_id": run_id,
                    "total_monitoring_runs": len(monitoring_history),
                    "monitoring_history": monitoring_history[-20:],
                }
            )
            _write_json(case_record_path, updated_case_record.model_dump(mode="json"))
        finally:
            self._unlock_case(lock_handle)

        return PersistedMonitoringState(
            storage_root=self.storage_root,
            case_dir=case_dir,
            case_record_path=case_record_path,
            monitoring_run_path=monitoring_run_path,
            alerts_path=alerts_path,
            monitoring_snapshot_path=monitoring_snapshot_path,
            run_id=run_id,
        )
