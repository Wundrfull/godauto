"""Tests for project add-input command."""

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


# ---------------------------------------------------------------------------
# Tests for project list-inputs
# ---------------------------------------------------------------------------


def _make_project_with_inputs(tmp_path: Path) -> Path:
    """Create a project.godot with pre-existing input actions."""
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
        "project", "add-input",
        "--action", "move_up", "--key", "w", "--key", "up",
        str(tmp_path),
    ])
    runner.invoke(cli, [
        "project", "add-input",
        "--action", "jump", "--key", "space", "--joypad", "a",
        str(tmp_path),
    ])
    return project_godot


class TestListInputsBasic:
    """Verify list-inputs shows input actions."""

    def test_list_empty(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "list-inputs", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "No input actions defined" in result.output

    def test_list_with_actions(self, tmp_path: Path) -> None:
        _make_project_with_inputs(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "list-inputs", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "move_up" in result.output
        assert "jump" in result.output

    def test_list_shows_key_names(self, tmp_path: Path) -> None:
        _make_project_with_inputs(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "list-inputs", str(tmp_path),
        ])
        assert result.exit_code == 0
        # move_up is bound to w and up
        assert "w" in result.output
        assert "up" in result.output

    def test_list_shows_joypad(self, tmp_path: Path) -> None:
        _make_project_with_inputs(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "list-inputs", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "joypad" in result.output

    def test_list_no_project_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "list-inputs", "/nonexistent/path",
        ])
        assert result.exit_code != 0


class TestListInputsJson:
    """Verify JSON output for list-inputs."""

    def test_json_empty(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "list-inputs", str(tmp_path),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["actions"] == []
        assert data["count"] == 0

    def test_json_with_actions(self, tmp_path: Path) -> None:
        _make_project_with_inputs(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "list-inputs", str(tmp_path),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 2
        actions = {a["action"]: a for a in data["actions"]}
        assert "move_up" in actions
        assert "jump" in actions

    def test_json_binding_structure(self, tmp_path: Path) -> None:
        _make_project_with_inputs(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "list-inputs", str(tmp_path),
        ])
        data = json.loads(result.output)
        actions = {a["action"]: a for a in data["actions"]}
        # move_up has two key bindings (w, up)
        move_up_bindings = actions["move_up"]["bindings"]
        assert len(move_up_bindings) == 2
        assert all(b["type"] == "key" for b in move_up_bindings)
        # jump has one key + one joypad
        jump_bindings = actions["jump"]["bindings"]
        assert len(jump_bindings) == 2
        types = {b["type"] for b in jump_bindings}
        assert "key" in types
        assert "joypad" in types


# ---------------------------------------------------------------------------
# Tests for project remove-input
# ---------------------------------------------------------------------------


class TestRemoveInputBasic:
    """Verify remove-input deletes input actions."""

    def test_remove_action(self, tmp_path: Path) -> None:
        _make_project_with_inputs(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "remove-input",
            "--action", "jump",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        assert "Removed" in result.output
        text = (tmp_path / "project.godot").read_text()
        assert "jump=" not in text
        # move_up should still be there
        assert "move_up=" in text

    def test_remove_first_action(self, tmp_path: Path) -> None:
        _make_project_with_inputs(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "remove-input",
            "--action", "move_up",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = (tmp_path / "project.godot").read_text()
        assert "move_up=" not in text
        assert "jump=" in text

    def test_remove_nonexistent_error(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "remove-input",
            "--action", "nonexistent",
            str(tmp_path),
        ])
        assert result.exit_code != 0

    def test_remove_no_project_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "remove-input",
            "--action", "jump",
            "/nonexistent/path",
        ])
        assert result.exit_code != 0

    def test_remove_then_list_empty(self, tmp_path: Path) -> None:
        """After removing all actions, list-inputs shows empty."""
        _make_project_with_inputs(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "project", "remove-input", "--action", "move_up",
            str(tmp_path),
        ])
        runner.invoke(cli, [
            "project", "remove-input", "--action", "jump",
            str(tmp_path),
        ])
        result = runner.invoke(cli, [
            "-j", "project", "list-inputs", str(tmp_path),
        ])
        data = json.loads(result.output)
        assert data["count"] == 0

    def test_remove_then_re_add(self, tmp_path: Path) -> None:
        """Can add an action back after removing it."""
        _make_project_with_inputs(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "project", "remove-input", "--action", "jump",
            str(tmp_path),
        ])
        result = runner.invoke(cli, [
            "project", "add-input",
            "--action", "jump", "--key", "enter",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "project.godot").read_text()
        assert "jump=" in text


class TestRemoveInputJson:
    """Verify JSON output for remove-input."""

    def test_json_output(self, tmp_path: Path) -> None:
        _make_project_with_inputs(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "remove-input",
            "--action", "jump",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["removed"] is True
        assert data["action"] == "jump"

    def test_json_error_not_found(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "remove-input",
            "--action", "nonexistent",
            str(tmp_path),
        ])
        assert result.exit_code != 0
