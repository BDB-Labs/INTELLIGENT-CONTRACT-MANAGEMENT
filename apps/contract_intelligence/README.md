# Contract Intelligence Pilot

This directory contains the starter scaffold for a domain-specific application
layer built on top of ESE.

The goal is to validate a reusable case-intelligence platform using a first
vertical pack: construction contract management, evaluation, and tracking.
The current emphasis is public-infrastructure procurement, especially roadway
and transportation work where delivery method, funding overlays, governance
records, and post-award outcomes materially affect bid decisions.

## Current scope

The first slice is a `bid_review` workflow that turns a contract package into:

- document inventory
- contractor-side risk findings
- insurance anomalies
- funding and compliance findings
- internal-only context profile
- procurement profile
- outcome evidence bundle
- decision summary
- obligations preview
- adversarial review challenges

The next lifecycle slice adds:

- committed contract records
- carried-forward accepted risks
- negotiated-change capture
- current obligation snapshots tied to the committed contract baseline
- monitoring snapshots and alert records

## Local usage

Run the deterministic pilot over a project folder from the repo root:

```bash
python -m apps.contract_intelligence bid-review ./sample_project
```

Or send artifacts somewhere specific:

```bash
python -m apps.contract_intelligence bid-review ./sample_project --artifacts-dir ./tmp/bid_review
```

Run the same project through ESE's real orchestration path:

```bash
python -m apps.contract_intelligence ensemble-bid-review ./sample_project
```

Run the starter gold corpus:

```bash
python -m apps.contract_intelligence evaluate-corpus
```

Commit the latest reviewed package into committed-contract state:

```bash
python -m apps.contract_intelligence commit ./sample_project
```

Reload the current obligation snapshot from committed state:

```bash
python -m apps.contract_intelligence extract-obligations ./sample_project
```

Apply operational status inputs and emit current alerts:

```bash
python -m apps.contract_intelligence monitor ./sample_project --status-inputs-file ./status_inputs.json
```

The runner currently supports `.md`, `.txt`, `.json`, `.yaml`, `.docx`, and a
lightweight PDF text fallback. PDF extraction is still intentionally basic, but
the loader now preserves clause-like spans and uses them as evidence anchors in
the generated artifacts. The deterministic path now also tags transportation
procurement signals such as CMGC off-ramps, appropriation limits, Public Records
Act handling, WBS reporting, governance artifacts, and outcome/status evidence
when those materials are present in the package.

Budget, board, audit, funding, and status materials now also feed an
internal-only `context_profile.json` artifact so relationship and bid decisions
can consider funding flexibility, schedule pressure, oversight intensity, and
public visibility without turning those inputs into outward-facing report prose.

Each run also writes a durable case record under
`.contract_intelligence/<project_id>/` so later lifecycle stages can attach to a
stable project/run identity instead of treating every analysis as a one-off
artifact dump.

Committed contract and monitoring stages extend that same store with:

- `commits/` for committed contract records
- `obligations/` for current and by-commit obligation snapshots
- `monitoring/` for current and historical monitoring runs
- `alerts/` for current and historical alert snapshots

## Folder map

- `domain/`: shared pilot models and enums
- `ingestion/`: early document typing and intake helpers
- `orchestration/`: role catalog, pipeline definition, and prompts
- `schemas/`: JSON schema contracts for stable artifacts
- `corpus/`: starter gold-corpus cases and expected outcomes
- `api/`: thin FastAPI surface over the local lifecycle store and runners
- `storage/`: filesystem-backed persistence boundary for case, run, commit, and obligation records
- `ui/`: placeholder UI boundary

## Design rule

This package is intentionally not part of the published `ese` distribution yet.
It is a starter layer for product incubation while `ese` remains the generic
execution engine.
