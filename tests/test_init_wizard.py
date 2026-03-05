from __future__ import annotations

from pathlib import Path

from ese.init_wizard import (
    _apply_simple_mode_model_diversity,
    _ensemble_constraints,
    run_wizard,
)


class _FakePrompt:
    def __init__(self, answer) -> None:  # noqa: ANN001
        self._answer = answer

    def ask(self):  # noqa: ANN201
        return self._answer


def _patch_questionary(monkeypatch, *, selects, texts, confirms, checkboxes=None) -> None:
    select_answers = iter(selects)
    text_answers = iter(texts)
    confirm_answers = iter(confirms)
    checkbox_answers = iter(checkboxes or [])

    monkeypatch.setattr("ese.init_wizard.questionary.select", lambda *args, **kwargs: _FakePrompt(next(select_answers)))
    monkeypatch.setattr("ese.init_wizard.questionary.text", lambda *args, **kwargs: _FakePrompt(next(text_answers)))
    monkeypatch.setattr("ese.init_wizard.questionary.confirm", lambda *args, **kwargs: _FakePrompt(next(confirm_answers)))
    monkeypatch.setattr("ese.init_wizard.questionary.checkbox", lambda *args, **kwargs: _FakePrompt(next(checkbox_answers)))
    monkeypatch.setattr("ese.init_wizard.questionary.print", lambda *args, **kwargs: None)


def test_ensemble_constraints_filters_to_selected_roles() -> None:
    constraints = _ensemble_constraints(["architect", "implementer", "release_manager"])

    assert constraints["disallow_same_model_pairs"] == [
        ["architect", "implementer"],
        ["implementer", "release_manager"],
    ]


def test_simple_mode_model_diversity_overrides_implementer() -> None:
    cfg = {
        "provider": {"name": "openai", "model": "gpt-5"},
        "roles": {
            "architect": {},
            "implementer": {},
        },
    }

    _apply_simple_mode_model_diversity(
        cfg,
        provider="openai",
        selected_roles=["architect", "implementer"],
    )

    assert cfg["roles"]["implementer"]["model"] != "gpt-5"


def test_run_wizard_writes_scope_and_demo_config(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "ese.config.yaml"
    _patch_questionary(
        monkeypatch,
        selects=[
            "ensemble",
            "anthropic",
            "demo",
            "balanced",
            "recommended (claude-sonnet-4)",
        ],
        texts=[
            "Document the deployment workflow for the new auth system",
        ],
        confirms=[True, True, True],
    )

    written = run_wizard(str(config_path), advanced=False)

    assert written == str(config_path)
    contents = config_path.read_text(encoding="utf-8")
    assert "scope: Document the deployment workflow for the new auth system" in contents
    assert "adapter: dry-run" in contents


def test_run_wizard_rejects_invalid_custom_adapter_before_write(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "ese.config.yaml"
    _patch_questionary(
        monkeypatch,
        selects=[
            "ensemble",
            "openai",
            "custom_module",
            "fast",
            "recommended (gpt-5-mini)",
        ],
        texts=[
            "Ship a demo safely",
            "invalid-adapter",
        ],
        confirms=[True, True, False],
        checkboxes=[
            ["architect", "implementer"],
        ],
    )

    written = run_wizard(str(config_path), advanced=True)

    assert written is None
    assert not config_path.exists()
