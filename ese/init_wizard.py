"""Interactive wizard for creating ese.config.yaml."""

from __future__ import annotations

import os
from typing import Any, Dict

import questionary

from ese.config import ConfigValidationError, resolve_role_model, validate_config, write_config

PROVIDER_CHOICES = [
    "openai",
    "anthropic",
    "google",
    "xai",
    "openrouter",
    "huggingface",
    "local",
    "custom_api",
]

PROVIDER_SUPPORT = {
    "openai": {
        "live_title": "openai - built-in live adapter",
        "demo_title": "openai - demo or built-in live adapter",
        "supports_live": True,
    },
    "anthropic": {
        "live_title": "anthropic - requires custom module adapter",
        "demo_title": "anthropic - demo only unless you bring a custom adapter",
        "supports_live": False,
    },
    "google": {
        "live_title": "google - requires custom module adapter",
        "demo_title": "google - demo only unless you bring a custom adapter",
        "supports_live": False,
    },
    "xai": {
        "live_title": "xai - requires custom module adapter",
        "demo_title": "xai - demo only unless you bring a custom adapter",
        "supports_live": False,
    },
    "openrouter": {
        "live_title": "openrouter - requires custom module adapter",
        "demo_title": "openrouter - demo only unless you bring a custom adapter",
        "supports_live": False,
    },
    "huggingface": {
        "live_title": "huggingface - requires custom module adapter",
        "demo_title": "huggingface - demo only unless you bring a custom adapter",
        "supports_live": False,
    },
    "local": {
        "live_title": "local - requires custom module adapter",
        "demo_title": "local - demo only unless you bring a custom adapter",
        "supports_live": False,
    },
    "custom_api": {
        "live_title": "custom_api - Responses-compatible gateway",
        "demo_title": "custom_api - demo or gateway-backed live adapter",
        "supports_live": True,
    },
}

DEMO_EXECUTION_MODE = "demo"
LIVE_EXECUTION_MODE = "live"
CUSTOM_MODULE_EXECUTION_MODE = "custom_module"

GOAL_PROFILES = [
    "fast",
    "balanced",
    "high-quality",
    "security-heavy",
]

GOAL_TO_PRESET = {
    "fast": "fast",
    "balanced": "balanced",
    "high-quality": "strict",
    "security-heavy": "paranoid",
}

GOAL_DEFAULT_ROLES: Dict[str, list[str]] = {
    "fast": [
        "architect",
        "implementer",
        "adversarial_reviewer",
        "test_generator",
    ],
    "balanced": [
        "architect",
        "implementer",
        "adversarial_reviewer",
        "security_auditor",
        "test_generator",
        "performance_analyst",
    ],
    "high-quality": [
        "architect",
        "implementer",
        "adversarial_reviewer",
        "security_auditor",
        "test_generator",
        "performance_analyst",
        "documentation_writer",
    ],
    "security-heavy": [
        "architect",
        "implementer",
        "adversarial_reviewer",
        "security_auditor",
        "test_generator",
        "performance_analyst",
        "devops_sre",
        "database_engineer",
        "release_manager",
    ],
}

COMMON_MODELS_BY_PROVIDER: Dict[str, list[str]] = {
    "openai": [
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "o3",
    ],
    "anthropic": [
        "claude-sonnet-4",
        "claude-opus-4",
    ],
    "google": [
        "gemini-2.0-flash",
        "gemini-2.0-pro",
    ],
    "xai": [
        "grok-3",
        "grok-3-mini",
    ],
    "openrouter": [
        "openai/gpt-5",
        "anthropic/claude-sonnet-4",
        "google/gemini-2.0-pro",
    ],
    "huggingface": [
        "meta-llama/Llama-3.3-70B-Instruct",
        "Qwen/Qwen2.5-Coder-32B-Instruct",
    ],
    "local": [
        "llama3.1:8b",
        "qwen2.5-coder:14b",
    ],
}

