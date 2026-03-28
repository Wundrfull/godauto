# gdauto

## What This Is

gdauto is an agent-native command-line tool for the Godot game engine. Built in Python on Click, it wraps Godot's headless mode and directly manipulates Godot's text-based file formats (.tscn, .tres, project.godot) to automate workflows that currently require the Godot editor GUI. It operates in two modes: direct file manipulation (no Godot binary needed) and headless Godot invocation (for operations requiring the engine runtime).

## Core Value

The Aseprite-to-SpriteFrames bridge: read Aseprite's JSON export and generate valid Godot .tres SpriteFrames resources with named animations, correct frame durations, atlas texture regions, and loop settings, entirely in Python with no Godot binary required.

## Requirements

### Validated

Validated in Phase 1: Foundation and CLI Infrastructure
- [x] Click-based CLI with command groups: project, export, sprite, tileset, scene, resource
- [x] --json flag on every command for structured output (agent-native)
- [x] --help on every command with descriptions AI agents can parse
- [x] godot_backend.py wrapper for all headless Godot invocations (binary discovery, timeout, error handling)
- [x] project info: dump project.godot metadata as JSON
- [x] project validate: check project structure, missing resources, script syntax errors
- [x] project create: scaffold new projects from templates
- [x] resource inspect: dump any .tres/.tscn as JSON
- [x] Unit tests for all pure Python logic (no Godot binary needed)

Validated in Phase 2: Aseprite-to-SpriteFrames Bridge
- [x] sprite import-aseprite: parse Aseprite JSON, compute atlas regions, convert frame durations, handle animation directions and loop settings, write valid .tres SpriteFrames
- [x] sprite split: sprite sheet + optional JSON metadata to SpriteFrames
- [x] sprite create-atlas: batch multiple sprite images into atlas textures
- [x] sprite validate: verify generated SpriteFrames .tres files are valid and loadable

### Active

- [ ] export release/debug/pack with named presets, structured error reporting, exit codes
- [ ] import: force re-import with retry logic for known timing bugs
- [ ] tileset create: sprite sheet + tile size to TileSetAtlasSource
- [ ] tileset auto-terrain: auto-assign terrain peering bits for standard layouts (47-tile blob, 16-tile minimal, RPG Maker)
- [ ] tileset assign-physics: batch assign collision shapes to tile ranges by pattern
- [ ] tileset inspect: dump existing TileSet resource as structured JSON
- [ ] scene list: enumerate scenes, node trees, dependencies
- [ ] scene create: create scenes from JSON/YAML definitions
- [ ] All generated .tres/.tscn files loadable by Godot without modification
- [ ] E2E tests that load generated resources in headless Godot

### Out of Scope

- Live game interaction via remote debugger protocol -- complex, unstable API, defer to later milestone
- RL/ML training pipeline integration (Godot RL Agents) -- separate domain, defer
- Particle effect and shader preset generation -- requires GPU for validation, defer
- Multiplayer server management and load testing -- separate concern, defer
- Addon/plugin management wrapping the Asset Library API -- fragmented ecosystem, defer
- Tiled .tmx/.tmj import support -- stretch goal, defer to later milestone
- OAuth or GUI-based workflows -- CLI-only tool
- Godot 3.x support -- targets Godot 4.5+ only

## Context

**Domain:** Godot engine tooling. The community has version managers (GodotEnv, gdvm), GDScript linters (GDToolkit), CI Docker images (godot-ci), and several MCP servers, but no headless CLI tool that bridges Aseprite exports to SpriteFrames or automates TileSet terrain configuration.

**Technical foundation:** Godot 4.x uses `--headless` on any desktop binary (replaces Godot 3.x separate server binaries). Scene (.tscn) and resource (.tres) files are text-based with a bracket-section format, parseable and generatable from Python. project.godot is INI-style.

**Aseprite gap:** Multiple Godot editor plugins (Aseprite Wizard, Godot 4 Aseprite Importers) convert Aseprite exports to SpriteFrames, but all require the Godot GUI. No headless/CLI bridge exists. Aseprite's CLI (`aseprite -b`) exports sprite sheets with JSON metadata containing frame regions, durations in milliseconds, animation tags with directions, and repeat counts.

**TileSet gap:** Godot 4.x terrain peering bits for auto-tiling require manually clicking each bit for every tile in the editor. Standard tileset layouts (47-tile blob, 16-tile minimal, RPG Maker) have known position-to-bit mappings that can be automated.

**Reference documents:**
- `CLI-METHODOLOGY.md`: architectural patterns for Click CLI structure, backend wrapper, --json flag, test strategy, SKILL.md generation
- `GODOT-RESEARCH.md`: Godot headless mode capabilities, file format specs, Aseprite JSON structure, TileSet terrain system, community tooling landscape, known issues

**Target audiences:** the developer (personal use), the Godot community (filling ecosystem gaps), and as a GitHub portfolio/showcase project.

## Constraints

- **Tech stack**: Python 3.10+, Click >= 8.0, pytest >= 7.0
- **Engine compatibility**: Godot 4.5+ binary on PATH (for E2E tests and headless commands only)
- **Independence**: No Godot dependency for file manipulation commands (sprite, tileset, resource inspect)
- **License**: Apache-2.0
- **Error contract**: All errors produce non-zero exit codes and actionable messages; --json errors produce `{"error": "message", "code": "ERROR_CODE"}`
- **File validity**: Generated .tres/.tscn files must be loadable by Godot without modification
- **Code style**: No em dashes (use commas, colons, semicolons, parentheses), no emojis, type hints on all signatures, docstrings on public functions, functions under 30 lines, comments on non-obvious logic only

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python + Click over Rust/Go | Rapid iteration, rich ecosystem for text parsing, target audience familiar with pip | -- Pending |
| Direct .tres/.tscn generation over GDScript codegen | Simpler, no Godot dependency, text format is stable and documented | -- Pending |
| State machine parser over regex for Godot file format | Nested structures and multi-line values make regex fragile | -- Pending |
| PEP 420 namespace package structure | Coexistence with other CLI tools, clean module boundaries | -- Pending |
| Apache-2.0 license | Permissive, compatible with Godot's MIT license, suitable for community tool | -- Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check -- still the right priority?
3. Audit Out of Scope -- reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-28 after Phase 2 completion*
