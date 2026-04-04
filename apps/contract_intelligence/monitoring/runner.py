from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from apps.contract_intelligence.domain.models import (
    AlertRecord,
    MonitoredObligation,
    MonitoringStatusInput,
    Obligation,
)
from apps.contract_intelligence.orchestration.bid_review_runner import (
    compute_project_id,
)
from apps.contract_intelligence.paths import resolve_existing_directory
from apps.contract_intelligence.storage import FileSystemCaseStore
from ese.constants import read_json


@dataclass(frozen=True)
class MonitoringResult:
    project_id: str
    run_id: str
    monitoring_run_path: Path
    monitoring_snapshot_path: Path
    alerts_path: Path
    alerts_count: int


def _status_inputs_by_id(
    path: str | Path | None,
) -> tuple[dict[str, MonitoringStatusInput], str | None]:
    if path is None:
        return {}, None
    resolved = Path(path).expanduser().resolve()
    payload = read_json(resolved)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {resolved}.")
    indexed: dict[str, MonitoringStatusInput] = {}
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(
                f"Expected object items in {resolved}; item {index} is invalid."
            )
        try:
            record = MonitoringStatusInput.model_validate(item)
        except ValidationError as exc:
            if "status" in str(exc):
                raise ValueError(
                    "status must be one of pending, due, late, or satisfied"
                ) from exc
            raise ValueError(f"Status input item {index} is invalid: {exc}") from exc
        if record.obligation_id in indexed:
            raise ValueError(
                f"Duplicate obligation_id '{record.obligation_id}' in {resolved}."
            )
        indexed[record.obligation_id] = record
    return indexed, str(resolved)


def _status_from_due_dates(
    *,
    obligation: Obligation,
    next_due_at: datetime | None,
    last_satisfied_at: datetime | None,
    as_of_date: date,
) -> tuple[str, str]:
    if next_due_at is None:
        if obligation.obligation_type == "recurring_reporting":
            return (
                "pending",
                "Recurring reporting obligation is awaiting a scheduled next_due_at value.",
            )
        if obligation.obligation_type == "pre_start_requirement":
            return (
                "pending",
                "Pre-start requirement remains open until mobilization readiness is confirmed.",
            )
        if obligation.obligation_type == "notice_deadline":
            return (
                "pending",
                "Event-driven notice obligation remains open until a triggering event occurs.",
            )
        return (
            "pending",
            "Obligation is open and awaiting an operational status update.",
        )

    due_date = next_due_at.date()
    if last_satisfied_at is not None and last_satisfied_at >= next_due_at:
        return (
            "satisfied",
            "Operational inputs show this obligation was satisfied for the current due cycle.",
        )
    if as_of_date > due_date:
        return (
            "late",
            "Operational inputs show the due date has passed without a satisfaction record.",
        )
    if as_of_date == due_date:
        return (
            "due",
            "Operational inputs show the obligation is due as of the monitoring date.",
        )
    return (
        "pending",
        "Operational inputs show the obligation is scheduled for a future due date.",
    )


def _default_status(
    obligation: Obligation,
    *,
    next_due_at: datetime | None,
    last_satisfied_at: datetime | None,
    as_of_date: date,
) -> tuple[str, str]:
    if obligation.obligation_type in {
        "recurring_reporting",
        "pre_start_requirement",
        "notice_deadline",
    }:
        return _status_from_due_dates(
            obligation=obligation,
            next_due_at=next_due_at,
            last_satisfied_at=last_satisfied_at,
            as_of_date=as_of_date,
        )
    return "pending", "Obligation is open and awaiting an operational status update."


def _monitored_obligation(
    obligation: Obligation,
    status_input: MonitoringStatusInput | None,
    *,
    as_of_date: date,
) -> MonitoredObligation:
    next_due_at = status_input.next_due_at if status_input else None
    last_satisfied_at = status_input.last_satisfied_at if status_input else None
    default_status, default_summary = _default_status(
        obligation,
        next_due_at=next_due_at,
        last_satisfied_at=last_satisfied_at,
        as_of_date=as_of_date,
    )
    status = (
        status_input.status
        if status_input and status_input.status is not None
        else default_status
    )
    summary = (
        status_input.summary
        if status_input and status_input.summary is not None
        else default_summary
    )

    notes: list[str] = []
    if status_input:
        notes = [str(item) for item in status_input.notes]

    return MonitoredObligation(
        obligation_id=obligation.id,
        title=obligation.title,
        source_clause=obligation.source_clause,
        owner_role=obligation.owner_role,
        severity_if_missed=obligation.severity_if_missed,
        status=status,
        summary=summary,
        next_due_at=next_due_at,
        last_satisfied_at=last_satisfied_at,
        notes=notes,
    )


def _alerts_for(
    monitored: list[MonitoredObligation], *, as_of_date: date
) -> list[AlertRecord]:
    alerts: list[AlertRecord] = []
    now = datetime.now(timezone.utc)
    for obligation in monitored:
        if obligation.status not in {"due", "late"}:
            continue
        due_cycle = (
            obligation.next_due_at.isoformat()
            if obligation.next_due_at
            else as_of_date.isoformat()
        )
        digest = hashlib.sha1(
            f"{obligation.obligation_id}|{obligation.status}|{due_cycle}".encode(
                "utf-8"
            )
        ).hexdigest()[:12]
        alerts.append(
            AlertRecord(
                alert_id=f"alert_{digest}",
                obligation_id=obligation.obligation_id,
                created_at=now,
                severity=obligation.severity_if_missed,
                alert_type=obligation.status,
                status="open",
                summary=obligation.summary,
            )
        )
    return alerts


def monitor_contract(
    project_dir: str | Path,
    *,
    status_inputs_file: str | Path | None = None,
    as_of_date: date | None = None,
) -> MonitoringResult:
    project_path = resolve_existing_directory(project_dir, label="Project directory")
    project_id = compute_project_id(project_path)
    store = FileSystemCaseStore(project_path / ".contract_intelligence")
    latest_commit = store.load_latest_commit_record(project_id)
    obligations = store.load_current_obligations(project_id)
    status_inputs, status_inputs_path = _status_inputs_by_id(status_inputs_file)
    effective_as_of_date = as_of_date or date.today()

    monitored = [
        _monitored_obligation(
            item, status_inputs.get(item.id), as_of_date=effective_as_of_date
        )
        for item in obligations
    ]
    alerts = _alerts_for(monitored, as_of_date=effective_as_of_date)
    persisted = store.persist_monitoring_run(
        project_id=project_id,
        source_commit_id=latest_commit.commit_id,
        as_of_date=effective_as_of_date.isoformat(),
        monitored_obligations=monitored,
        alerts=alerts,
        status_inputs_path=status_inputs_path,
    )

    return MonitoringResult(
        project_id=project_id,
        run_id=persisted.run_id,
        monitoring_run_path=persisted.monitoring_run_path,
        monitoring_snapshot_path=persisted.monitoring_snapshot_path,
        alerts_path=persisted.alerts_path,
        alerts_count=len(alerts),
    )
