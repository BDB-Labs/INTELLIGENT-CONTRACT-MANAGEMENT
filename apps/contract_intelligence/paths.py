from __future__ import annotations

import os
from pathlib import Path


def allowed_roots_from_env() -> tuple[Path, ...]:
    raw = os.getenv("CONTRACT_INTELLIGENCE_ALLOWED_ROOTS", "").strip()
    if not raw:
        return ()
    return tuple(
        Path(part).expanduser().resolve()
        for part in raw.split(os.pathsep)
        if part.strip()
    )


def validate_allowed_root(path: Path, *, label: str, allowed_roots: tuple[Path, ...] | None = None) -> Path:
    roots = allowed_roots if allowed_roots is not None else allowed_roots_from_env()
    if roots and not any(path == root or root in path.parents for root in roots):
        raise ValueError(f"{label} is outside the configured allowed roots: {path}")
    return path


def validate_allowed_roots_configured() -> tuple[Path, ...]:
    roots = allowed_roots_from_env()
    for root in roots:
        if not root.exists():
            raise ValueError(f"Configured allowed root does not exist: {root}")
        if not root.is_dir():
            raise ValueError(f"Configured allowed root must be a directory: {root}")
    return roots


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


def resolve_existing_file(path: str | Path, *, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label} does not exist: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"{label} must be a file: {resolved}")
    return resolved


def resolve_guarded_existing_directory(path: str | Path, *, label: str) -> Path:
    return validate_allowed_root(resolve_existing_directory(path, label=label), label=label)


def resolve_guarded_optional_existing_directory(path: str | Path | None, *, label: str) -> Path | None:
    if path is None:
        return None
    return resolve_guarded_existing_directory(path, label=label)


def resolve_guarded_output_directory(path: str | Path, *, label: str) -> Path:
    return validate_allowed_root(resolve_output_directory(path, label=label), label=label)


def resolve_guarded_existing_file(path: str | Path, *, label: str) -> Path:
    return validate_allowed_root(resolve_existing_file(path, label=label), label=label)


def resolve_guarded_output_file(path: str | Path, *, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if resolved.exists() and not resolved.is_file():
        raise ValueError(f"{label} must be a file path: {resolved}")
    if resolved.parent.exists() and not resolved.parent.is_dir():
        raise ValueError(f"{label} parent must be a directory: {resolved.parent}")
    return validate_allowed_root(resolved, label=label)
