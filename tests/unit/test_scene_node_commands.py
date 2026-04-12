"""Tests for scene add-node and remove-node commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


def _make_scene(tmp_path: Path) -> Path:
    """Create a scene with some existing nodes."""
    scene_file = tmp_path / "main.tscn"
    scene_file.write_text(
        '[gd_scene format=3]\n'
        '\n'
        '[node name="Main" type="Node2D"]\n'
        '\n'
        '[node name="Player" type="CharacterBody2D" parent="."]\n'
        '\n'
        '[node name="Sprite" type="Sprite2D" parent="Player"]\n',
        encoding="utf-8",
    )
    return scene_file


class TestAddNode:
    """Verify scene add-node adds nodes to scenes."""

    def test_add_timer(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-node",
            "--scene", str(scene),
            "--name", "Timer",
            "--type", "Timer",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert 'name="Timer"' in text
        assert 'type="Timer"' in text

    def test_add_with_parent(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-node",
            "--scene", str(scene),
            "--name", "CollisionShape",
            "--type", "CollisionShape2D",
            "--parent", "Player",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert 'parent="Player"' in text

    def test_add_with_nested_parent(self, tmp_path: Path) -> None:
        """Bare --parent resolves nested node to full path from root."""
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        # Sprite is at parent="Player", so a child of Sprite needs
        # parent="Player/Sprite" in the .tscn file.
        result = runner.invoke(cli, [
            "scene", "add-node",
            "--scene", str(scene),
            "--name", "SpriteChild",
            "--type", "Node2D",
            "--parent", "Sprite",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert 'parent="Player/Sprite"' in text

    def test_add_with_full_path_parent(self, tmp_path: Path) -> None:
        """Full path --parent is used as-is without resolution."""
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-node",
            "--scene", str(scene),
            "--name", "SpriteChild",
            "--type", "Node2D",
            "--parent", "Player/Sprite",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert 'parent="Player/Sprite"' in text

    def test_add_with_root_parent(self, tmp_path: Path) -> None:
        """--parent RootName resolves to '.' in the .tscn file."""
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-node",
            "--scene", str(scene),
            "--name", "Timer",
            "--type", "Timer",
            "--parent", "Main",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert 'name="Timer"' in text
        assert 'parent="."' in text
        assert 'parent="Main"' not in text

    def test_add_with_root_prefixed_path(self, tmp_path: Path) -> None:
        """--parent RootName/Child strips root and resolves to 'Child'."""
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-node",
            "--scene", str(scene),
            "--name", "SpriteChild",
            "--type", "Node2D",
            "--parent", "Main/Player",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert 'parent="Player"' in text
        assert 'parent="Main/Player"' not in text

    def test_add_with_properties(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-node",
            "--scene", str(scene),
            "--name", "Label",
            "--type", "Label",
            "--property", 'text="Hello"',
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert 'name="Label"' in text

    def test_add_duplicate_error(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-node",
            "--scene", str(scene),
            "--name", "Player",
            "--type", "Node2D",
        ])
        assert result.exit_code != 0

    def test_add_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "add-node",
            "--scene", str(scene),
            "--name", "Camera",
            "--type", "Camera2D",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["name"] == "Camera"
        assert data["type"] == "Camera2D"

    def test_add_multiple_nodes(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        nodes = [
            ("Timer", "Timer"),
            ("Camera", "Camera2D"),
            ("HUD", "CanvasLayer"),
        ]
        for name, node_type in nodes:
            result = runner.invoke(cli, [
                "scene", "add-node",
                "--scene", str(scene),
                "--name", name,
                "--type", node_type,
            ])
            assert result.exit_code == 0, f"Failed for {name}: {result.output}"
        text = scene.read_text()
        for name, _ in nodes:
            assert f'name="{name}"' in text


class TestRemoveNode:
    """Verify scene remove-node removes nodes from scenes."""

    def test_remove_leaf_node(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "remove-node",
            "--scene", str(scene),
            "--name", "Sprite",
            "--parent", "Player",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert "Sprite" not in text
        assert "Player" in text  # Parent preserved

    def test_remove_with_children(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "remove-node",
            "--scene", str(scene),
            "--name", "Player",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "Player" not in text
        assert "Sprite" not in text  # Child removed too

    def test_remove_nonexistent_error(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "remove-node",
            "--scene", str(scene),
            "--name", "Nonexistent",
        ])
        assert result.exit_code != 0

    def test_cannot_remove_root(self, tmp_path: Path) -> None:
        scene = tmp_path / "simple.tscn"
        scene.write_text(
            '[gd_scene format=3]\n\n[node name="Root" type="Node2D"]\n',
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "remove-node",
            "--scene", str(scene),
            "--name", "Root",
        ])
        assert result.exit_code != 0

    def test_remove_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "remove-node",
            "--scene", str(scene),
            "--name", "Player",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["removed"] is True
        assert data["nodes_removed"] == 2  # Player + Sprite child

    def test_add_then_remove(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "scene", "add-node",
            "--scene", str(scene),
            "--name", "Timer",
            "--type", "Timer",
        ])
        assert "Timer" in scene.read_text()
        runner.invoke(cli, [
            "scene", "remove-node",
            "--scene", str(scene),
            "--name", "Timer",
        ])
        assert "Timer" not in scene.read_text()


class TestSetProperty:
    """Verify scene set-property modifies node properties."""

    def test_set_visible(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "set-property",
            "--scene", str(scene),
            "--node", "Player",
            "--property", "visible=false",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert "visible = false" in text

    def test_set_multiple_properties(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "set-property",
            "--scene", str(scene),
            "--node", "Player",
            "--property", "visible=false",
            "--property", "z_index=10",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "visible = false" in text
        assert "z_index = 10" in text

    def test_set_with_parent(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "set-property",
            "--scene", str(scene),
            "--node", "Sprite",
            "--parent", "Player",
            "--property", "visible=false",
        ])
        assert result.exit_code == 0

    def test_node_not_found_error(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "set-property",
            "--scene", str(scene),
            "--node", "Nonexistent",
            "--property", "visible=false",
        ])
        assert result.exit_code != 0

    def test_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "set-property",
            "--scene", str(scene),
            "--node", "Player",
            "--property", "visible=true",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["updated"] is True
        assert data["node"] == "Player"
        assert data["count"] == 1


class TestMissingFileJsonContract:
    """Missing files must produce JSON errors, not Click plain-text errors."""

    def test_add_node_missing_scene_json(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.tscn"
        result = CliRunner().invoke(cli, [
            "-j", "scene", "add-node",
            "--scene", str(missing),
            "--name", "Timer", "--type", "Timer",
        ])
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert "error" in data
        assert "code" in data
        assert data["code"] == "FILE_NOT_FOUND"

    def test_remove_node_missing_scene_json(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.tscn"
        result = CliRunner().invoke(cli, [
            "-j", "scene", "remove-node",
            "--scene", str(missing),
            "--name", "Foo",
        ])
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert data["code"] == "FILE_NOT_FOUND"

    def test_set_property_missing_scene_json(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.tscn"
        result = CliRunner().invoke(cli, [
            "-j", "scene", "set-property",
            "--scene", str(missing),
            "--node", "Root", "--property", "visible=false",
        ])
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert data["code"] == "FILE_NOT_FOUND"
        assert "fix" in data
