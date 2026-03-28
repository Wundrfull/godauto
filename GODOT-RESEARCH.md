# Godot Engine Technical Research for gdauto

This document consolidates all research on Godot's CLI capabilities, API surface, community tooling, and gaps. GSD subagents should reference this when making architectural decisions.

## Godot Overview

Godot Engine is MIT-licensed, fully open source. The source lives at github.com/godotengine/godot. Current stable versions as of March 2026: Godot 4.6.1 stable (January 2026 release) and Godot 4.5.2 stable (March 2026 patch). gdauto targets Godot 4.5+.

## Headless Mode

Godot 4.x uses a single `--headless` flag on any desktop binary (Linux, macOS, Windows). This replaces Godot 3.x's separate server/headless binaries. The flag is shorthand for `--display-driver headless --audio-driver Dummy`, using a no-op rendering backend.

### What works headlessly

- Running GDScript via `--script` (scripts must extend SceneTree or MainLoop)
- Exporting projects via `--export-release`, `--export-debug`, `--export-pack`, `--export-patch`
- Importing/re-importing assets via `--import`
- Building C# solutions via `--build-solutions`
- Running engine unit tests via `--test`
- Converting Godot 3.x projects via `--convert-3to4`
- Validating scripts via `--check-only`
- Generating API docs via `--doctool`
- Dumping GDExtension API via `--dump-extension-api`
- Running the full SceneTree with physics, signals, networking, game logic
- Spawning dedicated multiplayer servers
- LSP server on port 6005, DAP on port 6006
- Writing movie output via `--write-movie`
- Benchmarking scenes with JSON output

### What does NOT work headlessly

- No pixel rendering output (Dummy rasterizer produces nothing)
- No window creation or GUI
- No audio playback
- GLSL shader compilation fails without a GPU
- Visual editor features (TileMap editor, animation editor, visual shader editor) don't render
- Some resource imports depending on GPU operations will fail
- EditorInterface and EditorPlugin singletons are unavailable in `--script` mode

### Key CLI flags

Run options: `--headless`, `--script`, `--path`, `--scene` (4.5+), `--quit`, `--quit-after`, `--main-loop`, `--rendering-method`, `--rendering-driver`, `--gpu-index`, `--log-file`, `--write-movie`

Export tools: `--export-release`, `--export-debug`, `--export-pack`, `--export-patch` (4.5+), `--patches`, `--import`, `--install-android-build-template`

Debug options: `--remote-debug`, `--profiling`, `--gpu-profile`, `--gpu-validation`, `--print-fps`, `--fixed-fps`, `--max-fps`, `--time-scale`, `--debug-collisions`, `--debug-navigation`

Editor tools: `--editor`, `--lsp-port`, `--dap-port`, `--debug-server`, `--recovery-mode`, `--build-solutions`, `--benchmark`, `--benchmark-file`

Developer tools: `--doctool`, `--gdscript-docs`, `--gdextension-docs`, `--dump-gdextension-interface`, `--dump-extension-api`, `--dump-extension-api-with-docs`, `--validate-extension-api`, `--convert-3to4`, `--check-only`

## File Formats

### .tscn (Scene files)

Text-based, bracket-section format:
```
[gd_scene load_steps=2 format=3]
[ext_resource type="Script" path="res://player.gd" id="1"]
[node name="Player" type="CharacterBody2D"]
script = ExtResource("1")
```

Parseable and generatable from Python without Godot running.

### .tres (Resource files)

Same bracket format with `[gd_resource]` header:
```
[gd_resource type="SpriteFrames" format=3]
[sub_resource type="AtlasTexture" id="AtlasTexture_abc12"]
atlas = ExtResource("1_sheet")
region = Rect2(0, 0, 32, 32)
[resource]
animations = [{ ... }]
```

Key resource types for gdauto:
- SpriteFrames: animation name to frame array mapping with speed, loop settings
- TileSet: atlas sources, terrain sets, peering bits, physics layers
- ParticleProcessMaterial: emission, velocity, gravity, color ramps, turbulence
- ShaderMaterial: references a .gdshader text file
- Environment: post-processing settings (glow, fog, SSAO, tone mapping)

