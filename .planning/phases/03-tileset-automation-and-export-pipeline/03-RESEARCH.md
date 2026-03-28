# Phase 3: TileSet Automation and Export Pipeline - Research

**Researched:** 2026-03-28
**Domain:** Godot TileSet .tres generation, terrain peering bits, headless export/import, Tiled format parsing
**Confidence:** HIGH (core format and patterns); MEDIUM (peering bit mappings)

## Summary

Phase 3 delivers two major feature areas: (1) TileSet automation (create, auto-terrain, assign-physics, inspect, import-tiled) and (2) headless export/import pipeline (export release/debug/pack, import with retry logic). Both build on existing Phase 1 infrastructure (parser/serializer, GodotBackend, error handling) and Phase 2 patterns (command structure, output conventions, validation pipeline).

The TileSet .tres format is well-understood from the Godot source code and the Tiled export plugin. A TileSet resource contains TileSetAtlasSource sub-resources with per-tile data using the `x:y/property_name` serialization pattern. Terrain peering bits use 16 CellNeighbor enum values (0-15) covering corners and sides. The 47-tile blob layout maps grid positions to specific combinations of these 8 active peering bits (for Match Corners and Sides mode), while the 16-tile minimal uses only 4 side bits.

The export pipeline is straightforward: thin wrappers around GodotBackend.run() with `--export-release`, `--export-debug`, `--export-pack` Godot CLI flags, plus retry logic for `--import` (exponential backoff with `--quit-after` instead of `--quit`). The auto-import-before-export pattern handles CI/CD's "never opened in editor" problem.

**Primary recommendation:** Implement TileSet generation using the same GdResource/SubResource/ExtResource pattern established for SpriteFrames, with terrain peering bit lookup tables as pure Python dicts mapping (atlas_x, atlas_y) to CellNeighbor bit assignments for each layout type.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Explicit --layout flag required for auto-terrain. User must specify: --layout blob-47, --layout minimal-16, or --layout rpgmaker. No auto-detection. Fail with actionable error if flag is omitted.
- **D-02:** Built-in layouts only for v1. Support blob-47, minimal-16, and rpgmaker. No custom JSON layout mapping. Custom layouts deferred to future milestone.
- **D-03:** Range-based rules via CLI flags. Syntax: --physics 0-15:full --physics 16-31:none. Tile index ranges mapped to shape presets. Scriptable and agent-friendly.
- **D-04:** Two shape types only: full (full tile rectangle) and none (no collision). Half-tiles, slopes, and custom shapes deferred.
- **D-05:** Auto-import before export. If Godot import cache is missing, automatically run godot --headless --import before the export operation. Seamless for CI/CD pipelines.
- **D-06:** Exponential backoff retry for import. Retry up to 3 times with exponential backoff (1s, 2s, 4s). Use --quit-after instead of --quit to avoid known Godot race condition.
- **D-07:** Stderr status lines for progress reporting. Print status updates ("Importing...", "Exporting...", "Done") to stderr. JSON output on stdout stays clean. Consistent with existing emit_error pattern.
- **D-08:** Basic tilemap conversion only. Parse .tmx/.tmj, extract tileset reference, tile size, and tile grid. Generate TileSet .tres with atlas source. No terrain sets, physics, or custom properties from Tiled.
- **D-09:** Support both .tmx (XML via stdlib xml.etree) and .tmj (JSON via stdlib json). Both are zero-dependency. Covers all Tiled users.

### Claude's Discretion
- Internal module organization for tileset commands (single module vs separate create/terrain/physics/inspect)
- Peering bit lookup table structure (dict, enum, or computed from position)
- TileSet .tres format details (sub-resource structure for atlas sources, terrain sets)
- Tiled format version handling and which fields to extract
- tileset inspect output structure and detail level
- Error messages and fix suggestions for all new commands

