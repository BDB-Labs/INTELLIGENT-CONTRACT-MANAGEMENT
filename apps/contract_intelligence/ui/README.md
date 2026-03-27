# UI Surface

This directory now contains the generated operator-facing dashboard for the contract-intelligence product.

Current dashboard characteristics:

- rich single-file HTML output for local review and sharing
- executive masthead with project status, recommendation, confidence, and KPI cards
- left-rail navigation across overview, decision, review board, findings, obligations, context, procurement, documents, and lifecycle history
- internal vs external report mode switching for audience-aware presentation
- interactive filtering plus drill-down detail panels for findings and obligations
- local human-review actions and disposition tracking stored in the browser
- committed baseline, monitoring state, and alert visibility in one surface
- internal context and procurement/outcome artifacts rendered without exposing them as external-facing report language
- escaped rendering of contract-derived content before it is inserted into dynamic HTML fragments

Primary entry point:

- `apps/contract_intelligence/ui/dashboard.py`

Current workflow:

1. Run bid review, commit, and monitoring against a project workspace.
2. Render the dashboard with the contract-intelligence CLI `render-dashboard` command.
3. Open the generated HTML artifact from the project `artifacts/` directory.

Near-term UI follow-on work:

- server-backed persistence for human review dispositions instead of local browser storage
- exportable external report snapshots derived from the selected report mode
- deeper action workflows that tie review decisions back into the lifecycle store
