from __future__ import annotations

import pytest

from ese.config import ConfigValidationError, resolve_role_model, validate_config


def _base_cfg() -> dict:
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
        },
        "constraints": {
            "disallow_same_model_pairs": [["architect", "implementer"]],
        },
        "runtime": {
            "adapter": "dry-run",
            "timeout_seconds": 60,
            "max_retries": 2,
            "retry_backoff_seconds": 1.0,
        },
        "input": {
            "scope": "Review a login refactor",
        },
    }


def test_validate_config_accepts_zero_max_retries() -> None:
    cfg = _base_cfg()
    cfg["runtime"]["max_retries"] = 0

    validated = validate_config(cfg)

    assert validated["runtime"]["max_retries"] == 0


def test_validate_config_rejects_version_mismatch() -> None:
    cfg = _base_cfg()
    cfg["version"] = 2

    with pytest.raises(ConfigValidationError) as exc:
        validate_config(cfg, source="test.yaml")

    assert "unsupported version 2; expected 1" in str(exc.value)
    assert "test.yaml" in str(exc.value)


def test_validate_config_rejects_empty_roles() -> None:
    cfg = _base_cfg()
    cfg["roles"] = {}

    with pytest.raises(ConfigValidationError) as exc:
        validate_config(cfg, source="test.yaml")

    assert "must include at least one configured role" in str(exc.value)


def test_resolve_role_model_prefers_role_override() -> None:
    cfg = _base_cfg()
    cfg["roles"]["architect"] = {"provider": "openrouter", "model": "openai/gpt-5"}

    model_ref = resolve_role_model(cfg, "architect")

    assert model_ref == "openrouter:openai/gpt-5"


def test_custom_api_contract_requires_base_url() -> None:
    cfg = _base_cfg()
    cfg["provider"] = {
        "name": "my-gateway",
        "model": "my-model",
        "api_key_env": "CUSTOM_GATEWAY_TOKEN",
    }
    cfg["runtime"]["adapter"] = "custom_api"

    with pytest.raises(ConfigValidationError) as exc:
        validate_config(cfg, source="test.yaml")

    assert "runtime.adapter=custom_api requires provider.base_url or runtime.custom_api.base_url" in str(exc.value)


def test_validate_config_rejects_fail_on_high_without_json() -> None:
    cfg = _base_cfg()
    cfg["output"] = {"artifacts_dir": "artifacts", "enforce_json": False}
    cfg["gating"] = {"fail_on_high": True}

    with pytest.raises(ConfigValidationError) as exc:
        validate_config(cfg, source="test.yaml")

    assert "gating.fail_on_high requires output.enforce_json" in str(exc.value)


def test_validate_config_rejects_openai_adapter_with_non_openai_role_provider() -> None:
    cfg = _base_cfg()
    cfg["runtime"]["adapter"] = "openai"
    cfg["roles"]["implementer"] = {
        "provider": "openrouter",
        "model": "openai/gpt-5",
    }

    with pytest.raises(ConfigValidationError) as exc:
        validate_config(cfg, source="test.yaml")

    assert "runtime.adapter=openai requires all role providers to resolve to 'openai'" in str(exc.value)


def test_validate_config_rejects_custom_api_role_provider_mismatch() -> None:
    cfg = _base_cfg()
    cfg["provider"] = {
        "name": "my-gateway",
        "model": "my-model",
        "api_key_env": "CUSTOM_GATEWAY_TOKEN",
        "base_url": "https://gateway.example/v1",
    }
    cfg["runtime"]["adapter"] = "custom_api"
    cfg["runtime"]["custom_api"] = {"base_url": "https://gateway.example/v1"}
    cfg["roles"]["implementer"] = {
        "provider": "other-gateway",
        "model": "other-model",
    }

    with pytest.raises(ConfigValidationError) as exc:
        validate_config(cfg, source="test.yaml")

    assert "runtime.adapter=custom_api requires all role providers to match provider.name='my-gateway'" in str(exc.value)


def test_validate_config_rejects_invalid_custom_adapter_format() -> None:
    cfg = _base_cfg()
    cfg["runtime"]["adapter"] = "not-a-reference"

    with pytest.raises(ConfigValidationError) as exc:
        validate_config(cfg, source="test.yaml")

    assert "module:function" in str(exc.value)


def test_validate_config_accepts_local_adapter() -> None:
    cfg = _base_cfg()
    cfg["provider"] = {
        "name": "local",
        "model": "qwen2.5-coder:14b",
        "base_url": "http://localhost:11434/v1",
    }
    cfg["roles"] = {
        "architect": {},
        "implementer": {"model": "llama3.1:8b"},
    }
    cfg["runtime"]["adapter"] = "local"
    cfg["runtime"]["local"] = {"base_url": "http://localhost:11434/v1"}

    validated = validate_config(cfg, source="test.yaml")

    assert validated["runtime"]["adapter"] == "local"
    assert validated["runtime"]["local"]["base_url"] == "http://localhost:11434/v1"


def test_validate_config_accepts_explicit_role_order() -> None:
    cfg = _base_cfg()
    cfg["role_order"] = ["implementer", "architect"]

    validated = validate_config(cfg, source="test.yaml")

    assert validated["role_order"] == ["implementer", "architect"]


def test_validate_config_rejects_role_order_unknown_role() -> None:
    cfg = _base_cfg()
    cfg["role_order"] = ["architect", "unknown_role"]

    with pytest.raises(ConfigValidationError) as exc:
        validate_config(cfg, source="test.yaml")

    assert "role_order references unknown configured roles" in str(exc.value)
