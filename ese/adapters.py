"""Built-in runtime adapters for ESE role execution."""

from __future__ import annotations

import json
import logging
import os
import random
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Mapping
from dataclasses import dataclass, field
from enum import Enum

from ese.local_runtime import (
    ensure_local_runtime_ready,
    local_base_url,
    LocalRuntimeError,
)

logger = logging.getLogger(__name__)

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_CUSTOM_API_KEY_ENV = "CUSTOM_API_KEY"
DEFAULT_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}

# Retry configuration constants
RETRY_JITTER_FACTOR_MIN = 0.9
RETRY_JITTER_FACTOR_MAX = 1.1

# Timeout defaults (seconds)
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_HEALTH_CHECK_TIMEOUT = 10.0

# Default retry configuration
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 1.0

# Local runtime configuration
LOCAL_RUNTIME_API_KEY = "ollama"  # API key for local Ollama runtime


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Circuit breaker for external API resilience."""

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _half_open_calls: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def record_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._half_open_calls = 0
                    logger.info("Circuit breaker closed")
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("Circuit breaker opened after half-open failure")
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker opened after {self._failure_count} failures"
                )

    def can_execute(self) -> bool:
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit breaker entering half-open state")
                    return True
                return False
            return True

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state


# Global circuit breakers per adapter
_circuit_breakers: dict[str, CircuitBreaker] = {}
_circuit_breakers_lock = threading.Lock()


def _get_circuit_breaker(adapter_name: str) -> CircuitBreaker:
    with _circuit_breakers_lock:
        if adapter_name not in _circuit_breakers:
            _circuit_breakers[adapter_name] = CircuitBreaker()
        return _circuit_breakers[adapter_name]


# Connection pooling with thread-safe HTTP opener
# Using global state with lock is intentional for connection reuse across threads
_http_opener_lock = threading.Lock()
_http_opener: urllib.request.OpenerDirector | None = None


def _get_http_opener() -> urllib.request.OpenerDirector:
    global _http_opener
    with _http_opener_lock:
        if _http_opener is None:
            _http_opener = urllib.request.build_opener()
            _http_opener.addheaders = [("User-Agent", "ese-cli/1.0")]
        return _http_opener


class AdapterExecutionError(RuntimeError):
    """Raised when a runtime adapter cannot execute successfully."""


def _assurance_level(cfg: Mapping[str, Any]) -> str:
    mode = str(cfg.get("mode") or "ensemble").strip().lower()
    return "degraded" if mode == "solo" else "standard"


def _json_output_enabled(cfg: Mapping[str, Any]) -> bool:
    output_cfg = cfg.get("output")
    if not isinstance(output_cfg, Mapping):
        return True
    return bool(output_cfg.get("enforce_json", True))


def dry_run_adapter(
    *,
    role: str,
    model: str,
    prompt: str,
    context: Mapping[str, str],
    cfg: Mapping[str, Any],
) -> str:
    """Return deterministic placeholder output without external model calls."""
    snippet = prompt[:400].strip()
    review_isolation = str(
        (cfg.get("runtime") or {}).get("review_isolation") or "scope_and_implementation"
    )
    if _json_output_enabled(cfg):
        payload = {
            "summary": f"Dry-run placeholder output for role '{role}'.",
            "confidence": "MEDIUM",
            "assumptions": [
                "This run used the dry-run adapter and did not execute against a live model.",
            ],
            "unknowns": [
                "No provider-backed reasoning or external validation was performed.",
            ],
            "findings": [],
            "artifacts": [],
            "code_suggestions": [],
            "next_steps": [
                "Replace dry-run with a real adapter to execute this role against a model.",
            ],
            "metadata": {
                "model": model,
                "adapter": "dry-run",
                "assurance_level": _assurance_level(cfg),
                "prompt_excerpt": snippet or "(empty prompt)",
                "context_keys": sorted(context.keys()),
                "review_isolation": review_isolation,
            },
        }
        return json.dumps(payload)

    lines = [
        f"# {role}",
        "",
        f"Model: {model}",
        "Adapter: dry-run",
        "",
        "Prompt excerpt:",
        snippet or "(empty prompt)",
    ]
    if context:
        lines.extend(["", "Context keys:", ", ".join(sorted(context.keys()))])
    return "\n".join(lines) + "\n"


def _parse_provider_model(model: str) -> tuple[str, str]:
    if ":" in model:
        provider, model_name = model.split(":", 1)
        return provider.strip().lower(), model_name.strip()
    return "unknown", model.strip()


def _runtime_number(
    runtime_cfg: Mapping[str, Any],
    name: str,
    default: float,
    *,
    allow_zero: bool = False,
) -> float:
    raw = runtime_cfg.get(name, default)
    try:
        value = float(raw)
    except (TypeError, ValueError) as err:
        raise AdapterExecutionError(f"runtime.{name} must be numeric") from err
    if value < 0:
        comparator = ">= 0" if allow_zero else "> 0"
        raise AdapterExecutionError(f"runtime.{name} must be {comparator}")
    if not allow_zero and value == 0:
        raise AdapterExecutionError(f"runtime.{name} must be > 0")
    return value


def _provider_cfg(cfg: Mapping[str, Any]) -> Mapping[str, Any]:
    provider = cfg.get("provider")
    if isinstance(provider, Mapping):
        return provider
    return {}


def _runtime_cfg(cfg: Mapping[str, Any]) -> Mapping[str, Any]:
    runtime = cfg.get("runtime")
    if isinstance(runtime, Mapping):
        return runtime
    return {}


def _runtime_openai_cfg(cfg: Mapping[str, Any]) -> Mapping[str, Any]:
    runtime = _runtime_cfg(cfg)
    openai_cfg = runtime.get("openai")
    if isinstance(openai_cfg, Mapping):
        return openai_cfg
    return {}


def _runtime_custom_api_cfg(cfg: Mapping[str, Any]) -> Mapping[str, Any]:
    runtime = _runtime_cfg(cfg)
    custom_api_cfg = runtime.get("custom_api")
    if isinstance(custom_api_cfg, Mapping):
        return custom_api_cfg
    return {}


def _runtime_local_cfg(cfg: Mapping[str, Any]) -> Mapping[str, Any]:
    runtime = _runtime_cfg(cfg)
    local_cfg = runtime.get("local")
    if isinstance(local_cfg, Mapping):
        return local_cfg
    return {}


def _openai_base_url(cfg: Mapping[str, Any]) -> str:
    provider_cfg = _provider_cfg(cfg)
    openai_cfg = _runtime_openai_cfg(cfg)

    base_url = (
        openai_cfg.get("base_url")
        or provider_cfg.get("base_url")
        or DEFAULT_OPENAI_BASE_URL
    )
    if not isinstance(base_url, str) or not base_url.strip():
        raise AdapterExecutionError("OpenAI base URL must be a non-empty string")
    return base_url.rstrip("/")


def _custom_api_base_url(cfg: Mapping[str, Any]) -> str:
    provider_cfg = _provider_cfg(cfg)
    custom_api_cfg = _runtime_custom_api_cfg(cfg)
    base_url = custom_api_cfg.get("base_url") or provider_cfg.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        raise AdapterExecutionError(
            "Custom API base URL is required. Set provider.base_url or runtime.custom_api.base_url.",
        )
    return base_url.rstrip("/")


def _local_base_url(cfg: Mapping[str, Any]) -> str:
    base_url = local_base_url(cfg)
    if not isinstance(base_url, str) or not base_url.strip():
        raise AdapterExecutionError("Local base URL must be a non-empty string")
    return base_url.rstrip("/")


def _api_key_from_env(
    cfg: Mapping[str, Any], *, default_env: str, adapter_name: str
) -> str:
    provider_cfg = _provider_cfg(cfg)
    api_key_env = provider_cfg.get("api_key_env") or default_env
    if not isinstance(api_key_env, str) or not api_key_env.strip():
        raise AdapterExecutionError("provider.api_key_env must be a non-empty string")
    api_key_env = api_key_env.strip()

    api_key = os.getenv(api_key_env)
    if not api_key:
        raise AdapterExecutionError(
            f"Missing API key in env var '{api_key_env}' for {adapter_name} adapter",
        )
    return api_key


def _openai_api_key(cfg: Mapping[str, Any]) -> str:
    return _api_key_from_env(cfg, default_env="OPENAI_API_KEY", adapter_name="OpenAI")


def _custom_api_key(cfg: Mapping[str, Any]) -> str:
    return _api_key_from_env(
        cfg,
        default_env=DEFAULT_CUSTOM_API_KEY_ENV,
        adapter_name="custom_api",
    )


def _openai_payload(
    *,
    role: str,
    model_name: str,
    prompt: str,
    context: Mapping[str, str],
    cfg: Mapping[str, Any],
) -> dict[str, Any]:
    runtime_cfg = _runtime_cfg(cfg)
    # Context is available for future use but not currently needed in payload

    instructions = "Respond in concise Markdown focused on actionable output."
    if _json_output_enabled(cfg):
        instructions = "Return valid JSON only and follow the requested schema exactly."

    payload: dict[str, Any] = {
        "model": model_name,
        "instructions": instructions,
        "input": prompt,
    }

    max_output_tokens = runtime_cfg.get("max_output_tokens")
    if max_output_tokens is not None:
        try:
            token_limit = int(max_output_tokens)
        except (TypeError, ValueError) as err:
            raise AdapterExecutionError(
                "runtime.max_output_tokens must be an integer"
            ) from err
        if token_limit <= 0:
            raise AdapterExecutionError("runtime.max_output_tokens must be > 0")
        payload["max_output_tokens"] = token_limit

    return payload


def _extract_openai_text(data: Mapping[str, Any]) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = data.get("output")
    texts: list[str] = []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, Mapping):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())

    if texts:
        return "\n\n".join(texts)
    raise AdapterExecutionError("OpenAI response did not contain text output")


def _is_retryable_status(
    status_code: int, cfg: Mapping[str, Any] | None = None
) -> bool:
    runtime_cfg = _runtime_cfg(cfg) if cfg else {}
    retryable_codes = runtime_cfg.get("retryable_status_codes")
    if retryable_codes is not None:
        if isinstance(retryable_codes, (list, set, tuple)):
            return status_code in retryable_codes
        if isinstance(retryable_codes, str):
            codes = {
                int(x.strip())
                for x in retryable_codes.split(",")
                if x.strip().isdigit()
            }
            if codes:
                return status_code in codes
    return status_code in DEFAULT_RETRYABLE_STATUS_CODES


def _truncate_for_error(text: str, limit: int = 500) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def _redact_error_text(text: str) -> str:
    redacted = text
    patterns: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]+\b"), "Bearer [REDACTED]"),
        (
            re.compile(
                r"(?i)\b(api[_-]?key|token|secret)(\s*[:=]\s*)([A-Za-z0-9._\-]{8,})"
            ),
            r"\1\2[REDACTED]",
        ),
    ]
    for pattern, replacement in patterns:
        redacted = pattern.sub(replacement, redacted)
    return redacted


RETRY_JITTER_MIN = 0.9
RETRY_JITTER_MAX = 1.1


def _retry_delay(retry_backoff_seconds: float, attempt: int) -> float:
    jitter_factor = random.uniform(RETRY_JITTER_FACTOR_MIN, RETRY_JITTER_FACTOR_MAX)
    return retry_backoff_seconds * attempt * jitter_factor


def _execute_responses_request(
    *,
    url: str,
    api_key: str | None,
    payload: Mapping[str, Any],
    timeout_seconds: float,
    max_retries: int,
    retry_backoff_seconds: float,
    auth_error_message: str,
    provider_name: str,
    role: str,
    cfg: Mapping[str, Any] | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> str:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )

    last_error: str | None = None
    attempts = max_retries + 1
    for attempt in range(1, attempts + 1):
        # Check circuit breaker before attempting
        if circuit_breaker is not None and not circuit_breaker.can_execute():
            raise AdapterExecutionError(
                f"{provider_name} circuit breaker is open, request skipped"
            )

        try:
            # Use connection pool
            opener = _get_http_opener()
            with opener.open(request, timeout=timeout_seconds) as response:  # noqa: S310
                response_text = response.read().decode("utf-8")
                parsed = json.loads(response_text)
                if not isinstance(parsed, Mapping):
                    raise AdapterExecutionError(
                        f"{provider_name} response JSON must be an object"
                    )
                # Record success in circuit breaker
                if circuit_breaker is not None:
                    circuit_breaker.record_success()
                return _extract_openai_text(parsed)
        except urllib.error.HTTPError as err:
            response_body = err.read().decode("utf-8", errors="replace")
            status = err.code
            # Record failure in circuit breaker
            if circuit_breaker is not None:
                circuit_breaker.record_failure()
            if status in {401, 403}:
                raise AdapterExecutionError(
                    f"{auth_error_message} Role: {role}."
                ) from err

            last_error = (
                f"provider={provider_name} role={role} status={status} "
                f"attempt={attempt}/{attempts} body={_truncate_for_error(_redact_error_text(response_body))}"
            )
            if attempt < attempts and _is_retryable_status(status, cfg):
                time.sleep(_retry_delay(retry_backoff_seconds, attempt))
                continue

            raise AdapterExecutionError(
                f"{provider_name} request failed ({last_error})"
            ) from err
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            # Record failure in circuit breaker
            if circuit_breaker is not None:
                circuit_breaker.record_failure()
            last_error = (
                f"provider={provider_name} role={role} attempt={attempt}/{attempts} "
                f"error={_truncate_for_error(_redact_error_text(str(err)))}"
            )
            if attempt < attempts:
                time.sleep(_retry_delay(retry_backoff_seconds, attempt))
                continue
            raise AdapterExecutionError(
                f"{provider_name} request failed after retries: {last_error}"
            ) from err
        except json.JSONDecodeError as err:
            raise AdapterExecutionError(
                f"{provider_name} response was not valid JSON for role '{role}'"
            ) from err

    raise AdapterExecutionError(
        f"{provider_name} request failed after retries: {last_error or 'unknown error'}",
    )


def openai_adapter(
    *,
    role: str,
    model: str,
    prompt: str,
    context: Mapping[str, str],
    cfg: Mapping[str, Any],
) -> str:
    """Execute role prompt using the OpenAI Responses API."""
    provider_name, model_name = _parse_provider_model(model)
    if provider_name != "openai":
        raise AdapterExecutionError(
            f"OpenAI adapter requires openai:* model refs, received '{model}'",
        )
    if not model_name:
        raise AdapterExecutionError("Model reference is missing model name")

    runtime_cfg = _runtime_cfg(cfg)
    timeout_seconds = _runtime_number(runtime_cfg, "timeout_seconds", 60.0)
    max_retries = int(_runtime_number(runtime_cfg, "max_retries", 2, allow_zero=True))
    retry_backoff_seconds = _runtime_number(runtime_cfg, "retry_backoff_seconds", 1.0)

    payload = _openai_payload(
        role=role,
        model_name=model_name,
        prompt=prompt,
        context=context,
        cfg=cfg,
    )
    base_url = _openai_base_url(cfg)
    api_key = _openai_api_key(cfg)
    url = f"{base_url}/responses"

    circuit_breaker = _get_circuit_breaker("openai")

    return _execute_responses_request(
        url=url,
        api_key=api_key,
        payload=payload,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        auth_error_message="OpenAI authentication failed. Check provider.api_key_env and token scope.",
        provider_name="OpenAI",
        role=role,
        cfg=cfg,
        circuit_breaker=circuit_breaker,
    )


def custom_api_adapter(
    *,
    role: str,
    model: str,
    prompt: str,
    context: Mapping[str, str],
    cfg: Mapping[str, Any],
) -> str:
    """Execute role prompt against a custom Responses-compatible API gateway."""
    provider_name, model_name = _parse_provider_model(model)
    configured_provider = str((_provider_cfg(cfg).get("name") or "")).strip().lower()
    if not configured_provider:
        raise AdapterExecutionError(
            "provider.name must be a non-empty string for custom_api adapter"
        )
    if configured_provider == "openai":
        raise AdapterExecutionError(
            "custom_api adapter cannot be used with provider.name='openai'"
        )
    if provider_name in {"", "unknown"}:
        raise AdapterExecutionError(
            "Custom API role model must include provider and model id"
        )
    if provider_name != configured_provider:
        raise AdapterExecutionError(
            f"Role model provider '{provider_name}' does not match configured provider '{configured_provider}'",
        )
    if not model_name:
        raise AdapterExecutionError("Custom API role model is missing model id")

    runtime_cfg = _runtime_cfg(cfg)
    timeout_seconds = _runtime_number(runtime_cfg, "timeout_seconds", 60.0)
    max_retries = int(_runtime_number(runtime_cfg, "max_retries", 2, allow_zero=True))
    retry_backoff_seconds = _runtime_number(runtime_cfg, "retry_backoff_seconds", 1.0)

    payload = _openai_payload(
        role=role,
        model_name=model_name,
        prompt=prompt,
        context=context,
        cfg=cfg,
    )
    base_url = _custom_api_base_url(cfg)
    api_key = _custom_api_key(cfg)
    url = f"{base_url}/responses"

    return _execute_responses_request(
        url=url,
        api_key=api_key,
        payload=payload,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        auth_error_message="Custom API authentication failed. Check provider.api_key_env and token scope.",
        provider_name=f"Custom API ({configured_provider})",
        role=role,
        cfg=cfg,
        circuit_breaker=_get_circuit_breaker(f"custom_api_{configured_provider}"),
    )


def local_adapter(
    *,
    role: str,
    model: str,
    prompt: str,
    context: Mapping[str, str],
    cfg: Mapping[str, Any],
) -> str:
    """Execute role prompt against a local Ollama runtime."""
    provider_name, model_name = _parse_provider_model(model)
    if provider_name != "local":
        raise AdapterExecutionError(
            f"Local adapter requires local:* model refs, received '{model}'",
        )
    if not model_name:
        raise AdapterExecutionError("Local model reference is missing model name")

    runtime_cfg = _runtime_cfg(cfg)
    timeout_seconds = _runtime_number(runtime_cfg, "timeout_seconds", 60.0)
    max_retries = int(_runtime_number(runtime_cfg, "max_retries", 2, allow_zero=True))
    retry_backoff_seconds = _runtime_number(runtime_cfg, "retry_backoff_seconds", 1.0)

    try:
        ensure_local_runtime_ready(cfg, auto_start=True, require_models=True)
    except LocalRuntimeError as err:
        raise AdapterExecutionError(str(err)) from err

    payload = _openai_payload(
        role=role,
        model_name=model_name,
        prompt=prompt,
        context=context,
        cfg=cfg,
    )
    local_cfg = _runtime_local_cfg(cfg)
    base_url = _local_base_url(cfg)
    api_key = None
    if bool(local_cfg.get("use_openai_compat_auth", True)):
        api_key = LOCAL_RUNTIME_API_KEY
    url = f"{base_url}/responses"

    return _execute_responses_request(
        url=url,
        api_key=api_key,
        payload=payload,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        auth_error_message="Local adapter authentication failed unexpectedly.",
        provider_name="Local adapter",
        role=role,
        cfg=cfg,
        circuit_breaker=_get_circuit_breaker("local"),
    )


def check_adapter_health(
    adapter_name: str,
    cfg: Mapping[str, Any],
) -> tuple[bool, str]:
    """Check if an adapter's endpoint is reachable and responsive."""
    if adapter_name == "dry-run":
        return True, "dry-run adapter always ready"

    if adapter_name == "openai":
        try:
            base_url = _openai_base_url(cfg)
            api_key = _openai_api_key(cfg)
            url = f"{base_url}/models"
            request = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {api_key}"}
            )
            opener = _get_http_opener()
            with opener.open(request, timeout=10) as response:  # noqa: S310
                if response.status == 200:
                    cb = _get_circuit_breaker("openai")
                    return (
                        True,
                        f"OpenAI endpoint reachable at {base_url} (circuit: {cb.state.value})",
                    )
        except (urllib.error.URLError, TimeoutError) as e:
            return False, f"OpenAI endpoint unreachable: {e}"
        except Exception as e:
            logger.exception("Unexpected error checking OpenAI health")
            return False, f"OpenAI endpoint error: {e}"

    if adapter_name == "local":
        try:
            base_url = _local_base_url(cfg)
            url = f"{base_url}/tags"
            request = urllib.request.Request(url)
            local_cfg = _runtime_local_cfg(cfg)
            if bool(local_cfg.get("use_openai_compat_auth", True)):
                request.add_header("Authorization", "Bearer ollama")
            opener = _get_http_opener()
            with opener.open(request, timeout=10) as response:  # noqa: S310
                if response.status == 200:
                    cb = _get_circuit_breaker("local")
                    return (
                        True,
                        f"Local endpoint reachable at {base_url} (circuit: {cb.state.value})",
                    )
        except (urllib.error.URLError, TimeoutError) as e:
            return False, f"Local endpoint unreachable: {e}"
        except Exception as e:
            logger.exception("Unexpected error checking local health")
            return False, f"Local endpoint error: {e}"

    if adapter_name == "custom_api":
        try:
            base_url = _custom_api_base_url(cfg)
            api_key = _custom_api_key(cfg)
            url = f"{base_url}/models"
            request = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {api_key}"}
            )
            opener = _get_http_opener()
            with opener.open(request, timeout=10) as response:  # noqa: S310
                if response.status == 200:
                    return True, f"Custom API endpoint reachable at {base_url}"
        except (urllib.error.URLError, TimeoutError) as e:
            return False, f"Custom API endpoint unreachable: {e}"
        except Exception as e:
            logger.exception("Unexpected error checking custom API health")
            return False, f"Custom API endpoint error: {e}"

    return False, f"Unknown adapter: {adapter_name}"


BUILTIN_ADAPTERS = {
    "dry-run": dry_run_adapter,
    "openai": openai_adapter,
    "local": local_adapter,
    "custom_api": custom_api_adapter,
}
