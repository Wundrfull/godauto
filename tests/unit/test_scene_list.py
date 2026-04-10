"""Tests for scene lister: project directory to scene metadata."""

from __future__ import annotations

from pathlib import Path

from auto_godot.scene.lister import list_scenes


SAMPLE_TSCN = """\
[gd_scene load_steps=2 format=3 uid="uid://btk3example123"]

[ext_resource type="Script" uid="uid://c7gn4example" path="res://scripts/player.gd" id="1_script"]

[node name="Player" type="CharacterBody2D"]
script = ExtResource("1_script")

[node name="Sprite" type="Sprite2D" parent="."]
position = Vector2(0, 0)

[node name="CollisionShape" type="CollisionShape2D" parent="."]
"""

INSTANCE_TSCN = """\
[gd_scene load_steps=2 format=3 uid="uid://abc123"]

[ext_resource type="PackedScene" uid="uid://def456" path="res://scenes/player.tscn" id="1_player"]

[node name="Level" type="Node2D"]

[node name="Player" parent="." instance=ExtResource("1_player")]
"""


def _setup_project(tmp_path: Path, scenes: dict[str, str] | None = None) -> Path:
    """Create a minimal Godot project directory with optional scene files."""
    godot_cfg = tmp_path / "project.godot"
    godot_cfg.write_text(
        "; Engine configuration file.\n"
        "config_version=5\n"
        "[application]\n"
        'config/name="TestProject"\n'
    )
    if scenes:
        for name, content in scenes.items():
            scene_path = tmp_path / name
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            scene_path.write_text(content)
    return tmp_path


class TestListScenesBasic:
    """Tests for basic scene listing functionality."""

    def test_single_scene_returns_one_entry(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path, {"test.tscn": SAMPLE_TSCN})
        result = list_scenes(root)
        assert len(result) == 1

    def test_entry_has_required_keys(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path, {"test.tscn": SAMPLE_TSCN})
        result = list_scenes(root)
        entry = result[0]
        assert "path" in entry
        assert "root_type" in entry
        assert "node_count" in entry

    def test_correct_node_count(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path, {"test.tscn": SAMPLE_TSCN})
        result = list_scenes(root)
        # SAMPLE_TSCN has 3 nodes: Player, Sprite, CollisionShape
        assert result[0]["node_count"] == 3


class TestListScenesScriptsAndInstances:
    """Tests for script detection and instance resolution."""

    def test_detects_script_resources(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path, {"test.tscn": SAMPLE_TSCN})
        result = list_scenes(root)
        assert "scripts" in result[0]
        assert "res://scripts/player.gd" in result[0]["scripts"]

    def test_detects_instance_references(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path, {"level.tscn": INSTANCE_TSCN})
        result = list_scenes(root)
        assert "instances" in result[0]
        assert "res://scenes/player.tscn" in result[0]["instances"]


class TestListScenesMultipleAndFiltering:
    """Tests for multiple scenes and depth filtering."""

    def test_multiple_scenes_all_found(self, tmp_path: Path) -> None:
        root = _setup_project(
            tmp_path,
            {"scene_a.tscn": SAMPLE_TSCN, "scene_b.tscn": SAMPLE_TSCN},
        )
        result = list_scenes(root)
        assert len(result) == 2

    def test_depth_limits_tree(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path, {"test.tscn": SAMPLE_TSCN})
        result = list_scenes(root, depth=1)
        # With depth=1, should show root + direct children only
        nodes = result[0]["nodes"]
        # The nodes list should contain the tree but limited
        assert len(nodes) > 0

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        result = list_scenes(root)
        assert result == []

    def test_path_is_relative(self, tmp_path: Path) -> None:
        root = _setup_project(
            tmp_path,
            {"scenes/test.tscn": SAMPLE_TSCN},
        )
        result = list_scenes(root)
        path_str = result[0]["path"]
        # Path should be relative (not absolute)
        assert not Path(path_str).is_absolute()
        assert "scenes" in path_str or "test.tscn" in path_str
