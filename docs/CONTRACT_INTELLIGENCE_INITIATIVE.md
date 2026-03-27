# Contract Intelligence Initiative

## Purpose

This document locks the remaining contract-intelligence work into execution
order. The sequence is dependency-driven: each initiative should land before
the next one begins unless a smaller prerequisite emerges during implementation.

## Priority Order

### 1. Durable Case And Run Persistence

Goal:
- persist bid-review outputs as durable case records instead of leaving them as
  one-off artifacts

Why first:
- monitoring, API retrieval, and human review all depend on a stable record of
  projects, runs, decisions, procurement profiles, and outcome evidence

Exit criteria:
- every bid review writes a case record and run record
- procurement and outcome artifacts are linked from the stored run
- later commands can address a project by stable project/run identity

### 2. Commit And Obligation Lifecycle

Goal:
- introduce the transition from pre-award review into committed contract state
  and durable obligation registers

Why second:
- post-award monitoring is not credible until the system distinguishes proposed
  terms from final accepted terms

Exit criteria:
- committed contract records exist
- accepted risks and negotiated changes are captured
- obligations can be extracted from a committed contract and reloaded later

### 3. Monitoring And Alert Engine

Goal:
- turn obligations into active monitoring with due-state tracking and event
  generation

Why third:
- once committed obligations exist, the next bottleneck is operational tracking

Exit criteria:
- obligations can move through pending, due, late, and satisfied states
- alert and event records are first-class outputs
- monitoring can be rerun without losing prior state

### 4. Product API Layer

Goal:
- expose projects, documents, runs, findings, obligations, and alerts through a
  stable API

Why fourth:
- the API should sit on top of the persistent lifecycle model, not invent it

Exit criteria:
- upload, run polling, findings retrieval, obligation retrieval, and alert
  retrieval endpoints exist
- API responses map directly to stored case/run records

### 5. Context Intelligence Ingestion

Goal:
- ingest agency budgets, board records, status dashboards, and other public
  context to support internal-only reasoning

Why fifth:
- context is more valuable once storage, runs, and monitoring can retain and
  audit it

Exit criteria:
- context artifacts are ingested and linked to cases
- internal reasoning can use them without leaking them into sanitized outputs
- justified omission and explanation paths stay intact

### 6. Corpus Expansion And Evaluation

Goal:
- convert the public-infrastructure research set into a reproducible gold
  corpus for regression testing and model evaluation

Why sixth:
- the product should first have the right lifecycle structure, then broaden the
  evidence base

Exit criteria:
- exemplar cases are added from awarded public infrastructure projects
- expected procurement and outcome labels are captured
- corpus evaluation covers both bid-review and monitoring-oriented artifacts

### 7. Operator UI And Human Review Workflow

Goal:
- deliver the operator-facing project shell for findings, decisions,
  obligations, monitoring, and escalation

Why seventh:
- the UI should reflect real product state and workflows rather than driving
  them prematurely

Exit criteria:
- project, run, finding, decision, obligation, and alert views exist
- human review and override actions are supported
- internal/external explanation visibility can be role-gated

## Execution Rule

Work this initiative sequentially:

1. Finish the current priority.
2. Add tests and docs for it.
3. Re-run the relevant suite.
4. Only then move to the next priority.

## Current Active Item

Current sequence complete for this roadmap.

Next likely extension:

- richer human-review actions and overrides
- external/internal report-mode separation
- deeper context-source ingestion beyond package-local documents
