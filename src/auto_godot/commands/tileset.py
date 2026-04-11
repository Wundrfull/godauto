"""TileSet creation and terrain automation."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import rich_click as click

from auto_godot.errors import AutoGodotError, ParseError, ValidationError
from auto_godot.formats.tres import parse_tres_file, serialize_tres_file
from auto_godot.formats.values import GodotJSONEncoder, serialize_value
from auto_godot.output import GlobalConfig, emit, emit_error
from auto_godot.tileset.builder import build_tileset
from auto_godot.tileset.physics import apply_physics_to_atlas, parse_physics_rule
from auto_godot.tileset.terrain import (
    LAYOUT_MAP,
    add_terrain_set_to_resource,
    apply_terrain_to_atlas,
)
from auto_godot.tileset.tiled import parse_tiled_file
from auto_godot.tileset.validator import validate_tileset, validate_tileset_headless


@click.group(invoke_without_command=True)
@click.pass_context
def tileset(ctx: click.Context) -> None:
    """TileSet creation and terrain automation."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _parse_tile_size(s: str) -> tuple[int, int]:
    """Parse a 'WxH' string into (width, height) positive integers."""
    parts = s.lower().split("x")
    if len(parts) != 2:
        raise ValidationError(
            message=f"Invalid tile size format: {s}",
            code="INVALID_TILE_SIZE",
            fix="Use format WxH (e.g., 32x32)",
        )
    try:
        w, h = int(parts[0]), int(parts[1])
    except ValueError as err:
        raise ValidationError(
            message=f"Invalid tile size values: {s}",
            code="INVALID_TILE_SIZE",
            fix="Width and height must be integers (e.g., 32x32)",
        ) from err
    if w <= 0 or h <= 0:
        raise ValidationError(
            message=f"Tile size must be positive: {s}",
            code="INVALID_TILE_SIZE",
            fix="Width and height must be positive integers",
        )
    return (w, h)


@tileset.command("create")
@click.argument("image", type=click.Path(exists=False))
@click.option(
    "--tile-size",
    type=str,
    required=True,
    help="Tile size as WxH (e.g., 32x32).",
)
@click.option("--columns", type=int, required=True, help="Number of tile columns.")
@click.option("--rows", type=int, required=True, help="Number of tile rows.")
@click.option(
    "--margin", type=int, default=0,
    help="Margin around the atlas edges in pixels. Default: 0.",
)
@click.option(
    "--separation", type=int, default=0,
    help="Separation between tiles in pixels. Default: 0.",
)
@click.option(
    "-o", "--output", type=click.Path(), default=None,
    help="Output .tres path. Default: <image_stem>.tres.",
)
@click.option(
    "--res-path", type=str, default=None,
    help="Godot res:// path for the texture. Default: res://<image filename>.",
)
@click.pass_context
def create(
    ctx: click.Context,
    image: str,
    tile_size: str,
    columns: int,
    rows: int,
    margin: int,
    separation: int,
    output: str | None,
    res_path: str | None,
) -> None:
    """Create a TileSet .tres from a sprite sheet image.

    Generates a Godot TileSet resource with a TileSetAtlasSource configured
    for the given tile dimensions, columns, and rows.
    """
    image_path = Path(image)
    if not image_path.exists():
        emit_error(
            AutoGodotError(
                message=f"File not found: {image}",
                code="FILE_NOT_FOUND",
                fix="Check the path to your sprite sheet image",
            ),
            ctx,
        )
        return

    try:
        tile_w, tile_h = _parse_tile_size(tile_size)
    except ValidationError as exc:
        emit_error(exc, ctx)
        return

    image_res = res_path or f"res://{image_path.name}"
    output_path = Path(output) if output else image_path.with_suffix(".tres")

    resource = build_tileset(image_res, tile_w, tile_h, columns, rows, margin, separation)
    serialize_tres_file(resource, output_path)

    def _human(data: dict[str, Any], verbose: bool = False) -> None:
        click.echo(
            f"Created {data['output_path']} with "
            f"{data['columns']}x{data['rows']} tiles "
            f"({data['tile_size']} each)"
        )

    emit(
        {
            "output_path": str(output_path),
            "tile_size": f"{tile_w}x{tile_h}",
            "columns": columns,
            "rows": rows,
            "total_tiles": columns * rows,
        },
        _human,
        ctx,
    )