RECOMMENDED_MODEL_BY_PROVIDER_GOAL: Dict[str, Dict[str, str]] = {
    "openai": {
        "fast": "gpt-5-mini",
        "balanced": "gpt-5",
        "high-quality": "gpt-5",
        "security-heavy": "o3",
    },
    "anthropic": {
        "fast": "claude-sonnet-4",
        "balanced": "claude-sonnet-4",
        "high-quality": "claude-opus-4",
        "security-heavy": "claude-opus-4",
    },
    "google": {
        "fast": "gemini-2.0-flash",
        "balanced": "gemini-2.0-pro",
        "high-quality": "gemini-2.0-pro",
        "security-heavy": "gemini-2.0-pro",
    },
    "xai": {
        "fast": "grok-3-mini",
        "balanced": "grok-3",
        "high-quality": "grok-3",
        "security-heavy": "grok-3",
    },
    "openrouter": {
        "fast": "openai/gpt-5",
        "balanced": "anthropic/claude-sonnet-4",
        "high-quality": "google/gemini-2.0-pro",
        "security-heavy": "anthropic/claude-opus-4",
    },
    "huggingface": {
        "fast": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "balanced": "meta-llama/Llama-3.3-70B-Instruct",
        "high-quality": "meta-llama/Llama-3.3-70B-Instruct",
        "security-heavy": "meta-llama/Llama-3.3-70B-Instruct",
    },
    "local": {
        "fast": "llama3.1:8b",
        "balanced": "qwen2.5-coder:14b",
        "high-quality": "qwen2.5-coder:14b",
        "security-heavy": "qwen2.5-coder:14b",
    },
}

MODEL_ALIASES_BY_PROVIDER: Dict[str, Dict[str, str]] = {
    "openai": {
        "g5": "gpt-5",
        "g5mini": "gpt-5-mini",
        "g5nano": "gpt-5-nano",
        "reasoning": "o3",
    },
    "anthropic": {
        "sonnet": "claude-sonnet-4",
        "opus": "claude-opus-4",
    },
    "google": {
        "flash": "gemini-2.0-flash",
        "pro": "gemini-2.0-pro",
    },
    "xai": {
        "grok": "grok-3",
        "grok-mini": "grok-3-mini",
    },
    "openrouter": {
        "or-g5": "openai/gpt-5",
        "or-sonnet": "anthropic/claude-sonnet-4",
        "or-pro": "google/gemini-2.0-pro",
    },
}

CUSTOM_MODEL_CHOICE = "custom (type model id)"
RECOMMENDED_MODEL_CHOICE = "recommended"
COMMON_MODEL_CHOICE = "choose common model"
CUSTOM_OR_ALIAS_MODEL_CHOICE = "custom or alias"

ROLE_DESCRIPTIONS: Dict[str, str] = {
    "architect": "System design, decomposition, and interface contracts.",
    "implementer": "Code changes and refactors.",
    "adversarial_reviewer": "Bug/risk hunting and regression checks.",
    "security_auditor": "Threat modeling and vulnerability review.",
    "test_generator": "Unit/integration/e2e test generation.",
    "performance_analyst": "Latency, memory, and scalability analysis.",
    "documentation_writer": "README, API docs, and migration notes.",
    "devops_sre": "CI/CD, deploy safety, and observability.",
    "database_engineer": "Schema/index/migration correctness.",
    "release_manager": "Go/no-go risk assessment and rollout checks.",
}

DEFAULT_SELECTED_ROLES = [
    "architect",
    "implementer",
    "adversarial_reviewer",
    "security_auditor",
    "test_generator",
    "performance_analyst",
]

DEFAULT_DISALLOW_SAME_MODEL_PAIRS = [
    ("architect", "implementer"),
    ("implementer", "adversarial_reviewer"),
    ("implementer", "security_auditor"),
    ("implementer", "release_manager"),
]

