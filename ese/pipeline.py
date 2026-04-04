"""ESE pipeline runner with pluggable role adapters and artifact chaining."""

from __future__ import annotations

import importlib
import inspect
import json
import logging
import os
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Protocol
from uuid import uuid4

import yaml

from ese.adapters import AdapterExecutionError, BUILTIN_ADAPTERS
from ese.config import (
    resolve_prompt_text,
    resolve_role_model,
    resolve_role_prompt_text,
    resolve_scope_text,
)
from ese.feedback import feedback_prompt_guidance
from ese.provider_runtime import BUILTIN_RUNTIME_ADAPTERS_TEXT

logger = logging.getLogger(__name__)

# Certainty assessment thresholds
CERTAINTY_THRESHOLD_HIGH = 0.75  # Below this, response should be curtailed
CERTAINTY_THRESHOLD_MEDIUM = 0.50  # Below this, strong warning issued
CERTAINTY_INDICATORS = {
    "low": 0.3,
    "medium": 0.6,
    "high": 0.85,
}

PIPELINE_ORDER = [
    "architect",
    "implementer",
    "adversarial_reviewer",
    "security_auditor",
    "test_generator",
    "performance_analyst",
    "documentation_writer",
    "devops_sre",
    "database_engineer",
    "release_manager",
]

JSON_REPORT_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
JSON_REPORT_CONFIDENCE = {"LOW", "MEDIUM", "HIGH"}
CONFIG_SNAPSHOT_NAME = "ese_config.snapshot.yaml"
STATE_CONTRACT_VERSION = 2
REPORT_CONTRACT_VERSION = 2
PROMPT_TRUNCATION_MARKER = "[...truncated for size...]"
PROMPT_LIMITS = {
    "scope": 4000,
    "additional_context": 6000,
    "operator_feedback": 3000,
    "architect_output": 6000,
    "implementer_output": 8000,
    "upstream_artifact": 6000,
}


def _validate_prompt_limits() -> None:
    for key, value in PROMPT_LIMITS.items():
        if not isinstance(value, int) or value <= 0:
            raise PipelineError(
                f"PROMPT_LIMITS['{key}'] must be a positive integer, got {value}"
            )


SPECIALIST_ROLE_INSTRUCTIONS = {
    "adversarial_reviewer": (
        "Act as an adversarial code reviewer. Hunt for correctness bugs, edge cases, "
        "regressions, unsafe assumptions, and missing validation."
    ),
    "security_auditor": (
        "Perform a security review. Focus on trust boundaries, authz/authn gaps, secrets "
        "handling, injection risks, data exposure, and abuse paths."
    ),
    "test_generator": (
        "Design a pragmatic automated test plan. Focus on missing unit, integration, and "
        "end-to-end coverage, including the highest-risk failure modes."
    ),
    "performance_analyst": (
        "Review performance and scalability. Focus on hot paths, latency risks, query or "
        "algorithmic complexity, memory pressure, and caching opportunities."
    ),
    "documentation_writer": (
        "Produce documentation deliverables. Focus on README updates, API usage notes, "
        "migration guidance, operator runbooks, and any documentation gaps that block adoption."
    ),
    "devops_sre": (
        "Review operational readiness. Focus on CI/CD safety, deployment sequencing, rollback "
        "plans, observability, alerting, and day-2 operability."
    ),
    "database_engineer": (
        "Review data-layer design. Focus on schema correctness, migrations, indexes, query "
        "plans, transaction safety, consistency, and rollback strategy."
    ),
    "release_manager": (
        "Assess release readiness. Focus on blockers, rollout sequencing, rollback readiness, "
        "dependency coordination, and launch sign-off criteria."
    ),
}
PARALLEL_SPECIALIST_ROLES = set(SPECIALIST_ROLE_INSTRUCTIONS)


class PipelineError(RuntimeError):
    """Raised when pipeline configuration or adapter execution fails."""


class RoleAdapter(Protocol):
    """Callable signature used by external role adapters."""

    def __call__(
        self,
        *,
        role: str,
        model: str,
        prompt: str,
        context: Mapping[str, str],
        cfg: Mapping[str, Any],
    ) -> str:
        ...


