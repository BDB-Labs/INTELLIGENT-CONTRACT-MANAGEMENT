from __future__ import annotations

from pathlib import Path


def resolve_existing_directory(path: str | Path, *, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label} does not exist: {resolved}")
    if not resolved.is_dir():
        raise ValueError(f"{label} must be a directory: {resolved}")
    return resolved


def resolve_optional_existing_directory(path: str | Path | None, *, label: str) -> Path | None:
    if path is None:
        return None
    return resolve_existing_directory(path, label=label)


def resolve_output_directory(path: str | Path, *, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if resolved.exists() and not resolved.is_dir():
        raise ValueError(f"{label} must be a directory path: {resolved}")
    if resolved.parent.exists() and not resolved.parent.is_dir():
        raise ValueError(f"{label} parent must be a directory: {resolved.parent}")
    return resolved
