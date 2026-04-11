"""Tests for scene diff command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


def _write_scene(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


SCENE_BASE = (
    '[gd_scene format=3]\n\n'
    '[node name="Main" type="Node2D"]\n\n'
    '[node name="Player" type="CharacterBody2D" parent="."]\n\n'
    '[node name="Sprite" type="Sprite2D" parent="Player"]\n'
)

SCENE_ADDED_NODE = (
    '[gd_scene format=3]\n\n'
    '[node name="Main" type="Node2D"]\n\n'
    '[node name="Player" type="CharacterBody2D" parent="."]\n\n'
    '[node name="Sprite" type="Sprite2D" parent="Player"]\n\n'
    '[node name="Timer" type="Timer" parent="."]\n'
)

SCENE_REMOVED_NODE = (
    '[gd_scene format=3]\n\n'
    '[node name="Main" type="Node2D"]\n\n'
    '[node name="Player" type="CharacterBody2D" parent="."]\n'
)

SCENE_MODIFIED_PROP = (
    '[gd_scene format=3]\n\n'
    '[node name="Main" type="Node2D"]\n\n'
    '[node name="Player" type="CharacterBody2D" parent="."]\n'
    'visible = false\n\n'
    '[node name="Sprite" type="Sprite2D" parent="Player"]\n'
)


class TestSceneDiff:

    def test_identical_scenes(self, tmp_path: Path) -> None:
        a = _write_scene(tmp_path / "a.tscn", SCENE_BASE)
        b = _write_scene(tmp_path / "b.tscn", SCENE_BASE)
        result = CliRunner().invoke(cli, ["scene", "diff", str(a), str(b)])
        assert result.exit_code == 0
        assert "identical" in result.output

    def test_added_node(self, tmp_path: Path) -> None:
        a = _write_scene(tmp_path / "a.tscn", SCENE_BASE)
        b = _write_scene(tmp_path / "b.tscn", SCENE_ADDED_NODE)
        result = CliRunner().invoke(cli, ["scene", "diff", str(a), str(b)])
        assert result.exit_code == 0
        assert "+ Timer" in result.output

    def test_removed_node(self, tmp_path: Path) -> None:
        a = _write_scene(tmp_path / "a.tscn", SCENE_BASE)
        b = _write_scene(tmp_path / "b.tscn", SCENE_REMOVED_NODE)
        result = CliRunner().invoke(cli, ["scene", "diff", str(a), str(b)])
        assert result.exit_code == 0
        assert "- Player/Sprite" in result.output

    def test_modified_property(self, tmp_path: Path) -> None:
        a = _write_scene(tmp_path / "a.tscn", SCENE_BASE)
        b = _write_scene(tmp_path / "b.tscn", SCENE_MODIFIED_PROP)
        result = CliRunner().invoke(cli, ["scene", "diff", str(a), str(b)])
        assert result.exit_code == 0
        assert "~ Player" in result.output
        assert "visible" in result.output

    def test_json_identical(self, tmp_path: Path) -> None:
        a = _write_scene(tmp_path / "a.tscn", SCENE_BASE)
        b = _write_scene(tmp_path / "b.tscn", SCENE_BASE)
        result = CliRunner().invoke(cli, ["-j", "scene", "diff", str(a), str(b)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["has_changes"] is False

    def test_json_added_node(self, tmp_path: Path) -> None:
        a = _write_scene(tmp_path / "a.tscn", SCENE_BASE)
        b = _write_scene(tmp_path / "b.tscn", SCENE_ADDED_NODE)
        result = CliRunner().invoke(cli, ["-j", "scene", "diff", str(a), str(b)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["has_changes"] is True
        assert len(data["added_nodes"]) == 1
        assert data["added_nodes"][0]["path"] == "Timer"
        assert data["added_nodes"][0]["type"] == "Timer"

    def test_json_modified_property(self, tmp_path: Path) -> None:
        a = _write_scene(tmp_path / "a.tscn", SCENE_BASE)
        b = _write_scene(tmp_path / "b.tscn", SCENE_MODIFIED_PROP)
        result = CliRunner().invoke(cli, ["-j", "scene", "diff", str(a), str(b)])
        data = json.loads(result.output)
        assert len(data["modified_nodes"]) == 1
        mod = data["modified_nodes"][0]
        assert mod["path"] == "Player"
        assert "visible" in mod["properties"]
