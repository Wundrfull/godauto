"""Unit tests for terrain peering bit lookup tables and apply_terrain_to_atlas."""

from __future__ import annotations

from gdauto.formats.tres import SubResource
from gdauto.formats.values import Color
from gdauto.tileset.terrain import (
    BLOB_47_LAYOUT,
    LAYOUT_MAP,
    MINIMAL_16_LAYOUT,
    PEERING_BIT_NAMES_CORNERS_AND_SIDES,
    PEERING_BIT_NAMES_SIDES,
    RPGMAKER_LAYOUT,
    TERRAIN_MODES,
    add_terrain_set_to_resource,
    apply_terrain_to_atlas,
)


# ---------------------------------------------------------------------------
# Layout table structure tests
# ---------------------------------------------------------------------------


class TestBlob47Layout:
    """Tests for the blob-47 peering bit lookup table."""

    def test_has_exactly_47_entries(self) -> None:
        assert len(BLOB_47_LAYOUT) == 47

    def test_keys_are_col_row_tuples(self) -> None:
        for key in BLOB_47_LAYOUT:
            assert isinstance(key, tuple)
            assert len(key) == 2
            assert isinstance(key[0], int)
            assert isinstance(key[1], int)

    def test_each_entry_has_8_peering_bits(self) -> None:
        expected_keys = set(PEERING_BIT_NAMES_CORNERS_AND_SIDES)
        for coord, bits in BLOB_47_LAYOUT.items():
            assert set(bits.keys()) == expected_keys, (
                f"Tile at {coord} has keys {set(bits.keys())}, "
                f"expected {expected_keys}"
            )

    def test_values_are_0_or_minus_1(self) -> None:
        for coord, bits in BLOB_47_LAYOUT.items():
            for bit_name, value in bits.items():
                assert value in (0, -1), (
                    f"Tile at {coord}, bit {bit_name} has value {value}, "
                    f"expected 0 or -1"
                )

    def test_blob47_constraint_side_empty_implies_adjacent_corners_empty(self) -> None:
        """If a side bit is -1, adjacent corner bits must also be -1.

        Adjacent corners for each side:
          right_side: top_right_corner, bottom_right_corner
          bottom_side: bottom_right_corner, bottom_left_corner
          left_side: bottom_left_corner, top_left_corner
          top_side: top_left_corner, top_right_corner
        """
        side_to_corners = {
            "right_side": ("top_right_corner", "bottom_right_corner"),
            "bottom_side": ("bottom_right_corner", "bottom_left_corner"),
            "left_side": ("bottom_left_corner", "top_left_corner"),
            "top_side": ("top_left_corner", "top_right_corner"),
        }
        for coord, bits in BLOB_47_LAYOUT.items():
            for side, corners in side_to_corners.items():
                if bits[side] == -1:
                    for corner in corners:
                        assert bits[corner] == -1, (
                            f"Tile at {coord}: {side}=-1 but "
                            f"{corner}={bits[corner]}, should be -1"
                        )

    def test_all_entries_are_unique(self) -> None:
        """No two tiles should have identical peering bit patterns."""
        seen: list[tuple[int, ...]] = []
        for coord, bits in BLOB_47_LAYOUT.items():
            pattern = tuple(bits[k] for k in PEERING_BIT_NAMES_CORNERS_AND_SIDES)
            assert pattern not in seen, (
                f"Duplicate peering bit pattern at {coord}"
            )
            seen.append(pattern)


class TestMinimal16Layout:
    """Tests for the minimal-16 peering bit lookup table."""

    def test_has_exactly_16_entries(self) -> None:
        assert len(MINIMAL_16_LAYOUT) == 16

    def test_keys_are_col_row_tuples(self) -> None:
        for key in MINIMAL_16_LAYOUT:
            assert isinstance(key, tuple)
            assert len(key) == 2

    def test_each_entry_has_4_side_bits(self) -> None:
        expected_keys = set(PEERING_BIT_NAMES_SIDES)
        for coord, bits in MINIMAL_16_LAYOUT.items():
            assert set(bits.keys()) == expected_keys, (
                f"Tile at {coord} has keys {set(bits.keys())}, "
                f"expected {expected_keys}"
            )

    def test_values_are_0_or_minus_1(self) -> None:
        for coord, bits in MINIMAL_16_LAYOUT.items():
            for bit_name, value in bits.items():
                assert value in (0, -1), (
                    f"Tile at {coord}, bit {bit_name} has value {value}"
                )

    def test_all_16_combinations_present(self) -> None:
        """With 4 binary bits there are exactly 16 combinations."""
        patterns: set[tuple[int, ...]] = set()
        for bits in MINIMAL_16_LAYOUT.values():
            pattern = tuple(bits[k] for k in PEERING_BIT_NAMES_SIDES)
            patterns.add(pattern)
        assert len(patterns) == 16


