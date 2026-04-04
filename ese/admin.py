"""ESE Admin UI — FastAPI web application for system management."""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
ESE_DIR = ROOT_DIR / "ese"
APP_DIR = ROOT_DIR / "apps" / "contract_intelligence"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_admin_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ESE Admin Console</title>
<style>
:root {
  --bg: #0f172a;
  --surface: #1e293b;
  --surface-hover: #334155;
  --border: #334155;
  --text: #f1f5f9;
  --text-muted: #94a3b8;
  --primary: #3b82f6;
  --primary-hover: #2563eb;
  --success: #22c55e;
  --warning: #f59e0b;
  --danger: #ef4444;
  --info: #06b6d4;
  --radius: 8px;
  --shadow: 0 1px 3px rgba(0,0,0,0.3);
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); line-height:1.6; }
.sidebar { position:fixed; left:0; top:0; bottom:0; width:260px; background: var(--surface); border-right:1px solid var(--border); padding:20px 0; overflow-y:auto; z-index:100; }
.sidebar-brand { padding:0 20px 20px; border-bottom:1px solid var(--border); margin-bottom:10px; }
.sidebar-brand h1 { font-size:1.25rem; color: var(--primary); }
.sidebar-brand p { font-size:0.75rem; color: var(--text-muted); }
.nav-item { display:flex; align-items:center; gap:10px; padding:10px 20px; color: var(--text-muted); text-decoration:none; cursor:pointer; transition:all 0.2s; }
.nav-item:hover, .nav-item.active { background: var(--surface-hover); color: var(--text); }
.nav-item svg { width:20px; height:20px; flex-shrink:0; }
.main { margin-left:260px; padding:24px; min-height:100vh; }
.page { display:none; }
.page.active { display:block; }
.page-header { margin-bottom:24px; }
.page-header h2 { font-size:1.5rem; margin-bottom:4px; }
.page-header p { color: var(--text-muted); }
.card { background: var(--surface); border:1px solid var(--border); border-radius: var(--radius); padding:20px; margin-bottom:16px; box-shadow: var(--shadow); }
.card h3 { font-size:1rem; margin-bottom:12px; color: var(--text); }
.grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:16px; margin-bottom:24px; }
.stat-card { background: var(--surface); border:1px solid var(--border); border-radius: var(--radius); padding:20px; }
.stat-card .label { font-size:0.8rem; color: var(--text-muted); text-transform:uppercase; letter-spacing:0.05em; }
.stat-card .value { font-size:2rem; font-weight:700; margin:4px 0; }
.stat-card .sub { font-size:0.8rem; color: var(--text-muted); }
.stat-card.success .value { color: var(--success); }
.stat-card.warning .value { color: var(--warning); }
.stat-card.danger .value { color: var(--danger); }
.stat-card.info .value { color: var(--info); }
.btn { display:inline-flex; align-items:center; gap:6px; padding:8px 16px; border-radius:6px; border:none; cursor:pointer; font-size:0.875rem; font-weight:500; transition:all 0.2s; }
.btn-primary { background: var(--primary); color:white; }
.btn-primary:hover { background: var(--primary-hover); }
.btn-success { background: var(--success); color:white; }
.btn-danger { background: var(--danger); color:white; }
.btn-outline { background:transparent; border:1px solid var(--border); color: var(--text); }
.btn-outline:hover { background: var(--surface-hover); }
.btn-sm { padding:4px 10px; font-size:0.75rem; }
table { width:100%; border-collapse:collapse; }
th, td { padding:10px 14px; text-align:left; border-bottom:1px solid var(--border); }
th { font-size:0.75rem; text-transform:uppercase; color: var(--text-muted); letter-spacing:0.05em; }
td { font-size:0.875rem; }
tr:hover td { background: var(--surface-hover); }
.badge { display:inline-block; padding:2px 8px; border-radius:12px; font-size:0.7rem; font-weight:600; text-transform:uppercase; }
.badge-success { background: rgba(34,197,94,0.15); color: var(--success); }
.badge-warning { background: rgba(245,158,11,0.15); color: var(--warning); }
.badge-danger { background: rgba(239,68,68,0.15); color: var(--danger); }
.badge-info { background: rgba(6,182,212,0.15); color: var(--info); }
.form-group { margin-bottom:16px; }
.form-group label { display:block; font-size:0.8rem; color: var(--text-muted); margin-bottom:4px; }
.form-group input, .form-group select, .form-group textarea { width:100%; padding:8px 12px; background: var(--bg); border:1px solid var(--border); border-radius:6px; color: var(--text); font-size:0.875rem; }
.form-group input:focus, .form-group select:focus, .form-group textarea:focus { outline:none; border-color: var(--primary); }
.form-row { display:grid; grid-template-columns: 1fr 1fr; gap:16px; }
.alert { padding:12px 16px; border-radius:6px; margin-bottom:16px; font-size:0.875rem; }
.alert-success { background: rgba(34,197,94,0.1); border:1px solid rgba(34,197,94,0.3); color: var(--success); }
.alert-warning { background: rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.3); color: var(--warning); }
.alert-danger { background: rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); color: var(--danger); }
.alert-info { background: rgba(6,182,212,0.1); border:1px solid rgba(6,182,212,0.3); color: var(--info); }
.progress-bar { height:8px; background: var(--bg); border-radius:4px; overflow:hidden; }
.progress-bar .fill { height:100%; background: var(--primary); border-radius:4px; transition:width 0.3s; }
.modal-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:200; align-items:center; justify-content:center; }
.modal-overlay.active { display:flex; }
.modal { background: var(--surface); border:1px solid var(--border); border-radius:12px; padding:24px; width:90%; max-width:600px; max-height:80vh; overflow-y:auto; }
.modal h3 { margin-bottom:16px; }
.modal-actions { display:flex; gap:8px; justify-content:flex-end; margin-top:20px; }
.toast-container { position:fixed; top:20px; right:20px; z-index:300; }
.toast { background: var(--surface); border:1px solid var(--border); border-radius:8px; padding:12px 16px; margin-bottom:8px; box-shadow: var(--shadow); animation:slideIn 0.3s; }
.toast.success { border-left:3px solid var(--success); }
.toast.error { border-left:3px solid var(--danger); }
@keyframes slideIn { from { transform:translateX(100%); opacity:0; } to { transform:translateX(0); opacity:1; } }
.code { font-family: 'SF Mono', 'Fira Code', monospace; font-size:0.8rem; background: var(--bg); padding:2px 6px; border-radius:4px; }
.empty-state { text-align:center; padding:40px; color: var(--text-muted); }
.empty-state svg { width:48px; height:48px; margin-bottom:12px; opacity:0.5; }
</style>
</head>
<body>
<nav class="sidebar">
  <div class="sidebar-brand">
    <h1>ESE Admin</h1>
    <p>Intelligent Contract Management</p>
  </div>
  <a class="nav-item active" data-page="dashboard" onclick="showPage('dashboard')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
    Dashboard
  </a>
  <a class="nav-item" data-page="pipeline" onclick="showPage('pipeline')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
    Pipeline
  </a>
  <a class="nav-item" data-page="contracts" onclick="showPage('contracts')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
    Contracts
  </a>
  <a class="nav-item" data-page="knowledge" onclick="showPage('knowledge')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
    Knowledge Base
  </a>
  <a class="nav-item" data-page="crm" onclick="showPage('crm')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
    CRM
  </a>
  <a class="nav-item" data-page="config" onclick="showPage('config')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
    Configuration
  </a>
  <a class="nav-item" data-page="system" onclick="showPage('system')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
    System
  </a>