def _write(path: str, text: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _write_yaml(path: str, payload: Mapping[str, Any]) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(dict(payload), f, sort_keys=False)


def _ensure_artifact_within_dir(artifacts_dir: str, path: str) -> str:
    """Resolve artifact path and ensure it stays within artifacts_dir."""
    artifacts_root = Path(artifacts_dir).resolve()
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(artifacts_root)
    except ValueError as err:
        raise PipelineError(f"Artifact path escapes artifacts_dir: {resolved}") from err
    return str(resolved)


def _compact_lines(text: str) -> str:
    """Remove leading/trailing blank lines and collapse excessive vertical space."""
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def _normalize_role_order(cfg: Dict[str, Any]) -> list[str]:
    roles_cfg = cfg.get("roles") or {}
    if not isinstance(roles_cfg, dict):
        raise PipelineError("roles must be a mapping of role names to role configs")

    configured_roles = list(roles_cfg.keys())
    if not configured_roles:
        return []

    explicit_role_order = cfg.get("role_order")
    if explicit_role_order is not None:
        if not isinstance(explicit_role_order, list):
            raise PipelineError("role_order must be a list of configured role names")

        normalized: list[str] = []
        seen: set[str] = set()
        for role in explicit_role_order:
            if not isinstance(role, str) or not role.strip():
                raise PipelineError("role_order entries must be non-empty strings")
            clean_role = role.strip()
            if clean_role not in roles_cfg:
                raise PipelineError(
                    f"role_order references unknown role '{clean_role}'"
                )
            if clean_role in seen:
                raise PipelineError(
                    f"role_order contains duplicate role '{clean_role}'"
                )
            normalized.append(clean_role)
            seen.add(clean_role)

        missing_roles = [role for role in configured_roles if role not in seen]
        if missing_roles:
            details = ", ".join(missing_roles)
            raise PipelineError(f"role_order omits configured roles: {details}")
        return normalized

    ordered: list[str] = [role for role in PIPELINE_ORDER if role in configured_roles]
    ordered.extend(role for role in configured_roles if role not in ordered)
    return ordered


def _require_scope(cfg: Dict[str, Any]) -> str:
    scope = resolve_scope_text(cfg)
    if scope:
        return scope
    raise PipelineError(
        "No project scope supplied. Set input.scope in the config or pass --scope."
    )


def _output_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    output = cfg.get("output")
    if not isinstance(output, dict):
        return {"artifacts_dir": "artifacts", "enforce_json": True}

    return {
        "artifacts_dir": output.get("artifacts_dir") or "artifacts",
        "enforce_json": bool(output.get("enforce_json", True)),
    }


def _gating_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    gating = cfg.get("gating")
    if not isinstance(gating, dict):
        return {"fail_on_high": True}
    return {"fail_on_high": bool(gating.get("fail_on_high", True))}


def _parallel_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    runtime_cfg = cfg.get("runtime")
    if not isinstance(runtime_cfg, dict):
        return {"parallel_specialists": True, "max_parallel_roles": 4}

    enabled = bool(runtime_cfg.get("parallel_specialists", True))
    raw_max_parallel = runtime_cfg.get("max_parallel_roles", 4)
    try:
        max_parallel_roles = int(raw_max_parallel)
    except (TypeError, ValueError) as err:
        raise PipelineError("runtime.max_parallel_roles must be an integer") from err
    if max_parallel_roles <= 0:
        raise PipelineError("runtime.max_parallel_roles must be > 0")
    return {
        "parallel_specialists": enabled,
        "max_parallel_roles": max_parallel_roles,
    }


def _resolve_artifacts_dir(cfg: Dict[str, Any], artifacts_dir: str | None) -> str:
    if isinstance(artifacts_dir, str) and artifacts_dir.strip():
        return artifacts_dir.strip()
    configured = _output_cfg(cfg).get("artifacts_dir")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    return "artifacts"


def _config_snapshot_path(artifacts_dir: str) -> str:
    return os.path.join(artifacts_dir, CONFIG_SNAPSHOT_NAME)


def _assurance_level(mode: str) -> str:
    clean_mode = str(mode or "ensemble").strip().lower()
    return "degraded" if clean_mode == "solo" else "standard"


def _review_isolation(cfg: Mapping[str, Any]) -> str:
    runtime_cfg = cfg.get("runtime")
    if not isinstance(runtime_cfg, Mapping):
        return "scope_and_implementation"
    value = (
        str(runtime_cfg.get("review_isolation") or "scope_and_implementation")
        .strip()
        .lower()
    )
    if value in {
        "framed",
        "implementation_only",
        "scope_only",
        "scope_and_implementation",
    }:
        return value
    return "scope_and_implementation"


def _truncate_prompt_block(text: str, *, limit: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return (
        cleaned[: limit - len(PROMPT_TRUNCATION_MARKER) - 1].rstrip()
        + f"\n{PROMPT_TRUNCATION_MARKER}"
    )


def _prompt_section(title: str, text: str, *, limit: int) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    return f"{title}:\n{_truncate_prompt_block(cleaned, limit=limit)}"


def _role_upstream_sections(
    role: str,
    outputs: Mapping[str, str],
    *,
    review_isolation: str,
) -> list[tuple[str, str, int]]:
    is_specialist = role in SPECIALIST_ROLE_INSTRUCTIONS
    architect_output = outputs.get("architect", "").strip()
    implementer_output = outputs.get("implementer", "").strip()

    if role == "architect":
        return []
    if role == "implementer":
        return (
            [("Architect Plan", architect_output, PROMPT_LIMITS["architect_output"])]
            if architect_output
            else []
        )

    if review_isolation == "scope_only":
        return []

    sections: list[tuple[str, str, int]] = []
    if review_isolation == "framed" and architect_output:
        sections.append(
            ("Architect Plan", architect_output, PROMPT_LIMITS["architect_output"])
        )
    if implementer_output:
        sections.append(
            (
                "Implementer Output",
                implementer_output,
                PROMPT_LIMITS["implementer_output"],
            )
        )

    if is_specialist:
        return sections

    fallback_sections = [
        (
            f"Upstream Artifact ({name})",
            text.strip(),
            PROMPT_LIMITS["upstream_artifact"],
        )
        for name, text in outputs.items()
        if isinstance(text, str)
        and text.strip()
        and name not in {"architect", "implementer"}
    ]
    if review_isolation == "framed" and not architect_output:
        fallback_sections = [
            (
                f"Upstream Artifact ({name})",
                text.strip(),
                PROMPT_LIMITS["upstream_artifact"],
            )
            for name, text in outputs.items()
            if isinstance(text, str) and text.strip()
        ]
    return sections + fallback_sections


def _json_report_contract() -> str:
    return textwrap.dedent(
        """
        Return valid JSON only, with no Markdown fences or prose outside the JSON object.
        Use this schema exactly:
        {
          "summary": "string",
          "confidence": "LOW | MEDIUM | HIGH",
          "assumptions": ["string"],
          "unknowns": ["string"],
          "evidence_basis": ["string"],
          "findings": [
            {
              "severity": "LOW | MEDIUM | HIGH | CRITICAL",
              "title": "string",
              "details": "string"
            }
          ],
          "artifacts": ["string"],
          "next_steps": ["string"],
          "code_suggestions": [
            {
              "path": "string",
              "kind": "edit | patch | test | refactor | config",
              "summary": "string",
              "suggestion": "string",
              "snippet": "string"
            }
          ]
        }
        confidence is required and should reflect execution certainty, not severity.
        assumptions and unknowns are required string arrays.
        evidence_basis is optional; include it when you relied on concrete artifacts, tests, logs, or docs.
        Use empty arrays when there are no findings, artifacts, next steps, code suggestions, assumptions, or unknowns.
        Use code_suggestions for concrete programmer-facing edits, ideally naming the target file and
        including a short patch-style snippet when you can.
        """,
    ).strip()


def _role_prompt(
    role: str,
    scope: str,
    outputs: Mapping[str, str],
    *,
    additional_context: str = "",
    operator_feedback: str = "",
    enforce_json: bool,
    role_prompt_text: str = "",
    review_isolation: str = "scope_and_implementation",
) -> str:
    json_contract = f"\n\n{_json_report_contract()}" if enforce_json else ""
    artifact_guidance = ""
    if enforce_json:
        artifact_guidance = (
            "\n\nUse `findings` only for actionable issues or gaps. "
            "Use `artifacts` for concrete deliverables such as docs, runbooks, test files, "
            "rollout checklists, or migration notes. "
            "Use `code_suggestions` for concrete file-targeted edits, test additions, or short patch-like snippets."
        )
    custom_prompt = role_prompt_text.strip()
    if custom_prompt:
        role_intro = custom_prompt
    elif role == "architect":
        role_intro = "You are the Architect. Produce a concise implementation plan for this scope."
    elif role == "implementer":
        role_intro = "You are the Implementer. Build from the Architect plan and scope."
    elif role in SPECIALIST_ROLE_INSTRUCTIONS:
        role_intro = f"You are the {role}. {SPECIALIST_ROLE_INSTRUCTIONS[role]}"
    else:
        role_intro = f"You are the {role}. Review the implementation against scope and report findings."

    sections = [
        role_intro.strip(),
        _prompt_section("Scope", scope, limit=PROMPT_LIMITS["scope"]),
        _prompt_section(
            "Additional Run Context",
            additional_context,
            limit=PROMPT_LIMITS["additional_context"],
        ),
    ]
    sections.extend(
        _prompt_section(title, text, limit=limit)
        for title, text, limit in _role_upstream_sections(
            role,
            outputs,
            review_isolation=review_isolation,
        )
    )
    sections.append(
        _prompt_section(
            "Operator Feedback",
            operator_feedback,
            limit=PROMPT_LIMITS["operator_feedback"],
        )
    )
    assembled = "\n\n".join(section for section in sections if section)
    uncertainty_reinforcement = (
        "\n\n## CERTAINTY AND EVIDENCE REQUIREMENT\n"
        "You MUST assess your own certainty level before answering. "
        "If the evidence is insufficient, ambiguous, or speculative, you MUST:\n"
        "1. State your confidence level explicitly as 'LOW', 'MEDIUM', or 'HIGH'\n"
        "2. List specific evidence gaps or unknowns in an 'evidence_gaps' or 'unknowns' field\n"
        "3. Curtail your response to only what you can support with facts or data\n"
        "4. NOT fabricate details, conclusions, or recommendations when certainty is low\n"
        "5. Surface the uncertainty situation clearly so downstream roles know this output is provisional\n\n"
        "CRITICAL: Answering authoritatively when indicators point to high uncertainty is worse than saying 'insufficient evidence'. "
        "If you cannot support your answer with facts from the supplied materials, say so explicitly. "
        "Do not invent conclusions to fill gaps."
    )
    return _compact_lines(
        f"{assembled}{artifact_guidance}{uncertainty_reinforcement}{json_contract}".strip()
    )


def _role_context(
    role: str,
    outputs: Mapping[str, str],
    *,
    review_isolation: str = "scope_and_implementation",
) -> Dict[str, str]:
    sections = _role_upstream_sections(role, outputs, review_isolation=review_isolation)
    context: dict[str, str] = {}
    for title, text, _limit in sections:
        if title == "Architect Plan":
            context["architect"] = text
        elif title == "Implementer Output":
            context["implementer"] = text
        elif title.startswith("Upstream Artifact (") and title.endswith(")"):
            context[title[len("Upstream Artifact (") : -1]] = text
    return context


def _prompt_context(cfg: Dict[str, Any], artifacts_dir: str) -> dict[str, str]:
    prompt_text = resolve_prompt_text(cfg)
    feedback_text = feedback_prompt_guidance(artifacts_dir)
    return {
        "additional_context": prompt_text,
        "operator_feedback": feedback_text,
    }


def _is_parallelizable_role(role: str) -> bool:
    return role in PARALLEL_SPECIALIST_ROLES


def _load_custom_adapter(reference: str) -> RoleAdapter:
    if ":" not in reference:
        raise PipelineError(
            f"runtime.adapter must be one of {BUILTIN_RUNTIME_ADAPTERS_TEXT} or a Python reference in 'module:function' format",
        )

    module_name, object_name = reference.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as err:
        raise PipelineError(f"Could not import adapter module '{module_name}'") from err

    adapter = getattr(module, object_name, None)
    if adapter is None or not callable(adapter):
        raise PipelineError(f"Adapter '{reference}' is not callable")

    return adapter


def _run_adapter_healthcheck(
    adapter: Callable[..., str] | RoleAdapter,
    *,
    cfg: Mapping[str, Any],
    reference: str,
) -> None:
    healthcheck = getattr(adapter, "healthcheck", None)
    if healthcheck is None:
        return
    if not callable(healthcheck):
        raise PipelineError(f"Adapter '{reference}' exposes a non-callable healthcheck")

    signature = inspect.signature(healthcheck)
    kwargs: dict[str, Any] = {}
    args: list[Any] = []
    parameters = list(signature.parameters.values())
    accepts_var_kwargs = any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters
    )
    if accepts_var_kwargs or "cfg" in signature.parameters:
        kwargs["cfg"] = cfg
    elif "config" in signature.parameters:
        kwargs["config"] = cfg
    elif parameters:
        first = parameters[0]
        if first.kind in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }:
            args.append(cfg)

    try:
        result = healthcheck(*args, **kwargs)
    except Exception as err:  # noqa: BLE001
        raise PipelineError(
            f"Adapter healthcheck failed for '{reference}': {err}"
        ) from err

    if result is False:
        raise PipelineError(f"Adapter healthcheck failed for '{reference}'")


