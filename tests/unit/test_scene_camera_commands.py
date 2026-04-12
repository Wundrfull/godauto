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


def _make_project_with_stretch(tmp_path: Path, mode: str) -> None:
    (tmp_path / "project.godot").write_text(
        'config_version=5\n\n[display]\n\n'
        f'window/stretch/mode="{mode}"\n',
        encoding="utf-8",
    )


class TestCameraZoomWarning:
    """Verify zoom + stretch compatibility warning."""

    def test_warns_zoom_with_viewport_stretch(self, tmp_path: Path) -> None:
        _make_project_with_stretch(tmp_path, "viewport")
        scene = _make_scene(tmp_path)
        result = CliRunner().invoke(cli, [
            "scene", "add-camera", "--scene", str(scene), "--zoom", "2",
        ])
        assert result.exit_code == 0
        assert "jitter" in result.output

    def test_warns_zoom_with_canvas_items_stretch(self, tmp_path: Path) -> None:
        _make_project_with_stretch(tmp_path, "canvas_items")
        scene = _make_scene(tmp_path)
        result = CliRunner().invoke(cli, [
            "scene", "add-camera", "--scene", str(scene), "--zoom", "3",
        ])
        assert result.exit_code == 0
        assert "jitter" in result.output

    def test_no_warning_zoom_1(self, tmp_path: Path) -> None:
        _make_project_with_stretch(tmp_path, "viewport")
        scene = _make_scene(tmp_path)
        result = CliRunner().invoke(cli, [
            "scene", "add-camera", "--scene", str(scene), "--zoom", "1",
        ])
        assert result.exit_code == 0
        assert "jitter" not in result.output

    def test_no_warning_disabled_stretch(self, tmp_path: Path) -> None:
        _make_project_with_stretch(tmp_path, "disabled")
        scene = _make_scene(tmp_path)
        result = CliRunner().invoke(cli, [
            "scene", "add-camera", "--scene", str(scene), "--zoom", "2",
        ])
        assert result.exit_code == 0
        assert "jitter" not in result.output

    def test_force_suppresses_warning(self, tmp_path: Path) -> None:
        _make_project_with_stretch(tmp_path, "viewport")
        scene = _make_scene(tmp_path)
        result = CliRunner().invoke(cli, [
            "scene", "add-camera", "--scene", str(scene), "--zoom", "2", "--force",
        ])
        assert result.exit_code == 0
        assert "jitter" not in result.output

    def test_json_includes_warning(self, tmp_path: Path) -> None:
        _make_project_with_stretch(tmp_path, "viewport")
        scene = _make_scene(tmp_path)
        result = CliRunner().invoke(cli, [
            "-j", "scene", "add-camera", "--scene", str(scene), "--zoom", "2",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "warning" in data
        assert "jitter" in data["warning"]

    def test_no_warning_without_project(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        # No project.godot in tmp_path
        result = CliRunner().invoke(cli, [
            "scene", "add-camera", "--scene", str(scene), "--zoom", "2",
        ])
        assert result.exit_code == 0
        assert "jitter" not in result.output
