"""Tests for tileset create and tileset inspect CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _create_dummy_image(path: Path) -> None:
    """Create a minimal PNG-like file for testing (not a real image)."""
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)


class TestTilesetCreate:
    """Tests for the tileset create subcommand."""

    def test_create_produces_tres_file(self, tmp_path: Path) -> None:
        img = tmp_path / "sheet.png"
        _create_dummy_image(img)
        output = tmp_path / "tileset.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "tileset", "create", str(img),
                "--tile-size", "32x32",
                "--columns", "8",
                "--rows", "6",
                "-o", str(output),
            ],
        )
        assert result.exit_code == 0, result.output + (result.stderr or "")
        assert output.exists()

    def test_create_tres_has_tileset_header(self, tmp_path: Path) -> None:
        img = tmp_path / "sheet.png"
        _create_dummy_image(img)
        output = tmp_path / "tileset.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "tileset", "create", str(img),
                "--tile-size", "32x32",
                "--columns", "8",
                "--rows", "6",
                "-o", str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        content = output.read_text()
        assert '[gd_resource type="TileSet"' in content

    def test_create_missing_image_file_not_found(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "tileset", "create", "nonexistent.png",
                "--tile-size", "32x32",
                "--columns", "8",
                "--rows", "6",
            ],
        )
        assert result.exit_code != 0

    def test_create_json_output(self, tmp_path: Path) -> None:
        img = tmp_path / "sheet.png"
        _create_dummy_image(img)
        output = tmp_path / "tileset.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "-j", "tileset", "create", str(img),
                "--tile-size", "32x32",
                "--columns", "8",
                "--rows", "6",
                "-o", str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["columns"] == 8
        assert data["rows"] == 6
        assert data["total_tiles"] == 48
        assert data["tile_size"] == "32x32"

    def test_create_default_output_path(self, tmp_path: Path) -> None:
        img = tmp_path / "tiles.png"
        _create_dummy_image(img)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "tileset", "create", str(img),
                "--tile-size", "16x16",
                "--columns", "4",
                "--rows", "4",
            ],
        )
        assert result.exit_code == 0, result.output
        expected = tmp_path / "tiles.tres"
        assert expected.exists()

    def test_create_invalid_tile_size(self, tmp_path: Path) -> None:
        img = tmp_path / "sheet.png"
        _create_dummy_image(img)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "tileset", "create", str(img),
                "--tile-size", "bad",
                "--columns", "8",
                "--rows", "6",
            ],
        )
        assert result.exit_code != 0

    def test_create_with_margin_and_separation(self, tmp_path: Path) -> None:
        img = tmp_path / "sheet.png"
        _create_dummy_image(img)
        output = tmp_path / "tileset.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "tileset", "create", str(img),
                "--tile-size", "32x32",
                "--columns", "8",
                "--rows", "6",
                "--margin", "2",
                "--separation", "1",
                "-o", str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        content = output.read_text()
        assert "margins = Vector2i(2, 2)" in content
        assert "separation = Vector2i(1, 1)" in content

    def test_create_custom_res_path(self, tmp_path: Path) -> None:
        img = tmp_path / "sheet.png"
        _create_dummy_image(img)
        output = tmp_path / "tileset.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "tileset", "create", str(img),
                "--tile-size", "32x32",
                "--columns", "8",
                "--rows", "6",
                "--res-path", "res://art/tileset.png",
                "-o", str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        content = output.read_text()
        assert "res://art/tileset.png" in content


class TestTilesetInspect:
    """Tests for the tileset inspect subcommand."""

    def _create_tileset(self, tmp_path: Path) -> Path:
        """Helper: create a tileset .tres via the create command."""
        img = tmp_path / "sheet.png"
        _create_dummy_image(img)
        output = tmp_path / "tileset.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "tileset", "create", str(img),
                "--tile-size", "32x32",
                "--columns", "8",
                "--rows", "6",
                "-o", str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        return output

    def test_inspect_valid_tileset(self, tmp_path: Path) -> None:
        tres = self._create_tileset(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["tileset", "inspect", str(tres)])
        assert result.exit_code == 0, result.output
        assert "TileSet" in result.output

    def test_inspect_json_output(self, tmp_path: Path) -> None:
        tres = self._create_tileset(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "tileset", "inspect", str(tres)])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["type"] == "TileSet"
        assert data["format"] == 3
        assert isinstance(data["atlas_sources"], list)
        assert len(data["atlas_sources"]) == 1

    def test_inspect_nonexistent_file(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["tileset", "inspect", "nonexistent.tres"]
        )
        assert result.exit_code != 0

    def test_inspect_non_tileset_resource(self, tmp_path: Path) -> None:
        """A SpriteFrames .tres should produce INVALID_RESOURCE_TYPE."""
        # Use the simple fixture from sprite tests
        fixture = FIXTURES_DIR / "aseprite_simple.json"
        if not fixture.exists():
            return  # skip if fixture missing
        from auto_godot.formats.aseprite import parse_aseprite_json
        from auto_godot.formats.tres import serialize_tres_file
        from auto_godot.sprite.spriteframes import build_spriteframes

        data = parse_aseprite_json(fixture)
        resource = build_spriteframes(data, "res://test.png")
        tres_path = tmp_path / "sprite.tres"
        serialize_tres_file(resource, tres_path)

        runner = CliRunner()
        result = runner.invoke(
            cli, ["tileset", "inspect", str(tres_path)]
        )
        assert result.exit_code != 0

    def test_inspect_json_has_ext_resources(self, tmp_path: Path) -> None:
        tres = self._create_tileset(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "tileset", "inspect", str(tres)])
        data = json.loads(result.output)
        assert "ext_resources" in data
        assert len(data["ext_resources"]) == 1
        assert data["ext_resources"][0]["type"] == "Texture2D"

    def test_inspect_tile_size_in_output(self, tmp_path: Path) -> None:
        tres = self._create_tileset(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "tileset", "inspect", str(tres)])
        data = json.loads(result.output)
        assert "Vector2i(32, 32)" in data["tile_size"]


class TestTilesetHelp:
    """Verify tileset help output."""

    def test_tileset_help_shows_subcommands(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["tileset", "--help"])
        assert result.exit_code == 0
        assert "create" in result.output
        assert "inspect" in result.output
