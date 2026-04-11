"""Tests for project list-autoloads and remove-autoload commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal project.godot for testing."""
    project_godot = tmp_path / "project.godot"
    project_godot.write_text(
        'config_version=5\n'
        '\n'
        '[application]\n'
        '\n'
        'config/name="TestGame"\n',
        encoding="utf-8",
    )
    return project_godot


def _make_project_with_autoloads(tmp_path: Path) -> Path:
    """Create a project.godot with pre-existing autoload singletons."""
    project_godot = tmp_path / "project.godot"
    runner = CliRunner()
    project_godot.write_text(
        'config_version=5\n'
        '\n'
        '[application]\n'
        '\n'
        'config/name="TestGame"\n',
        encoding="utf-8",
    )
    runner.invoke(cli, [
        "project", "add-autoload",
        "--name", "GameManager",
        "--path", "res://scripts/autoload/game_manager.gd",
        str(tmp_path),
    ])
    runner.invoke(cli, [
        "project", "add-autoload",
        "--name", "AudioBus",
        "--path", "res://scripts/autoload/audio_bus.gd",
        str(tmp_path),
    ])
    return project_godot


# ---------------------------------------------------------------------------
# Tests for project list-autoloads
# ---------------------------------------------------------------------------


class TestListAutoloadsBasic:
    """Verify list-autoloads shows autoload singletons."""

    def test_list_empty(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "list-autoloads", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "No autoload singletons defined" in result.output

    def test_list_with_autoloads(self, tmp_path: Path) -> None:
        _make_project_with_autoloads(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "list-autoloads", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "GameManager" in result.output
        assert "AudioBus" in result.output

    def test_list_shows_paths(self, tmp_path: Path) -> None:
        _make_project_with_autoloads(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "list-autoloads", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "res://scripts/autoload/game_manager.gd" in result.output
        assert "res://scripts/autoload/audio_bus.gd" in result.output

    def test_list_shows_enabled(self, tmp_path: Path) -> None:
        _make_project_with_autoloads(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "list-autoloads", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "enabled" in result.output

    def test_list_no_project_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "list-autoloads", "/nonexistent/path",
        ])
        assert result.exit_code != 0

    def test_list_disabled_autoload(self, tmp_path: Path) -> None:
        """An autoload registered with --no-singleton shows disabled."""
        _make_project(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "project", "add-autoload",
            "--name", "Helper",
            "--path", "res://scripts/helper.gd",
            "--no-singleton",
            str(tmp_path),
        ])
        result = runner.invoke(cli, [
            "project", "list-autoloads", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "Helper" in result.output
        assert "disabled" in result.output


class TestListAutoloadsJson:
    """Verify JSON output for list-autoloads."""

    def test_json_empty(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "list-autoloads", str(tmp_path),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["autoloads"] == []
        assert data["count"] == 0

    def test_json_with_autoloads(self, tmp_path: Path) -> None:
        _make_project_with_autoloads(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "list-autoloads", str(tmp_path),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 2
        autoloads = {a["name"]: a for a in data["autoloads"]}
        assert "GameManager" in autoloads
        assert "AudioBus" in autoloads

    def test_json_autoload_structure(self, tmp_path: Path) -> None:
        _make_project_with_autoloads(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "list-autoloads", str(tmp_path),
        ])
        data = json.loads(result.output)
        autoloads = {a["name"]: a for a in data["autoloads"]}
        gm = autoloads["GameManager"]
        assert gm["path"] == "res://scripts/autoload/game_manager.gd"
        assert gm["enabled"] is True

    def test_json_disabled_autoload(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "project", "add-autoload",
            "--name", "Helper",
            "--path", "res://scripts/helper.gd",
            "--no-singleton",
            str(tmp_path),
        ])
        result = runner.invoke(cli, [
            "-j", "project", "list-autoloads", str(tmp_path),
        ])
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["autoloads"][0]["enabled"] is False


# ---------------------------------------------------------------------------
# Tests for project remove-autoload
# ---------------------------------------------------------------------------


class TestRemoveAutoloadBasic:
    """Verify remove-autoload deletes autoload singletons."""

    def test_remove_autoload(self, tmp_path: Path) -> None:
        _make_project_with_autoloads(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "remove-autoload",
            "--name", "AudioBus",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        assert "Removed" in result.output
        text = (tmp_path / "project.godot").read_text()
        assert "AudioBus=" not in text
        # GameManager should still be there
        assert "GameManager=" in text

    def test_remove_first_autoload(self, tmp_path: Path) -> None:
        _make_project_with_autoloads(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "remove-autoload",
            "--name", "GameManager",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = (tmp_path / "project.godot").read_text()
        assert "GameManager=" not in text
        assert "AudioBus=" in text

    def test_remove_nonexistent_error(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "remove-autoload",
            "--name", "NonExistent",
            str(tmp_path),
        ])
        assert result.exit_code != 0

    def test_remove_no_project_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "remove-autoload",
            "--name", "GameManager",
            "/nonexistent/path",
        ])
        assert result.exit_code != 0

    def test_remove_then_list_empty(self, tmp_path: Path) -> None:
        """After removing all autoloads, list-autoloads shows empty."""
        _make_project_with_autoloads(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "project", "remove-autoload", "--name", "GameManager",
            str(tmp_path),
        ])
        runner.invoke(cli, [
            "project", "remove-autoload", "--name", "AudioBus",
            str(tmp_path),
        ])
        result = runner.invoke(cli, [
            "-j", "project", "list-autoloads", str(tmp_path),
        ])
        data = json.loads(result.output)
        assert data["count"] == 0

    def test_remove_then_re_add(self, tmp_path: Path) -> None:
        """Can add an autoload back after removing it."""
        _make_project_with_autoloads(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "project", "remove-autoload", "--name", "AudioBus",
            str(tmp_path),
        ])
        result = runner.invoke(cli, [
            "project", "add-autoload",
            "--name", "AudioBus",
            "--path", "res://scripts/autoload/new_audio.gd",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "project.godot").read_text()
        assert "AudioBus=" in text
        assert "new_audio.gd" in text


class TestRemoveAutoloadJson:
    """Verify JSON output for remove-autoload."""

    def test_json_output(self, tmp_path: Path) -> None:
        _make_project_with_autoloads(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "remove-autoload",
            "--name", "AudioBus",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["removed"] is True
        assert data["name"] == "AudioBus"

    def test_json_error_not_found(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "remove-autoload",
            "--name", "NonExistent",
            str(tmp_path),
        ])
        assert result.exit_code != 0
