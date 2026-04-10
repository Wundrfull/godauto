"""Tests for physics command group."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


def _make_scene(tmp_path: Path) -> Path:
    """Create a minimal scene for testing."""
    scene_file = tmp_path / "main.tscn"
    scene_file.write_text(
        '[gd_scene format=3]\n'
        '\n'
        '[node name="Main" type="Node2D"]\n',
        encoding="utf-8",
    )
    return scene_file


class TestAddBodyBasic:
    """Verify physics add-body creates physics bodies with shapes."""

    def test_add_character_body(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "physics", "add-body",
            "--scene", str(scene),
            "--name", "Player",
            "--type", "character",
            "--shape", "rectangle",
            "--size", "16,32",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert "CharacterBody2D" in text
        assert "CollisionShape2D" in text
        assert "RectangleShape2D" in text

    def test_add_static_body(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "physics", "add-body",
            "--scene", str(scene),
            "--name", "Wall",
            "--type", "static",
            "--shape", "rectangle",
            "--size", "64,16",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "StaticBody2D" in text

    def test_add_rigid_body(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "physics", "add-body",
            "--scene", str(scene),
            "--name", "Ball",
            "--type", "rigid",
            "--shape", "circle",
            "--size", "16",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "RigidBody2D" in text
        assert "CircleShape2D" in text

    def test_add_area(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "physics", "add-body",
            "--scene", str(scene),
            "--name", "Pickup",
            "--type", "area",
            "--shape", "circle",
            "--size", "24",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "Area2D" in text
        assert "CircleShape2D" in text


class TestAddBodyShapes:
    """Verify different collision shape types."""

    def test_rectangle_shape(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "physics", "add-body",
            "--scene", str(scene),
            "--name", "Box",
            "--type", "static",
            "--shape", "rectangle",
            "--size", "48,24",
        ])
        text = scene.read_text()
        assert "RectangleShape2D" in text
        assert "Vector2(48" in text

    def test_circle_shape(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "physics", "add-body",
            "--scene", str(scene),
            "--name", "Ball",
            "--type", "rigid",
            "--shape", "circle",
            "--size", "20",
        ])
        text = scene.read_text()
        assert "CircleShape2D" in text
        assert "radius" in text

    def test_capsule_shape(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "physics", "add-body",
            "--scene", str(scene),
            "--name", "Player",
            "--type", "character",
            "--shape", "capsule",
            "--size", "16,48",
        ])
        text = scene.read_text()
        assert "CapsuleShape2D" in text


class TestAddBodyJson:
    """Verify JSON output."""

    def test_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "physics", "add-body",
            "--scene", str(scene),
            "--name", "Player",
            "--type", "character",
            "--shape", "rectangle",
            "--size", "16,32",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["body_type"] == "CharacterBody2D"
        assert data["shape_type"] == "rectangle"


class TestAddBodyErrors:
    """Verify error handling."""

    def test_duplicate_name(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "physics", "add-body",
            "--scene", str(scene),
            "--name", "Player",
            "--type", "character",
            "--size", "16,32",
        ])
        result = runner.invoke(cli, [
            "physics", "add-body",
            "--scene", str(scene),
            "--name", "Player",
            "--type", "static",
            "--size", "16,32",
        ])
        assert result.exit_code != 0


class TestAddShape:
    """Verify adding shapes to existing physics bodies."""

    def test_add_shape_to_body(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        # First add a body
        runner.invoke(cli, [
            "physics", "add-body",
            "--scene", str(scene),
            "--name", "Player",
            "--type", "character",
            "--size", "16,32",
        ])
        # Then add another shape
        result = runner.invoke(cli, [
            "physics", "add-shape",
            "--scene", str(scene),
            "--parent", "Player",
            "--shape", "circle",
            "--size", "24",
            "--name", "HurtBox",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert "HurtBox" in text
        assert "CircleShape2D" in text

    def test_add_shape_json(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "physics", "add-shape",
            "--scene", str(scene),
            "--parent", "SomeBody",
            "--shape", "rectangle",
            "--size", "32,32",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["shape_type"] == "rectangle"


class TestMultipleBodies:
    """Verify adding multiple physics bodies to a scene."""

    def test_add_player_and_enemies(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        bodies = [
            ("Player", "character", "capsule", "16,32"),
            ("Wall", "static", "rectangle", "64,16"),
            ("Coin", "area", "circle", "12"),
        ]
        for name, body_type, shape, size in bodies:
            result = runner.invoke(cli, [
                "physics", "add-body",
                "--scene", str(scene),
                "--name", name,
                "--type", body_type,
                "--shape", shape,
                "--size", size,
            ])
            assert result.exit_code == 0, f"Failed for {name}: {result.output}"

        text = scene.read_text()
        assert "CharacterBody2D" in text
        assert "StaticBody2D" in text
        assert "Area2D" in text
