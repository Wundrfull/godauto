"""Tests for scene lint command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli

# Scene with a Sprite2D that has a texture (no warning expected)
SCENE_WITH_TEXTURE = """\
[gd_scene load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://icon.svg" id="1_icon"]

[node name="Root" type="Node2D"]

[node name="Sprite" type="Sprite2D" parent="."]
texture = ExtResource("1_icon")
"""

# Scene with nodes missing required properties
SCENE_MISSING_PROPS = """\
[gd_scene format=3]

[node name="Root" type="Node2D"]

[node name="Ghost" type="Sprite2D" parent="."]

[node name="Hitbox" type="CollisionShape2D" parent="."]

[node name="Music" type="AudioStreamPlayer" parent="."]
"""

# Scene with mixed: some nodes have required props, some don't
SCENE_MIXED = """\
[gd_scene load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://icon.svg" id="1_icon"]

[node name="Root" type="Node2D"]

[node name="GoodSprite" type="Sprite2D" parent="."]
texture = ExtResource("1_icon")

[node name="BadSprite" type="Sprite2D" parent="."]

[node name="Timer" type="Timer" parent="."]
"""

# Scene with no lintable nodes
SCENE_NO_ISSUES = """\
[gd_scene format=3]

[node name="Root" type="Node2D"]

[node name="Timer" type="Timer" parent="."]

[node name="Container" type="VBoxContainer" parent="."]
"""


class TestSceneLint:
    def test_no_warnings_when_clean(self, tmp_path: Path) -> None:
        scene_file = tmp_path / "clean.tscn"
        scene_file.write_text(SCENE_WITH_TEXTURE)
        result = CliRunner().invoke(cli, ["scene", "lint", str(scene_file)])
        assert result.exit_code == 0, result.output
        assert "No issues" in result.output

    def test_detects_missing_texture(self, tmp_path: Path) -> None:
        scene_file = tmp_path / "missing.tscn"
        scene_file.write_text(SCENE_MISSING_PROPS)
        result = CliRunner().invoke(cli, ["scene", "lint", str(scene_file)])
        assert result.exit_code == 0
        assert "Ghost" in result.output
        assert "invisible" in result.output

    def test_detects_missing_shape(self, tmp_path: Path) -> None:
        scene_file = tmp_path / "missing.tscn"
        scene_file.write_text(SCENE_MISSING_PROPS)
        result = CliRunner().invoke(cli, ["scene", "lint", str(scene_file)])
        assert "Hitbox" in result.output
        assert "shape" in result.output

    def test_detects_missing_stream(self, tmp_path: Path) -> None:
        scene_file = tmp_path / "missing.tscn"
        scene_file.write_text(SCENE_MISSING_PROPS)
        result = CliRunner().invoke(cli, ["scene", "lint", str(scene_file)])
        assert "Music" in result.output
        assert "silent" in result.output

    def test_warning_count(self, tmp_path: Path) -> None:
        scene_file = tmp_path / "missing.tscn"
        scene_file.write_text(SCENE_MISSING_PROPS)
        result = CliRunner().invoke(cli, ["scene", "lint", str(scene_file)])
        assert "3 issue(s)" in result.output

    def test_mixed_scene(self, tmp_path: Path) -> None:
        scene_file = tmp_path / "mixed.tscn"
        scene_file.write_text(SCENE_MIXED)
        result = CliRunner().invoke(cli, ["scene", "lint", str(scene_file)])
        assert "BadSprite" in result.output
        assert "GoodSprite" not in result.output
        assert "1 issue(s)" in result.output

    def test_no_lintable_nodes(self, tmp_path: Path) -> None:
        scene_file = tmp_path / "noissue.tscn"
        scene_file.write_text(SCENE_NO_ISSUES)
        result = CliRunner().invoke(cli, ["scene", "lint", str(scene_file)])
        assert result.exit_code == 0
        assert "No issues" in result.output

    def test_json_output(self, tmp_path: Path) -> None:
        scene_file = tmp_path / "missing.tscn"
        scene_file.write_text(SCENE_MISSING_PROPS)
        result = CliRunner().invoke(cli, ["-j", "scene", "lint", str(scene_file)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["warning_count"] == 3
        assert len(data["warnings"]) == 3
        types = {w["type"] for w in data["warnings"]}
        assert "Sprite2D" in types
        assert "CollisionShape2D" in types
        assert "AudioStreamPlayer" in types

    def test_json_output_clean(self, tmp_path: Path) -> None:
        scene_file = tmp_path / "clean.tscn"
        scene_file.write_text(SCENE_WITH_TEXTURE)
        result = CliRunner().invoke(cli, ["-j", "scene", "lint", str(scene_file)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["warning_count"] == 0
        assert data["warnings"] == []

    def test_warning_details_in_json(self, tmp_path: Path) -> None:
        scene_file = tmp_path / "missing.tscn"
        scene_file.write_text(SCENE_MISSING_PROPS)
        result = CliRunner().invoke(cli, ["-j", "scene", "lint", str(scene_file)])
        data = json.loads(result.output)
        sprite_warn = [w for w in data["warnings"] if w["node"] == "Ghost"][0]
        assert sprite_warn["property"] == "texture"
        assert sprite_warn["type"] == "Sprite2D"