### project.godot

INI-style config file with sections. Contains project name, description, features, input mappings, autoloads, display settings. Parseable with Python's configparser or simple line-based parsing.

### export_presets.cfg

INI-style, defines export presets (platform, include filters, features). One file per project.

## Aseprite Integration (Key Opportunity)

### The gap

Aseprite has a full CLI with batch mode (`aseprite -b`) that exports sprite sheets and JSON metadata. Several Godot editor plugins (Aseprite Wizard, Godot 4 Aseprite Importers, Aseprite Spritesheet Importer) convert this into SpriteFrames resources, but ALL of them are EditorPlugins requiring the Godot GUI. No headless/CLI tool exists that bridges Aseprite's JSON output to Godot's SpriteFrames .tres format.

### Aseprite JSON output format

When you run `aseprite -b character.ase --sheet sheet.png --data sheet.json --format json-array`, you get:
```json
{
  "frames": [
    {
      "filename": "character 0.ase",
      "frame": {"x": 0, "y": 0, "w": 32, "h": 32},
      "rotated": false,
      "trimmed": false,
      "spriteSourceSize": {"x": 0, "y": 0, "w": 32, "h": 32},
      "sourceSize": {"w": 32, "h": 32},
      "duration": 100
    }
  ],
  "meta": {
    "app": "https://www.aseprite.org/",
    "image": "sheet.png",
    "size": {"w": 256, "h": 32},
    "frameTags": [
      {"name": "idle", "from": 0, "to": 3, "direction": "forward"},
      {"name": "walk", "from": 4, "to": 9, "direction": "forward"},
      {"name": "attack", "from": 10, "to": 14, "direction": "forward"}
    ],
    "slices": []
  }
}
```

### What gdauto needs to do

1. Parse the Aseprite JSON metadata
2. For each frameTag, create a named animation
3. Compute atlas texture regions (Rect2) from each frame's x, y, w, h
4. Convert Aseprite's per-frame duration (milliseconds) to Godot's animation speed (FPS)
5. Handle animation directions: forward, reverse, ping-pong, ping-pong reverse
6. Handle loop vs non-loop (Aseprite repeat count)
7. Write a valid .tres SpriteFrames resource referencing the sprite sheet image
8. Optionally copy the sprite sheet image to the Godot project's resource directory

This is all pure Python. No Godot binary needed. The output is a text file.

## TileSet Automation (Key Opportunity)

### Godot 4.x TileSet structure

A TileSet resource contains:
- Tile size (Vector2i, e.g., 16x16, 32x32)
- TileSetAtlasSource objects, each referencing a texture atlas
- Per-tile properties: physics layers, navigation polygons, custom data
- Terrain sets with terrain peering bits for auto-tiling

### Terrain peering bit system

Godot 4.x uses terrain peering bits for auto-tiling (connecting walls, paths, water edges). Each tile in a terrain set has bits indicating which neighbors it connects to. The bit layout depends on the terrain mode:
- Match Corners and Sides: 8 peering bits (full blob tileset, up to 47 tiles)
- Match Corners: 4 bits
- Match Sides: 4 bits

### Standard tileset layouts

Many tileset artists follow standard layouts:
- **47-tile blob**: full corner+side matching, covers every possible neighbor combination
- **16-tile minimal**: side-only matching, simpler but less flexible
- **RPG Maker style**: specific grid positions map to specific terrain configurations
- **Wang tiles**: mathematical tiling system with edge/corner matching

If gdauto knows which layout convention a tileset follows, it can automatically assign all peering bits based on grid position alone. This eliminates hours of manual clicking in the editor.

### What gdauto needs to do

1. Accept a sprite sheet image and tile size
2. Detect or accept the layout convention (47-tile, 16-tile, RPG Maker, custom)
3. Split the image into a grid and create TileSetAtlasSource
4. For standard layouts, auto-assign terrain peering bits based on position
5. Optionally assign physics collision shapes to tile ranges (e.g., "row 3 = solid")
6. Write a valid .tres TileSet resource
7. Support importing from Tiled .tmx/.tmj files (stretch goal)

