"""Tests for project set-display command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gdauto.cli import cli


def _make_project(tmp_path: Path) -> Path:
    project_godot = tmp_path / "project.godot"
    project_godot.write_text(
        'config_version=5\n'
        '\n'
        '[application]\n'
        '\n'
        'config/name="TestGame"\n',
        encoding="utf-8",
    )
    return project_godot


class TestSetDisplayResolution:
    """Verify viewport and window size settings."""

    def test_set_viewport_size(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-display",
            "--width", "320", "--height", "180",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = (tmp_path / "project.godot").read_text()
        assert "window/size/viewport_width=320" in text
        assert "window/size/viewport_height=180" in text

    def test_set_window_override(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-display",
            "--window-width", "1280",
            "--window-height", "720",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "project.godot").read_text()
        assert "window_width_override=1280" in text
        assert "window_height_override=720" in text

    def test_set_both(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-display",
            "--width", "480", "--height", "270",
            "--window-width", "1920", "--window-height", "1080",
            str(tmp_path),
        ])
        assert result.exit_code == 0


class TestSetDisplayStretch:
    """Verify stretch mode settings."""

    def test_set_stretch_mode(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-display",
            "--stretch-mode", "viewport",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "project.godot").read_text()
        assert 'window/stretch/mode="viewport"' in text

    def test_set_stretch_aspect(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-display",
            "--stretch-aspect", "keep",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "project.godot").read_text()
        assert 'window/stretch/aspect="keep"' in text


class TestSetDisplayTexture:
    """Verify texture filter settings."""

    def test_nearest_filter(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-display",
            "--texture-filter", "nearest",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "project.godot").read_text()
        assert "default_texture_filter=0" in text

    def test_linear_filter(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-display",
            "--texture-filter", "linear",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "project.godot").read_text()
        assert "default_texture_filter=1" in text


class TestSetDisplayJson:
    """Verify JSON output."""

    def test_json_output(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "set-display",
            "--width", "320", "--height", "180",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["updated"] is True
        assert data["count"] == 2


class TestSetDisplayErrors:
    """Verify error handling."""

    def test_no_options(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-display", str(tmp_path),
        ])
        assert result.exit_code != 0

    def test_no_project(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-display",
            "--width", "320",
            "/nonexistent",
        ])
        assert result.exit_code != 0


class TestSetDisplayUpdateExisting:
    """Verify updating existing settings."""

    def test_update_existing_value(self, tmp_path: Path) -> None:
        project_godot = tmp_path / "project.godot"
        project_godot.write_text(
            'config_version=5\n'
            '\n'
            '[display]\n'
            '\n'
            'window/size/viewport_width=640\n',
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-display",
            "--width", "320",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = project_godot.read_text()
        assert "viewport_width=320" in text
        assert "viewport_width=640" not in text


class TestPixelArtSetup:
    """Integration test: configure for pixel art game."""

    def test_pixel_art_config(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-display",
            "--width", "480", "--height", "270",
            "--window-width", "1920", "--window-height", "1080",
            "--stretch-mode", "viewport",
            "--stretch-aspect", "keep",
            "--texture-filter", "nearest",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "project.godot").read_text()
        assert "viewport_width=480" in text
        assert "viewport_height=270" in text
        assert "default_texture_filter=0" in text