</nav>

<main class="main">
  <!-- Dashboard Page -->
  <div id="page-dashboard" class="page active">
    <div class="page-header">
      <h2>System Dashboard</h2>
      <p>Overview of ESE Intelligent Contract Management</p>
    </div>
    <div class="grid" id="stats-grid"></div>
    <div class="card">
      <h3>Recent Pipeline Runs</h3>
      <div id="recent-runs"></div>
    </div>
    <div class="grid" style="grid-template-columns:1fr 1fr;">
      <div class="card">
        <h3>Knowledge Base</h3>
        <div id="kb-stats"></div>
      </div>
      <div class="card">
        <h3>CRM Entities</h3>
        <div id="crm-stats"></div>
      </div>
    </div>
  </div>

  <!-- Pipeline Page -->
  <div id="page-pipeline" class="page">
    <div class="page-header">
      <h2>Pipeline Management</h2>
      <p>Run and monitor ESE pipeline executions</p>
    </div>
    <div class="card">
      <h3>Run New Pipeline</h3>
      <div class="form-row">
        <div class="form-group">
          <label>Project Directory</label>
          <input type="text" id="pipeline-project-dir" placeholder="/path/to/project">
        </div>
        <div class="form-group">
          <label>Provider</label>
          <select id="pipeline-provider">
            <option value="openai">OpenAI</option>
            <option value="local">Local (Ollama)</option>
            <option value="custom_api">Custom API</option>
          </select>
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>Execution Mode</label>
          <select id="pipeline-mode">
            <option value="demo">Demo (Dry Run)</option>
            <option value="live">Live</option>
          </select>
        </div>
        <div class="form-group">
          <label>Analysis Perspective</label>
          <select id="pipeline-perspective">
            <option value="vendor">Vendor (Contractor)</option>
            <option value="agency">Agency (Owner)</option>
          </select>
        </div>
      </div>
      <button class="btn btn-primary" onclick="runPipeline()">▶ Run Pipeline</button>
    </div>
    <div class="card">
      <h3>Pipeline Status</h3>
      <div id="pipeline-status"></div>
    </div>
  </div>

  <!-- Contracts Page -->
  <div id="page-contracts" class="page">
    <div class="page-header">
      <h2>Contract Analysis</h2>
      <p>Review and manage contract intelligence results</p>
    </div>
    <div class="card">
      <h3>Recent Analyses</h3>
      <div id="contract-list"></div>
    </div>
  </div>

  <!-- Knowledge Base Page -->
  <div id="page-knowledge" class="page">
    <div class="page-header">
      <h2>Knowledge Base</h2>
      <p>Manage historical contract analysis data for RAG retrieval</p>
    </div>
    <div class="card">
      <h3>Search Knowledge Base</h3>
      <div class="form-group">
        <label>Query</label>
        <input type="text" id="kb-query" placeholder="Search past analyses...">
      </div>
      <div class="form-group">
        <label>Entity Filter (optional)</label>
        <input type="text" id="kb-entity" placeholder="Filter by entity name">
      </div>
      <button class="btn btn-primary" onclick="searchKB()">Search</button>
    </div>
    <div class="card">
      <h3>Results</h3>
      <div id="kb-results"></div>
    </div>
    <div class="card">
      <h3>Add Entry</h3>
      <div class="form-group">
        <label>Entity Name</label>
        <input type="text" id="kb-entity-name" placeholder="e.g. State DOT">
      </div>
      <div class="form-group">
        <label>Project Name</label>
        <input type="text" id="kb-project-name" placeholder="e.g. Highway Bridge">
      </div>
      <div class="form-group">
        <label>Summary</label>
        <textarea id="kb-summary" rows="3" placeholder="Brief summary of the analysis"></textarea>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>Relationship Impact (-10 to +10)</label>
          <input type="number" id="kb-impact" min="-10" max="10" step="0.1" value="0">
        </div>
        <div class="form-group">
          <label>Negotiation Outcome</label>
          <select id="kb-outcome">
            <option value="go">Go</option>
            <option value="go-with-conditions">Go with Conditions</option>
            <option value="no-go">No Go</option>
          </select>
        </div>
      </div>
      <button class="btn btn-success" onclick="addKBEntry()">Add Entry</button>
    </div>
  </div>

  <!-- CRM Page -->
  <div id="page-crm" class="page">
    <div class="page-header">
      <h2>CRM — Entity Management</h2>
      <p>Track agencies, vendors, and stakeholder relationships</p>
    </div>
    <div class="card">
      <h3>Add Entity</h3>
      <div class="form-row">
        <div class="form-group">
          <label>Entity Name</label>
          <input type="text" id="crm-entity-name" placeholder="e.g. State DOT">
        </div>
        <div class="form-group">
          <label>Type</label>
          <select id="crm-entity-type">
            <option value="agency">Agency</option>
            <option value="vendor">Vendor</option>
            <option value="contractor">Contractor</option>
            <option value="subcontractor">Subcontractor</option>
            <option value="consultant">Consultant</option>
          </select>
        </div>
      </div>
      <div class="form-group">
        <label>Description</label>
        <textarea id="crm-entity-desc" rows="2" placeholder="Brief description"></textarea>
      </div>
      <button class="btn btn-success" onclick="addEntity()">Add Entity</button>
    </div>
    <div class="card">
      <h3>Entities</h3>
      <div id="crm-entity-list"></div>
    </div>
  </div>

  <!-- Configuration Page -->
  <div id="page-config" class="page">
    <div class="page-header">
      <h2>Configuration</h2>
      <p>Manage system settings and defaults</p>
    </div>
    <div class="card">
      <h3>Current Configuration</h3>
      <div id="config-display"></div>
    </div>
  </div>

  <!-- System Page -->
  <div id="page-system" class="page">
    <div class="page-header">
      <h2>System Information</h2>
      <p>Runtime environment and health status</p>
    </div>
    <div class="grid" id="system-info"></div>
    <div class="card">
      <h3>Health Checks</h3>
      <div id="health-checks"></div>
    </div>
  </div>