Steps 1-6 are pure Python file generation. Step 7 adds an XML/JSON parser for Tiled's format.

## Community Tooling Landscape

### Version managers
- GodotEnv (Chickensoft): .NET CLI, manages versions and addons
- gdvm: Rust-based, per-project pinning via .gdvmrc
- fgvm: hybrid CLI/TUI

### GDScript tooling
- GDToolkit (gdformat, gdlint, gdparse): pip-installable, pre-commit hooks
- GDQuest's GDScript Formatter: faster binary alternative

### CI/CD
- abarichello/godot-ci: Docker images with export templates
- Chickensoft setup-godot: GitHub Action with caching
- firebelley/godot-export: auto-detects presets
- gdUnit4-action: test runner for CI

### MCP servers (6+ exist)
- @satelliteoflove/godot-mcp: most feature-complete, bidirectional communication
- Coding-Solo/godot-mcp: scene creation, UID management
- bradypp/godot-mcp: read-only safe analysis
- ee0pdt/Godot-MCP: comprehensive editor commands
- LeeSinLiang/godot-mcp: remote debugger connection
- Dokujaa/Godot-MCP: Python-based with Meshy 3D integration

### Package managers (fragmented)
- godam (Rust CLI): npm-like workflows
- gd-plug: GDScript-based minimal manager
- GodotEnv: handles addons from git repos
- No official CLI client for the Godot Asset Library REST API

### Testing frameworks
- GUT (Godot Unit Testing): most popular, headless CLI support, JUnit XML output
- gdUnit4: GDScript + C#, SceneRunner for gameplay testing, GitHub Action
- PlayGodot: experimental Playwright-inspired Python tool (requires custom Godot fork)

## Scriptable API Surface

### Scene manipulation
- Create nodes: `Node2D.new()`, `CharacterBody2D.new()`, etc.
- Build hierarchies: `parent.add_child(child)`
- Set properties: `node.set("property", value)`
- Pack scenes: `PackedScene.pack(root)`
- Save: `ResourceSaver.save(scene, path)`
- Load: `ResourceLoader.load("res://scene.tscn").instantiate()`

### Mesh generation
- SurfaceTool, ArrayMesh, MeshDataTool for procedural meshes
- GLTF import/export via GLTFDocument and GLTFState

### Animation
- Animation resource: track-and-keyframe API
- Programmatic track creation, keyframe insertion, interpolation modes
- Save/load animations as .tres resources

### Input injection
- `Input.parse_input_event()` for programmatic input from GDScript
- Enables automated gameplay testing

### Remote debugging
- TCP-based protocol (`--remote-debug tcp://host:6007`)
- EngineDebugger singleton with `register_message_capture()` and `send_message()`
- Wire protocol is NOT publicly documented as a stable API (read remote_debugger.cpp)
- Supports scene tree inspection, breakpoints, variable inspection, profiling, live property editing

### RL/ML integration
- Godot RL Agents: TCP bridge between Godot and Python ML frameworks
- Supports StableBaselines3, Sample Factory, Ray RLLib, CleanRL
- ONNX export for in-game inference
- ~12k interactions/sec on 4 CPU cores

## Known Issues and Gotchas

- Headless export can fail if the project has never been opened in the editor (import cache missing). Workaround: run `godot --headless --import` first.
- The `--import` flag has known timing/reliability issues on some projects. May need retry logic.
- GDScript scripts run via `--script` must extend SceneTree or MainLoop, not Node or Object.
- GLSL shaders cannot be compiled headlessly. Text-based .gdshader files can be created/edited but not validated without a GPU.
- The interactive debugger can block CI pipelines when scripts error. Proposal #13048 requests structured error output.
- `EditorInterface` and `EditorPlugin` APIs are unavailable in headless `--script` mode. The workaround `godot --editor --headless` with `@tool` scripts is unreliable.
- Godot 4.6 introduced LibGodot (engine as embeddable library) but it's still early and not widely used for CLI tooling yet.

## Licensing

Godot is MIT licensed. Zero royalties, free to use/modify/redistribute for any purpose including commercial. Games and tools built with Godot are entirely your property. Can sublicense under different terms. Only requirement is including the MIT copyright notice.
