from __future__ import annotations

from pathlib import Path

import pytest

from ese.feedback import FeedbackStoreError, feedback_store_path, feedback_summary, record_feedback


def test_feedback_is_stored_at_run_family_root(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "20260317-task-run"
    run_dir.mkdir(parents=True)
    (run_dir / "pipeline_state.json").write_text("{}", encoding="utf-8")

    entry = record_feedback(
        run_dir,
        role="adversarial_reviewer",
        title="Null dereference risk",
        feedback="noisy",
        details="Duplicates a stronger reviewer finding.",
    )

    assert entry["feedback"] == "noisy"
    assert feedback_store_path(run_dir) == run_dir.parent / ".ese_feedback.json"


def test_feedback_summary_generates_pluralism_safe_guidance(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    root.mkdir()

    record_feedback(root, role="security_auditor", title="Missing authz", feedback="useful")
    record_feedback(root, role="security_auditor", title="Weak tenant check", feedback="useful")
    record_feedback(root, role="adversarial_reviewer", title="Speculative bug", feedback="wrong")
    record_feedback(root, role="adversarial_reviewer", title="Duplicate blocker", feedback="noisy")

    summary = feedback_summary(root)

    assert summary["counts"]["useful"] == 2
    assert summary["counts"]["wrong"] == 1
    assert summary["role_bias"]["security_auditor"] == "positive"
    assert summary["role_bias"]["adversarial_reviewer"] == "negative"
    assert any("without suppressing unique dissent" in item for item in summary["guidance"])


def test_feedback_store_corruption_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    root.mkdir()
    store_path = feedback_store_path(root)
    store_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(FeedbackStoreError):
        record_feedback(root, role="security_auditor", title="Missing authz", feedback="useful")

    with pytest.raises(FeedbackStoreError):
        feedback_summary(root)
