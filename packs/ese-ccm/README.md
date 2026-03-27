# ESE-CCM Pack for INTELLIGENT-CONTRACT-MANAGEMENT

**Construction-specific domain pack** for roadway infrastructure contracts in Southern California.

## Usage

```bash
ese init --pack ese-ccm
ese task "Review roadway contract for Caltrans compliance" --pack ese-ccm --mode full
```

## Outputs

- `external_report.md` — Professional, shareable report (Colleen-style)
- `internal_trace.json` — Full traceability and justified omissions
- `obligation_register.json` — Post-award monitoring ready

Built on the ESE framework. Focuses on payment risk, schedule exposure, insurance, compliance, relationship balance, and long-term agency partnerships.

## Pipeline

### Pre-Award
| Stage | Role | Purpose |
|---|---|---|
| 1 | contractor_reviewer | Contractor-protective risk analysis |
| 2 | owner_reviewer | Agency feasibility & enforceability |
| 3 | compliance_reviewer | Regulatory compliance (Caltrans, DBE, Davis-Bacon) |
| 4 | contractor_manager | Contractor risk aggregation |
| 5 | owner_manager | Owner feasibility aggregation |
| 6 | relationship_strategist | Long-term relationship & negotiation strategy |
| 7 | contextual_relationship_analyst | Environment & budget signal analysis (internal only) |
| 8 | orchestrator | Final decision authority |
| 9 | contract_optimizer | Clause revision recommendations |

### Post-Award
| Stage | Role | Purpose |
|---|---|---|
| 1 | compliance_monitor | Stateful obligation tracking & enforcement |

## Schemas

- `risk_packet.json` — Structured risk findings
- `obligation.json` — Post-award obligation tracking
- `decision_trace.json` — Full decision traceability

## Sanitization

External outputs are sanitized per `prompts/sanitization_rules.md`. Internal context signals (budget pressure, political climate, funding constraints) are translated to neutral commercial language before any client-facing output.
