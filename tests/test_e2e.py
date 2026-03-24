from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from ese.cli import app


runner = CliRunner()


def _run(args: list[str], *, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)  # noqa: S603


def _init_repo(path: Path) -> None:
    _run(["git", "init"], cwd=path)
    _run(["git", "config", "user.email", "ese@example.com"], cwd=path)
    _run(["git", "config", "user.name", "ESE Test"], cwd=path)
    (path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    _run(["git", "add", "app.py"], cwd=path)
    _run(["git", "commit", "-m", "init"], cwd=path)


def test_e2e_task_workflow_supports_status_report_export_and_rerun(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    config_path = tmp_path / "generated-task-config.yaml"
    export_path = tmp_path / "report.sarif.json"

    task_result = runner.invoke(
        app,
        [
            "task",
            "Prepare a safer release workflow",
            "--template",
            "release-readiness",
            "--provider",
            "openai",
            "--execution-mode",
            "demo",
            "--artifacts-dir",
            str(artifacts_dir),
            "--write-config",
            str(config_path),
        ],
    )

    assert task_result.exit_code == 0
    assert "Task run completed" in task_result.stdout
    assert config_path.exists()
    assert (artifacts_dir / "ese_summary.md").exists()
    assert (artifacts_dir / "pipeline_state.json").exists()

    status_result = runner.invoke(
        app,
        ["status", "--artifacts-dir", str(artifacts_dir)],
    )
    assert status_result.exit_code == 0
    assert "Status: completed" in status_result.stdout

    report_result = runner.invoke(
        app,
        ["report", "--artifacts-dir", str(artifacts_dir), "--json"],
    )
    assert report_result.exit_code == 0
    report = json.loads(report_result.stdout)
    assert report["status"] == "completed"
    assert "release_manager" in {item["role"] for item in report["roles"]}

    export_result = runner.invoke(
        app,
        ["export", "--artifacts-dir", str(artifacts_dir), "--format", "sarif", "--output-path", str(export_path)],
    )
    assert export_result.exit_code == 0
    assert export_path.exists()

    rerun_result = runner.invoke(
        app,
        ["rerun", "adversarial_reviewer", "--artifacts-dir", str(artifacts_dir)],
    )
    assert rerun_result.exit_code == 0
    assert "Reran pipeline from role 'adversarial_reviewer'" in rerun_result.stdout


def test_e2e_pr_review_workflow_generates_review_markdown_from_real_git_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "app.py").write_text("print('hello pluralism')\n", encoding="utf-8")
    _run(["git", "commit", "-am", "update app"], cwd=repo)

    artifacts_dir = tmp_path / "pr-artifacts"
    config_path = tmp_path / "generated-pr-config.yaml"

    result = runner.invoke(
        app,
        [
            "pr",
            "--repo-path",
            str(repo),
            "--base",
            "HEAD~1",
            "--head",
            "HEAD",
            "--provider",
            "openai",
            "--execution-mode",
            "demo",
            "--artifacts-dir",
            str(artifacts_dir),
            "--max-diff-chars",
            "120",
            "--write-config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "PR review completed" in result.stdout
    assert config_path.exists()
    assert (artifacts_dir / "pr_review.md").exists()
    assert (artifacts_dir / "pipeline_state.json").exists()

    review_text = (artifacts_dir / "pr_review.md").read_text(encoding="utf-8")
    assert "HEAD" in review_text
    assert "HEAD~1" in review_text
