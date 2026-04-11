"""Tests for newly added commands across project, scene, resource, and script groups."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

STANDARD_PROJECT_GODOT = (
    "; Engine configuration file.\n"
    "\n"
    "config_version=5\n"
    "\n"
    "[application]\n"
    "\n"
    'config/name="Test"\n'
    'run/main_scene="res://scenes/main.tscn"\n'
    'config/features=PackedStringArray("4.5", "GL Compatibility")\n'
)

MINIMAL_TSCN = (
    '[gd_scene format=3]\n'
    '\n'
    '[node name="Main" type="Node2D"]\n'
    '\n'
    '[node name="Player" type="CharacterBody2D" parent="."]\n'
    '\n'
    '[node name="Sprite" type="Sprite2D" parent="Player"]\n'
    'position = Vector2(10, 20)\n'
    '\n'
    '[node name="HUD" type="Control" parent="."]\n'
    '\n'
    '[node name="ScoreLabel" type="Label" parent="HUD"]\n'
    'text = "Score: 0"\n'
    '\n'
    '[node name="HealthLabel" type="Label" parent="HUD"]\n'
    'text = "HP: 100"\n'
)

MINIMAL_TSCN_WITH_RESOURCE = (
    '[gd_scene load_steps=2 format=3]\n'
    '\n'
    '[ext_resource type="Script" path="res://scripts/main.gd" id="1"]\n'
    '\n'
    '[node name="Main" type="Node2D"]\n'
    'script = ExtResource("1")\n'
    '\n'
    '[node name="Sprite" type="Sprite2D" parent="."]\n'
)

MINIMAL_GD_SCRIPT = (
    "extends Node2D\n"
    "\n"
    "\n"
    "func _ready() -> void:\n"
    "\tpass\n"
)


def _make_project(tmp_path: Path, content: str | None = None) -> Path:
    """Create a temp project.godot and return its path."""
    pg = tmp_path / "project.godot"
    pg.write_text(content or STANDARD_PROJECT_GODOT, encoding="utf-8")
    return pg


def _make_scene(tmp_path: Path, content: str | None = None) -> Path:
    """Create a temp .tscn scene file and return its path."""
    scene_file = tmp_path / "main.tscn"
    scene_file.write_text(content or MINIMAL_TSCN, encoding="utf-8")
    return scene_file


def _make_script(tmp_path: Path, content: str | None = None) -> Path:
    """Create a temp .gd script file and return its path."""
    gd_file = tmp_path / "test.gd"
    gd_file.write_text(content or MINIMAL_GD_SCRIPT, encoding="utf-8")
    return gd_file


# ===================================================================
# project set-config
# ===================================================================


class TestProjectSetConfig:
    """Verify project set-config writes key-value pairs to project.godot."""

    def test_set_existing_key(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-config",
            "--section", "application",
            "--key", "config/name",
            "--value", '"My Game"',
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = (tmp_path / "project.godot").read_text()
        assert 'config/name="My Game"' in text

    def test_set_new_section_and_key(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-config",
            "--section", "custom_section",
            "--key", "my_key",
            "--value", "42",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = (tmp_path / "project.godot").read_text()
        assert "[custom_section]" in text
        assert "my_key=42" in text

    def test_set_config_json_output(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "set-config",
            "--section", "application",
            "--key", "config/name",
            "--value", '"Updated"',
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["updated"] is True
        assert data["section"] == "application"
        assert data["key"] == "config/name"

    def test_set_config_nonexistent_project_error(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-config",
            "--section", "application",
            "--key", "config/name",
            "--value", '"Test"',
            str(tmp_path / "nonexistent"),
        ])
        assert result.exit_code != 0


# ===================================================================
# project set-main-scene
# ===================================================================


class TestProjectSetMainScene:
    """Verify project set-main-scene updates run/main_scene."""

    def test_set_main_scene(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-main-scene",
            "--scene", "res://scenes/game.tscn",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = (tmp_path / "project.godot").read_text()
        assert 'run/main_scene="res://scenes/game.tscn"' in text

    def test_set_main_scene_json_output(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "set-main-scene",
            "--scene", "res://scenes/new_main.tscn",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["updated"] is True
        assert data["main_scene"] == "res://scenes/new_main.tscn"

    def test_set_main_scene_nonexistent_project(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-main-scene",
            "--scene", "res://scenes/main.tscn",
            str(tmp_path / "missing"),
        ])
        assert result.exit_code != 0

    def test_set_main_scene_overwrites_existing(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        # First call sets an initial value
        runner.invoke(cli, [
            "project", "set-main-scene",
            "--scene", "res://scenes/first.tscn",
            str(tmp_path),
        ])
        # Second call overwrites
        result = runner.invoke(cli, [
            "project", "set-main-scene",
            "--scene", "res://scenes/second.tscn",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "project.godot").read_text()
        assert 'run/main_scene="res://scenes/second.tscn"' in text
        # The old value should be gone
        assert "first.tscn" not in text


# ===================================================================
# project add-plugin
# ===================================================================


class TestProjectAddPlugin:
    """Verify project add-plugin enables plugins in editor_plugins."""

    def test_add_first_plugin(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-plugin",
            "--name", "gut",
            "--path", "res://addons/gut/plugin.cfg",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = (tmp_path / "project.godot").read_text()
        assert "[editor_plugins]" in text
        assert "res://addons/gut/plugin.cfg" in text

    def test_add_second_plugin(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        # Add first plugin
        runner.invoke(cli, [
            "project", "add-plugin",
            "--name", "gut",
            "--path", "res://addons/gut/plugin.cfg",
            str(tmp_path),
        ])
        # Add second plugin
        result = runner.invoke(cli, [
            "project", "add-plugin",
            "--name", "dialogic",
            "--path", "res://addons/dialogic/plugin.cfg",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = (tmp_path / "project.godot").read_text()
        assert "res://addons/gut/plugin.cfg" in text
        assert "res://addons/dialogic/plugin.cfg" in text

    def test_add_duplicate_plugin_error(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "project", "add-plugin",
            "--name", "gut",
            "--path", "res://addons/gut/plugin.cfg",
            str(tmp_path),
        ])
        result = runner.invoke(cli, [
            "project", "add-plugin",
            "--name", "gut",
            "--path", "res://addons/gut/plugin.cfg",
            str(tmp_path),
        ])
        assert result.exit_code != 0

    def test_add_plugin_json_output(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "add-plugin",
            "--name", "gut",
            "--path", "res://addons/gut/plugin.cfg",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["name"] == "gut"


# ===================================================================
# scene rename-node
# ===================================================================


class TestSceneRenameNode:
    """Verify scene rename-node renames nodes and updates parent references."""

    def test_rename_simple_node(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "rename-node",
            "--scene", str(scene),
            "--node", "Player",
            "--new-name", "Hero",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert 'name="Hero"' in text
        # Child "Sprite" should now reference parent "Hero" instead of "Player"
        assert 'parent="Hero"' in text

    def test_rename_node_not_found(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "rename-node",
            "--scene", str(scene),
            "--node", "NonExistent",
            "--new-name", "Renamed",
        ])
        assert result.exit_code != 0

    def test_rename_with_parent_disambiguation(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "rename-node",
            "--scene", str(scene),
            "--node", "ScoreLabel",
            "--parent", "HUD",
            "--new-name", "PointsLabel",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert 'name="PointsLabel"' in text

    def test_rename_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "rename-node",
            "--scene", str(scene),
            "--node", "HUD",
            "--new-name", "UI",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["renamed"] is True
        assert data["old_name"] == "HUD"
        assert data["new_name"] == "UI"


# ===================================================================
# scene reorder-node
# ===================================================================


class TestSceneReorderNode:
    """Verify scene reorder-node changes sibling order."""

    def test_reorder_to_first(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "reorder-node",
            "--scene", str(scene),
            "--node", "HealthLabel",
            "--parent", "HUD",
            "--index", "0",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        # HealthLabel should appear before ScoreLabel in the file
        health_pos = text.index("HealthLabel")
        score_pos = text.index("ScoreLabel")
        assert health_pos < score_pos

    def test_reorder_node_not_found(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "reorder-node",
            "--scene", str(scene),
            "--node", "Missing",
            "--index", "0",
        ])
        assert result.exit_code != 0

    def test_reorder_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "reorder-node",
            "--scene", str(scene),
            "--node", "HealthLabel",
            "--parent", "HUD",
            "--index", "0",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["reordered"] is True
        assert data["name"] == "HealthLabel"
        assert data["index"] == 0


# ===================================================================
# scene set-resource
# ===================================================================


class TestSceneSetResource:
    """Verify scene set-resource assigns ext_resource to node properties."""

    def test_set_new_resource(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "set-resource",
            "--scene", str(scene),
            "--node", "Main",
            "--property", "theme",
            "--resource", "res://theme/game_theme.tres",
            "--type", "Theme",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert "res://theme/game_theme.tres" in text
        assert "Theme" in text
        # The node should have an ExtResource reference on the theme property
        assert "theme" in text
        assert "ExtResource" in text

    def test_set_resource_reuses_existing(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path, MINIMAL_TSCN_WITH_RESOURCE)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "set-resource",
            "--scene", str(scene),
            "--node", "Sprite",
            "--property", "script",
            "--resource", "res://scripts/main.gd",
            "--type", "Script",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        # Should reuse existing ext_resource id "1", not create a duplicate
        assert text.count("res://scripts/main.gd") == 1

    def test_set_resource_node_not_found(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "set-resource",
            "--scene", str(scene),
            "--node", "NonExistent",
            "--property", "theme",
            "--resource", "res://theme/t.tres",
            "--type", "Theme",
        ])
        assert result.exit_code != 0

    def test_set_resource_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "set-resource",
            "--scene", str(scene),
            "--node", "Main",
            "--property", "material",
            "--resource", "res://materials/flash.tres",
            "--type", "ShaderMaterial",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["set"] is True
        assert data["node"] == "Main"
        assert data["property"] == "material"
        assert data["resource"] == "res://materials/flash.tres"


# ===================================================================
# scene create-simple
# ===================================================================


class TestSceneCreateSimple:
    """Verify scene create-simple creates a scene from CLI args."""

    def test_create_node2d_scene(self, tmp_path: Path) -> None:
        output = tmp_path / "level.tscn"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "create-simple",
            "--root-type", "Node2D",
            "--root-name", "Level",
            "-o", str(output),
        ])
        assert result.exit_code == 0, result.output
        assert output.exists()
        text = output.read_text()
        assert "[gd_scene" in text
        assert 'name="Level"' in text
        assert 'type="Node2D"' in text

    def test_create_control_scene(self, tmp_path: Path) -> None:
        output = tmp_path / "menu.tscn"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "create-simple",
            "--root-type", "Control",
            "--root-name", "Menu",
            "-o", str(output),
        ])
        assert result.exit_code == 0, result.output
        text = output.read_text()
        assert 'type="Control"' in text
        assert 'name="Menu"' in text

    def test_create_simple_creates_parent_dirs(self, tmp_path: Path) -> None:
        output = tmp_path / "scenes" / "nested" / "deep.tscn"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "create-simple",
            "--root-type", "Node2D",
            "--root-name", "Deep",
            "-o", str(output),
        ])
        assert result.exit_code == 0, result.output
        assert output.exists()

    def test_create_simple_json_output(self, tmp_path: Path) -> None:
        output = tmp_path / "test.tscn"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "create-simple",
            "--root-type", "Node2D",
            "--root-name", "World",
            "-o", str(output),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["root_type"] == "Node2D"
        assert data["root_name"] == "World"


# ===================================================================
# scene inspect-node
# ===================================================================


class TestSceneInspectNode:
    """Verify scene inspect-node shows node properties and metadata."""

    def test_inspect_root_node(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "inspect-node",
            "--scene", str(scene),
            "--node", "Main",
        ])
        assert result.exit_code == 0, result.output
        assert "Main" in result.output
        assert "Node2D" in result.output

    def test_inspect_node_with_properties(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "inspect-node",
            "--scene", str(scene),
            "--node", "ScoreLabel",
            "--parent", "HUD",
        ])
        assert result.exit_code == 0, result.output
        assert "ScoreLabel" in result.output

    def test_inspect_node_not_found(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "inspect-node",
            "--scene", str(scene),
            "--node", "NonExistent",
        ])
        assert result.exit_code != 0

    def test_inspect_node_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "inspect-node",
            "--scene", str(scene),
            "--node", "Main",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["name"] == "Main"
        assert data["type"] == "Node2D"
        assert data["parent"] is None
        assert "properties" in data


# ===================================================================
# scene move-node
# ===================================================================


class TestSceneMoveNode:
    """Verify scene move-node moves nodes to a different parent."""

    def test_move_node_to_new_parent(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "move-node",
            "--scene", str(scene),
            "--node", "ScoreLabel",
            "--parent", "HUD",
            "--new-parent", ".",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        # ScoreLabel should now be a direct child of root
        # Find the ScoreLabel node section and check its parent
        assert 'name="ScoreLabel"' in text

    def test_move_node_not_found(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "move-node",
            "--scene", str(scene),
            "--node", "Ghost",
            "--new-parent", "Player",
        ])
        assert result.exit_code != 0

    def test_move_node_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "move-node",
            "--scene", str(scene),
            "--node", "Sprite",
            "--parent", "Player",
            "--new-parent", ".",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["moved"] is True
        assert data["name"] == "Sprite"
        assert data["to"] == "."

    def test_move_updates_child_parent_references(self, tmp_path: Path) -> None:
        """Moving HUD should update its children's parent paths."""
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "move-node",
            "--scene", str(scene),
            "--node", "HUD",
            "--new-parent", "Player",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        # Children of HUD should now reference Player/HUD as parent
        assert "Player/HUD" in text