</main>

<div class="toast-container" id="toast-container"></div>

<script>
function showPage(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + page).classList.add('active');
  document.querySelector('[data-page="' + page + '"]').classList.add('active');
  loadPageData(page);
}

function loadPageData(page) {
  switch(page) {
    case 'dashboard': loadDashboard(); break;
    case 'system': loadSystemInfo(); break;
    case 'config': loadConfig(); break;
    case 'crm': loadCRM(); break;
    case 'knowledge': loadKBStats(); break;
  }
}

function toast(message, type='info') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.textContent = message;
  c.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

async function api(path, opts={}) {
  const res = await fetch('/admin' + path, opts);
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || res.statusText); }
  return res.json();
}

// Dashboard
async function loadDashboard() {
  try {
    const stats = await api('/stats');
    const g = document.getElementById('stats-grid');
    g.innerHTML = `
      <div class="stat-card info"><div class="label">Total Analyses</div><div class="value">${stats.total_runs || 0}</div><div class="sub">Pipeline executions</div></div>
      <div class="stat-card success"><div class="label">Knowledge Entries</div><div class="value">${stats.knowledge_entries || 0}</div><div class="sub">Historical analyses</div></div>
      <div class="stat-card warning"><div class="label">CRM Entities</div><div class="value">${stats.crm_entities || 0}</div><div class="sub">Tracked organizations</div></div>
      <div class="stat-card info"><div class="label">Pipeline Roles</div><div class="value">${stats.pipeline_roles || 13}</div><div class="sub">Ensemble members</div></div>
    `;
    const rr = document.getElementById('recent-runs');
    if (stats.recent_runs && stats.recent_runs.length > 0) {
      rr.innerHTML = '<table><thead><tr><th>Project</th><th>Date</th><th>Roles</th><th>Status</th></tr></thead><tbody>' +
        stats.recent_runs.map(r => `<tr><td>${r.project_id || '—'}</td><td>${r.date || '—'}</td><td>${r.roles || '—'}</td><td><span class="badge badge-success">${r.status || 'completed'}</span></td></tr>`).join('') +
        '</tbody></table>';
    } else {
      rr.innerHTML = '<div class="empty-state"><p>No pipeline runs yet</p></div>';
    }
    const kb = document.getElementById('kb-stats');
    kb.innerHTML = stats.kb_summary ? '<pre style="font-size:0.8rem;white-space:pre-wrap;">' + JSON.stringify(stats.kb_summary, null, 2) + '</pre>' : '<div class="empty-state"><p>No knowledge base data</p></div>';
    const crm = document.getElementById('crm-stats');
    crm.innerHTML = stats.crm_summary ? '<pre style="font-size:0.8rem;white-space:pre-wrap;">' + JSON.stringify(stats.crm_summary, null, 2) + '</pre>' : '<div class="empty-state"><p>No CRM data</p></div>';
  } catch(e) { toast('Failed to load dashboard: ' + e.message, 'error'); }
}

