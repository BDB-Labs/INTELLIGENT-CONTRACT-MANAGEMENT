# Contract Intelligence Product Direction

## Purpose

This document translates recent external feedback into a repo-grounded product
assessment and a concrete extension plan.

It also clarifies the intended product shape:

- either a vendor or a public agency should be able to upload a proposed or
  boilerplate agreement
- the system should evaluate clause-level exposure during intake, before or
  during negotiation
- the output should explain why specific clauses matter from the chosen
  perspective
- the system should preserve that reasoning into later contract-management and
  monitoring workflows
- relationship-aware guidance should help operators understand how negotiation
  asks may affect long-term agency or vendor relationships

This is not just a post-award compliance product and not just a static contract
analysis tool. It is a dual-perspective intake, negotiation, and lifecycle
management system.

## Repo-Grounded Assessment

### What the current product already does

The current `apps/contract_intelligence` implementation already supports:

- project intake from a local document set
- deterministic bid-review analysis
- contractor/commercial, insurance, compliance, procurement, outcome, and
  internal-only context artifacts
- clause-linked obligation extraction
- committed-contract state with explicit finding dispositions
- accepted-risk and negotiated-change capture
- post-commit obligation monitoring with `pending`, `due`, `late`, and
  `satisfied` states
- alert generation
- persisted case, run, commit, monitoring, and review-action records
- an operator dashboard with internal and external rendering paths

That means the product is already lifecycle-aware and already beyond
"analysis-only."

### Where the external feedback was right

The feedback correctly identified the next major product gaps:

- no first-class vendor or counterparty entity model
- no true dual-perspective negotiation model for vendor vs agency positions
- limited playbook and policy comparison capability
- no full KPI and breach/waiver state machine
- weak portfolio analytics across counterparties and agreements

### Where the external feedback was outdated

Several claims in the feedback are no longer accurate relative to the codebase:

- obligation tracking is present
- temporal monitoring is present
- accepted-risk and negotiated-change capture is present
- audit history and review-action persistence are present
- the dashboard external mode is now a true sanitized rendering path

The correct conclusion is:

- the current system is already a contract-intelligence lifecycle product
- but it is not yet a full vendor/agency negotiation and compliance operating
  system

## Clarified Product Intent

The product should support two primary intake perspectives.

### 1. Vendor-side intake and negotiation support

Input:

- agency boilerplate
- draft agreement
- addenda
- procurement package

System behavior:

- identify payment, delay, insurance, indemnity, compliance, and termination
  terms that disadvantage the contractor
- explain why those terms matter in practical operating language
- recommend negotiation positions such as:
  - push hard
  - negotiate softly
  - accept and price
  - accept as standard
- estimate relationship sensitivity so the operator understands where pushing
  may create long-term friction

### 2. Agency-side intake and negotiation support

Input:

- internal boilerplate
- draft agreement
- proposed vendor redlines
- procurement overlays and funding conditions

System behavior:

- identify clauses that expose the agency to claims, delay, cost growth, or
  unenforceability
- distinguish between reasonable vendor asks and problematic redlines
- explain which vendor requests are operationally acceptable, non-negotiable,
  or likely to damage schedule, funding, or governance posture

### 3. Shared lifecycle carry-forward

For either side, the intake and negotiation record must become the seed for
later management:

- approved deviations
- accepted risks
- negotiated changes
- committed obligations
- monitoring events
- alerts
- historical explanations

## Product Principles

### Dual-perspective by design

Every intake should carry an explicit perspective:

- `vendor`
- `agency`

The product should not treat perspective as hidden prompt flavor. It should be
a first-class data attribute that shapes findings, recommendations, and report
language.

### Negotiation is part of intake

Intake is not only classification. It is the first stage of contract
management.

The system should produce:

- clause findings
- explanation
- negotiation posture
- relationship-aware guidance
- structured disposition candidates for later commit

### Relationship-aware, not relationship-dictated

