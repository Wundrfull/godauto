"""Tests for particle command group."""

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


class TestParticleAdd:
    """Verify particle add creates CPUParticles2D nodes."""

    def test_add_with_preset(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "particle", "add",
            "--scene", str(scene),
            "--name", "Explosion",
            "--preset", "explosion",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert "CPUParticles2D" in text
        assert 'name="Explosion"' in text

    def test_add_sparkle(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "particle", "add",
            "--scene", str(scene),
            "--name", "Sparkle",
            "--preset", "sparkle",
        ])
        assert result.exit_code == 0

    def test_add_fire(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "particle", "add",
            "--scene", str(scene),
            "--name", "Fire",
            "--preset", "fire",
        ])
        assert result.exit_code == 0

    def test_add_custom(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "particle", "add",
            "--scene", str(scene),
            "--name", "Custom",
            "--amount", "32",
            "--lifetime", "2.0",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "CPUParticles2D" in text
        assert "amount = 32" in text

    def test_add_with_parent(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "particle", "add",
            "--scene", str(scene),
            "--name", "Trail",
            "--preset", "dust",
            "--parent", "Player",
        ])
        assert result.exit_code == 0
        assert 'parent="Player"' in scene.read_text()

    def test_override_preset(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "particle", "add",
            "--scene", str(scene),
            "--name", "BigExplosion",
            "--preset", "explosion",
            "--amount", "64",
            "--lifetime", "2.0",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "amount = 64" in text

    def test_duplicate_error(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "particle", "add",
            "--scene", str(scene),
            "--name", "FX",
            "--preset", "sparkle",
        ])
        result = runner.invoke(cli, [
            "particle", "add",
            "--scene", str(scene),
            "--name", "FX",
            "--preset", "fire",
        ])
        assert result.exit_code != 0

    def test_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "particle", "add",
            "--scene", str(scene),
            "--name", "Boom",
            "--preset", "explosion",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["preset"] == "explosion"


class TestParticleAllPresets:
    """Verify all presets work."""

    def test_all_presets(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        presets = ["explosion", "sparkle", "fire", "smoke", "rain", "dust"]
        for p in presets:
            result = runner.invoke(cli, [
                "particle", "add",
                "--scene", str(scene),
                "--name", f"FX_{p}",
                "--preset", p,
            ])
            assert result.exit_code == 0, f"Failed for preset '{p}': {result.output}"


class TestListPresets:
    """Verify listing particle presets."""

    def test_list_presets(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["particle", "list-presets"])
        assert result.exit_code == 0
        assert "explosion" in result.output
        assert "sparkle" in result.output

    def test_list_presets_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "particle", "list-presets"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 6
