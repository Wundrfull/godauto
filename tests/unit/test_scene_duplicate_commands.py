"""Tests for scene duplicate-node command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


def _make_scene(tmp_path: Path) -> Path:
    scene_file = tmp_path / "level.tscn"
    scene_file.write_text(
        '[gd_scene format=3]\n\n'
        '[node name="Level" type="Node2D"]\n\n'
        '[node name="Enemy" type="CharacterBody2D" parent="."]\n',
        encoding="utf-8",
    )
    return scene_file


class TestDuplicateNode:
    """Verify scene duplicate-node creates copies."""

    def test_basic_duplicate(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "duplicate-node",
            "--scene", str(scene),
            "--node", "Enemy",
            "--new-name", "Enemy2",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert 'name="Enemy"' in text
        assert 'name="Enemy2"' in text

    def test_duplicate_with_override(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "duplicate-node",
            "--scene", str(scene),
            "--node", "Enemy",
            "--new-name", "Enemy2",
            "--property", "visible=false",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "visible = false" in text

    def test_source_not_found(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "duplicate-node",
            "--scene", str(scene),
            "--node", "Missing",
            "--new-name", "Copy",
        ])
        assert result.exit_code != 0

    def test_new_name_exists(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "duplicate-node",
            "--scene", str(scene),
            "--node", "Enemy",
            "--new-name", "Enemy",
        ])
        assert result.exit_code != 0

    def test_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "duplicate-node",
            "--scene", str(scene),
            "--node", "Enemy",
            "--new-name", "Enemy3",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["duplicated"] is True
        assert data["source"] == "Enemy"
        assert data["new_name"] == "Enemy3"

    def test_multiple_duplicates(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        for i in range(2, 6):
            result = runner.invoke(cli, [
                "scene", "duplicate-node",
                "--scene", str(scene),
                "--node", "Enemy",
                "--new-name", f"Enemy{i}",
            ])
            assert result.exit_code == 0, f"Failed for Enemy{i}"
        text = scene.read_text()
        for i in range(2, 6):
            assert f"Enemy{i}" in text
