"""Deployment utility commands."""
from __future__ import annotations

import subprocess
from pathlib import Path

import typer

app = typer.Typer(help="Deployment utilities")


@app.command("build")
def build_service(
    service: str = typer.Argument(..., help="Service name to build"),
    tag: str = typer.Option("latest", "--tag", help="Docker image tag"),
    registry: str = typer.Option("", "--registry", help="Docker registry prefix"),
    push: bool = typer.Option(False, "--push", help="Push after build"),
) -> None:
    """Build a service Docker image."""
    image_name = f"{registry}/{service}:{tag}" if registry else f"sentra-aura/{service}:{tag}"
    service_dir = Path("services") / service

    if not service_dir.exists():
        typer.echo(f"Error: service directory not found: {service_dir}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Building {image_name} from {service_dir}")
    dockerfile = service_dir / "Dockerfile"
    if not dockerfile.exists():
        typer.echo(f"Warning: no Dockerfile found at {dockerfile}", err=True)

    cmd = ["docker", "build", "-t", image_name, "-f", str(dockerfile), str(service_dir)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        typer.echo(f"Build successful: {image_name}")
    else:
        typer.echo(f"Build failed: {result.stderr}", err=True)
        raise typer.Exit(1)

    if push:
        typer.echo(f"Pushing {image_name}...")
        push_result = subprocess.run(
            ["docker", "push", image_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if push_result.returncode != 0:
            typer.echo(f"Push failed: {push_result.stderr}", err=True)
            raise typer.Exit(1)


@app.command("push")
def push_service(
    service: str = typer.Argument(..., help="Service name to push"),
    tag: str = typer.Option("latest", "--tag", help="Docker image tag"),
    registry: str = typer.Option("", "--registry", help="Docker registry prefix"),
) -> None:
    """Push a service Docker image to registry."""
    image_name = f"{registry}/{service}:{tag}" if registry else f"sentra-aura/{service}:{tag}"
    typer.echo(f"Pushing {image_name}...")
    result = subprocess.run(
        ["docker", "push", image_name],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        typer.echo("Push successful")
    else:
        typer.echo(f"Push failed: {result.stderr}", err=True)
        raise typer.Exit(1)


@app.command("helm")
def deploy_helm(
    chart: str = typer.Argument(..., help="Helm chart path or name"),
    namespace: str = typer.Option("sentra-aura", "--namespace", "-n"),
    values: str = typer.Option("", "--values", "-f", help="Values file(s), comma-separated"),
    set_vars: str = typer.Option("", "--set", help="Override values, comma-separated key=val"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Render templates without applying"),
    wait: bool = typer.Option(True, "--wait/--no-wait", help="Wait for deployment"),
) -> None:
    """Deploy via Helm."""
    cmd = ["helm", "upgrade", "--install", chart, chart, "--namespace", namespace]
    if dry_run:
        cmd.append("--dry-run")
    if wait:
        cmd.append("--wait")
    if values:
        for v in values.split(","):
            cmd.extend(["-f", v.strip()])
    if set_vars:
        for s in set_vars.split(","):
            cmd.extend(["--set", s.strip()])

    typer.echo(f"Deploying {chart} to namespace {namespace}")
    typer.echo(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        typer.echo("Helm deploy successful")
        typer.echo(result.stdout)
    else:
        typer.echo(f"Helm deploy failed: {result.stderr}", err=True)
        raise typer.Exit(1)


@app.command("status")
def deployment_status(
    namespace: str = typer.Option("sentra-aura", "--namespace", "-n"),
) -> None:
    """Check deployment status in Kubernetes."""
    cmd = ["kubectl", "get", "pods", "-n", namespace]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    typer.echo(result.stdout if result.returncode == 0 else result.stderr)
