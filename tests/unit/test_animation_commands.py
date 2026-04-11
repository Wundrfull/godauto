"""Tests for animation command group."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


class TestCreateLibraryBasic:
    """Verify animation create-library generates valid .tres files."""

    def test_single_animation(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            str(out),
        ])
        assert result.exit_code == 0, result.output
        text = out.read_text()
        assert "AnimationLibrary" in text
        assert 'type="Animation"' in text
        assert "idle" in text

    def test_multiple_animations(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            "--name", "walk",
            "--name", "attack",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "idle" in text
        assert "walk" in text
        assert "attack" in text

    def test_custom_lengths(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle", "--length", "2.0",
            "--name", "attack", "--length", "0.5",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "2" in text  # length = 2
        assert "0.5" in text  # length = 0.5

    def test_loop_mode(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle", "--loop", "linear",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "loop_mode = 1" in text

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        out = tmp_path / "res" / "animations" / "player.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()


class TestCreateLibraryJson:
    """Verify JSON output for create-library."""

    def test_json_output(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "animation", "create-library",
            "--name", "idle",
            "--name", "walk",
            str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True
        assert data["animations"] == ["idle", "walk"]
        assert data["count"] == 2


class TestAddTrack:
    """Verify adding tracks to animations."""

    def _make_library(self, tmp_path: Path) -> Path:
        """Create a library with one animation for testing."""
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle", "--length", "1.0", "--loop", "linear",
            str(out),
        ])
        return out

    def test_add_single_track(self, tmp_path: Path) -> None:
        lib = self._make_library(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(lib),
            "--animation", "idle",
            "--property", "Sprite2D:modulate:a",
            "--keyframe", "0=1.0",
            "--keyframe", "0.5=0.5",
            "--keyframe", "1.0=1.0",
        ])
        assert result.exit_code == 0, result.output
        text = lib.read_text()
        assert "tracks/0/type" in text
        assert "Sprite2D:modulate:a" in text
        # Godot 4 dict format with separate times/transitions/values arrays
        assert '"times"' in text
        assert '"transitions"' in text
        assert '"values"' in text
        assert '"update"' in text
        assert "PackedFloat32Array" in text

    def test_add_multiple_tracks(self, tmp_path: Path) -> None:
        lib = self._make_library(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(lib),
            "--animation", "idle",
            "--property", ".:position:x",
            "--keyframe", "0=0",
            "--keyframe", "1.0=10",
        ])
        result = runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(lib),
            "--animation", "idle",
            "--property", ".:position:y",
            "--keyframe", "0=0",
            "--keyframe", "1.0=5",
        ])
        assert result.exit_code == 0
        text = lib.read_text()
        assert "tracks/0/" in text
        assert "tracks/1/" in text

    def test_cubic_interpolation(self, tmp_path: Path) -> None:
        lib = self._make_library(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(lib),
            "--animation", "idle",
            "--property", ".:scale:x",
            "--keyframe", "0=1",
            "--keyframe", "1.0=2",
            "--interp", "cubic",
        ])
        assert result.exit_code == 0
        text = lib.read_text()
        assert "interp = 2" in text  # cubic = 2

    def test_json_output(self, tmp_path: Path) -> None:
        lib = self._make_library(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "animation", "add-track",
            "--library", str(lib),
            "--animation", "idle",
            "--property", ".:rotation",
            "--keyframe", "0=0",
            "--keyframe", "1.0=3.14",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["animation"] == "idle"
        assert data["track_index"] == 0
        assert data["keyframe_count"] == 2


class TestAddTrackErrors:
    """Verify error handling for add-track."""

    def test_animation_not_found(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            str(out),
        ])
        result = runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(out),
            "--animation", "nonexistent",
            "--property", ".:x",
            "--keyframe", "0=0",
        ])
        assert result.exit_code != 0

    def test_invalid_keyframe_format(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            str(out),
        ])
        result = runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(out),
            "--animation", "idle",
            "--property", ".:x",
            "--keyframe", "invalid",
        ])
        assert result.exit_code != 0

    def test_non_numeric_keyframe(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            str(out),
        ])
        result = runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(out),
            "--animation", "idle",
            "--property", ".:x",
            "--keyframe", "0=abc",
        ])
        assert result.exit_code != 0


class TestListTracks:
    """Verify listing animation tracks."""

    def test_list_empty_library(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            str(out),
        ])
        result = runner.invoke(cli, ["animation", "list-tracks", str(out)])
        assert result.exit_code == 0
        assert "idle" in result.output

    def test_list_with_tracks(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle", "--length", "1.0", "--loop", "linear",
            str(out),
        ])
        runner.invoke(cli, [
            "animation", "add-track",
            "--library", str(out),
            "--animation", "idle",
            "--property", "Sprite2D:modulate:a",
            "--keyframe", "0=1", "--keyframe", "1=0",
        ])
        result = runner.invoke(cli, ["animation", "list-tracks", str(out)])
        assert result.exit_code == 0
        assert "idle" in result.output
        assert "1 track" in result.output or "Sprite2D" in result.output

    def test_list_json(self, tmp_path: Path) -> None:
        out = tmp_path / "anims.tres"
        runner = CliRunner()
        runner.invoke(cli, [
            "animation", "create-library",
            "--name", "idle",
            "--name", "walk",
            str(out),
        ])
        result = runner.invoke(cli, [
            "-j", "animation", "list-tracks", str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 2
        assert len(data["animations"]) == 2