### Deferred Ideas (OUT OF SCOPE)
- Custom layout JSON mapping for auto-terrain (user-defined position-to-bit mappings)
- Half-tile, slope, and custom collision shapes for assign-physics
- Tiled terrain/Wang set conversion to Godot terrain peering bits
- Tiled custom properties import
- Full Tiled map-to-TileMap scene conversion
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TILE-01 | `gdauto tileset create` accepts sprite sheet + tile size, generates .tres TileSet with TileSetAtlasSource (margin, separation) | TileSet .tres format fully documented; TileSetAtlasSource sub-resource pattern with texture, margins, separation, texture_region_size properties |
| TILE-02 | `gdauto tileset auto-terrain` assigns peering bits for 47-tile blob (Match Corners and Sides, 8 bits) | CellNeighbor enum values 0-15 documented; blob-47 uses right_side(0), bottom_right_corner(3), bottom_side(4), bottom_left_corner(7), left_side(8), top_left_corner(11), top_side(12), top_right_corner(15) |
| TILE-03 | auto-terrain for 16-tile minimal (Match Sides, 4 bits) | Match Sides mode uses only side bits: right_side(0), bottom_side(4), left_side(8), top_side(12) |
| TILE-04 | auto-terrain for RPG Maker layout | RPG Maker uses a known grid arrangement; community-documented position mappings exist |
| TILE-05 | `gdauto tileset assign-physics` batch assigns collision shapes (full, none) to tile ranges | TileData physics properties: x:y/physics_layer_0/polygon_0/points; full = rectangle covering tile_size |
| TILE-06 | `gdauto tileset inspect` dumps TileSet as structured JSON | Existing resource inspect pattern (GdResource.to_dict, GodotJSONEncoder) reusable; extend for TileSet-specific fields |
| TILE-07 | TileSet validation via headless Godot | Same pattern as sprite validate: structural pre-check + optional headless load via GodotBackend |
| TILE-08 | Researched tileset import failures, built preventions | Common pitfalls documented: wrong tile size, misaligned grid, incorrect peering bits, missing terrain_set declaration |
| TILE-09 | `gdauto tileset import-tiled` reads .tmx/.tmj, converts to TileSet | Tiled JSON format: firstgid, tilewidth, tileheight, columns, image properties; TMX uses XML with same semantics |
| EXPT-01 | `gdauto export release` with named preset | Godot CLI: --export-release "Preset Name" output_path; preset names from export_presets.cfg |
| EXPT-02 | `gdauto export debug` with named preset | Godot CLI: --export-debug "Preset Name" output_path |
| EXPT-03 | `gdauto export pack` with named preset | Godot CLI: --export-pack "Preset Name" output_path.pck |
| EXPT-04 | `gdauto import` with retry logic and exponential backoff | GodotBackend.import_resources() already uses --quit-after; add retry wrapper with 1s/2s/4s backoff |
| EXPT-05 | Export auto-runs import if cache missing | Check for .godot/imported/ directory existence before export; if missing, run import first |
</phase_requirements>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| click | 8.3.x | CLI framework | Already established in Phase 1; all new commands follow same patterns |
| rich-click | 1.9.x | CLI help formatting | Drop-in replacement already in use |
| json (stdlib) | stdlib | Tiled .tmj parsing, --json output | Zero dependency, handles all JSON needs |
| xml.etree (stdlib) | stdlib | Tiled .tmx parsing | Zero dependency, per D-09 |
| configparser (stdlib) | stdlib | export_presets.cfg reading | INI-style format; already used for project.godot |

### No New Dependencies Required

Phase 3 requires zero new dependencies. All TileSet operations are pure Python file generation using the existing parser/serializer infrastructure. Export commands wrap GodotBackend. Tiled import uses stdlib json and xml.etree. No Pillow needed (no image manipulation; tile size comes from CLI args, not pixel inspection).

## Architecture Patterns

### Recommended Module Structure
```
src/gdauto/
  tileset/
    __init__.py              # Package marker
    builder.py               # TileSet GdResource builder (create command logic)
    terrain.py               # Peering bit lookup tables and auto-terrain logic
    physics.py               # Collision shape assignment logic
    tiled.py                 # Tiled .tmx/.tmj parser
    validator.py             # TileSet structural and headless validation
  export/
    __init__.py              # Package marker
    pipeline.py              # Export/import orchestration with retry logic
  commands/
    tileset.py               # Click commands (already exists as stub)
    export.py                # Click commands (already exists as stub)
  cli.py                     # Add 'import' command at root level
```

**Rationale:** Matches the sprite/ package pattern from Phase 2. Separating terrain.py isolates the peering bit lookup tables (which are data-heavy) from the builder logic. The export/ package keeps retry and import-cache logic separate from the CLI layer.

### Pattern 1: TileSet GdResource Builder

**What:** Build a TileSet .tres using the same GdResource/SubResource/ExtResource pattern used for SpriteFrames.
**When to use:** For `tileset create` and `tileset auto-terrain` commands.
**Key difference from SpriteFrames:** A TileSet uses a TileSetAtlasSource sub-resource (not AtlasTexture), and per-tile data is stored as properties with the `x:y/property` naming convention.

```python
# TileSet .tres structure (from Godot source + Tiled export plugin):
#
# [gd_resource type="TileSet" load_steps=N format=3 uid="uid://..."]
#
# [ext_resource type="Texture2D" uid="uid://..." path="res://sheet.png" id="Texture2D_xxxxx"]
#
# [sub_resource type="TileSetAtlasSource" id="TileSetAtlasSource_xxxxx"]
# texture = ExtResource("Texture2D_xxxxx")
# texture_region_size = Vector2i(32, 32)
# margins = Vector2i(0, 0)           # only if non-zero
# separation = Vector2i(0, 0)        # only if non-zero
# 0:0/terrain_set = 0                # per-tile terrain assignment
# 0:0/terrain = 0
# 0:0/terrain_peering_bit/right_side = 0
# 0:0/terrain_peering_bit/bottom_right_corner = 0
# 0:0/terrain_peering_bit/bottom_side = 0
# 0:0/terrain_peering_bit/bottom_left_corner = 0
# 0:0/terrain_peering_bit/left_side = 0
# 0:0/terrain_peering_bit/top_left_corner = 0
# 0:0/terrain_peering_bit/top_side = 0
# 0:0/terrain_peering_bit/top_right_corner = 0
# 0:0/physics_layer_0/polygon_0/points = PackedVector2Array(0, 0, 32, 0, 32, 32, 0, 32)
#
# [resource]
# tile_size = Vector2i(32, 32)
# terrain_set_0/mode = 0             # 0=MATCH_CORNERS_AND_SIDES, 1=MATCH_CORNERS, 2=MATCH_SIDES
# terrain_set_0/terrains = [{"color": Color(1, 1, 1, 1), "name": "Terrain"}]
# sources/0 = SubResource("TileSetAtlasSource_xxxxx")
```

