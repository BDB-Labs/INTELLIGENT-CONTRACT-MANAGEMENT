from __future__ import annotations

import json
from pathlib import Path

import pytest

from ese.pipeline import PipelineError, _role_prompt, run_pipeline


def _cfg() -> dict:
    return {
        "version": 1,
        "mode": "ensemble",
        "execution_mode": "demo",
        "provider": {
            "name": "openai",
            "model": "gpt-5-mini",
            "api_key_env": "OPENAI_API_KEY",
        },
        "roles": {
            "architect": {},
            "implementer": {},
            "adversarial_reviewer": {},
        },
        "runtime": {
            "adapter": "dry-run",
        },
        "input": {
            "scope": "Build a to-do CLI",
        },
    }


def test_pipeline_writes_expected_artifacts_and_state(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"

    summary_path = run_pipeline(_cfg(), artifacts_dir=str(artifacts_dir))

    assert summary_path == str(artifacts_dir / "ese_summary.md")
    assert (artifacts_dir / "ese_config.snapshot.yaml").exists()
    assert (artifacts_dir / "01_architect.json").exists()
    assert (artifacts_dir / "02_implementer.json").exists()
    assert (artifacts_dir / "03_adversarial_reviewer.json").exists()

    state = json.loads((artifacts_dir / "pipeline_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert state["config_snapshot"] == str(artifacts_dir / "ese_config.snapshot.yaml")
    executed_roles = [item["role"] for item in state["execution"]]
    assert executed_roles == ["architect", "implementer", "adversarial_reviewer"]


def test_pipeline_context_chaining_visible_in_dry_run_outputs(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    run_pipeline(_cfg(), artifacts_dir=str(artifacts_dir))

    implementer_output = json.loads((artifacts_dir / "02_implementer.json").read_text(encoding="utf-8"))
    reviewer_output = json.loads((artifacts_dir / "03_adversarial_reviewer.json").read_text(encoding="utf-8"))

    assert implementer_output["metadata"]["context_keys"] == ["architect"]
    assert reviewer_output["metadata"]["context_keys"] == ["architect", "implementer"]


def test_pipeline_uses_role_prompt_override_for_custom_roles(tmp_path: Path) -> None:
    cfg = _cfg()
    cfg["roles"] = {
        "custom_role": {
            "prompt": "Use findings for contract issues, not software defects.",
        },
    }
    cfg["gating"] = {"fail_on_high": False}
    artifacts_dir = tmp_path / "artifacts"

    run_pipeline(cfg, artifacts_dir=str(artifacts_dir))

    custom_output = json.loads((artifacts_dir / "01_custom_role.json").read_text(encoding="utf-8"))
    assert "Use findings for contract issues, not software defects." in custom_output["metadata"]["prompt_excerpt"]


def test_pipeline_custom_roles_receive_prior_outputs_as_context(tmp_path: Path) -> None:
    cfg = _cfg()
    cfg["roles"] = {
        "document_intake_analyst": {"prompt": "First custom domain role."},
        "contract_risk_analyst": {"prompt": "Second custom domain role."},
    }
    cfg["gating"] = {"fail_on_high": False}
    artifacts_dir = tmp_path / "artifacts"

    run_pipeline(cfg, artifacts_dir=str(artifacts_dir))

    second_output = json.loads((artifacts_dir / "02_contract_risk_analyst.json").read_text(encoding="utf-8"))
    assert second_output["metadata"]["context_keys"] == ["document_intake_analyst"]


def test_pipeline_orders_custom_roles_after_builtin_order(tmp_path: Path) -> None:
    cfg = _cfg()
    cfg["roles"] = {
        "custom_role": {},
        "implementer": {},
        "architect": {},
    }

    artifacts_dir = tmp_path / "artifacts"
    run_pipeline(cfg, artifacts_dir=str(artifacts_dir))

    state = json.loads((artifacts_dir / "pipeline_state.json").read_text(encoding="utf-8"))
    executed_roles = [item["role"] for item in state["execution"]]
    assert executed_roles == ["architect", "implementer", "custom_role"]


def test_pipeline_honors_explicit_role_order_for_domain_packs(tmp_path: Path) -> None:
    cfg = _cfg()
    cfg["roles"] = {
        "document_intake_analyst": {"prompt": "Intake."},
        "contract_risk_analyst": {"prompt": "Risk."},
        "adversarial_reviewer": {"prompt": "Challenge."},
    }
    cfg["role_order"] = [
        "document_intake_analyst",
        "contract_risk_analyst",
        "adversarial_reviewer",
    ]
    cfg["gating"] = {"fail_on_high": False}
    artifacts_dir = tmp_path / "artifacts"

    run_pipeline(cfg, artifacts_dir=str(artifacts_dir))

    state = json.loads((artifacts_dir / "pipeline_state.json").read_text(encoding="utf-8"))
    executed_roles = [item["role"] for item in state["execution"]]
    assert executed_roles == cfg["role_order"]


def test_pipeline_uses_configured_artifacts_dir_when_not_overridden(tmp_path: Path) -> None:
    cfg = _cfg()
    configured_dir = tmp_path / "configured-artifacts"
    cfg["output"] = {"artifacts_dir": str(configured_dir), "enforce_json": True}

    summary_path = run_pipeline(cfg)

    assert summary_path == str(configured_dir / "ese_summary.md")
    assert (configured_dir / "01_architect.json").exists()


def test_pipeline_blocks_on_high_severity_findings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg()
    artifacts_dir = tmp_path / "artifacts"

    def _gating_adapter(**kwargs) -> str:  # noqa: ANN003
        role = kwargs["role"]
        if role == "architect":
            return json.dumps(
                {
                    "summary": "Architecture complete.",
                    "findings": [],
                    "artifacts": [],
                    "next_steps": [],
                },
            )
        return json.dumps(
            {
                "summary": "Reviewer found a release blocker.",
                "findings": [
                    {
                        "severity": "HIGH",
                        "title": "Release blocker",
                        "details": "A critical defect must be fixed before continuing.",
                    },
                ],
                "artifacts": [],
                "next_steps": ["Fix the blocker."],
            },
        )

    monkeypatch.setattr("ese.pipeline._resolve_adapter", lambda cfg: ("test-gating", _gating_adapter))

    with pytest.raises(PipelineError) as exc:
        run_pipeline(cfg, artifacts_dir=str(artifacts_dir))

    assert "Pipeline gated by HIGH severity findings" in str(exc.value)

    state = json.loads((artifacts_dir / "pipeline_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert "Release blocker" in state["failure"]


def test_pipeline_can_rerun_from_a_specific_role(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg()
    artifacts_dir = tmp_path / "artifacts"
    calls: list[str] = []

    def _tracking_adapter(**kwargs) -> str:  # noqa: ANN003
        role = kwargs["role"]
        calls.append(role)
        return json.dumps(
            {
                "summary": f"{role} finished.",
                "findings": [],
                "artifacts": [],
                "next_steps": [],
            },
        )

    monkeypatch.setattr("ese.pipeline._resolve_adapter", lambda cfg: ("tracking", _tracking_adapter))

    run_pipeline(cfg, artifacts_dir=str(artifacts_dir))
    assert calls == ["architect", "implementer", "adversarial_reviewer"]

    calls.clear()
    run_pipeline(cfg, artifacts_dir=str(artifacts_dir), start_role="implementer")

    assert calls == ["implementer", "adversarial_reviewer"]
    state = json.loads((artifacts_dir / "pipeline_state.json").read_text(encoding="utf-8"))
    executed_roles = [item["role"] for item in state["execution"]]
    assert executed_roles == ["architect", "implementer", "adversarial_reviewer"]


def test_pipeline_rejects_non_json_output_when_enforced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts_dir = tmp_path / "artifacts"

    def _bad_adapter(**kwargs) -> str:  # noqa: ANN003
        return "not json"

    monkeypatch.setattr("ese.pipeline._resolve_adapter", lambda cfg: ("bad-adapter", _bad_adapter))

    with pytest.raises(PipelineError) as exc:
        run_pipeline(_cfg(), artifacts_dir=str(artifacts_dir))

    assert "must be valid JSON" in str(exc.value)


def test_pipeline_requires_explicit_scope(tmp_path: Path) -> None:
    cfg = _cfg()
    cfg.pop("input")

    with pytest.raises(PipelineError) as exc:
        run_pipeline(cfg, artifacts_dir=str(tmp_path / "artifacts"))

    assert "Set input.scope in the config or pass --scope" in str(exc.value)


def test_pipeline_rejects_empty_role_configuration(tmp_path: Path) -> None:
    cfg = _cfg()
    cfg["roles"] = {}

    with pytest.raises(PipelineError) as exc:
        run_pipeline(cfg, artifacts_dir=str(tmp_path / "artifacts"))

    assert "No roles configured" in str(exc.value)


def test_pipeline_rejects_non_mapping_roles_configuration(tmp_path: Path) -> None:
    cfg = _cfg()
    cfg["roles"] = ["architect", "implementer"]

    with pytest.raises(PipelineError) as exc:
        run_pipeline(cfg, artifacts_dir=str(tmp_path / "artifacts"))

    assert "roles must be a mapping of role names to role configs" in str(exc.value)


def test_pipeline_invalid_adapter_message_lists_local_builtin(tmp_path: Path) -> None:
    cfg = _cfg()
    cfg["runtime"] = {"adapter": "not-a-reference"}

    with pytest.raises(PipelineError) as exc:
        run_pipeline(cfg, artifacts_dir=str(tmp_path / "artifacts"))

    assert "{'dry-run', 'openai', 'local', 'custom_api'}" in str(exc.value)


def test_documentation_writer_prompt_is_specialized() -> None:
    prompt = _role_prompt(
        role="documentation_writer",
        scope="Document a new authentication flow",
        outputs={
            "architect": "Introduce auth middleware and session contracts.",
            "implementer": "Added login handlers and token refresh support.",
        },
        enforce_json=True,
    )

    lowered = prompt.lower()
    assert "documentation deliverables" in lowered
    assert "readme updates" in lowered
    assert "migration guidance" in lowered


def test_release_manager_prompt_is_specialized() -> None:
    prompt = _role_prompt(
        role="release_manager",
        scope="Launch a staged rollout for feature flags",
        outputs={
            "architect": "Use a staged rollout with metrics checkpoints.",
            "implementer": "Implemented flag checks and telemetry hooks.",
        },
        enforce_json=True,
    )

    lowered = prompt.lower()
    assert "assess release readiness" in lowered
    assert "rollback readiness" in lowered


def test_specialist_prompt_includes_additional_context_without_placeholder_noise() -> None:
    prompt = _role_prompt(
        role="adversarial_reviewer",
        scope="Review pull request changes for a billing refactor",
        outputs={},
        additional_context="Unified diff:\n+ fix billing edge case",
        enforce_json=True,
    )

    assert "Additional Run Context" in prompt
    assert "Unified diff" in prompt
    assert "(none provided)" not in prompt
    assert "code_suggestions" in prompt


def test_pipeline_normalizes_structured_code_suggestions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts_dir = tmp_path / "artifacts"

    def _suggesting_adapter(**kwargs) -> str:  # noqa: ANN003
        role = kwargs["role"]
        return json.dumps(
            {
                "summary": f"{role} completed.",
                "findings": [],
                "artifacts": [],
                "next_steps": [],
                "code_suggestions": [
                    {
                        "path": "src/app.py",
                        "kind": "patch",
                        "summary": "Guard missing config",
                        "suggestion": "Add an early return before dereferencing config in the request handler.",
                        "snippet": "if config is None:\n    return default_response()",
                    },
                ],
            },
        )

    monkeypatch.setattr("ese.pipeline._resolve_adapter", lambda cfg: ("suggesting", _suggesting_adapter))

    run_pipeline(_cfg(), artifacts_dir=str(artifacts_dir))

    report = json.loads((artifacts_dir / "01_architect.json").read_text(encoding="utf-8"))
    assert report["code_suggestions"][0]["path"] == "src/app.py"
    assert report["code_suggestions"][0]["kind"] == "patch"
    assert "default_response" in report["code_suggestions"][0]["snippet"]


def test_pipeline_rejects_resume_artifact_outside_artifacts_dir(tmp_path: Path) -> None:
    cfg = _cfg()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    outside_artifact = tmp_path / "outside.json"
    outside_artifact.write_text("seeded output", encoding="utf-8")
    state = {
        "status": "completed",
        "artifacts": {
            "architect": str(outside_artifact),
        },
        "role_models": {
            "architect": "openai:gpt-5-mini",
        },
        "execution": [],
    }
    (artifacts_dir / "pipeline_state.json").write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(PipelineError) as exc:
        run_pipeline(cfg, artifacts_dir=str(artifacts_dir), start_role="implementer")

    assert "escapes artifacts_dir" in str(exc.value)
