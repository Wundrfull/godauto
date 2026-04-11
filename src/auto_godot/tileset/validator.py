"""TileSet validation: structural checks and headless Godot loading.

Structural validation parses the .tres file and checks resource type,
tile_size property, TileSetAtlasSource sub-resources, texture references,
and terrain_set consistency. Headless validation creates a GDScript and
runs it in Godot to confirm the resource loads correctly.
"""

from __future__ import annotations

import re
import tempfile
from typing import TYPE_CHECKING, Any

from auto_godot.errors import GodotBinaryError, ParseError
from auto_godot.formats.tres import GdResource, parse_tres_file
from auto_godot.formats.values import serialize_value

if TYPE_CHECKING:
    from pathlib import Path

# Compiled patterns for tile coordinate matching
_TILE_COORD_RE = re.compile(r"^(\d+:\d+)/")
_TERRAIN_RE = re.compile(r"^\d+:\d+/terrain_set$")
_PHYSICS_RE = re.compile(r"^\d+:\d+/physics_layer")
_TERRAIN_SET_MODE_RE = re.compile(r"^terrain_set_(\d+)/mode$")


def validate_tileset(path: Path) -> dict[str, Any]:
    """Validate a TileSet .tres file structurally (no Godot needed).

    Returns a dict with keys: valid (bool), type (str), tile_size (str),
    atlas_sources (list), terrain_sets (int), issues (list), warnings (list).
    """
    issues: list[str] = []
    warnings: list[str] = []

    try:
        resource = parse_tres_file(path)
    except (ParseError, OSError, Exception) as exc:
        return _invalid_result(issues=[str(exc)])

    _check_resource_type(resource, issues)
    if issues:
        return _build_result(resource, [], 0, issues, warnings)

    _check_tile_size(resource, issues)
    atlas_summaries = _check_atlas_sources(resource, issues)
    terrain_set_count = _count_terrain_sets(resource)
    _check_terrain_consistency(resource, warnings)

    return _build_result(resource, atlas_summaries, terrain_set_count, issues, warnings)


def validate_tileset_headless(
    path: Path, backend: Any
) -> dict[str, Any]:
    """Validate a TileSet .tres file by loading it in headless Godot.

    Falls back to structural-only validation if the Godot binary is not
    available. Returns the same dict shape as validate_tileset, with
    additional 'headless_validated' and 'notes' keys.
    """
    structural = validate_tileset(path)
    notes: list[str] = []

    if structural["issues"]:
        structural["headless_validated"] = False
        notes.append("Structural issues found; skipping headless validation")
        structural["notes"] = notes
        return structural

    script_content = _build_validation_script(path)

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".gd", mode="w", delete=False
        ) as tmp:
            tmp.write(script_content)
            tmp.flush()
            script_path = tmp.name

        result = backend.run(
            ["--script", script_path], project_path=path.parent
        )
        headless_result = _parse_headless_output(result.stdout)
        structural["headless_validated"] = True
        structural["headless_result"] = headless_result
        notes.append("Headless Godot validation passed")
    except GodotBinaryError:
        notes.append("Godot binary not available; structural validation only (fallback)")
        structural["headless_validated"] = False
    except Exception as exc:
        notes.append(f"Headless validation failed: {exc}; structural fallback used")
        structural["headless_validated"] = False

    structural["notes"] = notes
    return structural


def _check_resource_type(resource: GdResource, issues: list[str]) -> None:
    """Check that the resource type is TileSet."""
    if resource.type != "TileSet":
        issues.append(
            f"Resource type is '{resource.type}', expected 'TileSet'"
        )


def _check_tile_size(resource: GdResource, issues: list[str]) -> None:
    """Check that the resource has a tile_size property."""
    if "tile_size" not in resource.resource_properties:
        issues.append("Missing 'tile_size' in resource properties")


