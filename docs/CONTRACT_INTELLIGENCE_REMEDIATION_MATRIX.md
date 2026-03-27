# Contract Intelligence Remediation Matrix

This document converts the full code-review findings set into an execution
matrix. Every finding has a remediation ID, priority wave, implementation
direction, dependency notes, verification path, and explicit status.

Status key:

- `done`: implemented and verified in the repository
- `open`: not yet implemented
- `bundled`: addressed as part of another remediation item but still tracked
- `defer`: intentionally postponed with rationale

Priority wave key:

- `P0`: stop-ship or production-safety defect
- `P1`: next sprint hardening required before broader rollout
- `P2`: important correctness or trust improvement after P0/P1
- `P3`: cleanup or polish that should still be tracked to closure

## Remediation Waves

### Wave P0: fail closed and protect internal data

These items should land first because they affect committed state, data
exposure, or the ability to trust the lifecycle record:

- `CI-RM-001` Validate `project_dir` in CLI and orchestration paths and fail
  closed on missing directories.
- `CI-RM-002` Validate `committed_contract_dir` before commit and reject empty
  or nonexistent baselines.
- `CI-RM-003` Replace default accepted-risk carry-forward with explicit commit
  dispositions.
- `CI-RM-004` Generate a true external report payload instead of shipping the
  full internal dashboard state.
- `CI-RM-005` Apply allowed-root validation consistently to API output/input
  path fields.
- `CI-RM-006` Add atomic persistence and write coordination for case state.

### Wave P1: stabilize lifecycle identity and monitoring trust

These items should land next because they affect traceability and operator
confidence:

- `CI-RM-007` Stable obligation identity generation
- `CI-RM-008` Stronger obligation deduplication keyed by clause and trigger
- `CI-RM-009` Clause-level obligation traceability
- `CI-RM-010` Stable alert identity generation
- `CI-RM-011` Real due-state calculation for monitoring
- `CI-RM-012` Strict monitoring input schema and status validation
- `CI-RM-013` Persist review actions server-side
- `CI-RM-014` Validate and normalize `/projects/alerts` responses
- `CI-RM-015` Fail invalid optional JSON payloads instead of silently dropping rows

### Wave P2: improve ingestion and decision quality

These items improve correctness and reduce false confidence:

- `CI-RM-016` Content-aware document classification
- `CI-RM-017` Reliable PDF extraction with extraction-quality scoring
- `CI-RM-018` File-size and binary guards during ingestion
- `CI-RM-019` Real contradiction analysis in review challenges
- `CI-RM-020` Stronger bid decision escalation rules
- `CI-RM-021` Better ESE bridge context packing and salience ordering
- `CI-RM-022` Surface missing artifact / partial-run failures in the dashboard
- `CI-RM-023` Replace stringly-typed lifecycle fields with constrained models

### Wave P3: final polish and operator ergonomics

- `CI-RM-024` Replace silent frontend localStorage recovery with visible operator
  warnings

## Full Matrix

