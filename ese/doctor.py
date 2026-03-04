"""ESE doctor checks.

Validates config and enforces ensemble role separation constraints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ese.config import load_config, resolve_role_model

ROLE_NAMES = [
    "architect",
    "implementer",
    "adversarial_reviewer",
    "security_auditor",
    "test_generator",
    "performance_analyst",
]


def run_doctor(config_path: str) -> Tuple[bool, List[str], Dict[str, str]]:
    cfg = load_config(config_path)
    mode = (cfg.get("mode") or "ensemble").strip().lower()

    role_models = {r: resolve_role_model(cfg, r) for r in ROLE_NAMES}

    if mode == "solo":
        return True, ["SOLO MODE: reduced independence; higher self-confirmation risk."], role_models

    constraints = cfg.get("constraints") or {}
    pairs = constraints.get("disallow_same_model_pairs") or []

    violations: List[str] = []
    for a, b in pairs:
        if role_models.get(a) == role_models.get(b):
            violations.append(f"{a} and {b} share model {role_models[a]}")

    ok = len(violations) == 0
    return ok, violations, role_models