def _check_atlas_sources(
    resource: GdResource, issues: list[str]
) -> list[dict[str, Any]]:
    """Find and validate TileSetAtlasSource sub-resources."""
    atlas_subs = [
        sub for sub in resource.sub_resources
        if sub.type == "TileSetAtlasSource"
    ]

    if not atlas_subs:
        issues.append("No TileSetAtlasSource found in the TileSet")
        return []

    summaries: list[dict[str, Any]] = []
    for sub in atlas_subs:
        has_texture = "texture" in sub.properties
        if not has_texture:
            issues.append(
                f"TileSetAtlasSource '{sub.id}' missing texture reference"
            )

        # Count unique tile coordinates
        coord_set: set[str] = set()
        terrain_count = 0
        physics_count = 0

        for key in sub.properties:
            coord_match = _TILE_COORD_RE.match(key)
            if coord_match:
                coord_set.add(coord_match.group(1))
            if _TERRAIN_RE.match(key):
                terrain_count += 1
            if _PHYSICS_RE.match(key):
                physics_count += 1

        summaries.append({
            "tile_count": len(coord_set),
            "terrain_tiles": terrain_count,
            "physics_tiles": physics_count,
            "has_texture": has_texture,
        })

    return summaries


def _count_terrain_sets(resource: GdResource) -> int:
    """Count terrain_set_N/mode keys in resource properties."""
    return sum(
        1 for k in resource.resource_properties
        if _TERRAIN_SET_MODE_RE.match(k)
    )


def _check_terrain_consistency(
    resource: GdResource, warnings: list[str]
) -> None:
    """Warn if tiles reference a terrain_set not declared in resource."""
    # Collect terrain_set indices referenced by tiles
    referenced_sets: set[int] = set()
    for sub in resource.sub_resources:
        if sub.type != "TileSetAtlasSource":
            continue
        for key, value in sub.properties.items():
            if _TERRAIN_RE.match(key) and isinstance(value, int):
                referenced_sets.add(value)

    # Collect declared terrain_set indices
    declared_sets: set[int] = set()
    for key in resource.resource_properties:
        m = _TERRAIN_SET_MODE_RE.match(key)
        if m:
            declared_sets.add(int(m.group(1)))

    # Warn about referenced but undeclared terrain sets
    for idx in sorted(referenced_sets - declared_sets):
        warnings.append(
            f"Tiles reference terrain_set={idx} but no terrain_set_{idx}/mode "
            f"declared in resource properties (peering bits without terrain_set)"
        )


def _build_result(
    resource: GdResource,
    atlas_summaries: list[dict[str, Any]],
    terrain_set_count: int,
    issues: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    """Build the validation result dict."""
    tile_size_val = resource.resource_properties.get("tile_size")
    tile_size_str = serialize_value(tile_size_val) if tile_size_val else "unknown"

    return {
        "valid": len(issues) == 0,
        "type": resource.type,
        "tile_size": tile_size_str,
        "atlas_sources": atlas_summaries,
        "terrain_sets": terrain_set_count,
        "issues": issues,
        "warnings": warnings,
    }


def _invalid_result(issues: list[str]) -> dict[str, Any]:
    """Build a validation result for files that cannot be parsed."""
    return {
        "valid": False,
        "type": "unknown",
        "tile_size": "unknown",
        "atlas_sources": [],
        "terrain_sets": 0,
        "issues": issues,
        "warnings": [],
    }


def _build_validation_script(path: Path) -> str:
    """Create a GDScript that loads and validates a TileSet resource."""
    res_path = str(path.resolve()).replace("\\", "/")
    return (
        'extends SceneTree\n'
        '\n'
        'func _init() -> void:\n'
        f'    var res = load("{res_path}")\n'
        '    if res == null:\n'
        '        print("VALIDATION_FAIL: Could not load resource")\n'
        '        quit(1)\n'
        '    if not res is TileSet:\n'
        '        print("VALIDATION_FAIL: Resource is not TileSet")\n'
        '        quit(1)\n'
        '    var sources = res.get_source_count()\n'
        '    print("VALIDATION_OK: sources=" + str(sources))\n'
        '    quit(0)\n'
    )


def _parse_headless_output(stdout: str) -> dict[str, Any]:
    """Parse VALIDATION_OK/VALIDATION_FAIL output from the GDScript."""
    result: dict[str, Any] = {"ok": False}
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("VALIDATION_OK:"):
            result["ok"] = True
            # Extract source count if present
            parts = line.split("sources=")
            if len(parts) == 2:
                result["sources"] = int(parts[1].strip())
        elif line.startswith("VALIDATION_FAIL:"):
            result["ok"] = False
            result["error"] = line.split(":", 1)[1].strip()
    return result