@tileset.command("inspect")
@click.argument("tres_file", type=click.Path(exists=False))
@click.pass_context
def inspect(ctx: click.Context, tres_file: str) -> None:
    """Inspect a TileSet .tres resource and display its structure.

    Parses the TileSet and shows atlas sources, tile counts, terrain sets,
    physics layers, and external resource references.
    """
    config: GlobalConfig = ctx.obj
    tres_path = Path(tres_file)

    if not tres_path.exists():
        emit_error(
            AutoGodotError(
                message=f"File not found: {tres_file}",
                code="FILE_NOT_FOUND",
                fix="Check the path to your .tres file",
            ),
            ctx,
        )
        return

    try:
        resource = parse_tres_file(tres_path)
    except (ParseError, Exception) as exc:
        emit_error(
            AutoGodotError(
                message=f"Failed to parse {tres_file}: {exc}",
                code="PARSE_ERROR",
                fix="Ensure the file is a valid Godot .tres resource",
            ),
            ctx,
        )
        return

    if resource.type != "TileSet":
        emit_error(
            AutoGodotError(
                message=f"Resource type is '{resource.type}', not 'TileSet'",
                code="INVALID_RESOURCE_TYPE",
                fix="Expected a TileSet .tres file",
            ),
            ctx,
        )
        return

    data = _build_inspect_data(resource)

    if config.json_mode:
        sys.stdout.write(
            json.dumps(data, cls=GodotJSONEncoder, indent=2) + "\n"
        )
    elif not config.quiet:
        _print_inspect_human(data, verbose=config.verbose)


def _build_inspect_data(resource: Any) -> dict[str, Any]:
    """Build the structured inspection dict for a TileSet resource."""
    tile_size_val = resource.resource_properties.get("tile_size", "unknown")
    tile_size_str = (
        serialize_value(tile_size_val)
        if tile_size_val != "unknown"
        else "unknown"
    )

    atlas_sources = _extract_atlas_sources(resource)
    terrain_sets = _extract_terrain_sets(resource)
    physics_count = _count_physics_layers(resource)

    return {
        "type": resource.type,
        "format": resource.format,
        "uid": resource.uid,
        "tile_size": tile_size_str,
        "atlas_sources": atlas_sources,
        "terrain_sets": terrain_sets,
        "physics_layers": physics_count,
        "ext_resources": [
            {"type": ext.type, "path": ext.path}
            for ext in resource.ext_resources
        ],
    }


def _extract_atlas_sources(resource: Any) -> list[dict[str, Any]]:
    """Extract atlas source info from TileSetAtlasSource sub-resources."""
    sources: list[dict[str, Any]] = []
    tile_coord_re = re.compile(r"^\d+:\d+/")
    terrain_re = re.compile(r"^\d+:\d+/terrain_set")
    physics_re = re.compile(r"^\d+:\d+/physics_layer")

    for sub in resource.sub_resources:
        if sub.type != "TileSetAtlasSource":
            continue
        region_size = sub.properties.get("texture_region_size")
        tile_count = sum(1 for k in sub.properties if tile_coord_re.match(k))
        terrain_tiles = sum(1 for k in sub.properties if terrain_re.match(k))
        physics_tiles = sum(1 for k in sub.properties if physics_re.match(k))
        sources.append({
            "id": sub.id,
            "texture_region_size": (
                serialize_value(region_size) if region_size else "unknown"
            ),
            "tile_count": tile_count,
            "terrain_tiles": terrain_tiles,
            "physics_tiles": physics_tiles,
        })
    return sources


def _extract_terrain_sets(resource: Any) -> list[dict[str, Any]]:
    """Extract terrain set info from resource properties."""
    terrain_sets: list[dict[str, Any]] = []
    mode_re = re.compile(r"^terrain_set_(\d+)/mode$")

    for key in resource.resource_properties:
        m = mode_re.match(key)
        if m:
            idx = int(m.group(1))
            terrain_sets.append({
                "index": idx,
                "mode": serialize_value(resource.resource_properties[key]),
            })
    return terrain_sets


def _count_physics_layers(resource: Any) -> int:
    """Count physics layers defined in resource properties."""
    physics_re = re.compile(r"^physics_layer_\d+")
    return sum(1 for k in resource.resource_properties if physics_re.match(k))


