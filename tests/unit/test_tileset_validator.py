"""Tests for TileSet structural and headless validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from gdauto.cli import cli
from gdauto.formats.tres import serialize_tres_file
from gdauto.tileset.builder import build_tileset


def _build_valid_tres(path: Path) -> Path:
    """Create a valid TileSet .tres file at the given path."""
    resource = build_tileset("res://terrain.png", 32, 32, 8, 6)
    serialize_tres_file(resource, path)
    return path


def _build_invalid_type_tres(path: Path) -> Path:
    """Create a .tres file with wrong resource type (SpriteFrames)."""
    path.write_text(
        '[gd_resource type="SpriteFrames" format=3]\n\n'
        "[resource]\n"
        'animations = []\n'
    )
    return path


def _build_no_atlas_tres(path: Path) -> Path:
    """Create a TileSet .tres with no TileSetAtlasSource sub-resource."""
    path.write_text(
        '[gd_resource type="TileSet" format=3]\n\n'
        "[resource]\n"
        'tile_size = Vector2i(32, 32)\n'
    )
    return path


def _build_no_texture_tres(path: Path) -> Path:
    """Create a TileSet .tres with atlas source missing texture reference."""
    path.write_text(
        '[gd_resource type="TileSet" load_steps=2 format=3]\n\n'
        '[sub_resource type="TileSetAtlasSource" id="atlas_1"]\n'
        'texture_region_size = Vector2i(32, 32)\n\n'
        "[resource]\n"
        'tile_size = Vector2i(32, 32)\n'
        'sources/0 = SubResource("atlas_1")\n'
    )
    return path


def _build_terrain_mismatch_tres(path: Path) -> Path:
    """TileSet where tiles reference terrain_set=0 but resource lacks declaration."""
    path.write_text(
        '[gd_resource type="TileSet" load_steps=3 format=3]\n\n'
        '[ext_resource type="Texture2D" path="res://t.png" id="tex_1"]\n\n'
        '[sub_resource type="TileSetAtlasSource" id="atlas_1"]\n'
        'texture = ExtResource("tex_1")\n'
        'texture_region_size = Vector2i(32, 32)\n'
        '0:0/terrain_set = 0\n'
        '0:0/terrain/peering_bit/right_side = 0\n\n'
        "[resource]\n"
        'tile_size = Vector2i(32, 32)\n'
        'sources/0 = SubResource("atlas_1")\n'
    )
    return path


# ---------------------------------------------------------------------------
# validate_tileset (structural)
# ---------------------------------------------------------------------------


class TestValidateTileset:
    """Tests for validate_tileset structural checks."""

    def test_valid_tileset_returns_valid(self, tmp_path: Path) -> None:
        from gdauto.tileset.validator import validate_tileset

        tres = _build_valid_tres(tmp_path / "valid.tres")
        result = validate_tileset(tres)
        assert result["valid"] is True
        assert result["issues"] == []

    def test_wrong_resource_type(self, tmp_path: Path) -> None:
        from gdauto.tileset.validator import validate_tileset

        tres = _build_invalid_type_tres(tmp_path / "sprites.tres")
        result = validate_tileset(tres)
        assert result["valid"] is False
        assert any("SpriteFrames" in i or "resource type" in i.lower() for i in result["issues"])

    def test_checks_tile_size(self, tmp_path: Path) -> None:
        from gdauto.tileset.validator import validate_tileset

        tres = _build_valid_tres(tmp_path / "good.tres")
        result = validate_tileset(tres)
        assert "tile_size" in result

    def test_checks_atlas_source_present(self, tmp_path: Path) -> None:
        from gdauto.tileset.validator import validate_tileset

        tres = _build_no_atlas_tres(tmp_path / "no_atlas.tres")
        result = validate_tileset(tres)
        assert result["valid"] is False
        assert any("atlas" in i.lower() for i in result["issues"])

    def test_missing_texture_reference(self, tmp_path: Path) -> None:
        from gdauto.tileset.validator import validate_tileset

        tres = _build_no_texture_tres(tmp_path / "no_tex.tres")
        result = validate_tileset(tres)
        # Should report missing texture as issue
        assert any("texture" in i.lower() for i in result["issues"])

    def test_terrain_set_mismatch(self, tmp_path: Path) -> None:
        from gdauto.tileset.validator import validate_tileset

        tres = _build_terrain_mismatch_tres(tmp_path / "mismatch.tres")
        result = validate_tileset(tres)
        # Should warn about terrain_set referenced in tiles but not declared
        has_terrain_warning = any(
            "terrain" in w.lower() for w in result.get("warnings", [])
        )
        assert has_terrain_warning

    def test_counts_tiles_in_summary(self, tmp_path: Path) -> None:
        from gdauto.tileset.validator import validate_tileset

        tres = _build_valid_tres(tmp_path / "count.tres")
        result = validate_tileset(tres)
        assert "atlas_sources" in result
        assert isinstance(result["atlas_sources"], list)

    def test_unparseable_file_returns_invalid(self, tmp_path: Path) -> None:
        from gdauto.tileset.validator import validate_tileset

        bad = tmp_path / "bad.tres"
        bad.write_text("this is not a valid tres file at all!!!")
        result = validate_tileset(bad)
        assert result["valid"] is False
        assert len(result["issues"]) > 0


# ---------------------------------------------------------------------------
# validate_tileset_headless (mocked)
# ---------------------------------------------------------------------------


class TestValidateTilesetHeadless:
    """Tests for validate_tileset_headless."""

    def test_headless_calls_backend(self, tmp_path: Path) -> None:
        from gdauto.tileset.validator import validate_tileset_headless

        tres = _build_valid_tres(tmp_path / "headless.tres")
        mock_backend = MagicMock()
        mock_backend.run.return_value = MagicMock(
            stdout="VALIDATION_OK: sources=1\n",
            returncode=0,
        )
        result = validate_tileset_headless(tres, mock_backend)
        assert result["headless_validated"] is True


# ---------------------------------------------------------------------------
# CLI tileset validate
# ---------------------------------------------------------------------------


class TestValidateCli:
    """Tests for the tileset validate CLI command."""

    def test_valid_file_returns_success(self, tmp_path: Path) -> None:
        tres = _build_valid_tres(tmp_path / "cli_valid.tres")
        runner = CliRunner()
        result = runner.invoke(cli, ["tileset", "validate", str(tres)])
        assert result.exit_code == 0

    def test_invalid_file_returns_nonzero(self, tmp_path: Path) -> None:
        tres = _build_no_atlas_tres(tmp_path / "cli_invalid.tres")
        runner = CliRunner()
        result = runner.invoke(cli, ["tileset", "validate", str(tres)])
        assert result.exit_code != 0

    def test_json_output(self, tmp_path: Path) -> None:
        tres = _build_valid_tres(tmp_path / "cli_json.tres")
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json", "tileset", "validate", str(tres)]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["valid"] is True

    def test_help_shows_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["tileset", "validate", "--help"])
        assert result.exit_code == 0
        assert "--godot" in result.output
        assert "TRES_FILE" in result.output
