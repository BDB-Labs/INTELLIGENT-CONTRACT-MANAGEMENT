from __future__ import annotations

import typer

from ese.config import ConfigValidationError, load_config
from ese.doctor import run_doctor
from ese.init_wizard import ROLE_DESCRIPTIONS, run_wizard
from ese.pipeline import PipelineError, run_pipeline


app = typer.Typer(help="Ensemble Software Engineering (ESE) CLI")


@app.command()
def init(
    config: str = typer.Option("ese.config.yaml", help="Path to write the generated config"),
    simple: bool = typer.Option(
        True,
        "--simple/--advanced",
        help="Use simple setup (default) or advanced role-level setup.",
    ),
):
    """Create an ESE configuration via an interactive wizard."""
    written = run_wizard(config_path=config, advanced=not simple)
    if not written:
        typer.echo("⚠️ Setup canceled. Config was not written.")
        raise typer.Exit(code=1)
    typer.echo(f"✅ Wrote {written}")


@app.command("roles")
def list_roles():
    """List selectable ESE roles and their responsibilities."""
    typer.echo("Selectable ESE roles:")
    for role, description in ROLE_DESCRIPTIONS.items():
        typer.echo(f"  - {role}: {description}")


@app.command()
def doctor(config: str = typer.Option("ese.config.yaml", help="Path to ESE config")):
    """Validate configuration and enforce ensemble constraints."""
    ok, violations, role_models = run_doctor(config_path=config)

    typer.echo("Role model assignments:")
    for role, model in role_models.items():
        typer.echo(f"  - {role}: {model}")

    # Ensemble failures should show the violations and exit.
    if not ok:
        typer.echo("❌ ESE doctor failed. Violations:")
        for v in violations:
            typer.echo(f"  - {v}")
        raise typer.Exit(code=2)

    # Solo mode returns violations as messages to display.
    if violations:
        typer.echo("⚠️ Solo mode enabled:")
        for v in violations:
            typer.echo(f"  - {v}")
    else:
        typer.echo("✅ Doctor checks passed")


def _start_pipeline(config: str, artifacts_dir: str | None) -> None:
    ok, violations, _ = run_doctor(config_path=config)
    if not ok:
        typer.echo("❌ ESE doctor failed. Violations:")
        for v in violations:
            typer.echo(f"  - {v}")
        raise typer.Exit(code=2)

    try:
        cfg = load_config(path=config)
        summary_path = run_pipeline(cfg=cfg or {}, artifacts_dir=artifacts_dir)
    except (ConfigValidationError, PipelineError) as err:
        typer.echo(f"❌ ESE start failed: {err}")
        raise typer.Exit(code=2) from err

    typer.echo(f"✅ Pipeline completed. Summary: {summary_path}")


@app.command("start")
def start(
    config: str = typer.Option("ese.config.yaml", help="Path to ESE config"),
    artifacts_dir: str | None = typer.Option(
        None,
        help="Directory for pipeline artifacts (overrides output.artifacts_dir in config)",
    ),
):
    """Start the full ESE pipeline."""
    _start_pipeline(config=config, artifacts_dir=artifacts_dir)


@app.command("run", hidden=True)
def run_alias(
    config: str = typer.Option("ese.config.yaml", help="Path to ESE config"),
    artifacts_dir: str | None = typer.Option(
        None,
        help="Directory for pipeline artifacts (overrides output.artifacts_dir in config)",
    ),
):
    """Backward-compatible alias for `ese start`."""
    _start_pipeline(config=config, artifacts_dir=artifacts_dir)


if __name__ == "__main__":
    app()