def _print_inspect_human(data: dict[str, Any], verbose: bool = False) -> None:
    """Display TileSet inspection in human-readable format."""
    click.echo(f"TileSet (format={data['format']})")
    click.echo(f"  Tile size: {data['tile_size']}")
    click.echo(f"  Atlas sources: {len(data['atlas_sources'])}")
    for src in data["atlas_sources"]:
        click.echo(
            f"    [{src['id']}] region={src['texture_region_size']}, "
            f"tiles={src['tile_count']}, terrain={src['terrain_tiles']}, "
            f"physics={src['physics_tiles']}"
        )
    if data["terrain_sets"]:
        click.echo(f"  Terrain sets: {len(data['terrain_sets'])}")
    if data["physics_layers"]:
        click.echo(f"  Physics layers: {data['physics_layers']}")
    if data["ext_resources"]:
        click.echo("  External resources:")
        for ext in data["ext_resources"]:
            click.echo(f"    {ext['type']}: {ext['path']}")


# ---------------------------------------------------------------------------
# tileset auto-terrain
# ---------------------------------------------------------------------------


def _find_atlas_source(resource: Any) -> Any | None:
    """Find the first TileSetAtlasSource sub-resource, or None."""
    for sub in resource.sub_resources:
        if sub.type == "TileSetAtlasSource":
            return sub
    return None


@tileset.command("auto-terrain")
@click.argument("tres_file", type=click.Path(exists=False))
@click.option(
    "--layout",
    type=click.Choice(["blob-47", "minimal-16", "rpgmaker"]),
    required=True,
    help="Terrain layout type. Required.",
)
@click.option(
    "--terrain-name",
    type=str,
    default="Terrain",
    help="Name for the terrain. Default: Terrain.",
)
@click.option(
    "-o", "--output", type=click.Path(), default=None,
    help="Output .tres path. Default: overwrite input file.",
)
@click.pass_context
def auto_terrain(
    ctx: click.Context,
    tres_file: str,
    layout: str,
    terrain_name: str,
    output: str | None,
) -> None:
    """Assign terrain peering bits to a TileSet using a standard layout.

    Reads an existing TileSet .tres, applies the selected terrain layout
    (blob-47, minimal-16, or rpgmaker) to the first TileSetAtlasSource,
    and writes the modified resource back.
    """
    tres_path = Path(tres_file)
    if not tres_path.exists():
        emit_error(
            AutoGodotError(
                message=f"File not found: {tres_file}",
                code="FILE_NOT_FOUND",
                fix="Check the path to your .tres file",
            ),
            ctx,
        )
        return

    try:
        resource = parse_tres_file(tres_path)
    except (ParseError, Exception) as exc:
        emit_error(
            AutoGodotError(
                message=f"Failed to parse {tres_file}: {exc}",
                code="PARSE_ERROR",
                fix="Ensure the file is a valid Godot .tres resource",
            ),
            ctx,
        )
        return

    if resource.type != "TileSet":
        emit_error(
            AutoGodotError(
                message=f"Resource type is '{resource.type}', not 'TileSet'",
                code="INVALID_RESOURCE_TYPE",
                fix="Expected a TileSet .tres file",
            ),
            ctx,
        )
        return

    atlas_sub = _find_atlas_source(resource)
    if atlas_sub is None:
        emit_error(
            AutoGodotError(
                message="No TileSetAtlasSource found in the TileSet",
                code="NO_ATLAS_SOURCE",
                fix="Create a TileSet with a TileSetAtlasSource first",
            ),
            ctx,
        )
        return

    selected_layout = LAYOUT_MAP[layout]
    apply_terrain_to_atlas(atlas_sub, selected_layout)
    add_terrain_set_to_resource(resource.resource_properties, layout, terrain_name)

    # Force model-based serialization (properties were modified)
    resource._raw_header = None
    resource._raw_sections = None

    output_path = Path(output) if output else tres_path
    serialize_tres_file(resource, output_path)

    def _human(data: dict[str, Any], verbose: bool = False) -> None:
        click.echo(
            f"Applied {data['layout']} terrain to {data['output_path']} "
            f"({data['tiles_assigned']} tiles)"
        )

    emit(
        {
            "output_path": str(output_path),
            "layout": layout,
            "tiles_assigned": len(selected_layout),
        },
        _human,
        ctx,
    )


# ---------------------------------------------------------------------------
# tileset assign-physics
# ---------------------------------------------------------------------------


