# Contract Intelligence Product

This directory contains the incubating contract-intelligence application layer
built on top of ESE.

The current vertical is construction contract compliance and lifecycle
monitoring for public-infrastructure work, with a particular emphasis on
roadway and transportation packages where procurement method, funding overlays,
governance records, and post-award outcomes materially affect bid decisions.

The intended product posture is dual-perspective:

- vendor-side intake and negotiation support against agency boilerplate
- agency-side intake and negotiation support against proposed vendor terms
- lifecycle carry-forward from intake findings into committed obligations,
  exceptions, and monitoring

## Current lifecycle

The product now covers a real end-to-end local lifecycle:

1. ingest project documents from a folder
2. run bid review and emit typed artifacts
3. persist durable case and run records
4. commit the latest reviewed package into committed-contract state
5. extract current obligations from committed state
6. monitor those obligations against status inputs
7. render an operator dashboard over the persisted lifecycle state

## Current artifacts and records

Bid review emits:

- document inventory
- perspective-aware clause findings
- contractor-side risk findings
- insurance anomalies
- funding and compliance findings
- internal-only context profile
- procurement profile
- outcome evidence bundle
- decision summary
- obligations preview
- adversarial review challenges

Persistent lifecycle state now includes:

- durable case records
- bid-review run records
- committed contract records
- accepted risks and negotiated changes
- current and by-commit obligation snapshots
- monitoring runs
- current and historical alert snapshots

## Local usage

From the repository root, sync the project once with `uv`:

```bash
uv sync --locked
```

Run the deterministic bid review over a project folder:

```bash
uv run python -m apps.contract_intelligence bid-review ./sample_project
uv run python -m apps.contract_intelligence bid-review ./sample_project --perspective agency
```

Run the same project through ESE's orchestration path:

```bash
uv run python -m apps.contract_intelligence ensemble-bid-review ./sample_project
```

Commit the latest reviewed package into committed state:

```bash
uv run python -m apps.contract_intelligence commit ./sample_project
```

Reload the current obligation snapshot:

```bash
uv run python -m apps.contract_intelligence extract-obligations ./sample_project
```

Apply operational status inputs and emit alerts:

```bash
uv run python -m apps.contract_intelligence monitor ./sample_project --status-inputs-file ./status_inputs.json
```

Render the generated operator dashboard:

```bash
uv run python -m apps.contract_intelligence render-dashboard ./sample_project
uv run python -m apps.contract_intelligence render-dashboard ./sample_project --mode external
```

Run the starter gold corpus:

```bash
uv run python -m apps.contract_intelligence evaluate-corpus
```

Build the Vercel demo assets and the Render reference workspaces:

```bash
uv run python -m apps.contract_intelligence build-demo
```

## Product behavior notes

- supported source types currently include `.md`, `.txt`, `.json`, `.yaml`,
  `.docx`, and a lightweight PDF text fallback
- transportation-specific heuristics now tag CMGC off-ramps, appropriation
  limits, Public Records Act handling, WBS reporting, governance artifacts, and
  outcome/status evidence when those materials are present
- budget, board, audit, funding, and status materials feed an internal-only
  `context_profile.json` artifact used for strategy and relationship-aware
  reasoning
- bid review now supports explicit `vendor` and `agency` perspectives so the
  same package can be framed either as contractor-side intake or agency-side
  pre-negotiation review
- the generated dashboard supports internal and external outputs; rendering
  with `--mode external` omits internal-only context, review actions, and
  sensitive path metadata from the generated HTML payload

## Local API safety defaults

The thin FastAPI layer in `api/` now:

- disables interactive docs by default
- validates project directories before lifecycle actions run
- validates optional input files before commit and monitoring actions
- supports boundary enforcement through `CONTRACT_INTELLIGENCE_ALLOWED_ROOTS`

Set `CONTRACT_INTELLIGENCE_EXPOSE_DOCS=1` only when you explicitly want the API
docs enabled in a trusted local environment.

## Deployment posture

This product should currently be treated as two separate deployment surfaces:

- a private operator/runtime environment for real lifecycle work
- a public demo environment that serves only sanitized demo artifacts

See [`docs/DEPLOYMENT_SPLIT_PLAN.md`](/Users/billp/Documents/GitHub/INTELLIGENT-CONTRACT-MANAGEMENT/docs/DEPLOYMENT_SPLIT_PLAN.md)
for the recommended domain split, hosting posture, and rollout phases.

Concrete deployment scaffolding now exists in:

- [demo_site/README.md](/Users/billp/Documents/GitHub/INTELLIGENT-CONTRACT-MANAGEMENT/demo_site/README.md)
- [render.yaml](/Users/billp/Documents/GitHub/INTELLIGENT-CONTRACT-MANAGEMENT/render.yaml)
- [scripts/start_icm_reference.sh](/Users/billp/Documents/GitHub/INTELLIGENT-CONTRACT-MANAGEMENT/scripts/start_icm_reference.sh)
- [docs/DEPLOYMENT_CHECKLIST.md](/Users/billp/Documents/GitHub/INTELLIGENT-CONTRACT-MANAGEMENT/docs/DEPLOYMENT_CHECKLIST.md)

## Folder map

- `domain/`: shared models and enums
- `ingestion/`: document typing and intake helpers
- `orchestration/`: role catalog, deterministic heuristics, prompts, and ESE bridge
- `schemas/`: JSON schema contracts for stable artifacts
- `corpus/`: gold-corpus cases and expected outcomes
- `storage/`: filesystem-backed lifecycle persistence
- `api/`: thin FastAPI surface over projects, runs, commits, monitoring, and alerts
- `ui/`: generated operator dashboard surface

## Design rule

This package remains outside the published `ese` distribution. It is the
product incubation layer while `ese` stays the generic execution engine.