ROLE_DEFAULTS_BY_PRESET: Dict[str, Dict[str, Dict[str, Any]]] = {
    "fast": {
        "architect": {"temperature": 0.2},
        "implementer": {"temperature": 0.1},
        "adversarial_reviewer": {"temperature": 0.6},
        "security_auditor": {"temperature": 0.2},
        "test_generator": {"temperature": 0.2},
        "performance_analyst": {"temperature": 0.2},
        "documentation_writer": {"temperature": 0.3},
        "devops_sre": {"temperature": 0.2},
        "database_engineer": {"temperature": 0.2},
        "release_manager": {"temperature": 0.2},
    },
    "balanced": {
        "architect": {"temperature": 0.2},
        "implementer": {"temperature": 0.1},
        "adversarial_reviewer": {"temperature": 0.7},
        "security_auditor": {"temperature": 0.2},
        "test_generator": {"temperature": 0.2},
        "performance_analyst": {"temperature": 0.2},
        "documentation_writer": {"temperature": 0.2},
        "devops_sre": {"temperature": 0.2},
        "database_engineer": {"temperature": 0.2},
        "release_manager": {"temperature": 0.2},
    },
    "strict": {
        "architect": {"temperature": 0.1},
        "implementer": {"temperature": 0.05},
        "adversarial_reviewer": {"temperature": 0.6},
        "security_auditor": {"temperature": 0.1},
        "test_generator": {"temperature": 0.1},
        "performance_analyst": {"temperature": 0.1},
        "documentation_writer": {"temperature": 0.15},
        "devops_sre": {"temperature": 0.1},
        "database_engineer": {"temperature": 0.1},
        "release_manager": {"temperature": 0.1},
    },
    "paranoid": {
        "architect": {"temperature": 0.1},
        "implementer": {"temperature": 0.05},
        "adversarial_reviewer": {"temperature": 0.8},
        "security_auditor": {"temperature": 0.1},
        "test_generator": {"temperature": 0.1},
        "performance_analyst": {"temperature": 0.1},
        "documentation_writer": {"temperature": 0.15},
        "devops_sre": {"temperature": 0.1},
        "database_engineer": {"temperature": 0.1},
        "release_manager": {"temperature": 0.1},
    },
}


def _default_api_key_env(provider: str) -> str:
    if provider == "openai":
        return "OPENAI_API_KEY"
    if provider == "anthropic":
        return "ANTHROPIC_API_KEY"
    if provider == "google":
        return "GOOGLE_API_KEY"
    if provider == "xai":
        return "XAI_API_KEY"
    if provider == "openrouter":
        return "OPENROUTER_API_KEY"
    if provider == "huggingface":
        return "HF_TOKEN"
    if provider == "local":
        return "LOCAL_MODEL"
    if provider == "custom_api":
        return "CUSTOM_API_KEY"
    return "MODEL_TOKEN"


def _provider_default_from_env() -> str:
    detectable_providers = PROVIDER_CHOICES
    configured = [p for p in detectable_providers if os.getenv(_default_api_key_env(p))]
    if not configured:
        return "openai"
    if len(configured) == 1:
        return configured[0]
    if "openai" in configured:
        return "openai"
    return configured[0]


def _provider_choices(*, advanced: bool) -> list[questionary.Choice]:
    choices: list[questionary.Choice] = []
    for provider in PROVIDER_CHOICES:
        support = PROVIDER_SUPPORT[provider]
        if support["supports_live"] or advanced:
            title = str(support["live_title"])
        else:
            title = str(support["demo_title"])
        choices.append(questionary.Choice(title=title, value=provider))
    return choices


def _validate_non_empty_text(label: str):
    def _validator(value: str | None) -> bool | str:
        if isinstance(value, str) and value.strip():
            return True
        return f"{label} is required."

    return _validator


def _validate_adapter_reference(value: str | None) -> bool | str:
    raw = (value or "").strip()
    module_name, separator, object_name = raw.partition(":")
    if separator and module_name.strip() and object_name.strip():
        return True
    return "Enter adapter reference in 'module:function' format."