def _resolve_adapter(cfg: Dict[str, Any]) -> tuple[str, RoleAdapter]:
    runtime_cfg = cfg.get("runtime") or {}
    reference = str(runtime_cfg.get("adapter") or "").strip()
    if not reference:
        raise PipelineError(
            "runtime.adapter must be explicitly configured. Use 'dry-run' only with execution_mode='demo', "
            "or choose a live adapter.",
        )

    builtin = BUILTIN_ADAPTERS.get(reference)
    if builtin is not None:
        return reference, builtin

    adapter = _load_custom_adapter(reference)
    _run_adapter_healthcheck(adapter, cfg=cfg, reference=reference)
    return reference, adapter


def _invoke_adapter(
    adapter: Callable[..., str] | RoleAdapter,
    *,
    role: str,
    model: str,
    prompt: str,
    context: Mapping[str, str],
    cfg: Mapping[str, Any],
) -> str:
    try:
        result = adapter(
            role=role, model=model, prompt=prompt, context=context, cfg=cfg
        )
    except AdapterExecutionError as err:
        raise PipelineError(
            f"Adapter execution failed for role '{role}': {err}"
        ) from err
    except Exception as err:  # noqa: BLE001 - preserve adapter stack info in message.
        raise PipelineError(
            f"Adapter execution failed for role '{role}': {err}"
        ) from err

    if not isinstance(result, str):
        raise PipelineError(f"Adapter output for role '{role}' must be a string")
    return result


