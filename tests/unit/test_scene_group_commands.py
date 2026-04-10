"""Tests for scene add-group command."""

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
        '[node name="Enemy" type="CharacterBody2D" parent="."]\n\n'
        '[node name="Coin" type="Area2D" parent="."]\n',
        encoding="utf-8",
    )
    return scene_file


class TestAddGroup:
    """Verify scene add-group assigns nodes to groups."""

    def test_add_single_group(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-group",
            "--scene", str(scene),
            "--node", "Enemy",
            "--group", "enemies",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert "enemies" in text
        assert "groups=" in text

    def test_add_multiple_groups(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-group",
            "--scene", str(scene),
            "--node", "Enemy",
            "--group", "enemies",
            "--group", "damageable",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "enemies" in text
        assert "damageable" in text

    def test_add_group_to_different_nodes(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "scene", "add-group",
            "--scene", str(scene),
            "--node", "Enemy",
            "--group", "enemies",
        ])
        result = runner.invoke(cli, [
            "scene", "add-group",
            "--scene", str(scene),
            "--node", "Coin",
            "--group", "collectibles",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "enemies" in text
        assert "collectibles" in text

    def test_node_not_found_error(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-group",
            "--scene", str(scene),
            "--node", "Nonexistent",
            "--group", "test",
        ])
        assert result.exit_code != 0

    def test_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "add-group",
            "--scene", str(scene),
            "--node", "Enemy",
            "--group", "enemies",
            "--group", "damageable",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["updated"] is True
        assert "enemies" in data["groups_added"]
        assert "damageable" in data["groups_added"]

    def test_duplicate_group_not_added_twice(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "scene", "add-group",
            "--scene", str(scene),
            "--node", "Enemy",
            "--group", "enemies",
        ])
        result = runner.invoke(cli, [
            "-j", "scene", "add-group",
            "--scene", str(scene),
            "--node", "Enemy",
            "--group", "enemies",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        # Should not add duplicate
        assert "enemies" not in data["groups_added"]
