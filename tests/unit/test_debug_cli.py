"""Tests for the debug CLI command group and connect subcommand."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from auto_godot.cli import cli
from auto_godot.debugger.connect import ConnectResult
from auto_godot.debugger.errors import DebuggerConnectionError, DebuggerError


@pytest.fixture()
def runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


def test_debug_group_help(runner: CliRunner) -> None:
    """debug --help should show the group description."""
    result = runner.invoke(cli, ["debug", "--help"])
    assert result.exit_code == 0
    assert "remote debugger protocol" in result.output


def test_debug_connect_help(runner: CliRunner) -> None:
    """debug connect --help should list all expected options."""
    result = runner.invoke(cli, ["debug", "connect", "--help"])
    assert result.exit_code == 0
    assert "--project" in result.output
    assert "--port" in result.output
    assert "--scene" in result.output
    assert "--timeout" in result.output


@patch("auto_godot.commands.debug.async_connect", new_callable=AsyncMock)
def test_debug_connect_default_port(
    mock_connect: AsyncMock,
    runner: CliRunner,
    tmp_path: Path,
) -> None:
    """connect with no --port should pass port=6007 to async_connect."""
    mock_connect.return_value = ConnectResult(
        host="127.0.0.1", port=6007, thread_id=1, game_pid=1234,
    )
    result = runner.invoke(cli, ["debug", "connect", "--project", str(tmp_path)])
    assert result.exit_code == 0
    call_kwargs = mock_connect.call_args
    assert call_kwargs[1]["port"] == 6007 or call_kwargs.kwargs.get("port") == 6007


@patch("auto_godot.commands.debug.async_connect", new_callable=AsyncMock)
def test_debug_connect_custom_port(
    mock_connect: AsyncMock,
    runner: CliRunner,
    tmp_path: Path,
) -> None:
    """connect --port 9999 should pass port=9999 to async_connect."""
    mock_connect.return_value = ConnectResult(
        host="127.0.0.1", port=9999, thread_id=1, game_pid=1234,
    )
    result = runner.invoke(
        cli, ["debug", "connect", "--project", str(tmp_path), "--port", "9999"],
    )
    assert result.exit_code == 0
    # async_connect is called via asyncio.run(); check the args
    call_kwargs = mock_connect.call_args
    assert call_kwargs[1].get("port") == 9999 or call_kwargs.kwargs.get("port") == 9999


@patch("auto_godot.commands.debug.async_connect", new_callable=AsyncMock)
def test_debug_connect_with_scene(
    mock_connect: AsyncMock,
    runner: CliRunner,
    tmp_path: Path,
) -> None:
    """connect --scene should pass scene to async_connect."""
    mock_connect.return_value = ConnectResult(
        host="127.0.0.1", port=6007, thread_id=1, game_pid=1234,
    )
    result = runner.invoke(
        cli,
        ["debug", "connect", "--project", str(tmp_path), "--scene", "res://main.tscn"],
    )
    assert result.exit_code == 0
    call_kwargs = mock_connect.call_args
    assert call_kwargs[1].get("scene") == "res://main.tscn" or call_kwargs.kwargs.get("scene") == "res://main.tscn"


@patch("auto_godot.commands.debug.async_connect", new_callable=AsyncMock)
def test_debug_connect_json_output(
    mock_connect: AsyncMock,
    runner: CliRunner,
    tmp_path: Path,
) -> None:
    """--json flag should produce structured JSON output with status connected."""
    mock_connect.return_value = ConnectResult(
        host="127.0.0.1", port=6007, thread_id=1, game_pid=5678,
    )
    result = runner.invoke(
        cli, ["--json", "debug", "connect", "--project", str(tmp_path)],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "connected"
    assert data["game_pid"] == 5678


@patch("auto_godot.commands.debug.async_connect", new_callable=AsyncMock)
def test_debug_connect_error_json_output(
    mock_connect: AsyncMock,
    runner: CliRunner,
    tmp_path: Path,
) -> None:
    """--json with error should produce JSON error on stderr."""
    mock_connect.side_effect = DebuggerConnectionError(
        message="Port in use",
        code="DEBUG_PORT_IN_USE",
        fix="Try another port",
    )
    result = runner.invoke(
        cli,
        ["--json", "debug", "connect", "--project", str(tmp_path)],
        catch_exceptions=False,
    )
    # emit_error calls ctx.exit(1), which raises SystemExit in CliRunner
    # CliRunner catches it and sets exit_code
    assert result.exit_code != 0
    # Error JSON goes to stderr; CliRunner merges it depending on mix_stderr
    # Check both output and stderr for the error
    error_text = result.output
    assert "DEBUG_PORT_IN_USE" in error_text or "Port in use" in error_text


@patch("auto_godot.commands.debug.async_connect", new_callable=AsyncMock)
def test_debug_connect_error_exit_code(
    mock_connect: AsyncMock,
    runner: CliRunner,
    tmp_path: Path,
) -> None:
    """Errors from async_connect should produce non-zero exit code."""
    mock_connect.side_effect = DebuggerError(
        message="Something went wrong",
        code="DEBUG_UNKNOWN",
        fix="Check logs",
    )
    result = runner.invoke(
        cli, ["debug", "connect", "--project", str(tmp_path)],
    )
    assert result.exit_code != 0


def test_debug_registered_in_cli() -> None:
    """The debug command group should be registered in the main CLI."""
    # cli.commands is a dict of registered command names
    assert "debug" in cli.commands
