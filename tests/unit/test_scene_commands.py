"""Tests for scene list and scene create CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_SCENE_DEF = str(FIXTURES_DIR / "scene_definition.json")

SAMPLE_TSCN = """\
[gd_scene load_steps=2 format=3 uid="uid://btk3example123"]

[ext_resource type="Script" uid="uid://c7gn4example" path="res://scripts/player.gd" id="1_script"]

[node name="Player" type="CharacterBody2D"]
script = ExtResource("1_script")

[node name="Sprite" type="Sprite2D" parent="."]
position = Vector2(0, 0)

[node name="CollisionShape" type="CollisionShape2D" parent="."]
"""

MINIMAL_PROJECT_GODOT = (
    "; Engine configuration file.\n"
    "config_version=5\n"
    "[application]\n"
    'config/name="TestProject"\n'
)


def _setup_project(tmp_path: Path, scenes: dict[str, str] | None = None) -> Path:
    """Create a minimal Godot project with optional scene files."""
    (tmp_path / "project.godot").write_text(MINIMAL_PROJECT_GODOT)
    if scenes:
        for name, content in scenes.items():
            scene_path = tmp_path / name
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            scene_path.write_text(content)
    return tmp_path


class TestSceneCreateFromJson:
    """Tests for scene create subcommand."""

    def test_scene_create_from_json(self, tmp_path: Path) -> None:
        output = tmp_path / "level.tscn"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["scene", "create", FIXTURE_SCENE_DEF, "-o", str(output)],
        )
        assert result.exit_code == 0, result.output
        assert output.exists()
        content = output.read_text()
        assert "[gd_scene" in content
        assert '[node name="Level"' in content
        assert '[node name="Player"' in content
        assert 'parent="."' in content

    def test_scene_create_custom_output(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom_output.tscn"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["scene", "create", FIXTURE_SCENE_DEF, "-o", str(custom)],
        )
        assert result.exit_code == 0, result.output
        assert custom.exists()

    def test_scene_create_json_output(self, tmp_path: Path) -> None:
        output = tmp_path / "level.tscn"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["-j", "scene", "create", FIXTURE_SCENE_DEF, "-o", str(output)],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "path" in data
        assert "nodes" in data

    def test_scene_create_file_not_found(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["scene", "create", "nonexistent.json"],
        )
        assert result.exit_code != 0
        # Check stderr for error code
        combined = (result.output or "") + (result.stderr or "")
        assert "FILE_NOT_FOUND" in combined or "not found" in combined.lower()

    def test_scene_create_invalid_json(self, tmp_path: Path) -> None:
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("not json{")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["scene", "create", str(bad_json)],
        )
        assert result.exit_code != 0
        combined = (result.output or "") + (result.stderr or "")
        assert "INVALID_JSON" in combined or "Invalid JSON" in combined

    def test_scene_create_missing_root(self, tmp_path: Path) -> None:
        no_root = tmp_path / "no_root.json"
        no_root.write_text('{"other": {}}')
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["scene", "create", str(no_root)],
        )
        assert result.exit_code != 0
        combined = (result.output or "") + (result.stderr or "")
        assert "INVALID_SCENE_DEFINITION" in combined or "missing" in combined.lower()

    def test_scene_create_uid_file_written(self, tmp_path: Path) -> None:
        output = tmp_path / "level.tscn"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["scene", "create", FIXTURE_SCENE_DEF, "-o", str(output)],
        )
        assert result.exit_code == 0, result.output
        uid_file = Path(str(output) + ".uid")
        assert uid_file.exists()

    def test_scene_create_properties_passthrough(self, tmp_path: Path) -> None:
        defn = tmp_path / "props.json"
        defn.write_text(json.dumps({
            "root": {
                "name": "Root",
                "type": "Node2D",
                "properties": {"position": "Vector2(50, 75)"},
            },
        }))
        output = tmp_path / "props.tscn"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["scene", "create", str(defn), "-o", str(output)],
        )
        assert result.exit_code == 0, result.output
        content = output.read_text()
        assert "position = Vector2(50, 75)" in content

    def test_scene_create_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scene", "create", "--help"])
        assert result.exit_code == 0
        assert "JSON_FILE" in result.output
        assert "--output" in result.output


class TestSceneList:
    """Tests for scene list subcommand."""

    def test_scene_list_finds_scenes(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path, {"test.tscn": SAMPLE_TSCN})
        runner = CliRunner()
        result = runner.invoke(cli, ["scene", "list", str(root)])
        assert result.exit_code == 0, result.output
        assert "test.tscn" in result.output

    def test_scene_list_json_output(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path, {"test.tscn": SAMPLE_TSCN})
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "scene", "list", str(root)])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "scenes" in data
        assert len(data["scenes"]) == 1
        assert "path" in data["scenes"][0]
        assert "root_type" in data["scenes"][0]

    def test_scene_list_not_a_project(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scene", "list", str(tmp_path)])
        assert result.exit_code != 0
        combined = (result.output or "") + (result.stderr or "")
        assert "NOT_GODOT_PROJECT" in combined or "not" in combined.lower()

    def test_scene_list_depth_flag(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path, {"test.tscn": SAMPLE_TSCN})
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["-j", "scene", "list", str(root), "--depth", "0"],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        # With depth=0, only root node should appear
        nodes = data["scenes"][0]["nodes"]
        assert len(nodes) == 1  # only root

    def test_scene_list_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scene", "list", "--help"])
        assert result.exit_code == 0
        assert "--depth" in result.output