@tileset.command("assign-physics")
@click.argument("tres_file", type=click.Path(exists=False))
@click.option(
    "--physics",
    multiple=True,
    required=True,
    type=str,
    help="Tile range and shape: INDEX_RANGE:SHAPE (e.g., 0-15:full, 16-31:none).",
)
@click.option(
    "--columns",
    type=int,
    required=True,
    help="Number of tile columns in the atlas.",
)
@click.option(
    "-o", "--output", type=click.Path(), default=None,
    help="Output .tres path. Default: overwrite input file.",
)
@click.pass_context
def assign_physics(
    ctx: click.Context,
    tres_file: str,
    physics: tuple[str, ...],
    columns: int,
    output: str | None,
) -> None:
    """Batch assign collision shapes to tile ranges in a TileSet.

    Reads an existing TileSet .tres, applies physics rules to the first
    TileSetAtlasSource, and writes the modified resource back. Rules use
    the format INDEX_RANGE:SHAPE (e.g., 0-15:full, 16-31:none).
    """
    tres_path = Path(tres_file)
    if not tres_path.exists():
        emit_error(
            AutoGodotError(
                message=f"File not found: {tres_file}",
                code="FILE_NOT_FOUND",
                fix="Check the path to your .tres file",
            ),
            ctx,
        )
        return

    try:
        resource = parse_tres_file(tres_path)
    except (ParseError, Exception) as exc:
        emit_error(
            AutoGodotError(
                message=f"Failed to parse {tres_file}: {exc}",
                code="PARSE_ERROR",
                fix="Ensure the file is a valid Godot .tres resource",
            ),
            ctx,
        )
        return

    if resource.type != "TileSet":
        emit_error(
            AutoGodotError(
                message=f"Resource type is '{resource.type}', not 'TileSet'",
                code="INVALID_RESOURCE_TYPE",
                fix="Expected a TileSet .tres file",
            ),
            ctx,
        )
        return

    atlas_sub = _find_atlas_source(resource)
    if atlas_sub is None:
        emit_error(
            AutoGodotError(
                message="No TileSetAtlasSource found in the TileSet",
                code="NO_ATLAS_SOURCE",
                fix="Create a TileSet with a TileSetAtlasSource first",
            ),
            ctx,
        )
        return

    # Parse physics rules
    parsed_rules: list[tuple[range, str]] = []
    total_affected = 0
    try:
        for rule_str in physics:
            tile_range, shape_type = parse_physics_rule(rule_str)
            parsed_rules.append((tile_range, shape_type))
            total_affected += len(tile_range)
    except ValidationError as exc:
        emit_error(exc, ctx)
        return

    # Get tile size from resource properties
    tile_size = resource.resource_properties.get("tile_size")
    if tile_size is None:
        emit_error(
            AutoGodotError(
                message="No tile_size found in TileSet resource properties",
                code="MISSING_TILE_SIZE",
                fix="Ensure the TileSet has a tile_size property",
            ),
            ctx,
        )
        return

    apply_physics_to_atlas(
        atlas_sub, parsed_rules, columns, tile_size.x, tile_size.y
    )

    # Add physics layer declaration if not already present
    if "physics_layer_0/collision_layer" not in resource.resource_properties:
        resource.resource_properties["physics_layer_0/collision_layer"] = 1
    if "physics_layer_0/collision_mask" not in resource.resource_properties:
        resource.resource_properties["physics_layer_0/collision_mask"] = 1

    # Force model-based serialization
    resource._raw_header = None
    resource._raw_sections = None

    output_path = Path(output) if output else tres_path
    serialize_tres_file(resource, output_path)

    def _human(data: dict[str, Any], verbose: bool = False) -> None:
        click.echo(
            f"Applied {data['rules_applied']} physics rules to "
            f"{data['output_path']} ({data['tiles_affected']} tiles)"
        )

    emit(
        {
            "output_path": str(output_path),
            "rules_applied": len(parsed_rules),
            "tiles_affected": total_affected,
        },
        _human,
        ctx,
    )


# ---------------------------------------------------------------------------
# tileset import-tiled
# ---------------------------------------------------------------------------