class TestRPGMakerLayout:
    """Tests for the RPG Maker peering bit lookup table."""

    def test_has_expected_entry_count(self) -> None:
        # RPG Maker A2 autotile has 48 tiles (2 columns x 24 rows)
        # but some may be duplicates; the standard mapping yields 48 positions
        assert len(RPGMAKER_LAYOUT) == 48

    def test_each_entry_has_8_peering_bits(self) -> None:
        expected_keys = set(PEERING_BIT_NAMES_CORNERS_AND_SIDES)
        for coord, bits in RPGMAKER_LAYOUT.items():
            assert set(bits.keys()) == expected_keys, (
                f"Tile at {coord} has keys {set(bits.keys())}"
            )

    def test_values_are_0_or_minus_1(self) -> None:
        for coord, bits in RPGMAKER_LAYOUT.items():
            for bit_name, value in bits.items():
                assert value in (0, -1)

    def test_blob47_constraint_holds_for_rpgmaker(self) -> None:
        """RPG Maker uses Match Corners and Sides; same constraint applies."""
        side_to_corners = {
            "right_side": ("top_right_corner", "bottom_right_corner"),
            "bottom_side": ("bottom_right_corner", "bottom_left_corner"),
            "left_side": ("bottom_left_corner", "top_left_corner"),
            "top_side": ("top_left_corner", "top_right_corner"),
        }
        for coord, bits in RPGMAKER_LAYOUT.items():
            for side, corners in side_to_corners.items():
                if bits[side] == -1:
                    for corner in corners:
                        assert bits[corner] == -1, (
                            f"RPG Maker tile at {coord}: {side}=-1 but "
                            f"{corner}={bits[corner]}"
                        )