def _normalize_json_report(*, role: str, model: str, output: str) -> dict[str, Any]:
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as err:
        raise PipelineError(
            f"Adapter output for role '{role}' must be valid JSON when output.enforce_json=true",
        ) from err

    if not isinstance(parsed, dict):
        raise PipelineError(
            f"Adapter output for role '{role}' must be a JSON object when output.enforce_json=true",
        )

    report = dict(parsed)

    summary = report.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise PipelineError(
            f"JSON report for role '{role}' must contain a non-empty string field 'summary'",
        )
    report["summary"] = summary.strip()

    confidence = report.get("confidence")
    if not isinstance(confidence, str):
        raise PipelineError(
            f"JSON report for role '{role}' must contain a string field 'confidence'",
        )
    normalized_confidence = confidence.strip().upper()
    if normalized_confidence not in JSON_REPORT_CONFIDENCE:
        allowed = ", ".join(sorted(JSON_REPORT_CONFIDENCE))
        raise PipelineError(
            f"JSON report for role '{role}' has invalid confidence '{confidence}'; "
            f"expected one of {allowed}",
        )
    report["confidence"] = normalized_confidence

    for key in ("assumptions", "unknowns"):
        raw_value = report.get(key)
        if not isinstance(raw_value, list) or any(
            not isinstance(item, str) for item in raw_value
        ):
            raise PipelineError(
                f"JSON report for role '{role}' must contain a string list field '{key}'",
            )
        report[key] = [item.strip() for item in raw_value if item.strip()]

    evidence_basis = report.get("evidence_basis")
    if evidence_basis is not None:
        if not isinstance(evidence_basis, list) or any(
            not isinstance(item, str) for item in evidence_basis
        ):
            raise PipelineError(
                f"JSON report for role '{role}' must contain a string list field 'evidence_basis' when present",
            )
        report["evidence_basis"] = [
            item.strip() for item in evidence_basis if item.strip()
        ]

    findings = report.get("findings")
    if not isinstance(findings, list):
        raise PipelineError(
            f"JSON report for role '{role}' must contain a list field 'findings'"
        )

    normalized_findings: list[dict[str, str]] = []
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            raise PipelineError(
                f"JSON report for role '{role}' has non-object finding at index {index}",
            )

        title = finding.get("title")
        severity = finding.get("severity")
        details = finding.get("details", "")
        if not isinstance(title, str) or not title.strip():
            raise PipelineError(
                f"JSON report for role '{role}' has finding {index} without a non-empty 'title'",
            )
        if not isinstance(severity, str):
            raise PipelineError(
                f"JSON report for role '{role}' has finding {index} without string 'severity'",
            )
        normalized_severity = severity.strip().upper()
        if normalized_severity not in JSON_REPORT_SEVERITIES:
            allowed = ", ".join(sorted(JSON_REPORT_SEVERITIES))
            raise PipelineError(
                f"JSON report for role '{role}' has invalid severity '{severity}' "
                f"at finding {index}; expected one of {allowed}",
            )
        if not isinstance(details, str):
            raise PipelineError(
                f"JSON report for role '{role}' has finding {index} with non-string 'details'",
            )
        normalized_findings.append(
            {
                **finding,
                "title": title.strip(),
                "severity": normalized_severity,
                "details": details.strip(),
            },
        )
    report["findings"] = normalized_findings

    for key in ("artifacts", "next_steps"):
        raw_value = report.get(key, [])
        if not isinstance(raw_value, list) or any(
            not isinstance(item, str) for item in raw_value
        ):
            raise PipelineError(
                f"JSON report for role '{role}' must contain a string list field '{key}'",
            )
        report[key] = [item.strip() for item in raw_value if item.strip()]

    raw_code_suggestions = report.get("code_suggestions", [])
    if not isinstance(raw_code_suggestions, list):
        raise PipelineError(
            f"JSON report for role '{role}' must contain a list field 'code_suggestions'",
        )

    normalized_code_suggestions: list[dict[str, str]] = []
    for index, suggestion in enumerate(raw_code_suggestions, start=1):
        if not isinstance(suggestion, dict):
            raise PipelineError(
                f"JSON report for role '{role}' has non-object code_suggestion at index {index}",
            )

        path = suggestion.get("path", "")
        kind = suggestion.get("kind", "edit")
        summary = suggestion.get("summary", "")
        suggestion_text = suggestion.get("suggestion", "")
        snippet = suggestion.get("snippet", "")
        if not isinstance(path, str):
            raise PipelineError(
                f"JSON report for role '{role}' has code_suggestion {index} with non-string 'path'",
            )
        if not isinstance(kind, str) or not kind.strip():
            raise PipelineError(
                f"JSON report for role '{role}' has code_suggestion {index} without non-empty string 'kind'",
            )
        if not isinstance(summary, str):
            raise PipelineError(
                f"JSON report for role '{role}' has code_suggestion {index} with non-string 'summary'",
            )
        if not isinstance(suggestion_text, str) or not suggestion_text.strip():
            raise PipelineError(
                f"JSON report for role '{role}' has code_suggestion {index} without non-empty string 'suggestion'",
            )
        if not isinstance(snippet, str):
            raise PipelineError(
                f"JSON report for role '{role}' has code_suggestion {index} with non-string 'snippet'",
            )
        clean_suggestion = suggestion_text.strip()
        clean_summary = summary.strip() or clean_suggestion[:120]
        normalized_code_suggestions.append(
            {
                "path": path.strip(),
                "kind": kind.strip().lower(),
                "summary": clean_summary,
                "suggestion": clean_suggestion,
                "snippet": snippet.rstrip(),
            },
        )
    report["code_suggestions"] = normalized_code_suggestions

    report["role"] = role
    report["model"] = model
    return report


def _render_role_output(
    *,
    role: str,
    model: str,
    output: str,
    enforce_json: bool,
) -> tuple[str, str, dict[str, Any] | None]:
    if not enforce_json:
        return "md", output, None

    report = _normalize_json_report(role=role, model=model, output=output)
    rendered = json.dumps(report, indent=2) + "\n"
    return "json", rendered, report