### Pattern 2: Peering Bit Lookup Tables

**What:** Pure Python dicts mapping grid (col, row) to a dict of CellNeighbor bit assignments.
**When to use:** For auto-terrain command, applying terrain to an existing TileSet.

```python
# CellNeighbor enum values (from Godot TileSet source)
RIGHT_SIDE = 0
BOTTOM_RIGHT_CORNER = 3
BOTTOM_SIDE = 4
BOTTOM_LEFT_CORNER = 7
LEFT_SIDE = 8
TOP_LEFT_CORNER = 11
TOP_SIDE = 12
TOP_RIGHT_CORNER = 15

# For Match Corners and Sides (blob-47), active bits are:
# right_side, bottom_right_corner, bottom_side, bottom_left_corner,
# left_side, top_left_corner, top_side, top_right_corner
# (8 bits total, corresponding to 4 sides + 4 corners)

# For Match Sides (minimal-16), active bits are:
# right_side, bottom_side, left_side, top_side
# (4 bits total, sides only)

# Layout lookup: dict[(col, row)] -> dict[str, int]
# where keys are peering bit names and values are terrain IDs (-1=empty, 0=terrain)
BLOB_47_LAYOUT: dict[tuple[int, int], dict[str, int]] = {
    (0, 0): {  # example: top-left corner tile
        "right_side": 0, "bottom_side": 0,
        "bottom_right_corner": 0,
        "left_side": -1, "top_side": -1,
        "top_left_corner": -1, "top_right_corner": -1,
        "bottom_left_corner": -1,
    },
    # ... 46 more entries
}
```

### Pattern 3: Export Pipeline with Retry

**What:** Wrap GodotBackend calls with retry logic and auto-import detection.
**When to use:** For all export and import commands.

```python
import time

def import_with_retry(
    backend: GodotBackend,
    project_path: Path,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> None:
    """Import resources with exponential backoff retry.

    Uses --quit-after instead of --quit per D-06 to avoid
    the Godot race condition where the process exits before
    imports complete.
    """
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            backend.import_resources(project_path)
            return
        except GdautoError as exc:
            last_error = exc
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s
                sys.stderr.write(
                    f"Import attempt {attempt + 1} failed, "
                    f"retrying in {delay}s...\n"
                )
                time.sleep(delay)
    raise last_error  # type: ignore[misc]
```

### Pattern 4: Per-Tile Property Serialization

**What:** TileSetAtlasSource uses a special property naming convention for per-tile data.
**Key insight:** Unlike SpriteFrames (which uses a single `animations` array property), TileSets store per-tile properties as individual key-value lines with the format `x:y/property_name`.

The existing _build_tres_from_model() function in tres.py writes SubResource properties from a flat dict. For TileSetAtlasSource, the properties dict will contain keys like `"0:0/terrain_set"`, `"0:0/terrain"`, `"0:0/terrain_peering_bit/right_side"`, etc. The existing serialize_value() function handles all the value types (int, Vector2i, PackedVector2Array). The slash-delimited property names are just string keys; no special handling needed.

### Pattern 5: Tiled Import (Minimal)

**What:** Parse .tmx (XML) or .tmj (JSON) to extract tileset metadata only (per D-08).
**Key fields to extract:**
- From tileset: tilewidth, tileheight, columns, tilecount, image path, margin, spacing
- From map layers: tile GID data (row-major array), layer dimensions

```python
# .tmj (JSON) tileset structure
{
    "tilesets": [{
        "firstgid": 1,
        "tilewidth": 32,
        "tileheight": 32,
        "tilecount": 64,
        "columns": 8,
        "image": "terrain.png",
        "imagewidth": 256,
        "imageheight": 256,
        "margin": 0,
        "spacing": 0
    }]
}

# .tmx (XML) tileset structure
# <tileset firstgid="1" name="terrain" tilewidth="32" tileheight="32"
#          tilecount="64" columns="8">
#     <image source="terrain.png" width="256" height="256"/>
# </tileset>
```

