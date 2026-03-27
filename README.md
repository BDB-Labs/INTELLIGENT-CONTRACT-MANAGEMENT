# Ensemble Software Engineering (ESE)

ESE is a lightweight CLI framework for orchestrated AI ensembles. The core
engine stays generic, while config packs and application layers can ship fixed
role catalogs for specific domains.

This repository now contains both:

- the published `ese` orchestration engine and local dashboard
- an incubating `apps/contract_intelligence` product for construction contract
  compliance, monitoring, and lifecycle review

## Core pipeline

```mermaid
flowchart TD
  A["Human Scope"] --> B["Architect"]
  B --> C["Implementer"]
  C --> D["Adversarial Reviewer"]
  C --> E["Security Auditor"]
  C --> F["Test Generator"]
  C --> G["Performance Analyst"]
  D --> H["Human Merge"]
  E --> H
  F --> H
  G --> H
```

## Installation

```bash
pip install ese-cli
```

Or with `uv`:

```bash
uv tool install ese-cli
```

Homebrew install from the dedicated tap:

```bash
brew tap Excelsior2026/ese https://github.com/Excelsior2026/homebrew-ese
brew install ese-cli
```

If you want local models via Ollama:

```bash
brew install ollama
brew services start ollama
```

## Repository Development With UV

For local work from a clone of this repository, use `uv` as the primary
environment and command runner:

```bash
uv sync --locked
uv run ruff check ese tests
uv run pytest -q
```

If you are running commands from the repo instead of an installed package,
prefix CLI calls with `uv run`.

## One-Command Local Start

There is now a local GUI: the ESE dashboard.

From the repo root, the simplest way to start everything is:

```bash
./start_ese.sh
```

That script will:
- sync the project with `uv` using `uv.lock`,
- create or refresh the local `.venv` managed by `uv`,
- start the local dashboard GUI.

If you run a `local`/Ollama-backed workflow through the launcher, it now:
- auto-starts Ollama when it is installed but not running,
- prompts you to install Ollama or switch to a hosted provider when Ollama is missing.

Other common launcher modes:

```bash
./start_ese.sh task "Prepare a staged rollout plan for billing"
./start_ese.sh pr --base origin/main --head HEAD
./start_ese.sh cli report --artifacts-dir artifacts
```

## Production quickstart

For the fastest path, you can now start from a task description instead of writing config first:

```bash
ese task "Prepare a staged rollout plan for the new billing flow"
```

Use `ese templates` to inspect the built-in task templates.

If you want an explicit saved config, use the original wizard path:

1. Generate a config:

```bash
ese init --advanced
```

The wizard now asks for:
- a real project scope/task,
- whether you are creating a `framework` config or using a fixed `pack`,
- whether this should be a `demo` config (`dry-run`, no API calls) or a `live` config,
- provider/model defaults appropriate for that choice,
- either custom framework roles with starter prompt suggestions and overlap warnings, or a fixed pack-defined role set,
- optional per-role model overrides in advanced mode.

2. Validate configuration and ensemble constraints:

```bash
ese doctor --config ese.config.yaml
```

3. Execute the pipeline:

```bash
ese start --config ese.config.yaml
```

Pass `--artifacts-dir ...` only when you want to override `output.artifacts_dir` from the config.

4. Review outputs:
- `artifacts/ese_summary.md`
- `artifacts/pipeline_state.json`
- `artifacts/ese_config.snapshot.yaml`
- per-role reports in `artifacts/*.json` when `output.enforce_json: true` (default)

`ese run` remains available as a backward-compatible alias for `ese start`.

For ad hoc runs, you can override the saved scope:

```bash
ese start --config ese.config.yaml --scope "Review the release checklist for hidden rollback risks"
```

## Task-First CLI

Opinionated templates:

```bash
ese templates
```

Task-first execution without hand-authoring config:

```bash
ese task "Prepare a safer release workflow" --template release-readiness
```

Pull request review from a local diff or GitHub PR:

```bash
ese pr --repo-path . --base origin/main --head HEAD
```

Or, if you use GitHub CLI:

```bash
ese pr --repo-path . --pr 42
```

This writes the usual run artifacts plus `artifacts/pr_review.md`, a GitHub-ready review summary.

Status and aggregated reporting for an artifacts directory:

```bash
ese status --artifacts-dir artifacts
ese report --artifacts-dir artifacts
```

Rerun from a specific role while reusing upstream artifacts:

```bash
ese rerun implementer --artifacts-dir artifacts
```

Launch the local dashboard:

```bash
ese dashboard --artifacts-dir artifacts
```

The dashboard now supports both task-first runs and PR review runs.

## Contract Intelligence Application

The repository also includes a full-lifecycle contract-intelligence product
prototype aimed at public-infrastructure and roadway contract packages.

Current contract-intelligence lifecycle:

- bid review with contractor, insurance, compliance, procurement, outcome, and
  internal-only context artifacts
- committed contract state with accepted risks and negotiated changes
- obligation extraction and current/by-commit snapshots
- monitoring runs with due, late, satisfied, and alert state
- generated operator dashboard with internal/external display modes and
  server-backed human review actions
- thin local API over projects, runs, commits, obligations, monitoring, and
  alerts