def _assess_response_certainty(
    *,
    role: str,
    report: dict[str, Any] | None,
    output: str,
) -> dict[str, Any]:
    """Assess the certainty level of a model's response and flag uncertainty.

    Returns a certainty assessment dict with:
    - certainty_score: 0.0 to 1.0
    - certainty_level: "low", "medium", or "high"
    - warning: str or None - warning message if certainty is below threshold
    - curtailed: bool - whether the response should be curtailed
    - reasons: list[str] - reasons for the certainty assessment
    """
    reasons: list[str] = []
    certainty_score = 1.0  # Start with full certainty, deduct for issues

    if report is None:
        # Non-JSON output, assess based on text patterns
        output_lower = output.lower()
        uncertainty_phrases = [
            "uncertain",
            "cannot determine",
            "insufficient",
            "unclear",
            "may or may not",
            "it is possible",
            "could be",
            "might be",
            "speculative",
            "unknown",
            "not enough",
            "lack of",
            "unable to confirm",
            "cannot verify",
            "no evidence",
        ]
        for phrase in uncertainty_phrases:
            if phrase in output_lower:
                certainty_score -= 0.15
                reasons.append(f"Uncertainty phrase detected: '{phrase}'")

        # Check for hedging language
        hedge_count = sum(
            1
            for phrase in ["perhaps", "possibly", "maybe", "likely", "seems"]
            if phrase in output_lower
        )
        if hedge_count >= 3:
            certainty_score -= 0.2
            reasons.append(f"Multiple hedging phrases detected ({hedge_count})")
    else:
        # Check confidence field if present
        confidence = report.get("confidence", "")
        if isinstance(confidence, str):
            confidence_lower = confidence.lower().strip()
            if confidence_lower in CERTAINTY_INDICATORS:
                certainty_score = CERTAINTY_INDICATORS[confidence_lower]
                reasons.append(f"Explicit confidence: {confidence}")
            elif "low" in confidence_lower:
                certainty_score = 0.3
                reasons.append(f"Low confidence stated: {confidence}")
            elif "medium" in confidence_lower:
                certainty_score = 0.6
                reasons.append(f"Medium confidence stated: {confidence}")
            elif "high" in confidence_lower:
                certainty_score = 0.85
                reasons.append(f"High confidence stated: {confidence}")

        # Check for evidence gaps
        evidence_gaps = (
            report.get("evidence_gaps")
            or report.get("coverage_gaps")
            or report.get("unknowns")
        )
        if isinstance(evidence_gaps, list) and len(evidence_gaps) > 0:
            gap_penalty = min(0.4, len(evidence_gaps) * 0.1)
            certainty_score -= gap_penalty
            reasons.append(f"Evidence gaps identified: {len(evidence_gaps)}")

        # Check for uncertainty notes
        uncertainty_notes = report.get("uncertainty_notes", [])
        if isinstance(uncertainty_notes, list) and len(uncertainty_notes) > 0:
            note_penalty = min(0.3, len(uncertainty_notes) * 0.1)
            certainty_score -= note_penalty
            reasons.append(f"Uncertainty notes present: {len(uncertainty_notes)}")

        # Check findings for low confidence
        findings = report.get("findings", [])
        if isinstance(findings, list):
            low_confidence_findings = [
                f
                for f in findings
                if isinstance(f, dict)
                and f.get("confidence")
                and isinstance(f["confidence"], (int, float))
                and f["confidence"] < 0.5
            ]
            if low_confidence_findings:
                certainty_score -= min(0.3, len(low_confidence_findings) * 0.1)
                reasons.append(
                    f"Low-confidence findings: {len(low_confidence_findings)}"
                )

    # Clamp score
    certainty_score = max(0.0, min(1.0, certainty_score))

    # Determine level
    if certainty_score >= 0.75:
        certainty_level = "high"
    elif certainty_score >= 0.50:
        certainty_level = "medium"
    else:
        certainty_level = "low"

    # Determine if response should be curtailed
    curtailed = certainty_score < CERTAINTY_THRESHOLD_MEDIUM
    warning = None

    if curtailed:
        warning = (
            f"ROLE '{role}' RESPONSE CERTAINTY CRITICALLY LOW ({certainty_score:.2f}). "
            f"The model is answering despite high uncertainty. "
            f"Response should be curtailed until supporting evidence is available. "
            f"Reasons: {'; '.join(reasons)}"
        )
    elif certainty_score < CERTAINTY_THRESHOLD_HIGH:
        warning = (
            f"ROLE '{role}' RESPONSE CERTAINTY BELOW THRESHOLD ({certainty_score:.2f}). "
            f"Model is answering with moderate uncertainty. "
            f"Review findings carefully before acting on this output. "
            f"Reasons: {'; '.join(reasons)}"
        )

    return {
        "certainty_score": round(certainty_score, 2),
        "certainty_level": certainty_level,
        "warning": warning,
        "curtailed": curtailed,
        "reasons": reasons,
    }


def _high_severity_findings(report: Mapping[str, Any]) -> list[dict[str, str]]:
    findings = report.get("findings")
    if not isinstance(findings, list):
        return []
    return [
        finding
        for finding in findings
        if isinstance(finding, dict) and finding.get("severity") in {"HIGH", "CRITICAL"}
    ]