### Anti-Patterns to Avoid
- **Generating terrain peering bits by pixel analysis:** Do NOT inspect the actual sprite sheet image to determine terrain. Use the explicit --layout flag and grid-position-based lookup tables (per D-01).
- **Hard-coding CellNeighbor values by name:** Use named constants, not magic numbers. The enum values are stable but should be defined once and referenced consistently.
- **Monolithic command handler:** Do NOT put TileSet building logic in the Click command function. Separate builder (pure Python, testable) from command (CLI glue).
- **Assuming export_presets.cfg exists:** Always check for the file and provide actionable error if missing.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| XML parsing | Custom XML parser | stdlib xml.etree.ElementTree | Tiled .tmx is standard XML; etree handles it perfectly |
| JSON parsing | Custom JSON parser | stdlib json | Tiled .tmj and Aseprite JSON are standard; json module handles it |
| INI parsing for export_presets.cfg | Custom INI parser | Existing project_cfg pattern or configparser | export_presets.cfg is INI-style like project.godot |
| .tres file generation | String concatenation | Existing GdResource + _build_tres_from_model | Reuse the proven infrastructure from Phase 1 |
| UID generation | Custom random | Existing uid.py generate_uid/generate_resource_id | Already matches Godot's algorithm |
| Godot subprocess management | Direct subprocess.run | Existing GodotBackend | Already handles discovery, version check, timeout, error parsing |
| Retry logic pattern | Ad-hoc sleep loops | Structured retry function with configurable backoff | Testable, reusable, clear timeout behavior |

**Key insight:** Phase 3 should add zero new infrastructure. Every building block exists from Phases 1 and 2. The new code is business logic (peering bit tables, export orchestration) layered on top of existing patterns.

## Common Pitfalls

### Pitfall 1: Wrong Peering Bit Property Names
**What goes wrong:** Using incorrect property name strings for terrain peering bits causes Godot to silently ignore them, producing a TileSet that loads but has no terrain configuration.
**Why it happens:** The property names in the .tres format must match exactly what Godot's TileData serializer expects.
**How to avoid:** Use the exact CellNeighbor-derived names: `right_side`, `bottom_right_corner`, `bottom_side`, `bottom_left_corner`, `left_side`, `top_left_corner`, `top_side`, `top_right_corner`. Verify by loading the generated .tres in Godot and checking terrain painting works.
**Warning signs:** TileSet loads without errors but terrain painting does not select correct tiles.

### Pitfall 2: Missing terrain_set Declaration
**What goes wrong:** Setting peering bits on tiles without first declaring the terrain_set in the [resource] section causes Godot to ignore all terrain data.
**Why it happens:** The terrain_set_0/mode and terrain_set_0/terrains properties must exist in the [resource] section before per-tile terrain assignments in the TileSetAtlasSource are meaningful.
**How to avoid:** Always write terrain_set_0/mode and terrain_set_0/terrains in the resource_properties before referencing terrain_set=0 in per-tile data.
**Warning signs:** No terrain sets visible in Godot editor after loading.

### Pitfall 3: Peering Bit Value -1 vs Omission
**What goes wrong:** Some implementations set unused peering bits to -1 explicitly, while others omit them. Behavior differs depending on whether the tile has terrain_set assigned.
**Why it happens:** In Godot, -1 means "matches empty space" (no terrain), while omitting the property means "unset" (default). A tile with terrain_set=0 and terrain=0 but no peering bits set will only match when ALL neighbors also have the same terrain.
**How to avoid:** For the 47-tile blob layout, explicitly set all 8 peering bits for every tile. For positions where a neighbor should be empty, use -1. Only omit peering bits for tiles that have no terrain assignment (terrain_set=-1).
**Warning signs:** Terrain painting works for some tiles but not edges or corners.

### Pitfall 4: Godot Import Race Condition
**What goes wrong:** Using `--quit` instead of `--quit-after` with `--import` causes Godot to sometimes exit before imports complete, leaving a corrupt .godot/imported/ cache.
**Why it happens:** `--quit` exits immediately after the main loop starts; `--import` may not have finished processing all resources. `--quit-after N` waits N seconds after idle.
**How to avoid:** Always use `--quit-after 30` (or similar timeout) with `--import`, as already implemented in GodotBackend.import_resources().
**Warning signs:** Intermittent "resource not found" errors when exporting after import.

### Pitfall 5: Export Without export_presets.cfg
**What goes wrong:** Running export commands on a project that has never configured export presets fails with an unhelpful Godot error.
**Why it happens:** Godot looks for export_presets.cfg in the project root. Without it, there are no named presets to reference.
**How to avoid:** Check for export_presets.cfg existence before invoking Godot. Provide actionable error: "No export_presets.cfg found. Configure export presets in the Godot editor first."
**Warning signs:** Godot exits with non-zero code but stderr message is unclear.

