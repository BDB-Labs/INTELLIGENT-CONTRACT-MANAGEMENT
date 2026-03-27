# ESE-CCM Pack Notes

This directory captures the construction-specific pack design for roadway and
public-infrastructure contract analysis in Southern California.

It represents the contract-intelligence role design and artifact contract that
the application layer uses today. It is not yet exposed as a standalone
first-class `ese --pack ...` runtime surface in the published CLI.

## Current application path

Use the application layer directly:

```bash
python -m apps.contract_intelligence bid-review ./sample_project
python -m apps.contract_intelligence commit ./sample_project
python -m apps.contract_intelligence monitor ./sample_project --status-inputs-file ./status_inputs.json
python -m apps.contract_intelligence render-dashboard ./sample_project
```

## Scope

The pack focuses on:

- payment and cash-flow risk
- schedule and delay exposure
- insurance and compliance anomalies
- public-funding and regulatory overlays
- relationship-aware negotiation strategy
- internal-only context signals from budgets, board records, audits, and status materials
- post-award obligation tracking and alerting

## Current role stack

### Pre-award

| Stage | Role | Purpose |
|---|---|---|
| 1 | contractor_reviewer | Contractor-protective risk analysis |
| 2 | owner_reviewer | Agency feasibility and enforceability |
| 3 | compliance_reviewer | Regulatory compliance across local, state, and federal overlays |
| 4 | contractor_manager | Contractor risk aggregation |
| 5 | owner_manager | Owner feasibility aggregation |
| 6 | relationship_strategist | Long-term relationship and negotiation posture |
| 7 | contextual_relationship_analyst | Internal-only environment and budget signal analysis |
| 8 | orchestrator | Final decision authority |
| 9 | contract_optimizer | Clause revision recommendations |

### Post-award

| Stage | Role | Purpose |
|---|---|---|
| 1 | compliance_monitor | Obligation tracking and enforcement monitoring |

## Outputs

The current application layer persists and/or renders:

- decision summary
- risk findings
- context profile
- procurement profile
- outcome evidence
- obligation register
- monitoring runs
- alert snapshots
- generated operator dashboard

## Sanitization rule

Internal context signals are used to shape reasoning and negotiation posture,
but they should not be treated as client-safe output. The current dashboard's
external mode is presentation-only; true external artifact generation remains a
separate follow-on product step.
