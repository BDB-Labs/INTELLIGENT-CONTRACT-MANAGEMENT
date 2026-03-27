# Security Notes

This document captures the current security and protection posture that is
implemented directly in the repository as of March 27, 2026.

## Current application safeguards

### Contract-intelligence API

The local FastAPI surface in `apps/contract_intelligence/api/` now defaults to
a safer local posture:

- interactive docs are disabled unless `CONTRACT_INTELLIGENCE_EXPOSE_DOCS=1`
  is explicitly set
- project directories are validated before lifecycle actions run
- optional input files are validated before commit and monitoring actions
- path access can be constrained with `CONTRACT_INTELLIGENCE_ALLOWED_ROOTS`

These defaults are meant to reduce accidental exposure and keep local operators
from pointing the application at arbitrary filesystem paths without intention.

### Contract-intelligence dashboard

The generated contract-intelligence dashboard now escapes contract-derived
values before inserting them into dynamic HTML fragments.

That reduces the obvious browser-side injection risk from filenames, clause
text, summaries, and other artifact content rendered into the operator surface.

### Exception posture

The current `apps/contract_intelligence` Python package has no bare `except:`
or broad `except Exception` handlers in its application code. Exception
handling there is currently limited to more specific failure paths such as
missing files and validation failures.

## Dashboard artifact boundaries

The contract-intelligence dashboard now has distinct internal and external
rendering paths.

When rendered in external mode, the generated HTML omits internal-only context,
review-action data, and sensitive path metadata from the embedded payload
itself.

Internal-mode dashboards still contain strategy-only material and should remain
inside the trusted operator boundary.

## Dependabot note

On March 27, 2026, the repository's only open Dependabot alert was:

- `GHSA-5239-wwwm-4pmq` / `CVE-2026-4539`
- package: `Pygments`
- manifest: `uv.lock`
- severity: low

At the time of review:

- `Pygments 2.19.2` was still the latest release on PyPI
- the advisory had no patched version available
- the issue was described as local-access only
- this repository does not process untrusted ADL/GUID input through the
  affected lexer path

The GitHub Dependabot alert was dismissed as `tolerable_risk` until an upstream
patched release becomes available.

## Next protection-oriented follow-on work

- introduce authentication and role-gated visibility if the local API or
  dashboard is ever promoted beyond trusted local use
- add signed or checksummed external exports if external dashboards become part
  of a formal reporting workflow
- continue tightening ingestion-quality controls for weak PDFs and low-signal
  source documents