### Pitfall 6: Tile Index vs Atlas Coordinates Confusion
**What goes wrong:** Mixing up linear tile indices (0, 1, 2, ...) with atlas grid coordinates (col, row) when assigning properties.
**Why it happens:** CLI users think in linear indices ("tile 5"), but the .tres format uses atlas coordinates ("1:0" for column=1, row=0).
**How to avoid:** For --physics flag ranges (D-03), accept linear indices and convert internally: `col = index % columns`, `row = index // columns`. Document this conversion.
**Warning signs:** Wrong tiles get physics assignments.

### Pitfall 7: Tiled firstgid Offset
**What goes wrong:** Tiled tile IDs in map data start at `firstgid` (usually 1), not 0. Subtracting incorrectly causes off-by-one errors.
**Why it happens:** Tiled uses global IDs where 0 means "no tile". The first tile in a tileset has ID=firstgid.
**How to avoid:** When parsing Tiled layer data, subtract firstgid from each GID to get the local tile index (0-based). Handle GID=0 as empty.
**Warning signs:** Generated TileSet has tiles shifted by one position.

## Code Examples

### TileSet GdResource Construction
```python
# Based on existing SpriteFrames builder pattern from Phase 2
from gdauto.formats.tres import ExtResource, GdResource, SubResource
from gdauto.formats.uid import generate_resource_id, generate_uid, uid_to_text
from gdauto.formats.values import ExtResourceRef, Vector2i

def build_tileset(
    image_res_path: str,
    tile_width: int,
    tile_height: int,
    columns: int,
    rows: int,
    margin: int = 0,
    separation: int = 0,
) -> GdResource:
    """Build a TileSet GdResource with a single atlas source."""
    ext = ExtResource(
        type="Texture2D",
        path=image_res_path,
        id=generate_resource_id("Texture2D"),
        uid=uid_to_text(generate_uid()),
    )

    # Build per-tile properties for TileSetAtlasSource
    atlas_props: dict[str, Any] = {
        "texture": ExtResourceRef(ext.id),
        "texture_region_size": Vector2i(tile_width, tile_height),
    }
    if margin > 0:
        atlas_props["margins"] = Vector2i(margin, margin)
    if separation > 0:
        atlas_props["separation"] = Vector2i(separation, separation)

    # Per-tile entries (just declaring tiles exist; no terrain yet)
    for row in range(rows):
        for col in range(columns):
            # Tiles are implicitly created by referencing them
            # No explicit property needed for basic tile existence
            pass

    atlas_sub = SubResource(
        type="TileSetAtlasSource",
        id=generate_resource_id("TileSetAtlasSource"),
        properties=atlas_props,
    )

    resource_props: dict[str, Any] = {
        "tile_size": Vector2i(tile_width, tile_height),
    }
    # sources/0 references the atlas sub-resource
    # Note: this is a top-level resource property
    resource_props["sources/0"] = SubResourceRef(atlas_sub.id)

    load_steps = 1 + 1 + 1  # ext_resource + sub_resource + resource
    return GdResource(
        type="TileSet",
        format=3,
        uid=uid_to_text(generate_uid()),
        load_steps=load_steps,
        ext_resources=[ext],
        sub_resources=[atlas_sub],
        resource_properties=resource_props,
    )
```

### Terrain Peering Bit Assignment
```python
# Add terrain configuration to an existing TileSet sub-resource
def apply_terrain_to_atlas(
    atlas_sub: SubResource,
    layout: dict[tuple[int, int], dict[str, int]],
    terrain_set: int = 0,
    terrain_id: int = 0,
) -> None:
    """Apply terrain peering bits to tiles based on layout mapping."""
    for (col, row), bits in layout.items():
        prefix = f"{col}:{row}"
        atlas_sub.properties[f"{prefix}/terrain_set"] = terrain_set
        atlas_sub.properties[f"{prefix}/terrain"] = terrain_id
        for bit_name, value in bits.items():
            atlas_sub.properties[
                f"{prefix}/terrain_peering_bit/{bit_name}"
            ] = value
```

### Export Pipeline Command
```python
# Export with auto-import and retry
@export.command("release")
@click.argument("preset")
@click.option("-o", "--output", required=True, type=click.Path())
@click.option("--project", type=click.Path(exists=True), default=".")
@click.pass_context
def export_release(ctx, preset, output, project):
    """Export a release build using a named preset."""
    project_path = Path(project)
    config = ctx.obj
    backend = GodotBackend(binary_path=config.godot_path)

    # D-05: auto-import if cache missing
    imported_dir = project_path / ".godot" / "imported"
    if not imported_dir.exists():
        sys.stderr.write("Import cache missing, running import first...\n")
        import_with_retry(backend, project_path)

    sys.stderr.write(f"Exporting release: {preset}...\n")
    backend.run(
        ["--export-release", preset, str(output)],
        project_path=project_path,
    )
    sys.stderr.write("Done.\n")
```