def _resolve_model_alias(provider: str, model_name: str) -> str:
    raw = (model_name or "").strip()
    if not raw:
        return raw
    aliases = MODEL_ALIASES_BY_PROVIDER.get(provider, {})
    return aliases.get(raw.lower(), raw)


def _input_model_id(provider: str, prompt: str) -> str:
    alias_help = ", ".join(sorted(MODEL_ALIASES_BY_PROVIDER.get(provider, {}).keys()))
    if alias_help:
        prompt = f"{prompt} (aliases: {alias_help})"
    typed = questionary.text(prompt).ask()
    return _resolve_model_alias(provider, typed)


def _select_default_model(provider: str, goal_profile: str | None = None) -> str:
    common_models = COMMON_MODELS_BY_PROVIDER.get(provider, [])
    recommended = RECOMMENDED_MODEL_BY_PROVIDER_GOAL.get(provider, {}).get(goal_profile or "")

    if not common_models and recommended:
        return recommended

    if not common_models:
        return _input_model_id(provider, "Default model name (provider model id):")

    choices: list[str] = common_models + [CUSTOM_MODEL_CHOICE]
    default = common_models[0]
    if recommended:
        recommended_label = f"{RECOMMENDED_MODEL_CHOICE} ({recommended})"
        choices = [recommended_label, COMMON_MODEL_CHOICE, CUSTOM_OR_ALIAS_MODEL_CHOICE]
        default = recommended_label

    model_choice = questionary.select(
        "Default model:",
        choices=choices,
        default=default,
    ).ask()

    if model_choice == COMMON_MODEL_CHOICE:
        return questionary.select(
            "Choose common model:",
            choices=common_models,
            default=recommended if recommended in common_models else common_models[0],
        ).ask()

    if isinstance(model_choice, str) and model_choice.startswith(f"{RECOMMENDED_MODEL_CHOICE} (") and model_choice.endswith(")"):
        return model_choice[len(RECOMMENDED_MODEL_CHOICE) + 2 : -1]

    if model_choice in {CUSTOM_MODEL_CHOICE, CUSTOM_OR_ALIAS_MODEL_CHOICE}:
        return _input_model_id(provider, "Custom model id:")

    return model_choice


def _select_execution_mode(provider: str, *, advanced: bool) -> str:
    supports_live = bool(PROVIDER_SUPPORT[provider]["supports_live"])
    choices: list[questionary.Choice] = []

    if supports_live:
        live_title = "live - built-in runtime adapter"
        if provider == "custom_api":
            live_title = "live - Responses-compatible gateway adapter"
        choices.append(questionary.Choice(title=live_title, value=LIVE_EXECUTION_MODE))

    choices.append(
        questionary.Choice(
            title="demo - dry-run with provider/model defaults",
            value=DEMO_EXECUTION_MODE,
        ),
    )

    if advanced and not supports_live:
        choices.append(
            questionary.Choice(
                title="custom module - live execution via module:function",
                value=CUSTOM_MODULE_EXECUTION_MODE,
            ),
        )
    elif advanced and supports_live:
        choices.append(
            questionary.Choice(
                title="custom module - override built-in runtime",
                value=CUSTOM_MODULE_EXECUTION_MODE,
            ),
        )

    default_mode = LIVE_EXECUTION_MODE if supports_live and os.getenv(_default_api_key_env(provider)) else DEMO_EXECUTION_MODE
    if not supports_live:
        default_mode = DEMO_EXECUTION_MODE

    return questionary.select(
        "Execution mode:",
        choices=choices,
        default=default_mode,
    ).ask()


def _resolve_runtime_adapter(
    *,
    provider: str,
    execution_mode: str,
    advanced: bool,
) -> str:
    if execution_mode == DEMO_EXECUTION_MODE:
        return "dry-run"
    if execution_mode == LIVE_EXECUTION_MODE:
        if provider in {"openai", "custom_api"}:
            return provider
        if not advanced:
            return "dry-run"
    return questionary.text(
        "Custom adapter reference (module:function):",
        validate=_validate_adapter_reference,
    ).ask()


