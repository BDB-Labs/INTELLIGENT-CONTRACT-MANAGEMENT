# Release Process

## Version bump

1. Update `pyproject.toml` project version.
2. Update `CHANGELOG.md` with release date, features, and compatibility notes.
3. Verify docs for config/pipeline contracts and troubleshooting are current.
4. Verify product docs and security notes are current for `apps/contract_intelligence/`.

## Pre-release verification

Run locally:

```bash
uv sync --locked
uv run ruff check ese tests
uv run pytest -q
uv run ese doctor --config ese.config.yaml
uv run ese start --config ese.config.yaml --artifacts-dir artifacts
uv run pytest tests/test_contract_intelligence_corpus.py tests/test_contract_intelligence_ui.py tests/test_contract_intelligence_api.py tests/test_contract_intelligence_monitoring.py tests/test_contract_intelligence_commit_lifecycle.py tests/test_contract_intelligence_bid_review.py tests/test_contract_intelligence_ese_bridge.py tests/test_contract_intelligence_ingestion.py tests/test_contract_intelligence_scaffold.py
```

## Publish flow

1. Create and push a release tag (for example `v1.0.0`).
2. Publish a GitHub release from that tag.
3. GitHub release event triggers `.github/workflows/pypi-publish.yml`.
4. Workflow builds package and publishes to PyPI using `PYPI_API_TOKEN`.

## Post-release smoke checks

After publish:

```bash
uv venv /tmp/ese-smoke
UV_PYTHON=/tmp/ese-smoke/bin/python uv pip install "ese-cli==<version>"
/tmp/ese-smoke/bin/ese --help
/tmp/ese-smoke/bin/ese roles
```

Confirm CLI loads and basic commands execute.

Also verify:

- any dismissed security advisories in [`docs/SECURITY_NOTES.md`](SECURITY_NOTES.md)
  are still accurately characterized
- no new contract-intelligence lifecycle docs are stale relative to the shipped
  commands and dashboard behavior