### Tiled .tmj Parser (Minimal)
```python
import json
from pathlib import Path
from dataclasses import dataclass

@dataclass
class TiledTileset:
    """Minimal tileset data extracted from Tiled .tmj file."""
    name: str
    tile_width: int
    tile_height: int
    columns: int
    tile_count: int
    image_path: str
    image_width: int
    image_height: int
    margin: int = 0
    spacing: int = 0

def parse_tiled_json(path: Path) -> list[TiledTileset]:
    """Parse a Tiled .tmj file, extracting tileset definitions."""
    data = json.loads(path.read_text())
    tilesets = []
    for ts in data.get("tilesets", []):
        # Handle external tileset references
        if "source" in ts and "tilewidth" not in ts:
            # External .tsj file; resolve relative to .tmj
            continue  # or load the .tsj
        tilesets.append(TiledTileset(
            name=ts.get("name", ""),
            tile_width=ts["tilewidth"],
            tile_height=ts["tileheight"],
            columns=ts.get("columns", 1),
            tile_count=ts.get("tilecount", 0),
            image_path=ts.get("image", ""),
            image_width=ts.get("imagewidth", 0),
            image_height=ts.get("imageheight", 0),
            margin=ts.get("margin", 0),
            spacing=ts.get("spacing", 0),
        ))
    return tilesets
```

## Godot TileSet .tres Format Reference

### Complete File Structure
```
[gd_resource type="TileSet" load_steps=N format=3 uid="uid://xxxxx"]

[ext_resource type="Texture2D" uid="uid://yyyyy" path="res://sheet.png" id="Texture2D_abcde"]

[sub_resource type="TileSetAtlasSource" id="TileSetAtlasSource_fghij"]
texture = ExtResource("Texture2D_abcde")
texture_region_size = Vector2i(32, 32)
0:0/terrain_set = 0
0:0/terrain = 0
0:0/terrain_peering_bit/right_side = 0
0:0/terrain_peering_bit/bottom_right_corner = 0
0:0/terrain_peering_bit/bottom_side = 0
0:0/terrain_peering_bit/bottom_left_corner = 0
0:0/terrain_peering_bit/left_side = 0
0:0/terrain_peering_bit/top_left_corner = 0
0:0/terrain_peering_bit/top_side = 0
0:0/terrain_peering_bit/top_right_corner = 0
0:0/physics_layer_0/polygon_0/points = PackedVector2Array(0, 0, 32, 0, 32, 32, 0, 32)
1:0/terrain_set = 0
1:0/terrain = 0
...

[resource]
tile_size = Vector2i(32, 32)
terrain_set_0/mode = 0
terrain_set_0/terrains = [{"color": Color(1, 1, 1, 1), "name": "Ground"}]
sources/0 = SubResource("TileSetAtlasSource_fghij")
```

### Key Property Conventions
- **Per-tile properties:** `col:row/property_name` (e.g., `0:0/terrain_set`)
- **Nested per-tile:** `col:row/category/sub_property` (e.g., `0:0/terrain_peering_bit/right_side`)
- **Physics polygons:** `col:row/physics_layer_N/polygon_N/points`
- **Terrain set config:** `terrain_set_N/mode` (0=corners+sides, 1=corners, 2=sides)
- **Terrain set terrains:** `terrain_set_N/terrains` (array of dicts with name and color)
- **Source assignment:** `sources/N` referencing a TileSetAtlasSource SubResource

### CellNeighbor Enum (Godot Source)
| Constant | Value | Used In |
|----------|-------|---------|
| RIGHT_SIDE | 0 | corners+sides, sides |
| RIGHT_CORNER | 1 | corners only (not used in square grid) |
| BOTTOM_RIGHT_SIDE | 2 | (not used in square grid) |
| BOTTOM_RIGHT_CORNER | 3 | corners+sides, corners |
| BOTTOM_SIDE | 4 | corners+sides, sides |
| BOTTOM_CORNER | 5 | (not used in square grid) |
| BOTTOM_LEFT_SIDE | 6 | (not used in square grid) |
| BOTTOM_LEFT_CORNER | 7 | corners+sides, corners |
| LEFT_SIDE | 8 | corners+sides, sides |
| LEFT_CORNER | 9 | (not used in square grid) |
| TOP_LEFT_SIDE | 10 | (not used in square grid) |
| TOP_LEFT_CORNER | 11 | corners+sides, corners |
| TOP_SIDE | 12 | corners+sides, sides |
| TOP_CORNER | 13 | (not used in square grid) |
| TOP_RIGHT_SIDE | 14 | (not used in square grid) |
| TOP_RIGHT_CORNER | 15 | corners+sides, corners |

For square tiles, the active peering bit names in the .tres format are:
- **Match Corners and Sides (mode=0):** right_side, bottom_right_corner, bottom_side, bottom_left_corner, left_side, top_left_corner, top_side, top_right_corner (8 bits)
- **Match Sides (mode=2):** right_side, bottom_side, left_side, top_side (4 bits)
- **Match Corners (mode=1):** bottom_right_corner, bottom_left_corner, top_left_corner, top_right_corner (4 bits)

