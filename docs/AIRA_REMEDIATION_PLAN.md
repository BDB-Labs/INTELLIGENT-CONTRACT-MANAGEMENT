# AIRA Remediation Plan

This plan tracks the repository-grounded remediation work from the AIRA v1 audit.
Each item maps to a specific finding and is ordered by implementation priority.

## P0

1. `AIRA-001` Fail closed on corrupted feedback evidence stores.
Status: Complete
Target:
- `ese/feedback.py`
- `tests/test_feedback.py`
Success criteria:
- malformed feedback state raises instead of resetting to an empty store
- feedback writes never overwrite unreadable evidence silently

2. `AIRA-002` Remove silent supplemental artifact generation failures.
Status: Complete
Target:
- `ese/pipeline.py`
- related pipeline/report tests
Success criteria:
- release-simulation and code-suggestion generation failures surface as run failures

3. `AIRA-003` Make dry-run execution explicit instead of implicit.
Status: Complete
Target:
- `ese/config.py`
- `ese/pipeline.py`
- `ese/doctor.py`
- config/pipeline tests
Success criteria:
- no implicit `dry-run` fallback when adapter is omitted
- `dry-run` allowed only in explicit demo mode

4. `AIRA-004` Apply the same path-boundary enforcement across CLI and API.
Status: Complete
Target:
- `apps/contract_intelligence/paths.py`
- `apps/contract_intelligence/api/app.py`
- `apps/contract_intelligence/cli.py`
- API/CLI tests
Success criteria:
- project, input, and output paths are consistently validated in all entry points

5. `AIRA-005` Add startup integrity validation for the contract-intelligence API.
Status: Complete
Target:
- `apps/contract_intelligence/api/app.py`
- API tests
Success criteria:
- invalid startup configuration fails application startup
- health signaling does not report ready before startup validation passes

## P1

6. `AIRA-006` Stop silently discarding corrupted dashboard job state.
Status: Complete
Target:
- `ese/dashboard.py`
- dashboard tests
Success criteria:
- persisted job corruption is surfaced explicitly instead of skipped

7. `AIRA-007` Remove local-only success semantics for server-backed review actions.
Status: Complete
Target:
- `apps/contract_intelligence/ui/dashboard.py`
- contract-intelligence UI tests
Success criteria:
- server-backed review actions do not appear saved or cleared when server persistence fails

8. `AIRA-008` Replace ambiguous dashboard artifact loading return contracts with structured status.
Status: Planned
Target:
- `apps/contract_intelligence/ui/dashboard.py`
- contract-intelligence UI tests
Success criteria:
- callers can distinguish missing, unreadable, invalid, and successful artifact loads without relying on `None`

9. `AIRA-009` Replace ambiguous feedback-store return semantics with structured integrity outcomes.
Status: Planned
Target:
- `ese/feedback.py`
- feedback/report tests
Success criteria:
- callers can distinguish missing feedback from corrupted feedback without shared empty payloads

10. `AIRA-010` Centralize degraded document extraction policy.
Status: Planned
Target:
- `apps/contract_intelligence/ingestion/project_loader.py`
- ingestion tests
Success criteria:
- fallback sources, quality thresholds, and failure policy are defined in one place

11. `AIRA-011` Centralize dashboard artifact degradation policy.
Status: Planned
Target:
- `apps/contract_intelligence/ui/dashboard.py`
- contract-intelligence UI tests
Success criteria:
- partial artifact rendering follows one explicit policy instead of multiple ad hoc continuations

## P2

12. `AIRA-012` Review remaining broad exception handlers and either narrow or escalate them.
Status: Planned
Target:
- `ese/pipeline.py`
- `ese/dashboard.py`
- `apps/contract_intelligence/ui/dashboard.py`
- `apps/contract_intelligence/storage/filesystem.py`
Success criteria:
- broad handlers are either justified, narrowed, or converted into typed failures

13. `AIRA-013` Revisit dashboard/local runtime background work for explicit supervision guarantees.
Status: Planned
Target:
- `ese/dashboard.py`
- `ese/local_runtime.py`
Success criteria:
- background execution paths have explicit supervision, error propagation, or health visibility contracts

14. `AIRA-014` Add regression tests for startup and integrity failure modes.
Status: Planned
Target:
- API, dashboard, feedback, pipeline, and CLI tests
Success criteria:
- corrupted state, invalid startup config, and blocked persistence are covered by automated tests

## Exit criteria

The AIRA remediation stream is complete when:

- no corrupted evidence store is silently reset
- no required artifact generation failure is silently ignored
- demo-mode execution is explicit and gated
- CLI and API path enforcement are aligned
- startup validation fails closed on invalid runtime configuration
- server-backed review actions do not fall back to misleading local-only success