def _write_summary_and_state(
    *,
    artifacts_dir: str,
    run_id: str,
    assurance_level: str,
    mode: str,
    provider: str,
    adapter_name: str,
    scope: str,
    role_models: Mapping[str, str],
    role_artifacts: Mapping[str, str],
    execution: list[dict[str, str]],
    status: str,
    config_snapshot: str,
    start_role: str | None = None,
    parent_run_id: str | None = None,
    failed_roles: list[str] | None = None,
    failure: str | None = None,
) -> str:
    summary_lines = [
        "# ESE Summary",
        "",
        f"Run ID: {run_id}",
        f"Status: {status}",
        f"Assurance Level: {assurance_level}",
        f"Mode: {mode}",
        f"Provider: {provider}",
        f"Adapter: {adapter_name}",
        "",
        "Executed roles:",
    ]
    summary_lines.extend(
        f"- {item['role']} ({item['model']}) -> {item['artifact']}"
        for item in execution
    )
    if parent_run_id:
        summary_lines.extend(["", f"Parent Run ID: {parent_run_id}"])
    if start_role:
        summary_lines.extend(["", f"Start Role: {start_role}"])
    if failed_roles:
        summary_lines.extend(["", f"Failed Roles: {', '.join(failed_roles)}"])
    if failure:
        summary_lines.extend(["", f"Failure: {failure}"])

    summary_path = os.path.join(artifacts_dir, "ese_summary.md")
    _write(summary_path, "\n".join(summary_lines) + "\n")

    state: dict[str, Any] = {
        "run_id": run_id,
        "status": status,
        "assurance_level": assurance_level,
        "mode": mode,
        "provider": provider,
        "adapter": adapter_name,
        "scope": scope,
        "config_snapshot": config_snapshot,
        "state_contract_version": STATE_CONTRACT_VERSION,
        "report_contract_version": REPORT_CONTRACT_VERSION,
        "role_models": dict(role_models),
        "artifacts": dict(role_artifacts),
        "execution": execution,
    }
    if parent_run_id:
        state["parent_run_id"] = parent_run_id
    if start_role:
        state["start_role"] = start_role
    if failed_roles:
        state["failed_roles"] = list(failed_roles)
    if failure:
        state["failure"] = failure

    state_path = os.path.join(artifacts_dir, "pipeline_state.json")
    _write(state_path, json.dumps(state, indent=2) + "\n")
    return summary_path


def _write_release_simulation_artifact(artifacts_dir: str) -> None:
    from ese.reports import build_release_simulation, collect_run_report

    report = collect_run_report(artifacts_dir)
    release_payload = build_release_simulation(report)
    if not release_payload.get("enabled"):
        return

    release_path = os.path.join(artifacts_dir, "release_simulation.json")
    _write(release_path, json.dumps(release_payload, indent=2) + "\n")


def _write_code_suggestion_artifacts(artifacts_dir: str) -> None:
    from ese.reports import (
        collect_run_report,
        render_code_suggestions_json,
        render_code_suggestions_markdown,
    )

    report = collect_run_report(artifacts_dir)
    suggestions = report.get("code_suggestions") or []
    if not suggestions:
        return

    markdown_path = os.path.join(artifacts_dir, "code_suggestions.md")
    json_path = os.path.join(artifacts_dir, "code_suggestions.json")
    _write(markdown_path, render_code_suggestions_markdown(report))
    _write(json_path, render_code_suggestions_json(report))


def _persist_run_outputs(
    *,
    artifacts_dir: str,
    run_id: str,
    assurance_level: str,
    mode: str,
    provider: str,
    adapter_name: str,
    scope: str,
    role_models: Mapping[str, str],
    role_artifacts: Mapping[str, str],
    execution: list[dict[str, Any]],
    status: str,
    config_snapshot: str,
    start_role: str | None = None,
    parent_run_id: str | None = None,
    failed_roles: list[str] | None = None,
    failure: str | None = None,
) -> str:
    summary_path = _write_summary_and_state(
        artifacts_dir=artifacts_dir,
        run_id=run_id,
        assurance_level=assurance_level,
        mode=mode,
        provider=provider,
        adapter_name=adapter_name,
        scope=scope,
        role_models=role_models,
        role_artifacts=role_artifacts,
        execution=execution,
        status=status,
        config_snapshot=config_snapshot,
        start_role=start_role,
        parent_run_id=parent_run_id,
        failed_roles=failed_roles,
        failure=failure,
    )
    _write_code_suggestion_artifacts(artifacts_dir)
    _write_release_simulation_artifact(artifacts_dir)
    return summary_path


def _execute_role(
    *,
    index: int,
    role: str,
    scope: str,
    outputs: Mapping[str, str],
    additional_context: str,
    operator_feedback: str,
    review_isolation: str,
    enforce_json: bool,
    adapter: Callable[..., str] | RoleAdapter,
    cfg: Dict[str, Any],
    artifacts_dir: str,
    strategy: str,
) -> dict[str, Any]:
    started_at = time.time()
    logger.info("Executing role=%s index=%d strategy=%s", role, index, strategy)
    model_ref = resolve_role_model(cfg, role)
    prompt = _role_prompt(
        role=role,
        scope=scope,
        outputs=outputs,
        additional_context=additional_context,
        operator_feedback=operator_feedback,
        enforce_json=enforce_json,
        role_prompt_text=resolve_role_prompt_text(cfg, role),
        review_isolation=review_isolation,
    )
    context = _role_context(
        role=role, outputs=outputs, review_isolation=review_isolation
    )
    output = _invoke_adapter(
        adapter,
        role=role,
        model=model_ref,
        prompt=prompt,
        context=context,
        cfg=cfg,
    )
    artifact_extension, rendered_output, structured_report = _render_role_output(
        role=role,
        model=model_ref,
        output=output,
        enforce_json=enforce_json,
    )
    certainty = _assess_response_certainty(
        role=role,
        report=structured_report,
        output=output,
    )
    if certainty["warning"]:
        if certainty["curtailed"]:
            logger.error("CERTAINTY CRITICAL %s", certainty["warning"])
        else:
            logger.warning("CERTAINTY LOW %s", certainty["warning"])
    artifact_name = f"{index:02d}_{role}.{artifact_extension}"
    artifact_path = os.path.join(artifacts_dir, artifact_name)
    _write(artifact_path, rendered_output)
    completed_at = time.time()
    duration_ms = int(round((completed_at - started_at) * 1000))
    logger.info(
        "Completed role=%s duration_ms=%d certainty=%.2f",
        role,
        duration_ms,
        certainty["certainty_score"],
    )
    return {
        "role": role,
        "index": index,
        "model": model_ref,
        "artifact_path": artifact_path,
        "rendered_output": rendered_output,
        "structured_report": structured_report,
        "certainty": certainty,
        "execution": {
            "role": role,
            "model": model_ref,
            "artifact": artifact_path,
            "strategy": strategy,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_at)),
            "completed_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(completed_at)
            ),
            "duration_ms": duration_ms,
        },
    }


def _apply_role_result(
    result: Mapping[str, Any],
    *,
    role_outputs: dict[str, str],
    role_artifacts: dict[str, str],
    role_models: dict[str, str],
    execution: list[dict[str, Any]],
) -> None:
    role = str(result["role"])
    role_outputs[role] = str(result["rendered_output"])
    role_artifacts[role] = str(result["artifact_path"])
    role_models[role] = str(result["model"])
    execution.append(dict(result["execution"]))