# ===================================================================
# scene list-types
# ===================================================================


class TestSceneListTypes:
    """Verify scene list-types shows node type counts."""

    def test_list_types_basic(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "list-types", str(scene),
        ])
        assert result.exit_code == 0, result.output
        assert "Node2D" in result.output
        assert "Label" in result.output

    def test_list_types_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "list-types", str(scene),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "types" in data
        assert data["total_nodes"] > 0
        type_names = [t["type"] for t in data["types"]]
        assert "Node2D" in type_names
        assert "Label" in type_names

    def test_list_types_counts_correct(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "list-types", str(scene),
        ])
        data = json.loads(result.output)
        label_entry = next(t for t in data["types"] if t["type"] == "Label")
        # There are two Label nodes: ScoreLabel and HealthLabel
        assert label_entry["count"] == 2

    def test_list_types_empty_scene(self, tmp_path: Path) -> None:
        """A minimal scene with just a header yields a single root node type."""
        minimal = tmp_path / "empty.tscn"
        minimal.write_text(
            '[gd_scene format=3]\n\n'
            '[node name="Root" type="Node"]\n',
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "list-types", str(minimal),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["total_nodes"] == 1
        assert data["types"][0]["type"] == "Node"


# ===================================================================
# scene copy-properties
# ===================================================================


class TestSceneCopyProperties:
    """Verify scene copy-properties copies properties between nodes."""

    def test_copy_properties_basic(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "copy-properties",
            "--scene", str(scene),
            "--from-node", "ScoreLabel",
            "--to-node", "HealthLabel",
            "--parent", "HUD",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        # HealthLabel should now also have the "text" property from ScoreLabel
        # (though it already had one, it should be overwritten)
        assert result.exit_code == 0

    def test_copy_properties_json(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "copy-properties",
            "--scene", str(scene),
            "--from-node", "ScoreLabel",
            "--to-node", "HealthLabel",
            "--parent", "HUD",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["copied"] >= 1
        assert data["from"] == "ScoreLabel"
        assert data["to"] == "HealthLabel"

    def test_copy_source_not_found(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "copy-properties",
            "--scene", str(scene),
            "--from-node", "Missing",
            "--to-node", "HealthLabel",
        ])
        assert result.exit_code != 0

    def test_copy_dest_not_found(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "copy-properties",
            "--scene", str(scene),
            "--from-node", "ScoreLabel",
            "--to-node", "Missing",
        ])
        assert result.exit_code != 0


# ===================================================================
# scene set-anchor
# ===================================================================


class TestSceneSetAnchor:
    """Verify scene set-anchor sets anchor presets on Control nodes."""

    def test_set_full_rect_anchor(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "set-anchor",
            "--scene", str(scene),
            "--node", "HUD",
            "--preset", "full_rect",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert "anchor_left" in text
        assert "anchor_right" in text

    def test_set_center_anchor(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "set-anchor",
            "--scene", str(scene),
            "--node", "HUD",
            "--preset", "center",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert "anchor_left" in text

    def test_set_anchor_node_not_found(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "set-anchor",
            "--scene", str(scene),
            "--node", "NonExistent",
            "--preset", "full_rect",
        ])
        assert result.exit_code != 0

    def test_set_anchor_invalid_preset(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "set-anchor",
            "--scene", str(scene),
            "--node", "HUD",
            "--preset", "invalid_preset",
        ])
        # Click should reject invalid choice before command runs
        assert result.exit_code != 0

    def test_set_anchor_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "set-anchor",
            "--scene", str(scene),
            "--node", "HUD",
            "--preset", "top_left",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["set"] is True
        assert data["preset"] == "top_left"


# ===================================================================
# scene from-template
# ===================================================================


class TestSceneFromTemplate:
    """Verify scene from-template creates scenes from built-in templates."""

    def test_player_2d_template(self, tmp_path: Path) -> None:
        output = tmp_path / "player.tscn"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "from-template",
            "--template", "player-2d",
            "-o", str(output),
        ])
        assert result.exit_code == 0, result.output
        assert output.exists()
        text = output.read_text()
        assert "[gd_scene" in text
        assert 'name="Player"' in text
        assert "CharacterBody2D" in text
        assert "Sprite2D" in text
        assert "CollisionShape2D" in text
        assert "Camera2D" in text

    def test_ui_panel_template(self, tmp_path: Path) -> None:
        output = tmp_path / "shop.tscn"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "from-template",
            "--template", "ui-panel",
            "-o", str(output),
            "--title", "Shop",
        ])
        assert result.exit_code == 0, result.output
        text = output.read_text()
        assert "PanelContainer" in text
        assert "VBoxContainer" in text

    def test_level_2d_template(self, tmp_path: Path) -> None:
        output = tmp_path / "level.tscn"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "from-template",
            "--template", "level-2d",
            "-o", str(output),
        ])
        assert result.exit_code == 0, result.output
        text = output.read_text()
        assert 'name="Level"' in text
        assert "TileMapLayer" in text

    def test_invalid_template_rejected(self, tmp_path: Path) -> None:
        output = tmp_path / "bad.tscn"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "from-template",
            "--template", "nonexistent-template",
            "-o", str(output),
        ])
        # Click Choice should reject the invalid template
        assert result.exit_code != 0

    def test_from_template_json_output(self, tmp_path: Path) -> None:
        output = tmp_path / "test.tscn"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "from-template",
            "--template", "player-2d",
            "-o", str(output),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["template"] == "player-2d"
        assert "path" in data


