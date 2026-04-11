"""Terrain peering bit lookup tables and auto-terrain application.

Provides pre-computed peering bit assignments for standard tileset layouts
(blob-47, minimal-16, RPG Maker) and functions to apply them to
TileSetAtlasSource sub-resources.

Peering bit values: 0 = expects neighbor with terrain, -1 = expects empty.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from auto_godot.formats.values import Color

if TYPE_CHECKING:
    from auto_godot.formats.tres import SubResource

# ---------------------------------------------------------------------------
# CellNeighbor peering bit name constants
# ---------------------------------------------------------------------------

RIGHT_SIDE = "right_side"
BOTTOM_RIGHT_CORNER = "bottom_right_corner"
BOTTOM_SIDE = "bottom_side"
BOTTOM_LEFT_CORNER = "bottom_left_corner"
LEFT_SIDE = "left_side"
TOP_LEFT_CORNER = "top_left_corner"
TOP_SIDE = "top_side"
TOP_RIGHT_CORNER = "top_right_corner"

PEERING_BIT_NAMES_CORNERS_AND_SIDES: tuple[str, ...] = (
    RIGHT_SIDE,
    BOTTOM_RIGHT_CORNER,
    BOTTOM_SIDE,
    BOTTOM_LEFT_CORNER,
    LEFT_SIDE,
    TOP_LEFT_CORNER,
    TOP_SIDE,
    TOP_RIGHT_CORNER,
)

PEERING_BIT_NAMES_SIDES: tuple[str, ...] = (
    RIGHT_SIDE,
    BOTTOM_SIDE,
    LEFT_SIDE,
    TOP_SIDE,
)

# ---------------------------------------------------------------------------
# Terrain mode mapping (layout name -> Godot TerrainMode int)
# ---------------------------------------------------------------------------

TERRAIN_MODES: dict[str, int] = {
    "blob-47": 0,      # MATCH_CORNERS_AND_SIDES
    "minimal-16": 2,   # MATCH_SIDES
    "rpgmaker": 0,     # MATCH_CORNERS_AND_SIDES
}

# Shorthand for peering bit values
_E = -1  # empty (no terrain neighbor expected)
_T = 0   # terrain (neighbor with same terrain expected)

# Bit ordering for algorithmic layout generation:
#   bit 0: right_side
#   bit 1: bottom_right_corner
#   bit 2: bottom_side
#   bit 3: bottom_left_corner
#   bit 4: left_side
#   bit 5: top_left_corner
#   bit 6: top_side
#   bit 7: top_right_corner

_BIT_NAMES_ORDERED = (
    RIGHT_SIDE,           # bit 0
    BOTTOM_RIGHT_CORNER,  # bit 1
    BOTTOM_SIDE,          # bit 2
    BOTTOM_LEFT_CORNER,   # bit 3
    LEFT_SIDE,            # bit 4
    TOP_LEFT_CORNER,      # bit 5
    TOP_SIDE,             # bit 6
    TOP_RIGHT_CORNER,     # bit 7
)

# Corner adjacency constraints: each corner requires both adjacent sides.
# If either adjacent side is empty, the corner must also be empty.
_CORNER_CONSTRAINTS: dict[int, tuple[int, int]] = {
    1: (0, 2),  # bottom_right requires right and bottom
    3: (2, 4),  # bottom_left requires bottom and left
    5: (4, 6),  # top_left requires left and top
    7: (0, 6),  # top_right requires right and top
}


def _valid_blob_patterns() -> list[int]:
    """Return all 47 valid 8-bit bitmask patterns for blob tilesets.

    A pattern is valid when: if a corner bit is set, both adjacent
    side bits must also be set. This reduces 256 combos to exactly 47.
    """
    patterns: list[int] = []
    for mask in range(256):
        valid = True
        for corner_bit, (side_a, side_b) in _CORNER_CONSTRAINTS.items():
            if mask & (1 << corner_bit) and (not (mask & (1 << side_a)) or not (mask & (1 << side_b))):
                valid = False
                break
        if valid:
            patterns.append(mask)
    return patterns


def _mask_to_bits8(mask: int) -> dict[str, int]:
    """Convert an 8-bit bitmask to a peering bit dict."""
    return {
        name: _T if (mask & (1 << idx)) else _E
        for idx, name in enumerate(_BIT_NAMES_ORDERED)
    }


# ---------------------------------------------------------------------------
# Blob-47 layout (algorithmic generation)
# ---------------------------------------------------------------------------
# Standard blob-47 tileset layout: all 47 valid 8-bit patterns arranged
# in a 12-column grid (matching community convention from tile_bit_tools,
# Tilesetter, and OpenGameArt blob template).

def _generate_blob47() -> dict[tuple[int, int], dict[str, int]]:
    """Generate the blob-47 layout in a 12-column grid."""
    patterns = _valid_blob_patterns()
    assert len(patterns) == 47, f"Expected 47, got {len(patterns)}"
    columns = 12
    return {
        (idx % columns, idx // columns): _mask_to_bits8(mask)
        for idx, mask in enumerate(patterns)
    }


BLOB_47_LAYOUT: dict[tuple[int, int], dict[str, int]] = _generate_blob47()


# ---------------------------------------------------------------------------
# Minimal-16 layout
# ---------------------------------------------------------------------------
# 4 side bits (right, bottom, left, top), all 16 combinations in a 4x4 grid.

def _generate_minimal16() -> dict[tuple[int, int], dict[str, int]]:
    """Generate the minimal-16 layout: all 16 combinations of 4 side bits."""
    side_names = (RIGHT_SIDE, BOTTOM_SIDE, LEFT_SIDE, TOP_SIDE)
    layout: dict[tuple[int, int], dict[str, int]] = {}
    for mask in range(16):
        col = mask % 4
        row = mask // 4
        bits = {
            name: _T if (mask & (1 << bit_idx)) else _E
            for bit_idx, name in enumerate(side_names)
        }
        layout[(col, row)] = bits
    return layout


MINIMAL_16_LAYOUT: dict[tuple[int, int], dict[str, int]] = _generate_minimal16()


# ---------------------------------------------------------------------------
# RPG Maker layout
# ---------------------------------------------------------------------------
# RPG Maker A2 autotile: 2 columns x 24 rows (48 tiles), using 8-bit
# peering patterns (Match Corners and Sides). The 48 positions include
# all 47 unique blob patterns plus one duplicate (the full-terrain tile).
# Sorted by terrain density (most neighbors first) for RPG Maker's
# visual grouping convention.

def _generate_rpgmaker() -> dict[tuple[int, int], dict[str, int]]:
    """Generate the RPG Maker A2 autotile layout (2 columns x 24 rows)."""
    patterns = _valid_blob_patterns()

    # Sort by terrain density (descending popcount, then descending value)
    sorted_patterns = sorted(
        patterns,
        key=lambda m: (bin(m).count("1"), m),
        reverse=True,
    )
    # Add duplicate of full-terrain tile (0xFF) to fill 48th slot
    sorted_patterns.append(0b11111111)

    return {
        (idx % 2, idx // 2): _mask_to_bits8(mask)
        for idx, mask in enumerate(sorted_patterns)
    }


RPGMAKER_LAYOUT: dict[tuple[int, int], dict[str, int]] = _generate_rpgmaker()


# ---------------------------------------------------------------------------
# Layout map
# ---------------------------------------------------------------------------

LAYOUT_MAP: dict[str, dict[tuple[int, int], dict[str, int]]] = {
    "blob-47": BLOB_47_LAYOUT,
    "minimal-16": MINIMAL_16_LAYOUT,
    "rpgmaker": RPGMAKER_LAYOUT,
}


# ---------------------------------------------------------------------------
# apply_terrain_to_atlas
# ---------------------------------------------------------------------------

def apply_terrain_to_atlas(
    atlas_sub: SubResource,
    layout: dict[tuple[int, int], dict[str, int]],
    terrain_set: int = 0,
    terrain_id: int = 0,
) -> None:
    """Apply terrain peering bits to a TileSetAtlasSource sub-resource.

    For each tile position in the layout, sets terrain_set, terrain,
    and all peering bit properties on the atlas sub-resource.
    """
    for (col, row), bits in layout.items():
        prefix = f"{col}:{row}"
        atlas_sub.properties[f"{prefix}/terrain_set"] = terrain_set
        atlas_sub.properties[f"{prefix}/terrain"] = terrain_id
        for bit_name, value in bits.items():
            key = f"{prefix}/terrain_peering_bit/{bit_name}"
            atlas_sub.properties[key] = value


# ---------------------------------------------------------------------------
# add_terrain_set_to_resource
# ---------------------------------------------------------------------------

def add_terrain_set_to_resource(
    resource_props: dict[str, Any],
    layout_name: str,
    terrain_name: str = "Terrain",
) -> None:
    """Add terrain set declaration to resource-level properties.

    Sets terrain_set_0/mode and terrain_set_0/terrains based on the
    layout type. Must be called before per-tile terrain assignments
    are meaningful to Godot.
    """
    mode = TERRAIN_MODES[layout_name]
    resource_props["terrain_set_0/mode"] = mode
    resource_props["terrain_set_0/terrains"] = [
        {"color": Color(1.0, 1.0, 1.0, 1.0), "name": terrain_name}
    ]
