"""Tests for export CLI commands and root-level import command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from gdauto.cli import cli
from gdauto.errors import GdautoError, GodotBinaryError
from gdauto.output import GlobalConfig


@pytest.fixture()
def runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture()
def mock_backend() -> MagicMock:
    """Create a mock GodotBackend."""
    backend = MagicMock()
    backend.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    backend.import_resources.return_value = MagicMock(returncode=0)
    return backend


# ---------------------------------------------------------------------------
# export release tests
# ---------------------------------------------------------------------------


class TestExportRelease:
    """Tests for the export release CLI command."""

    def test_release_invokes_with_correct_flag(
        self, runner: CliRunner, mock_backend: MagicMock, tmp_path: Path
    ) -> None:
        """export release calls backend.run with --export-release flag."""
        # Create import cache to skip auto-import
        (tmp_path / ".godot" / "imported").mkdir(parents=True)

        with patch("gdauto.commands.export.GodotBackend", return_value=mock_backend):
            result = runner.invoke(
                cli,
                ["export", "release", "MyPreset", "-o", "game.exe",
                 "--project", str(tmp_path)],
            )

        assert result.exit_code == 0
        mock_backend.run.assert_called_once()
        args = mock_backend.run.call_args
        assert args[0][0][0] == "--export-release"
        assert args[0][0][1] == "MyPreset"

    def test_release_json_output(
        self, runner: CliRunner, mock_backend: MagicMock, tmp_path: Path
    ) -> None:
        """export release --json produces JSON output."""
        (tmp_path / ".godot" / "imported").mkdir(parents=True)

        with patch("gdauto.commands.export.GodotBackend", return_value=mock_backend):
            result = runner.invoke(
                cli,
                ["--json", "export", "release", "MyPreset", "-o", "game.exe",
                 "--project", str(tmp_path)],
            )

        assert result.exit_code == 0
        assert '"mode": "release"' in result.output
        assert '"preset": "MyPreset"' in result.output


# ---------------------------------------------------------------------------
# export debug tests
# ---------------------------------------------------------------------------


class TestExportDebug:
    """Tests for the export debug CLI command."""

    def test_debug_invokes_with_correct_flag(
        self, runner: CliRunner, mock_backend: MagicMock, tmp_path: Path
    ) -> None:
        """export debug calls backend.run with --export-debug flag."""
        (tmp_path / ".godot" / "imported").mkdir(parents=True)

        with patch("gdauto.commands.export.GodotBackend", return_value=mock_backend):
            result = runner.invoke(
                cli,
                ["export", "debug", "MyPreset", "-o", "game.exe",
                 "--project", str(tmp_path)],
            )

        assert result.exit_code == 0
        mock_backend.run.assert_called_once()
        args = mock_backend.run.call_args
        assert args[0][0][0] == "--export-debug"


# ---------------------------------------------------------------------------
# export pack tests
# ---------------------------------------------------------------------------


class TestExportPack:
    """Tests for the export pack CLI command."""

    def test_pack_invokes_with_correct_flag(
        self, runner: CliRunner, mock_backend: MagicMock, tmp_path: Path
    ) -> None:
        """export pack calls backend.run with --export-pack flag."""
        (tmp_path / ".godot" / "imported").mkdir(parents=True)

        with patch("gdauto.commands.export.GodotBackend", return_value=mock_backend):
            result = runner.invoke(
                cli,
                ["export", "pack", "MyPreset", "-o", "game.pck",
                 "--project", str(tmp_path)],
            )

        assert result.exit_code == 0
        mock_backend.run.assert_called_once()
        args = mock_backend.run.call_args
        assert args[0][0][0] == "--export-pack"


# ---------------------------------------------------------------------------
# --no-import tests
# ---------------------------------------------------------------------------


class TestNoImportFlag:
    """Tests for the --no-import flag."""

    def test_no_import_skips_auto_import(
        self, runner: CliRunner, mock_backend: MagicMock, tmp_path: Path
    ) -> None:
        """export release --no-import skips auto-import even if cache is missing."""
        with patch("gdauto.commands.export.GodotBackend", return_value=mock_backend):
            result = runner.invoke(
                cli,
                ["export", "release", "MyPreset", "-o", "game.exe",
                 "--project", str(tmp_path), "--no-import"],
            )

        assert result.exit_code == 0
        mock_backend.import_resources.assert_not_called()


# ---------------------------------------------------------------------------
# import command tests
# ---------------------------------------------------------------------------


class TestImportCommand:
    """Tests for the root-level import command."""

    def test_import_command_exists(self, runner: CliRunner) -> None:
        """gdauto import --help should work."""
        result = runner.invoke(cli, ["import", "--help"])
        assert result.exit_code == 0
        assert "--project" in result.output
        assert "--max-retries" in result.output

    def test_import_calls_import_with_retry(
        self, runner: CliRunner, mock_backend: MagicMock
    ) -> None:
        """import command with mocked backend calls import_with_retry."""
        with patch("gdauto.cli.GodotBackend", return_value=mock_backend):
            with patch("gdauto.cli.import_with_retry") as mock_retry:
                result = runner.invoke(
                    cli, ["import", "--project", "."]
                )

        assert result.exit_code == 0
        mock_retry.assert_called_once()

    def test_import_passes_max_retries(
        self, runner: CliRunner, mock_backend: MagicMock
    ) -> None:
        """import command passes --max-retries to import_with_retry."""
        with patch("gdauto.cli.GodotBackend", return_value=mock_backend):
            with patch("gdauto.cli.import_with_retry") as mock_retry:
                result = runner.invoke(
                    cli, ["import", "--max-retries", "5"]
                )

        assert result.exit_code == 0
        call_kwargs = mock_retry.call_args
        assert call_kwargs[1]["max_retries"] == 5 or call_kwargs.kwargs["max_retries"] == 5


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling in export commands."""

    def test_godot_binary_error_produces_error_output(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """GodotBinaryError produces proper error output."""
        mock_backend = MagicMock()
        mock_backend.run.side_effect = GodotBinaryError(
            message="Godot binary not found",
            code="GODOT_NOT_FOUND",
            fix="Install Godot 4.5+",
        )
        (tmp_path / ".godot" / "imported").mkdir(parents=True)

        with patch("gdauto.commands.export.GodotBackend", return_value=mock_backend):
            result = runner.invoke(
                cli,
                ["export", "release", "MyPreset", "-o", "game.exe",
                 "--project", str(tmp_path)],
            )

        assert result.exit_code == 1

    def test_import_error_produces_error_output(
        self, runner: CliRunner
    ) -> None:
        """GodotBinaryError in import command produces proper error output."""
        mock_backend = MagicMock()

        with patch("gdauto.cli.GodotBackend", return_value=mock_backend):
            with patch(
                "gdauto.cli.import_with_retry",
                side_effect=GodotBinaryError(
                    message="Godot not found",
                    code="GODOT_NOT_FOUND",
                    fix="Install Godot",
                ),
            ):
                result = runner.invoke(cli, ["import"])

        assert result.exit_code == 1