Common commands:

```bash
uv run python -m apps.contract_intelligence bid-review ./sample_project
uv run python -m apps.contract_intelligence commit ./sample_project
uv run python -m apps.contract_intelligence monitor ./sample_project --status-inputs-file ./status_inputs.json
uv run python -m apps.contract_intelligence render-dashboard ./sample_project
uv run python -m apps.contract_intelligence render-dashboard ./sample_project --mode external
```

The contract-intelligence dashboard escapes rendered contract-derived content
before inserting it into dynamic HTML. Rendering with `--mode external`
produces a sanitized artifact that omits internal-only context, review-action
data, and sensitive path metadata from the embedded payload. Internal dashboard
artifacts should still be treated as sensitive local operator outputs.

## Framework role drafting

Use `ese roles` to print the built-in starter role examples for framework installs.
Use `ese packs` to list shipped config packs with fixed role catalogs.

- `architect`: System design, decomposition, and interface contracts.
- `implementer`: Code changes and refactors.
- `adversarial_reviewer`: Bug/risk hunting and regression checks.
- `security_auditor`: Threat modeling and vulnerability review.
- `test_generator`: Unit/integration/e2e test generation.
- `performance_analyst`: Latency, memory, and scalability analysis.
- `documentation_writer`: README, API docs, and migration notes.
- `devops_sre`: CI/CD, deploy safety, and observability.
- `database_engineer`: Schema/index/migration correctness.
- `release_manager`: Go/no-go risk assessment and rollout checks.

Framework installs are not limited to those names. The wizard can now generate starter prompts for user-defined roles and warn when responsibilities overlap enough to weaken ensemble independence.

## Provider/model selection and adapters

Wizard provider presets: `openai`, `anthropic`, `google`, `xai`, `openrouter`, `huggingface`, `local`, `custom_api`.
If no hosted-provider credentials are detected, the wizard now defaults to `local`, and choosing `local` defaults the execution mode to `live`.

Built-in runtime adapters:
- `dry-run`: deterministic placeholder artifacts, no API calls.
- `openai`: OpenAI Responses API adapter with retry/timeout handling.
- `local`: Ollama-backed local adapter using the OpenAI-compatible endpoint.
- `custom_api`: Responses-compatible custom provider adapter with validated base URL and auth env var.
- `module:function`: custom Python callable adapter.

When `output.enforce_json: true`, adapters must return valid JSON role reports and `gating.fail_on_high: true` will stop the pipeline on `HIGH` or `CRITICAL` findings.

## Demo vs live setup

- `demo`: writes a safe `dry-run` config using the selected provider/model defaults. This is the prudent path for first-time setup, local walkthroughs, and providers without native live adapters.
- `live`: uses the built-in runtime for `openai`, `local` (Ollama), and `custom_api`.
- Other providers remain available for model selection in the wizard, but live execution requires an explicit `module:function` adapter in advanced mode.

### Local runtime example

```yaml
provider:
  name: local
  model: qwen2.5-coder:14b
runtime:
  adapter: local
  timeout_seconds: 60
  max_retries: 2
  retry_backoff_seconds: 1.0
  local:
    base_url: http://localhost:11434/v1
    use_openai_compat_auth: true
```

### OpenAI runtime example

```yaml
provider:
  name: openai
  model: gpt-5-mini
  api_key_env: OPENAI_API_KEY
runtime:
  adapter: openai
  timeout_seconds: 60
  max_retries: 2
  retry_backoff_seconds: 1.0
  openai:
    base_url: https://api.openai.com/v1
```

### Custom API runtime example

```yaml
provider:
  name: my-gateway
  model: my-model-id
  api_key_env: CUSTOM_GATEWAY_TOKEN
  base_url: https://gateway.example/v1
runtime:
  adapter: custom_api
  timeout_seconds: 60
  max_retries: 2
  retry_backoff_seconds: 1.0
  custom_api:
    base_url: https://gateway.example/v1
```

## Contract documentation

- Config schema + version policy: [`docs/CONFIG_CONTRACT.md`](docs/CONFIG_CONTRACT.md)
- Pipeline state schema + deterministic role ordering: [`docs/PIPELINE_STATE.md`](docs/PIPELINE_STATE.md)
- Contract-intelligence product overview: [`apps/contract_intelligence/README.md`](apps/contract_intelligence/README.md)
- Case-intelligence platform design: [`docs/CASE_INTELLIGENCE_PLATFORM.md`](docs/CASE_INTELLIGENCE_PLATFORM.md)
- Contract-intelligence initiative and current extension targets: [`docs/CONTRACT_INTELLIGENCE_INITIATIVE.md`](docs/CONTRACT_INTELLIGENCE_INITIATIVE.md)
- Security posture and current advisory notes: [`docs/SECURITY_NOTES.md`](docs/SECURITY_NOTES.md)
- Troubleshooting: [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)
- Contributor CI requirements: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Release checklist for 1.0.0: [`MILESTONE_1_0_0.md`](MILESTONE_1_0_0.md)
- Changelog: [`CHANGELOG.md`](CHANGELOG.md)
- Release process: [`docs/RELEASE.md`](docs/RELEASE.md)