def _maybe_gate_pipeline(
    *,
    fail_on_high: bool,
    results: list[Mapping[str, Any]],
    artifacts_dir: str,
    run_id: str,
    assurance_level: str,
    mode: str,
    provider: str,
    adapter_name: str,
    scope: str,
    role_models: Mapping[str, str],
    role_artifacts: Mapping[str, str],
    execution: list[dict[str, Any]],
    config_snapshot: str,
    start_role: str | None = None,
    parent_run_id: str | None = None,
) -> None:
    if not fail_on_high:
        return

    blocker_chunks: list[str] = []
    for result in results:
        structured_report = result.get("structured_report")
        if not isinstance(structured_report, Mapping):
            continue
        high_findings = _high_severity_findings(structured_report)
        if not high_findings:
            continue
        titles = ", ".join(finding["title"] for finding in high_findings)
        blocker_chunks.append(f"{result['role']}: {titles}")

    if not blocker_chunks:
        return

    failure = "Pipeline gated by HIGH severity findings in " + "; ".join(blocker_chunks)
    summary_path = _persist_run_outputs(
        artifacts_dir=artifacts_dir,
        run_id=run_id,
        assurance_level=assurance_level,
        mode=mode,
        provider=provider,
        adapter_name=adapter_name,
        scope=scope,
        role_models=role_models,
        role_artifacts=role_artifacts,
        execution=execution,
        status="failed",
        config_snapshot=config_snapshot,
        start_role=start_role,
        parent_run_id=parent_run_id,
        failure=failure,
    )
    raise PipelineError(f"{failure}. Summary: {summary_path}")


def _load_resume_state(
    *,
    cfg: Dict[str, Any],
    artifacts_dir: str,
    role_order: list[str],
    start_role: str | None,
) -> tuple[
    int,
    dict[str, str],
    dict[str, str],
    dict[str, str],
    list[dict[str, Any]],
    str | None,
]:
    if not start_role:
        return 0, {}, {}, {}, [], None

    clean_role = start_role.strip()
    if clean_role not in role_order:
        available = ", ".join(role_order)
        raise PipelineError(
            f"Unknown start role '{start_role}'. Choose one of: {available}"
        )

    start_index = role_order.index(clean_role)
    if start_index == 0:
        return 0, {}, {}, {}, [], None

    state_path = os.path.join(artifacts_dir, "pipeline_state.json")
    if not os.path.exists(state_path):
        raise PipelineError(
            f"Cannot rerun from role '{clean_role}' without existing pipeline_state.json in {artifacts_dir}",
        )

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except json.JSONDecodeError as err:
        raise PipelineError(
            f"Could not parse existing pipeline state at {state_path}"
        ) from err

    if not isinstance(state, dict):
        raise PipelineError(
            f"Existing pipeline state at {state_path} must be a JSON object"
        )

    state_artifacts = state.get("artifacts")
    state_models = state.get("role_models")
    state_execution = state.get("execution")
    if not isinstance(state_artifacts, Mapping):
        raise PipelineError(
            f"Existing pipeline state at {state_path} is missing an artifacts map"
        )

    seeded_outputs: dict[str, str] = {}
    seeded_artifacts: dict[str, str] = {}
    seeded_models: dict[str, str] = {}
    seeded_execution: list[dict[str, Any]] = []
    existing_execution_by_role: dict[str, dict[str, Any]] = {}
    if isinstance(state_execution, list):
        for item in state_execution:
            if not isinstance(item, Mapping):
                continue
            role_name = str(item.get("role") or "").strip()
            if role_name:
                existing_execution_by_role[role_name] = dict(item)

    for role in role_order[:start_index]:
        artifact_ref = state_artifacts.get(role)
        if not isinstance(artifact_ref, str) or not artifact_ref.strip():
            raise PipelineError(
                f"Cannot rerun from role '{clean_role}' because prior role '{role}' has no saved artifact",
            )

        artifact_path = artifact_ref
        if not os.path.isabs(artifact_path):
            artifact_path = os.path.join(artifacts_dir, artifact_path)

        artifact_path = _ensure_artifact_within_dir(artifacts_dir, artifact_path)

        if not os.path.exists(artifact_path):
            raise PipelineError(
                f"Cannot rerun from role '{clean_role}' because prior artifact is missing: {artifact_path}",
            )

        with open(artifact_path, "r", encoding="utf-8") as f:
            seeded_outputs[role] = f.read()

        seeded_artifacts[role] = artifact_path
        model_ref = resolve_role_model(cfg, role)
        if isinstance(state_models, Mapping) and isinstance(
            state_models.get(role), str
        ):
            model_ref = str(state_models[role])
        seeded_models[role] = model_ref
        prior_execution = existing_execution_by_role.get(role, {})
        seeded_execution.append(
            {
                **prior_execution,
                "role": role,
                "model": model_ref,
                "artifact": artifact_path,
                "strategy": "seeded",
            },
        )

    parent_run_id = str(state.get("run_id") or "").strip() or None
    return (
        start_index,
        seeded_outputs,
        seeded_artifacts,
        seeded_models,
        seeded_execution,
        parent_run_id,
    )


