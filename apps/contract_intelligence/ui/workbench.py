from __future__ import annotations

import json
from typing import Any

from apps.contract_intelligence.demo import default_demo_site_dir, default_reference_root
from apps.contract_intelligence.evaluation.corpus import default_corpus_dir


def _command_catalog() -> list[dict[str, str]]:
    return [
        {
            "id": "bid-review",
            "label": "Deterministic review",
            "summary": "Run the fixed construction contract analysis flow over a local project package.",
            "cli": "uv run python -m apps.contract_intelligence bid-review <project_dir> --perspective <vendor|agency>",
        },
        {
            "id": "ensemble-review",
            "label": "AI ensemble review",
            "summary": "Run the same project through the model-backed orchestration path.",
            "cli": "uv run python -m apps.contract_intelligence ensemble-bid-review <project_dir> --perspective <vendor|agency>",
        },
        {
            "id": "commit",
            "label": "Commit package",
            "summary": "Persist negotiated dispositions and freeze the committed obligation baseline.",
            "cli": "uv run python -m apps.contract_intelligence commit <project_dir> --finding-dispositions-file <json>",
        },
        {
            "id": "monitor",
            "label": "Monitor",
            "summary": "Apply current status inputs and emit live alerts against the committed baseline.",
            "cli": "uv run python -m apps.contract_intelligence monitor <project_dir> --status-inputs-file <json>",
        },
        {
            "id": "render-dashboard",
            "label": "Render dashboard",
            "summary": "Generate an internal or external dashboard over persisted lifecycle state.",
            "cli": "uv run python -m apps.contract_intelligence render-dashboard <project_dir> --mode <internal|external>",
        },
        {
            "id": "extract-obligations",
            "label": "Extract obligations",
            "summary": "Copy the current committed obligation snapshot for downstream operators.",
            "cli": "uv run python -m apps.contract_intelligence extract-obligations <project_dir> --output-path <json>",
        },
        {
            "id": "evaluate-corpus",
            "label": "Evaluate corpus",
            "summary": "Run the shipped gold corpus and surface case-level pass/fail results.",
            "cli": "uv run python -m apps.contract_intelligence evaluate-corpus --corpus-dir <dir>",
        },
        {
            "id": "build-demo",
            "label": "Build demo",
            "summary": "Generate curated reference workspaces and sanitized demo-site assets.",
            "cli": "uv run python -m apps.contract_intelligence build-demo --corpus-dir <dir> --reference-root <dir> --site-dir <dir>",
        },
    ]


def workbench_bootstrap() -> dict[str, Any]:
    return {
        "product_name": "Intelligent Contract Management",
        "tagline": "Powered by Ensemble Systems Engineering",
        "default_perspective": "vendor",
        "defaults": {
            "corpus_dir": str(default_corpus_dir()),
            "reference_root": str(default_reference_root()),
            "site_dir": str(default_demo_site_dir()),
            "ensemble_artifacts_dir": "artifacts/contract_intelligence_ese",
        },
        "commands": _command_catalog(),
        "endpoints": {
            "workbench": "/workbench",
            "reference_manifest": "/reference/manifest",
            "analyze": "/projects/analyze",
            "ensemble_review": "/projects/ensemble-review",
            "commit": "/projects/commit",
            "monitor": "/projects/monitor",
            "render_dashboard": "/projects/render-dashboard",
            "dashboard_view": "/projects/dashboard/view",
            "extract_obligations": "/projects/extract-obligations",
            "state": "/projects/state",
            "latest_run": "/projects/runs/latest",
            "latest_commit": "/projects/commits/latest",
            "latest_monitoring": "/projects/monitoring/latest",
            "obligations": "/projects/obligations",
            "alerts": "/projects/alerts",
            "review_actions": "/projects/review-actions",
            "evaluate_corpus": "/evaluation/corpus",
            "build_demo": "/reference/build-demo",
        },
    }


