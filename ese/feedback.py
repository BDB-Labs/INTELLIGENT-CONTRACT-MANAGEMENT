"""Local feedback capture and lightweight learning helpers for ESE."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FEEDBACK_STORE_NAME = ".ese_feedback.json"
ALLOWED_FEEDBACK = {"useful", "noisy", "wrong"}


def _feedback_root(path: str | Path) -> Path:
    candidate = Path(path)
    if (candidate / "pipeline_state.json").is_file():
        return candidate.parent
    return candidate


def feedback_store_path(path: str | Path) -> Path:
    """Return the local feedback store path for an artifacts root or run dir."""
    return _feedback_root(path) / FEEDBACK_STORE_NAME


def load_feedback_store(path: str | Path) -> dict[str, Any]:
    """Load the local feedback store, returning an empty structure when missing."""
    store_path = feedback_store_path(path)
    if not store_path.exists():
        return {"version": 1, "items": []}

    try:
        parsed = json.loads(store_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "items": []}

    if not isinstance(parsed, dict):
        return {"version": 1, "items": []}
    items = parsed.get("items")
    if not isinstance(items, list):
        return {"version": 1, "items": []}
    return {"version": 1, "items": [item for item in items if isinstance(item, dict)]}


def record_feedback(
    path: str | Path,
    *,
    role: str,
    title: str,
    feedback: str,
    artifacts_dir: str | None = None,
    details: str | None = None,
) -> dict[str, Any]:
    """Persist one feedback event for a finding title and role."""
    normalized_feedback = (feedback or "").strip().lower()
    if normalized_feedback not in ALLOWED_FEEDBACK:
        allowed = ", ".join(sorted(ALLOWED_FEEDBACK))
        raise ValueError(f"feedback must be one of: {allowed}")

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "role": str(role or "").strip(),
        "title": str(title or "").strip(),
        "feedback": normalized_feedback,
        "artifacts_dir": str(artifacts_dir or "").strip(),
        "details": str(details or "").strip(),
    }
    if not entry["role"]:
        raise ValueError("role is required")
    if not entry["title"]:
        raise ValueError("title is required")

    store_path = feedback_store_path(path)
    store = load_feedback_store(path)
    items = list(store.get("items", []))
    items.append(entry)
    payload = {"version": 1, "items": items}
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return entry


def feedback_summary(path: str | Path) -> dict[str, Any]:
    """Aggregate feedback history into counts, role trends, and prompt guidance."""
    store = load_feedback_store(path)
    items = [item for item in store.get("items", []) if isinstance(item, dict)]
    counts = Counter(
        str(item.get("feedback") or "").strip().lower()
        for item in items
        if str(item.get("feedback") or "").strip().lower() in ALLOWED_FEEDBACK
    )

    by_role: dict[str, dict[str, int]] = {}
    for item in items:
        role = str(item.get("role") or "").strip()
        feedback = str(item.get("feedback") or "").strip().lower()
        if not role or feedback not in ALLOWED_FEEDBACK:
            continue
        role_counts = by_role.setdefault(role, {label: 0 for label in sorted(ALLOWED_FEEDBACK)})
        role_counts[feedback] = role_counts.get(feedback, 0) + 1

    guidance: list[str] = []
    role_bias: dict[str, str] = {}
    for role, role_counts in sorted(by_role.items()):
        useful = role_counts.get("useful", 0)
        noisy = role_counts.get("noisy", 0)
        wrong = role_counts.get("wrong", 0)
        if useful >= max(noisy + wrong, 2):
            role_bias[role] = "positive"
            guidance.append(
                f"{role}: prior operators valued concrete, actionable output with clear remediation.",
            )
            continue
        if noisy + wrong >= max(useful, 2):
            role_bias[role] = "negative"
            guidance.append(
                f"{role}: avoid duplicate or speculative findings and prefer fewer, higher-signal issues without suppressing unique dissent.",
            )

    return {
        "counts": {label: counts.get(label, 0) for label in sorted(ALLOWED_FEEDBACK)},
        "role_counts": by_role,
        "role_bias": role_bias,
        "guidance": guidance,
        "entries": items,
    }


def feedback_prompt_guidance(path: str | Path) -> str:
    """Render feedback-based prompt guidance for future runs."""
    summary = feedback_summary(path)
    guidance = summary.get("guidance", [])
    if not isinstance(guidance, list) or not guidance:
        return ""
    lines = ["Operator feedback from prior runs:"]
    lines.extend(f"- {item}" for item in guidance if isinstance(item, str) and item.strip())
    return "\n".join(lines)