// System
async function loadSystemInfo() {
  try {
    const info = await api('/system');
    const g = document.getElementById('system-info');
    g.innerHTML = `
      <div class="stat-card"><div class="label">Python</div><div class="value" style="font-size:1rem;">${info.python_version || '—'}</div></div>
      <div class="stat-card"><div class="label">Platform</div><div class="value" style="font-size:1rem;">${info.platform || '—'}</div></div>
      <div class="stat-card"><div class="label">ESE Version</div><div class="value" style="font-size:1rem;">${info.ese_version || '—'}</div></div>
      <div class="stat-card"><div class="label">Uptime</div><div class="value" style="font-size:1rem;">${info.uptime || '—'}</div></div>
    `;
    const hc = document.getElementById('health-checks');
    const health = await api('/health');
    hc.innerHTML = '<table><thead><tr><th>Check</th><th>Status</th><th>Details</th></tr></thead><tbody>' +
      Object.entries(health).map(([k,v]) => `<tr><td>${k}</td><td><span class="badge badge-success">OK</span></td><td class="code">${typeof v === 'object' ? JSON.stringify(v) : v}</td></tr>`).join('') +
      '</tbody></table>';
  } catch(e) { toast('Failed to load system info: ' + e.message, 'error'); }
}

// Config
async function loadConfig() {
  try {
    const cfg = await api('/config');
    document.getElementById('config-display').innerHTML = '<pre style="font-size:0.8rem;white-space:pre-wrap;">' + JSON.stringify(cfg, null, 2) + '</pre>';
  } catch(e) { toast('Failed to load config: ' + e.message, 'error'); }
}

