"""SentraAura CLI main entry point."""
from __future__ import annotations

import typer

from sentra_cli.commands import agent, eval, migrate, deploy, lint

app = typer.Typer(
    name="sentra",
    help="SentraAura Developer CLI",
    no_args_is_help=True,
)

app.add_typer(agent.app, name="agent", help="Agent lifecycle management")
app.add_typer(eval.app, name="eval", help="Agent evaluation and benchmarking")
app.add_typer(migrate.app, name="migrate", help="Database and schema migrations")
app.add_typer(deploy.app, name="deploy", help="Deployment utilities")
app.add_typer(lint.app, name="lint", help="Lint and type-check utilities")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
