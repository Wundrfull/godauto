"""Unit tests for physics shape assignment and CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from gdauto.cli import cli
from gdauto.errors import ValidationError
from gdauto.formats.tres import SubResource
from gdauto.formats.values import PackedVector2Array
from gdauto.tileset.physics import apply_physics_to_atlas, parse_physics_rule


# ---------------------------------------------------------------------------
# parse_physics_rule
# ---------------------------------------------------------------------------


class TestParsePhysicsRule:
    """Tests for the parse_physics_rule function."""

    def test_range_full(self) -> None:
        tile_range, shape = parse_physics_rule("0-15:full")
        assert tile_range == range(0, 16)
        assert shape == "full"

    def test_single_tile_none(self) -> None:
        tile_range, shape = parse_physics_rule("5:none")
        assert tile_range == range(5, 6)
        assert shape == "none"

    def test_single_tile_full(self) -> None:
        tile_range, shape = parse_physics_rule("10:full")
        assert tile_range == range(10, 11)
        assert shape == "full"

    def test_invalid_format_no_colon(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_physics_rule("invalid")
        assert exc_info.value.code == "INVALID_PHYSICS_RULE"

    def test_invalid_shape_type(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_physics_rule("0-15:slope")
        assert exc_info.value.code == "INVALID_PHYSICS_RULE"
        assert "slope" in exc_info.value.message

    def test_invalid_range_not_integers(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            parse_physics_rule("abc:full")
        assert exc_info.value.code == "INVALID_PHYSICS_RULE"

    def test_whitespace_handling(self) -> None:
        tile_range, shape = parse_physics_rule("  0-15 : full ")
        assert tile_range == range(0, 16)
        assert shape == "full"


# ---------------------------------------------------------------------------
# apply_physics_to_atlas
# ---------------------------------------------------------------------------


class TestApplyPhysicsToAtlas:
    """Tests for the apply_physics_to_atlas function."""

    def _make_atlas_sub(self) -> SubResource:
        return SubResource(
            type="TileSetAtlasSource",
            id="TileSetAtlasSource_test",
            properties={},
        )

    def test_full_adds_packed_vector2_array(self) -> None:
        atlas = self._make_atlas_sub()
        rules = [(range(0, 1), "full")]
        apply_physics_to_atlas(atlas, rules, columns=4, tile_width=32, tile_height=32)
        key = "0:0/physics_layer_0/polygon_0/points"
        assert key in atlas.properties
        points = atlas.properties[key]
        assert isinstance(points, PackedVector2Array)
        assert points.values == (0.0, 0.0, 32.0, 0.0, 32.0, 32.0, 0.0, 32.0)

    def test_none_does_not_add_properties(self) -> None:
        atlas = self._make_atlas_sub()
        rules = [(range(0, 4), "none")]
        apply_physics_to_atlas(atlas, rules, columns=4, tile_width=32, tile_height=32)
        physics_keys = [k for k in atlas.properties if "physics" in k]
        assert len(physics_keys) == 0

    def test_index_to_atlas_coordinate_conversion(self) -> None:
        """Index 5 with 4 columns should be (1, 1)."""
        atlas = self._make_atlas_sub()
        rules = [(range(5, 6), "full")]
        apply_physics_to_atlas(atlas, rules, columns=4, tile_width=16, tile_height=16)
        key = "1:1/physics_layer_0/polygon_0/points"
        assert key in atlas.properties

    def test_multiple_rules(self) -> None:
        atlas = self._make_atlas_sub()
        rules = [
            (range(0, 2), "full"),
            (range(2, 4), "none"),
        ]
        apply_physics_to_atlas(atlas, rules, columns=4, tile_width=32, tile_height=32)
        assert "0:0/physics_layer_0/polygon_0/points" in atlas.properties
        assert "1:0/physics_layer_0/polygon_0/points" in atlas.properties
        assert "2:0/physics_layer_0/polygon_0/points" not in atlas.properties

    def test_tile_size_reflected_in_points(self) -> None:
        atlas = self._make_atlas_sub()
        rules = [(range(0, 1), "full")]
        apply_physics_to_atlas(atlas, rules, columns=4, tile_width=16, tile_height=24)
        points = atlas.properties["0:0/physics_layer_0/polygon_0/points"]
        assert points.values == (0.0, 0.0, 16.0, 0.0, 16.0, 24.0, 0.0, 24.0)


# ---------------------------------------------------------------------------
# CLI auto-terrain
# ---------------------------------------------------------------------------


def _create_dummy_image(path: Path) -> None:
    """Create a minimal PNG-like file for testing."""
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)


def _create_tileset(tmp_path: Path) -> Path:
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
            "--columns", "12",
            "--rows", "4",
            "-o", str(output),
        ],
    )
    assert result.exit_code == 0, result.output + (result.stderr or "")
    return output


class TestAutoTerrainCLI:
    """Tests for the tileset auto-terrain CLI command."""

    def test_auto_terrain_blob47(self, tmp_path: Path) -> None:
        tres = _create_tileset(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["tileset", "auto-terrain", str(tres), "--layout", "blob-47"],
        )
        assert result.exit_code == 0, result.output + (result.stderr or "")
        content = tres.read_text()
        assert "terrain_peering_bit" in content

    def test_auto_terrain_json_output(self, tmp_path: Path) -> None:
        tres = _create_tileset(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["-j", "tileset", "auto-terrain", str(tres), "--layout", "blob-47"],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["layout"] == "blob-47"
        assert data["tiles_assigned"] == 47

    def test_auto_terrain_minimal16(self, tmp_path: Path) -> None:
        tres = _create_tileset(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["-j", "tileset", "auto-terrain", str(tres), "--layout", "minimal-16"],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["tiles_assigned"] == 16

    def test_auto_terrain_without_layout_fails(self, tmp_path: Path) -> None:
        tres = _create_tileset(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["tileset", "auto-terrain", str(tres)],
        )
        assert result.exit_code != 0

    def test_auto_terrain_nonexistent_file(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["tileset", "auto-terrain", "nonexistent.tres", "--layout", "blob-47"],
        )
        assert result.exit_code != 0

    def test_auto_terrain_adds_terrain_set_to_resource(self, tmp_path: Path) -> None:
        tres = _create_tileset(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["tileset", "auto-terrain", str(tres), "--layout", "blob-47"],
        )
        assert result.exit_code == 0, result.output
        content = tres.read_text()
        assert "terrain_set_0/mode" in content
        assert "terrain_set_0/terrains" in content

    def test_auto_terrain_custom_output(self, tmp_path: Path) -> None:
        tres = _create_tileset(tmp_path)
        out = tmp_path / "terrain_out.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "tileset", "auto-terrain", str(tres),
                "--layout", "rpgmaker",
                "-o", str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        content = out.read_text()
        assert "terrain_peering_bit" in content


# ---------------------------------------------------------------------------
# CLI assign-physics
# ---------------------------------------------------------------------------


class TestAssignPhysicsCLI:
    """Tests for the tileset assign-physics CLI command."""

    def test_assign_physics_full(self, tmp_path: Path) -> None:
        tres = _create_tileset(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "tileset", "assign-physics", str(tres),
                "--physics", "0-3:full",
                "--columns", "12",
            ],
        )
        assert result.exit_code == 0, result.output + (result.stderr or "")
        content = tres.read_text()
        assert "physics_layer_0" in content
        assert "PackedVector2Array" in content

    def test_assign_physics_json_output(self, tmp_path: Path) -> None:
        tres = _create_tileset(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "-j", "tileset", "assign-physics", str(tres),
                "--physics", "0-7:full",
                "--physics", "8-15:none",
                "--columns", "12",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["rules_applied"] == 2
        assert data["tiles_affected"] == 16

    def test_assign_physics_adds_collision_layer(self, tmp_path: Path) -> None:
        tres = _create_tileset(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "tileset", "assign-physics", str(tres),
                "--physics", "0-3:full",
                "--columns", "12",
            ],
        )
        assert result.exit_code == 0, result.output
        content = tres.read_text()
        assert "physics_layer_0/collision_layer = 1" in content
        assert "physics_layer_0/collision_mask = 1" in content

    def test_assign_physics_nonexistent_file(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "tileset", "assign-physics", "nonexistent.tres",
                "--physics", "0-3:full",
                "--columns", "4",
            ],
        )
        assert result.exit_code != 0


class TestTilesetHelpUpdated:
    """Verify tileset help shows new subcommands."""

    def test_tileset_help_shows_auto_terrain(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["tileset", "--help"])
        assert result.exit_code == 0
        assert "auto-terrain" in result.output

    def test_tileset_help_shows_assign_physics(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["tileset", "--help"])
        assert result.exit_code == 0
        assert "assign-physics" in result.output

    def test_auto_terrain_help_shows_layout_choices(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["tileset", "auto-terrain", "--help"])
        assert result.exit_code == 0
        assert "blob-47" in result.output
        assert "minimal-16" in result.output
        assert "rpgmaker" in result.output
