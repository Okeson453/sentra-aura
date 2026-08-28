"""Database and schema migration commands."""
from __future__ import annotations

import subprocess
from pathlib import Path

import typer

app = typer.Typer(help="Database and schema migrations")

MIGRATIONS_DIR = Path("migrations")


@app.command("up")
def migrate_up(
    revision: str = typer.Option("head", "--revision", help="Target revision"),
    database_url: str = typer.Option("", "--database-url", help="Database URL (defaults to env)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be applied"),
) -> None:
    """Apply database migrations up to a target revision."""
    if not database_url:
        database_url = "${DATABASE_URL}"

    if dry_run:
        typer.echo(f"[DRY RUN] Would apply migrations up to: {revision}")
        typer.echo(f"[DRY RUN] Database: {database_url}")
        return

    typer.echo(f"Applying migrations up to: {revision}")
    typer.echo(f"Database: {database_url}")

    # In production, this runs Alembic
    try:
        result = subprocess.run(
            ["alembic", "upgrade", revision],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            typer.echo("Migrations applied successfully")
        else:
            typer.echo(f"Migration failed: {result.stderr}", err=True)
            raise typer.Exit(1)
    except FileNotFoundError:
        typer.echo("Alembic not found. Ensure alembic is installed.", err=True)
        raise typer.Exit(1)


@app.command("down")
def migrate_down(
    revision: str = typer.Option("-1", "--revision", help="Target revision (e.g. -1, base, abc123)"),
    database_url: str = typer.Option("", "--database-url", help="Database URL"),
) -> None:
    """Rollback database migrations to a target revision."""
    typer.echo(f"Rolling back migrations to: {revision}")
    try:
        result = subprocess.run(
            ["alembic", "downgrade", revision],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            typer.echo("Rollback completed successfully")
        else:
            typer.echo(f"Rollback failed: {result.stderr}", err=True)
            raise typer.Exit(1)
    except FileNotFoundError:
        typer.echo("Alembic not found.", err=True)
        raise typer.Exit(1)


@app.command("create")
def create_migration(
    message: str = typer.Argument(..., help="Migration message"),
    auto_generate: bool = typer.Option(False, "--auto-generate", help="Auto-detect schema changes"),
) -> None:
    """Create a new Alembic migration."""
    typer.echo(f"Creating migration: {message}")
    cmd = ["alembic", "revision", "-m", message]
    if auto_generate:
        cmd.append("--autogenerate")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            typer.echo(result.stdout)
        else:
            typer.echo(f"Failed: {result.stderr}", err=True)
            raise typer.Exit(1)
    except FileNotFoundError:
        typer.echo("Alembic not found.", err=True)
        raise typer.Exit(1)


@app.command("history")
def migration_history(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Show migration history."""
    try:
        result = subprocess.run(
            ["alembic", "history"] + (["--verbose"] if verbose else []),
            capture_output=True,
            text=True,
            check=False,
        )
        typer.echo(result.stdout if result.returncode == 0 else result.stderr)
    except FileNotFoundError:
        typer.echo("Alembic not found.", err=True)
        raise typer.Exit(1)


@app.command("current")
def current_revision() -> None:
    """Show current database revision."""
    try:
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            check=False,
        )
        typer.echo(result.stdout if result.returncode == 0 else result.stderr)
    except FileNotFoundError:
        typer.echo("Alembic not found.", err=True)
        raise typer.Exit(1)
