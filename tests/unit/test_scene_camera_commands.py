"""Tests for scene add-camera command."""

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


class TestAddCamera:
    """Verify scene add-camera creates Camera2D nodes."""

    def test_basic_camera(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-camera",
            "--scene", str(scene),
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert "Camera2D" in text
        assert "position_smoothing_enabled" in text

    def test_zoom(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-camera",
            "--scene", str(scene),
            "--zoom", "2",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "Vector2(2" in text

    def test_with_limits(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-camera",
            "--scene", str(scene),
            "--limit-left", "0",
            "--limit-top", "0",
            "--limit-right", "1920",
            "--limit-bottom", "1080",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "limit_left = 0" in text
        assert "limit_right = 1920" in text

    def test_with_parent(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-camera",
            "--scene", str(scene),
            "--parent", "Player",
        ])
        assert result.exit_code == 0
        assert 'parent="Player"' in scene.read_text()

    def test_no_smoothing(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-camera",
            "--scene", str(scene),
            "--no-smoothing",
        ])
        assert result.exit_code == 0
        assert "smoothing" not in scene.read_text()

    def test_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "add-camera",
            "--scene", str(scene),
            "--zoom", "3",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["zoom"] == 3.0
        assert data["smoothing"] is True

    def test_duplicate_error(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "scene", "add-camera", "--scene", str(scene),
        ])
        result = runner.invoke(cli, [
            "scene", "add-camera", "--scene", str(scene),
        ])
        assert result.exit_code != 0
