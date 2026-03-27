# UI Surface

This directory now contains the generated operator-facing dashboard for the contract-intelligence product.

Current dashboard characteristics:

- rich single-file HTML output for local review and sharing
- executive masthead with project status, recommendation, confidence, and KPI cards
- left-rail navigation across overview, decision, review board, findings, obligations, context, procurement, documents, and lifecycle history
- internal vs external report mode switching for audience-aware presentation
- interactive filtering plus drill-down detail panels for findings and obligations
- server-backed human-review actions with browser caching when the dashboard is served through the local API
- committed baseline, monitoring state, and alert visibility in one surface
- internal context and procurement/outcome artifacts rendered without exposing them as external-facing report language
- escaped rendering of contract-derived content before it is inserted into dynamic HTML fragments
- artifact diagnostics that surface missing or corrupt lifecycle files instead of silently flattening them into empty panels
- visible local-cache recovery warning with a reset path when browser review state becomes unreadable
- text-quality visibility in the document inventory for higher-trust ingestion review

Primary entry point:

- `apps/contract_intelligence/ui/dashboard.py`

Current workflow:

1. Run bid review, commit, and monitoring against a project workspace.
2. Render the dashboard with the contract-intelligence CLI `render-dashboard` command.
3. Open the generated HTML artifact from the project `artifacts/` directory.

Near-term UI follow-on work:

- exportable external report snapshots derived from the selected report mode
- deeper action workflows that tie review decisions back into the lifecycle store