def render_workbench_html() -> str:
    bootstrap = json.dumps(workbench_bootstrap()).replace("</", "<\\/")
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0c1416">
  <title>Intelligent Contract Management</title>
  <style>
    :root {
      --ink: #142125;
      --muted: #5b6766;
      --paper: rgba(251, 247, 240, 0.9);
      --paper-strong: rgba(255, 252, 247, 0.94);
      --line: rgba(20, 33, 37, 0.12);
      --line-strong: rgba(20, 33, 37, 0.22);
      --olive: #6f7f46;
      --olive-soft: rgba(111, 127, 70, 0.16);
      --copper: #c56a2d;
      --copper-soft: rgba(197, 106, 45, 0.16);
      --slate: #22343a;
      --cream: #fbf7f0;
      --shadow: 0 22px 60px rgba(13, 23, 28, 0.14);
      --radius-lg: 28px;
      --radius-md: 18px;
      --radius-sm: 12px;
      --mono: "IBM Plex Mono", "SFMono-Regular", Menlo, monospace;
      --sans: "Avenir Next", "Segoe UI", sans-serif;
      --serif: "Iowan Old Style", "Palatino Linotype", serif;
    }

    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }

    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: var(--sans);
      background:
        radial-gradient(circle at top left, rgba(111, 127, 70, 0.18), transparent 28%),
        radial-gradient(circle at 85% 10%, rgba(197, 106, 45, 0.16), transparent 26%),
        linear-gradient(180deg, #f6f0e7 0%, #f0ebe1 100%);
      position: relative;
      overflow-x: hidden;
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(rgba(20, 33, 37, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(20, 33, 37, 0.03) 1px, transparent 1px);
      background-size: 28px 28px;
      mask-image: radial-gradient(circle at 50% 10%, black 35%, transparent 78%);
      pointer-events: none;
      opacity: 0.8;
    }

    .shell {
      position: relative;
      z-index: 1;
      max-width: 1600px;
      margin: 0 auto;
      padding: 26px;
    }

    .masthead {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.65fr);
      gap: 20px;
      align-items: stretch;
      padding: 18px 0 24px;
      border-bottom: 1px solid var(--line);
      animation: rise 560ms ease both;
    }

    .brand-block {
      padding: 22px 6px 12px 0;
    }

    .kicker {
      margin: 0 0 14px;
      font-size: 0.78rem;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--olive);
      font-weight: 700;
    }

    h1 {
      margin: 0;
      font-family: var(--serif);
      font-weight: 700;
      letter-spacing: -0.04em;
      line-height: 0.95;
      font-size: clamp(2.6rem, 5vw, 4.9rem);
      max-width: 9ch;
    }

    .brand-mark {
      display: block;
      color: var(--copper);
      font-family: var(--sans);
      font-size: clamp(0.9rem, 1.1vw, 1rem);
      letter-spacing: 0.24em;
      text-transform: uppercase;
      margin-top: 16px;
      font-weight: 700;
    }

    .lede {
      max-width: 66ch;
      color: var(--muted);
      font-size: 1.02rem;
      line-height: 1.7;
      margin: 20px 0 0;
    }

    .mast-meta {
      display: grid;
      gap: 14px;
      align-content: start;
      padding: 18px;
      border-radius: var(--radius-lg);
      background:
        linear-gradient(180deg, rgba(255,255,255,0.55), rgba(255,255,255,0.22)),
        rgba(255, 252, 247, 0.7);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      backdrop-filter: blur(8px);
    }

    .mast-stat {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      padding: 12px 0;
      border-bottom: 1px solid var(--line);
      font-size: 0.95rem;
    }

    .mast-stat:last-child { border-bottom: 0; }
    .mast-stat strong { font-weight: 700; }

    .grid {
      display: grid;
      grid-template-columns: minmax(320px, 380px) minmax(0, 1fr);
      gap: 26px;
      margin-top: 28px;
      align-items: start;
    }

    aside {
      position: sticky;
      top: 20px;
      display: grid;
      gap: 18px;
    }

    .rail-panel,
    .stage {
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      background:
        linear-gradient(180deg, rgba(255,255,255,0.45), rgba(255,255,255,0.16)),
        var(--paper);
      box-shadow: var(--shadow);
      overflow: hidden;
      animation: rise 620ms ease both;
    }

    .rail-panel .inner,
    .stage .inner {
      padding: 22px;
    }

    .rail-panel header,
    .stage header {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: flex-start;
      padding: 18px 22px 0;
    }

    .section-tag {
      margin: 0;
      font-family: var(--mono);
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }

    h2, h3 {
      margin: 6px 0 0;
      font-size: 1.32rem;
      line-height: 1.08;
      letter-spacing: -0.02em;
    }

    .section-copy {
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 0.96rem;
      line-height: 1.65;
      max-width: 70ch;
    }

    .nav-strip {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 24px;
    }

    .nav-strip a,
    .quick-link,
    .button,
    button {
      appearance: none;
      border: 0;
      text-decoration: none;
      border-radius: 999px;
      cursor: pointer;
      font: inherit;
      transition: transform 180ms ease, box-shadow 180ms ease, background 180ms ease;
    }

    .nav-strip a,
    .quick-link {
      padding: 11px 16px;
      color: var(--ink);
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.55);
    }

    .nav-strip a:hover,
    .quick-link:hover,
    .button:hover,
    button:hover {
      transform: translateY(-1px);
      box-shadow: 0 10px 24px rgba(20, 33, 37, 0.08);
    }

    .button,
    button.primary {
      padding: 12px 18px;
      background: linear-gradient(135deg, var(--slate), #152126);
      color: white;
      font-weight: 700;
    }

    button.secondary {
      padding: 12px 18px;
      background: rgba(255,255,255,0.5);
      color: var(--ink);
      border: 1px solid var(--line);
      font-weight: 700;
    }

    .status-chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      font-family: var(--mono);
      font-size: 0.74rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      background: var(--olive-soft);
      color: var(--olive);
      border: 1px solid rgba(111, 127, 70, 0.2);
    }

    .status-chip.warning {
      background: var(--copper-soft);
      color: var(--copper);
      border-color: rgba(197, 106, 45, 0.22);
    }

    .form-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }

    .form-grid.single {
      grid-template-columns: 1fr;
    }

    label {
      display: grid;
      gap: 8px;
      font-size: 0.9rem;
      color: var(--muted);
    }

    label span {
      font-family: var(--mono);
      font-size: 0.76rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }

    input,
    select,
    textarea {
      width: 100%;
      border: 1px solid rgba(20, 33, 37, 0.16);
      border-radius: var(--radius-sm);
      background: rgba(255,255,255,0.78);
      color: var(--ink);
      font: inherit;
      padding: 13px 14px;
      transition: border-color 180ms ease, box-shadow 180ms ease, background 180ms ease;
    }

    textarea {
      min-height: 110px;
      resize: vertical;
    }

    input:focus,
    select:focus,
    textarea:focus {
      outline: none;
      border-color: rgba(197, 106, 45, 0.5);
      box-shadow: 0 0 0 4px rgba(197, 106, 45, 0.12);
      background: white;
    }

    .path-field {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
    }

    .path-field input {
      min-width: 0;
    }

    .browse-button {
      padding: 13px 16px;
      border-radius: var(--radius-sm);
      background: rgba(20, 33, 37, 0.06);
      color: var(--ink);
      border: 1px solid rgba(20, 33, 37, 0.14);
      font-family: var(--mono);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-weight: 700;
      white-space: nowrap;
    }

    .browse-button:disabled {
      cursor: not-allowed;
      opacity: 0.45;
      box-shadow: none;
      transform: none;
    }

    .field-note {
      color: var(--muted);
      font-size: 0.85rem;
      line-height: 1.55;
      margin-top: -2px;
    }

    .form-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      margin-top: 18px;
    }

    .command-line {
      margin-top: 16px;
      padding: 14px 16px;
      border-radius: var(--radius-md);
      background: rgba(20, 33, 37, 0.06);
      border: 1px solid rgba(20, 33, 37, 0.08);
      font-family: var(--mono);
      font-size: 0.82rem;
      color: var(--ink);
      overflow-wrap: anywhere;
    }

    .stage-stack {
      display: grid;
      gap: 22px;
    }

    .stage .inner {
      display: grid;
      gap: 20px;
    }

    .split {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      align-items: start;
    }

    .subpanel {
      padding: 18px;
      border-radius: var(--radius-md);
      background: var(--paper-strong);
      border: 1px solid rgba(20, 33, 37, 0.08);
    }

    .subpanel h3 {
      font-size: 1.06rem;
      margin: 0 0 10px;
    }

    .subpanel p {
      margin: 0 0 16px;
      color: var(--muted);
      line-height: 1.6;
      font-size: 0.92rem;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .summary-tile {
      padding: 14px;
      border-radius: var(--radius-md);
      background: rgba(255,255,255,0.56);
      border: 1px solid rgba(20, 33, 37, 0.08);
    }

    .summary-tile .label {
      display: block;
      font-family: var(--mono);
      font-size: 0.7rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }

    .summary-tile strong {
      display: block;
      margin-top: 6px;
      font-size: 1.2rem;
      letter-spacing: -0.02em;
    }

    .summary-list,
    .case-list,
    .activity-list,
    .command-list {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 10px;
    }

    .summary-list li,
    .case-list li,
    .activity-list li,
    .command-list li {
      padding: 14px 0;
      border-top: 1px solid var(--line);
    }

    .summary-list li:first-child,
    .case-list li:first-child,
    .activity-list li:first-child,
    .command-list li:first-child {
      border-top: 0;
      padding-top: 0;
    }

    .summary-row {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: flex-start;
      font-size: 0.95rem;
    }

    .summary-row .label {
      color: var(--muted);
    }

    .pill-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
    }

    .pill {
      padding: 8px 10px;
      border-radius: 999px;
      background: rgba(20, 33, 37, 0.07);
      font-size: 0.8rem;
      color: var(--ink);
    }

    .dashboard-links {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .empty {
      color: var(--muted);
      font-size: 0.94rem;
      line-height: 1.6;
      padding: 14px 0;
    }

    .activity-list li strong,
    .case-list li strong,
    .command-list li strong {
      display: block;
      font-size: 0.98rem;
    }

    .meta {
      margin-top: 6px;
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.55;
    }

    .json-preview {
      margin-top: 14px;
      padding: 16px;
      border-radius: var(--radius-md);
      background: #11191b;
      color: #e5f1ef;
      font-family: var(--mono);
      font-size: 0.8rem;
      max-height: 360px;
      overflow: auto;
      white-space: pre-wrap;
    }

    .toast {
      position: fixed;
      right: 24px;
      bottom: 24px;
      max-width: min(420px, calc(100vw - 32px));
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(20, 33, 37, 0.94);
      color: white;
      box-shadow: 0 18px 36px rgba(20, 33, 37, 0.2);
      transform: translateY(22px);
      opacity: 0;
      pointer-events: none;
      transition: opacity 220ms ease, transform 220ms ease;
      z-index: 10;
    }

    .toast.is-visible {
      opacity: 1;
      transform: translateY(0);
    }

    .toast.error {
      background: rgba(124, 36, 16, 0.95);
    }

    .scanline {
      position: relative;
      overflow: hidden;
    }

    .scanline::after {
      content: "";
      position: absolute;
      inset: -20% 0 auto;
      height: 38%;
      background: linear-gradient(180deg, transparent, rgba(197,106,45,0.1), transparent);
      animation: scan 7.2s linear infinite;
      pointer-events: none;
    }

    @keyframes scan {
      from { transform: translateY(-120%); }
      to { transform: translateY(340%); }
    }

    @keyframes rise {
      from {
        opacity: 0;
        transform: translateY(14px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    @media (max-width: 1180px) {
      .grid,
      .masthead,
      .split,
      .form-grid {
        grid-template-columns: 1fr;
      }

      aside {
        position: static;
      }

      .shell {
        padding: 18px;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="masthead">
      <section class="brand-block">
        <p class="kicker">Contract-specific desktop surface</p>
        <h1>Intelligent Contract Management</h1>
        <span class="brand-mark">Powered by Ensemble Systems Engineering</span>
        <p class="lede">
          Run pre-award review, model-backed analysis, commitment, obligation extraction,
          monitoring, and dashboard generation from one local operator workbench. Every lane
          below maps back to a real contract-intelligence command, not a demo-only wrapper.
        </p>
        <nav class="nav-strip" aria-label="Section navigation">
          <a href="#review-stage">Review</a>
          <a href="#commit-stage">Commit</a>
          <a href="#monitor-stage">Monitor</a>
          <a href="#outputs-stage">Outputs</a>
          <a href="#validation-stage">Validation</a>
        </nav>
      </section>
      <section class="mast-meta scanline">
        <div class="mast-stat"><span>Surface</span><strong>ICM Workbench</strong></div>
        <div class="mast-stat"><span>Platform posture</span><strong>macOS first</strong></div>
        <div class="mast-stat"><span>Future targets</span><strong>Windows and SaaS</strong></div>
        <div class="mast-stat"><span>Runtime model</span><strong>Private loopback API + native webview</strong></div>
      </section>
    </header>

    <div class="grid">
      <aside>
        <section class="rail-panel scanline">
          <header>
            <div>
              <p class="section-tag">Workspace</p>
              <h2>Operator context</h2>
              <p class="section-copy">Set the active project once, then run the lifecycle from left to right.</p>
            </div>
            <span class="status-chip" id="ready-chip">Idle</span>
          </header>
          <div class="inner">
            <div class="form-grid single">
              <label>
                <span>Project directory</span>
                <input id="workspace-project-dir" type="text" placeholder="/absolute/path/to/project" autocomplete="off" data-picker="directory">
              </label>
              <label>
                <span>Perspective</span>
                <select id="workspace-perspective">
                  <option value="vendor">Vendor</option>
                  <option value="agency">Agency</option>
                </select>
              </label>
            </div>
            <div class="form-actions">
              <button class="primary" id="refresh-state" type="button">Refresh project state</button>
              <a class="quick-link" id="internal-dashboard-link" href="#" target="_blank" rel="noreferrer">Open internal preview</a>
              <a class="quick-link" id="external-dashboard-link" href="#" target="_blank" rel="noreferrer">Open external preview</a>
            </div>
            <p class="field-note">Dashboard preview links render the latest persisted project state through the local API.</p>
          </div>
        </section>

        <section class="rail-panel">
          <header>
            <div>
              <p class="section-tag">State</p>
              <h2>Project pulse</h2>
            </div>
          </header>
          <div class="inner">
            <div class="summary-grid" id="summary-grid">
              <div class="summary-tile"><span class="label">Review runs</span><strong>0</strong></div>
              <div class="summary-tile"><span class="label">Commits</span><strong>0</strong></div>
              <div class="summary-tile"><span class="label">Monitoring runs</span><strong>0</strong></div>
              <div class="summary-tile"><span class="label">Open alerts</span><strong>0</strong></div>
            </div>
            <ul class="summary-list" id="state-list">
              <li class="empty">Select a project directory and refresh to load the latest run, commit, monitoring, and obligation state.</li>
            </ul>
            <div class="pill-row" id="reason-pills"></div>
          </div>
        </section>

        <section class="rail-panel">
          <header>
            <div>
              <p class="section-tag">Reference</p>
              <h2>Curated cases</h2>
            </div>
          </header>
          <div class="inner">
            <ul class="case-list" id="reference-cases">
              <li class="empty">Loading reference manifest…</li>
            </ul>
          </div>
        </section>
      </aside>

      <main class="stage-stack">
        <section class="stage" id="review-stage">
          <header>
            <div>
              <p class="section-tag">Stage 01</p>
              <h2>Review</h2>
              <p class="section-copy">Start with deterministic review, then escalate to the model-backed ensemble path when you want the orchestration substrate involved.</p>
            </div>
          </header>
          <div class="inner">
            <div class="split">
              <section class="subpanel">
                <h3>Deterministic review</h3>
                <p>Runs the fixed contract reviewer over the active project and writes the standard lifecycle artifacts.</p>
                <form class="operation-form" data-endpoint="/projects/analyze" data-command="uv run python -m apps.contract_intelligence bid-review <project_dir> --perspective <vendor|agency>">
                  <input type="hidden" name="project_dir" data-shared="project_dir">
                  <input type="hidden" name="analysis_perspective" data-shared="analysis_perspective">
                  <div class="form-grid single">
                    <label>
                      <span>Artifacts directory</span>
                      <input type="text" name="artifacts_dir" placeholder="Optional output directory" data-picker="directory">
                    </label>
                  </div>
                  <div class="form-actions">
                    <button class="primary" type="submit">Run deterministic review</button>
                  </div>
                </form>
              </section>

              <section class="subpanel">
                <h3>AI ensemble review</h3>
                <p>Exposes the orchestration-backed review lane without putting ESE branding into the product surface.</p>
                <form class="operation-form" data-endpoint="/projects/ensemble-review" data-command="uv run python -m apps.contract_intelligence ensemble-bid-review <project_dir> --perspective <vendor|agency>">
                  <input type="hidden" name="project_dir" data-shared="project_dir">
                  <input type="hidden" name="analysis_perspective" data-shared="analysis_perspective">
                  <div class="form-grid">
                    <label>
                      <span>Provider</span>
                      <select name="provider">
                        <option value="local">Local</option>
                        <option value="openai">OpenAI</option>
                        <option value="custom_api">Custom API</option>
                      </select>
                    </label>
                    <label>
                      <span>Execution mode</span>
                      <select name="execution_mode">
                        <option value="demo">Demo</option>
                        <option value="auto">Auto</option>
                        <option value="live">Live</option>
                      </select>
                    </label>
                    <label>
                      <span>Artifacts directory</span>
                      <input type="text" name="artifacts_dir" id="ensemble-artifacts-dir" data-picker="directory">
                    </label>
                    <label>
                      <span>Model override</span>
                      <input type="text" name="model" placeholder="Optional model">
                    </label>
                    <label>
                      <span>Base URL</span>
                      <input type="text" name="base_url" placeholder="Optional runtime base URL">
                    </label>
                    <label>
                      <span>Config output path</span>
                      <input type="text" name="write_config_path" placeholder="Optional generated config path" data-picker="save-file" data-save-filename="contract-intelligence-ese.config.yaml" data-file-types="YAML files (*.yaml;*.yml)">
                    </label>
                  </div>
                  <div class="form-actions">
                    <button class="primary" type="submit">Run AI ensemble review</button>
                  </div>
                </form>
              </section>
            </div>
          </div>
        </section>

        <section class="stage" id="commit-stage">
          <header>
            <div>
              <p class="section-tag">Stage 02</p>
              <h2>Commit</h2>
              <p class="section-copy">Capture negotiated outcomes and freeze the obligation baseline that field operations will inherit.</p>
            </div>
          </header>
          <div class="inner">
            <form class="operation-form" data-endpoint="/projects/commit" data-command="uv run python -m apps.contract_intelligence commit <project_dir> --finding-dispositions-file <json>">
              <input type="hidden" name="project_dir" data-shared="project_dir">
              <div class="form-grid">
                <label>
                  <span>Committed contract directory</span>
                  <input type="text" name="committed_contract_dir" placeholder="Optional final contract package directory" data-picker="directory">
                </label>
                <label>
                  <span>Finding dispositions file</span>
                  <input type="text" name="finding_dispositions_file" placeholder="JSON file with commit dispositions" data-picker="open-file" data-file-types="JSON files (*.json)">
                </label>
                <label>
                  <span>Accepted risks file</span>
                  <input type="text" name="accepted_risks_file" placeholder="Legacy optional JSON file" data-picker="open-file" data-file-types="JSON files (*.json)">
                </label>
                <label>
                  <span>Negotiated changes file</span>
                  <input type="text" name="negotiated_changes_file" placeholder="Optional JSON file" data-picker="open-file" data-file-types="JSON files (*.json)">
                </label>
              </div>
              <div class="form-actions">
                <button class="primary" type="submit">Create committed baseline</button>
              </div>
            </form>
          </div>
        </section>

        <section class="stage" id="monitor-stage">
          <header>
            <div>
              <p class="section-tag">Stage 03</p>
              <h2>Monitor</h2>
              <p class="section-copy">Apply live field status inputs, generate alerts, and track whether commitments are drifting off the committed baseline.</p>
            </div>
          </header>
          <div class="inner">
            <form class="operation-form" data-endpoint="/projects/monitor" data-command="uv run python -m apps.contract_intelligence monitor <project_dir> --status-inputs-file <json>">
              <input type="hidden" name="project_dir" data-shared="project_dir">
              <div class="form-grid single">
                <label>
                  <span>Status inputs file</span>
                  <input type="text" name="status_inputs_file" placeholder="JSON list of live obligation statuses" data-picker="open-file" data-file-types="JSON files (*.json)">
                </label>
              </div>
              <div class="form-actions">
                <button class="primary" type="submit">Run monitoring</button>
              </div>
            </form>
          </div>
        </section>

        <section class="stage" id="outputs-stage">
          <header>
            <div>
              <p class="section-tag">Stage 04</p>
              <h2>Outputs</h2>
              <p class="section-copy">Export obligation data and generate internal or sanitized dashboard views from the same persisted lifecycle state.</p>
            </div>
          </header>
          <div class="inner">
            <div class="split">
              <section class="subpanel">
                <h3>Render dashboard</h3>
                <p>Write a dashboard artifact and keep a live preview route available through the local API.</p>
                <form class="operation-form" data-endpoint="/projects/render-dashboard" data-command="uv run python -m apps.contract_intelligence render-dashboard <project_dir> --mode <internal|external>">
                  <input type="hidden" name="project_dir" data-shared="project_dir">
                  <div class="form-grid">
                    <label>
                      <span>Mode</span>
                      <select name="mode">
                        <option value="internal">Internal</option>
                        <option value="external">External</option>
                      </select>
                    </label>
                    <label>
                      <span>Output path</span>
                      <input type="text" name="output_path" placeholder="Optional HTML output path" data-picker="save-file" data-save-filename="contract_intelligence_dashboard.html" data-file-types="HTML files (*.html)">
                    </label>
                  </div>
                  <div class="form-actions">
                    <button class="primary" type="submit">Render dashboard</button>
                  </div>
                </form>
                <div class="dashboard-links" style="margin-top:16px;">
                  <a class="quick-link" id="internal-dashboard-link-inline" href="#" target="_blank" rel="noreferrer">Internal preview</a>
                  <a class="quick-link" id="external-dashboard-link-inline" href="#" target="_blank" rel="noreferrer">External preview</a>
                </div>
              </section>

              <section class="subpanel">
                <h3>Extract obligations</h3>
                <p>Copy the current obligation snapshot for downstream operations, audit, or external system handoff.</p>
                <form class="operation-form" data-endpoint="/projects/extract-obligations" data-command="uv run python -m apps.contract_intelligence extract-obligations <project_dir> --output-path <json>">
                  <input type="hidden" name="project_dir" data-shared="project_dir">
                  <div class="form-grid single">
                    <label>
                      <span>Output path</span>
                      <input type="text" name="output_path" placeholder="Optional JSON destination" data-picker="save-file" data-save-filename="obligations.json" data-file-types="JSON files (*.json)">
                    </label>
                  </div>
                  <div class="form-actions">
                    <button class="primary" type="submit">Extract obligations</button>
                  </div>
                </form>
              </section>
            </div>
          </div>
        </section>

        <section class="stage" id="validation-stage">
          <header>
            <div>
              <p class="section-tag">Stage 05</p>
              <h2>Validation and reference</h2>
              <p class="section-copy">Run the shipped corpus or regenerate reference cases without dropping into the terminal.</p>
            </div>
          </header>
          <div class="inner">
            <div class="split">
              <section class="subpanel">
                <h3>Evaluate corpus</h3>
                <p>Execute the deterministic gold corpus and return pass or fail by case.</p>
                <form class="operation-form" data-endpoint="/evaluation/corpus" data-command="uv run python -m apps.contract_intelligence evaluate-corpus --corpus-dir <dir>">
                  <div class="form-grid">
                    <label>
                      <span>Corpus directory</span>
                      <input type="text" name="corpus_dir" id="corpus-dir-input" data-picker="directory">
                    </label>
                    <label>
                      <span>Artifacts directory</span>
                      <input type="text" name="artifacts_dir" placeholder="Optional evaluation artifacts root" data-picker="directory">
                    </label>
                  </div>
                  <div class="form-actions">
                    <button class="primary" type="submit">Evaluate corpus</button>
                  </div>
                </form>
              </section>

              <section class="subpanel">
                <h3>Build demo assets</h3>
                <p>Rebuild the curated reference cases and sanitized demo-site payloads served by the local API.</p>
                <form class="operation-form" data-endpoint="/reference/build-demo" data-command="uv run python -m apps.contract_intelligence build-demo --corpus-dir <dir> --reference-root <dir> --site-dir <dir>">
                  <div class="form-grid">
                    <label>
                      <span>Corpus directory</span>
                      <input type="text" name="corpus_dir" id="demo-corpus-dir-input" data-picker="directory">
                    </label>
                    <label>
                      <span>Reference root</span>
                      <input type="text" name="reference_root" id="reference-root-input" data-picker="directory">
                    </label>
                    <label>
                      <span>Site directory</span>
                      <input type="text" name="site_dir" id="site-dir-input" data-picker="directory">
                    </label>
                  </div>
                  <div class="form-actions">
                    <button class="primary" type="submit">Build demo</button>
                  </div>
                </form>
              </section>
            </div>
          </div>
        </section>

        <section class="stage">
          <header>
            <div>
              <p class="section-tag">Command map</p>
              <h2>CLI parity</h2>
              <p class="section-copy">The workbench mirrors the published contract-intelligence command surface. Use the catalog below to confirm what each lane maps to.</p>
            </div>
          </header>
          <div class="inner">
            <ul class="command-list" id="command-list"></ul>
          </div>
        </section>

        <section class="stage">
          <header>
            <div>
              <p class="section-tag">Activity</p>
              <h2>Execution feed</h2>
              <p class="section-copy">Recent responses, emitted paths, and the last raw payload returned by the local API.</p>
            </div>
          </header>
          <div class="inner">
            <ul class="activity-list" id="activity-list">
              <li class="empty">Run a command to populate the local execution feed.</li>
            </ul>
            <div class="json-preview" id="json-preview">{}</div>
          </div>
        </section>
      </main>
    </div>
  </div>

  <div class="toast" id="toast" role="status" aria-live="polite"></div>

  <script>
    window.ICM_WORKBENCH_BOOTSTRAP = __ICM_WORKBENCH_BOOTSTRAP__;
  </script>
  <script>
    const bootstrap = window.ICM_WORKBENCH_BOOTSTRAP;
    const state = {
      activity: [],
      lastPayload: {},
    };

    const $ = (id) => document.getElementById(id);

    function currentProjectDir() {
      return $("workspace-project-dir").value.trim();
    }

    function currentPerspective() {
      return $("workspace-perspective").value;
    }

    function showToast(message, type = "info") {
      const node = $("toast");
      node.textContent = message;
      node.className = `toast ${type === "error" ? "error" : ""} is-visible`;
      window.clearTimeout(showToast._timer);
      showToast._timer = window.setTimeout(() => {
        node.className = "toast";
      }, 3200);
    }

    function setReadyChip(label, warning = false) {
      const chip = $("ready-chip");
      chip.textContent = label;
      chip.className = `status-chip${warning ? " warning" : ""}`;
    }

    function syncSharedInputs() {
      const projectDir = currentProjectDir();
      const perspective = currentPerspective();
      document.querySelectorAll('[data-shared="project_dir"]').forEach((input) => {
        input.value = projectDir;
      });
      document.querySelectorAll('[data-shared="analysis_perspective"]').forEach((input) => {
        input.value = perspective;
      });

      const viewBase = projectDir
        ? `${bootstrap.endpoints.dashboard_view}?project_dir=${encodeURIComponent(projectDir)}`
        : "#";
      const links = [
        $("internal-dashboard-link"),
        $("internal-dashboard-link-inline"),
      ];
      const externalLinks = [
        $("external-dashboard-link"),
        $("external-dashboard-link-inline"),
      ];
      links.forEach((link) => {
        link.href = projectDir ? `${viewBase}&mode=internal` : "#";
        link.style.pointerEvents = projectDir ? "auto" : "none";
        link.style.opacity = projectDir ? "1" : "0.45";
      });
      externalLinks.forEach((link) => {
        link.href = projectDir ? `${viewBase}&mode=external` : "#";
        link.style.pointerEvents = projectDir ? "auto" : "none";
        link.style.opacity = projectDir ? "1" : "0.45";
      });
    }

    function formPayload(form) {
      const payload = {};
      const data = new FormData(form);
      for (const [key, value] of data.entries()) {
        if (typeof value === "string" && value.trim() !== "") {
          payload[key] = value.trim();
        }
      }
      form.querySelectorAll('input[type="checkbox"]').forEach((input) => {
        payload[input.name] = input.checked;
      });
      return payload;
    }

    async function fetchJson(url, options = {}) {
      const response = await fetch(url, options);
      const text = await response.text();
      let payload;
      try {
        payload = text ? JSON.parse(text) : {};
      } catch {
        payload = { raw: text };
      }
      if (!response.ok) {
        const detail = payload && typeof payload === "object" ? payload.detail || payload.message : text;
        throw new Error(detail || `Request failed with status ${response.status}`);
      }
      return payload;
    }

    function recordActivity(label, payload) {
      state.lastPayload = payload;
      state.activity.unshift({
        label,
        at: new Date().toLocaleTimeString(),
        payload,
      });
      state.activity = state.activity.slice(0, 10);
      renderActivity();
    }

    function renderActivity() {
      const list = $("activity-list");
      if (!state.activity.length) {
        list.innerHTML = '<li class="empty">Run a command to populate the local execution feed.</li>';
      } else {
        list.innerHTML = state.activity.map((item) => {
          const summary = summarizePayload(item.payload);
          return `
            <li>
              <strong>${escapeHtml(item.label)}</strong>
              <div class="meta">${escapeHtml(item.at)}${summary ? ` · ${escapeHtml(summary)}` : ""}</div>
            </li>
          `;
        }).join("");
      }
      $("json-preview").textContent = JSON.stringify(state.lastPayload, null, 2);
    }

    function summarizePayload(payload) {
      if (!payload || typeof payload !== "object") return "";
      if (payload.recommendation) return `Recommendation: ${payload.recommendation}`;
      if (payload.commit_id) return `Commit ${payload.commit_id}`;
      if (payload.run_id) return `Monitoring run ${payload.run_id}`;
      if (payload.dashboard_path) return `Dashboard written`;
      if (payload.obligations_count !== undefined) return `${payload.obligations_count} obligations`;
      if (payload.passed_cases !== undefined) return `${payload.passed_cases}/${payload.total_cases} cases passed`;
      if (payload.cases && Array.isArray(payload.cases)) return `${payload.cases.length} reference cases`;
      return "";
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    let desktopPathApiPromise = null;

    function desktopPathBridge() {
      if (window.pywebview?.api?.choose_path) {
        return Promise.resolve(window.pywebview.api);
      }
      if (!desktopPathApiPromise) {
        desktopPathApiPromise = new Promise((resolve) => {
          const finish = () => resolve(window.pywebview?.api?.choose_path ? window.pywebview.api : null);
          const onReady = () => finish();
          window.addEventListener("pywebviewready", onReady, { once: true });
          window.setTimeout(() => {
            window.removeEventListener("pywebviewready", onReady);
            finish();
          }, 900);
        });
      }
      return desktopPathApiPromise.then((api) => {
        if (!api) {
          desktopPathApiPromise = null;
        }
        return api;
      });
    }

    function filenameFromPath(value) {
      const cleaned = (value || "").trim();
      if (!cleaned) return "";
      const parts = cleaned.split(/[\\\\/]/).filter(Boolean);
      return parts.length ? parts[parts.length - 1] : "";
    }

    function pickerDirectoryHint(input) {
      const explicit = input.value.trim();
      if (explicit) return explicit;
      const projectDir = currentProjectDir();
      if (projectDir) return projectDir;
      return bootstrap.defaults.reference_root || bootstrap.defaults.corpus_dir || "";
    }

    function pickerFileTypes(input) {
      return input.dataset.fileTypes ? [input.dataset.fileTypes] : [];
    }

    function attachBrowseControls() {
      document.querySelectorAll("input[data-picker]").forEach((input) => {
        if (input.parentElement?.classList.contains("path-field")) {
          return;
        }

        const wrapper = document.createElement("div");
        wrapper.className = "path-field";
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        const button = document.createElement("button");
        button.type = "button";
        button.className = "browse-button";
        button.textContent = "Browse";
        button.title = "Select a local path";
        button.addEventListener("click", async () => {
          const bridge = await desktopPathBridge();
          if (!bridge) {
            showToast("Native path browsing is available in the desktop app only.", "error");
            return;
          }
          try {
            const selected = await bridge.choose_path(
              input.dataset.picker,
              pickerDirectoryHint(input),
              false,
              filenameFromPath(input.value) || input.dataset.saveFilename || "",
              pickerFileTypes(input),
            );
            if (!selected) {
              return;
            }
            input.value = Array.isArray(selected) ? selected.join(", ") : selected;
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dispatchEvent(new Event("change", { bubbles: true }));
          } catch (error) {
            showToast(error.message || "Could not open the native file picker.", "error");
          }
        });
        wrapper.appendChild(button);
      });
    }

    async function handleFormSubmit(event) {
      event.preventDefault();
      syncSharedInputs();
      const form = event.currentTarget;
      const payload = formPayload(form);
      if (!payload.project_dir && form.querySelector('[data-shared="project_dir"]')) {
        showToast("Set a project directory before running this operation.", "error");
        return;
      }

      const label = form.closest(".subpanel, .stage")?.querySelector("h3, h2")?.textContent || "Operation";
      const command = form.dataset.command || "";
      setReadyChip("Running", false);

      try {
        const result = await fetchJson(form.dataset.endpoint, {
          method: form.dataset.method || "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        recordActivity(label, result);
        if (command) {
          showToast(`${label} completed`);
        }
        setReadyChip("Ready", false);
        if (payload.project_dir) {
          await refreshProjectState();
        } else if (form.dataset.endpoint === bootstrap.endpoints.build_demo) {
          await loadReferenceCases();
        }
      } catch (error) {
        setReadyChip("Attention", true);
        showToast(error.message || "Operation failed.", "error");
        recordActivity(`${label} failed`, { error: error.message || "Operation failed." });
      }
    }

    function renderSummary(caseRecord, latestRun, latestCommit, latestMonitoring, obligations, alerts, reviewActions) {
      const tiles = [
        ["Review runs", caseRecord?.total_runs || 0],
        ["Commits", caseRecord?.total_commits || 0],
        ["Monitoring runs", caseRecord?.total_monitoring_runs || 0],
        ["Open alerts", Array.isArray(alerts) ? alerts.length : 0],
      ];
      $("summary-grid").innerHTML = tiles.map(([label, value]) => `
        <div class="summary-tile">
          <span class="label">${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `).join("");

      const rows = [];
      if (caseRecord) {
        rows.push(["Project", caseRecord.project_id || "unknown"]);
        rows.push(["Perspective", caseRecord.latest_analysis_perspective || currentPerspective()]);
      }
      if (latestRun?.decision_summary) {
        rows.push(["Recommendation", latestRun.decision_summary.recommendation || "unknown"]);
        rows.push(["Overall risk", latestRun.decision_summary.overall_risk || "unknown"]);
      }
      if (latestCommit?.commit_id) {
        rows.push(["Latest commit", latestCommit.commit_id]);
      }
      if (latestMonitoring?.run_id) {
        rows.push(["Latest monitoring", latestMonitoring.run_id]);
      }
      rows.push(["Obligations", Array.isArray(obligations) ? obligations.length : 0]);
      rows.push(["Review actions", Array.isArray(reviewActions) ? reviewActions.length : 0]);

      if (!rows.length) {
        $("state-list").innerHTML = '<li class="empty">No persisted lifecycle data was found for this project yet.</li>';
      } else {
        $("state-list").innerHTML = rows.map(([label, value]) => `
          <li>
            <div class="summary-row">
              <span class="label">${escapeHtml(label)}</span>
              <strong>${escapeHtml(value)}</strong>
            </div>
          </li>
        `).join("");
      }

      const reasons = [];
      if (latestRun?.decision_summary?.top_reasons) {
        reasons.push(...latestRun.decision_summary.top_reasons.slice(0, 4));
      }
      if (latestRun?.decision_summary?.must_fix_before_bid) {
        reasons.push(...latestRun.decision_summary.must_fix_before_bid.slice(0, 2));
      }
      $("reason-pills").innerHTML = reasons.length
        ? reasons.map((reason) => `<span class="pill">${escapeHtml(reason)}</span>`).join("")
        : "";
    }

    async function fetchOptional(url) {
      const response = await fetch(url);
      if (response.status === 404) {
        return null;
      }
      const text = await response.text();
      const payload = text ? JSON.parse(text) : null;
      if (!response.ok) {
        throw new Error(payload?.detail || `Request failed with status ${response.status}`);
      }
      return payload;
    }

    async function refreshProjectState() {
      syncSharedInputs();
      const projectDir = currentProjectDir();
      if (!projectDir) {
        renderSummary(null, null, null, null, [], [], []);
        return;
      }

      setReadyChip("Refreshing", false);
      const q = `project_dir=${encodeURIComponent(projectDir)}`;
      try {
        const [caseRecord, latestRun, latestCommit, latestMonitoring, obligations, alerts, reviewActions] = await Promise.all([
          fetchOptional(`${bootstrap.endpoints.state}?${q}`),
          fetchOptional(`${bootstrap.endpoints.latest_run}?${q}`),
          fetchOptional(`${bootstrap.endpoints.latest_commit}?${q}`),
          fetchOptional(`${bootstrap.endpoints.latest_monitoring}?${q}`),
          fetchOptional(`${bootstrap.endpoints.obligations}?${q}`),
          fetchOptional(`${bootstrap.endpoints.alerts}?${q}`),
          fetchOptional(`${bootstrap.endpoints.review_actions}?${q}`),
        ]);
        renderSummary(caseRecord, latestRun, latestCommit, latestMonitoring, obligations || [], alerts || [], reviewActions || []);
        setReadyChip(caseRecord ? "Ready" : "No data", !caseRecord);
      } catch (error) {
        renderSummary(null, null, null, null, [], [], []);
        setReadyChip("Attention", true);
        showToast(error.message || "Could not refresh project state.", "error");
      }
    }

    async function loadReferenceCases() {
      try {
        const payload = await fetchJson(bootstrap.endpoints.reference_manifest);
        const cases = Array.isArray(payload.cases) ? payload.cases : [];
        const list = $("reference-cases");
        if (!cases.length) {
          list.innerHTML = '<li class="empty">No reference cases exist yet. Build demo assets to seed the local showcase.</li>';
          return;
        }
        list.innerHTML = cases.map((item) => `
          <li>
            <strong>${escapeHtml(item.title || item.case_id || "Reference case")}</strong>
            <div class="meta">${escapeHtml(item.recommendation || "unknown")} · ${escapeHtml(item.overall_risk || "unknown")} · ${escapeHtml(item.findings_count || 0)} findings</div>
            <div class="form-actions" style="margin-top:12px;">
              <a class="quick-link" href="/reference/cases/${encodeURIComponent(item.case_id)}/dashboard" target="_blank" rel="noreferrer">Open dashboard</a>
            </div>
          </li>
        `).join("");
      } catch (error) {
        $("reference-cases").innerHTML = `<li class="empty">${escapeHtml(error.message || "Could not load reference cases.")}</li>`;
      }
    }

    function renderCommandCatalog() {
      $("command-list").innerHTML = bootstrap.commands.map((command) => `
        <li>
          <strong>${escapeHtml(command.label)}</strong>
          <div class="meta">${escapeHtml(command.summary)}</div>
          <div class="command-line">${escapeHtml(command.cli)}</div>
        </li>
      `).join("");
    }

    function seedDefaults() {
      $("workspace-perspective").value = bootstrap.default_perspective;
      $("ensemble-artifacts-dir").value = bootstrap.defaults.ensemble_artifacts_dir;
      $("corpus-dir-input").value = bootstrap.defaults.corpus_dir;
      $("demo-corpus-dir-input").value = bootstrap.defaults.corpus_dir;
      $("reference-root-input").value = bootstrap.defaults.reference_root;
      $("site-dir-input").value = bootstrap.defaults.site_dir;
      attachBrowseControls();
      syncSharedInputs();
      renderCommandCatalog();
      renderActivity();
      loadReferenceCases();
    }

    document.querySelectorAll(".operation-form").forEach((form) => {
      form.addEventListener("submit", handleFormSubmit);
    });

    $("workspace-project-dir").addEventListener("input", syncSharedInputs);
    $("workspace-perspective").addEventListener("change", syncSharedInputs);
    $("refresh-state").addEventListener("click", refreshProjectState);

    seedDefaults();
  </script>
</body>
</html>
""".replace("__ICM_WORKBENCH_BOOTSTRAP__", bootstrap)
