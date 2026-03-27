from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from apps.contract_intelligence.domain.models import AlertRecord, MonitoredObligation, Obligation
from apps.contract_intelligence.orchestration.bid_review_runner import _project_id
from apps.contract_intelligence.storage import FileSystemCaseStore


@dataclass(frozen=True)
class MonitoringResult:
    project_id: str
    run_id: str
    monitoring_run_path: Path
    monitoring_snapshot_path: Path
    alerts_path: Path
    alerts_count: int


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _status_inputs_by_id(path: str | Path | None) -> tuple[dict[str, dict[str, Any]], str | None]:
    if path is None:
        return {}, None
    resolved = Path(path).expanduser().resolve()
    payload = _read_json(resolved)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {resolved}.")
    indexed: dict[str, dict[str, Any]] = {}
    for item in payload:
        if isinstance(item, dict) and isinstance(item.get("obligation_id"), str):
            indexed[item["obligation_id"]] = item
    return indexed, str(resolved)


def _default_status(obligation: Obligation) -> tuple[str, str]:
    if obligation.obligation_type == "recurring_reporting":
        return "due", "Recurring reporting obligation requires an updated operational status."
    if obligation.obligation_type == "pre_start_requirement":
        return "pending", "Pre-start requirement remains open until mobilization readiness is confirmed."
    if obligation.obligation_type == "notice_deadline":
        return "pending", "Event-driven notice obligation remains open until a triggering event occurs."
    return "pending", "Obligation is open and awaiting an operational status update."


def _monitored_obligation(obligation: Obligation, status_input: dict[str, Any] | None) -> MonitoredObligation:
    default_status, default_summary = _default_status(obligation)
    status = str((status_input or {}).get("status", default_status))
    summary = str((status_input or {}).get("summary", default_summary))

    notes: list[str] = []
    raw_notes = (status_input or {}).get("notes", [])
    if isinstance(raw_notes, str):
        notes = [raw_notes]
    elif isinstance(raw_notes, list):
        notes = [str(item) for item in raw_notes]

    return MonitoredObligation(
        obligation_id=obligation.id,
        title=obligation.title,
        source_clause=obligation.source_clause,
        owner_role=obligation.owner_role,
        severity_if_missed=obligation.severity_if_missed,
        status=status,
        summary=summary,
        next_due_at=_parse_dt((status_input or {}).get("next_due_at")),
        last_satisfied_at=_parse_dt((status_input or {}).get("last_satisfied_at")),
        notes=notes,
    )


def _alerts_for(monitored: list[MonitoredObligation]) -> list[AlertRecord]:
    alerts: list[AlertRecord] = []
    now = datetime.now(timezone.utc)
    for index, obligation in enumerate(monitored, start=1):
        if obligation.status not in {"due", "late"}:
            continue
        alerts.append(
            AlertRecord(
                alert_id=f"alert_{index:03d}",
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
    project_path = Path(project_dir).expanduser().resolve()
    project_id = _project_id(project_path)
    store = FileSystemCaseStore(project_path / ".contract_intelligence")
    latest_commit = store.load_latest_commit_record(project_id)
    obligations = store.load_current_obligations(project_id)
    status_inputs, status_inputs_path = _status_inputs_by_id(status_inputs_file)

    monitored = [_monitored_obligation(item, status_inputs.get(item.id)) for item in obligations]
    alerts = _alerts_for(monitored)
    persisted = store.persist_monitoring_run(
        project_id=project_id,
        source_commit_id=latest_commit.commit_id,
        as_of_date=(as_of_date or date.today()).isoformat(),
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
