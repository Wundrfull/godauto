"""Tests for script attach command."""

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
        '[node name="Player" type="CharacterBody2D" parent="."]\n',
        encoding="utf-8",
    )
    return scene_file


class TestScriptAttach:
    """Verify script attach wires scripts to scene nodes."""

    def test_attach_to_root(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "attach",
            "--scene", str(scene),
            "--node", "Main",
            "--script", "res://scripts/main.gd",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert "res://scripts/main.gd" in text
        assert "Script" in text
        assert "ExtResource" in text

    def test_attach_to_child(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "attach",
            "--scene", str(scene),
            "--node", "Player",
            "--script", "res://scripts/player.gd",
        ])
        assert result.exit_code == 0

    def test_node_not_found(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "attach",
            "--scene", str(scene),
            "--node", "Missing",
            "--script", "res://scripts/test.gd",
        ])
        assert result.exit_code != 0

    def test_script_already_attached(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "script", "attach",
            "--scene", str(scene),
            "--node", "Main",
            "--script", "res://scripts/main.gd",
        ])
        result = runner.invoke(cli, [
            "script", "attach",
            "--scene", str(scene),
            "--node", "Main",
            "--script", "res://scripts/other.gd",
        ])
        assert result.exit_code != 0

    def test_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "script", "attach",
            "--scene", str(scene),
            "--node", "Player",
            "--script", "res://scripts/player.gd",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["attached"] is True
        assert data["node"] == "Player"
        assert data["script"] == "res://scripts/player.gd"

    def test_attach_multiple_scripts(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result1 = runner.invoke(cli, [
            "script", "attach",
            "--scene", str(scene),
            "--node", "Main",
            "--script", "res://scripts/main.gd",
        ])
        result2 = runner.invoke(cli, [
            "script", "attach",
            "--scene", str(scene),
            "--node", "Player",
            "--script", "res://scripts/player.gd",
        ])
        assert result1.exit_code == 0
        assert result2.exit_code == 0
        text = scene.read_text()
        assert "main.gd" in text
        assert "player.gd" in text
