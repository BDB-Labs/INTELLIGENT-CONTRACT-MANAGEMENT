"""ESE system-wide constants and shared utilities.

Centralizes configuration constants, default values, and shared helper
functions that were previously scattered across multiple modules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Execution Modes
# ---------------------------------------------------------------------------

DEMO_EXECUTION_MODE = "demo"
LIVE_EXECUTION_MODE = "live"
AUTO_EXECUTION_MODE = "auto"

# ---------------------------------------------------------------------------
# Pipeline Defaults
# ---------------------------------------------------------------------------

PIPELINE_ORDER = [
    "architect",
    "implementer",
    "adversarial_reviewer",
    "reviewer",
    "qa_engineer",
    "security_auditor",
    "test_generator",
    "release_manager",
    "doc_writer",
    "devops_engineer",
]

PROMPT_LIMITS = {
    "scope": 4000,
    "additional_context": 6000,
    "operator_feedback": 3000,
    "architect_output": 6000,
    "implementer_output": 8000,
    "upstream_artifact": 6000,
}

STATE_CONTRACT_VERSION = 2
REPORT_CONTRACT_VERSION = 2
CONFIG_VERSION = 1

PROMPT_TRUNCATION_MARKER = "[...truncated for size...]"

# ---------------------------------------------------------------------------
# Adapter Defaults
# ---------------------------------------------------------------------------

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_CUSTOM_API_KEY_ENV = "CUSTOM_API_KEY"
DEFAULT_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 1.0

# ---------------------------------------------------------------------------
# Certainty Thresholds
# ---------------------------------------------------------------------------

CERTAINTY_THRESHOLD_HIGH = 0.75
CERTAINTY_THRESHOLD_MEDIUM = 0.50
CERTAINTY_INDICATORS = {
    "low": 0.3,
    "medium": 0.6,
    "high": 0.85,
}

# ---------------------------------------------------------------------------
# Document Ingestion Defaults
# ---------------------------------------------------------------------------

MAX_DOCUMENT_BYTES = 8 * 1024 * 1024  # 8 MB
TEXT_SAMPLE_BYTES = 4096
MAX_CHUNK_SIZE = 4000
CHUNK_OVERLAP = 200
MAX_CHARS_PER_DOC = 500_000

# ---------------------------------------------------------------------------
# Feedback Store
# ---------------------------------------------------------------------------

FEEDBACK_STORE_NAME = ".ese_feedback.json"

# ---------------------------------------------------------------------------
# Role Drafting
# ---------------------------------------------------------------------------

OVERLAP_SIMILARITY_THRESHOLD = 0.35

# ---------------------------------------------------------------------------
# PR Review Defaults
# ---------------------------------------------------------------------------

DEFAULT_MAX_DIFF_CHARS = 16000

# ---------------------------------------------------------------------------
# Shared Utilities
# ---------------------------------------------------------------------------


def read_json(path: str | Path) -> dict[str, Any]:
    """Read and parse a JSON file. Returns empty dict if file is missing or malformed."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return {}


def write_json(path: str | Path, data: Any) -> None:
    """Write data as formatted JSON."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
