# auto-godot

Agent-native CLI for the Godot game engine. Wraps Godot's headless mode and directly manipulates Godot's text-based file formats (`.tscn`, `.tres`, `project.godot`) to automate workflows that normally require the editor GUI.

**18,000+ lines of source** | **1,400+ tests** | **111 commands** | **No Godot binary required for file operations**

## Why

The Godot ecosystem has version managers, GDScript linters, CI Docker images, and MCP servers, but no headless CLI tool that bridges Aseprite exports to SpriteFrames or automates TileSet terrain configuration. auto-godot fills that gap.

## Ecosystem Position

auto-godot fills a specific gap in Godot tooling: headless, editor-free file generation and manipulation.

| Need | Existing Solutions | auto-godot |
|------|-------------------|---------|
| CI/CD export | Docker images with headless Godot | `auto-godot export` wraps headless binary with retry logic |
| Editor automation | MCP servers (require running editor instance) | No editor needed; direct file manipulation |
| Aseprite to SpriteFrames | None | `auto-godot sprite import-aseprite` |
| TexturePacker to SpriteFrames | Editor plugin only (CodeAndWeb) | `auto-godot sprite import-texturepacker` |
| TileSet terrain automation | None (manual editor work) | `auto-godot tileset auto-terrain` |
| Resource inspection | Editor only | `auto-godot resource inspect --json`, `resource dump` |
| GDScript documentation | GDQuest docs-maker (Godot 3 only, unmaintained) | `auto-godot script docs` |
| Export preset management | No standalone tool | `auto-godot preset inspect`, `preset validate` |

No other tool generates SpriteFrames from Aseprite or TexturePacker JSON, automates TileSet terrain peering bits, or generates GDScript documentation for Godot 4 without the Godot editor.

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

Convert sprite sheet exports into valid Godot SpriteFrames `.tres` resources, entirely from the command line, no Godot editor required. Supports both Aseprite and TexturePacker workflows.

```bash
# Convert Aseprite JSON export to SpriteFrames .tres
auto-godot sprite import-aseprite character.json
auto-godot sprite import-aseprite character.json -o sprites/character.tres
auto-godot sprite import-aseprite character.json --res-path res://art/character.png

# Convert TexturePacker JSON atlas to SpriteFrames .tres
auto-godot sprite import-texturepacker atlas.json
auto-godot sprite import-texturepacker atlas.json -o sprites/atlas.tres --fps 12

# Split a sprite sheet into frames
auto-godot sprite split sheet.png --frame-size 32x32
auto-godot sprite split sheet.png --json-meta regions.json

# Composite multiple sprites into an atlas
auto-godot sprite create-atlas frame1.png frame2.png frame3.png -o atlas.png

# Validate a generated SpriteFrames resource
auto-godot sprite validate character.tres
auto-godot sprite validate character.tres --godot  # also load in headless Godot
```

Aseprite importer supports all four animation directions (forward, reverse, ping-pong, ping-pong reverse), variable-duration frames via GCD-based FPS, trimmed sprites, and partial failure handling. TexturePacker importer auto-groups frames into animations by filename prefix (`idle_0`, `idle_1` -> animation "idle").

### TileSet Commands

Automate TileSet creation and terrain configuration that normally requires clicking hundreds of peering bits by hand in the editor.

```bash
# Create a TileSet from a sprite sheet
auto-godot tileset create tileset.png --tile-size 16x16
auto-godot tileset create tileset.png --tile-size 16x16 --margin 1 --separation 1

# Auto-assign terrain peering bits
auto-godot tileset auto-terrain tileset.tres --layout blob-47
auto-godot tileset auto-terrain tileset.tres --layout minimal-16
auto-godot tileset auto-terrain tileset.tres --layout rpgmaker

# Batch assign collision shapes
auto-godot tileset assign-physics tileset.tres --rules "0-15:full" "16-31:none"

# Inspect a TileSet as structured JSON
auto-godot tileset inspect tileset.tres --json

# Import from Tiled
auto-godot tileset import-tiled map.tmj -o tileset.tres
auto-godot tileset import-tiled map.tmx -o tileset.tres

# Validate a TileSet resource
auto-godot tileset validate tileset.tres
auto-godot tileset validate tileset.tres --godot  # headless Godot check
```

Supports 47-tile blob (Match Corners and Sides), 16-tile minimal (Match Sides), and RPG Maker A2 autotile layouts. Peering bits are generated algorithmically from bitmask combinatorics.

