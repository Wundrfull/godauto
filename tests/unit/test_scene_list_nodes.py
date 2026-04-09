"""Tests for scene list-nodes command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gdauto.cli import cli


def _make_scene(tmp_path: Path) -> Path:
    scene_file = tmp_path / "main.tscn"
    scene_file.write_text(
        '[gd_scene format=3]\n\n'
        '[node name="Main" type="Node2D"]\n\n'
        '[node name="Player" type="CharacterBody2D" parent="."]\n\n'
        '[node name="Sprite" type="Sprite2D" parent="Player"]\n\n'
        '[node name="Timer" type="Timer" parent="."]\n',
        encoding="utf-8",
    )
    return scene_file


class TestListNodes:
    """Verify scene list-nodes shows node tree."""

    def test_list_all_nodes(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["scene", "list-nodes", str(scene)])
        assert result.exit_code == 0, result.output
        assert "Main" in result.output
        assert "Player" in result.output
        assert "Sprite" in result.output
        assert "Timer" in result.output

    def test_shows_types(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["scene", "list-nodes", str(scene)])
        assert "Node2D" in result.output
        assert "CharacterBody2D" in result.output

    def test_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "scene", "list-nodes", str(scene)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 4
        names = [n["name"] for n in data["nodes"]]
        assert "Main" in names
        assert "Player" in names
        assert "Sprite" in names

    def test_json_has_types(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "scene", "list-nodes", str(scene)])
        data = json.loads(result.output)
        player = next(n for n in data["nodes"] if n["name"] == "Player")
        assert player["type"] == "CharacterBody2D"
        assert player["parent"] == "."

    def test_empty_scene(self, tmp_path: Path) -> None:
        scene = tmp_path / "empty.tscn"
        scene.write_text(
            '[gd_scene format=3]\n\n[node name="Root" type="Node"]\n',
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "scene", "list-nodes", str(scene)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1