// Pipeline
async function runPipeline() {
  const dir = document.getElementById('pipeline-project-dir').value;
  if (!dir) { toast('Project directory is required', 'error'); return; }
  try {
    toast('Starting pipeline...', 'info');
    const result = await api('/pipeline/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        project_dir: dir,
        provider: document.getElementById('pipeline-provider').value,
        execution_mode: document.getElementById('pipeline-mode').value,
        analysis_perspective: document.getElementById('pipeline-perspective').value,
      })
    });
    toast('Pipeline completed: ' + (result.summary_path || 'done'), 'success');
    document.getElementById('pipeline-status').innerHTML = '<div class="alert alert-success">Pipeline completed successfully. Summary: ' + (result.summary_path || 'N/A') + '</div>';
  } catch(e) { toast('Pipeline failed: ' + e.message, 'error'); }
}

// Knowledge Base
async function loadKBStats() {
  try {
    const stats = await api('/kb/stats');
    document.getElementById('kb-results').innerHTML = '<div class="alert alert-info">Knowledge base has ' + (stats.entry_count || 0) + ' entries</div>';
  } catch(e) {}
}

async function searchKB() {
  const q = document.getElementById('kb-query').value;
  const entity = document.getElementById('kb-entity').value;
  if (!q) { toast('Query is required', 'error'); return; }
  try {
    const params = new URLSearchParams({query: q});
    if (entity) params.set('entity', entity);
    const results = await api('/kb/search?' + params);
    const r = document.getElementById('kb-results');
    if (results.length === 0) {
      r.innerHTML = '<div class="empty-state"><p>No results found</p></div>';
    } else {
      r.innerHTML = results.map((item, i) =>
        '<div class="card"><h3>' + (i+1) + '. ' + (item.project_name || 'Unknown') + ' <span class="badge badge-info">Score: ' + (item.score || 0).toFixed(2) + '</span></h3>' +
        '<p><strong>Entity:</strong> ' + (item.entity_name || '—') + '</p>' +
        '<p><strong>Outcome:</strong> ' + (item.negotiation_outcome || '—') + '</p>' +
        '<p><strong>Impact:</strong> ' + (item.relationship_impact_score || 0) + '/10</p>' +
        '<p>' + (item.summary || '').substring(0, 200) + '...</p>' +
        '<p><strong>Findings:</strong> ' + (item.key_findings || []).join('; ') + '</p></div>'
      ).join('');
    }
  } catch(e) { toast('Search failed: ' + e.message, 'error'); }
}

async function addKBEntry() {
  try {
    await api('/kb/add', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        entity_name: document.getElementById('kb-entity-name').value,
        project_name: document.getElementById('kb-project-name').value,
        summary: document.getElementById('kb-summary').value,
        relationship_impact_score: parseFloat(document.getElementById('kb-impact').value),
        negotiation_outcome: document.getElementById('kb-outcome').value,
      })
    });
    toast('Knowledge base entry added', 'success');
    document.getElementById('kb-entity-name').value = '';
    document.getElementById('kb-project-name').value = '';
    document.getElementById('kb-summary').value = '';
  } catch(e) { toast('Failed to add entry: ' + e.message, 'error'); }
}

