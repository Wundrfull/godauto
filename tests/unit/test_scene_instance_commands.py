"""Tests for scene add-instance command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


def _make_scene(tmp_path: Path) -> Path:
    scene_file = tmp_path / "level.tscn"
    scene_file.write_text(
        '[gd_scene format=3]\n\n[node name="Level" type="Node2D"]\n',
        encoding="utf-8",
    )
    return scene_file


class TestAddInstance:
    """Verify scene add-instance adds sub-scene instances."""

    def test_add_basic_instance(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-instance",
            "--scene", str(scene),
            "--name", "Player",
            "--instance", "res://scenes/player.tscn",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert "PackedScene" in text
        assert "res://scenes/player.tscn" in text
        assert 'name="Player"' in text

    def test_instance_with_parent(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-instance",
            "--scene", str(scene),
            "--name", "Enemy",
            "--instance", "res://scenes/enemy.tscn",
            "--parent", "Enemies",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert 'parent="Enemies"' in text

    def test_instance_with_property_override(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-instance",
            "--scene", str(scene),
            "--name", "Enemy1",
            "--instance", "res://scenes/enemy.tscn",
            "--property", "position=Vector2(100, 50)",
        ])
        assert result.exit_code == 0

    def test_multiple_instances(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        instances = [
            ("Player", "res://scenes/player.tscn"),
            ("Enemy1", "res://scenes/enemy.tscn"),
            ("Enemy2", "res://scenes/enemy.tscn"),
        ]
        for name, inst_path in instances:
            result = runner.invoke(cli, [
                "scene", "add-instance",
                "--scene", str(scene),
                "--name", name,
                "--instance", inst_path,
            ])
            assert result.exit_code == 0, f"Failed for {name}"
        text = scene.read_text()
        assert "Player" in text
        assert "Enemy1" in text
        assert "Enemy2" in text

    def test_duplicate_error(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "scene", "add-instance",
            "--scene", str(scene),
            "--name", "Player",
            "--instance", "res://scenes/player.tscn",
        ])
        result = runner.invoke(cli, [
            "scene", "add-instance",
            "--scene", str(scene),
            "--name", "Player",
            "--instance", "res://scenes/other.tscn",
        ])
        assert result.exit_code != 0

    def test_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "add-instance",
            "--scene", str(scene),
            "--name", "Player",
            "--instance", "res://scenes/player.tscn",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["name"] == "Player"
        assert data["instance"] == "res://scenes/player.tscn"
