from __future__ import annotations

import html
from pathlib import Path

from apps.contract_intelligence.orchestration.bid_review_runner import _project_id
from apps.contract_intelligence.storage import FileSystemCaseStore


def _escape(value: object) -> str:
    return html.escape("" if value is None else str(value))


def _list_items(items: list[str]) -> str:
    if not items:
        return "<li>None</li>"
    return "".join(f"<li>{_escape(item)}</li>" for item in items)


def _table(rows: list[tuple[str, str]]) -> str:
    cells = "".join(
        f"<tr><th>{_escape(label)}</th><td>{_escape(value)}</td></tr>"
        for label, value in rows
    )
    return f"<table>{cells}</table>"


def render_project_dashboard(project_dir: str | Path, *, output_path: str | Path | None = None) -> Path:
    project_path = Path(project_dir).expanduser().resolve()
    project_id = _project_id(project_path)
    store = FileSystemCaseStore(project_path / ".contract_intelligence")
    case_record = store.load_case_record(project_id)
    latest_run = store.load_latest_run_record(project_id)

    latest_commit = None
    obligations: list[object] = []
    latest_monitoring = None
    alerts: list[dict[str, object]] = []

    if case_record.latest_commit_id:
        latest_commit = store.load_latest_commit_record(project_id)
        obligations = store.load_current_obligations(project_id)
    if case_record.latest_monitoring_run_id:
        latest_monitoring = store.load_latest_monitoring_run(project_id)
        alerts = [item.model_dump(mode="json") for item in latest_monitoring.alerts]

    decision = latest_run.decision_summary
    context_profile = latest_run.context_profile
    procurement_profile = latest_run.procurement_profile
    outcome_evidence = latest_run.outcome_evidence

    html_output = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Contract Intelligence Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #132238;
      --muted: #5b6b7a;
      --line: #d8e0e8;
      --paper: #f4f6f8;
      --panel: #ffffff;
      --accent: #0f6c5a;
      --warn: #a55007;
      --risk: #9b1c1c;
    }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      background: linear-gradient(180deg, #eef4f3 0%, var(--paper) 100%);
      color: var(--ink);
    }}
    main {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 32px 20px 64px;
    }}
    .hero {{
      background: radial-gradient(circle at top left, rgba(15,108,90,0.15), transparent 48%), var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 24px;
      box-shadow: 0 20px 50px rgba(19,34,56,0.08);
    }}
    h1, h2 {{
      margin: 0 0 12px;
      font-weight: 700;
      letter-spacing: 0.01em;
    }}
    h1 {{
      font-size: 2rem;
    }}
    h2 {{
      font-size: 1.2rem;
      margin-top: 28px;
    }}
    p {{
      color: var(--muted);
      line-height: 1.5;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
      margin-top: 18px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
    }}
    .metric {{
      font-size: 1.8rem;
      font-weight: 700;
      margin-bottom: 6px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      overflow: hidden;
    }}
    th, td {{
      text-align: left;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{
      width: 240px;
      color: var(--muted);
      font-weight: 600;
    }}
    ul {{
      margin: 0;
      padding-left: 20px;
    }}
    .flag-risk {{ color: var(--risk); }}
    .flag-warn {{ color: var(--warn); }}
    .flag-good {{ color: var(--accent); }}
  </style>
</head>
<body>
<main>
  <section class="hero">
    <h1>{_escape(project_id)}</h1>
    <p>Lifecycle dashboard for contract review, commitment, monitoring, and internal context tracking.</p>
    <div class="grid">
      <div class="card">
        <div class="metric flag-risk">{_escape(decision.recommendation.value)}</div>
        <div>Latest recommendation</div>
      </div>
      <div class="card">
        <div class="metric">{_escape(decision.overall_risk.value)}</div>
        <div>Overall risk</div>
      </div>
      <div class="card">
        <div class="metric">{_escape(case_record.total_commits)}</div>
        <div>Committed baselines</div>
      </div>
      <div class="card">
        <div class="metric">{_escape(case_record.total_monitoring_runs)}</div>
        <div>Monitoring runs</div>
      </div>
    </div>
  </section>

  <h2>Decision Summary</h2>
  {_table([
      ("Human review required", str(decision.human_review_required)),
      ("Confidence", str(decision.confidence)),
      ("Latest run", case_record.latest_run_id),
      ("Latest commit", case_record.latest_commit_id or "None"),
      ("Latest monitoring run", case_record.latest_monitoring_run_id or "None"),
  ])}

  <h2>Top Reasons</h2>
  <div class="card"><ul>{_list_items(decision.top_reasons)}</ul></div>

  <h2>Internal Context</h2>
  {_table([
      ("Funding flexibility", context_profile.funding_flexibility),
      ("Schedule pressure", context_profile.schedule_pressure),
      ("Oversight intensity", context_profile.oversight_intensity),
      ("Public visibility", context_profile.public_visibility),
  ])}

  <h2>Procurement And Outcomes</h2>
  {_table([
      ("Agreement type", procurement_profile.agreement_type),
      ("Procurement method", procurement_profile.procurement_method),
      ("Payment mechanism", procurement_profile.payment_mechanism),
      ("Outcome status", outcome_evidence.outcome_status),
  ])}

  <h2>Current Obligations</h2>
  <div class="card">
    <ul>{_list_items([item.title for item in obligations])}</ul>
  </div>

  <h2>Current Alerts</h2>
  <div class="card">
    <ul>{_list_items([f"{item['alert_type']}: {item['summary']}" for item in alerts])}</ul>
  </div>
</main>
</body>
</html>
"""

    destination = Path(output_path).expanduser().resolve() if output_path else project_path / "artifacts" / "contract_intelligence_dashboard.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html_output, encoding="utf-8")
    return destination
