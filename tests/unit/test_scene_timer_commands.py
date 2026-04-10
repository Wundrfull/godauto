"""Tests for scene add-timer command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


def _make_scene(tmp_path: Path) -> Path:
    scene_file = tmp_path / "main.tscn"
    scene_file.write_text(
        '[gd_scene format=3]\n\n[node name="Main" type="Node2D"]\n',
        encoding="utf-8",
    )
    return scene_file


class TestAddTimer:
    """Verify scene add-timer creates Timer nodes."""

    def test_basic_timer(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-timer",
            "--scene", str(scene),
            "--name", "SpawnTimer",
            "--wait", "2.0",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert 'type="Timer"' in text
        assert "wait_time = 2" in text

    def test_one_shot_timer(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-timer",
            "--scene", str(scene),
            "--name", "Cooldown",
            "--wait", "0.5",
            "--one-shot",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "one_shot = true" in text

    def test_autostart_timer(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-timer",
            "--scene", str(scene),
            "--name", "GameTimer",
            "--wait", "1.0",
            "--autostart",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "autostart = true" in text

    def test_timer_with_connection(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-timer",
            "--scene", str(scene),
            "--name", "SpawnTimer",
            "--wait", "3.0",
            "--autostart",
            "--connect", "_on_spawn_timer_timeout",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "[connection" in text
        assert "timeout" in text
        assert "_on_spawn_timer_timeout" in text

    def test_timer_with_parent(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "scene", "add-timer",
            "--scene", str(scene),
            "--name", "AttackCooldown",
            "--wait", "0.8",
            "--parent", "Player",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert 'parent="Player"' in text

    def test_duplicate_error(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "scene", "add-timer",
            "--scene", str(scene),
            "--name", "Timer",
            "--wait", "1.0",
        ])
        result = runner.invoke(cli, [
            "scene", "add-timer",
            "--scene", str(scene),
            "--name", "Timer",
            "--wait", "2.0",
        ])
        assert result.exit_code != 0

    def test_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "scene", "add-timer",
            "--scene", str(scene),
            "--name", "Timer",
            "--wait", "1.5",
            "--one-shot",
            "--autostart",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["wait_time"] == 1.5
        assert data["one_shot"] is True
        assert data["autostart"] is True
