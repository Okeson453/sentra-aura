"""Lint and type-check utility commands."""
from __future__ import annotations

import subprocess
from pathlib import Path

import typer

app = typer.Typer(help="Lint and type-check utilities")

DEFAULT_PATHS = ["packages/", "services/", "tools/"]


@app.command("all")
def lint_all(
    paths: list[str] = typer.Argument(help="Paths to lint"),
    fix: bool = typer.Option(False, "--fix", help="Auto-fix issues where possible"),
) -> None:
    """Run all linting and type-checking."""
    if not paths:
        paths = DEFAULT_PATHS
    exit_code = 0

    typer.echo("=== Running ruff check ===")
    ruff_cmd = ["ruff", "check"] + paths
    if fix:
        ruff_cmd.append("--fix")
    result = subprocess.run(ruff_cmd, capture_output=True, text=True, check=False)
    typer.echo(result.stdout)
    if result.returncode != 0:
        exit_code = 1

    typer.echo("=== Running mypy ===")
    mypy_result = subprocess.run(
        ["mypy"] + paths,
        capture_output=True,
        text=True,
        check=False,
    )
    typer.echo(mypy_result.stdout)
    if mypy_result.returncode != 0:
        exit_code = 1

    if exit_code == 0:
        typer.echo("All checks passed!")
    else:
        typer.echo("Some checks failed.", err=True)
        raise typer.Exit(1)


@app.command("format")
def format_code(
    paths: list[str] = typer.Argument(),
    check: bool = typer.Option(False, "--check", help="Check formatting without modifying"),
) -> None:
    """Format code with ruff."""
    if not paths:
        paths = DEFAULT_PATHS
    cmd = ["ruff", "format"] + paths
    if check:
        cmd.append("--check")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    typer.echo(result.stdout)
    if result.stderr:
        typer.echo(result.stderr, err=True)
    if result.returncode != 0:
        raise typer.Exit(1)


@app.command("types")
def type_check(
    paths: list[str] = typer.Argument(),
    strict: bool = typer.Option(False, "--strict", help="Enable strict mode"),
) -> None:
    """Run mypy type checking."""
    if not paths:
        paths = DEFAULT_PATHS
    cmd = ["mypy"] + paths
    if strict:
        cmd.append("--strict")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    typer.echo(result.stdout)
    if result.stderr:
        typer.echo(result.stderr, err=True)
    if result.returncode != 0:
        raise typer.Exit(1)


@app.command("imports")
def check_imports(
    paths: list[str] = typer.Argument(),
) -> None:
    """Check import ordering with ruff."""
    if not paths:
        paths = DEFAULT_PATHS
    cmd = ["ruff", "check", "--select", "I"] + paths
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    typer.echo(result.stdout)
    if result.returncode != 0:
        raise typer.Exit(1)
