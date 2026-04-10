"""Tests for audio command group."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


def _make_scene(tmp_path: Path, name: str = "main.tscn") -> Path:
    """Create a minimal .tscn scene file for testing."""
    scene_file = tmp_path / name
    scene_file.write_text(
        '[gd_scene format=3]\n'
        '\n'
        '[node name="Main" type="Node2D"]\n',
        encoding="utf-8",
    )
    return scene_file


def _make_scene_with_resource(tmp_path: Path) -> Path:
    """Create a scene with an existing ext_resource."""
    scene_file = tmp_path / "scene.tscn"
    scene_file.write_text(
        '[gd_scene load_steps=2 format=3]\n'
        '\n'
        '[ext_resource type="Script" path="res://scripts/main.gd" id="1_script"]\n'
        '\n'
        '[node name="Main" type="Node2D"]\n'
        'script = ExtResource("1_script")\n',
        encoding="utf-8",
    )
    return scene_file


class TestAddPlayerBasic:
    """Verify audio add-player adds AudioStreamPlayer nodes."""

    def test_add_basic_player(self, tmp_path: Path) -> None:
        scene_file = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audio", "add-player",
            "--scene", str(scene_file),
            "--name", "BGM",
            "--stream", "res://audio/music.ogg",
        ])
        assert result.exit_code == 0, result.output
        text = scene_file.read_text()
        assert 'type="AudioStreamPlayer"' in text
        assert 'name="BGM"' in text
        assert "res://audio/music.ogg" in text

    def test_add_player_2d(self, tmp_path: Path) -> None:
        scene_file = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audio", "add-player",
            "--scene", str(scene_file),
            "--name", "JumpSound",
            "--stream", "res://audio/jump.ogg",
            "--type", "AudioStreamPlayer2D",
        ])
        assert result.exit_code == 0
        assert 'type="AudioStreamPlayer2D"' in scene_file.read_text()

    def test_add_player_3d(self, tmp_path: Path) -> None:
        scene_file = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audio", "add-player",
            "--scene", str(scene_file),
            "--name", "Ambient",
            "--stream", "res://audio/ambient.ogg",
            "--type", "AudioStreamPlayer3D",
        ])
        assert result.exit_code == 0
        assert 'type="AudioStreamPlayer3D"' in scene_file.read_text()

    def test_add_player_without_stream(self, tmp_path: Path) -> None:
        scene_file = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audio", "add-player",
            "--scene", str(scene_file),
            "--name", "DynamicPlayer",
        ])
        assert result.exit_code == 0
        text = scene_file.read_text()
        assert 'name="DynamicPlayer"' in text
        # No ext_resource when no stream specified
        assert "AudioStream" not in text or "ext_resource" not in text.split("DynamicPlayer")[0]


class TestAddPlayerOptions:
    """Verify audio player options."""

    def test_custom_bus(self, tmp_path: Path) -> None:
        scene_file = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "audio", "add-player",
            "--scene", str(scene_file),
            "--name", "SFX",
            "--stream", "res://audio/hit.ogg",
            "--bus", "SFX",
        ])
        text = scene_file.read_text()
        assert '"SFX"' in text

    def test_volume_db(self, tmp_path: Path) -> None:
        scene_file = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "audio", "add-player",
            "--scene", str(scene_file),
            "--name", "Quiet",
            "--stream", "res://audio/bg.ogg",
            "--volume", "-10.0",
        ])
        text = scene_file.read_text()
        assert "volume_db" in text
        assert "-10" in text

    def test_autoplay(self, tmp_path: Path) -> None:
        scene_file = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "audio", "add-player",
            "--scene", str(scene_file),
            "--name", "BGM",
            "--stream", "res://audio/music.ogg",
            "--autoplay",
        ])
        text = scene_file.read_text()
        assert "autoplay = true" in text

    def test_parent_path(self, tmp_path: Path) -> None:
        scene_file = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "audio", "add-player",
            "--scene", str(scene_file),
            "--name", "SFX",
            "--stream", "res://audio/hit.ogg",
            "--parent", "AudioManager",
        ])
        text = scene_file.read_text()
        assert 'parent="AudioManager"' in text


class TestAddPlayerJson:
    """Verify JSON output for add-player."""

    def test_json_output(self, tmp_path: Path) -> None:
        scene_file = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "audio", "add-player",
            "--scene", str(scene_file),
            "--name", "BGM",
            "--stream", "res://audio/music.ogg",
            "--bus", "Music",
            "--autoplay",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["node_name"] == "BGM"
        assert data["player_type"] == "AudioStreamPlayer"
        assert data["stream"] == "res://audio/music.ogg"
        assert data["bus"] == "Music"
        assert data["autoplay"] is True


class TestAddPlayerErrors:
    """Verify error handling for add-player."""

    def test_duplicate_node_name(self, tmp_path: Path) -> None:
        scene_file = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "audio", "add-player",
            "--scene", str(scene_file),
            "--name", "BGM",
            "--stream", "res://audio/music.ogg",
        ])
        result = runner.invoke(cli, [
            "audio", "add-player",
            "--scene", str(scene_file),
            "--name", "BGM",
            "--stream", "res://audio/other.ogg",
        ])
        assert result.exit_code != 0


class TestAddPlayerWithExistingResources:
    """Verify add-player works with scenes that already have resources."""

    def test_adds_to_existing_scene(self, tmp_path: Path) -> None:
        scene_file = _make_scene_with_resource(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audio", "add-player",
            "--scene", str(scene_file),
            "--name", "Music",
            "--stream", "res://audio/bgm.ogg",
            "--autoplay",
        ])
        assert result.exit_code == 0, result.output
        text = scene_file.read_text()
        assert "AudioStream" in text
        assert 'name="Music"' in text


class TestCreateBusLayout:
    """Verify audio bus layout .tres generation."""

    def test_create_basic_layout(self, tmp_path: Path) -> None:
        out = tmp_path / "bus_layout.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audio", "create-bus-layout",
            "--bus", "SFX:Master",
            "--bus", "Music:Master",
            str(out),
        ])
        assert result.exit_code == 0, result.output
        text = out.read_text()
        assert "AudioBusLayout" in text
        assert 'bus/1/name = "SFX"' in text
        assert 'bus/2/name = "Music"' in text
        assert 'bus/1/send = "Master"' in text

    def test_create_nested_buses(self, tmp_path: Path) -> None:
        out = tmp_path / "layout.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audio", "create-bus-layout",
            "--bus", "SFX:Master",
            "--bus", "Music:Master",
            "--bus", "UI:SFX",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert 'bus/3/name = "UI"' in text
        assert 'bus/3/send = "SFX"' in text

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        out = tmp_path / "audio" / "bus_layout.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audio", "create-bus-layout",
            "--bus", "SFX:Master",
            str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()

    def test_invalid_bus_format(self, tmp_path: Path) -> None:
        out = tmp_path / "layout.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audio", "create-bus-layout",
            "--bus", "InvalidNoParen",
            str(out),
        ])
        assert result.exit_code != 0

    def test_json_output(self, tmp_path: Path) -> None:
        out = tmp_path / "layout.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "audio", "create-bus-layout",
            "--bus", "SFX:Master",
            "--bus", "Music:Master",
            str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True
        assert data["bus_count"] == 3  # Master + SFX + Music


class TestListBuses:
    """Verify listing audio buses from a layout file."""

    def test_list_buses(self, tmp_path: Path) -> None:
        layout = tmp_path / "layout.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "audio", "create-bus-layout",
            "--bus", "SFX:Master",
            "--bus", "Music:Master",
            str(layout),
        ])
        result = runner.invoke(cli, [
            "audio", "list-buses", str(layout),
        ])
        assert result.exit_code == 0
        assert "Master" in result.output
        assert "SFX" in result.output
        assert "Music" in result.output

    def test_list_buses_json(self, tmp_path: Path) -> None:
        layout = tmp_path / "layout.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "audio", "create-bus-layout",
            "--bus", "SFX:Master",
            str(layout),
        ])
        result = runner.invoke(cli, [
            "-j", "audio", "list-buses", str(layout),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 2
        assert data["buses"][0]["name"] == "Master"
        assert data["buses"][1]["name"] == "SFX"
