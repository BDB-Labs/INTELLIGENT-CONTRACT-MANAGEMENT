from __future__ import annotations

import yaml

from ese.doctor import run_doctor


def _write_cfg(path, cfg: dict) -> str:
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return str(path)


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
            "architect": {"model": "gpt-5"},
            "implementer": {"model": "gpt-5-mini"},
        },
        "constraints": {
            "disallow_same_model_pairs": [["architect", "implementer"]],
        },
        "runtime": {
            "adapter": "dry-run",
        },
        "input": {
            "scope": "Review release readiness for a service hardening change",
        },
    }


def test_doctor_detects_shared_model_violation(tmp_path) -> None:
    cfg = _base_cfg()
    cfg["roles"]["implementer"]["model"] = "gpt-5"
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, role_models = run_doctor(path)

    assert not ok
    assert "architect and implementer share model openai:gpt-5" in violations
    assert role_models["architect"] == "openai:gpt-5"


def test_doctor_uses_dynamic_role_list(tmp_path) -> None:
    cfg = _base_cfg()
    cfg["roles"] = {
        "architect": {"model": "gpt-5"},
        "documentation_writer": {"model": "gpt-5-mini"},
    }
    cfg["constraints"]["disallow_same_model_pairs"] = [["architect", "documentation_writer"]]
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, role_models = run_doctor(path)

    assert ok
    assert violations == []
    assert set(role_models.keys()) == {"architect", "documentation_writer"}


def test_doctor_reports_config_validation_error(tmp_path) -> None:
    cfg = _base_cfg()
    cfg["version"] = 9
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, role_models = run_doctor(path)

    assert not ok
    assert role_models == {}
    assert len(violations) == 1
    assert "unsupported version 9; expected 1" in violations[0]


def test_doctor_fails_when_scope_is_missing(tmp_path) -> None:
    cfg = _base_cfg()
    cfg.pop("input", None)
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, role_models = run_doctor(path)

    assert not ok
    assert "No project scope supplied. Set input.scope in the config or pass --scope." in violations
    assert set(role_models.keys()) == {"architect", "implementer"}


def test_doctor_enforces_required_roles_and_provider_separation(tmp_path) -> None:
    cfg = _base_cfg()
    cfg["roles"]["adversarial_reviewer"] = {
        "provider": "openrouter",
        "model": "openai/gpt-5-mini",
    }
    cfg["constraints"]["require_roles"] = ["architect", "adversarial_reviewer"]
    cfg["constraints"]["disallow_same_provider_pairs"] = [["architect", "adversarial_reviewer"]]
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, _role_models = run_doctor(path)

    assert ok
    assert violations == []


def test_doctor_rejects_minimum_distinct_models_shortfall(tmp_path) -> None:
    cfg = _base_cfg()
    cfg["roles"]["implementer"]["model"] = "gpt-5"
    cfg["constraints"]["minimum_distinct_models"] = 2
    path = _write_cfg(tmp_path / "ese.config.yaml", cfg)

    ok, violations, _role_models = run_doctor(path)

    assert not ok
    assert any("at least 2 distinct role models" in item for item in violations)
