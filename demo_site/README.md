# ICM Demo Site

This directory is the Vercel-facing public demo surface for ICM.

It is intentionally static and read-only.

## Expected contents

- `index.html`, `styles.css`, `app.js`: public demo shell
- `generated/manifest.json`: generated demo metadata
- `generated/cases/*/dashboard.html`: sanitized external dashboards

## Refresh demo assets

From the repository root:

```bash
uv sync --locked
uv run python -m apps.contract_intelligence build-demo
```

## Vercel recommendation

Point the Vercel project root at `demo_site/`.

Do not deploy the internal Python/FastAPI runtime directly to Vercel.