# ===================================================================
# resource list
# ===================================================================


class TestResourceList:
    """Verify resource list shows ext_resources in a scene."""

    def test_list_resources_with_ext(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path, MINIMAL_TSCN_WITH_RESOURCE)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "resource", "list",
            "--scene", str(scene),
        ])
        assert result.exit_code == 0, result.output
        assert "Script" in result.output
        assert "res://scripts/main.gd" in result.output

    def test_list_resources_empty(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "resource", "list",
            "--scene", str(scene),
        ])
        assert result.exit_code == 0, result.output

    def test_list_resources_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path, MINIMAL_TSCN_WITH_RESOURCE)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "resource", "list",
            "--scene", str(scene),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["resources"][0]["type"] == "Script"
        assert data["resources"][0]["path"] == "res://scripts/main.gd"

    def test_list_resources_unsupported_file(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.txt"
        bad_file.write_text("not a resource", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, [
            "resource", "list",
            "--scene", str(bad_file),
        ])
        assert result.exit_code != 0


# ===================================================================
# script add-method
# ===================================================================


class TestScriptAddMethod:
    """Verify script add-method appends methods to .gd files."""

    def test_add_simple_method(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-method",
            "--file", str(gd),
            "--name", "_on_button_pressed",
            "--body", "score += 1",
        ])
        assert result.exit_code == 0, result.output
        text = gd.read_text()
        assert "func _on_button_pressed()" in text
        assert "score += 1" in text

    def test_add_method_with_params_and_return(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-method",
            "--file", str(gd),
            "--name", "take_damage",
            "--params", "amount: int",
            "--return-type", "void",
            "--body", "health -= amount",
        ])
        assert result.exit_code == 0, result.output
        text = gd.read_text()
        assert "func take_damage(amount: int) -> void:" in text
        assert "health -= amount" in text

    def test_add_duplicate_method_error(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        # _ready already exists in the script
        result = runner.invoke(cli, [
            "script", "add-method",
            "--file", str(gd),
            "--name", "_ready",
            "--body", "print('hello')",
        ])
        assert result.exit_code != 0

    def test_add_method_nonexistent_file(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-method",
            "--file", str(tmp_path / "missing.gd"),
            "--name", "test_method",
        ])
        assert result.exit_code != 0

    def test_add_method_json_output(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "script", "add-method",
            "--file", str(gd),
            "--name", "heal",
            "--body", "health += 10",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["method"] == "heal"

    def test_add_method_fixes_variant_inference(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-method",
            "--file", str(gd),
            "--name", "load_data",
            "--body", "var data := JSON.parse_string(some_text)",
        ])
        assert result.exit_code == 0, result.output
        text = gd.read_text()
        assert "var data: Variant = JSON.parse_string(some_text)" in text
        assert ":=" not in text

    def test_add_method_preserves_safe_walrus(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-method",
            "--file", str(gd),
            "--name", "compute",
            "--body", "var x := 5 + 3",
        ])
        assert result.exit_code == 0, result.output
        text = gd.read_text()
        # Non-Variant := should be preserved
        assert "var x := 5 + 3" in text

    def test_add_method_fixes_dict_get_variant(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-method",
            "--file", str(gd),
            "--name", "get_value",
            "--body", "var val := my_dict.get(key)",
        ])
        assert result.exit_code == 0, result.output
        text = gd.read_text()
        assert "var val: Variant = my_dict.get(key)" in text


