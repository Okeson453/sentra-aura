"""Tests for sentra-cli."""
import pytest
from typer.testing import CliRunner

from sentra_cli.main import app

runner = CliRunner()


def _invoke_help(args: list[str]):
    """Invoke help, accepting exit_code 0 or 1 due to typer/click 8.2 compat."""
    result = runner.invoke(app, args)
    assert result.exit_code in (0, 1), f"Unexpected exit: {result.output}"
    return result


def test_cli_help():
    result = _invoke_help(["--help"])
    assert "SentraAura Developer CLI" in result.output


def test_agent_command_help():
    result = _invoke_help(["agent", "--help"])
    assert "sentra agent" in result.output


def test_agent_create_invalid_domain():
    result = runner.invoke(app, ["agent", "create", "TestAgent", "--domain", "invalid"])
    assert result.exit_code != 0


def test_eval_command_help():
    result = _invoke_help(["eval", "--help"])
    assert "sentra eval" in result.output


def test_migrate_command_help():
    result = _invoke_help(["migrate", "--help"])
    assert "sentra migrate" in result.output


def test_deploy_command_help():
    result = _invoke_help(["deploy", "--help"])
    assert "sentra deploy" in result.output


def test_lint_command_help():
    result = _invoke_help(["lint", "--help"])
    assert "sentra lint" in result.output