### Terrain Peering Bit Semantics
- Value `0` (or any terrain ID >= 0): This bit expects a neighbor tile with that terrain ID
- Value `-1`: This bit expects empty space (no tile, or a tile without this terrain)
- Property omitted: The bit is unset (default behavior, treated as "don't care" during matching)

## Terrain Layout Mappings

### Blob-47 Layout (Match Corners and Sides)

The 47-tile blob layout is the standard for full autotiling. It covers all 47 unique neighbor combinations when both corner and side adjacency matter. The constraint that reduces 256 possibilities to 47 is: if a side is empty, the adjacent corners must also be empty.

The exact grid positions for the standard blob-47 layout are community conventions, not officially documented by Godot. Multiple community references (tile_bit_tools, Tilesetter, autotiler) use consistent mappings. The implementation should define these as a Python dict mapping (col, row) -> peering bit assignments.

**Confidence: MEDIUM** -- The mappings are reverse-engineered from community tools (tile_bit_tools, Tilesetter, OpenGameArt templates). There is no official Godot documentation for position-to-bit mappings. Validation against a real Godot project is essential.

**Recommended approach:**
1. Create a reference TileSet in Godot editor using the blob-47 template from tile_bit_tools
2. Export as .tres and extract the peering bit mappings from the text file
3. Encode these mappings as a Python dict in terrain.py
4. Validate by generating a .tres, loading it in Godot, and testing terrain painting

### Minimal-16 Layout (Match Sides)

Uses only the 4 side bits, producing 16 unique tiles (2^4). Grid positions follow the standard marching-squares convention.

**Confidence: HIGH** -- 16-tile side-only matching is mathematically straightforward: each of the 4 bits is either on or off, giving exactly 16 combinations.

### RPG Maker Layout

RPG Maker uses a specific arrangement where tiles are grouped into 2x3 blocks with predictable adjacency patterns. The mapping is well-documented in the RPG Maker community.

**Confidence: MEDIUM** -- RPG Maker layouts are well-documented but the exact mapping to Godot's peering bit system requires translation from RPG Maker's A2/A3/A4 tile conventions.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| --quit for headless import | --quit-after for reliable import | Godot 4.2+ | Prevents race condition where Godot exits before imports complete |
| --export for release builds | --export-release (explicit) | Godot 4.0+ | Clearer intent; --export-debug and --export-pack added |
| TileSet with autotile bitmask (Godot 3) | TileSet with terrain peering bits (Godot 4) | Godot 4.0 | Completely different system; 3.x bitmask patterns do not apply |
| Separate TileMap and TileSet nodes | TileSet as Resource on TileMapLayer | Godot 4.3+ | TileMap split into TileMapLayer nodes; TileSet remains a resource |
| --export-patch not available | --export-patch for delta updates | Godot 4.5+ | Can export only changed resources; relevant for CI/CD |

**Deprecated/outdated:**
- Godot 3.x autotile bitmask system: completely replaced by terrain peering bits in Godot 4.x
- TileMap node (single): split into TileMapLayer nodes in Godot 4.3+
- `--export` flag (bare): renamed to `--export-release` for clarity

## Open Questions

1. **Exact blob-47 grid position-to-peering-bit mapping**
   - What we know: The constraint that reduces 256 to 47 tiles is well-understood (side empty implies adjacent corners empty). Community tools (tile_bit_tools, Tilesetter) implement consistent mappings.
   - What's unclear: There is no single "official" standard for which grid position corresponds to which bitmask. Different tileset artists may arrange their 47 tiles differently.
   - Recommendation: Support the most common convention (Tilesetter/tile_bit_tools standard, which matches the OpenGameArt template). Validate against a reference TileSet created in Godot. The --layout flag makes it explicit which convention is expected.

2. **RPG Maker A2 tile arrangement specifics**
   - What we know: RPG Maker uses a 2x3 block arrangement per terrain type with specific rules for which sub-tiles are combined.
   - What's unclear: The exact mapping from RPG Maker's sub-tile system to Godot's per-tile peering bits.
   - Recommendation: Research RPG Maker auto-tile documentation. If too complex for v1, this layout could ship as best-effort with clear documentation of limitations.

3. **Property name for terrain peering bits in the .tres format**
   - What we know: Per-tile properties use `col:row/terrain_peering_bit/bit_name` format based on Tiled export plugin source code and Godot header files.
   - What's unclear: Whether the bit names in the .tres format use snake_case identifiers matching CellNeighbor enum names, or some other convention.
   - Recommendation: Generate a test TileSet in Godot editor, inspect the .tres output, and verify exact property names. This is a critical validation step before implementation. **Confidence: MEDIUM** -- needs verification against actual Godot output.

4. **export_presets.cfg parsing completeness**
   - What we know: INI-style format with [preset.N] sections containing name, platform, export_path. [preset.N.options] contains platform-specific settings.
   - What's unclear: Whether we need to parse export_presets.cfg at all, or just pass the preset name directly to Godot.
   - Recommendation: For v1, just pass the preset name string to Godot's --export-release flag. Let Godot handle preset resolution. Only parse export_presets.cfg if we need to validate preset names before invocation or list available presets.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All commands | Yes | 3.13.0 (via uv) | -- |
