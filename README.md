# godauto

Agent-native CLI for the Godot game engine. Wraps Godot's headless mode and directly manipulates Godot's text-based file formats (`.tscn`, `.tres`, `project.godot`) to automate workflows that normally require the editor GUI.

**7,200+ lines of source** | **648 tests** | **28 commands** | **No Godot binary required for file operations**

## Why

The Godot ecosystem has version managers, GDScript linters, CI Docker images, and MCP servers, but no headless CLI tool that bridges Aseprite exports to SpriteFrames or automates TileSet terrain configuration. godauto fills that gap.

## Install

```bash
# With uv (recommended)
uv pip install -e .

# With image processing support (sprite split, create-atlas)
uv pip install -e ".[image]"

# With dev dependencies
uv pip install -e ".[dev]"
```

Requires Python 3.12+. Godot 4.5+ binary on PATH is only needed for headless commands (`export`, `import`) and E2E tests.

## Commands

### Sprite Commands

Convert Aseprite sprite sheet exports into valid Godot SpriteFrames `.tres` resources, entirely from the command line, no Godot editor required.

```bash
# Convert Aseprite JSON export to SpriteFrames .tres
gdauto sprite import-aseprite character.json
gdauto sprite import-aseprite character.json -o sprites/character.tres
gdauto sprite import-aseprite character.json --res-path res://art/character.png

# Split a sprite sheet into frames
gdauto sprite split sheet.png --frame-size 32x32
gdauto sprite split sheet.png --json-meta regions.json

# Composite multiple sprites into an atlas
gdauto sprite create-atlas frame1.png frame2.png frame3.png -o atlas.png

# Validate a generated SpriteFrames resource
gdauto sprite validate character.tres
gdauto sprite validate character.tres --godot  # also load in headless Godot
```

Supports all four Aseprite animation directions (forward, reverse, ping-pong, ping-pong reverse), variable-duration frames via GCD-based base FPS with per-frame multipliers, trimmed sprites with spriteSourceSize offsets, loop settings from repeat counts, and partial failure handling that skips invalid tags and continues.

### TileSet Commands

Automate TileSet creation and terrain configuration that normally requires clicking hundreds of peering bits by hand in the editor.

```bash
# Create a TileSet from a sprite sheet
gdauto tileset create tileset.png --tile-size 16x16
gdauto tileset create tileset.png --tile-size 16x16 --margin 1 --separation 1

# Auto-assign terrain peering bits
gdauto tileset auto-terrain tileset.tres --layout blob-47
gdauto tileset auto-terrain tileset.tres --layout minimal-16
gdauto tileset auto-terrain tileset.tres --layout rpgmaker

# Batch assign collision shapes
gdauto tileset assign-physics tileset.tres --rules "0-15:full" "16-31:none"

# Inspect a TileSet as structured JSON
gdauto tileset inspect tileset.tres --json

# Import from Tiled
gdauto tileset import-tiled map.tmj -o tileset.tres
gdauto tileset import-tiled map.tmx -o tileset.tres

# Validate a TileSet resource
gdauto tileset validate tileset.tres
gdauto tileset validate tileset.tres --godot  # headless Godot check
```

Supports 47-tile blob (Match Corners and Sides), 16-tile minimal (Match Sides), and RPG Maker A2 autotile layouts. Peering bits are generated algorithmically from bitmask combinatorics.

### Scene Commands

List and create Godot scenes from the command line.

```bash
# List all scenes in a project with full node trees
gdauto scene list /path/to/project
gdauto scene list /path/to/project --depth 2
gdauto scene list /path/to/project --json

# Create a scene from a JSON definition
gdauto scene create definition.json -o level.tscn
```

Scene list shows node hierarchy, script references, instanced sub-scenes, and cross-scene dependency graphs. Scene create accepts JSON with full property passthrough for any Godot node type.

### Export and Import Commands

Headless Godot project export for CI/CD pipelines.

```bash
# Export builds using named presets
gdauto export release "Windows Desktop"
gdauto export debug "Linux/X11"
gdauto export pack "Web"

# Force re-import (with retry logic for known Godot timing bugs)
gdauto import
gdauto import --max-retries 5
```

Export auto-runs import first when the import cache is missing. Import uses exponential backoff retry and `--quit-after` instead of `--quit` to avoid Godot race conditions.

### Project Commands

```bash
# Show project metadata as JSON
gdauto project info --json

# Validate project structure (missing resources, broken res:// paths)
gdauto project validate
gdauto project validate --godot  # also check script syntax

# Scaffold a new Godot project
gdauto project create my-game
```

### Resource Inspection

```bash
# Dump any .tres or .tscn as structured JSON
gdauto resource inspect player.tres --json
gdauto resource inspect level.tscn --json
```

### AI Agent Discoverability

```bash
# Auto-generate SKILL.md from the CLI command tree
gdauto skill generate
gdauto skill generate -o SKILL.md
```

Walks the Click command tree via introspection and produces structured markdown with all command names, arguments, options, help text, and one usage example per command. Designed for LLM tool discovery.

### Global Flags

Every command supports:

| Flag | Short | Description |
|------|-------|-------------|
| `--json` | `-j` | Structured JSON output (agent-native) |
| `--verbose` | `-v` | Extra detail |
| `--quiet` | `-q` | Errors only |
| `--no-color` | | Disable colored output |
| `--godot-path` | | Explicit Godot binary path |

All errors produce non-zero exit codes. With `--json`, errors return `{"error": "message", "code": "ERROR_CODE"}` with actionable fix suggestions.

## Architecture

- **Custom parser**: State-machine parser for `.tscn`/`.tres` files, no third-party parser dependency. Round-trip fidelity: parse and re-serialize without introducing spurious diffs.
- **Value types**: Frozen dataclasses with `slots=True` for all Godot value types (Vector2, Rect2, Color, Transform2D, PackedVector2Array, etc.)
- **project.godot**: Custom line-based parser that handles Godot constructors and multi-line values (stdlib configparser cannot)
- **Backend wrapper**: Discovers Godot binary on PATH, validates version >= 4.5, manages timeouts, parses stderr for structured error reporting
- **Optional Pillow**: Only needed for `sprite split` and `sprite create-atlas` (image pixel operations). All other commands are pure Python.

## Tests

```bash
# Run all tests (no Godot binary needed)
uv run pytest

# Run with coverage
uv run pytest --cov=gdauto

# Run E2E tests (requires Godot 4.5+ on PATH)
uv run pytest tests/e2e/ -v
```

648 unit tests covering the parser, value types, Aseprite conversion, SpriteFrames builder, TileSet builder, terrain peering bits, export pipeline, scene builder, SKILL.md generator, golden file comparison, and CLI integration. 4 E2E tests validate generated resources in headless Godot (skipped when Godot is not available).

## License

Apache-2.0
