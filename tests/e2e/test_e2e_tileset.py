"""E2E tests: TileSet resources load in headless Godot."""

from __future__ import annotations

from pathlib import Path

import pytest

from gdauto.backend import GodotBackend
from gdauto.formats.tres import serialize_tres_file
from gdauto.tileset.builder import build_tileset
from gdauto.tileset.terrain import (
    LAYOUT_MAP,
    add_terrain_set_to_resource,
    apply_terrain_to_atlas,
)


_PROJECT_GODOT = (
    "; Engine configuration file.\n"
    "config_version=5\n\n"
    "[application]\nconfig/name=\"E2ETest\"\n"
)


def _build_tileset_validation_script(tres_name: str) -> str:
    """Create a GDScript that loads and validates a TileSet resource."""
    return (
        "extends SceneTree\n"
        "\n"
        "func _init() -> void:\n"
        f'    var res = load("res://{tres_name}")\n'
        "    if res == null:\n"
        '        print("VALIDATION_FAIL: Could not load TileSet")\n'
        "        quit(1)\n"
        "    if not res is TileSet:\n"
        '        print("VALIDATION_FAIL: Resource is not TileSet, got " + res.get_class())\n'
        "        quit(1)\n"
        "    var sources = res.get_source_count()\n"
        "    if sources == 0:\n"
        '        print("VALIDATION_FAIL: No atlas sources found")\n'
        "        quit(1)\n"
        '    print("VALIDATION_OK: sources=" + str(sources))\n'
        "    quit(0)\n"
    )


def _build_terrain_validation_script(tres_name: str) -> str:
    """Create a GDScript that validates TileSet terrain configuration."""
    return (
        "extends SceneTree\n"
        "\n"
        "func _init() -> void:\n"
        f'    var res = load("res://{tres_name}")\n'
        "    if res == null:\n"
        '        print("VALIDATION_FAIL: Could not load TileSet")\n'
        "        quit(1)\n"
        "    if not res is TileSet:\n"
        '        print("VALIDATION_FAIL: Resource is not TileSet")\n'
        "        quit(1)\n"
        "    var terrain_sets = res.get_terrain_sets_count()\n"
        "    if terrain_sets == 0:\n"
        '        print("VALIDATION_FAIL: No terrain sets found")\n'
        "        quit(1)\n"
        '    var mode = res.get_terrain_set_mode(0)\n'
        '    print("VALIDATION_OK: terrain_sets=" + str(terrain_sets) + " mode=" + str(mode))\n'
        "    quit(0)\n"
    )


@pytest.mark.requires_godot
def test_tileset_loads_in_godot(
    tmp_path: Path, godot_backend: GodotBackend
) -> None:
    """Generate a basic TileSet and validate it loads in headless Godot."""
    # 1. Build TileSet resource
    resource = build_tileset(
        image_res_path="res://tileset.png",
        tile_width=16,
        tile_height=16,
        columns=4,
        rows=4,
    )

    # 2. Write to tmp_path
    tres_path = tmp_path / "test_tileset.tres"
    serialize_tres_file(resource, tres_path)

    # 3. Create project.godot
    (tmp_path / "project.godot").write_text(_PROJECT_GODOT)

    # 4. Create and run validation script
    script = _build_tileset_validation_script("test_tileset.tres")
    script_path = tmp_path / "validate.gd"
    script_path.write_text(script)

    result = godot_backend.run(
        ["--headless", "--script", str(script_path)],
        project_path=tmp_path,
    )
    assert "VALIDATION_OK" in result.stdout


@pytest.mark.requires_godot
def test_tileset_terrain_loads_in_godot(
    tmp_path: Path, godot_backend: GodotBackend
) -> None:
    """Generate a TileSet with blob-47 terrain and validate in headless Godot."""
    # 1. Build TileSet with terrain
    resource = build_tileset(
        image_res_path="res://tileset.png",
        tile_width=16,
        tile_height=16,
        columns=12,
        rows=4,
    )

    # 2. Apply terrain
    add_terrain_set_to_resource(
        resource.resource_properties, "blob-47", "Ground"
    )
    atlas_sub = resource.sub_resources[0]
    apply_terrain_to_atlas(atlas_sub, LAYOUT_MAP["blob-47"])

    # 3. Write to tmp_path
    tres_path = tmp_path / "test_tileset_terrain.tres"
    serialize_tres_file(resource, tres_path)

    # 4. Create project.godot
    (tmp_path / "project.godot").write_text(_PROJECT_GODOT)

    # 5. Create and run terrain validation script
    script = _build_terrain_validation_script("test_tileset_terrain.tres")
    script_path = tmp_path / "validate.gd"
    script_path.write_text(script)

    result = godot_backend.run(
        ["--headless", "--script", str(script_path)],
        project_path=tmp_path,
    )
    assert "VALIDATION_OK" in result.stdout
    assert "terrain_sets=" in result.stdout
