"""ESE pipeline runner with pluggable role adapters and artifact chaining."""

from __future__ import annotations

import importlib
import json
import os
import textwrap
from typing import Any, Callable, Dict, Mapping, Protocol

from ese.adapters import AdapterExecutionError, BUILTIN_ADAPTERS
from ese.config import resolve_role_model

PIPELINE_ORDER = [
    "architect",
    "implementer",
    "adversarial_reviewer",
    "security_auditor",
    "test_generator",
    "performance_analyst",
]

JSON_REPORT_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


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


def _normalize_role_order(cfg: Dict[str, Any]) -> list[str]:
    roles_cfg = cfg.get("roles") or {}
    configured_roles = list(roles_cfg.keys()) if isinstance(roles_cfg, dict) else []
    if not configured_roles:
        return PIPELINE_ORDER.copy()

    ordered: list[str] = [role for role in PIPELINE_ORDER if role in configured_roles]
    ordered.extend(role for role in configured_roles if role not in ordered)
    return ordered


def _build_scope(cfg: Dict[str, Any]) -> str:
    input_cfg = cfg.get("input") or {}
    candidates = [
        input_cfg.get("scope"),
        cfg.get("scope"),
        input_cfg.get("prompt"),
        cfg.get("prompt"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return "No project scope supplied. Proceed with generic role behavior."


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


def _resolve_artifacts_dir(cfg: Dict[str, Any], artifacts_dir: str | None) -> str:
    if isinstance(artifacts_dir, str) and artifacts_dir.strip():
        return artifacts_dir.strip()
    configured = _output_cfg(cfg).get("artifacts_dir")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    return "artifacts"


def _json_report_contract() -> str:
    return textwrap.dedent(
        """
        Return valid JSON only, with no Markdown fences or prose outside the JSON object.
        Use this schema exactly:
        {
          "summary": "string",
          "findings": [
            {
              "severity": "LOW | MEDIUM | HIGH | CRITICAL",
              "title": "string",
              "details": "string"
            }
          ],
          "artifacts": ["string"],
          "next_steps": ["string"]
        }
        Use empty arrays when there are no findings, artifacts, or next steps.
        """,
    ).strip()


def _role_prompt(
    role: str,
    scope: str,
    outputs: Mapping[str, str],
    *,
    enforce_json: bool,
) -> str:
    architect_output = outputs.get("architect", "").strip()
    implementer_output = outputs.get("implementer", "").strip()
    json_contract = f"\n\n{_json_report_contract()}" if enforce_json else ""

    if role == "architect":
        return textwrap.dedent(
            f"""
            You are the Architect.
            Produce a concise implementation plan for this scope:

            {scope}

            {json_contract}
            """,
        ).strip()

    if role == "implementer":
        return textwrap.dedent(
            f"""
            You are the Implementer.
            Build from the Architect plan and scope.

            Scope:
            {scope}

            Architect Plan:
            {architect_output or "(none provided)"}

            {json_contract}
            """,
        ).strip()

    return textwrap.dedent(
        f"""
        You are the {role}.
        Review the implementation against scope and report findings.

        Scope:
        {scope}

        Implementer Output:
        {implementer_output or "(none provided)"}

        {json_contract}
        """,
    ).strip()


def _role_context(role: str, outputs: Mapping[str, str]) -> Dict[str, str]:
    if role == "architect":
        return {}
    if role == "implementer":
        return {"architect": outputs.get("architect", "")}
    return {
        "implementer": outputs.get("implementer", ""),
        "architect": outputs.get("architect", ""),
    }


def _load_custom_adapter(reference: str) -> RoleAdapter:
    if ":" not in reference:
        raise PipelineError(
            "runtime.adapter must be one of {'dry-run', 'openai', 'custom_api'} or a Python reference in 'module:function' format",
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


def _resolve_adapter(cfg: Dict[str, Any]) -> tuple[str, RoleAdapter]:
    runtime_cfg = cfg.get("runtime") or {}
    reference = (runtime_cfg.get("adapter") or "dry-run").strip()
    if not reference:
        reference = "dry-run"

    builtin = BUILTIN_ADAPTERS.get(reference)
    if builtin is not None:
        return reference, builtin

    return reference, _load_custom_adapter(reference)


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
        result = adapter(role=role, model=model, prompt=prompt, context=context, cfg=cfg)
    except AdapterExecutionError as err:
        raise PipelineError(f"Adapter execution failed for role '{role}': {err}") from err
    except Exception as err:  # noqa: BLE001 - preserve adapter stack info in message.
        raise PipelineError(f"Adapter execution failed for role '{role}': {err}") from err

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

    findings = report.get("findings")
    if not isinstance(findings, list):
        raise PipelineError(f"JSON report for role '{role}' must contain a list field 'findings'")

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
        if not isinstance(raw_value, list) or any(not isinstance(item, str) for item in raw_value):
            raise PipelineError(
                f"JSON report for role '{role}' must contain a string list field '{key}'",
            )
        report[key] = [item.strip() for item in raw_value if item.strip()]

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
    mode: str,
    provider: str,
    adapter_name: str,
    scope: str,
    role_models: Mapping[str, str],
    role_artifacts: Mapping[str, str],
    execution: list[dict[str, str]],
    status: str,
    failure: str | None = None,
) -> str:
    summary_lines = [
        "# ESE Summary",
        "",
        f"Status: {status}",
        f"Mode: {mode}",
        f"Provider: {provider}",
        f"Adapter: {adapter_name}",
        "",
        "Executed roles:",
    ]
    summary_lines.extend(f"- {item['role']} ({item['model']}) -> {item['artifact']}" for item in execution)
    if failure:
        summary_lines.extend(["", f"Failure: {failure}"])

    summary_path = os.path.join(artifacts_dir, "ese_summary.md")
    _write(summary_path, "\n".join(summary_lines) + "\n")

    state: dict[str, Any] = {
        "status": status,
        "mode": mode,
        "provider": provider,
        "adapter": adapter_name,
        "scope": scope,
        "role_models": dict(role_models),
        "artifacts": dict(role_artifacts),
        "execution": execution,
    }
    if failure:
        state["failure"] = failure

    state_path = os.path.join(artifacts_dir, "pipeline_state.json")
    _write(state_path, json.dumps(state, indent=2))
    return summary_path


def run_pipeline(cfg: Dict[str, Any], artifacts_dir: str | None = None) -> str:
    """Run the ESE pipeline and write per-role artifacts plus summary outputs."""
    artifacts_dir = _resolve_artifacts_dir(cfg, artifacts_dir)
    os.makedirs(artifacts_dir, exist_ok=True)

    provider = (cfg.get("provider") or {}).get("name", "unknown")
    mode = cfg.get("mode", "ensemble")
    scope = _build_scope(cfg)
    role_order = _normalize_role_order(cfg)
    adapter_name, adapter = _resolve_adapter(cfg)
    output_cfg = _output_cfg(cfg)
    gating_cfg = _gating_cfg(cfg)
    enforce_json = output_cfg["enforce_json"]
    fail_on_high = gating_cfg["fail_on_high"]

    role_outputs: dict[str, str] = {}
    role_artifacts: dict[str, str] = {}
    role_models: dict[str, str] = {}
    execution: list[dict[str, str]] = []

    for index, role in enumerate(role_order, start=1):
        model_ref = resolve_role_model(cfg, role)
        prompt = _role_prompt(role=role, scope=scope, outputs=role_outputs, enforce_json=enforce_json)
        context = _role_context(role=role, outputs=role_outputs)
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

        artifact_name = f"{index:02d}_{role}.{artifact_extension}"
        artifact_path = os.path.join(artifacts_dir, artifact_name)
        _write(artifact_path, rendered_output)

        role_outputs[role] = rendered_output
        role_artifacts[role] = artifact_path
        role_models[role] = model_ref
        execution.append(
            {
                "role": role,
                "model": model_ref,
                "artifact": artifact_path,
            },
        )

        if fail_on_high and structured_report is not None:
            high_findings = _high_severity_findings(structured_report)
            if high_findings:
                finding_titles = ", ".join(finding["title"] for finding in high_findings)
                failure = (
                    f"Pipeline gated by HIGH severity findings in role '{role}': {finding_titles}"
                )
                summary_path = _write_summary_and_state(
                    artifacts_dir=artifacts_dir,
                    mode=mode,
                    provider=provider,
                    adapter_name=adapter_name,
                    scope=scope,
                    role_models=role_models,
                    role_artifacts=role_artifacts,
                    execution=execution,
                    status="failed",
                    failure=failure,
                )
                raise PipelineError(f"{failure}. Summary: {summary_path}")

    return _write_summary_and_state(
        artifacts_dir=artifacts_dir,
        mode=mode,
        provider=provider,
        adapter_name=adapter_name,
        scope=scope,
        role_models=role_models,
        role_artifacts=role_artifacts,
        execution=execution,
        status="completed",
    )