// CRM
async function loadCRM() {
  try {
    const entities = await api('/crm/entities');
    const el = document.getElementById('crm-entity-list');
    if (entities.length === 0) {
      el.innerHTML = '<div class="empty-state"><p>No entities tracked yet</p></div>';
    } else {
      el.innerHTML = '<table><thead><tr><th>Name</th><th>Type</th><th>Health</th><th>Score</th><th>Interactions</th><th>Actions</th></tr></thead><tbody>' +
        entities.map(e => `<tr><td>${e.name}</td><td><span class="badge badge-info">${e.entity_type || '—'}</span></td><td><span class="badge badge-${e.relationship_health === 'positive' ? 'success' : e.relationship_health === 'negative' ? 'danger' : 'warning'}">${e.relationship_health || 'neutral'}</span></td><td>${e.health_score || 0}</td><td>${e.total_interactions || 0}</td><td><button class="btn btn-sm btn-outline" onclick="viewEntity('${e.entity_id}')">View</button></td></tr>`).join('') +
        '</tbody></table>';
    }
  } catch(e) { toast('Failed to load CRM: ' + e.message, 'error'); }
}

async function addEntity() {
  try {
    await api('/crm/entities', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        name: document.getElementById('crm-entity-name').value,
        entity_type: document.getElementById('crm-entity-type').value,
        description: document.getElementById('crm-entity-desc').value,
      })
    });
    toast('Entity added', 'success');
    document.getElementById('crm-entity-name').value = '';
    document.getElementById('crm-entity-desc').value = '';
    loadCRM();
  } catch(e) { toast('Failed to add entity: ' + e.message, 'error'); }
}

function viewEntity(id) {
  toast('Viewing entity: ' + id, 'info');
}