@tileset.command("import-tiled")
@click.argument("tiled_file", type=click.Path(exists=False))
@click.option(
    "-o", "--output", type=click.Path(), default=None,
    help="Output .tres path. Default: <tiled_file_stem>.tres.",
)
@click.option(
    "--res-path", type=str, default=None,
    help="Godot res:// path for the tileset image. Default: res://<image_path>.",
)
@click.pass_context
def import_tiled(
    ctx: click.Context,
    tiled_file: str,
    output: str | None,
    res_path: str | None,
) -> None:
    """Import a Tiled .tmj/.tmx file and create a Godot TileSet .tres.

    Reads the first embedded tileset from a Tiled map file, extracts tile
    size, columns, rows, and image path, then generates a Godot TileSet
    resource with a TileSetAtlasSource.
    """
    tiled_path = Path(tiled_file)
    if not tiled_path.exists():
        emit_error(
            AutoGodotError(
                message=f"File not found: {tiled_file}",
                code="FILE_NOT_FOUND",
                fix="Check the path to your Tiled .tmj or .tmx file",
            ),
            ctx,
        )
        return

    try:
        tilesets = parse_tiled_file(tiled_path)
    except (ValidationError, Exception) as exc:
        emit_error(
            AutoGodotError(
                message=f"Failed to parse {tiled_file}: {exc}",
                code="TILED_PARSE_ERROR",
                fix="Ensure the file is a valid Tiled .tmj or .tmx map",
            ),
            ctx,
        )
        return

    if not tilesets:
        emit_error(
            AutoGodotError(
                message="No embedded tilesets found in the Tiled file",
                code="TILED_NO_TILESETS",
                fix="Ensure the Tiled file contains at least one embedded tileset definition",
            ),
            ctx,
        )
        return

    ts = tilesets[0]
    image_res = res_path or f"res://{ts.image_path}"
    output_path = Path(output) if output else tiled_path.with_suffix(".tres")
    source_format = tiled_path.suffix.lstrip(".").lower()

    resource = build_tileset(
        image_res, ts.tile_width, ts.tile_height,
        ts.columns, ts.rows, ts.margin, ts.spacing,
    )
    serialize_tres_file(resource, output_path)

    def _human(data: dict[str, Any], verbose: bool = False) -> None:
        click.echo(
            f"Imported '{data['tileset_name']}' from {data['source_format']} "
            f"({data['tile_size']}, {data['tile_count']} tiles) -> {data['output_path']}"
        )

    emit(
        {
            "output_path": str(output_path),
            "tileset_name": ts.name,
            "tile_size": f"{ts.tile_width}x{ts.tile_height}",
            "tile_count": ts.tile_count,
            "image": ts.image_path,
            "source_format": source_format,
        },
        _human,
        ctx,
    )


# ---------------------------------------------------------------------------
# tileset validate
# ---------------------------------------------------------------------------


@tileset.command("validate")
@click.argument("tres_file", type=click.Path(exists=False))
@click.option(
    "--godot",
    is_flag=True,
    default=False,
    help="Also validate by loading in headless Godot (requires Godot binary).",
)
@click.pass_context
def validate(ctx: click.Context, tres_file: str, godot: bool) -> None:
    """Validate a TileSet .tres resource file.

    Checks resource type, tile_size, atlas sources, texture references,
    and terrain_set consistency. With --godot, also loads the resource
    in headless Godot to confirm it is valid.
    """
    tres_path = Path(tres_file)
    if not tres_path.exists():
        emit_error(
            AutoGodotError(
                message=f"File not found: {tres_file}",
                code="FILE_NOT_FOUND",
                fix="Check the path to your .tres file",
            ),
            ctx,
        )
        return

    result = validate_tileset(tres_path)

    if godot:
        from auto_godot.backend import GodotBackend

        config: GlobalConfig = ctx.obj
        backend = GodotBackend(
            binary_path=config.godot_path if config else None
        )
        result = validate_tileset_headless(tres_path, backend)

    emit(result, _print_validate_result, ctx)

    if not result["valid"]:
        ctx.exit(1)


def _print_validate_result(data: dict[str, Any], verbose: bool = False) -> None:
    """Display TileSet validation result in human-readable format."""
    if data["valid"]:
        sources = data.get("atlas_sources", [])
        total_tiles = sum(s.get("tile_count", 0) for s in sources)
        terrain_tiles = sum(s.get("terrain_tiles", 0) for s in sources)
        physics_tiles = sum(s.get("physics_tiles", 0) for s in sources)
        click.echo(
            f"Valid TileSet: {total_tiles} tiles, "
            f"{terrain_tiles} with terrain, {physics_tiles} with physics"
        )
    else:
        click.echo(
            f"Invalid TileSet: {len(data['issues'])} issue(s)"
        )
        for issue in data["issues"]:
            click.echo(f"  - {issue}")
