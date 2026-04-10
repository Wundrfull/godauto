"""Tests for debug pause, resume, step, speed CLI commands (Phase 8 Plan 03)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from auto_godot.cli import cli
from auto_godot.debugger.errors import DebuggerError
from auto_godot.debugger.models import GameState


@pytest.fixture()
def runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


# ---------------------------------------------------------------------------
# debug pause
# ---------------------------------------------------------------------------


class TestDebugPause:
    """Tests for the debug pause CLI command."""

    def test_help_shows_options(self, runner: CliRunner) -> None:
        """debug pause --help shows --project, --port, --timeout."""
        result = runner.invoke(cli, ["debug", "pause", "--help"])
        assert result.exit_code == 0
        assert "--project" in result.output
        assert "--port" in result.output
        assert "--timeout" in result.output

    @patch("auto_godot.commands.debug._run_with_session", new_callable=AsyncMock)
    def test_json_output(
        self,
        mock_run: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """--json debug pause returns GameState JSON with paused=true."""
        mock_run.return_value = GameState(paused=True, speed=1.0, frame=0)
        result = runner.invoke(
            cli, ["--json", "debug", "pause", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["paused"] is True
        assert data["speed"] == 1.0
        assert data["frame"] == 0

    @patch("auto_godot.commands.debug._run_with_session", new_callable=AsyncMock)
    def test_human_output(
        self,
        mock_run: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Human mode prints 'Game paused (speed: 1.0x)'."""
        mock_run.return_value = GameState(paused=True, speed=1.0, frame=0)
        result = runner.invoke(
            cli, ["debug", "pause", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "Game paused" in result.output
        assert "1.0x" in result.output

    @patch("auto_godot.commands.debug._run_with_session", new_callable=AsyncMock)
    def test_error_exit_code(
        self,
        mock_run: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Error during pause produces non-zero exit."""
        mock_run.side_effect = DebuggerError(
            message="Not connected", code="DEBUG_ERROR", fix="Connect first",
        )
        result = runner.invoke(
            cli, ["debug", "pause", "--project", str(tmp_path)],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# debug resume
# ---------------------------------------------------------------------------


class TestDebugResume:
    """Tests for the debug resume CLI command."""

    def test_help_shows_options(self, runner: CliRunner) -> None:
        """debug resume --help shows --project, --port, --timeout."""
        result = runner.invoke(cli, ["debug", "resume", "--help"])
        assert result.exit_code == 0
        assert "--project" in result.output
        assert "--port" in result.output
        assert "--timeout" in result.output

    @patch("auto_godot.commands.debug._run_with_session", new_callable=AsyncMock)
    def test_json_output(
        self,
        mock_run: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """--json debug resume returns GameState JSON with paused=false."""
        mock_run.return_value = GameState(paused=False, speed=1.0, frame=0)
        result = runner.invoke(
            cli, ["--json", "debug", "resume", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["paused"] is False

    @patch("auto_godot.commands.debug._run_with_session", new_callable=AsyncMock)
    def test_human_output(
        self,
        mock_run: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Human mode prints 'Game resumed (speed: 1.0x)'."""
        mock_run.return_value = GameState(paused=False, speed=1.0, frame=0)
        result = runner.invoke(
            cli, ["debug", "resume", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "Game resumed" in result.output
        assert "1.0x" in result.output


# ---------------------------------------------------------------------------
# debug step
# ---------------------------------------------------------------------------


class TestDebugStep:
    """Tests for the debug step CLI command."""

    def test_help_shows_options(self, runner: CliRunner) -> None:
        """debug step --help shows --project, --port, --timeout."""
        result = runner.invoke(cli, ["debug", "step", "--help"])
        assert result.exit_code == 0
        assert "--project" in result.output
        assert "--port" in result.output
        assert "--timeout" in result.output

    @patch("auto_godot.commands.debug._run_with_session", new_callable=AsyncMock)
    def test_json_output(
        self,
        mock_run: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """--json debug step returns GameState JSON with paused=true."""
        mock_run.return_value = GameState(paused=True, speed=1.0, frame=0)
        result = runner.invoke(
            cli, ["--json", "debug", "step", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["paused"] is True

    @patch("auto_godot.commands.debug._run_with_session", new_callable=AsyncMock)
    def test_human_output(
        self,
        mock_run: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Human mode prints 'Stepped one frame'."""
        mock_run.return_value = GameState(paused=True, speed=1.0, frame=0)
        result = runner.invoke(
            cli, ["debug", "step", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "Stepped one frame" in result.output
        assert "1.0x" in result.output


# ---------------------------------------------------------------------------
# debug speed
# ---------------------------------------------------------------------------


class TestDebugSpeed:
    """Tests for the debug speed CLI command."""

    def test_help_shows_multiplier(self, runner: CliRunner) -> None:
        """debug speed --help shows MULTIPLIER and --project."""
        result = runner.invoke(cli, ["debug", "speed", "--help"])
        assert result.exit_code == 0
        assert "MULTIPLIER" in result.output
        assert "--project" in result.output
        assert "--port" in result.output
        assert "--timeout" in result.output

    @patch("auto_godot.commands.debug._run_with_session", new_callable=AsyncMock)
    def test_set_speed_json(
        self,
        mock_run: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """--json debug speed 10 returns GameState with speed=10.0."""
        mock_run.return_value = GameState(paused=False, speed=10.0, frame=0)
        result = runner.invoke(
            cli,
            ["--json", "debug", "speed", "10", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["speed"] == 10.0
        assert data["paused"] is False

    @patch("auto_godot.commands.debug._run_with_session", new_callable=AsyncMock)
    def test_set_speed_human(
        self,
        mock_run: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Human mode prints 'Speed set to 10.0x'."""
        mock_run.return_value = GameState(paused=False, speed=10.0, frame=0)
        result = runner.invoke(
            cli,
            ["debug", "speed", "10", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "Speed set to 10.0x" in result.output

    @patch("auto_godot.commands.debug._run_with_session", new_callable=AsyncMock)
    def test_query_speed_json(
        self,
        mock_run: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """debug speed with no arg returns current speed."""
        mock_run.return_value = GameState(paused=False, speed=1.0, frame=0)
        result = runner.invoke(
            cli,
            ["--json", "debug", "speed", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["speed"] == 1.0

    @patch("auto_godot.commands.debug._run_with_session", new_callable=AsyncMock)
    def test_query_speed_human(
        self,
        mock_run: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Human mode without arg prints 'Current speed: 1.0x'."""
        mock_run.return_value = GameState(paused=False, speed=1.0, frame=0)
        result = runner.invoke(
            cli,
            ["debug", "speed", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "Current speed: 1.0x" in result.output

    @patch("auto_godot.commands.debug._run_with_session", new_callable=AsyncMock)
    def test_invalid_speed_error(
        self,
        mock_run: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """debug speed 0 returns error with DEBUG_INVALID_SPEED."""
        mock_run.side_effect = DebuggerError(
            message="Speed multiplier must be positive, got 0.0",
            code="DEBUG_INVALID_SPEED",
            fix="Use a positive number",
        )
        result = runner.invoke(
            cli,
            ["debug", "speed", "0", "--project", str(tmp_path)],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Command registration
# ---------------------------------------------------------------------------


class TestExecCommandRegistration:
    """Verify all four execution commands are registered."""

    def test_pause_registered(self) -> None:
        """pause command is registered in the debug group."""
        from auto_godot.commands.debug import debug
        assert "pause" in debug.commands

    def test_resume_registered(self) -> None:
        """resume command is registered in the debug group."""
        from auto_godot.commands.debug import debug
        assert "resume" in debug.commands

    def test_step_registered(self) -> None:
        """step command is registered in the debug group."""
        from auto_godot.commands.debug import debug
        assert "step" in debug.commands

    def test_speed_registered(self) -> None:
        """speed command is registered in the debug group."""
        from auto_godot.commands.debug import debug
        assert "speed" in debug.commands