The relationship manager should not override hard risk or compliance concerns.
It should:

- influence negotiation tone
- help prioritize asks
- explain probable relationship impact

It should not:

- suppress serious risk
- mask mandatory compliance problems

### Explainable carry-forward

Anything accepted, negotiated, waived, priced, or monitored later must remain
traceable to:

- a clause
- a finding
- a perspective
- a disposition
- a human decision

## Strategic Gaps To Close

### Gap 1: Perspective model

Current state:

- perspective is implied by specific analyst roles

Needed:

- explicit case-level and report-level perspective selection
- ability to run the same agreement from vendor or agency posture

### Gap 2: Counterparty model

Current state:

- project-centric storage

Needed:

- vendor, agency, and counterparty records
- cross-agreement exposure and history

### Gap 3: Negotiation object model

Current state:

- findings and review actions exist

Needed:

- first-class negotiation issues, positions, and redline intents

### Gap 4: Playbook engine

Current state:

- deterministic heuristics and domain rules

Needed:

- explicit comparison against internal standards, fallback positions, and
  disallowed language

### Gap 5: KPI and exception state machine

Current state:

- obligations have due rules and monitoring states

Needed:

- measurable KPIs
- waiver, breach, cure, and exception lifecycles

### Gap 6: Portfolio analytics

Current state:

- strong per-project lifecycle state

Needed:

- cross-contract query and reporting surfaces

## Extension Backlog

The extension sequence below is dependency-driven and should be executed in
order.

### Phase 1. Dual-Perspective Intake

Goal:

- make the system explicitly aware of whether it is analyzing from the vendor
  or agency side

Deliver:

- perspective field on cases and runs
- perspective-aware report generation
- perspective-specific finding framing

Exit criteria:

- the same agreement can be evaluated in either perspective
- persisted records retain the perspective used
- dashboard and API expose the selected perspective

### Phase 2. Negotiation Packet Layer

Goal:

- turn findings into first-class negotiation issues

Deliver:

- clause-level negotiation packet output
- stance classification
- fallback language placeholders
- relationship-impact guidance per issue

Exit criteria:

- a vendor user can upload agency boilerplate and receive a usable negotiation
  packet
- an agency user can upload vendor redlines and receive a review packet

### Phase 3. Counterparty and Portfolio Model

Goal:

- move from project-only state to counterparty-aware state

Deliver:

- vendor, agency, and counterparty entities
- agreement-to-counterparty linking
- cross-agreement risk rollups

Exit criteria:

- operators can inspect all agreements tied to a counterparty
- repeated non-standard terms and repeated performance issues are queryable

### Phase 4. Playbook and Policy Engine

Goal:

- compare proposed language to explicit internal standards

Deliver:

- playbook rule model
- policy references
- fallback and must-not-accept rules

Exit criteria:

- findings can cite violated playbook rules
- negotiation packets can recommend approved fallback positions

### Phase 5. KPI and Exception Lifecycle

Goal:

- extend obligations into measurable compliance controls

Deliver:

- KPI model
- breach, cure, waiver, and exception state machine
- approval capture for exceptions

Exit criteria:

- an obligation can move beyond `late` into `breached`, `waived`, or `cured`
- exception approvals are auditable

### Phase 6. Portfolio Query and Reporting

Goal:

- support compliance-manager workflows across many agreements

Deliver:

- cross-agreement query endpoints
- counterparty summaries
- term-pattern and exception reporting

Exit criteria:

- users can answer questions like:
  - show all agreements with non-standard payment timing
  - show all active waived insurance requirements
  - show all late recurring reports for a given vendor

## Required Schema Extensions

The following schema additions are recommended.

### Case and run layer

Add:

- `analysis_perspective: "vendor" | "agency"`
- `counterparty_id: str | null`
- `counterparty_name: str | null`

### New entity: Counterparty

Recommended shape:

