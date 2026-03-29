# ESE Platform Downstream Sync Matrix

Date: 2026-03-29

## Policy

ICM should treat `ese/` as a downstream-consumed platform layer.

Default sync direction:

1. Platform (`upstream/main` in `Excelsior2026/ensemble-software-engineering`) can flow down into ICM.
2. Application-specific changes made in ICM should not be pushed back into the platform by default.
3. If ICM develops a genuinely framework-level improvement, that should be extracted deliberately and proposed upstream as a separate, generalized platform change, not pushed back automatically.

This keeps the platform stable and reusable while allowing ICM to evolve product-specific behavior in `apps/contract_intelligence`.

## Current Divergence Snapshot

As of 2026-03-29:

- `origin/main` and local `main`: in sync
- `upstream/main...main`: ICM is `6` commits ahead and `1` commit behind
- Shared framework divergence is limited to `ese/`
- Product divergence is concentrated in `apps/contract_intelligence/`

Common-base comparison:

- Upstream changed `10` files under `ese/`
- ICM changed `9` files under `ese/`
- Overlap is concentrated in:
  - `ese/pipeline.py`
  - `ese/config.py`
  - `ese/cli.py`
  - `ese/doctor.py`
  - `ese/init_wizard.py`
  - `ese/dashboard.py`
  - `ese/templates.py`

Upstream-only governance commit currently missing from ICM:

- `4c7f865` `Complete governance hardening pass for ensemble contracts, uncertainty, and run lineage (#10)`

## Bottom-Line Assessment

Comparing ICM to upstream ESE is still worth doing, but only in the shared `ese/` framework layer.

It is not worth trying to compare or reconcile `apps/contract_intelligence` against upstream, because that is now a product layer with its own lifecycle, persistence, UI, and monitoring concerns.

The practical benefit is:

- upstream ESE still contains framework-level governance improvements that ICM has not absorbed
- ICM has local hardening that should stay local unless intentionally generalized
- the overlap is small enough to manage with a targeted merge plan

## Sync Status Update

Completed in ICM on 2026-03-29:

- `ese/config.py`
- `ese/doctor.py`
- `ese/pipeline.py`
- `ese/adapters.py`
- `ese/reports.py`
- `ese/cli.py`
- `ese/init_wizard.py`

Still intentionally local or low-priority:

- `ese/dashboard.py`
- `ese/feedback.py`
- `ese/config_packs.py`
- `ese/templates.py`
- `ese/__init__.py`

## File-by-File Merge Matrix

| File | Upstream Delta | ICM Delta | Recommendation | Priority | Notes |
| --- | --- | --- | --- | --- | --- |
| `ese/pipeline.py` | Major governance expansion: run lineage, assurance levels, prompt truncation, review isolation, richer JSON contract, contract versions | Local fail-closed adapter configuration and no swallowed supplemental artifact failures | Manual merge | P0 | Highest-value sync target. Both sides changed core execution logic. Upstream work should be selectively integrated on top of local hardening, not overwritten. |
| `ese/config.py` | Major config governance expansion: `strict_config`, `review_isolation`, role/provider identity helpers, stronger constraints schema | Local explicit `execution_mode` and required adapter contract | Manual merge | P0 | Strong downstream value. Upstream governance settings complement local live/demo enforcement. |
| `ese/doctor.py` | Major enforcement expansion: baseline model independence, provider diversity, required roles, minimum distinct models, JSON enforcement checks | Local guidance for explicit adapter selection and demo-mode messaging | Manual merge | P0 | High-value downstream adoption. This improves ensemble integrity without touching product-layer logic. |
| `ese/cli.py` | Stronger preflight policy, doctor gating, quiet mode, better TTY handling, consolidated run execution | Local fix for PR review artifact path handling | Manual merge | P1 | Upstream structure is better. Fold local PR artifact fix into upstream command flow. |
| `ese/adapters.py` | Upstream-only: better dry-run payload contract, assurance tagging, redacted errors, role-aware error messages, retry jitter, prompt isolation cleanup | No local changes | Adopt downstream | P1 | Good candidate for direct adoption after `config` and `pipeline` are aligned. |
| `ese/reports.py` | Upstream-only: run IDs, assurance notes, confidence, assumptions, unknowns, recurring unknowns, stronger release gating | No local changes | Adopt downstream | P1 | High value, but should land after `pipeline.py` because it expects richer state/report data. |
| `ese/init_wizard.py` | Better simple-mode model diversity across multiple specialist roles | Local addition of `execution_mode` to generated config | Manual merge | P2 | Low conflict and worthwhile. Keep local execution-mode generation while taking upstream diversity logic. |
| `ese/templates.py` | Upstream import cleanup only | Local addition of `execution_mode` in generated task configs | Keep local / no meaningful sync needed | P3 | No real upstream functional gain. |
| `ese/dashboard.py` | Upstream import reshuffle only | Local fail-closed persisted state handling | Keep local / no meaningful sync needed | P3 | Local version is operationally stronger. |
| `ese/feedback.py` | No upstream change | Local fail-closed feedback store integrity | Keep local | P2 | Leave local. Potential upstream candidate later if intentionally generalized. |
| `ese/config_packs.py` | No upstream counterpart change | Local-only config pack support | Keep local | P3 | Product/distribution convenience, not an upstream sync target. |
| `ese/__init__.py` | Whitespace-only cleanup | No local change | Ignore | P3 | No material value. |

## Recommended Integration Order

Do not merge upstream platform changes in arbitrary order. The useful sequence is:

1. `ese/config.py`
2. `ese/doctor.py`
3. `ese/pipeline.py`
4. `ese/adapters.py`
5. `ese/reports.py`
6. `ese/cli.py`
7. `ese/init_wizard.py`
8. review `ese/dashboard.py`, `ese/templates.py`, and `ese/__init__.py` only for low-risk cleanup

Reasoning:

- `config`, `doctor`, and `pipeline` define the runtime contract
- `adapters` and `reports` should inherit that contract rather than forcing it
- `cli` should be merged after the runtime behavior is settled
- wizard/template changes are lower risk and mostly UX/config generation

## Merge Method

Recommended method:

1. Compare `upstream/main` against the merge base for each target file.
2. Apply upstream framework changes into ICM manually for overlapping files.
3. Preserve local ICM hardening where it already tightens failure semantics.
4. Run the full repo test suite after each major merge group, not only at the end.

Avoid:

- wholesale merging of `upstream/main`
- attempting to reconcile `apps/contract_intelligence` with upstream
- pushing ICM-specific product features back into ESE without first generalizing them

## What Should Flow Down

These upstream themes are worth bringing into ICM:

- run lineage and report contract versioning
- assurance-level signaling
- stronger ensemble independence checks
- stricter config validation
- richer structured uncertainty reporting
- safer retry and error redaction behavior in adapters

## What Should Stay Local

These ICM themes should remain local unless deliberately generalized:

- contract-intelligence product workflows
- operator dashboard and report surfaces for contract review
- ICM-specific persistence and monitoring
- path and workspace controls added for the contract-intelligence app
- local fail-closed changes that were made to protect ICM’s operational behavior, unless they can be generalized cleanly

## Practical Conclusion

The right model is:

- ESE remains the platform
- ICM remains the downstream application
- platform improvements can and should flow down into ICM
- ICM improvements should only flow up when they are refactored into platform-grade abstractions

That means a targeted upstream-framework comparison is still useful today, and the highest-value next comparison is the `P0`/`P1` set in this matrix.
