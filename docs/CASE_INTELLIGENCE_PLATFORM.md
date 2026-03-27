# Case Intelligence Platform

## Purpose

This document defines a reusable application layer that sits on top of ESE and
supports many industry-specific workflows without changing the ESE core.

The key design move is to treat ESE as the orchestration substrate and build a
separate casework platform above it:

- ESE handles role execution, adapters, artifacts, reruns, summaries, and the
  operator dashboard.
- The platform layer handles cases, documents, evidence, findings, decisions,
  obligations, alerts, and human review.
- Industry-specific behavior is supplied through domain packs.

The construction contract management pilot is the first domain pack, not the
platform itself.

## Product Frame

The reusable product is an institutional decision-operations platform for
high-stakes, document-driven workflows.

It should support a common evaluation graph across industries:

`ingest -> structure -> evaluate -> challenge -> synthesize -> decide -> commit -> monitor`

Construction contracts are one instance of this graph. Future packs can apply
the same model to procurement, underwriting, vendor risk, lending, healthcare
authorization, or regulated compliance review.

## Architecture Layers

### 1. ESE Core

Leave the `ese` package focused on its current role:

- role sequencing and parallel execution
- runtime/provider abstraction
- artifact generation
- rerun support
- reporting and dashboard views

This keeps the published CLI stable and avoids turning ESE into a vertical
application.

### 2. Platform Layer

The shared platform above ESE should own the durable casework model:

- `Case`
- `Document`
- `DocumentChunk`
- `EvidenceSpan`
- `Finding`
- `DecisionSummary`
- `NegotiationIssue`
- `Obligation`
- `Alert`
- `Run`
- `RoleReport`
- `HumanReview`
- `Precedent`

This layer is where auditability, persistence, and monitoring become
cross-industry capabilities instead of one-off features.

### 3. Governance Layer

Borrow the following operational ideas from the ELEANOR material:

- evaluate, do not command
- preserve separation between specialist reviewers
- quantify uncertainty
- escalate contradiction or low confidence to human review
- retain evidence-rich, append-only run history
- allow precedent retrieval without hiding novel cases

Every role output should carry:

- cited evidence
- confidence
- severity or risk band
- recommended action
- uncertainty notes

Every synthesized decision should carry:

- recommendation
- rationale
- dissent summary
- human-review flag
- linked artifacts

### 4. Domain Pack Interface

Each industry pack should provide:

- role catalog
- prompt set
- artifact contract
- schema set
- scoring policy
- expected-document rules
- obligation extraction rules
- report templates

That means a new industry should require a new pack, not a new platform.

### 5. Product Shell

The product shell should be shared across packs:

- API
- project and case UI
- storage
- export surfaces
- audit views
- operator feedback workflow

## Universal Workflow

The base workflow should be fixed even when the role names change:

1. Intake
   - classify uploaded documents
   - detect missing expected inputs
   - extract metadata
2. Structuring
   - normalize files
   - chunk text
   - build clause or evidence index
3. Specialist Review
   - run pack-defined analysts in parallel
4. Adversarial Challenge
   - explicitly search for missed risks and contradictions
5. Synthesis
   - merge outputs into stable decision artifacts
6. Human Decision
   - accept, reject, escalate, or request rerun
7. Commit
   - convert approved findings into obligations or tracked actions
8. Monitor
   - alert on deadlines, drift, or changed source material

The current pilot now implements the first half of that lifecycle with durable
run records and committed-contract obligation snapshots. Monitoring remains the
next product step rather than an implied future state.

## Artifact Contract

The platform should favor stable artifacts before polished UI.

Recommended baseline artifacts:

- `document_inventory.json`
- `risk_findings.json`
- `context_profile.json`
- `procurement_profile.json`
- `outcome_evidence.json`
- `decision_summary.json`
- `review_challenges.json`
- `obligations_register.json`
- `audit_trace.json`

Those artifacts should then be persisted into durable case and run records so
commit, monitoring, and API layers work from stable product state instead of
re-reading ad hoc output folders.

This keeps the system inspectable and makes evaluation easier across packs.

## Repo Strategy

For speed, keep the first scaffold inside this repository under `apps/`.

For long-term product separation, the cleaner shape is:

- `ensemble-software-engineering` remains the orchestration engine
- a sibling product repo owns the platform shell and domain packs

The in-repo scaffold is a deliberate incubation path, not a statement that the
vertical application belongs permanently inside the `ese` package.

## Pilot 1: Construction Contract Intelligence

The first pack should focus on a narrow bid-review product slice:

- contract package intake
- contractor-side risk findings
- insurance anomaly review
- funding and compliance findings
- internal-only context ingestion from budget, board, audit, and status materials
- procurement and delivery-method profiling
- public governance and outcome evidence capture
- executive go/no-go summary
- obligation preview

Suggested pack roles:

- `document_intake_analyst`
- `contract_risk_analyst`
- `insurance_requirements_analyst`
- `funding_compliance_analyst`
- `relationship_strategy_analyst`
- `bid_decision_analyst`
- `obligation_register_builder`
- `adversarial_reviewer`

## Acceptance Criteria For The Base

The platform base is good enough when:

- a new domain pack can be added without editing ESE core logic
- every run emits typed artifacts with evidence and confidence
- low-confidence or contradictory runs are explicitly escalated
- prior cases can be referenced as precedents
- obligations and alerts are first-class records, not report prose

## Near-Term Build Sequence

1. Define the base casework entities and artifact contract.
2. Define the pack interface and construction pilot role catalog.
3. Scaffold the first pilot under `apps/contract_intelligence/`.
4. Keep persistence and UI thin until the artifact contract settles.
5. Add a second vertical only after the first pack proves the abstraction.