def _role_choices() -> list[questionary.Choice]:
    return [
        questionary.Choice(
            title=f"{role} - {description}",
            value=role,
            checked=role in DEFAULT_SELECTED_ROLES,
        )
        for role, description in ROLE_DESCRIPTIONS.items()
    ]


def _ordered_selected_roles(selected_roles: list[str]) -> list[str]:
    selected = set(selected_roles)
    return [role for role in ROLE_DESCRIPTIONS if role in selected]


def _roles_for_preset(preset: str, selected_roles: list[str]) -> Dict[str, Dict[str, Any]]:
    defaults = ROLE_DEFAULTS_BY_PRESET.get(preset, {})
    return {role: dict(defaults.get(role, {"temperature": 0.2})) for role in selected_roles}


def _ensemble_constraints(selected_roles: list[str]) -> Dict[str, Any]:
    selected = set(selected_roles)
    pairs = [
        [left, right]
        for left, right in DEFAULT_DISALLOW_SAME_MODEL_PAIRS
        if left in selected and right in selected
    ]
    return {"disallow_same_model_pairs": pairs}


def _preview_config(cfg: Dict[str, Any]) -> None:
    roles = cfg.get("roles", {}) or {}
    role_models = {role: resolve_role_model(cfg, role) for role in roles}
    pairs = (cfg.get("constraints") or {}).get("disallow_same_model_pairs") or []
    scope = ((cfg.get("input") or {}).get("scope") or "").strip()

    violations: list[str] = []
    for left, right in pairs:
        if role_models.get(left) == role_models.get(right):
            violations.append(f"{left} and {right} share {role_models.get(left)}")

    lines = [
        "",
        "Configuration preview:",
        f"  mode: {cfg.get('mode')}",
        f"  scope: {scope}",
        f"  provider: {(cfg.get('provider') or {}).get('name')} / {(cfg.get('provider') or {}).get('model')}",
        f"  runtime.adapter: {(cfg.get('runtime') or {}).get('adapter')}",
        f"  output.artifacts_dir: {(cfg.get('output') or {}).get('artifacts_dir')}",
        "  role models:",
    ]
    lines.extend(f"    - {role}: {model}" for role, model in role_models.items())
    if violations:
        lines.append("  doctor risk flags:")
        lines.extend(f"    - {item}" for item in violations)
    else:
        lines.append("  doctor risk flags: none")

    questionary.print("\n".join(lines))


def _apply_simple_mode_model_diversity(
    cfg: Dict[str, Any],
    *,
    provider: str,
    selected_roles: list[str],
) -> None:
    if "implementer" not in selected_roles:
        return

    common_models = COMMON_MODELS_BY_PROVIDER.get(provider, [])
    if len(common_models) < 2:
        return

    provider_cfg = cfg.get("provider") or {}
    base_model = provider_cfg.get("model")
    alternatives = [model for model in common_models if model != base_model]
    if not alternatives:
        return

    roles_cfg = cfg.get("roles") or {}
    implementer_cfg = roles_cfg.get("implementer") or {}
    implementer_cfg["model"] = alternatives[0]
    roles_cfg["implementer"] = implementer_cfg
    cfg["roles"] = roles_cfg


