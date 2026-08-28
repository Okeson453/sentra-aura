"""Agent lifecycle management commands."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(help="Agent lifecycle management")

VALID_DOMAINS = [
    "intelligence", "creative", "production", "clipping", "distribution", "operations"
]


@app.command("create")
def create_agent(
    name: str = typer.Argument(..., help="Agent name (PascalCase)"),
    domain: str = typer.Option(..., "--domain", help=f"Agent domain: {', '.join(VALID_DOMAINS)}"),
    output_dir: str = typer.Option("services", "--output-dir", help="Output directory"),
) -> None:
    """Create a new agent with scaffolding."""
    if domain not in VALID_DOMAINS:
        typer.echo(f"Error: domain must be one of {VALID_DOMAINS}", err=True)
        raise typer.Exit(1)

    agent_dir = Path(output_dir) / f"{name.lower()}-agent"
    if agent_dir.exists():
        typer.echo(f"Error: directory {agent_dir} already exists", err=True)
        raise typer.Exit(1)

    # Create directory structure
    dirs = ["src", "tests", f"evals/{name.lower()}", "prompts"]
    for d in dirs:
        (agent_dir / d).mkdir(parents=True)

    # Write scaffolded files from templates
    template_dir = Path(__file__).parent.parent / "templates" / "agent"
    _write_from_template(template_dir / "agent.py.j2", agent_dir / "src" / "agent.py", {"name": name, "domain": domain})
    _write_from_template(template_dir / "schemas.py.j2", agent_dir / "src" / "schemas.py", {"name": name})
    _write_from_template(template_dir / "config.py.j2", agent_dir / "src" / "config.py", {"name": name})
    _write_from_template(template_dir / "state.py.j2", agent_dir / "src" / "state.py", {"name": name})
    _write_from_template(template_dir / "tools.py.j2", agent_dir / "src" / "tools.py", {"name": name})
    _write_from_template(template_dir / "test_agent.py.j2", agent_dir / "tests" / f"test_{name.lower()}.py", {"name": name})
    _write_from_template(template_dir / "README.md.j2", agent_dir / "README.md", {"name": name, "domain": domain})
    _write_from_template(template_dir / "pyproject.toml.j2", agent_dir / "pyproject.toml", {"name": name.lower()})

    typer.echo(f"Created agent '{name}' in {agent_dir}")


@app.command("list")
def list_agents(
    services_dir: str = typer.Option("services", "--services-dir"),
) -> None:
    """List all agents in the services directory."""
    services_path = Path(services_dir)
    if not services_path.exists():
        typer.echo("No services directory found", err=True)
        raise typer.Exit(1)

    agents = [d.name for d in services_path.iterdir() if d.is_dir() and d.name.endswith("-agent")]
    if not agents:
        typer.echo("No agents found")
        return

    for agent_name in sorted(agents):
        typer.echo(f"  - {agent_name}")


def _write_from_template(template_path: Path, output_path: Path, context: dict[str, Any]) -> None:
    """Read a template file and substitute simple {{var}} placeholders."""
    if template_path.exists():
        content = template_path.read_text()
        for key, value in context.items():
            content = content.replace(f"{{{{{key}}}}}", str(value))
        output_path.write_text(content)
    else:
        output_path.write_text(f"# TODO: {output_path.name}\n")
