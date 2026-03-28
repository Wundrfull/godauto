# gdauto

Agent-native CLI for the Godot game engine. Wraps Godot's headless mode and directly manipulates Godot's text-based file formats (`.tscn`, `.tres`, `project.godot`) to automate workflows that normally require the editor GUI.

## Why

The Godot ecosystem has version managers, GDScript linters, CI Docker images, and several MCP servers, but no headless CLI tool that bridges Aseprite exports to SpriteFrames or automates TileSet terrain configuration. gdauto fills that gap.

## Install

```bash
# With uv (recommended)
uv pip install -e .

# With image processing support (sprite split, create-atlas)
uv pip install -e ".[image]"

# With dev dependencies
uv pip install -e ".[dev]"
```

Requires Python 3.12+. Godot 4.5+ binary on PATH is only needed for headless commands and E2E tests.

## What's Working

### Sprite Commands (Phase 2 -- core value)

Convert Aseprite sprite sheet exports into valid Godot SpriteFrames `.tres` resources, entirely from the command line, with no Godot editor required.

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

Supports:
- Array and hash JSON formats from Aseprite
- All four animation directions (forward, reverse, ping-pong, ping-pong reverse)
- Variable-duration frames via GCD-based base FPS with per-frame duration multipliers
- Trimmed sprites with spriteSourceSize offsets
- Loop settings from Aseprite repeat counts
- Partial failure handling (skips invalid tags, continues with valid ones)
- Grid-based and JSON-defined sprite sheet splitting
- Shelf-packing atlas compositor with power-of-two sizing

### Project Commands (Phase 1)

```bash
# Show project metadata as JSON
gdauto project info --json

# Validate project structure
gdauto project validate

# Scaffold a new Godot project
gdauto project create my-game
```

### Resource Inspection (Phase 1)

```bash
# Dump any .tres or .tscn as structured JSON
gdauto resource inspect player.tres --json
gdauto resource inspect level.tscn --json
```

### Global Flags

Every command supports:
- `--json` / `-j` -- structured JSON output (agent-native)
- `--verbose` / `-v` -- extra detail
- `--quiet` / `-q` -- errors only
- `--no-color` -- disable colored output
- `--godot-path PATH` -- explicit Godot binary path

All errors produce non-zero exit codes. With `--json`, errors return `{"error": "message", "code": "ERROR_CODE"}` with actionable fix suggestions.

## What's Ahead

- **Phase 3**: TileSet creation, terrain peering bit automation (47-tile blob, 16-tile minimal, RPG Maker), physics assignment, headless export/import
- **Phase 4**: Scene list/create commands, E2E test suite, golden file validation, SKILL.md agent discoverability

## Architecture

- Custom state-machine parser for `.tscn`/`.tres` files (no third-party parser dependency)
- Custom line-based parser for `project.godot` (handles Godot constructors, multi-line values)
- Frozen dataclasses with `slots=True` for all Godot value types
- Round-trip fidelity: parse and re-serialize without introducing spurious diffs
- Pillow is optional, only needed for `sprite split` and `sprite create-atlas`

## Tests

```bash
# Run all tests (no Godot binary needed)
uv run pytest

# Run with coverage
uv run pytest --cov=gdauto
```

439 unit tests covering the parser, value types, Aseprite conversion, SpriteFrames builder, CLI commands, splitter, atlas creator, and validator.

## License

Apache-2.0
