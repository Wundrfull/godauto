"""E2E tests: TileSet resources load in headless Godot."""

from __future__ import annotations

import struct
import zlib
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


def _create_minimal_png(path: Path, width: int = 64, height: int = 64) -> None:
    """Write a valid minimal RGB PNG file using only stdlib (no Pillow).

    Creates a solid-color image with the given dimensions. Each chunk
    follows the PNG spec: 4-byte length + 4-byte type + data + 4-byte CRC32.
    """
    signature = b"\x89PNG\r\n\x1a\n"

    # IHDR: width, height, bit_depth=8, color_type=2 (RGB), compress=0, filter=0, interlace=0
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = _png_chunk(b"IHDR", ihdr_data)

    # IDAT: raw pixel data (filter byte 0 + 3 zero bytes per pixel per row)
    raw_rows = b""
    for _ in range(height):
        raw_rows += b"\x00" + b"\x00\x00\x00" * width
    compressed = zlib.compress(raw_rows)
    idat_chunk = _png_chunk(b"IDAT", compressed)

    # IEND
    iend_chunk = _png_chunk(b"IEND", b"")

    path.write_bytes(signature + ihdr_chunk + idat_chunk + iend_chunk)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a single PNG chunk: length + type + data + CRC32."""
    length = struct.pack(">I", len(data))
    crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    return length + chunk_type + data + crc


def _build_atlas_bounds_validation_script(tres_name: str) -> str:
    """Create a GDScript that validates TileSet atlas bounds are within texture."""
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
        "    var atlas: TileSetAtlasSource = res.get_source(0)\n"
        "    if atlas.has_tiles_outside_texture():\n"
        '        print("VALIDATION_FAIL: Tiles outside texture detected")\n'
        "        quit(1)\n"
        '    print("VALIDATION_OK: sources=" + str(sources) + " bounds=valid")\n'
        "    quit(0)\n"
    )


@pytest.mark.requires_godot
def test_tileset_no_load_steps(
    tmp_path: Path, godot_backend: GodotBackend
) -> None:
    """Validate TileSet without load_steps loads in headless Godot (VAL-01)."""
    # 1. Build TileSet resource
    resource = build_tileset(
        image_res_path="res://tileset.png",
        tile_width=16,
        tile_height=16,
        columns=4,
        rows=4,
    )

    # 2. Confirm load_steps is None at the Python level
    assert resource.load_steps is None

    # 3. Write to tmp_path
    tres_path = tmp_path / "test_nols_tileset.tres"
    serialize_tres_file(resource, tres_path)

    # 4. Confirm load_steps is absent in the serialized text
    tres_text = tres_path.read_text()
    assert "load_steps" not in tres_text

    # 5. Create project.godot
    (tmp_path / "project.godot").write_text(_PROJECT_GODOT)

    # 6. Create and run validation script
    script = _build_tileset_validation_script("test_nols_tileset.tres")
    script_path = tmp_path / "validate.gd"
    script_path.write_text(script)

    result = godot_backend.run(
        ["--headless", "--script", str(script_path)],
        project_path=tmp_path,
    )
    assert "VALIDATION_OK" in result.stdout


@pytest.mark.requires_godot
def test_tileset_atlas_bounds_edge(
    tmp_path: Path, godot_backend: GodotBackend
) -> None:
    """Validate TileSet atlas bounds at texture edge in headless Godot (VAL-02).

    Creates a 64x64 PNG and a 4x4 tile grid (16px tiles) that exactly fills
    the texture. Verifies no tiles-outside-texture error in Godot.
    """
    # 1. Create a minimal 64x64 PNG (no Pillow dependency)
    png_path = tmp_path / "tileset.png"
    _create_minimal_png(png_path, width=64, height=64)

    # 2. Build TileSet with tiles exactly filling the texture
    resource = build_tileset(
        image_res_path="res://tileset.png",
        tile_width=16,
        tile_height=16,
        columns=4,
        rows=4,
    )

    # 3. Serialize to disk
    tres_path = tmp_path / "test_tileset_bounds.tres"
    serialize_tres_file(resource, tres_path)

    # 4. Create project.godot
    (tmp_path / "project.godot").write_text(_PROJECT_GODOT)

    # 5. Create and run atlas bounds validation script
    script = _build_atlas_bounds_validation_script("test_tileset_bounds.tres")
    script_path = tmp_path / "validate.gd"
    script_path.write_text(script)

    result = godot_backend.run(
        ["--headless", "--script", str(script_path)],
        project_path=tmp_path,
    )
    assert "VALIDATION_OK" in result.stdout
    assert "bounds=valid" in result.stdout
