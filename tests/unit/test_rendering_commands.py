"""Tests for project set-rendering command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


def _make_project(tmp_path: Path) -> Path:
    project_godot = tmp_path / "project.godot"
    project_godot.write_text(
        'config_version=5\n\n[application]\n\nconfig/name="TestGame"\n',
        encoding="utf-8",
    )
    return project_godot


class TestSetRendering:
    """Verify project set-rendering configures renderer."""

    def test_set_method(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-rendering",
            "--method", "gl_compatibility",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = (tmp_path / "project.godot").read_text()
        assert 'rendering_method="gl_compatibility"' in text

    def test_set_msaa_2d(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-rendering",
            "--msaa-2d", "4x",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "project.godot").read_text()
        assert "msaa_2d=2" in text  # 4x = value 2

    def test_set_msaa_3d(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-rendering",
            "--msaa-3d", "8x",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "project.godot").read_text()
        assert "msaa_3d=3" in text

    def test_no_options_error(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-rendering", str(tmp_path),
        ])
        assert result.exit_code != 0

    def test_json_output(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "set-rendering",
            "--method", "forward_plus",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["updated"] is True
        assert "method=forward_plus" in data["changes"]

    def test_combined_settings(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "set-rendering",
            "--method", "mobile",
            "--msaa-2d", "2x",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "project.godot").read_text()
        assert "mobile" in text
        assert "msaa_2d" in text
