"""Tests for gdauto CLI entry point, error infrastructure, and output module."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

from click.testing import CliRunner

from gdauto.cli import cli
from gdauto.errors import (
    GdautoError,
    GodotBinaryError,
    ParseError,
    ProjectError,
    ResourceNotFoundError,
    ValidationError,
)
from gdauto.output import GlobalConfig, emit, emit_error


# ---------------------------------------------------------------------------
# CLI help and flag tests
# ---------------------------------------------------------------------------


class TestCLIHelp:
    """Verify --help shows all command groups and global flags are accepted."""

    def test_help_shows_command_groups(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        for group in ("project", "export", "sprite", "tileset", "scene", "resource"):
            assert group in result.output, f"Missing command group: {group}"

    def test_version(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "gdauto" in result.output.lower()

    def test_json_flag_accepted(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "--help"])
        assert result.exit_code == 0

    def test_verbose_flag_accepted(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-v", "--help"])
        assert result.exit_code == 0

    def test_quiet_flag_accepted(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-q", "--help"])
        assert result.exit_code == 0

    def test_no_color_flag_accepted(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--no-color", "--help"])
        assert result.exit_code == 0

    def test_godot_path_flag_accepted(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--godot-path", "/usr/bin/godot", "--help"])
        assert result.exit_code == 0

    def test_no_subcommand_shows_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "project" in result.output


# ---------------------------------------------------------------------------
# Error hierarchy tests
# ---------------------------------------------------------------------------


class TestErrorHierarchy:
    """Verify GdautoError and subclasses produce correct dict output."""

    def test_error_to_dict(self) -> None:
        err = GdautoError(message="test error", code="TEST_ERROR")
        d = err.to_dict()
        assert d == {"error": "test error", "code": "TEST_ERROR"}

    def test_error_to_dict_with_fix(self) -> None:
        err = GdautoError(message="missing file", code="FILE_NOT_FOUND", fix="check the path")
        d = err.to_dict()
        assert d["error"] == "missing file"
        assert d["code"] == "FILE_NOT_FOUND"
        assert d["fix"] == "check the path"

    def test_subclasses_inherit_to_dict(self) -> None:
        err = ParseError(message="bad format", code="PARSE_ERROR")
        assert isinstance(err, GdautoError)
        assert err.to_dict()["code"] == "PARSE_ERROR"

    def test_resource_not_found_error(self) -> None:
        err = ResourceNotFoundError(
            message="File not found: test.tres",
            code="RESOURCE_NOT_FOUND",
            fix="Verify the file path exists",
        )
        assert isinstance(err, GdautoError)
        assert err.to_dict()["fix"] == "Verify the file path exists"

    def test_godot_binary_error(self) -> None:
        err = GodotBinaryError(message="Godot not found", code="GODOT_NOT_FOUND")
        assert isinstance(err, GdautoError)

    def test_validation_error(self) -> None:
        err = ValidationError(message="invalid value", code="VALIDATION_ERROR")
        assert isinstance(err, GdautoError)

    def test_project_error(self) -> None:
        err = ProjectError(message="not a project", code="PROJECT_ERROR")
        assert isinstance(err, GdautoError)


# ---------------------------------------------------------------------------
# GlobalConfig tests
# ---------------------------------------------------------------------------


class TestGlobalConfig:
    """Verify GlobalConfig dataclass defaults."""

    def test_defaults(self) -> None:
        cfg = GlobalConfig()
        assert cfg.json_mode is False
        assert cfg.verbose is False
        assert cfg.quiet is False
        assert cfg.godot_path is None


# ---------------------------------------------------------------------------
# Output module tests
# ---------------------------------------------------------------------------


class TestEmit:
    """Verify emit() dispatches to JSON or human output correctly."""

    def test_emit_json_mode(self) -> None:
        import types

        ctx = types.SimpleNamespace()
        ctx.obj = GlobalConfig(json_mode=True)
        data = {"key": "value"}
        captured: list[str] = []

        def mock_human(d: dict, verbose: bool = False) -> None:  # type: ignore[type-arg]
            captured.append("human called")

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            emit(data, mock_human, ctx)  # type: ignore[arg-type]
            output = mock_stdout.getvalue()

        parsed = json.loads(output)
        assert parsed == {"key": "value"}
        assert "human called" not in captured

    def test_emit_human_mode(self) -> None:
        import types

        ctx = types.SimpleNamespace()
        ctx.obj = GlobalConfig(json_mode=False, verbose=True)
        data = {"key": "value"}
        called_with: list[tuple[dict, bool]] = []  # type: ignore[type-arg]

        def mock_human(d: dict, verbose: bool = False) -> None:  # type: ignore[type-arg]
            called_with.append((d, verbose))

        emit(data, mock_human, ctx)  # type: ignore[arg-type]
        assert len(called_with) == 1
        assert called_with[0] == ({"key": "value"}, True)

    def test_emit_quiet_mode_suppresses_human(self) -> None:
        import types

        ctx = types.SimpleNamespace()
        ctx.obj = GlobalConfig(json_mode=False, quiet=True)
        data = {"key": "value"}
        called: list[bool] = []

        def mock_human(d: dict, verbose: bool = False) -> None:  # type: ignore[type-arg]
            called.append(True)

        emit(data, mock_human, ctx)  # type: ignore[arg-type]
        assert len(called) == 0


class TestEmitError:
    """Verify emit_error() outputs JSON or human errors correctly."""

    def test_emit_error_json_mode(self) -> None:
        import types

        ctx = types.SimpleNamespace()
        ctx.obj = GlobalConfig(json_mode=True)
        exit_called_with: list[int] = []
        ctx.exit = lambda code: exit_called_with.append(code)

        err = GdautoError(message="something broke", code="BROKE")

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            emit_error(err, ctx)  # type: ignore[arg-type]
            output = mock_stderr.getvalue()

        parsed = json.loads(output)
        assert parsed["error"] == "something broke"
        assert parsed["code"] == "BROKE"
        assert exit_called_with == [1]

    def test_emit_error_human_mode_with_fix(self) -> None:
        import types

        ctx = types.SimpleNamespace()
        ctx.obj = GlobalConfig(json_mode=False)
        exit_called_with: list[int] = []
        ctx.exit = lambda code: exit_called_with.append(code)

        err = GdautoError(message="file missing", code="NOT_FOUND", fix="check the path")

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            emit_error(err, ctx)  # type: ignore[arg-type]
            output = mock_stderr.getvalue()

        assert "file missing" in output
        assert "check the path" in output
        assert exit_called_with == [1]
