"""Tests for script create command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gdauto.cli import cli


class TestScriptCreateBasic:
    """Verify script create generates valid GDScript files."""

    def test_minimal_script(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        result = runner.invoke(cli, ["script", "create", str(out)])
        assert result.exit_code == 0, result.output
        text = out.read_text()
        assert "extends Node2D" in text
        assert "func _ready() -> void:" in text

    def test_custom_extends(self, tmp_path: Path) -> None:
        out = tmp_path / "player.gd"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "create", "--extends", "CharacterBody2D", str(out),
        ])
        assert result.exit_code == 0
        assert "extends CharacterBody2D" in out.read_text()

    def test_class_name(self, tmp_path: Path) -> None:
        out = tmp_path / "player.gd"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "create", "--class-name", "Player",
            "--extends", "CharacterBody2D", str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "class_name Player" in text
        assert "extends CharacterBody2D" in text

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        out = tmp_path / "scripts" / "enemies" / "slime.gd"
        runner = CliRunner()
        result = runner.invoke(cli, ["script", "create", str(out)])
        assert result.exit_code == 0
        assert out.exists()


class TestScriptCreateSignals:
    """Verify signal declarations."""

    def test_single_signal(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "create", "--signal", "died", str(out),
        ])
        assert result.exit_code == 0
        assert "signal died" in out.read_text()

    def test_signal_with_params(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "create",
            "--signal", "health_changed(amount: int)",
            str(out),
        ])
        assert result.exit_code == 0
        assert "signal health_changed(amount: int)" in out.read_text()

    def test_multiple_signals(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "create",
            "--signal", "died",
            "--signal", "hit(damage: float)",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "signal died" in text
        assert "signal hit(damage: float)" in text


class TestScriptCreateExports:
    """Verify @export variable generation."""

    def test_export_with_default(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "create",
            "--export", "speed:float=200.0",
            str(out),
        ])
        assert result.exit_code == 0
        assert "@export var speed: float = 200.0" in out.read_text()

    def test_export_without_default(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "create",
            "--export", "health:int",
            str(out),
        ])
        assert result.exit_code == 0
        assert "@export var health: int" in out.read_text()

    def test_multiple_exports(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "create",
            "--export", "speed:float=200.0",
            "--export", "health:int=100",
            "--export", "name:String",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "@export var speed: float = 200.0" in text
        assert "@export var health: int = 100" in text
        assert "@export var name: String" in text

    def test_invalid_export_format(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "create", "--export", "invalid_no_type", str(out),
        ])
        assert result.exit_code != 0


class TestScriptCreateOnready:
    """Verify @onready variable generation."""

    def test_onready_var(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "create",
            "--onready", "sprite:Sprite2D=Sprite2D",
            str(out),
        ])
        assert result.exit_code == 0
        assert "@onready var sprite: Sprite2D = $Sprite2D" in out.read_text()

    def test_invalid_onready_no_path(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "create", "--onready", "sprite:Sprite2D", str(out),
        ])
        assert result.exit_code != 0

    def test_invalid_onready_no_type(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "create", "--onready", "sprite=Sprite2D", str(out),
        ])
        assert result.exit_code != 0


class TestScriptCreateMethods:
    """Verify lifecycle method generation."""

    def test_ready_default_on(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        runner.invoke(cli, ["script", "create", str(out)])
        assert "func _ready() -> void:" in out.read_text()

    def test_no_ready(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        runner.invoke(cli, ["script", "create", "--no-ready", str(out)])
        assert "_ready" not in out.read_text()

    def test_process(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        runner.invoke(cli, ["script", "create", "--process", str(out)])
        assert "func _process(delta: float) -> void:" in out.read_text()

    def test_physics_process(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        runner.invoke(cli, ["script", "create", "--physics", str(out)])
        assert "func _physics_process(delta: float) -> void:" in out.read_text()

    def test_input(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        runner.invoke(cli, ["script", "create", "--input", str(out)])
        assert "func _unhandled_input(event: InputEvent) -> void:" in out.read_text()

    def test_all_methods(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        runner.invoke(cli, [
            "script", "create",
            "--ready", "--process", "--physics", "--input",
            str(out),
        ])
        text = out.read_text()
        assert "func _ready" in text
        assert "func _process" in text
        assert "func _physics_process" in text
        assert "func _unhandled_input" in text


class TestScriptCreateJson:
    """Verify JSON output."""

    def test_json_output(self, tmp_path: Path) -> None:
        out = tmp_path / "test.gd"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "script", "create",
            "--extends", "Area2D",
            "--signal", "collected",
            "--export", "value:int=10",
            str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True
        assert data["extends"] == "Area2D"
        assert data["signals"] == ["collected"]
        assert data["exports"] == ["value:int=10"]


class TestScriptCreateFullExample:
    """Integration test: generate a realistic game script."""

    def test_player_controller(self, tmp_path: Path) -> None:
        """Generate a complete player controller script."""
        out = tmp_path / "player.gd"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "script", "create",
            "--extends", "CharacterBody2D",
            "--class-name", "Player",
            "--signal", "died",
            "--signal", "health_changed(new_health: int)",
            "--export", "speed:float=200.0",
            "--export", "max_health:int=100",
            "--onready", "sprite:AnimatedSprite2D=AnimatedSprite2D",
            "--onready", "collision:CollisionShape2D=CollisionShape2D",
            "--ready", "--physics", "--input",
            str(out),
        ])
        assert result.exit_code == 0, result.output
        text = out.read_text()
        assert "class_name Player" in text
        assert "extends CharacterBody2D" in text
        assert "signal died" in text
        assert "signal health_changed(new_health: int)" in text
        assert "@export var speed: float = 200.0" in text
        assert "@export var max_health: int = 100" in text
        assert "@onready var sprite: AnimatedSprite2D = $AnimatedSprite2D" in text
        assert "@onready var collision: CollisionShape2D = $CollisionShape2D" in text
        assert "func _ready" in text
        assert "func _physics_process" in text
        assert "func _unhandled_input" in text
