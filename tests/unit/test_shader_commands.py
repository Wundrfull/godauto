"""Tests for shader command group."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gdauto.cli import cli


class TestShaderCreateTemplates:
    """Verify shader create with built-in templates."""

    def test_flash_template(self, tmp_path: Path) -> None:
        out = tmp_path / "flash.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "shader", "create", "--template", "flash", str(out),
        ])
        assert result.exit_code == 0, result.output
        text = out.read_text()
        assert 'type="Shader"' in text
        assert "flash_color" in text
        assert "flash_amount" in text

    def test_outline_template(self, tmp_path: Path) -> None:
        out = tmp_path / "outline.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "shader", "create", "--template", "outline", str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "outline_color" in text
        assert "outline_width" in text

    def test_dissolve_template(self, tmp_path: Path) -> None:
        out = tmp_path / "dissolve.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "shader", "create", "--template", "dissolve", str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "dissolve_amount" in text
        assert "edge_color" in text

    def test_grayscale_template(self, tmp_path: Path) -> None:
        out = tmp_path / "gray.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "shader", "create", "--template", "grayscale", str(out),
        ])
        assert result.exit_code == 0
        assert "gray" in out.read_text().lower() or "0.299" in out.read_text()

    def test_pixelate_template(self, tmp_path: Path) -> None:
        out = tmp_path / "pixel.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "shader", "create", "--template", "pixelate", str(out),
        ])
        assert result.exit_code == 0
        assert "pixel_size" in out.read_text()

    def test_color_replace_template(self, tmp_path: Path) -> None:
        out = tmp_path / "replace.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "shader", "create", "--template", "color_replace", str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "target_color" in text
        assert "replace_color" in text


class TestShaderCreateCustom:
    """Verify shader create with custom code."""

    def test_from_file(self, tmp_path: Path) -> None:
        shader_src = tmp_path / "custom.gdshader"
        shader_src.write_text(
            "shader_type canvas_item;\nvoid fragment() { COLOR = vec4(1.0); }\n",
            encoding="utf-8",
        )
        out = tmp_path / "custom.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "shader", "create", "--file", str(shader_src), str(out),
        ])
        assert result.exit_code == 0
        assert "canvas_item" in out.read_text()

    def test_from_inline_code(self, tmp_path: Path) -> None:
        out = tmp_path / "inline.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "shader", "create",
            "--code", "shader_type canvas_item; void fragment() { COLOR = vec4(1); }",
            str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()


class TestShaderCreateJson:
    """Verify JSON output."""

    def test_json_output(self, tmp_path: Path) -> None:
        out = tmp_path / "shader.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "shader", "create", "--template", "flash", str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True
        assert data["template"] == "flash"
        assert data["code_length"] > 0


class TestShaderCreateErrors:
    """Verify error handling."""

    def test_no_source(self, tmp_path: Path) -> None:
        out = tmp_path / "shader.tres"
        runner = CliRunner()
        result = runner.invoke(cli, ["shader", "create", str(out)])
        assert result.exit_code != 0

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        out = tmp_path / "shaders" / "effects" / "flash.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "shader", "create", "--template", "flash", str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()


class TestShaderCreateMaterial:
    """Verify ShaderMaterial creation."""

    def test_create_material(self, tmp_path: Path) -> None:
        out = tmp_path / "material.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "shader", "create-material",
            "--shader", "res://shaders/flash.tres",
            str(out),
        ])
        assert result.exit_code == 0, result.output
        text = out.read_text()
        assert "ShaderMaterial" in text
        assert "res://shaders/flash.tres" in text

    def test_material_json(self, tmp_path: Path) -> None:
        out = tmp_path / "material.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "shader", "create-material",
            "--shader", "res://shaders/custom.tres",
            str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True
        assert data["shader"] == "res://shaders/custom.tres"


class TestListTemplates:
    """Verify listing shader templates."""

    def test_list_templates(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["shader", "list-templates"])
        assert result.exit_code == 0
        assert "flash" in result.output
        assert "outline" in result.output
        assert "dissolve" in result.output

    def test_list_templates_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "shader", "list-templates"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 6
        names = [t["name"] for t in data["templates"]]
        assert "flash" in names
        assert "outline" in names
