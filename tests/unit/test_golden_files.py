"""Golden file comparison tests for generated Godot resources.

Regenerates SpriteFrames, TileSet, and scene resources from known inputs,
normalizes UIDs and resource IDs, and compares against committed reference
files in tests/fixtures/golden/.

Normalization uses anchored regexes (per Pitfall 3 from research) to avoid
false matches on content that merely resembles UIDs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from auto_godot.formats.aseprite import parse_aseprite_json
from auto_godot.formats.tres import serialize_tres
from auto_godot.formats.tscn import serialize_tscn
from auto_godot.scene.builder import build_scene
from auto_godot.sprite.spriteframes import build_spriteframes
from auto_godot.tileset.builder import build_tileset
from auto_godot.tileset.terrain import (
    LAYOUT_MAP,
    add_terrain_set_to_resource,
    apply_terrain_to_atlas,
)


FIXTURES = Path(__file__).parent.parent / "fixtures"
GOLDEN = FIXTURES / "golden"

# ---------------------------------------------------------------------------
# UID and resource ID normalization
# ---------------------------------------------------------------------------

# Anchored patterns to avoid false matches (per Pitfall 3)
_UID_ATTR_PATTERN = re.compile(r'uid="uid://[a-y0-8]+"')
_STANDALONE_UID = re.compile(r"uid://[a-y0-8]+")
_RESOURCE_ID_PATTERN = re.compile(r'id="(\w+)_[a-zA-Z0-9_]{5}"')
_EXT_REF_PATTERN = re.compile(r'ExtResource\("(\w+)_[a-zA-Z0-9_]{5}"\)')
_SUB_REF_PATTERN = re.compile(r'SubResource\("(\w+)_[a-zA-Z0-9_]{5}"\)')

# Strip load_steps=N from file headers (per Pitfall 3/11: anchored to header brackets)
_LOAD_STEPS_PATTERN = re.compile(r" load_steps=\d+")

# Strip unique_id=N from [node] headers (anchored to avoid matching property values)
_UNIQUE_ID_PATTERN = re.compile(r" unique_id=\d+")


def normalize_for_comparison(text: str) -> str:
    """Normalize randomly-generated UIDs and resource IDs for stable comparison.

    Replaces uid="uid://xxx" with uid="uid://NORMALIZED",
    id="Type_xxxxx" with id="Type_XXXXX",
    ExtResource("Type_xxxxx") with ExtResource("Type_XXXXX"),
    SubResource("Type_xxxxx") with SubResource("Type_XXXXX"),
    standalone uid://xxx with uid://NORMALIZED,
    and strips load_steps and unique_id from header lines.
    """
    text = _LOAD_STEPS_PATTERN.sub("", text)
    text = _UNIQUE_ID_PATTERN.sub("", text)
    text = _UID_ATTR_PATTERN.sub('uid="uid://NORMALIZED"', text)
    text = _STANDALONE_UID.sub("uid://NORMALIZED", text)
    text = _RESOURCE_ID_PATTERN.sub(
        lambda m: f'id="{m.group(1)}_XXXXX"', text
    )
    text = _EXT_REF_PATTERN.sub(
        lambda m: f'ExtResource("{m.group(1)}_XXXXX")', text
    )
    text = _SUB_REF_PATTERN.sub(
        lambda m: f'SubResource("{m.group(1)}_XXXXX")', text
    )
    return text


# ---------------------------------------------------------------------------
# Golden file comparison helpers
# ---------------------------------------------------------------------------

def _load_golden(name: str) -> str:
    """Load a golden reference file, stripping Windows line endings."""
    return (GOLDEN / name).read_text().replace("\r\n", "\n")


# ---------------------------------------------------------------------------
# Golden file comparison tests
# ---------------------------------------------------------------------------


def test_golden_spriteframes() -> None:
    """Regenerate SpriteFrames from fixture and compare to golden file."""
    aseprite_data = parse_aseprite_json(FIXTURES / "aseprite_simple.json")
    resource = build_spriteframes(aseprite_data, "res://test_sheet.png")
    generated = normalize_for_comparison(serialize_tres(resource))
    expected = _load_golden("spriteframes_simple.tres")
    assert generated == expected


def test_golden_tileset() -> None:
    """Regenerate TileSet from parameters and compare to golden file."""
    resource = build_tileset(
        image_res_path="res://tileset.png",
        tile_width=16,
        tile_height=16,
        columns=4,
        rows=4,
    )
    generated = normalize_for_comparison(serialize_tres(resource))
    expected = _load_golden("tileset_basic.tres")
    assert generated == expected


def test_golden_scene() -> None:
    """Regenerate scene from definition and compare to golden file."""
    definition = {
        "root": {
            "name": "TestScene",
            "type": "Node2D",
            "children": [
                {
                    "name": "Sprite",
                    "type": "Sprite2D",
                    "properties": {"position": "Vector2(10, 20)"},
                },
            ],
        },
    }
    scene = build_scene(definition)
    generated = normalize_for_comparison(serialize_tscn(scene))
    expected = _load_golden("scene_basic.tscn")
    assert generated == expected


# ---------------------------------------------------------------------------
# Normalization unit tests
# ---------------------------------------------------------------------------


def test_normalize_uid_pattern() -> None:
    """Verify normalization replaces uid attributes correctly."""
    text = 'uid="uid://abc123" other="value"'
    result = normalize_for_comparison(text)
    assert 'uid="uid://NORMALIZED"' in result
    assert 'other="value"' in result


def test_normalize_resource_id_pattern() -> None:
    """Verify normalization replaces resource IDs correctly."""
    text = 'id="Script_ab1Cd"'
    result = normalize_for_comparison(text)
    assert 'id="Script_XXXXX"' in result


def test_normalize_ext_resource_ref() -> None:
    """Verify normalization replaces ExtResource references correctly."""
    text = 'texture = ExtResource("Texture2D_sDQHw")'
    result = normalize_for_comparison(text)
    assert 'ExtResource("Texture2D_XXXXX")' in result


def test_normalize_sub_resource_ref() -> None:
    """Verify normalization replaces SubResource references correctly."""
    text = 'sources/0 = SubResource("TileSetAtlasSource_iW2dr")'
    result = normalize_for_comparison(text)
    assert 'SubResource("TileSetAtlasSource_XXXXX")' in result


def test_normalize_preserves_non_uid_content() -> None:
    """Verify normalization does not change regular content."""
    text = (
        'type="Node2D"\n'
        'name="Player"\n'
        'position = Vector2(100, 200)\n'
        'tile_size = Vector2i(16, 16)\n'
    )
    result = normalize_for_comparison(text)
    assert result == text


def test_normalize_standalone_uid() -> None:
    """Verify normalization replaces standalone uid:// references."""
    text = "uid://dnhachg64twdg"
    result = normalize_for_comparison(text)
    assert result == "uid://NORMALIZED"


