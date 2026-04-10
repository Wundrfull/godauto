"""Tests for project add-layer command."""

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


class TestAddLayerBasic:
    """Verify add-layer names layers in project.godot."""

    def test_add_physics_layer(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-layer",
            "--type", "2d_physics",
            "--index", "1",
            "--name", "player",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        text = (tmp_path / "project.godot").read_text()
        assert "[layer_names]" in text
        assert 'layer_names/2d_physics/layer_1="player"' in text

    def test_add_render_layer(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-layer",
            "--type", "2d_render",
            "--index", "1",
            "--name", "foreground",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "project.godot").read_text()
        assert "2d_render/layer_1" in text

    def test_add_navigation_layer(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-layer",
            "--type", "2d_navigation",
            "--index", "1",
            "--name", "walkable",
            str(tmp_path),
        ])
        assert result.exit_code == 0


class TestAddLayerMultiple:
    """Verify adding multiple layers."""

    def test_add_multiple_physics_layers(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        layers = [
            (1, "player"), (2, "enemy"), (3, "projectile"), (4, "terrain"),
        ]
        for index, name in layers:
            result = runner.invoke(cli, [
                "project", "add-layer",
                "--type", "2d_physics",
                "--index", str(index),
                "--name", name,
                str(tmp_path),
            ])
            assert result.exit_code == 0, f"Failed for {name}: {result.output}"
        text = (tmp_path / "project.godot").read_text()
        for index, name in layers:
            assert f'layer_{index}="{name}"' in text


class TestAddLayerErrors:
    """Verify error handling."""

    def test_invalid_index_zero(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-layer",
            "--type", "2d_physics",
            "--index", "0",
            "--name", "invalid",
            str(tmp_path),
        ])
        assert result.exit_code != 0

    def test_invalid_index_33(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "project", "add-layer",
            "--type", "2d_physics",
            "--index", "33",
            "--name", "invalid",
            str(tmp_path),
        ])
        assert result.exit_code != 0


class TestAddLayerJson:
    """Verify JSON output."""

    def test_json_output(self, tmp_path: Path) -> None:
        _make_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "project", "add-layer",
            "--type", "2d_physics",
            "--index", "1",
            "--name", "player",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["layer_type"] == "2d_physics"
        assert data["index"] == 1
        assert data["name"] == "player"
