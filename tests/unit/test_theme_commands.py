"""Tests for theme command group."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


class TestThemeCreateBasic:
    """Verify theme create generates valid Theme .tres files."""

    def test_default_theme(self, tmp_path: Path) -> None:
        out = tmp_path / "theme.tres"
        runner = CliRunner()
        result = runner.invoke(cli, ["theme", "create", str(out)])
        assert result.exit_code == 0, result.output
        text = out.read_text()
        assert 'type="Theme"' in text
        assert "StyleBoxFlat" in text
        assert "Panel/styles/panel" in text
        assert "Button/styles/normal" in text

    def test_custom_colors(self, tmp_path: Path) -> None:
        out = tmp_path / "theme.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "theme", "create",
            "--base-color", "#1a1a2e",
            "--accent-color", "#e94560",
            "--text-color", "#ffffff",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "Theme" in text
        assert "StyleBoxFlat" in text

    def test_named_colors(self, tmp_path: Path) -> None:
        out = tmp_path / "theme.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "theme", "create",
            "--base-color", "black",
            "--accent-color", "blue",
            "--text-color", "white",
            str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()

    def test_custom_font_size(self, tmp_path: Path) -> None:
        out = tmp_path / "theme.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "theme", "create",
            "--font-size", "24",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "font_size" in text
        assert "24" in text

    def test_custom_corner_radius(self, tmp_path: Path) -> None:
        out = tmp_path / "theme.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "theme", "create",
            "--corner-radius", "8",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "corner_radius" in text

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        out = tmp_path / "ui" / "themes" / "main.tres"
        runner = CliRunner()
        result = runner.invoke(cli, ["theme", "create", str(out)])
        assert result.exit_code == 0
        assert out.exists()


class TestThemeCreateContent:
    """Verify theme content has all required styles."""

    def test_has_panel_style(self, tmp_path: Path) -> None:
        out = tmp_path / "theme.tres"
        runner = CliRunner()
        runner.invoke(cli, ["theme", "create", str(out)])
        text = out.read_text()
        assert "Panel/styles/panel" in text

    def test_has_button_states(self, tmp_path: Path) -> None:
        out = tmp_path / "theme.tres"
        runner = CliRunner()
        runner.invoke(cli, ["theme", "create", str(out)])
        text = out.read_text()
        assert "Button/styles/normal" in text
        assert "Button/styles/hover" in text
        assert "Button/styles/pressed" in text
        assert "Button/styles/focus" in text

    def test_has_label_style(self, tmp_path: Path) -> None:
        out = tmp_path / "theme.tres"
        runner = CliRunner()
        runner.invoke(cli, ["theme", "create", str(out)])
        text = out.read_text()
        assert "Label/colors/font_color" in text
        assert "Label/font_sizes/font_size" in text

    def test_has_lineedit_style(self, tmp_path: Path) -> None:
        out = tmp_path / "theme.tres"
        runner = CliRunner()
        runner.invoke(cli, ["theme", "create", str(out)])
        text = out.read_text()
        assert "LineEdit/styles/normal" in text
        assert "LineEdit/colors/font_color" in text

    def test_has_button_colors(self, tmp_path: Path) -> None:
        out = tmp_path / "theme.tres"
        runner = CliRunner()
        runner.invoke(cli, ["theme", "create", str(out)])
        text = out.read_text()
        assert "Button/colors/font_color" in text


class TestThemeCreateJson:
    """Verify JSON output for theme create."""

    def test_json_output(self, tmp_path: Path) -> None:
        out = tmp_path / "theme.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "theme", "create",
            "--base-color", "#2d2d3d",
            "--accent-color", "#478cbf",
            str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True
        assert data["base_color"] == "#2d2d3d"
        assert data["accent_color"] == "#478cbf"
        assert data["stylebox_count"] == 6


class TestThemeCreateErrors:
    """Verify error handling."""

    def test_invalid_hex_color(self, tmp_path: Path) -> None:
        out = tmp_path / "theme.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "theme", "create", "--base-color", "not_a_color", str(out),
        ])
        assert result.exit_code != 0

    def test_invalid_hex_length(self, tmp_path: Path) -> None:
        out = tmp_path / "theme.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "theme", "create", "--base-color", "#12345", str(out),
        ])
        assert result.exit_code != 0


class TestCreateStylebox:
    """Verify standalone StyleBoxFlat generation."""

    def test_basic_stylebox(self, tmp_path: Path) -> None:
        out = tmp_path / "panel.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "theme", "create-stylebox",
            "--bg-color", "#1a1a2e",
            str(out),
        ])
        assert result.exit_code == 0, result.output
        text = out.read_text()
        assert "StyleBoxFlat" in text
        assert "bg_color" in text

    def test_stylebox_with_border(self, tmp_path: Path) -> None:
        out = tmp_path / "alert.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "theme", "create-stylebox",
            "--bg-color", "red",
            "--border-color", "white",
            "--border-width", "2",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "border_color" in text
        assert "border_width" in text

    def test_stylebox_with_radius(self, tmp_path: Path) -> None:
        out = tmp_path / "rounded.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "theme", "create-stylebox",
            "--bg-color", "#333333",
            "--corner-radius", "12",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "corner_radius" in text

    def test_stylebox_with_margin(self, tmp_path: Path) -> None:
        out = tmp_path / "padded.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "theme", "create-stylebox",
            "--bg-color", "black",
            "--margin", "16",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "content_margin" in text

    def test_stylebox_json(self, tmp_path: Path) -> None:
        out = tmp_path / "panel.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "theme", "create-stylebox",
            "--bg-color", "#444",  # short hex not supported
            str(out),
        ])
        # This should fail because #444 is not valid hex
        assert result.exit_code != 0

    def test_stylebox_json_valid(self, tmp_path: Path) -> None:
        out = tmp_path / "panel.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "theme", "create-stylebox",
            "--bg-color", "#444444",
            str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True


class TestColorParsing:
    """Verify color parsing for various formats."""

    def test_hex_6_digit(self, tmp_path: Path) -> None:
        out = tmp_path / "t.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "theme", "create-stylebox", "--bg-color", "#ff0000", str(out),
        ])
        assert result.exit_code == 0

    def test_hex_8_digit_with_alpha(self, tmp_path: Path) -> None:
        out = tmp_path / "t.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "theme", "create-stylebox", "--bg-color", "#ff000080", str(out),
        ])
        assert result.exit_code == 0

    def test_named_white(self, tmp_path: Path) -> None:
        out = tmp_path / "t.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "theme", "create-stylebox", "--bg-color", "white", str(out),
        ])
        assert result.exit_code == 0

    def test_named_transparent(self, tmp_path: Path) -> None:
        out = tmp_path / "t.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "theme", "create-stylebox", "--bg-color", "transparent", str(out),
        ])
        assert result.exit_code == 0
