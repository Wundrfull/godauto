"""Tests for scene tree command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


def _make_scene(tmp_path: Path) -> Path:
    scene_file = tmp_path / "main.tscn"
    scene_file.write_text(
        '[gd_scene format=3]\n\n'
        '[node name="Main" type="Node2D"]\n\n'
        '[node name="Player" type="CharacterBody2D" parent="."]\n\n'
        '[node name="Sprite" type="Sprite2D" parent="Player"]\n\n'
        '[node name="CollisionShape" type="CollisionShape2D" parent="Player"]\n\n'
        '[node name="Timer" type="Timer" parent="."]\n\n'
        '[node name="UI" type="CanvasLayer" parent="."]\n\n'
        '[node name="HUD" type="Control" parent="UI"]\n\n'
        '[node name="HealthBar" type="ProgressBar" parent="UI/HUD"]\n',
        encoding="utf-8",
    )
    return scene_file


class TestSceneTree:

    def test_tree_output_contains_all_nodes(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        result = CliRunner().invoke(cli, ["scene", "tree", str(scene)])
        assert result.exit_code == 0, result.output
        for name in ("Main", "Player", "Sprite", "CollisionShape", "Timer", "UI", "HUD", "HealthBar"):
            assert name in result.output

    def test_tree_shows_types(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        result = CliRunner().invoke(cli, ["scene", "tree", str(scene)])
        assert "Node2D" in result.output
        assert "CharacterBody2D" in result.output
        assert "ProgressBar" in result.output

    def test_tree_no_types(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        result = CliRunner().invoke(cli, ["scene", "tree", "--no-types", str(scene)])
        assert result.exit_code == 0
        assert "Main" in result.output
        # Types should not appear
        assert "Node2D" not in result.output
        assert "CharacterBody2D" not in result.output

    def test_tree_json_nested(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        result = CliRunner().invoke(cli, ["-j", "scene", "tree", str(scene)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 8
        tree = data["tree"]
        assert tree["name"] == "Main"
        assert tree["type"] == "Node2D"
        # Player is a child of root
        player = next(c for c in tree["children"] if c["name"] == "Player")
        assert player["type"] == "CharacterBody2D"
        # Sprite is a child of Player
        sprite = next(c for c in player["children"] if c["name"] == "Sprite")
        assert sprite["type"] == "Sprite2D"

    def test_tree_json_deep_nesting(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        result = CliRunner().invoke(cli, ["-j", "scene", "tree", str(scene)])
        data = json.loads(result.output)
        tree = data["tree"]
        ui = next(c for c in tree["children"] if c["name"] == "UI")
        hud = next(c for c in ui["children"] if c["name"] == "HUD")
        health = next(c for c in hud["children"] if c["name"] == "HealthBar")
        assert health["type"] == "ProgressBar"

    def test_single_root(self, tmp_path: Path) -> None:
        scene = tmp_path / "root.tscn"
        scene.write_text(
            '[gd_scene format=3]\n\n[node name="Root" type="Node"]\n',
            encoding="utf-8",
        )
        result = CliRunner().invoke(cli, ["-j", "scene", "tree", str(scene)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["tree"]["name"] == "Root"
        assert "children" not in data["tree"]