### Scene Commands

List and create Godot scenes from the command line.

```bash
# List all scenes in a project with full node trees
auto-godot scene list /path/to/project
auto-godot scene list /path/to/project --depth 2
auto-godot scene list /path/to/project --json

# Create a scene from a JSON definition
auto-godot scene create definition.json -o level.tscn
```

Scene list shows node hierarchy, script references, instanced sub-scenes, and cross-scene dependency graphs. Scene create accepts JSON with full property passthrough for any Godot node type.

### Script Commands

Generate, inspect, and document GDScript files.

```bash
# Generate a GDScript with boilerplate
auto-godot script create --extends CharacterBody2D --export "speed:float=200.0" player.gd

# Add elements to existing scripts
auto-godot script add-method --file player.gd --name take_damage --params "amount: int"
auto-godot script add-signal --file player.gd --name died
auto-godot script add-export --file player.gd --name health --type int --value 100

# Attach a script to a scene node
auto-godot script attach --scene main.tscn --node Player --script res://scripts/player.gd

# Generate documentation from GDScript files
auto-godot script docs scripts/player.gd
auto-godot script docs /path/to/project -o docs/
auto-godot --json script docs scripts/player.gd
```

`script docs` parses `##` doc comments (Godot 4 syntax), signals, exports, functions, enums, and constants. Outputs Markdown or JSON. Accepts a single file or a directory (recursive).

### Export and Import Commands

Headless Godot project export for CI/CD pipelines.

```bash
# Export builds using named presets
auto-godot export release "Windows Desktop"
auto-godot export debug "Linux/X11"
auto-godot export pack "Web"

# Force re-import (with retry logic for known Godot timing bugs)
auto-godot import
auto-godot import --max-retries 5

# Manage export presets
auto-godot preset list
auto-godot preset create --platform windows --platform web
auto-godot preset inspect "Windows Desktop"
auto-godot preset validate  # check for issues before building
```

Export auto-runs import first when the import cache is missing. Import uses exponential backoff retry and `--quit-after` instead of `--quit` to avoid Godot race conditions. `preset validate` checks for duplicate names, missing export paths, unrecognized platforms, and missing export directories.

### Project Commands

```bash
# Show project metadata as JSON
auto-godot project info --json

# Validate project structure (missing resources, broken res:// paths)
auto-godot project validate
auto-godot project validate --godot  # also check script syntax

# Scaffold a new Godot project
auto-godot project create my-game

# Scaffold a pixel-perfect project in one shot (sets stretch mode, nearest filter,
# pixel snap, physics interpolation, and a 320x240 viewport)
auto-godot project create my-pixel-game --pixel-art
auto-godot project create my-pixel-game --pixel-art --pixel-art-width 480 --pixel-art-height 270
```

### Resource Commands

```bash
# Inspect any .tres or .tscn (tree view or JSON)
auto-godot resource inspect player.tres
auto-godot resource inspect level.tscn --json

# Dump full parsed structure as JSON AST
auto-godot resource dump scene.tscn
auto-godot resource dump scene.tscn --section nodes
auto-godot resource dump spriteframes.tres --section properties

# Create gradient and curve resources
auto-godot resource create-gradient --stop "0:black" --stop "1:white" fade.tres
auto-godot resource create-curve --point "0,0" --point "0.5,1" --point "1,0" falloff.tres
```

`resource dump` always outputs JSON and supports `--section` filtering: `nodes`, `ext_resources`, `sub_resources`, `properties`, `connections`.

### AI Agent Discoverability

```bash
# Auto-generate SKILL.md from the CLI command tree
auto-godot skill generate
auto-godot skill generate -o SKILL.md
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

All errors produce non-zero exit codes. With `--json`, errors return `{"error": "message", "code": "ERROR_CODE", "fix": "suggestion"}` to stderr with actionable fix suggestions.

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
uv run pytest --cov=auto_godot

# Run E2E tests (requires Godot 4.5+ on PATH)
uv run pytest tests/e2e/ -v
```

1,400+ unit tests covering the parser, value types, Aseprite and TexturePacker conversion, SpriteFrames builder, TileSet builder, terrain peering bits, export pipeline, scene builder, script generation, GDScript docs, resource inspection and dump, preset management, locale management, SKILL.md generator, golden file comparison, and CLI integration. E2E tests validate generated resources in headless Godot (skipped when Godot is not available).

## License

Apache-2.0
