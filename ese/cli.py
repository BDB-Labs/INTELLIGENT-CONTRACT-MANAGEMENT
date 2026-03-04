from __future__ import annotations

import typer

from ese.config import load_config
from ese.doctor import run_doctor
from ese.init_wizard import run_wizard
from ese.pipeline import run_pipeline


app = typer.Typer(help="Ensemble Software Engineering (ESE) CLI")


@app.command()
def init(config: str = typer.Option("ese.config.yaml", help="Path to write the generated config")):
    """Create an ESE configuration via an interactive wizard."""
    written = run_wizard(config_path=config)
    typer.echo(f"✅ Wrote {written}")


@app.command()
def doctor(config: str = typer.Option("ese.config.yaml", help="Path to ESE config")):
    """Validate configuration and enforce ensemble constraints."""
    ok, violations, role_models = run_doctor(config_path=config)

    typer.echo("Role model assignments:")
    for role, model in role_models.items():
        typer.echo(f"  - {role}: {model}")

    if not ok:
        typer.echo("❌ ESE doctor failed. Fix config and rerun. Run `ese doctor` for details.")
        raise typer.Exit(code=2)

    if violations:
        typer.echo("⚠️ Violations detected but allowed (solo mode):")
        for a, b, model in violations:
            typer.echo(f"  - {a} and {b} are both {model}")
    else:
        typer.echo("✅ Doctor checks passed")


@app.command()
def run(
    config: str = typer.Option("ese.config.yaml", help="Path to ESE config"),
    artifacts_dir: str = typer.Option("artifacts", help="Directory for pipeline artifacts"),
):
    """Run the full ESE pipeline."""
    cfg = load_config(config_path=config)

    ok, violations, _ = run_doctor(config_path=config)
    if not ok:
        typer.echo("❌ ESE doctor failed. Fix config and rerun. Run `ese doctor` for details.")
        raise typer.Exit(code=2)

    summary_path = run_pipeline(cfg=cfg or {}, artifacts_dir=artifacts_dir)
    typer.echo(f"✅ Pipeline completed. Summary: {summary_path}")


if __name__ == "__main__":
    app()