def run_wizard(config_path: str = "ese.config.yaml", *, advanced: bool = False) -> str | None:
    while True:
        mode = questionary.select("Setup mode:", choices=["ensemble", "solo"]).ask()
        provider = questionary.select(
            "Provider:",
            choices=_provider_choices(advanced=advanced),
            default=_provider_default_from_env(),
        ).ask()
        execution_mode = _select_execution_mode(provider, advanced=advanced)

        provider_name = provider
        provider_cfg: Dict[str, Any] = {}

        if provider == "custom_api":
            provider_name = questionary.text(
                "Custom provider name (e.g., my-gateway):",
                validate=_validate_non_empty_text("Provider name"),
            ).ask()

        goal_profile = None
        selected_roles: list[str]
        preset: str
        if advanced:
            preset = questionary.select(
                "Preset:", choices=["fast", "balanced", "strict", "paranoid"],
            ).ask()
            selected_roles = questionary.checkbox(
                "Select roles for this pipeline (each option includes its responsibility):",
                choices=_role_choices(),
                validate=lambda value: bool(value) or "Select at least one role.",
            ).ask()
            selected_roles = _ordered_selected_roles(selected_roles or DEFAULT_SELECTED_ROLES)
        else:
            goal_profile = questionary.select(
                "Goal profile:",
                choices=GOAL_PROFILES,
                default="balanced",
            ).ask()
            preset = GOAL_TO_PRESET[goal_profile]
            selected_roles = GOAL_DEFAULT_ROLES[goal_profile]

        scope = questionary.text(
            "Project scope or task for this ensemble run:",
            validate=_validate_non_empty_text("Project scope"),
        ).ask()
        model = _select_default_model(provider=provider, goal_profile=goal_profile)
        runtime_adapter = _resolve_runtime_adapter(
            provider=provider,
            execution_mode=execution_mode,
            advanced=advanced,
        )

        api_key_env = None
        if runtime_adapter in {"openai", "custom_api"}:
            api_key_env = questionary.text(
                "API key environment variable:",
                default=_default_api_key_env(provider),
                validate=_validate_non_empty_text("API key environment variable"),
            ).ask()
        if runtime_adapter == "custom_api":
            custom_base_url = questionary.text(
                "Custom API base URL (required, e.g., https://gateway.example/v1):",
                validate=_validate_non_empty_text("Base URL"),
            ).ask()
            provider_cfg["base_url"] = custom_base_url.strip()

        enforce_json = questionary.confirm(
            "Enforce JSON-only outputs for role reports?",
            default=True,
        ).ask()

        fail_on_high = questionary.confirm(
            "Fail pipeline on HIGH severity findings?",
            default=True,
        ).ask()

        cfg: Dict[str, Any] = {
            "version": 1,
            "mode": mode,
            "provider": {
                "name": provider_name,
                "model": model,
                **provider_cfg,
            },
            "preset": preset,
            "roles": _roles_for_preset(preset=preset, selected_roles=selected_roles),
            "input": {
                "scope": scope.strip(),
            },
            "output": {
                "artifacts_dir": "artifacts",
                "enforce_json": enforce_json,
            },
            "gating": {
                "fail_on_high": fail_on_high,
            },
            "runtime": {
                "adapter": runtime_adapter,
                "timeout_seconds": 60,
                "max_retries": 2,
                "retry_backoff_seconds": 1.0,
            },
        }
        if api_key_env:
            cfg["provider"]["api_key_env"] = api_key_env

        if runtime_adapter == "openai":
            cfg["runtime"]["openai"] = {
                "base_url": provider_cfg.get("base_url", "https://api.openai.com/v1"),
            }
        if runtime_adapter == "custom_api":
            cfg["runtime"]["custom_api"] = {
                "base_url": provider_cfg.get("base_url"),
            }

        if mode == "ensemble":
            cfg["constraints"] = _ensemble_constraints(selected_roles=selected_roles)
            if not advanced:
                _apply_simple_mode_model_diversity(
                    cfg,
                    provider=provider,
                    selected_roles=selected_roles,
                )

        try:
            validated_cfg = validate_config(cfg, source=config_path)
        except ConfigValidationError as err:
            questionary.print(f"\nConfiguration error:\n  {err}\n")
            if not questionary.confirm("Restart setup?", default=True).ask():
                return None
            continue

        _preview_config(validated_cfg)
        if questionary.confirm("Write this config?", default=True).ask():
            write_config(config_path, validated_cfg)
            return config_path

        if not questionary.confirm("Restart setup?", default=True).ask():
            return None
