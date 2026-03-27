from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apps.contract_intelligence.orchestration.bid_review_runner import _project_id
from apps.contract_intelligence.storage import FileSystemCaseStore


def _read_json(path: str | Path | None) -> Any:
    if not path:
        return None
    target = Path(path)
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def _severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for finding in findings:
        severity = str(finding.get("severity", "")).lower()
        if severity in counts:
            counts[severity] += 1
    return counts


def _lifecycle_timeline(case_record: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for run in case_record.get("run_history", []):
        entries.append(
            {
                "kind": "review",
                "id": run.get("run_id"),
                "created_at": run.get("created_at"),
                "summary": f"{run.get('recommendation', 'unknown')} / {run.get('overall_risk', 'unknown')}",
            }
        )
    for commit in case_record.get("commit_history", []):
        entries.append(
            {
                "kind": "commit",
                "id": commit.get("commit_id"),
                "created_at": commit.get("created_at"),
                "summary": (
                    f"{commit.get('accepted_risks_count', 0)} carried risks, "
                    f"{commit.get('obligations_count', 0)} obligations"
                ),
            }
        )
    for monitoring in case_record.get("monitoring_history", []):
        entries.append(
            {
                "kind": "monitor",
                "id": monitoring.get("run_id"),
                "created_at": monitoring.get("created_at"),
                "summary": (
                    f"{monitoring.get('alerts_count', 0)} alerts, "
                    f"{monitoring.get('late_count', 0)} late"
                ),
            }
        )
    return sorted(entries, key=lambda item: str(item.get("created_at", "")), reverse=True)


def _load_dashboard_data(project_path: Path) -> dict[str, Any]:
    project_id = _project_id(project_path)
    store = FileSystemCaseStore(project_path / ".contract_intelligence")
    case_record = store.load_case_record(project_id).model_dump(mode="json")
    latest_run = store.load_latest_run_record(project_id).model_dump(mode="json")

    artifact_paths = latest_run.get("artifact_paths", {})
    risk_findings = _read_json(artifact_paths.get("risk_findings.json")) or []
    insurance_findings = _read_json(artifact_paths.get("insurance_findings.json")) or []
    compliance_findings = _read_json(artifact_paths.get("compliance_findings.json")) or []

    findings: list[dict[str, Any]] = []
    for source_name, payload in (
        ("commercial", risk_findings),
        ("insurance", insurance_findings),
        ("compliance", compliance_findings),
    ):
        for index, finding in enumerate(payload, start=1):
            if isinstance(finding, dict):
                enriched = dict(finding)
                enriched["source_group"] = source_name
                enriched["ui_id"] = str(enriched.get("id") or f"{source_name}_finding_{index}")
                findings.append(enriched)

    latest_commit = (
        store.load_latest_commit_record(project_id).model_dump(mode="json")
        if case_record.get("latest_commit_id")
        else None
    )
    latest_monitoring = (
        store.load_latest_monitoring_run(project_id).model_dump(mode="json")
        if case_record.get("latest_monitoring_run_id")
        else None
    )
    obligations = []
    if case_record.get("latest_commit_id"):
        for index, item in enumerate(store.load_current_obligations(project_id), start=1):
            payload = item.model_dump(mode="json")
            payload["ui_id"] = str(payload.get("id") or f"obligation_{index}")
            obligations.append(payload)

    alerts = latest_monitoring.get("alerts", []) if latest_monitoring else []
    for index, item in enumerate(alerts, start=1):
        if isinstance(item, dict):
            item.setdefault("ui_id", str(item.get("alert_id") or f"alert_{index}"))
    monitored_obligations = latest_monitoring.get("monitored_obligations", []) if latest_monitoring else []
    documents = latest_run.get("document_inventory", {}).get("documents", [])
    decision = latest_run.get("decision_summary", {})
    severity_counts = _severity_counts(findings)
    obligation_status_counts = {"pending": 0, "due": 0, "late": 0, "satisfied": 0}
    for item in monitored_obligations:
        status = str(item.get("status", "pending")).lower()
        if status in obligation_status_counts:
            obligation_status_counts[status] += 1
        else:
            obligation_status_counts["pending"] += 1

    return {
        "project_id": project_id,
        "project_path": str(project_path),
        "case_record": case_record,
        "latest_run": latest_run,
        "latest_commit": latest_commit,
        "latest_monitoring": latest_monitoring,
        "documents": documents,
        "findings": findings,
        "obligations": obligations,
        "monitored_obligations": monitored_obligations,
        "alerts": alerts,
        "severity_counts": severity_counts,
        "obligation_status_counts": obligation_status_counts,
        "timeline": _lifecycle_timeline(case_record),
        "summary_metrics": {
            "recommendation": decision.get("recommendation", "unknown"),
            "overall_risk": decision.get("overall_risk", "unknown"),
            "confidence": decision.get("confidence", 0),
            "must_fix_count": len(decision.get("must_fix_before_bid", [])),
            "findings_count": len(findings),
            "alerts_count": len(alerts),
            "documents_count": len(documents),
            "obligations_count": len(obligations),
        },
    }


def render_project_dashboard(project_dir: str | Path, *, output_path: str | Path | None = None) -> Path:
    project_path = Path(project_dir).expanduser().resolve()
    data = _load_dashboard_data(project_path)
    payload = json.dumps(data).replace("</", "<\\/")

    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Contract Intelligence Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --sand: #f4efe6;
      --paper: #fbf8f2;
      --panel: rgba(255, 255, 255, 0.92);
      --panel-strong: #ffffff;
      --ink: #132238;
      --muted: #5c6874;
      --line: rgba(19, 34, 56, 0.10);
      --accent: #0f7662;
      --accent-2: #c96b2c;
      --risk: #9e2a2b;
      --warn: #a16207;
      --glow: rgba(15, 118, 98, 0.18);
      --shadow: 0 18px 60px rgba(19, 34, 56, 0.10);
      --radius-xl: 28px;
      --radius-lg: 20px;
      --radius-md: 14px;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 0% 0%, rgba(201, 107, 44, 0.14), transparent 30%),
        radial-gradient(circle at 100% 20%, rgba(15, 118, 98, 0.18), transparent 36%),
        linear-gradient(180deg, #f7f0e6 0%, #f4f6f7 44%, #eef2f3 100%);
      font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
      min-height: 100vh;
    }}

    .shell {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 28px 18px 56px;
    }}

    .masthead {{
      position: relative;
      overflow: hidden;
      background:
        linear-gradient(135deg, rgba(255,255,255,0.90), rgba(255,255,255,0.74)),
        linear-gradient(135deg, rgba(15,118,98,0.08), rgba(201,107,44,0.10));
      border: 1px solid rgba(255,255,255,0.65);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow);
      padding: 28px;
      backdrop-filter: blur(12px);
    }}

    .masthead::after {{
      content: "";
      position: absolute;
      inset: auto -10% -40% 50%;
      height: 220px;
      background: radial-gradient(circle, rgba(15,118,98,0.10), transparent 65%);
      pointer-events: none;
    }}

    .eyebrow {{
      font: 700 0.74rem/1.2 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 14px;
    }}

    h1, h2, h3 {{
      margin: 0;
      color: var(--ink);
    }}

    h1 {{
      font: 700 clamp(2.2rem, 5vw, 4.2rem)/0.94 "Avenir Next Condensed", "Avenir Next", "Segoe UI Variable Display", sans-serif;
      letter-spacing: -0.04em;
      max-width: 12ch;
    }}

    .lead {{
      margin-top: 14px;
      max-width: 72ch;
      color: var(--muted);
      font-size: 1.02rem;
      line-height: 1.6;
    }}

    .hero-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.9fr);
      gap: 22px;
      margin-top: 22px;
    }}

    .hero-panel,
    .card,
    .workspace,
    .subpanel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      box-shadow: 0 10px 35px rgba(19, 34, 56, 0.06);
      backdrop-filter: blur(10px);
    }}

    .hero-panel {{
      padding: 22px;
      min-height: 100%;
    }}

    .kpis {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 22px;
    }}

    .kpi {{
      padding: 18px;
      border-radius: var(--radius-md);
      background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(255,255,255,0.80));
      border: 1px solid rgba(19, 34, 56, 0.08);
    }}

    .kpi .value {{
      font: 700 1.9rem/1 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      letter-spacing: -0.04em;
      margin-bottom: 6px;
    }}

    .kpi .label {{
      color: var(--muted);
      font: 600 0.86rem/1.3 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    .badge-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }}

    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 14px;
      border-radius: 999px;
      font: 700 0.8rem/1 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      background: rgba(255,255,255,0.88);
      border: 1px solid rgba(19, 34, 56, 0.08);
    }}

    .badge.risk {{ color: var(--risk); }}
    .badge.warn {{ color: var(--warn); }}
    .badge.good {{ color: var(--accent); }}

    .mode-switch {{
      display: inline-flex;
      gap: 8px;
      padding: 6px;
      border-radius: 999px;
      background: rgba(19,34,56,0.06);
      border: 1px solid rgba(19,34,56,0.08);
      margin-bottom: 10px;
    }}

    .mode-button {{
      appearance: none;
      border: 0;
      background: transparent;
      color: var(--muted);
      padding: 10px 14px;
      border-radius: 999px;
      cursor: pointer;
      font: 700 0.82rem/1 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      transition: background 150ms ease, color 150ms ease, transform 150ms ease;
    }}

    .mode-button:hover {{
      transform: translateY(-1px);
    }}

    .mode-button.is-active {{
      background: linear-gradient(135deg, rgba(15,118,98,0.18), rgba(255,255,255,0.95));
      color: var(--ink);
      box-shadow: inset 0 0 0 1px rgba(15,118,98,0.18);
    }}

    .mode-caption {{
      color: var(--muted);
      font: 500 0.92rem/1.5 "Avenir Next", "Segoe UI Variable Text", sans-serif;
      margin: 0 0 16px;
    }}

    .summary-strip {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 18px;
    }}

    .summary-pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 12px;
      border-radius: 14px;
      background: rgba(255,255,255,0.86);
      border: 1px solid rgba(19,34,56,0.08);
      font: 700 0.8rem/1 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      color: var(--ink);
    }}

    .confidence-wrap {{
      margin-top: 18px;
    }}

    .confidence-track {{
      height: 12px;
      border-radius: 999px;
      background: linear-gradient(90deg, rgba(158,42,43,0.16), rgba(201,107,44,0.18), rgba(15,118,98,0.18));
      overflow: hidden;
    }}

    .confidence-fill {{
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, #d86d4f, #0f7662);
      box-shadow: 0 0 28px var(--glow);
    }}

    .layout {{
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      gap: 18px;
      margin-top: 22px;
      align-items: start;
    }}

    .rail {{
      position: sticky;
      top: 18px;
      padding: 18px;
    }}

    .rail h2 {{
      font: 700 1rem/1.1 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      margin-bottom: 14px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }}

    .nav-list {{
      display: grid;
      gap: 10px;
    }}

    .nav-button {{
      appearance: none;
      border: 1px solid rgba(19, 34, 56, 0.08);
      border-radius: 16px;
      background: rgba(255,255,255,0.75);
      padding: 14px 16px;
      text-align: left;
      cursor: pointer;
      color: var(--ink);
      font: 700 0.92rem/1.2 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      transition: transform 160ms ease, background 160ms ease, border-color 160ms ease;
    }}

    .nav-button small {{
      display: block;
      margin-top: 6px;
      color: var(--muted);
      font: 500 0.76rem/1.4 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    .nav-button:hover,
    .nav-button[aria-selected="true"] {{
      transform: translateX(3px);
      background: linear-gradient(135deg, rgba(15,118,98,0.12), rgba(255,255,255,0.92));
      border-color: rgba(15,118,98,0.28);
    }}

    .workspace {{
      overflow: hidden;
      padding: 18px;
    }}

    body[data-report-mode="external"] [data-internal-only="true"] {{
      display: none !important;
    }}

    .view {{
      display: none;
      animation: rise 220ms ease;
    }}

    .view.active {{
      display: block;
    }}

    @keyframes rise {{
      from {{ opacity: 0; transform: translateY(6px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    .section-head {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 16px;
    }}

    .section-head p {{
      margin: 8px 0 0;
      max-width: 70ch;
    }}

    .control-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 16px;
    }}

    .control-row input,
    .control-row select {{
      appearance: none;
      border: 1px solid rgba(19,34,56,0.12);
      background: rgba(255,255,255,0.95);
      border-radius: 12px;
      padding: 12px 14px;
      font: 500 0.92rem/1 "Avenir Next", "Segoe UI Variable Text", sans-serif;
      color: var(--ink);
      min-width: 180px;
    }}

    .chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}

    .chip {{
      border-radius: 999px;
      padding: 8px 12px;
      background: rgba(15,118,98,0.08);
      border: 1px solid rgba(15,118,98,0.14);
      font: 700 0.76rem/1 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--accent);
    }}

    .grid-2,
    .grid-3 {{
      display: grid;
      gap: 16px;
    }}

    .grid-2 {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}

    .grid-3 {{
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }}

    .detail-layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.9fr);
      gap: 16px;
      align-items: start;
    }}

    .stat-card {{
      padding: 18px;
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(255,255,255,0.78));
      border: 1px solid rgba(19,34,56,0.08);
    }}

    .stat-card .number {{
      font: 700 2rem/1 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      letter-spacing: -0.05em;
    }}

    .stack {{
      display: grid;
      gap: 14px;
    }}

    .finding,
    .timeline-item,
    .obligation-card,
    .signal-card,
    .alert-card,
    .doc-card,
    .review-card,
    .detail-card {{
      border: 1px solid rgba(19,34,56,0.08);
      border-radius: 18px;
      background: rgba(255,255,255,0.88);
      padding: 16px;
    }}

    .finding h3,
    .timeline-item h3,
    .obligation-card h3,
    .signal-card h3,
    .alert-card h3,
    .doc-card h3,
    .review-card h3,
    .detail-card h3 {{
      font: 700 1rem/1.25 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      margin-bottom: 8px;
    }}

    .interactive-card {{
      cursor: pointer;
      transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
    }}

    .interactive-card:hover {{
      transform: translateY(-1px);
      border-color: rgba(15,118,98,0.22);
      box-shadow: 0 12px 28px rgba(19,34,56,0.08);
    }}

    .interactive-card.active {{
      border-color: rgba(15,118,98,0.32);
      box-shadow: 0 14px 34px rgba(15,118,98,0.12);
      background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(236,248,245,0.92));
    }}

    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 10px;
    }}

    .meta span {{
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(19,34,56,0.05);
      color: var(--muted);
      font: 700 0.72rem/1 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}

    .severity-critical {{ color: var(--risk); }}
    .severity-high {{ color: var(--risk); }}
    .severity-medium {{ color: var(--warn); }}
    .severity-low {{ color: var(--accent); }}

    .timeline {{
      position: relative;
      padding-left: 20px;
    }}

    .timeline::before {{
      content: "";
      position: absolute;
      left: 5px;
      top: 0;
      bottom: 0;
      width: 2px;
      background: linear-gradient(180deg, rgba(15,118,98,0.26), rgba(201,107,44,0.24));
    }}

    .timeline-item {{
      position: relative;
      margin-left: 16px;
    }}

    .timeline-item::before {{
      content: "";
      position: absolute;
      left: -25px;
      top: 18px;
      width: 12px;
      height: 12px;
      border-radius: 999px;
      background: var(--accent);
      box-shadow: 0 0 0 6px rgba(15,118,98,0.12);
    }}

    .columns {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }}

    .column {{
      border-radius: 18px;
      padding: 14px;
      background: linear-gradient(180deg, rgba(255,255,255,0.82), rgba(255,255,255,0.64));
      border: 1px solid rgba(19,34,56,0.08);
      min-height: 220px;
    }}

    .column h3 {{
      margin-bottom: 10px;
    }}

    .column .stack {{
      gap: 10px;
    }}

    .detail-panel {{
      position: sticky;
      top: 18px;
      border-radius: 20px;
      padding: 18px;
      background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(249,252,251,0.82));
      border: 1px solid rgba(19,34,56,0.08);
      box-shadow: 0 16px 40px rgba(19,34,56,0.08);
    }}

    .detail-divider {{
      height: 1px;
      background: rgba(19,34,56,0.10);
      margin: 16px 0;
    }}

    .detail-list {{
      display: grid;
      gap: 10px;
      padding-left: 18px;
      margin: 0;
      color: var(--muted);
    }}

    .detail-list li {{
      line-height: 1.5;
    }}

    .review-form {{
      display: grid;
      gap: 12px;
    }}

    .review-form label {{
      display: grid;
      gap: 6px;
      font: 700 0.78rem/1.25 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
    }}

    .review-form input,
    .review-form select,
    .review-form textarea {{
      width: 100%;
      appearance: none;
      border: 1px solid rgba(19,34,56,0.12);
      background: rgba(255,255,255,0.96);
      border-radius: 12px;
      padding: 12px 14px;
      font: 500 0.92rem/1.35 "Avenir Next", "Segoe UI Variable Text", sans-serif;
      color: var(--ink);
    }}

    .review-form textarea {{
      min-height: 88px;
      resize: vertical;
    }}

    .inline-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}

    .action-button {{
      appearance: none;
      border: 1px solid rgba(15,118,98,0.18);
      background: linear-gradient(135deg, rgba(15,118,98,0.12), rgba(255,255,255,0.94));
      color: var(--ink);
      border-radius: 12px;
      padding: 10px 14px;
      cursor: pointer;
      font: 700 0.82rem/1 "Avenir Next", "Segoe UI Variable Display", sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    .action-button.subtle {{
      border-color: rgba(19,34,56,0.10);
      background: rgba(255,255,255,0.90);
    }}

    .note {{
      margin: 0;
      color: var(--muted);
      font: 500 0.88rem/1.5 "Avenir Next", "Segoe UI Variable Text", sans-serif;
    }}

    .doc-table {{
      width: 100%;
      border-collapse: collapse;
      background: rgba(255,255,255,0.84);
      border-radius: 18px;
      overflow: hidden;
      border: 1px solid rgba(19,34,56,0.08);
    }}

    .doc-table th,
    .doc-table td {{
      padding: 12px 14px;
      text-align: left;
      border-bottom: 1px solid rgba(19,34,56,0.08);
      font-family: "Avenir Next", "Segoe UI Variable Text", sans-serif;
      font-size: 0.92rem;
    }}

    .doc-table th {{
      color: var(--muted);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    .empty {{
      padding: 28px 20px;
      text-align: center;
      color: var(--muted);
      border: 1px dashed rgba(19,34,56,0.16);
      border-radius: 18px;
      background: rgba(255,255,255,0.54);
    }}

    @media (max-width: 1120px) {{
      .hero-grid,
      .layout,
      .grid-2,
      .grid-3,
      .columns,
      .detail-layout {{
        grid-template-columns: 1fr;
      }}
      .kpis {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .rail {{
        position: static;
      }}
    }}

    @media (max-width: 700px) {{
      .shell {{
        padding: 18px 12px 42px;
      }}
      .masthead,
      .hero-panel,
      .workspace {{
        padding: 16px;
      }}
      .kpis {{
        grid-template-columns: 1fr;
      }}
      .mode-switch,
      .summary-strip,
      .inline-actions {{
        width: 100%;
      }}
      .control-row input,
      .control-row select {{
        width: 100%;
      }}
    }}
  </style>
</head>
<body data-report-mode="internal">
  <div class="shell">
    <section class="masthead">
      <div class="eyebrow">Construction Contract Intelligence</div>
      <div class="hero-grid">
        <div>
          <h1 id="project-title"></h1>
          <p class="lead" id="hero-lead">
            A project command surface for review decisions, committed baselines, internal context,
            operational obligations, and live alert posture.
          </p>
          <div class="badge-row" id="hero-badges"></div>
          <div class="confidence-wrap">
            <div class="eyebrow" style="margin-bottom:8px;">Decision Confidence</div>
            <div class="confidence-track"><div class="confidence-fill" id="confidence-fill"></div></div>
          </div>
        </div>
        <div class="hero-panel">
          <div class="section-head" style="margin-bottom:12px;">
            <div>
              <div class="eyebrow">Report Mode</div>
              <h2 style="font:700 1.15rem/1.1 'Avenir Next', 'Segoe UI Variable Display', sans-serif;">Audience-Aware Surface</h2>
            </div>
          </div>
          <div class="mode-switch" id="report-mode-switch">
            <button class="mode-button is-active" data-report-mode-control="internal">Internal</button>
            <button class="mode-button" data-report-mode-control="external">External</button>
          </div>
          <p class="mode-caption" id="mode-caption"></p>
          <div class="summary-strip" id="review-snapshot"></div>
          <div class="eyebrow">Project Posture</div>
          <div class="kpis" id="kpis"></div>
        </div>
      </div>
    </section>

    <section class="layout">
      <aside class="rail card">
        <h2>Workspace</h2>
        <div class="nav-list" id="nav-list"></div>
      </aside>

      <section class="workspace">
        <div class="view active" data-view="overview">
          <div class="section-head">
            <div>
              <h2>Executive Overview</h2>
              <p>Decision framing, must-fix items, lifecycle counts, and the immediate operating picture.</p>
            </div>
          </div>
          <div class="grid-3" id="overview-stats"></div>
          <div class="grid-2" style="margin-top:16px;">
            <div class="subpanel" style="padding:18px;">
              <div class="eyebrow">Top Reasons</div>
              <div class="stack" id="top-reasons"></div>
            </div>
            <div class="subpanel" style="padding:18px;">
              <div class="eyebrow">Must Fix Before Bid</div>
              <div class="stack" id="must-fix"></div>
            </div>
          </div>
        </div>

        <div class="view" data-view="decision">
          <div class="section-head">
            <div>
              <h2>Decision And Risk Posture</h2>
              <p>Severity distribution, recommendation framing, and the combined commercial, insurance, and compliance picture.</p>
            </div>
          </div>
          <div class="grid-2">
            <div class="subpanel" style="padding:18px;">
              <div class="eyebrow">Severity Mix</div>
              <div class="grid-2" id="severity-mix"></div>
            </div>
            <div class="subpanel" style="padding:18px;">
              <div class="eyebrow">Lifecycle Summary</div>
              <div id="decision-summary-table"></div>
            </div>
          </div>
        </div>

        <div class="view" data-view="review" data-internal-only="true">
          <div class="section-head">
            <div>
              <h2>Human Review Board</h2>
              <p>Capture operator dispositions, triage unresolved items, and keep a local review log alongside the generated analysis.</p>
            </div>
          </div>
          <div class="grid-3" id="review-stats"></div>
          <div class="grid-2" style="margin-top:16px;">
            <div class="subpanel" style="padding:18px;">
              <div class="eyebrow">Saved Review Actions</div>
              <div class="stack" id="review-board"></div>
            </div>
            <div class="subpanel" style="padding:18px;">
              <div class="eyebrow">Outstanding Review Queue</div>
              <div class="stack" id="review-candidates"></div>
            </div>
          </div>
        </div>

        <div class="view" data-view="findings">
          <div class="section-head">
            <div>
              <h2>Findings Workspace</h2>
              <p>Search, filter, and scan the latest commercial, insurance, and compliance findings.</p>
            </div>
          </div>
          <div class="control-row">
            <input id="finding-query" type="search" placeholder="Search findings, categories, or recommendations">
            <select id="finding-severity">
              <option value="all">All severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            <select id="finding-source">
              <option value="all">All source groups</option>
              <option value="commercial">Commercial</option>
              <option value="insurance">Insurance</option>
              <option value="compliance">Compliance</option>
            </select>
          </div>
          <div class="detail-layout">
            <div class="stack" id="findings-list"></div>
            <aside class="detail-panel">
              <div class="eyebrow">Selected Finding</div>
              <div class="stack" id="finding-detail"></div>
              <div class="detail-divider" data-internal-only="true"></div>
              <div class="eyebrow" data-internal-only="true">Review Action</div>
              <div id="finding-review-form" data-internal-only="true"></div>
            </aside>
          </div>
        </div>

        <div class="view" data-view="obligations">
          <div class="section-head">
            <div>
              <h2>Obligations And Alerts</h2>
              <p>Track the current committed baseline and its live monitoring status by queue, not by raw JSON.</p>
            </div>
          </div>
          <div class="control-row">
            <input id="obligation-query" type="search" placeholder="Search obligations or owners">
            <select id="obligation-status">
              <option value="all">All statuses</option>
              <option value="pending">Pending</option>
              <option value="due">Due</option>
              <option value="late">Late</option>
              <option value="satisfied">Satisfied</option>
            </select>
          </div>
          <div class="detail-layout">
            <div>
              <div class="columns" id="obligation-columns"></div>
              <div style="margin-top:18px;" class="stack" id="alerts-list"></div>
            </div>
            <aside class="detail-panel">
              <div class="eyebrow">Selected Obligation</div>
              <div class="stack" id="obligation-detail"></div>
              <div class="detail-divider" data-internal-only="true"></div>
              <div class="eyebrow" data-internal-only="true">Review Action</div>
              <div id="obligation-review-form" data-internal-only="true"></div>
            </aside>
          </div>
        </div>

        <div class="view" data-view="context" data-internal-only="true">
          <div class="section-head">
            <div>
              <h2>Internal Context Signals</h2>
              <p>Budget, board, audit, funding, and status signals that shape internal strategy without becoming outward-facing report language.</p>
            </div>
          </div>
          <div class="grid-2">
            <div class="subpanel" style="padding:18px;">
              <div class="eyebrow">Signal Levels</div>
              <div class="grid-2" id="context-metrics"></div>
            </div>
            <div class="subpanel" style="padding:18px;">
              <div class="eyebrow">Context Notes</div>
              <ul id="context-notes"></ul>
            </div>
          </div>
          <div class="stack" style="margin-top:16px;" id="context-signals"></div>
        </div>

        <div class="view" data-view="procurement">
          <div class="section-head">
            <div>
              <h2>Procurement And Outcome Profile</h2>
              <p>Delivery structure, clause families, governance traces, and what has happened in the project record so far.</p>
            </div>
          </div>
          <div class="grid-2">
            <div class="subpanel" style="padding:18px;">
              <div class="eyebrow">Procurement Profile</div>
              <div id="procurement-table"></div>
              <div class="chip-row" id="clause-family-chips" style="margin-top:14px;"></div>
            </div>
            <div class="subpanel" style="padding:18px;">
              <div class="eyebrow">Outcome Signals</div>
              <div class="stack" id="outcome-events"></div>
            </div>
          </div>
        </div>

        <div class="view" data-view="documents">
          <div class="section-head">
            <div>
              <h2>Document Inventory</h2>
              <p>Every document the latest run saw, with type, text readiness, and clause coverage.</p>
            </div>
          </div>
          <table class="doc-table">
            <thead>
              <tr>
                <th>Document</th>
                <th>Type</th>
                <th>Text source</th>
                <th>Clauses</th>
                <th>Required</th>
              </tr>
            </thead>
            <tbody id="documents-table"></tbody>
          </table>
        </div>

        <div class="view" data-view="history">
          <div class="section-head">
            <div>
              <h2>Lifecycle Timeline</h2>
              <p>See how the case moved from review into commitment and then into monitoring.</p>
            </div>
          </div>
          <div class="timeline" id="timeline"></div>
        </div>
      </section>
    </section>
  </div>

  <script>
    const dashboardData = __DASHBOARD_PAYLOAD__;
    const reviewStorageKey = `contract-intelligence-review-actions:${dashboardData.project_id}`;

    const navItems = [
      { key: "overview", label: "Overview", detail: "Executive posture" },
      { key: "decision", label: "Decision", detail: "Severity and rationale" },
      { key: "review", label: "Review", detail: "Human dispositions", internalOnly: true },
      { key: "findings", label: "Findings", detail: "Filter the risk set" },
      { key: "obligations", label: "Obligations", detail: "Current queues and alerts" },
      { key: "context", label: "Context", detail: "Internal-only signals", internalOnly: true },
      { key: "procurement", label: "Procurement", detail: "Structure and outcomes" },
      { key: "documents", label: "Documents", detail: "Inventory and text readiness" },
      { key: "history", label: "History", detail: "Lifecycle events" },
    ];

    const reportModeCopy = {
      internal: {
        lead: "A project command surface for review decisions, committed baselines, internal context, operational obligations, and live alert posture.",
        caption: "Internal mode keeps strategy-only signals, review controls, and human triage visible.",
      },
      external: {
        lead: "A shareable contract-operating summary for decision posture, committed obligations, procurement structure, and current project readiness.",
        caption: "External mode suppresses internal strategy panels and leaves a cleaner client-facing operational surface.",
      },
    };

    const uiState = {
      reportMode: "internal",
      activeView: "overview",
      selectedFindingId: null,
      selectedObligationId: null,
      reviewActions: loadReviewActions(),
    };

    function el(id) {
      return document.getElementById(id);
    }

    function fmt(value) {
      if (value === null || value === undefined || value === "") return "None";
      if (typeof value === "boolean") return value ? "Yes" : "No";
      return String(value);
    }

    function titleize(value) {
      return fmt(value).replace(/_/g, " ");
    }

    function escapeHtml(value) {
      return fmt(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function escapeAttr(value) {
      return escapeHtml(value);
    }

    function safe(value) {
      return escapeHtml(value);
    }

    function safeTitle(value) {
      return escapeHtml(titleize(value));
    }

    function emptyState(message) {
      return `<div class="empty">${escapeHtml(message)}</div>`;
    }

    function evidenceList(items) {
      if (!items || !items.length) {
        return '<p class="note">No evidence references were recorded.</p>';
      }
      return `
        <ul class="detail-list">
          ${items.map((item) => `
            <li>
              <strong>${safe(item.location)}</strong>
              ${item.excerpt ? `<div class="note">${safe(item.excerpt)}</div>` : ""}
            </li>
          `).join("")}
        </ul>
      `;
    }

    function loadReviewActions() {
      try {
        const raw = window.localStorage.getItem(reviewStorageKey);
        if (!raw) return {};
        const payload = JSON.parse(raw);
        return payload && typeof payload === "object" ? payload : {};
      } catch (error) {
        return {};
      }
    }

    function persistReviewActions() {
      window.localStorage.setItem(reviewStorageKey, JSON.stringify(uiState.reviewActions));
    }

    function reviewKey(kind, id) {
      return `${kind}:${id}`;
    }

    function getReviewRecord(kind, id) {
      return uiState.reviewActions[reviewKey(kind, id)] || null;
    }

    function reviewSummary() {
      const records = Object.values(uiState.reviewActions);
      const byDisposition = {
        needs_legal: 0,
        negotiate: 0,
        price_risk: 0,
        accept: 0,
        track: 0,
        escalate: 0,
        close: 0,
      };
      records.forEach((item) => {
        if (item && item.disposition && Object.prototype.hasOwnProperty.call(byDisposition, item.disposition)) {
          byDisposition[item.disposition] += 1;
        }
      });
      return {
        total: records.length,
        needsLegal: byDisposition.needs_legal + byDisposition.escalate,
        priced: byDisposition.price_risk,
        accepted: byDisposition.accept + byDisposition.close,
        tracked: byDisposition.track,
      };
    }

    function availableNavItems() {
      return navItems.filter((item) => uiState.reportMode === "internal" || !item.internalOnly);
    }

    function initNav() {
      const container = el("nav-list");
      container.innerHTML = availableNavItems().map((item) => `
        <button class="nav-button" data-target="${escapeAttr(item.key)}" aria-selected="${item.key === uiState.activeView ? "true" : "false"}">
          ${escapeHtml(item.label)}
          <small>${escapeHtml(item.detail)}</small>
        </button>
      `).join("");

      container.querySelectorAll(".nav-button").forEach((button) => {
        button.addEventListener("click", () => changeView(button.dataset.target));
      });
    }

    function changeView(viewKey) {
      const nextView = availableNavItems().some((item) => item.key === viewKey) ? viewKey : "overview";
      uiState.activeView = nextView;
      document.querySelectorAll(".nav-button").forEach((item) => {
        item.setAttribute("aria-selected", item.dataset.target === nextView ? "true" : "false");
      });
      document.querySelectorAll(".view").forEach((view) => {
        view.classList.toggle("active", view.dataset.view === nextView);
      });
    }

    function setReportMode(mode) {
      uiState.reportMode = mode === "external" ? "external" : "internal";
      document.body.dataset.reportMode = uiState.reportMode;
      document.querySelectorAll("[data-report-mode-control]").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.reportModeControl === uiState.reportMode);
      });
      const copy = reportModeCopy[uiState.reportMode];
      el("hero-lead").textContent = copy.lead;
      el("mode-caption").textContent = copy.caption;
      initNav();
      if (!availableNavItems().some((item) => item.key === uiState.activeView)) {
        uiState.activeView = "overview";
      }
      changeView(uiState.activeView);
      renderAll();
    }

    function renderHero() {
      const metrics = dashboardData.summary_metrics;
      el("project-title").textContent = dashboardData.project_id;
      el("hero-badges").innerHTML = [
        `<span class="badge risk">${safeTitle(metrics.recommendation)}</span>`,
        `<span class="badge warn">${safeTitle(metrics.overall_risk)} overall risk</span>`,
        `<span class="badge good">${safe(metrics.documents_count)} documents indexed</span>`,
        `<span class="badge">${safeTitle(uiState.reportMode)} mode</span>`,
      ].join("");
      el("confidence-fill").style.width = `${Math.max(6, Number(metrics.confidence || 0) * 100)}%`;

      const kpis = [
        ["Findings", metrics.findings_count],
        ["Obligations", metrics.obligations_count],
        ["Alerts", metrics.alerts_count],
        ["Must fix", metrics.must_fix_count],
      ];
      el("kpis").innerHTML = kpis.map(([label, value]) => `
        <div class="kpi">
          <div class="value">${safe(value)}</div>
          <div class="label">${safe(label)}</div>
        </div>
      `).join("");

      const review = reviewSummary();
      el("review-snapshot").innerHTML = [
        ["Saved actions", review.total],
        ["Legal or escalated", review.needsLegal],
        ["Priced", review.priced],
        ["Tracked", review.tracked],
      ].map(([label, value]) => `
        <div class="summary-pill">
          <span>${safe(label)}</span>
          <strong>${safe(value)}</strong>
        </div>
      `).join("");
    }

    function renderOverview() {
      const decision = dashboardData.latest_run.decision_summary || {};
      const review = reviewSummary();
      const stats = [
        ["Review runs", dashboardData.case_record.total_runs],
        ["Commits", dashboardData.case_record.total_commits],
        ["Monitoring runs", dashboardData.case_record.total_monitoring_runs],
        ["Confidence", decision.confidence],
        ["Late obligations", dashboardData.obligation_status_counts.late],
        ["Saved review actions", review.total],
      ];
      el("overview-stats").innerHTML = stats.map(([label, value]) => `
        <div class="stat-card">
          <div class="number">${safe(value)}</div>
          <div class="label">${safe(label)}</div>
        </div>
      `).join("");

      el("top-reasons").innerHTML = (decision.top_reasons || []).length ? (decision.top_reasons || []).map((reason) => `
        <div class="finding">
          <h3>${safe(reason)}</h3>
        </div>
      `).join("") : emptyState("No top reasons were recorded.");

      el("must-fix").innerHTML = (decision.must_fix_before_bid || []).length ? (decision.must_fix_before_bid || []).map((item) => `
        <div class="finding">
          <h3>${safe(item)}</h3>
        </div>
      `).join("") : emptyState("No must-fix items were recorded.");
    }

    function renderDecision() {
      const counts = dashboardData.severity_counts || {};
      el("severity-mix").innerHTML = Object.entries(counts).map(([severity, count]) => `
        <div class="stat-card">
          <div class="number severity-${escapeAttr(severity)}">${safe(count)}</div>
          <div class="label">${safeTitle(severity)}</div>
        </div>
      `).join("");

      const decision = dashboardData.latest_run.decision_summary || {};
      const summaryRows = [
        ["Recommendation", titleize(decision.recommendation)],
        ["Overall risk", titleize(decision.overall_risk)],
        ["Human review required", fmt(decision.human_review_required)],
        ["Report mode", titleize(uiState.reportMode)],
        ["Latest run id", dashboardData.case_record.latest_run_id],
        ["Latest commit id", dashboardData.case_record.latest_commit_id],
        ["Latest monitoring id", dashboardData.case_record.latest_monitoring_run_id],
      ];
      el("decision-summary-table").innerHTML = `
        <table class="doc-table">
          <tbody>
            ${summaryRows.map(([label, value]) => `<tr><th>${safe(label)}</th><td>${safe(value)}</td></tr>`).join("")}
          </tbody>
        </table>
      `;
    }

    function filteredFindings() {
      const query = el("finding-query").value.trim().toLowerCase();
      const severity = el("finding-severity").value;
      const source = el("finding-source").value;
      return (dashboardData.findings || []).filter((item) => {
        if (severity !== "all" && item.severity !== severity) return false;
        if (source !== "all" && item.source_group !== source) return false;
        if (!query) return true;
        return [item.title, item.category, item.summary, item.recommended_action, item.source_group]
          .join(" ")
          .toLowerCase()
          .includes(query);
      });
    }

    function lookupFinding(id) {
      return (dashboardData.findings || []).find((item) => item.ui_id === id) || null;
    }

    function ensureSelectedFinding(items) {
      if (!items.length) {
        uiState.selectedFindingId = null;
        return null;
      }
      if (!items.some((item) => item.ui_id === uiState.selectedFindingId)) {
        uiState.selectedFindingId = items[0].ui_id;
      }
      return items.find((item) => item.ui_id === uiState.selectedFindingId) || items[0];
    }

    function renderReviewForm(kind, target) {
      if (!target) return emptyState("Select an item to capture a human review action.");
      const record = getReviewRecord(kind, target.ui_id) || {};
      const options = kind === "finding"
        ? [
            ["needs_legal", "Needs legal review"],
            ["negotiate", "Negotiate"],
            ["price_risk", "Price risk"],
            ["accept", "Accept"],
            ["track", "Track only"],
          ]
        : [
            ["track", "Track"],
            ["escalate", "Escalate"],
            ["close", "Close"],
            ["accept", "Accept"],
          ];
      return `
        <div class="review-form" data-review-kind="${escapeAttr(kind)}" data-review-id="${escapeAttr(target.ui_id)}">
          <label>
            Disposition
            <select data-field="disposition">
              <option value="">Select disposition</option>
              ${options.map(([value, label]) => `<option value="${escapeAttr(value)}" ${record.disposition === value ? "selected" : ""}>${escapeHtml(label)}</option>`).join("")}
            </select>
          </label>
          <label>
            Owner
            <input type="text" data-field="owner" value="${escapeAttr(record.owner || "")}" placeholder="Legal, PM, estimator, compliance">
          </label>
          <label>
            Notes
            <textarea data-field="note" placeholder="Capture what should happen next.">${escapeHtml(record.note || "")}</textarea>
          </label>
          <div class="inline-actions">
            <button type="button" class="action-button" data-save-review="true" data-review-kind="${escapeAttr(kind)}" data-review-id="${escapeAttr(target.ui_id)}">Save action</button>
            <button type="button" class="action-button subtle" data-clear-review="true" data-review-kind="${escapeAttr(kind)}" data-review-id="${escapeAttr(target.ui_id)}">Clear</button>
          </div>
          <p class="note">${record.updatedAt ? `Saved ${safe(record.updatedAt)}` : "No saved action for this item yet."}</p>
        </div>
      `;
    }

    function renderFindingDetail(item) {
      if (!item) {
        el("finding-detail").innerHTML = emptyState("No findings match the current filters.");
        el("finding-review-form").innerHTML = emptyState("No item selected.");
        return;
      }
      el("finding-detail").innerHTML = `
        <article class="detail-card">
          <div class="meta">
            <span class="severity-${escapeAttr(item.severity)}">${safeTitle(item.severity)}</span>
            <span>${safeTitle(item.source_group)}</span>
            <span>${safeTitle(item.category)}</span>
          </div>
          <h3>${safe(item.title)}</h3>
          <p>${safe(item.summary)}</p>
          <p><strong>Recommended action:</strong> ${safe(item.recommended_action || "None")}</p>
          <p><strong>Confidence:</strong> ${safe(item.confidence)}</p>
          ${item.uncertainty_notes && item.uncertainty_notes.length ? `
            <div class="detail-divider"></div>
            <div class="eyebrow">Uncertainty Notes</div>
            <ul class="detail-list">${item.uncertainty_notes.map((note) => `<li>${safe(note)}</li>`).join("")}</ul>
          ` : ""}
          <div class="detail-divider"></div>
          <div class="eyebrow">Evidence</div>
          ${evidenceList(item.evidence || [])}
        </article>
      `;
      el("finding-review-form").innerHTML = renderReviewForm("finding", item);
    }

    function renderFindings() {
      const items = filteredFindings();
      const selected = ensureSelectedFinding(items);
      el("findings-list").innerHTML = items.length ? items.map((item) => `
        <article class="finding interactive-card ${item.ui_id === uiState.selectedFindingId ? "active" : ""}" data-select-finding="${escapeAttr(item.ui_id)}">
          <div class="meta">
            <span class="severity-${escapeAttr(item.severity)}">${safeTitle(item.severity)}</span>
            <span>${safeTitle(item.source_group)}</span>
            <span>${safeTitle(item.category)}</span>
          </div>
          <h3>${safe(item.title)}</h3>
          <p>${safe(item.summary || "No summary provided.")}</p>
          <p><strong>Recommended action:</strong> ${safe(item.recommended_action || "None")}</p>
        </article>
      `).join("") : emptyState("No findings match the current filters.");
      renderFindingDetail(selected);
    }

    function normalizedObligations() {
      const monitoredById = new Map((dashboardData.monitored_obligations || []).map((item) => [item.obligation_id, item]));
      return (dashboardData.obligations || []).map((item) => {
        const monitor = monitoredById.get(item.id) || {};
        return {
          ...item,
          monitorStatus: monitor.status || "pending",
          monitorSummary: monitor.summary || "Awaiting monitoring input.",
          notes: monitor.notes || [],
          nextDueAt: monitor.next_due_at || null,
          lastSatisfiedAt: monitor.last_satisfied_at || null,
        };
      });
    }

    function filteredObligations() {
      const query = el("obligation-query").value.trim().toLowerCase();
      const selectedStatus = el("obligation-status").value;
      return normalizedObligations().filter((item) => {
        if (selectedStatus !== "all" && item.monitorStatus !== selectedStatus) return false;
        if (!query) return true;
        return [item.title, item.owner_role, item.obligation_type, item.monitorSummary, item.source_clause].join(" ").toLowerCase().includes(query);
      });
    }

    function ensureSelectedObligation(items) {
      if (!items.length) {
        uiState.selectedObligationId = null;
        return null;
      }
      if (!items.some((item) => item.ui_id === uiState.selectedObligationId)) {
        uiState.selectedObligationId = items[0].ui_id;
      }
      return items.find((item) => item.ui_id === uiState.selectedObligationId) || items[0];
    }

    function relatedAlerts(obligationId) {
      return (dashboardData.alerts || []).filter((item) => item.obligation_id === obligationId);
    }

    function renderObligationDetail(item) {
      if (!item) {
        el("obligation-detail").innerHTML = emptyState("No obligations match the current filters.");
        el("obligation-review-form").innerHTML = emptyState("No item selected.");
        return;
      }
      const alerts = relatedAlerts(item.id);
      el("obligation-detail").innerHTML = `
        <article class="detail-card">
          <div class="meta">
            <span class="severity-${escapeAttr(item.severity_if_missed)}">${safeTitle(item.severity_if_missed)}</span>
            <span>${safeTitle(item.obligation_type)}</span>
            <span>${safeTitle(item.owner_role)}</span>
            <span>${safeTitle(item.monitorStatus)}</span>
          </div>
          <h3>${safe(item.title)}</h3>
          <p>${safe(item.monitorSummary)}</p>
          <p><strong>Source clause:</strong> ${safe(item.source_clause)}</p>
          <p><strong>Trigger:</strong> ${safe(item.trigger)}</p>
          <p><strong>Due rule:</strong> ${safe(item.due_rule)}</p>
          <p><strong>Next due:</strong> ${safe(item.nextDueAt)}</p>
          <p><strong>Last satisfied:</strong> ${safe(item.lastSatisfiedAt)}</p>
          ${item.notes && item.notes.length ? `
            <div class="detail-divider"></div>
            <div class="eyebrow">Monitoring Notes</div>
            <ul class="detail-list">${item.notes.map((note) => `<li>${safe(note)}</li>`).join("")}</ul>
          ` : ""}
          <div class="detail-divider"></div>
          <div class="eyebrow">Evidence</div>
          ${evidenceList(item.evidence || [])}
          <div class="detail-divider"></div>
          <div class="eyebrow">Related Alerts</div>
          ${alerts.length ? `<ul class="detail-list">${alerts.map((alert) => `<li>${safe(alert.summary)} (${safeTitle(alert.severity)})</li>`).join("")}</ul>` : '<p class="note">No related alerts are currently open.</p>'}
        </article>
      `;
      el("obligation-review-form").innerHTML = renderReviewForm("obligation", item);
    }

    function renderObligations() {
      const items = filteredObligations();
      const selected = ensureSelectedObligation(items);
      const columns = [
        ["late", "Late"],
        ["due", "Due"],
        ["pending", "Pending"],
        ["satisfied", "Satisfied"],
      ];

      el("obligation-columns").innerHTML = columns.map(([statusKey, label]) => {
        const cards = items.filter((item) => item.monitorStatus === statusKey);
        return `
          <section class="column">
            <h3>${safe(label)}</h3>
            <div class="stack">
              ${cards.length ? cards.map((item) => `
                <article class="obligation-card interactive-card ${item.ui_id === uiState.selectedObligationId ? "active" : ""}" data-select-obligation="${escapeAttr(item.ui_id)}">
                  <div class="meta">
                    <span class="severity-${escapeAttr(item.severity_if_missed)}">${safeTitle(item.severity_if_missed)}</span>
                    <span>${safeTitle(item.obligation_type)}</span>
                    <span>${safeTitle(item.owner_role)}</span>
                  </div>
                  <h3>${safe(item.title)}</h3>
                  <p>${safe(item.monitorSummary)}</p>
                  <p><strong>Trigger:</strong> ${safe(item.trigger)}</p>
                  <p><strong>Due rule:</strong> ${safe(item.due_rule)}</p>
                </article>
              `).join("") : emptyState(`No ${label.toLowerCase()} obligations.`)}
            </div>
          </section>
        `;
      }).join("");

      const alerts = dashboardData.alerts || [];
      el("alerts-list").innerHTML = alerts.length ? alerts.map((item) => `
        <article class="alert-card interactive-card" data-open-kind="obligation" data-open-id="${escapeAttr((normalizedObligations().find((obligation) => obligation.id === item.obligation_id) || {}).ui_id || "")}">
          <div class="meta">
            <span class="severity-${escapeAttr(item.severity)}">${safeTitle(item.severity)}</span>
            <span>${safeTitle(item.alert_type)}</span>
            <span>${safeTitle(item.status)}</span>
          </div>
          <h3>${safe(item.summary)}</h3>
          <p><strong>Obligation:</strong> ${safe(item.obligation_id)}</p>
        </article>
      `).join("") : emptyState("No open alerts are currently recorded.");

      renderObligationDetail(selected);
    }

    function renderContext() {
      const profile = dashboardData.latest_run.context_profile || { notes: [], signals: [] };
      const metrics = [
        ["Funding flexibility", profile.funding_flexibility],
        ["Schedule pressure", profile.schedule_pressure],
        ["Oversight intensity", profile.oversight_intensity],
        ["Public visibility", profile.public_visibility],
      ];

      el("context-metrics").innerHTML = metrics.map(([label, value]) => `
        <div class="stat-card">
          <div class="number">${safeTitle(value)}</div>
          <div class="label">${safe(label)}</div>
        </div>
      `).join("");

      el("context-notes").innerHTML = (profile.notes || []).length
        ? (profile.notes || []).map((note) => `<li>${safe(note)}</li>`).join("")
        : "<li>None</li>";

      el("context-signals").innerHTML = (profile.signals || []).length ? profile.signals.map((signal) => `
        <article class="signal-card">
          <div class="meta">
            <span>${safeTitle(signal.signal_type)}</span>
            <span>${safeTitle(signal.intensity)}</span>
            <span>internal only</span>
          </div>
          <h3>${safe(signal.summary)}</h3>
          ${evidenceList(signal.evidence || [])}
        </article>
      `).join("") : emptyState("No internal context signals were extracted.");
    }

    function renderProcurement() {
      const procurement = dashboardData.latest_run.procurement_profile || {};
      const outcome = dashboardData.latest_run.outcome_evidence || {};

      const rows = [
        ["Agreement type", procurement.agreement_type],
        ["Project sector", procurement.project_sector],
        ["Procurement method", procurement.procurement_method],
        ["Payment mechanism", procurement.payment_mechanism],
        ["Public text quality", procurement.public_text_quality],
        ["Outcome status", outcome.outcome_status],
      ];
      el("procurement-table").innerHTML = `
        <table class="doc-table">
          <tbody>
            ${rows.map(([label, value]) => `<tr><th>${safe(label)}</th><td>${safeTitle(value)}</td></tr>`).join("")}
          </tbody>
        </table>
      `;

      el("clause-family-chips").innerHTML = (procurement.detected_clause_families || []).length
        ? (procurement.detected_clause_families || []).map((item) => `<span class="chip">${safeTitle(item)}</span>`).join("")
        : '<span class="chip">No clause families tagged</span>';

      el("outcome-events").innerHTML = (outcome.events || []).length ? outcome.events.map((item) => `
        <article class="timeline-item">
          <div class="meta">
            <span>${safeTitle(item.event_type)}</span>
            <span>${safeTitle(item.source_document_type)}</span>
            <span>${safeTitle(item.evidence_source_type)}</span>
          </div>
          <h3>${safe(item.summary)}</h3>
          <p>${(item.impact_types || []).length ? `Impacts: ${(item.impact_types || []).map((impact) => safeTitle(impact)).join(", ")}` : "No explicit impact tags."}</p>
        </article>
      `).join("") : emptyState("No outcome events are recorded for the latest run.");
    }

    function renderDocuments() {
      const rows = dashboardData.documents || [];
      el("documents-table").innerHTML = rows.length ? rows.map((item) => `
        <tr>
          <td>${safe(item.filename)}</td>
          <td>${safeTitle(item.document_type)}</td>
          <td>${safeTitle(item.text_source)}</td>
          <td>${safe(item.clause_count)}</td>
          <td>${item.required_for_bid_review ? "Yes" : "No"}</td>
        </tr>
      `).join("") : `<tr><td colspan="5">No documents were recorded.</td></tr>`;
    }

    function renderHistory() {
      const timeline = dashboardData.timeline || [];
      el("timeline").innerHTML = timeline.length ? timeline.map((item) => `
        <article class="timeline-item">
          <div class="meta">
            <span>${safeTitle(item.kind)}</span>
            <span>${safe(item.created_at)}</span>
            <span>${safe(item.id)}</span>
          </div>
          <h3>${safeTitle(item.kind)} event</h3>
          <p>${safe(item.summary)}</p>
        </article>
      `).join("") : emptyState("No lifecycle events are available.");
    }

    function lookupObligation(id) {
      return normalizedObligations().find((item) => item.ui_id === id) || null;
    }

    function renderReviewBoard() {
      const records = Object.values(uiState.reviewActions).sort((left, right) => String(right.updatedAt || "").localeCompare(String(left.updatedAt || "")));
      const counts = reviewSummary();
      const candidates = [
        ...(dashboardData.findings || []).filter((item) => ["critical", "high"].includes(item.severity) && !getReviewRecord("finding", item.ui_id)).map((item) => ({
          kind: "finding",
          ui_id: item.ui_id,
          title: item.title,
          summary: item.recommended_action,
        })),
        ...normalizedObligations().filter((item) => ["late", "due"].includes(item.monitorStatus) && !getReviewRecord("obligation", item.ui_id)).map((item) => ({
          kind: "obligation",
          ui_id: item.ui_id,
          title: item.title,
          summary: item.monitorSummary,
        })),
      ];

      el("review-stats").innerHTML = [
        ["Saved actions", counts.total],
        ["Needs legal", counts.needsLegal],
        ["Priced", counts.priced],
      ].map(([label, value]) => `
        <div class="stat-card">
          <div class="number">${safe(value)}</div>
          <div class="label">${safe(label)}</div>
        </div>
      `).join("");

      el("review-board").innerHTML = records.length ? records.map((item) => `
        <article class="review-card">
          <div class="meta">
            <span>${safeTitle(item.kind)}</span>
            <span>${safeTitle(item.disposition)}</span>
            <span>${safe(item.owner || "Unassigned")}</span>
          </div>
          <h3>${safe(item.title || "Untitled item")}</h3>
          <p>${safe(item.note || "No note captured.")}</p>
          <p class="note">Saved ${safe(item.updatedAt)}</p>
          <div class="inline-actions">
            <button type="button" class="action-button subtle" data-open-kind="${escapeAttr(item.kind)}" data-open-id="${escapeAttr(item.ui_id)}">Open item</button>
          </div>
        </article>
      `).join("") : emptyState("No human review actions have been recorded yet.");

      el("review-candidates").innerHTML = candidates.length ? candidates.map((item) => `
        <article class="review-card">
          <div class="meta">
            <span>${safeTitle(item.kind)}</span>
            <span>needs disposition</span>
          </div>
          <h3>${safe(item.title)}</h3>
          <p>${safe(item.summary)}</p>
          <div class="inline-actions">
            <button type="button" class="action-button" data-open-kind="${escapeAttr(item.kind)}" data-open-id="${escapeAttr(item.ui_id)}">Review now</button>
          </div>
        </article>
      `).join("") : emptyState("The current high-signal queue already has a saved disposition.");
    }

    function saveReviewAction(kind, id) {
      const form = document.querySelector(`.review-form[data-review-kind="${kind}"][data-review-id="${id}"]`);
      if (!form) return;
      const disposition = form.querySelector('[data-field="disposition"]').value;
      const owner = form.querySelector('[data-field="owner"]').value.trim();
      const note = form.querySelector('[data-field="note"]').value.trim();
      const source = kind === "finding" ? lookupFinding(id) : lookupObligation(id);
      if (!disposition && !owner && !note) return;
      uiState.reviewActions[reviewKey(kind, id)] = {
        kind,
        ui_id: id,
        title: source ? source.title : id,
        disposition,
        owner,
        note,
        updatedAt: new Date().toISOString(),
      };
      persistReviewActions();
      renderAll();
    }

    function clearReviewAction(kind, id) {
      delete uiState.reviewActions[reviewKey(kind, id)];
      persistReviewActions();
      renderAll();
    }

    function openItem(kind, id) {
      if (!id) return;
      if (kind === "finding") {
        uiState.selectedFindingId = id;
        changeView("findings");
        renderFindings();
      } else if (kind === "obligation") {
        uiState.selectedObligationId = id;
        changeView("obligations");
        renderObligations();
      }
    }

    function bindControls() {
      [["finding-query", renderFindings], ["finding-severity", renderFindings], ["finding-source", renderFindings], ["obligation-query", renderObligations], ["obligation-status", renderObligations]].forEach(([id, fn]) => {
        const node = el(id);
        node.addEventListener("input", fn);
        node.addEventListener("change", fn);
      });

      document.querySelectorAll("[data-report-mode-control]").forEach((button) => {
        button.addEventListener("click", () => setReportMode(button.dataset.reportModeControl));
      });

      document.addEventListener("click", (event) => {
        const findingTarget = event.target.closest("[data-select-finding]");
        if (findingTarget) {
          uiState.selectedFindingId = findingTarget.dataset.selectFinding;
          renderFindings();
          return;
        }

        const obligationTarget = event.target.closest("[data-select-obligation]");
        if (obligationTarget) {
          uiState.selectedObligationId = obligationTarget.dataset.selectObligation;
          renderObligations();
          return;
        }

        const openTarget = event.target.closest("[data-open-kind]");
        if (openTarget) {
          openItem(openTarget.dataset.openKind, openTarget.dataset.openId);
          return;
        }

        const saveTarget = event.target.closest("[data-save-review]");
        if (saveTarget) {
          saveReviewAction(saveTarget.dataset.reviewKind, saveTarget.dataset.reviewId);
          return;
        }

        const clearTarget = event.target.closest("[data-clear-review]");
        if (clearTarget) {
          clearReviewAction(clearTarget.dataset.reviewKind, clearTarget.dataset.reviewId);
        }
      });
    }

    function renderAll() {
      renderHero();
      renderOverview();
      renderDecision();
      renderReviewBoard();
      renderFindings();
      renderObligations();
      renderContext();
      renderProcurement();
      renderDocuments();
      renderHistory();
    }

    function init() {
      initNav();
      setReportMode("internal");
      bindControls();
    }

    init();
  </script>
</body>
</html>
"""

    html_output = (
        html_template.replace("__DASHBOARD_PAYLOAD__", payload).replace("{{", "{").replace("}}", "}")
    )

    destination = (
        Path(output_path).expanduser().resolve()
        if output_path
        else project_path / "artifacts" / "contract_intelligence_dashboard.html"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html_output, encoding="utf-8")
    return destination
