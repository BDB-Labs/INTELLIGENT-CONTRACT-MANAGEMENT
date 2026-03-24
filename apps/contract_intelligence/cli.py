from __future__ import annotations

from pathlib import Path

import typer

from apps.contract_intelligence.evaluation.corpus import default_corpus_dir, evaluate_corpus
from apps.contract_intelligence.orchestration.bid_review_runner import run_bid_review


app = typer.Typer(help="Contract intelligence pilot CLI")


@app.callback()
def main() -> None:
    """Run contract-intelligence pilot workflows."""


@app.command("bid-review")
def bid_review(
    project_dir: str = typer.Argument(..., help="Path to the project document folder"),
    artifacts_dir: str | None = typer.Option(
        None,
        "--artifacts-dir",
        help="Optional output directory for generated bid-review artifacts",
    ),
) -> None:
    """Run the deterministic construction bid-review pilot over a project folder."""
    result = run_bid_review(project_dir=project_dir, artifacts_dir=artifacts_dir)
    typer.echo(f"Project: {result.project_id}")
    typer.echo(f"Artifacts: {result.artifacts_dir}")
    typer.echo(f"Recommendation: {result.decision_summary.recommendation.value}")
    typer.echo(f"Overall risk: {result.decision_summary.overall_risk.value}")
    typer.echo(f"Human review required: {result.decision_summary.human_review_required}")
    typer.echo("Artifacts written:")
    for filename in sorted(result.artifact_paths):
        relative = Path(result.artifact_paths[filename]).resolve()
        typer.echo(f"  - {filename}: {relative}")


@app.command("evaluate-corpus")
def evaluate_corpus_command(
    corpus_dir: str = typer.Option(
        str(default_corpus_dir()),
        "--corpus-dir",
        help="Directory containing gold-corpus cases with expected.json and inputs/.",
    ),
    artifacts_dir: str | None = typer.Option(
        None,
        "--artifacts-dir",
        help="Optional root directory where evaluation artifacts will be written.",
    ),
) -> None:
    """Run the deterministic gold-corpus evaluation suite for the pilot."""
    results = evaluate_corpus(corpus_dir=corpus_dir, artifacts_root=artifacts_dir)
    passed = 0
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(f"{status} {result.case_id} -> {result.artifacts_dir}")
        for failure in result.failures:
            typer.echo(f"  - {failure}")
        if result.passed:
            passed += 1
    typer.echo(f"Summary: {passed}/{len(results)} cases passed")
    if passed != len(results):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
