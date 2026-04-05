"""Shared utility functions for Contract Intelligence."""

from __future__ import annotations

from apps.contract_intelligence.domain.enums import AnalysisPerspective


def normalize_analysis_perspective(
    value: str | AnalysisPerspective,
) -> AnalysisPerspective:
    """Normalize analysis perspective from string or enum to enum.

    Args:
        value: Either a string ('vendor' or 'agency') or AnalysisPerspective enum

    Returns:
        AnalysisPerspective enum value

    Raises:
        ValueError: If value is not a valid perspective
    """
    if isinstance(value, AnalysisPerspective):
        return value
    normalized = str(value).strip().lower()
    try:
        return AnalysisPerspective(normalized)
    except ValueError as exc:
        raise ValueError(
            "analysis_perspective must be either 'vendor' or 'agency'."
        ) from exc


def perspective_label(perspective: AnalysisPerspective) -> str:
    """Get human-readable label for analysis perspective.

    Args:
        perspective: AnalysisPerspective enum value

    Returns:
        Human-readable label string
    """
    return (
        "contractor-side"
        if perspective is AnalysisPerspective.VENDOR
        else "agency-side"
    )