```json
{
  "counterparty_id": "cp_sandag",
  "counterparty_type": "agency",
  "name": "San Diego Association of Governments",
  "aliases": ["SANDAG"],
  "region": "Southern California",
  "status": "active"
}
```

### New entity: NegotiationIssue

Recommended shape:

```json
{
  "issue_id": "neg_001",
  "source_finding_id": "finding_123",
  "source_clause": "Prime Contract.md::§5.3",
  "perspective": "vendor",
  "issue_type": "payment_term",
  "stance": "negotiate_soft",
  "relationship_impact": "medium",
  "recommended_position": "Request fixed timing for undisputed amounts.",
  "fallback_position": "Price funding delay risk if clause remains.",
  "playbook_rule_ids": ["vendor_payment_001"]
}
```

### New entity: PlaybookRule

Recommended shape:

```json
{
  "rule_id": "vendor_payment_001",
  "perspective": "vendor",
  "category": "payment",
  "title": "Do not accept contingent payment without escalation",
  "rule_type": "fallback",
  "preferred_language": "Undisputed amounts due within 30 days.",
  "forbidden_patterns": ["payment contingent upon receipt of funds"],
  "severity": "high"
}
```

### Extend Obligation

Add:

- `counterparty_id`
- `kpi_id: str | null`
- `exception_state: "none" | "waived" | "excused" | "breached" | "cured"`
- `exception_reference: str | null`

### New entity: ComplianceKPI

Recommended shape:

```json
{
  "kpi_id": "kpi_monthly_progress_report",
  "obligation_id": "obl_abcd1234",
  "metric_type": "submission",
  "target": "1 report per month",
  "measurement_method": "document_received",
  "breach_threshold": "missed due cycle"
}
```

### New entity: ExceptionRecord

Recommended shape:

```json
{
  "exception_id": "exc_001",
  "obligation_id": "obl_abcd1234",
  "exception_type": "waiver",
  "status": "approved",
  "approved_by": "legal",
  "rationale": "Agency-approved temporary reporting deferment.",
  "effective_from": "2026-04-01T00:00:00Z",
  "effective_to": "2026-04-30T23:59:59Z"
}
```

## Required API Extensions

The following API additions should be prioritized.

### Intake and perspective

- `POST /projects/intake`
  - create a case with `analysis_perspective`
- `POST /projects/runs/bid-review`
  - require or accept `analysis_perspective`

### Negotiation support

- `GET /projects/negotiation-packet/latest`
- `POST /projects/negotiation-issues`
- `PUT /projects/negotiation-issues/{issue_id}`

### Counterparty records

- `GET /counterparties`
- `POST /counterparties`
- `GET /counterparties/{counterparty_id}`
- `GET /counterparties/{counterparty_id}/agreements`

### Playbook engine

- `GET /playbooks/rules`
- `POST /playbooks/rules`
- `POST /projects/playbook-evaluation`

### KPI and exception lifecycle

- `GET /projects/kpis`
- `POST /projects/exceptions`
- `PUT /projects/exceptions/{exception_id}`
- `GET /projects/exceptions`

### Portfolio query

- `GET /portfolio/findings`
- `GET /portfolio/obligations`
- `GET /portfolio/alerts`
- `GET /portfolio/nonstandard-terms`

## Required UI Extensions

The operator UI should gain:

- a perspective selector for vendor vs agency intake
- a negotiation packet view
- a counterparty summary view
- playbook rule hits alongside findings
- KPI and exception views alongside obligations
- portfolio screens for counterparty and term-pattern rollups

## Immediate Recommendation

The next build sequence should be:

1. add explicit perspective to the domain model and intake flow
2. produce negotiation packets as first-class artifacts
3. add counterparty entities and project linking
4. add playbook rules and rule-evaluation output
5. extend obligations into KPI and exception tracking

This sequence aligns directly with the intended product: intake-first contract
analysis that supports negotiation and then carries into ongoing management.
