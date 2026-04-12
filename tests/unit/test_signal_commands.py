"""Tests for signal connection management commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


def _make_scene(tmp_path: Path, extra_nodes: str = "") -> Path:
    """Create a scene with some nodes for signal testing."""
    scene_file = tmp_path / "main.tscn"
    scene_file.write_text(
        '[gd_scene load_steps=2 format=3]\n'
        '\n'
        '[ext_resource type="Script" path="res://scripts/main.gd" id="1_script"]\n'
        '\n'
        '[node name="Main" type="Control"]\n'
        'script = ExtResource("1_script")\n'
        '\n'
        '[node name="Button" type="Button" parent="."]\n'
        '\n'
        '[node name="Timer" type="Timer" parent="."]\n'
        + extra_nodes,
        encoding="utf-8",
    )
    return scene_file


def _make_scene_with_connection(tmp_path: Path) -> Path:
    """Create a scene with an existing signal connection."""
    scene_file = tmp_path / "main.tscn"
    scene_file.write_text(
        '[gd_scene format=3]\n'
        '\n'
        '[node name="Main" type="Control"]\n'
        '\n'
        '[node name="Button" type="Button" parent="."]\n'
        '\n'
        '[connection signal="pressed" from="Button" to="." method="_on_button_pressed"]\n',
        encoding="utf-8",
    )
    return scene_file


class TestSignalConnect:
    """Verify signal connect adds connections to scenes."""

    def test_connect_button_pressed(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "signal", "connect",
            "--scene", str(scene),
            "--signal", "pressed",
            "--from", "Button",
            "--to", ".",
            "--method", "_on_button_pressed",
        ])
        assert result.exit_code == 0, result.output
        text = scene.read_text()
        assert '[connection' in text
        assert 'signal="pressed"' in text
        assert 'from="Button"' in text
        assert 'method="_on_button_pressed"' in text

    def test_connect_timer_timeout(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "signal", "connect",
            "--scene", str(scene),
            "--signal", "timeout",
            "--from", "Timer",
            "--to", ".",
            "--method", "_on_timer_timeout",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert 'signal="timeout"' in text

    def test_connect_with_flags(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "signal", "connect",
            "--scene", str(scene),
            "--signal", "pressed",
            "--from", "Button",
            "--to", ".",
            "--method", "_on_button_pressed",
            "--flags", "4",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "flags=4" in text

    def test_connect_persist_flag_preserved(self, tmp_path: Path) -> None:
        # CONNECT_PERSIST = 2. Dropping this bit makes editor treat the
        # connection as transient and silently discard it on next save.
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "signal", "connect",
            "--scene", str(scene),
            "--signal", "pressed",
            "--from", "Button",
            "--to", ".",
            "--method", "_on_button_pressed",
            "--flags", "2",
        ])
        assert result.exit_code == 0
        assert "flags=2" in scene.read_text()

    def test_connect_flags_zero_not_emitted(self, tmp_path: Path) -> None:
        # Default flags=0: omit attribute rather than clutter output.
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "signal", "connect",
            "--scene", str(scene),
            "--signal", "pressed",
            "--from", "Button",
            "--to", ".",
            "--method", "_on_button_pressed",
        ])
        assert result.exit_code == 0
        assert "flags=" not in scene.read_text()

    def test_connect_flags_round_trip(self, tmp_path: Path) -> None:
        from auto_godot.formats.tscn import parse_tscn, serialize_tscn
        source = (
            '[gd_scene format=3]\n\n'
            '[node name="Main" type="Control"]\n\n'
            '[node name="Button" type="Button" parent="."]\n\n'
            '[connection signal="pressed" from="Button" to="." '
            'method="_on_pressed" flags=2]\n'
        )
        rebuilt = serialize_tscn(parse_tscn(source))
        assert "flags=2" in rebuilt

    def test_connect_multiple_signals(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "signal", "connect",
            "--scene", str(scene),
            "--signal", "pressed",
            "--from", "Button",
            "--to", ".",
            "--method", "_on_button_pressed",
        ])
        result = runner.invoke(cli, [
            "signal", "connect",
            "--scene", str(scene),
            "--signal", "timeout",
            "--from", "Timer",
            "--to", ".",
            "--method", "_on_timer_timeout",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "pressed" in text
        assert "timeout" in text


class TestSignalConnectJson:
    """Verify JSON output for signal connect."""

    def test_json_output(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "signal", "connect",
            "--scene", str(scene),
            "--signal", "pressed",
            "--from", "Button",
            "--to", ".",
            "--method", "_on_button_pressed",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["connected"] is True
        assert data["signal"] == "pressed"
        assert data["from"] == "Button"
        assert data["to"] == "."
        assert data["method"] == "_on_button_pressed"


class TestSignalConnectErrors:
    """Verify error handling for connect."""

    def test_duplicate_connection(self, tmp_path: Path) -> None:
        scene = _make_scene_with_connection(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "signal", "connect",
            "--scene", str(scene),
            "--signal", "pressed",
            "--from", "Button",
            "--to", ".",
            "--method", "_on_button_pressed",
        ])
        assert result.exit_code != 0


class TestSignalList:
    """Verify listing signal connections."""

    def test_list_empty(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["signal", "list", str(scene)])
        assert result.exit_code == 0
        assert "No signal" in result.output or "0" in result.output

    def test_list_with_connections(self, tmp_path: Path) -> None:
        scene = _make_scene_with_connection(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["signal", "list", str(scene)])
        assert result.exit_code == 0
        assert "pressed" in result.output
        assert "Button" in result.output

    def test_list_json(self, tmp_path: Path) -> None:
        scene = _make_scene_with_connection(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "signal", "list", str(scene)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["connections"][0]["signal"] == "pressed"

    def test_list_after_connect(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, [
            "signal", "connect",
            "--scene", str(scene),
            "--signal", "pressed",
            "--from", "Button",
            "--to", ".",
            "--method", "_on_btn",
        ])
        result = runner.invoke(cli, ["-j", "signal", "list", str(scene)])
        data = json.loads(result.output)
        assert data["count"] == 1


class TestSignalDisconnect:
    """Verify disconnecting signals."""

    def test_disconnect_existing(self, tmp_path: Path) -> None:
        scene = _make_scene_with_connection(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "signal", "disconnect",
            "--scene", str(scene),
            "--signal", "pressed",
            "--from", "Button",
            "--to", ".",
            "--method", "_on_button_pressed",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "[connection" not in text

    def test_disconnect_nonexistent_error(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "signal", "disconnect",
            "--scene", str(scene),
            "--signal", "pressed",
            "--from", "Button",
            "--to", ".",
            "--method", "_on_nonexistent",
        ])
        assert result.exit_code != 0

    def test_disconnect_preserves_others(self, tmp_path: Path) -> None:
        scene = _make_scene(tmp_path)
        runner = CliRunner()
        # Add two connections
        runner.invoke(cli, [
            "signal", "connect",
            "--scene", str(scene),
            "--signal", "pressed",
            "--from", "Button",
            "--to", ".",
            "--method", "_on_btn",
        ])
        runner.invoke(cli, [
            "signal", "connect",
            "--scene", str(scene),
            "--signal", "timeout",
            "--from", "Timer",
            "--to", ".",
            "--method", "_on_timer",
        ])
        # Disconnect one
        result = runner.invoke(cli, [
            "signal", "disconnect",
            "--scene", str(scene),
            "--signal", "pressed",
            "--from", "Button",
            "--to", ".",
            "--method", "_on_btn",
        ])
        assert result.exit_code == 0
        text = scene.read_text()
        assert "timeout" in text
        assert "_on_btn" not in text

    def test_disconnect_json(self, tmp_path: Path) -> None:
        scene = _make_scene_with_connection(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "signal", "disconnect",
            "--scene", str(scene),
            "--signal", "pressed",
            "--from", "Button",
            "--to", ".",
            "--method", "_on_button_pressed",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["disconnected"] is True