def test_normalize_strips_load_steps() -> None:
    """Verify normalization removes load_steps from resource headers."""
    text = '[gd_resource type="SpriteFrames" load_steps=6 format=3 uid="uid://abc"]'
    result = normalize_for_comparison(text)
    assert "load_steps" not in result
    assert 'type="SpriteFrames"' in result
    assert "format=3" in result


def test_normalize_strips_unique_id() -> None:
    """Verify normalization removes unique_id from node headers."""
    text = '[node name="Player" type="Node2D" parent="." unique_id=1234567890]'
    result = normalize_for_comparison(text)
    assert "unique_id" not in result
    assert 'name="Player"' in result
    assert 'parent="."' in result


def test_normalize_preserves_load_steps_in_properties() -> None:
    """Verify normalization does not strip load_steps from non-header context."""
    # This tests that we only strip the attribute form, not a property value
    text = "my_load_steps = 5"
    result = normalize_for_comparison(text)
    assert result == text  # Should be unchanged (no leading space before load_steps)


# ---------------------------------------------------------------------------
# Peering bit validation tests (TEST-03)
# ---------------------------------------------------------------------------


def test_golden_tileset_blob47_terrain() -> None:
    """Verify blob-47 terrain TileSet output structure has correct properties."""
    resource = build_tileset(
        image_res_path="res://tileset.png",
        tile_width=16,
        tile_height=16,
        columns=12,
        rows=4,
    )
    add_terrain_set_to_resource(
        resource.resource_properties, "blob-47", "Ground"
    )
    atlas_sub = resource.sub_resources[0]
    apply_terrain_to_atlas(atlas_sub, LAYOUT_MAP["blob-47"])

    output = normalize_for_comparison(serialize_tres(resource))

    # Verify terrain set declaration is present
    assert "terrain_set_0/mode = 0" in output
    assert "terrain_set_0/terrains" in output

    # Verify per-tile terrain properties exist (blob-47 has 47 tiles)
    terrain_set_lines = [
        line for line in output.splitlines()
        if "/terrain_set = " in line
    ]
    assert len(terrain_set_lines) == 47

    # Verify peering bit properties exist
    peering_lines = [
        line for line in output.splitlines()
        if "/terrain_peering_bit/" in line
    ]
    # 47 tiles x 8 peering bits each = 376
    assert len(peering_lines) == 47 * 8


def test_golden_tileset_minimal16_terrain() -> None:
    """Verify minimal-16 terrain TileSet output structure has correct properties."""
    resource = build_tileset(
        image_res_path="res://tileset.png",
        tile_width=16,
        tile_height=16,
        columns=4,
        rows=4,
    )
    add_terrain_set_to_resource(
        resource.resource_properties, "minimal-16", "Ground"
    )
    atlas_sub = resource.sub_resources[0]
    apply_terrain_to_atlas(atlas_sub, LAYOUT_MAP["minimal-16"])

    output = normalize_for_comparison(serialize_tres(resource))

    # Verify terrain set declaration; mode 2 = MATCH_SIDES
    assert "terrain_set_0/mode = 2" in output
    assert "terrain_set_0/terrains" in output

    # Verify per-tile terrain properties exist (minimal-16 has 16 tiles)
    terrain_set_lines = [
        line for line in output.splitlines()
        if "/terrain_set = " in line
    ]
    assert len(terrain_set_lines) == 16

    # Verify peering bit properties exist
    # minimal-16 uses 4 side bits per tile, but apply_terrain_to_atlas
    # writes all 8 peering bit names (sides + corners) per tile
    peering_lines = [
        line for line in output.splitlines()
        if "/terrain_peering_bit/" in line
    ]
    # The layout dict has 4 side bits per tile, but check that at least
    # the side peering bits are present
    side_bits = [
        line for line in output.splitlines()
        if any(
            s in line
            for s in [
                "terrain_peering_bit/right_side",
                "terrain_peering_bit/bottom_side",
                "terrain_peering_bit/left_side",
                "terrain_peering_bit/top_side",
            ]
        )
    ]
    assert len(side_bits) == 16 * 4
