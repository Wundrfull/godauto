"""Tests for --dry-run global flag."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_SCENE_DEF = str(FIXTURES_DIR / "scene_definition.json")

SAMPLE_TSCN = """\
[gd_scene format=3]

[node name="Root" type="Node2D"]
"""


class TestDryRunSceneCreate:
    """--dry-run should skip file writes for scene create commands."""

    def test_create_simple_no_file_written(self, tmp_path: Path) -> None:
        out = tmp_path / "level.tscn"
        result = CliRunner().invoke(cli, [
            "--dry-run", "scene", "create-simple",
            "--root-type", "Node2D", "--root-name", "Level",
            "-o", str(out),
        ])
        assert result.exit_code == 0, result.output
        assert not out.exists(), "File should not be created in dry-run mode"
        assert "[dry-run]" in result.output

    def test_create_simple_still_emits_output(self, tmp_path: Path) -> None:
        out = tmp_path / "level.tscn"
        result = CliRunner().invoke(cli, [
            "--dry-run", "scene", "create-simple",
            "--root-type", "Node2D", "--root-name", "Level",
            "-o", str(out),
        ])
        assert result.exit_code == 0
        assert "Created scene" in result.output

    def test_create_simple_json_output(self, tmp_path: Path) -> None:
        out = tmp_path / "level.tscn"
        result = CliRunner().invoke(cli, [
            "--dry-run", "-j", "scene", "create-simple",
            "--root-type", "Node2D", "--root-name", "Level",
            "-o", str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["root_type"] == "Node2D"
        assert not out.exists()

    def test_create_from_json_no_file_written(self, tmp_path: Path) -> None:
        out = tmp_path / "scene.tscn"
        result = CliRunner().invoke(cli, [
            "--dry-run", "scene", "create", FIXTURE_SCENE_DEF,
            "-o", str(out),
        ])
        assert result.exit_code == 0, result.output
        assert not out.exists()
        assert "[dry-run]" in result.output


class TestDryRunSceneModify:
    """--dry-run should skip file writes for scene modification commands."""

    def test_add_node_no_write(self, tmp_path: Path) -> None:
        scene_file = tmp_path / "test.tscn"
        scene_file.write_text(SAMPLE_TSCN)
        original = scene_file.read_text()

        result = CliRunner().invoke(cli, [
            "--dry-run", "scene", "add-node",
            "--scene", str(scene_file),
            "--name", "Timer", "--type", "Timer",
        ])
        assert result.exit_code == 0, result.output
        assert scene_file.read_text() == original, "File should not be modified"
        assert "[dry-run]" in result.output

    def test_add_node_still_emits_data(self, tmp_path: Path) -> None:
        scene_file = tmp_path / "test.tscn"
        scene_file.write_text(SAMPLE_TSCN)

        result = CliRunner().invoke(cli, [
            "--dry-run", "-j", "scene", "add-node",
            "--scene", str(scene_file),
            "--name", "Timer", "--type", "Timer",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["name"] == "Timer"

    def test_set_property_no_write(self, tmp_path: Path) -> None:
        scene_file = tmp_path / "test.tscn"
        scene_file.write_text(SAMPLE_TSCN)
        original = scene_file.read_text()

        result = CliRunner().invoke(cli, [
            "--dry-run", "scene", "set-property",
            "--scene", str(scene_file),
            "--node", "Root", "--property", "visible=false",
        ])
        assert result.exit_code == 0, result.output
        assert scene_file.read_text() == original

    def test_remove_node_no_write(self, tmp_path: Path) -> None:
        tscn = (
            '[gd_scene format=3]\n\n'
            '[node name="Root" type="Node2D"]\n\n'
            '[node name="Child" type="Sprite2D" parent="."]\n'
        )
        scene_file = tmp_path / "test.tscn"
        scene_file.write_text(tscn)
        original = scene_file.read_text()

        result = CliRunner().invoke(cli, [
            "--dry-run", "scene", "remove-node",
            "--scene", str(scene_file),
            "--name", "Child",
        ])
        assert result.exit_code == 0, result.output
        assert scene_file.read_text() == original


class TestDryRunWithoutFlag:
    """Normal operation (no --dry-run) should still write files."""

    def test_create_simple_writes_normally(self, tmp_path: Path) -> None:
        out = tmp_path / "level.tscn"
        result = CliRunner().invoke(cli, [
            "scene", "create-simple",
            "--root-type", "Node2D", "--root-name", "Level",
            "-o", str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()
        assert "Node2D" in out.read_text()


class TestDryRunSafetyGuard:
    """Unsupported commands must warn users that --dry-run had no effect."""

    def test_unsupported_command_emits_warning(self, tmp_path: Path) -> None:
        """script create does not yet honor --dry-run, so warning must fire."""
        out = tmp_path / "test.gd"
        result = CliRunner().invoke(cli, [
            "--dry-run", "script", "create",
            "--extends", "Node", str(out),
        ])
        # Warning fired because script create still writes directly.
        assert "--dry-run is not yet implemented" in result.output
        assert "Files may have been written" in result.output

    def test_supported_command_no_warning(self, tmp_path: Path) -> None:
        """scene create-simple honors --dry-run, so no warning."""
        out = tmp_path / "level.tscn"
        result = CliRunner().invoke(cli, [
            "--dry-run", "scene", "create-simple",
            "--root-type", "Node2D", "--root-name", "Level",
            "-o", str(out),
        ])
        assert result.exit_code == 0
        assert "--dry-run is not yet implemented" not in result.output

    def test_no_warning_without_dry_run(self, tmp_path: Path) -> None:
        """Warning must not fire when --dry-run was not passed."""
        out = tmp_path / "test.gd"
        result = CliRunner().invoke(cli, [
            "script", "create", "--extends", "Node", str(out),
        ])
        assert "--dry-run is not yet implemented" not in result.output