def run_pipeline(
    cfg: Dict[str, Any],
    artifacts_dir: str | None = None,
    *,
    start_role: str | None = None,
) -> str:
    """Run the ESE pipeline and write per-role artifacts plus summary outputs."""
    _validate_prompt_limits()
    artifacts_dir = _resolve_artifacts_dir(cfg, artifacts_dir)

    provider = (cfg.get("provider") or {}).get("name", "unknown")
    mode = cfg.get("mode", "ensemble")
    assurance_level = _assurance_level(str(mode))
    run_id = uuid4().hex
    scope = _require_scope(cfg)
    role_order = _normalize_role_order(cfg)
    if not role_order:
        raise PipelineError("No roles configured. Add at least one role under roles.")

    logger.info(
        "Starting ESE pipeline run_id=%s provider=%s mode=%s", run_id, provider, mode
    )
    logger.debug("Role order: %s", role_order)

    os.makedirs(artifacts_dir, exist_ok=True)
    config_snapshot = _config_snapshot_path(artifacts_dir)
    _write_yaml(config_snapshot, cfg)
    adapter_name, adapter = _resolve_adapter(cfg)
    output_cfg = _output_cfg(cfg)
    gating_cfg = _gating_cfg(cfg)
    parallel_cfg = _parallel_cfg(cfg)
    prompt_context = _prompt_context(cfg, artifacts_dir)
    review_isolation = _review_isolation(cfg)
    enforce_json = output_cfg["enforce_json"]
    fail_on_high = gating_cfg["fail_on_high"]

    (
        start_index,
        role_outputs,
        role_artifacts,
        role_models,
        execution,
        parent_run_id,
    ) = _load_resume_state(
        cfg=cfg,
        artifacts_dir=artifacts_dir,
        role_order=role_order,
        start_role=start_role,
    )

    index_pointer = start_index
    while index_pointer < len(role_order):
        role = role_order[index_pointer]
        absolute_index = index_pointer + 1
        if parallel_cfg["parallel_specialists"] and _is_parallelizable_role(role):
            batch: list[tuple[int, str]] = []
            scan_pointer = index_pointer
            while scan_pointer < len(role_order) and _is_parallelizable_role(
                role_order[scan_pointer]
            ):
                batch.append((scan_pointer + 1, role_order[scan_pointer]))
                scan_pointer += 1

            outputs_snapshot = dict(role_outputs)
            max_workers = min(parallel_cfg["max_parallel_roles"], len(batch))
            results: list[dict[str, Any]] = []
            failures: list[tuple[int, str, str]] = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {
                    executor.submit(
                        _execute_role,
                        index=run_index,
                        role=run_role,
                        scope=scope,
                        outputs=outputs_snapshot,
                        additional_context=prompt_context["additional_context"],
                        operator_feedback=prompt_context["operator_feedback"],
                        review_isolation=review_isolation,
                        enforce_json=enforce_json,
                        adapter=adapter,
                        cfg=cfg,
                        artifacts_dir=artifacts_dir,
                        strategy="parallel",
                    ): (run_index, run_role)
                    for run_index, run_role in batch
                }
                for future in as_completed(future_map):
                    run_index, run_role = future_map[future]
                    try:
                        results.append(future.result())
                    except Exception as err:  # noqa: BLE001
                        failures.append((run_index, run_role, str(err)))

            results.sort(key=lambda item: int(item["index"]))
            for result in results:
                _apply_role_result(
                    result,
                    role_outputs=role_outputs,
                    role_artifacts=role_artifacts,
                    role_models=role_models,
                    execution=execution,
                )

            if failures:
                failures.sort(key=lambda item: item[0])
                failed_roles = [role_name for _, role_name, _ in failures]
                completed_roles = [str(result["role"]) for result in results]
                failure_details = "; ".join(
                    f"{role_name}: {message}" for _, role_name, message in failures
                )
                completion_note = ", ".join(completed_roles) or "none"
                failure = (
                    "Parallel specialist batch failed. "
                    f"Completed roles: {completion_note}. "
                    f"Failed roles: {', '.join(failed_roles)}. "
                    f"Details: {failure_details}"
                )
                summary_path = _persist_run_outputs(
                    artifacts_dir=artifacts_dir,
                    run_id=run_id,
                    assurance_level=assurance_level,
                    mode=mode,
                    provider=provider,
                    adapter_name=adapter_name,
                    scope=scope,
                    role_models=role_models,
                    role_artifacts=role_artifacts,
                    execution=execution,
                    status="failed",
                    config_snapshot=config_snapshot,
                    start_role=start_role,
                    parent_run_id=parent_run_id,
                    failed_roles=failed_roles,
                    failure=failure,
                )
                raise PipelineError(f"{failure}. Summary: {summary_path}")

            _maybe_gate_pipeline(
                fail_on_high=fail_on_high,
                results=results,
                artifacts_dir=artifacts_dir,
                run_id=run_id,
                assurance_level=assurance_level,
                mode=mode,
                provider=provider,
                adapter_name=adapter_name,
                scope=scope,
                role_models=role_models,
                role_artifacts=role_artifacts,
                execution=execution,
                config_snapshot=config_snapshot,
                start_role=start_role,
                parent_run_id=parent_run_id,
            )
            index_pointer = scan_pointer
            continue

        try:
            result = _execute_role(
                index=absolute_index,
                role=role,
                scope=scope,
                outputs=role_outputs,
                additional_context=prompt_context["additional_context"],
                operator_feedback=prompt_context["operator_feedback"],
                review_isolation=review_isolation,
                enforce_json=enforce_json,
                adapter=adapter,
                cfg=cfg,
                artifacts_dir=artifacts_dir,
                strategy="serial",
            )
        except Exception as err:  # noqa: BLE001
            logger.error("Role execution failed role=%s error=%s", role, err)
            failure = f"Role '{role}' failed: {err}"
            summary_path = _persist_run_outputs(
                artifacts_dir=artifacts_dir,
                run_id=run_id,
                assurance_level=assurance_level,
                mode=mode,
                provider=provider,
                adapter_name=adapter_name,
                scope=scope,
                role_models=role_models,
                role_artifacts=role_artifacts,
                execution=execution,
                status="failed",
                config_snapshot=config_snapshot,
                start_role=start_role,
                parent_run_id=parent_run_id,
                failed_roles=[role],
                failure=failure,
            )
            raise PipelineError(f"{failure}. Summary: {summary_path}") from err
        _apply_role_result(
            result,
            role_outputs=role_outputs,
            role_artifacts=role_artifacts,
            role_models=role_models,
            execution=execution,
        )
        _maybe_gate_pipeline(
            fail_on_high=fail_on_high,
            results=[result],
            artifacts_dir=artifacts_dir,
            run_id=run_id,
            assurance_level=assurance_level,
            mode=mode,
            provider=provider,
            adapter_name=adapter_name,
            scope=scope,
            role_models=role_models,
            role_artifacts=role_artifacts,
            execution=execution,
            config_snapshot=config_snapshot,
            start_role=start_role,
            parent_run_id=parent_run_id,
        )
        index_pointer += 1

    summary_path = _persist_run_outputs(
        artifacts_dir=artifacts_dir,
        run_id=run_id,
        assurance_level=assurance_level,
        mode=mode,
        provider=provider,
        adapter_name=adapter_name,
        scope=scope,
        role_models=role_models,
        role_artifacts=role_artifacts,
        execution=execution,
        status="completed",
        config_snapshot=config_snapshot,
        start_role=start_role,
        parent_run_id=parent_run_id,
    )
    return summary_path