# ===================================================================
# script add-var
# ===================================================================


class TestScriptAddVar:
    """Verify script add-var inserts variable declarations."""

    def test_add_var_with_default(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-var",
            "--file", str(gd),
            "--name", "score",
            "--type", "int",
            "--value", "0",
        ])
        assert result.exit_code == 0, result.output
        text = gd.read_text()
        assert "var score: int = 0" in text

    def test_add_var_without_default(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-var",
            "--file", str(gd),
            "--name", "player_name",
            "--type", "String",
        ])
        assert result.exit_code == 0, result.output
        text = gd.read_text()
        assert "var player_name: String" in text

    def test_add_var_file_not_found(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-var",
            "--file", str(tmp_path / "missing.gd"),
            "--name", "x",
            "--type", "int",
        ])
        assert result.exit_code != 0

    def test_add_var_json_output(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "script", "add-var",
            "--file", str(gd),
            "--name", "health",
            "--type", "float",
            "--value", "100.0",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["var"] == "health"
        assert data["type"] == "float"

    def test_add_multiple_vars(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "script", "add-var",
            "--file", str(gd),
            "--name", "speed",
            "--type", "float",
            "--value", "200.0",
        ])
        result = runner.invoke(cli, [
            "script", "add-var",
            "--file", str(gd),
            "--name", "health",
            "--type", "int",
            "--value", "100",
        ])
        assert result.exit_code == 0
        text = gd.read_text()
        assert "var speed: float = 200.0" in text
        assert "var health: int = 100" in text


