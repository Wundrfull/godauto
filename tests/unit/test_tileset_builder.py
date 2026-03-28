"""Unit tests for PackedVector2Array and TileSet GdResource builder."""

from __future__ import annotations

from gdauto.formats.tres import serialize_tres
from gdauto.formats.values import PackedVector2Array, Vector2i, serialize_value
from gdauto.tileset.builder import build_tileset


# ---------------------------------------------------------------------------
# PackedVector2Array
# ---------------------------------------------------------------------------

class TestPackedVector2Array:
    """Tests for the PackedVector2Array value type."""

    def test_to_godot_integer_values(self) -> None:
        arr = PackedVector2Array((0.0, 0.0, 32.0, 0.0, 32.0, 32.0, 0.0, 32.0))
        assert arr.to_godot() == "PackedVector2Array(0, 0, 32, 0, 32, 32, 0, 32)"

    def test_to_godot_float_values(self) -> None:
        arr = PackedVector2Array((1.5, 2.5))
        assert arr.to_godot() == "PackedVector2Array(1.5, 2.5)"

    def test_serialize_value_integration(self) -> None:
        arr = PackedVector2Array((0.0, 0.0, 16.0, 0.0))
        assert serialize_value(arr) == "PackedVector2Array(0, 0, 16, 0)"

    def test_empty_array(self) -> None:
        arr = PackedVector2Array(())
        assert arr.to_godot() == "PackedVector2Array()"


# ---------------------------------------------------------------------------
# build_tileset
# ---------------------------------------------------------------------------

class TestBuildTileset:
    """Tests for the TileSet GdResource builder."""

    def test_resource_type(self) -> None:
        resource = build_tileset("res://sheet.png", 32, 32, 8, 6)
        assert resource.type == "TileSet"

    def test_format_is_3(self) -> None:
        resource = build_tileset("res://sheet.png", 32, 32, 8, 6)
        assert resource.format == 3

    def test_one_ext_resource_texture2d(self) -> None:
        resource = build_tileset("res://sheet.png", 32, 32, 8, 6)
        assert len(resource.ext_resources) == 1
        assert resource.ext_resources[0].type == "Texture2D"
        assert resource.ext_resources[0].path == "res://sheet.png"

    def test_one_sub_resource_atlas_source(self) -> None:
        resource = build_tileset("res://sheet.png", 32, 32, 8, 6)
        assert len(resource.sub_resources) == 1
        assert resource.sub_resources[0].type == "TileSetAtlasSource"

    def test_atlas_texture_region_size(self) -> None:
        resource = build_tileset("res://sheet.png", 32, 32, 8, 6)
        atlas = resource.sub_resources[0]
        assert atlas.properties["texture_region_size"] == Vector2i(32, 32)

    def test_resource_properties_tile_size(self) -> None:
        resource = build_tileset("res://sheet.png", 32, 32, 8, 6)
        assert resource.resource_properties["tile_size"] == Vector2i(32, 32)

    def test_resource_properties_sources_ref(self) -> None:
        resource = build_tileset("res://sheet.png", 32, 32, 8, 6)
        source_ref = resource.resource_properties["sources/0"]
        from gdauto.formats.values import SubResourceRef
        assert isinstance(source_ref, SubResourceRef)
        assert source_ref.id == resource.sub_resources[0].id

    def test_margin_included_when_nonzero(self) -> None:
        resource = build_tileset("res://sheet.png", 32, 32, 8, 6, margin=2, separation=1)
        atlas = resource.sub_resources[0]
        assert atlas.properties["margins"] == Vector2i(2, 2)
        assert atlas.properties["separation"] == Vector2i(1, 1)

    def test_margin_excluded_when_zero(self) -> None:
        resource = build_tileset("res://sheet.png", 32, 32, 8, 6)
        atlas = resource.sub_resources[0]
        assert "margins" not in atlas.properties
        assert "separation" not in atlas.properties

    def test_load_steps(self) -> None:
        resource = build_tileset("res://sheet.png", 32, 32, 8, 6)
        assert resource.load_steps == 3

    def test_uid_is_set(self) -> None:
        resource = build_tileset("res://sheet.png", 32, 32, 8, 6)
        assert resource.uid is not None
        assert resource.uid.startswith("uid://")


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestTilesetSerialization:
    """Tests for serialized TileSet .tres output."""

    def test_header_contains_tileset(self) -> None:
        resource = build_tileset("res://sheet.png", 32, 32, 8, 6)
        text = serialize_tres(resource)
        assert '[gd_resource type="TileSet"' in text

    def test_contains_atlas_source_section(self) -> None:
        resource = build_tileset("res://sheet.png", 32, 32, 8, 6)
        text = serialize_tres(resource)
        assert '[sub_resource type="TileSetAtlasSource"' in text

    def test_contains_texture_region_size(self) -> None:
        resource = build_tileset("res://sheet.png", 32, 32, 8, 6)
        text = serialize_tres(resource)
        assert "texture_region_size = Vector2i(32, 32)" in text
