"""Physics collision shape assignment for TileSet tiles.

Provides functions to parse physics rules (index range + shape type) and
apply collision shapes to TileSetAtlasSource sub-resources. Supports
'full' (full-tile rectangle) and 'none' (no collision) shape types.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from auto_godot.errors import ValidationError
from auto_godot.formats.values import PackedVector2Array

if TYPE_CHECKING:
    from auto_godot.formats.tres import SubResource

# Valid shape types per D-04: only 'full' and 'none'
_VALID_SHAPES = ("full", "none")


def parse_physics_rule(rule: str) -> tuple[range, str]:
    """Parse a physics rule string into a tile range and shape type.

    Accepts formats:
      "N:type"   - single tile index (e.g., "5:full")
      "N-M:type" - tile index range (e.g., "0-15:full")

    Valid shape types: "full", "none".

    Raises ValidationError with code INVALID_PHYSICS_RULE if malformed.
    """
    parts = rule.rsplit(":", 1)
    if len(parts) != 2:
        raise ValidationError(
            message=f"Invalid physics rule format: {rule}",
            code="INVALID_PHYSICS_RULE",
            fix="Use format INDEX:SHAPE or INDEX_START-INDEX_END:SHAPE (e.g., 0-15:full)",
        )

    range_str, shape_type = parts[0].strip(), parts[1].strip()

    if shape_type not in _VALID_SHAPES:
        raise ValidationError(
            message=f"Invalid shape type '{shape_type}' in rule: {rule}",
            code="INVALID_PHYSICS_RULE",
            fix=f"Valid shape types are: {', '.join(_VALID_SHAPES)}",
        )

    try:
        if "-" in range_str:
            start_str, end_str = range_str.split("-", 1)
            start, end = int(start_str), int(end_str)
            tile_range = range(start, end + 1)
        else:
            idx = int(range_str)
            tile_range = range(idx, idx + 1)
    except ValueError as err:
        raise ValidationError(
            message=f"Invalid tile index range '{range_str}' in rule: {rule}",
            code="INVALID_PHYSICS_RULE",
            fix="Tile indices must be integers (e.g., 0-15:full or 5:none)",
        ) from err

    return tile_range, shape_type


def apply_physics_to_atlas(
    atlas_sub: SubResource,
    rules: list[tuple[range, str]],
    columns: int,
    tile_width: int,
    tile_height: int,
) -> None:
    """Apply physics collision shapes to tiles in a TileSetAtlasSource.

    For each rule, converts tile indices to atlas (col, row) coordinates
    and assigns the appropriate collision shape. 'full' creates a
    rectangle covering the entire tile; 'none' skips the tile.
    """
    w = float(tile_width)
    h = float(tile_height)

    for tile_range, shape_type in rules:
        if shape_type == "none":
            continue
        for index in tile_range:
            col = index % columns
            row = index // columns
            prefix = f"{col}:{row}"
            if shape_type == "full":
                points = PackedVector2Array((0.0, 0.0, w, 0.0, w, h, 0.0, h))
                key = f"{prefix}/physics_layer_0/polygon_0/points"
                atlas_sub.properties[key] = points