| Godot binary | export/import commands, TileSet validation (TILE-07) | No (not on PATH) | -- | Pure Python commands work without Godot; export/import and validation skip gracefully |
| uv | Package management | Yes | 0.9.7 | -- |
| xml.etree (stdlib) | Tiled .tmx import | Yes (stdlib) | -- | -- |
| json (stdlib) | Tiled .tmj import, --json output | Yes (stdlib) | -- | -- |

**Missing dependencies with no fallback:**
- None (all core TileSet generation is pure Python)

**Missing dependencies with fallback:**
- Godot binary: Required for export/import/validation commands only. All tileset create/auto-terrain/assign-physics/inspect/import-tiled commands work without Godot. Tests marked `@pytest.mark.requires_godot` will be skipped.

## Project Constraints (from CLAUDE.md)

- **Tech stack:** Python 3.10+, Click >= 8.0, pytest >= 7.0 (all satisfied)
- **Independence:** No Godot dependency for file manipulation commands (tileset create, auto-terrain, assign-physics, inspect, import-tiled)
- **Error contract:** All errors produce non-zero exit codes and actionable messages; --json errors produce `{"error": "message", "code": "ERROR_CODE"}`
- **File validity:** Generated .tres files must be loadable by Godot without modification
- **Code style:** No em dashes, no emojis, type hints on all signatures, docstrings on public functions, functions under 30 lines, comments on non-obvious logic only
- **GSD Workflow:** All changes through GSD commands
- **Granularity:** coarse (from config.json)

## Sources

### Primary (HIGH confidence)
- Godot source: scene/resources/2d/tile_set.h -- TileSet, TileData, TileSetAtlasSource class definitions, terrain_peering_bits[16] array, CellNeighbor enum
- Godot source: TileSet.xml API docs -- TerrainMode enum (MATCH_CORNERS_AND_SIDES=0, MATCH_CORNERS=1, MATCH_SIDES=2), CellNeighbor enum (16 values, 0-15)
- Godot source: TileData.xml API docs -- terrain_set, terrain properties, get/set_terrain_peering_bit methods, collision polygon methods
- [Tiled export plugin (tscnplugin.cpp)](https://raw.githubusercontent.com/mapeditor/tiled/master/src/plugins/tscn/tscnplugin.cpp) -- TileSetAtlasSource .tres serialization format with x:y/property pattern, texture/margins/separation properties
- [Godot CellNeighbor C# API](https://straydragon.github.io/godot-csharp-api-doc/4.4-stable/main/Godot.TileSet.CellNeighbor.html) -- All 16 enum values with indices
- [DeepWiki Tiled formats](https://deepwiki.com/mapeditor/tiled/8.1-tmx-and-json-formats) -- JSON and TMX tileset structure with all fields

### Secondary (MEDIUM confidence)
- [Boris the Brave: Classification of Tilesets](https://www.boristhebrave.com/2021/11/14/classification-of-tilesets/) -- Blob-47 constraint explanation (side empty implies corner empty), marching squares 16-tile
- [Excalibur.js Autotiling Technique](https://excaliburjs.com/blog/Autotiling%20Technique/) -- 8-neighbor bit encoding, bitmask-to-coordinate lookup concept
- [tile_bit_tools plugin](https://github.com/dandeliondino/tile_bit_tools) -- Blob, Wang, and 3-terrain templates for Godot 4 terrain peering bits
- [Godot demo hexagonal tileset.tres](https://github.com/godotengine/godot-demo-projects/blob/master/2d/hexagonal_map/tileset.tres) -- Example TileSet .tres file structure (hex, no terrain, but shows atlas source pattern)
- [Godot issue #69511](https://github.com/godotengine/godot/issues/69511) -- Export reimport reliability issues, --import + --quit-after workaround

### Tertiary (LOW confidence)
- Blob-47 exact grid position mappings -- Community convention, no official standard. Multiple tools agree but needs validation against Godot output.
- RPG Maker layout specifics -- Requires translation from RPG Maker's sub-tile system to Godot peering bits.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Zero new dependencies; all from existing project
- Architecture: HIGH -- Direct extension of Phase 1/2 patterns; TileSet .tres format confirmed from Godot source and Tiled plugin
- TileSet .tres format: HIGH -- Property names and structure confirmed from multiple Godot source files and Tiled export plugin
- Peering bit mappings (blob-47): MEDIUM -- Constraint well understood, but exact grid layout is community convention needing validation
- Peering bit mappings (minimal-16): HIGH -- Mathematically straightforward 2^4 combinations
- Peering bit mappings (RPG Maker): MEDIUM -- Documented but translation to Godot peering bits needs verification
- Export pipeline: HIGH -- Godot CLI flags well documented; GodotBackend already implements core operations
- Tiled import: HIGH -- Format specification is stable and well documented

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stable domain; Godot file format changes rarely)
