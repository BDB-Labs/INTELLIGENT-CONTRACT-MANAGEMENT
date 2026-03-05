# Troubleshooting

## Auth failures

### OpenAI adapter

Symptoms:
- `Missing API key in env var 'OPENAI_API_KEY' for OpenAI adapter`
- `OpenAI authentication failed...`

Checks:
- Ensure `provider.api_key_env` points to a real env var.
- Ensure token has valid scope for the target endpoint.
- Confirm `runtime.openai.base_url` is correct if overridden.

### Custom API adapter

Symptoms:
- `Missing API key in env var '<NAME>' for custom_api adapter`
- `Custom API authentication failed...`

Checks:
- Ensure `provider.api_key_env` is set and exported.
- Verify `provider.base_url` or `runtime.custom_api.base_url`.
- Confirm provider/model mapping matches your gateway routing.

## Config validation failures

Symptoms:
- `Invalid ESE config at ...`
- `unsupported version ...; expected 1`

Checks:
- Validate top-level keys against [`CONFIG_CONTRACT.md`](CONFIG_CONTRACT.md).
- Ensure `version: 1` for current releases.
- Ensure `runtime.max_retries` is an integer `>= 0`.
- Ensure `gating.fail_on_high` is only used with `output.enforce_json: true`.
- Ensure built-in adapter/provider combinations are compatible (for example `runtime.adapter=openai` requires OpenAI role providers only).

## Ensemble doctor violations

Symptoms:
- `architect and implementer share model ...`

Checks:
- Update per-role overrides in `roles`.
- Update `constraints.disallow_same_model_pairs` to match your threat model.
- Re-run `ese doctor --config ese.config.yaml`.

## Adapter execution failures

Symptoms:
- HTTP errors (`429`, `5xx`) with retry exhaustion.
- `Adapter output for role '...' must be valid JSON when output.enforce_json=true`

Checks:
- Increase `runtime.timeout_seconds`.
- Increase `runtime.max_retries`.
- Tune `runtime.retry_backoff_seconds`.
- Validate upstream provider/gateway reliability.
- Ensure custom adapters return the required JSON report object when `output.enforce_json: true`.

## Gated pipeline failures

Symptoms:
- `Pipeline gated by HIGH severity findings in role '...'`

Checks:
- Inspect the failing role artifact and `pipeline_state.json`.
- Fix or waive the blocking findings before rerunning.
- Set `gating.fail_on_high: false` only if you intentionally want advisory-only execution.

## Pipeline output interpretation

Checks:
- `ese_summary.md` gives execution overview.
- `pipeline_state.json` provides deterministic machine-readable state.
- Schema details: [`PIPELINE_STATE.md`](PIPELINE_STATE.md).