| ID | Severity | Priority | Area | Finding | Planned remediation | Depends on | Verification | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `CI-RM-001` | high | P0 | bid review / CLI | `run_bid_review()` can review a nonexistent or mistyped project path instead of failing closed. | Add shared path validation in CLI and orchestration entrypoints; reject missing or non-directory project roots before ingestion begins. | none | unit tests for bad path inputs in CLI/API; assert no artifacts or case records are created | done |
| `CI-RM-002` | high | P0 | commit lifecycle | `commit_contract()` accepts a nonexistent `committed_contract_dir` and can create a commit from an empty package. | Validate committed contract path, require at least one readable committed document, and fail commit when the final package is empty. | `CI-RM-001` | tests for nonexistent and empty committed contract directories; assert commit is rejected | done |
| `CI-RM-003` | high | P0 | commit lifecycle | The default commit behavior promotes all latest findings into `accepted_risks`. | Replace implicit carry-forward with explicit operator dispositions: accepted, unresolved, rejected, priced, negotiated. Block commit when unresolved HIGH/CRITICAL findings remain unless an override is recorded. | `CI-RM-002` | commit-lifecycle tests covering explicit acceptance and rejection; assert unresolved high findings fail commit | done |
| `CI-RM-004` | high | P0 | reporting / UI | External dashboard mode only hides internal panels; the full internal payload is still embedded in exported HTML. | Split internal and external serializers. Generate a sanitized external artifact at render time that excludes internal context, review actions, file paths, and strategy-only notes. | none | snapshot tests confirming internal-only fields are absent from external HTML/JSON payloads | done |
| `CI-RM-005` | high | P0 | API | Allowed-root validation is inconsistent; `artifacts_dir` and `committed_contract_dir` bypass the same boundary checks as `project_dir`. | Centralize path normalization and boundary checks for every incoming path-like field, including output directories. | none | API tests for forbidden paths on analyze/commit/monitor/report endpoints | done |
| `CI-RM-006` | high | P0 | storage | Case state is written with non-atomic JSON overwrites and unlocked read-modify-write updates. | Implement temp-file writes plus atomic rename; add file locking or move lifecycle metadata to SQLite/Postgres-backed persistence. | none | concurrency/interruption tests; assert JSON files remain parseable and history entries are not lost | done |
| `CI-RM-007` | medium | P1 | obligations | Obligation IDs are position-based and can drift across reruns. | Derive obligation IDs from stable inputs such as clause ID, obligation type, due rule, and normalized title. | `CI-RM-017`, `CI-RM-023` | extraction tests asserting stable obligation IDs across repeated runs and reordered documents | done |
| `CI-RM-008` | medium | P1 | obligations | Obligation deduplication uses title alone and can collapse distinct obligations with similar wording. | Deduplicate on a compound signature including clause location, trigger, due rule, and normalized title. | `CI-RM-007` | tests with repeated notice/reporting language in different clauses; assert distinct obligations remain distinct | done |
| `CI-RM-009` | medium | P1 | obligations / traceability | `source_clause` only records the filename, not the clause location. | Store document ID, clause location, and optional excerpt for each obligation; expose that structure in commit and monitoring outputs. | `CI-RM-007` | obligation snapshot tests asserting clause-level traceability fields are present | done |
| `CI-RM-010` | medium | P1 | monitoring | Alert IDs are generated from list order and are not stable across runs. | Generate alert IDs from obligation ID, alert type, and due-cycle key; persist alert lineage so the same open condition keeps the same identity. | `CI-RM-007`, `CI-RM-011` | monitoring tests asserting repeated runs preserve alert IDs for unchanged open alerts | done |
| `CI-RM-011` | medium | P1 | monitoring | Recurring obligations default to `due` without using due cadence or `as_of_date`. | Add due-calendar logic based on obligation type and parsed due rules; compute pending/due/late from `as_of_date`, `next_due_at`, and `last_satisfied_at`. | `CI-RM-009`, `CI-RM-023` | tests for weekly/monthly/event-driven obligations with explicit dates | done |
| `CI-RM-012` | medium | P1 | monitoring / models | Monitoring input parsing silently drops malformed rows and accepts freeform statuses. | Introduce a validated monitoring input model with strict status enums and explicit row-level errors. | `CI-RM-023` | API/CLI tests asserting invalid rows fail with useful validation errors | done |
| `CI-RM-013` | medium | P1 | UI / lifecycle | Human review actions are stored only in localStorage and are not auditable or shared. | Persist review actions and overrides in the case store/API, keyed by project and run/commit context. Keep localStorage only as a client cache. | `CI-RM-006`, `CI-RM-023` | dashboard/API tests asserting dispositions survive browser refresh and appear across operators | done |
| `CI-RM-014` | medium | P1 | API | `/projects/alerts` returns raw JSON dicts instead of validated models. | Validate alert payloads through `AlertRecord` before returning them and surface malformed snapshots as typed server errors. | `CI-RM-023` | API tests asserting malformed alert snapshots return structured failures, not raw dicts | done |
| `CI-RM-015` | medium | P1 | commit inputs | Optional JSON loaders silently discard non-dict items instead of failing invalid operator inputs. | Make accepted-risk and negotiated-change files schema-validated end-to-end and reject mixed/partial payloads. | `CI-RM-023` | commit tests with malformed JSON items and wrong schemas; assert hard failure | done |
| `CI-RM-016` | medium | P2 | ingestion | Document classification is filename-only and first-match-wins. | Add content-aware classification using file name, extracted text, clause headings, and confidence scoring. Keep filename hints as a fallback, not the sole classifier. | `CI-RM-017` | classifier tests with misleading filenames and accurate body text | done |
| `CI-RM-017` | medium | P2 | ingestion | PDF extraction is too lossy and can still mark documents as text-available when the content is junk. | Replace regex stream scraping with a real PDF extractor and track extraction quality/confidence so low-quality text degrades downstream trust. | none | PDF fixtures covering searchable, scanned, and malformed files; assert quality flags and fallback behavior | done |
| `CI-RM-018` | medium | P2 | ingestion | Project ingestion walks every file recursively without size or binary guards. | Add file extension allow/deny lists, size thresholds, binary sniffing, and optional max document counts per run. | none | ingestion tests with large binaries and nested irrelevant files | done |
| `CI-RM-019` | medium | P2 | adversarial review | Review challenges do not really analyze contradictions; they mostly report missing docs and unreadable files. | Add actual cross-artifact contradiction detection between findings, decision posture, missing docs, and outcome evidence. | `CI-RM-023` | tests asserting explicit contradiction records are produced for conflicting signals | done |
| `CI-RM-020` | medium | P2 | decision engine | Bid recommendation logic is under-escalated for combinations of HIGH findings and review hazards. | Rework recommendation thresholds using weighted severity, missing-doc counts, unreadable critical docs, and explicit no-go combinations. | `CI-RM-019`, `CI-RM-023` | decision regression tests for multi-HIGH and mixed-confidence cases | done |
| `CI-RM-021` | medium | P2 | ESE bridge | ESE prompt context is truncated by position, not salience, and can omit decisive clauses. | Build salience-ranked context packing that prioritizes required documents, severe findings, obligations, and clause-family hits before truncation. | `CI-RM-016`, `CI-RM-017` | prompt-packing tests asserting high-signal clauses survive truncation | done |
| `CI-RM-022` | low | P2 | UI | The dashboard silently treats missing artifact files as empty panels, masking partial-run corruption. | Surface artifact load failures explicitly in the UI and expose them in summary metrics and diagnostics. | `CI-RM-006` | UI tests for missing/corrupt artifacts; assert visible error states | done |
| `CI-RM-023` | low | P2 | models | Many workflow-critical fields are plain strings rather than constrained enums/literals. | Introduce stronger typed enums/literals for obligation types, statuses, alert types, owner roles, outcome states, and report modes. | none | model validation tests and downstream schema update tests | done |
| `CI-RM-024` | low | P3 | UI | The frontend silently swallows localStorage parse failures and operator state corruption. | Replace silent recovery with a visible warning toast/banner and a reset option so operators know their local review cache was discarded. | `CI-RM-013` | dashboard tests for corrupt localStorage payloads; assert warning is shown | done |

## Bundles And Shared Work

Some remediations are best implemented as bundles:

- **Lifecycle hardening bundle**: `CI-RM-001` through `CI-RM-006`
- **Monitoring integrity bundle**: `CI-RM-007` through `CI-RM-015`
- **Ingestion and reasoning quality bundle**: `CI-RM-016` through `CI-RM-021`
- **UI trust and ergonomics bundle**: `CI-RM-022` through `CI-RM-024`

## Execution Sequence

1. Land all `P0` items before any broader external or multi-operator rollout.
2. Land `P1` immediately after `P0` because monitoring and operator auditability
   depend on stable identities and validated state transitions.
3. Land `P2` next to improve extraction trust, decision calibration, and ESE
   context quality.
4. Close `P3` after server-backed review persistence is in place.

## Release Gate Recommendation

Before treating contract intelligence as more than a trusted local operator tool,
the minimum required closure set should be:

- `CI-RM-001` through `CI-RM-015`

The remaining items should still be tracked, but those first fifteen represent
the minimum credible protection and lifecycle baseline.

Current executed state:

- `P0` complete
- `P1` complete
- `P2` complete
- `P3` complete
- remediation matrix complete through `CI-RM-024`