# ---------------------------------------------------------------------------
# Constants and mappings
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for module-level constants."""

    def test_peering_bit_names_corners_and_sides_has_8(self) -> None:
        assert len(PEERING_BIT_NAMES_CORNERS_AND_SIDES) == 8

    def test_peering_bit_names_sides_has_4(self) -> None:
        assert len(PEERING_BIT_NAMES_SIDES) == 4

    def test_sides_are_subset_of_corners_and_sides(self) -> None:
        assert set(PEERING_BIT_NAMES_SIDES).issubset(
            set(PEERING_BIT_NAMES_CORNERS_AND_SIDES)
        )

    def test_terrain_modes_blob47(self) -> None:
        assert TERRAIN_MODES["blob-47"] == 0

    def test_terrain_modes_minimal16(self) -> None:
        assert TERRAIN_MODES["minimal-16"] == 2

    def test_terrain_modes_rpgmaker(self) -> None:
        assert TERRAIN_MODES["rpgmaker"] == 0

    def test_layout_map_has_all_layouts(self) -> None:
        assert "blob-47" in LAYOUT_MAP
        assert "minimal-16" in LAYOUT_MAP
        assert "rpgmaker" in LAYOUT_MAP


# ---------------------------------------------------------------------------
# apply_terrain_to_atlas
# ---------------------------------------------------------------------------


class TestApplyTerrainToAtlas:
    """Tests for the apply_terrain_to_atlas function."""

    def _make_atlas_sub(self) -> SubResource:
        """Create a minimal TileSetAtlasSource sub-resource."""
        return SubResource(
            type="TileSetAtlasSource",
            id="TileSetAtlasSource_test",
            properties={},
        )

    def test_sets_terrain_set_property(self) -> None:
        atlas = self._make_atlas_sub()
        apply_terrain_to_atlas(atlas, BLOB_47_LAYOUT)
        # At least the first tile should have terrain_set
        first_coord = next(iter(BLOB_47_LAYOUT))
        prefix = f"{first_coord[0]}:{first_coord[1]}"
        assert atlas.properties[f"{prefix}/terrain_set"] == 0

    def test_sets_terrain_property(self) -> None:
        atlas = self._make_atlas_sub()
        apply_terrain_to_atlas(atlas, BLOB_47_LAYOUT)
        first_coord = next(iter(BLOB_47_LAYOUT))
        prefix = f"{first_coord[0]}:{first_coord[1]}"
        assert atlas.properties[f"{prefix}/terrain"] == 0

    def test_sets_peering_bits_for_all_47_tiles(self) -> None:
        atlas = self._make_atlas_sub()
        apply_terrain_to_atlas(atlas, BLOB_47_LAYOUT)
        terrain_set_keys = [
            k for k in atlas.properties if k.endswith("/terrain_set")
        ]
        assert len(terrain_set_keys) == 47

    def test_peering_bit_properties_present(self) -> None:
        atlas = self._make_atlas_sub()
        apply_terrain_to_atlas(atlas, BLOB_47_LAYOUT)
        first_coord = next(iter(BLOB_47_LAYOUT))
        prefix = f"{first_coord[0]}:{first_coord[1]}"
        for bit_name in PEERING_BIT_NAMES_CORNERS_AND_SIDES:
            key = f"{prefix}/terrain_peering_bit/{bit_name}"
            assert key in atlas.properties, f"Missing {key}"

    def test_custom_terrain_set_and_id(self) -> None:
        atlas = self._make_atlas_sub()
        apply_terrain_to_atlas(atlas, MINIMAL_16_LAYOUT, terrain_set=1, terrain_id=2)
        first_coord = next(iter(MINIMAL_16_LAYOUT))
        prefix = f"{first_coord[0]}:{first_coord[1]}"
        assert atlas.properties[f"{prefix}/terrain_set"] == 1
        assert atlas.properties[f"{prefix}/terrain"] == 2

    def test_minimal_16_produces_side_bits_only(self) -> None:
        atlas = self._make_atlas_sub()
        apply_terrain_to_atlas(atlas, MINIMAL_16_LAYOUT)
        first_coord = next(iter(MINIMAL_16_LAYOUT))
        prefix = f"{first_coord[0]}:{first_coord[1]}"
        for bit_name in PEERING_BIT_NAMES_SIDES:
            key = f"{prefix}/terrain_peering_bit/{bit_name}"
            assert key in atlas.properties


# ---------------------------------------------------------------------------
# add_terrain_set_to_resource
# ---------------------------------------------------------------------------


class TestAddTerrainSetToResource:
    """Tests for the add_terrain_set_to_resource function."""

    def test_adds_mode_for_blob47(self) -> None:
        props: dict = {}
        add_terrain_set_to_resource(props, "blob-47")
        assert props["terrain_set_0/mode"] == 0

    def test_adds_mode_for_minimal16(self) -> None:
        props: dict = {}
        add_terrain_set_to_resource(props, "minimal-16")
        assert props["terrain_set_0/mode"] == 2

    def test_adds_terrains_array(self) -> None:
        props: dict = {}
        add_terrain_set_to_resource(props, "blob-47")
        terrains = props["terrain_set_0/terrains"]
        assert isinstance(terrains, list)
        assert len(terrains) == 1
        assert terrains[0]["name"] == "Terrain"

    def test_custom_terrain_name(self) -> None:
        props: dict = {}
        add_terrain_set_to_resource(props, "rpgmaker", terrain_name="Grass")
        terrains = props["terrain_set_0/terrains"]
        assert terrains[0]["name"] == "Grass"

    def test_terrains_array_has_color(self) -> None:
        props: dict = {}
        add_terrain_set_to_resource(props, "blob-47")
        terrains = props["terrain_set_0/terrains"]
        color = terrains[0]["color"]
        assert isinstance(color, Color)
        assert color.r == 1.0
        assert color.g == 1.0
        assert color.b == 1.0
        assert color.a == 1.0
