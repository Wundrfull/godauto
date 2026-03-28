"""TileSet GdResource builder.

Constructs Godot TileSet resources from sprite sheet parameters. Produces
GdResource instances with TileSetAtlasSource sub-resources ready for
.tres serialization.
"""

from __future__ import annotations

from gdauto.formats.tres import ExtResource, GdResource, SubResource
from gdauto.formats.uid import generate_resource_id, generate_uid, uid_to_text
from gdauto.formats.values import ExtResourceRef, SubResourceRef, Vector2i


def build_tileset(
    image_res_path: str,
    tile_width: int,
    tile_height: int,
    columns: int,
    rows: int,
    margin: int = 0,
    separation: int = 0,
) -> GdResource:
    """Build a TileSet GdResource from sprite sheet parameters.

    Creates one ExtResource for the texture and one TileSetAtlasSource
    SubResource configured with tile size, optional margins, and separation.
    """
    ext = ExtResource(
        type="Texture2D",
        path=image_res_path,
        id=generate_resource_id("Texture2D"),
        uid=uid_to_text(generate_uid()),
    )

    atlas_props = _build_atlas_properties(ext, tile_width, tile_height, margin, separation)
    atlas_sub = SubResource(
        type="TileSetAtlasSource",
        id=generate_resource_id("TileSetAtlasSource"),
        properties=atlas_props,
    )

    resource_props = {
        "tile_size": Vector2i(tile_width, tile_height),
        "sources/0": SubResourceRef(atlas_sub.id),
    }

    return GdResource(
        type="TileSet",
        format=3,
        uid=uid_to_text(generate_uid()),
        load_steps=3,
        ext_resources=[ext],
        sub_resources=[atlas_sub],
        resource_properties=resource_props,
    )


def _build_atlas_properties(
    ext: ExtResource,
    tile_width: int,
    tile_height: int,
    margin: int,
    separation: int,
) -> dict:
    """Build the property dict for a TileSetAtlasSource sub-resource."""
    props: dict = {
        "texture": ExtResourceRef(ext.id),
        "texture_region_size": Vector2i(tile_width, tile_height),
    }
    if margin > 0:
        props["margins"] = Vector2i(margin, margin)
    if separation > 0:
        props["separation"] = Vector2i(separation, separation)
    return props