// Init
loadDashboard();
</script>
</body>
</html>"""


def create_admin_app(
    *,
    kb_dir: str | Path | None = None,
    crm_dir: str | Path | None = None,
) -> FastAPI:
    """Create the ESE Admin FastAPI application."""
    from datetime import datetime as _dt

    _start_time = _dt.now(timezone.utc)

    app = FastAPI(
        title="ESE Admin Console",
        description="Administrative interface for Intelligent Contract Management",
        version="1.0.0",
    )

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_home():
        return HTMLResponse(content=_build_admin_html())

    @app.get("/admin/health")
    async def health():
        return {
            "status": "healthy",
            "timestamp": _now_iso(),
            "uptime_seconds": (_dt.now(timezone.utc) - _start_time).total_seconds(),
        }

    @app.get("/admin/stats")
    async def stats():
        result = {
            "total_runs": 0,
            "knowledge_entries": 0,
            "crm_entities": 0,
            "pipeline_roles": 13,
            "recent_runs": [],
            "kb_summary": None,
            "crm_summary": None,
        }
        if kb_dir:
            try:
                from ese.knowledge_base import ContractKnowledgeBase

                kb = ContractKnowledgeBase(kb_dir)
                result["knowledge_entries"] = len(kb)
                result["kb_summary"] = {"storage": str(kb_dir), "entries": len(kb)}
            except Exception:
                pass
        if crm_dir:
            try:
                from ese.crm import ContractCRM

                crm = ContractCRM(crm_dir)
                result["crm_entities"] = len(crm)
                result["crm_summary"] = {
                    "storage": str(crm_dir),
                    "entities": len(crm),
                    "contacts": len(crm.contacts),
                    "interactions": len(crm.interactions),
                }
            except Exception:
                pass
        return result

    @app.get("/admin/system")
    async def system_info():
        import ese

        return {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": platform.platform(),
            "ese_version": getattr(ese, "__version__", "unknown"),
            "uptime": str(_dt.now(timezone.utc) - _start_time),
            "root_dir": str(ROOT_DIR),
        }

    @app.get("/admin/config")
    async def get_config():
        cfg_path = ROOT_DIR / "ese.config.yaml"
        if cfg_path.exists():
            import yaml

            return yaml.safe_load(cfg_path.read_text())
        return {"message": "No configuration file found", "path": str(cfg_path)}

    @app.post("/admin/pipeline/run")
    async def run_pipeline_req(body: dict[str, Any]):
        from apps.contract_intelligence.orchestration.ese_bridge import (
            build_bid_review_ese_config,
        )
        from ese.pipeline import run_pipeline as _run_pipeline

        project_dir = body.get("project_dir", "")
        if not project_dir:
            raise HTTPException(status_code=400, detail="project_dir is required")

        cfg = build_bid_review_ese_config(
            project_dir=project_dir,
            provider=body.get("provider", "local"),
            execution_mode=body.get("execution_mode", "demo"),
            artifacts_dir=body.get("artifacts_dir", str(ROOT_DIR / "admin_artifacts")),
            analysis_perspective=body.get("analysis_perspective", "vendor"),
            knowledge_base_dir=kb_dir,
            crm_dir=crm_dir,
        )
        summary_path = _run_pipeline(
            cfg=cfg, artifacts_dir=str(cfg["output"]["artifacts_dir"])
        )
        return {"summary_path": summary_path, "status": "completed"}

    @app.get("/admin/kb/stats")
    async def kb_stats():
        if not kb_dir:
            return {"enabled": False}
        from ese.knowledge_base import ContractKnowledgeBase

        kb = ContractKnowledgeBase(kb_dir)
        return {
            "enabled": True,
            "entry_count": len(kb),
            "storage": str(kb_dir),
        }

    @app.get("/admin/kb/search")
    async def kb_search(query: str = "", entity: str = ""):
        if not kb_dir:
            return []
        from ese.knowledge_base import ContractKnowledgeBase

        kb = ContractKnowledgeBase(kb_dir)
        results = kb.search(query, entity_filter=entity or None, top_k=10)
        return [
            {
                "project_name": e.project_name,
                "entity_name": e.entity_name,
                "score": score,
                "negotiation_outcome": e.negotiation_outcome,
                "relationship_impact_score": e.relationship_impact_score,
                "summary": e.summary,
                "key_findings": e.key_findings,
            }
            for e, score in results
        ]

    @app.post("/admin/kb/add")
    async def kb_add(body: dict[str, Any]):
        if not kb_dir:
            raise HTTPException(status_code=400, detail="Knowledge base not configured")
        from ese.knowledge_base import (
            ContractKnowledgeBase,
            create_entry_from_bid_review,
        )

        kb = ContractKnowledgeBase(kb_dir)
        entry = create_entry_from_bid_review(
            project_id=f"admin_{len(kb)}",
            entity_name=body.get("entity_name", "Unknown"),
            project_name=body.get("project_name", "Unknown"),
            project_type=body.get("project_type", "construction"),
            document_types=body.get("document_types", []),
            key_findings=body.get("key_findings", []),
            relationship_impact_score=body.get("relationship_impact_score", 0.0),
            negotiation_outcome=body.get("negotiation_outcome", "unknown"),
            summary=body.get("summary", ""),
            tags=body.get("tags", []),
        )
        kb.add_entry(entry)
        return {"entry_id": entry.entry_id, "status": "added"}

    @app.get("/admin/crm/entities")
    async def crm_entities(entity_type: str = ""):
        if not crm_dir:
            return []
        from ese.crm import ContractCRM

        crm = ContractCRM(crm_dir)
        entities = crm.list_entities(entity_type=entity_type or None)
        return [
            {
                "entity_id": e.entity_id,
                "name": e.name,
                "entity_type": e.entity_type,
                "relationship_health": e.relationship_health,
                "health_score": e.health_score,
                "total_interactions": e.total_interactions,
                "total_projects": e.total_projects,
            }
            for e in entities
        ]

    @app.post("/admin/crm/entities")
    async def crm_add_entity(body: dict[str, Any]):
        if not crm_dir:
            raise HTTPException(status_code=400, detail="CRM not configured")
        from ese.crm import ContractCRM, create_entity

        crm = ContractCRM(crm_dir)
        entity = create_entity(
            name=body.get("name", ""),
            entity_type=body.get("entity_type", ""),
            description=body.get("description", ""),
            tags=body.get("tags", []),
        )
        crm.add_entity(entity)
        return {"entity_id": entity.entity_id, "status": "added"}

    @app.get("/admin/crm/entity/{entity_id}")
    async def crm_entity_detail(entity_id: str):
        if not crm_dir:
            raise HTTPException(status_code=400, detail="CRM not configured")
        from ese.crm import ContractCRM

        crm = ContractCRM(crm_dir)
        profile = crm.get_entity_profile(entity_id)
        if not profile.get("found"):
            raise HTTPException(status_code=404, detail="Entity not found")
        return profile

    return app
