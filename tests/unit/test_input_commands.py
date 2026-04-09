"""Tests for project add-input command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gdauto.cli import cli


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


class TestAddInputBasic:
    """Verify add-input creates input actions in project.godot."""

    def test_add_single_key(self, tmp_path: Path) -> None:
        project_godot = _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-input",
            "--action", "move_up", "--key", "w",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = project_godot.read_text()
        assert "[input]" in text
        assert "move_up=" in text
        assert "InputEventKey" in text
        assert '"physical_keycode":87' in text

    def test_add_multiple_keys(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-input",
            "--action", "move_up", "--key", "w", "--key", "up",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = (tmp_path / "project.godot").read_text()
        assert '"physical_keycode":87' in text
        assert '"physical_keycode":4194320' in text

    def test_add_mouse_button(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-input",
            "--action", "shoot", "--mouse", "left",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = (tmp_path / "project.godot").read_text()
        assert "InputEventMouseButton" in text
        assert '"button_index":1' in text

    def test_add_joypad_button(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-input",
            "--action", "jump", "--joypad", "a",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = (tmp_path / "project.godot").read_text()
        assert "InputEventJoypadButton" in text
        assert '"button_index":0' in text

    def test_add_mixed_bindings(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-input",
            "--action", "attack",
            "--key", "space",
            "--mouse", "left",
            "--joypad", "x",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = (tmp_path / "project.godot").read_text()
        assert "InputEventKey" in text
        assert "InputEventMouseButton" in text
        assert "InputEventJoypadButton" in text


class TestAddInputJson:
    """Verify JSON output mode for add-input."""

    def test_json_output(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "add-input",
            "--action", "jump", "--key", "space",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["action"] == "jump"
        assert data["keys"] == ["space"]
        assert data["event_count"] == 1

    def test_json_mixed_bindings(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "add-input",
            "--action", "fire",
            "--key", "f", "--mouse", "left",
            str(tmp_path),
        ])
        data = json.loads(result.output)
        assert data["event_count"] == 2
        assert data["keys"] == ["f"]
        assert data["mouse_buttons"] == ["left"]


class TestAddInputErrors:
    """Verify error handling for add-input."""

    def test_no_bindings_error(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-input",
            "--action", "empty",
            str(tmp_path),
        ])
        assert result.exit_code != 0

    def test_duplicate_action_error(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "project", "add-input",
            "--action", "jump", "--key", "space",
            str(tmp_path),
        ])
        result = runner.invoke(cli, [
            "project", "add-input",
            "--action", "jump", "--key", "w",
            str(tmp_path),
        ])
        assert result.exit_code != 0

    def test_invalid_key_error(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-input",
            "--action", "bad", "--key", "nonexistent_key",
            str(tmp_path),
        ])
        assert result.exit_code != 0

    def test_invalid_mouse_error(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-input",
            "--action", "bad", "--mouse", "invalid",
            str(tmp_path),
        ])
        assert result.exit_code != 0

    def test_invalid_joypad_error(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-input",
            "--action", "bad", "--joypad", "invalid",
            str(tmp_path),
        ])
        assert result.exit_code != 0

    def test_no_project_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-input",
            "--action", "jump", "--key", "space",
            "/nonexistent/path",
        ])
        assert result.exit_code != 0


class TestAddInputDeadzone:
    """Verify deadzone configuration."""

    def test_default_deadzone(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "project", "add-input",
            "--action", "move", "--key", "w",
            str(tmp_path),
        ])
        text = (tmp_path / "project.godot").read_text()
        assert '"deadzone": 0.2' in text

    def test_custom_deadzone(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "project", "add-input",
            "--action", "move", "--key", "w",
            "--deadzone", "0.5",
            str(tmp_path),
        ])
        text = (tmp_path / "project.godot").read_text()
        assert '"deadzone": 0.5' in text


class TestAddInputMultipleActions:
    """Verify adding multiple input actions."""

    def test_add_two_actions(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "project", "add-input",
            "--action", "move_up", "--key", "w",
            str(tmp_path),
        ])
        result = runner.invoke(cli, [
            "project", "add-input",
            "--action", "move_down", "--key", "s",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "project.godot").read_text()
        assert "move_up=" in text
        assert "move_down=" in text

    def test_wasd_setup(self, tmp_path: Path) -> None:
        """Full WASD binding test: the most common game input setup."""
        _make_project(tmp_path)
        runner = CliRunner()
        actions = [
            ("move_up", "w"), ("move_down", "s"),
            ("move_left", "a"), ("move_right", "d"),
        ]
        for action, key in actions:
            result = runner.invoke(cli, [
                "project", "add-input",
                "--action", action, "--key", key,
                str(tmp_path),
            ])
            assert result.exit_code == 0, f"Failed for {action}: {result.output}"

        text = (tmp_path / "project.godot").read_text()
        for action, _ in actions:
            assert f"{action}=" in text


class TestAddInputKeyNames:
    """Verify all supported key names resolve correctly."""

    def test_letter_keys(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        for letter in "wasd":
            result = runner.invoke(cli, [
                "project", "add-input",
                "--action", f"test_{letter}", "--key", letter,
                str(tmp_path),
            ])
            assert result.exit_code == 0, f"Failed for key '{letter}': {result.output}"

    def test_special_keys(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        for key in ("space", "escape", "enter", "tab", "backspace"):
            result = runner.invoke(cli, [
                "project", "add-input",
                "--action", f"test_{key}", "--key", key,
                str(tmp_path),
            ])
            assert result.exit_code == 0, f"Failed for key '{key}': {result.output}"

    def test_arrow_keys(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        for key in ("up", "down", "left", "right"):
            result = runner.invoke(cli, [
                "project", "add-input",
                "--action", f"test_{key}", "--key", key,
                str(tmp_path),
            ])
            assert result.exit_code == 0, f"Failed for key '{key}': {result.output}"

    def test_function_keys(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        for i in range(1, 13):
            result = runner.invoke(cli, [
                "project", "add-input",
                "--action", f"test_f{i}", "--key", f"f{i}",
                str(tmp_path),
            ])
            assert result.exit_code == 0, f"Failed for key 'f{i}': {result.output}"