# ===================================================================
# script add-export
# ===================================================================


class TestScriptAddExport:
    """Verify script add-export inserts @export variable declarations."""

    def test_add_export_with_default(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-export",
            "--file", str(gd),
            "--name", "speed",
            "--type", "float",
            "--value", "100.0",
        ])
        assert result.exit_code == 0, result.output
        text = gd.read_text()
        assert "@export var speed: float = 100.0" in text

    def test_add_export_without_default(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-export",
            "--file", str(gd),
            "--name", "texture",
            "--type", "Texture2D",
        ])
        assert result.exit_code == 0, result.output
        text = gd.read_text()
        assert "@export var texture: Texture2D" in text

    def test_add_export_file_not_found(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-export",
            "--file", str(tmp_path / "missing.gd"),
            "--name", "val",
            "--type", "int",
        ])
        assert result.exit_code != 0

    def test_add_export_json_output(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "script", "add-export",
            "--file", str(gd),
            "--name", "max_hp",
            "--type", "int",
            "--value", "100",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["export"] == "max_hp"
        assert data["type"] == "int"


# ===================================================================
# script add-signal
# ===================================================================


class TestScriptAddSignal:
    """Verify script add-signal inserts signal declarations."""

    def test_add_signal_no_params(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-signal",
            "--file", str(gd),
            "--name", "died",
        ])
        assert result.exit_code == 0, result.output
        text = gd.read_text()
        assert "signal died" in text

    def test_add_signal_with_params(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-signal",
            "--file", str(gd),
            "--name", "score_changed",
            "--params", "new_score: int, old_score: int",
        ])
        assert result.exit_code == 0, result.output
        text = gd.read_text()
        assert "signal score_changed(new_score: int, old_score: int)" in text

    def test_add_signal_file_not_found(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "add-signal",
            "--file", str(tmp_path / "missing.gd"),
            "--name", "test_signal",
        ])
        assert result.exit_code != 0

    def test_add_signal_json_output(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "script", "add-signal",
            "--file", str(gd),
            "--name", "health_changed",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["signal"] == "health_changed"

    def test_add_multiple_signals(self, tmp_path: Path) -> None:
        gd = _make_script(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "script", "add-signal",
            "--file", str(gd),
            "--name", "died",
        ])
        result = runner.invoke(cli, [
            "script", "add-signal",
            "--file", str(gd),
            "--name", "respawned",
        ])
        assert result.exit_code == 0
        text = gd.read_text()
        assert "signal died" in text
        assert "signal respawned" in text
