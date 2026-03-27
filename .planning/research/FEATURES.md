# Feature Research

**Domain:** Godot engine CLI tooling / agent-native game engine automation
**Researched:** 2026-03-27
**Confidence:** HIGH (core features), MEDIUM (differentiators), MEDIUM (anti-features)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist in any Godot CLI automation tool. Missing these means the tool feels broken or incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `--json` flag on every command | Agent-native tools must produce structured output. CLI-Anything methodology and agentic CLI design principles treat this as non-negotiable. AI agents parse JSON; without it, the tool is human-only. | LOW | Already designed into CLI-METHODOLOGY.md. Implement via Click decorator pattern. |
| `--help` with parseable descriptions | Agents discover commands via help text. Godot MCP servers already expose structured command descriptions; a CLI must match this discoverability. | LOW | Click generates this automatically. Ensure descriptions are concise and unambiguous. |
| Non-zero exit codes on failure | Every CI/CD pipeline and agent loop relies on exit codes to detect failures. godot-ci, GitHub Actions workflows, and all existing Godot build tools follow this contract. | LOW | Click handles this with `sys.exit(1)`. Pair with structured error JSON. |
| Structured error messages | Agents need `{"error": "message", "code": "ERROR_CODE"}` to recover. Proposal #13048 in Godot itself asks for structured error output; the community wants this. | LOW | Error code enum plus actionable fix suggestions in every error path. |
| Godot binary discovery and wrapping | GodotEnv, gdvm, and godot-ci all solve binary management. A CLI tool that invokes Godot headlessly must find the binary on PATH, support explicit `--godot-path`, and report clear errors when missing. | MEDIUM | `shutil.which("godot")` plus environment variable fallback. Validate version >= 4.5 on first use. |
| Headless export (release/debug/pack) | This is what godot-ci Docker images, the rk042 build pipeline, and every CI tutorial already do. Table stakes for any Godot automation tool. | MEDIUM | Wrap `--export-release`, `--export-debug`, `--export-pack`. Parse Godot's stderr for structured error reporting. Handle the "import cache missing" gotcha by auto-running `--import` first. |
| Force re-import with retry logic | Godot's `--import` flag has known timing/reliability bugs. Every CI pipeline working with Godot has hit this. Without retry logic, headless builds are flaky. | MEDIUM | Exponential backoff with configurable max retries. Detect common import failure patterns in stderr. |
| Resource inspection (dump .tres/.tscn as JSON) | godot-resource-parser (archived Jan 2026) and tscn2json both prove demand for this. Developers need to programmatically read Godot resources. The archived status of existing tools means this gap is actively open. | MEDIUM | Use custom state machine parser (not regex). Must handle all Godot 4.x value types: Vector2/3/4, Rect2, Color, Transform2D/3D, arrays, dictionaries. |
| Project info (dump project.godot as JSON) | Every project management tool reads project.godot. INI-style format is trivial to parse. Agents need project name, Godot version, autoloads, input mappings. | LOW | Python configparser or simple line parser. Flatten nested sections into JSON. |
| Project validation (structure, missing resources, script errors) | Godot's `--check-only` flag validates scripts but does not check for missing resources or broken references. GDToolkit handles linting but not project-level validation. This is a gap. | MEDIUM | Combine file-system scanning (check all `res://` paths resolve) with `--check-only` for script syntax. Report missing resources, circular dependencies, orphan scripts. |

### Differentiators (Competitive Advantage)

Features that set gdauto apart. No existing tool provides these outside the Godot editor GUI.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Aseprite-to-SpriteFrames bridge** (`sprite import-aseprite`) | THE core value proposition. Aseprite Wizard, Godot 4 Aseprite Importers, and Aseprite Animation Importer all require the Godot GUI. Zero headless/CLI tools exist for this conversion. Every pixel art Godot developer using Aseprite (a huge percentage) currently must open the editor to import sprites. This is pure Python, no Godot binary needed. | HIGH | Parse Aseprite JSON (frame regions, durations in ms, animation tags with directions, repeat counts). Convert ms durations to Godot FPS. Handle forward/reverse/ping-pong/ping-pong-reverse directions. Handle loop vs non-loop. Generate valid .tres SpriteFrames with AtlasTexture sub-resources. Must handle trimmed sprites and sprite source size offsets. |
| **TileSet terrain auto-configuration** (`tileset auto-terrain`) | TileBitTools (archived April 2024) was the only tool that automated peering bit assignment, and it was a GUI plugin. No CLI tool does this. Manually clicking 8 peering bits per tile across a 47-tile blob set is hours of tedious work. Standard layout mappings (47-tile blob, 16-tile minimal, RPG Maker) are deterministic and automatable. | HIGH | Implement position-to-peering-bit lookup tables for each standard layout. Support all three Godot 4 terrain modes: Match Corners and Sides (8 bits), Match Corners (4 bits), Match Sides (4 bits). Must validate that the sprite sheet grid dimensions match the expected layout. |
| **Batch physics collision assignment** (`tileset assign-physics`) | Another tedious manual task in the editor. "Row 3 = solid" or "tiles 0-15 = full collision, 16-31 = half-height" are common patterns that can be expressed as CLI arguments. No existing tool does this. | MEDIUM | Accept tile ranges and collision shape presets (full, half-top, half-bottom, none). Generate physics layer data in the TileSet .tres. |
| **TileSet creation from sprite sheet** (`tileset create`) | Converts a sprite sheet image + tile size into a TileSet resource with TileSetAtlasSource. Currently requires the editor GUI to set up. | MEDIUM | Accept image path, tile size, margin, separation. Generate .tres with correct atlas source configuration. |
| **Scene creation from definitions** (`scene create`) | MCP servers like Coding-Solo/godot-mcp and ee0pdt/Godot-MCP can create scenes, but they require a running Godot editor. gdauto can generate .tscn files from JSON/YAML definitions without Godot running. | MEDIUM | Accept a JSON/YAML node tree definition. Generate valid .tscn with node hierarchy, property assignments, script references, signal connections. Validate node types against known Godot class list. |
| **Sprite sheet splitting** (`sprite split`) | Take a sprite sheet image + optional JSON metadata and produce individual frame images or a SpriteFrames resource. Useful for non-Aseprite sprite sheets. | MEDIUM | Support grid-based splitting (uniform cell size) and JSON-defined regions. Output individual PNGs or a SpriteFrames .tres. |
| **Sprite atlas creation** (`sprite create-atlas`) | Batch multiple individual sprite images into a single atlas texture with accompanying metadata. The reverse of splitting. | MEDIUM | Bin-packing algorithm for atlas layout. Generate atlas image (requires Pillow) and companion .tres or JSON metadata. Power-of-two texture sizes for GPU efficiency. |
| **Project scaffolding** (`project create`) | gdcli and godot-generate-project-cli exist but are minimal. Genre-specific templates (2D platformer, top-down, etc.) with recommended directory structures, autoload patterns, and starter scripts differentiate. | MEDIUM | Template system with variable substitution. Ship 2-3 built-in templates. Support custom template directories. Generate project.godot, default scene, folder structure. |
| **TileSet inspection** (`tileset inspect`) | Dump an existing TileSet as structured JSON: atlas sources, terrain sets, peering bit configurations, physics layers. Useful for debugging and migration. Generic resource inspect covers this partially, but TileSet-specific formatting is valuable. | LOW | Specialized JSON output that flattens TileSet's nested structure into a readable format. Show terrain names, bit assignments, collision shapes. |
| **Scene tree listing** (`scene list`) | Enumerate all scenes in a project, dump node trees, show dependencies between scenes and scripts. Useful for project auditing and agent navigation. | LOW | Walk the project directory, parse each .tscn, extract node hierarchy and resource references. Output as JSON tree or flat list. |
| **SKILL.md generation** | Auto-generate an AI agent discoverability document from the CLI's own `--help` output. Unique to agent-native tools. No other Godot tool does this. | LOW | Introspect Click command tree, extract names, arguments, options, help text. Format as markdown. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems. Explicitly NOT building these.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Live game interaction via remote debugger | MCP servers (LeeSinLiang/godot-mcp) do this. Seems powerful for testing and AI control. | Godot's remote debugger protocol is NOT a stable public API (read remote_debugger.cpp). It changes between Godot versions without notice. Building on it means constant breakage. MCP servers already cover this use case better since they run inside the editor. | Defer to a later milestone. Let MCP servers handle live interaction. gdauto focuses on offline file manipulation and headless invocation. |
| RL/ML training pipeline integration | Godot RL Agents exists. Combining it with CLI tooling seems natural. | Completely separate domain with its own complexity (TCP bridge, Python ML frameworks, training loops). Mixing it into a file manipulation CLI dilutes focus. Godot RL Agents already works well standalone. | Out of scope. Document how gdauto-generated resources can be used in RL pipelines, but don't build the pipeline. |
| Addon/plugin management (Asset Library client) | GodotEnv, godam, and gd-plug all do this. Users might expect it from a "Godot CLI tool." | Fragmented ecosystem with three competing approaches. The Godot Asset Library API is REST-based but has no official CLI client for a reason: addon installation requires editor reimport, dependency resolution is complex, and version compatibility checking is non-trivial. | Out of scope. Recommend GodotEnv for addon management. gdauto is not a package manager. |
| Godot version management | gdvm and GodotEnv solve this. Could be convenient to bundle. | Well-solved problem with mature tools (gdvm is Rust, fast, CI-ready; GodotEnv is .NET with addon support). Reimplementing in Python adds no value and fragments the ecosystem further. | Out of scope. Document recommended version managers. Support `--godot-path` flag for explicit binary selection. |
| GUI or TUI interface | Some developers prefer interactive tools. fgvm has a TUI. | Contradicts the agent-native design principle. TUIs cannot be driven by AI agents. Interactive prompts break CI/CD pipelines. Every interactive element is a barrier to automation. | CLI-only. Every operation must be expressible as a single non-interactive command. Use `--help` and `--json` for discoverability. |
| Particle effect and shader preset generation | Tempting to automate common visual effects. | Particles require GPU validation (Dummy rasterizer produces nothing headlessly). Shaders cannot be compiled without a GPU. Generated effects cannot be validated without the editor. | Out of scope. Can generate .gdshader text files as templates, but cannot validate them. |
| Tiled .tmx/.tmj import | Many tileset artists use Tiled. Import would be valuable. | Adds XML/JSON parser dependency for Tiled's format, which is complex (layers, objects, properties, tilesets-within-tilesets). Stretch goal, not core value. | Defer to later milestone. Core tileset features (create, auto-terrain, assign-physics) work with raw sprite sheets first. |
| Godot 3.x support | Some developers still use Godot 3.x. | Godot 3.x uses different file format (format=2 vs format=3), different headless binary approach (separate server builds), different TileSet system (autotile vs terrain). Supporting both doubles the parser complexity for a shrinking user base. | Target Godot 4.5+ only. Document this clearly. |
| Binary .scn/.res file support | Godot can save scenes and resources in binary format. | Binary format is underdocumented, version-specific, and changes between Godot releases. Text formats (.tscn/.tres) are the community standard for version control and are explicitly designed to be human/machine-readable. | Text formats only. If users have binary files, Godot can convert them: open in editor, re-save as text. |

## Feature Dependencies

```
[.tres/.tscn Parser/Generator] (formats/tscn.py, formats/tres.py)
    |
    +--requires--> [sprite import-aseprite]
    |                  |
    |                  +--requires--> [Aseprite JSON Parser] (formats/aseprite.py)
    |
    +--requires--> [tileset create]
    |                  |
    |                  +--enhances--> [tileset auto-terrain]
    |                  |
    |                  +--enhances--> [tileset assign-physics]
    |
    +--requires--> [scene create]
    |
    +--requires--> [resource inspect]
    |
    +--requires--> [tileset inspect]
    |
    +--requires--> [scene list]

[Godot Backend Wrapper] (godot_backend.py)
    |
    +--requires--> [export release/debug/pack]
    |
    +--requires--> [import (force re-import)]
    |
    +--requires--> [project validate] (for --check-only integration)

[project.godot Parser]
    |
    +--requires--> [project info]
    |
    +--requires--> [project validate]
    |
    +--requires--> [project create]

[sprite import-aseprite]
    +--enhances--> [sprite split] (shared frame region logic)
    +--enhances--> [sprite create-atlas] (shared atlas texture generation)

[tileset create]
    +--requires--> [tileset auto-terrain] (must create TileSet before assigning terrain bits)
    +--requires--> [tileset assign-physics] (must create TileSet before assigning physics)
```

### Dependency Notes

- **Parser/Generator is the foundation:** Every file manipulation command (sprite, tileset, scene, resource) depends on the .tscn/.tres parser/generator. This must be built first and tested thoroughly. The existing `godot_parser` library (stevearc) is a potential dependency but has uncertain Godot 4 format=3 support and has been inactive for 2+ years. Building a custom parser is the safer choice given the project's core value depends on correct file generation.
- **Godot Backend is independent:** The headless Godot wrapper is a separate concern from file manipulation. Export, import, and script validation commands need the backend, but sprite/tileset/scene commands do not.
- **tileset auto-terrain requires tileset create:** You cannot assign terrain peering bits without first having a TileSet resource. These could be combined into a single command with flags, or kept separate for composability. Recommendation: separate commands, but `auto-terrain` can accept an existing .tres or create a new one.
- **sprite commands share logic:** import-aseprite, split, and create-atlas share atlas region computation and AtlasTexture generation. Extract shared utilities into a common module.
- **project validate combines two paths:** File-system scanning (pure Python, checks resource references) and script validation (requires Godot binary, uses `--check-only`). Design so the pure Python checks run without Godot, with `--check-only` as an optional enhancement.

## MVP Definition

### Launch With (v1)

Minimum viable product: validate the core value proposition (Aseprite bridge) and establish the CLI foundation.

- [ ] **Click CLI skeleton with command groups** -- the container for everything else
- [ ] **`--json` flag infrastructure** -- agent-native from day one, architectural decision that affects every command
- [ ] **.tres/.tscn parser/generator** -- the foundation for all file manipulation; must handle Godot 4.x format=3 correctly
- [ ] **`sprite import-aseprite`** -- THE core value; Aseprite JSON to SpriteFrames .tres with named animations, correct durations, direction handling, loop settings
- [ ] **`resource inspect`** -- validates that generated files are correct; also immediately useful standalone
- [ ] **`project info`** -- trivial to implement, immediately useful, validates project.godot parsing
- [ ] **Godot backend wrapper** -- needed for E2E testing of generated resources and for export/import commands
- [ ] **`export release/debug/pack`** -- table stakes for CI/CD use; wraps existing Godot functionality with better error handling

### Add After Validation (v1.x)

Features to add once the Aseprite bridge is proven and the parser is battle-tested.

- [ ] **`tileset create`** -- once the parser handles TileSet .tres format reliably
- [ ] **`tileset auto-terrain`** -- the second major differentiator; implement after tileset create is solid
- [ ] **`tileset assign-physics`** -- natural companion to auto-terrain
- [ ] **`tileset inspect`** -- validates tileset generation; useful for debugging
- [ ] **`sprite split`** -- shares logic with import-aseprite; lower priority since non-Aseprite workflows are secondary
- [ ] **`sprite create-atlas`** -- requires Pillow for image manipulation; adds a dependency
- [ ] **`project validate`** -- combines file-system scanning with optional Godot --check-only
- [ ] **`import` (force re-import)** -- wraps Godot --import with retry logic

### Future Consideration (v2+)

Features to defer until the tool has community traction.

- [ ] **`scene create`** -- useful but complex (needs node type validation, signal wiring, script attachment)
- [ ] **`scene list`** -- nice for project auditing but not core value
- [ ] **`project create`** -- template scaffolding requires maintaining templates; defer until community feedback indicates which templates are wanted
- [ ] **SKILL.md auto-generation** -- valuable for agent discoverability but the tool must be feature-complete first
- [ ] **Tiled .tmx/.tmj import** -- stretch goal for tileset commands; adds parser complexity
- [ ] **Session undo/redo** -- sophisticated state management; only needed if the tool is used interactively (unlikely given agent-native focus)

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| sprite import-aseprite | HIGH | HIGH | P1 |
| .tres/.tscn parser/generator | HIGH | HIGH | P1 |
| --json flag infrastructure | HIGH | LOW | P1 |
| CLI skeleton with command groups | HIGH | LOW | P1 |
| resource inspect | HIGH | LOW | P1 |
| project info | MEDIUM | LOW | P1 |
| Godot backend wrapper | HIGH | MEDIUM | P1 |
| export release/debug/pack | HIGH | MEDIUM | P1 |
| tileset create | HIGH | MEDIUM | P2 |
| tileset auto-terrain | HIGH | HIGH | P2 |
| tileset assign-physics | MEDIUM | MEDIUM | P2 |
| tileset inspect | MEDIUM | LOW | P2 |
| sprite split | MEDIUM | MEDIUM | P2 |
| project validate | MEDIUM | MEDIUM | P2 |
| import (force re-import) | MEDIUM | LOW | P2 |
| sprite create-atlas | MEDIUM | HIGH | P2 |
| scene create | MEDIUM | HIGH | P3 |
| scene list | LOW | LOW | P3 |
| project create | LOW | MEDIUM | P3 |
| SKILL.md generation | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for launch (validates core value, establishes foundation)
- P2: Should have, add after core is proven (second wave of differentiators)
- P3: Nice to have, future consideration (community-driven additions)

## Competitor Feature Analysis

| Feature | Aseprite Wizard (GUI plugin) | TileBitTools (GUI plugin, archived) | godot-ci (Docker) | godot_parser (Python lib) | MCP Servers (6+) | gdauto (our approach) |
|---------|------------------------------|--------------------------------------|--------------------|-----------------------------|-------------------|------------------------|
| Aseprite to SpriteFrames | Full (GUI only) | N/A | N/A | N/A | N/A | Full (CLI, no Godot needed) |
| Animation direction support | forward, reverse, ping-pong, ping-pong reverse | N/A | N/A | N/A | N/A | All four directions |
| Frame duration conversion | ms to FPS | N/A | N/A | N/A | N/A | ms to FPS with per-frame support |
| Loop/repeat handling | Via Aseprite tags | N/A | N/A | N/A | N/A | Via Aseprite repeat counts |
| Terrain peering bit automation | N/A | Templates for all 3 terrain modes (archived) | N/A | N/A | N/A | Standard layout auto-assignment |
| Headless export | N/A | N/A | Full (Docker) | N/A | N/A | Full (native CLI) |
| Resource inspection as JSON | N/A | N/A | N/A | Parse only, no JSON output | Read-only (bradypp) | Parse + JSON output |
| .tres/.tscn generation | N/A | N/A | N/A | Read + write (Godot 3 focus) | Scene creation (requires editor) | Read + write (Godot 4.x focus) |
| Scene creation | N/A | N/A | N/A | Partial (high-level API) | Full (requires running editor) | From JSON/YAML definitions (no editor) |
| Agent-native (--json everywhere) | No | No | No | No | Structured (MCP protocol) | Yes (every command) |
| No Godot binary required | No (editor plugin) | No (editor plugin) | No (Docker with Godot) | Yes (Python only) | No (editor + plugin) | Yes (for file manipulation commands) |
| CI/CD friendly | No | No | Yes (primary purpose) | Yes | No | Yes (exit codes, JSON output, non-interactive) |

## Sources

- [Godot command line tutorial](https://docs.godotengine.org/en/latest/tutorials/editor/command_line_tutorial.html) -- official CLI flag documentation
- [Aseprite Wizard](https://github.com/viniciusgerevini/godot-aseprite-wizard) -- most feature-complete Aseprite-to-Godot plugin (GUI only)
- [Godot 4 Aseprite Importers](https://github.com/nklbdev/godot-4-aseprite-importers) -- alternative Aseprite import plugin
- [TileBitTools](https://github.com/dandeliondino/tile_bit_tools) -- archived Godot 4 terrain bit automation plugin
- [Terrain Autotiler](https://github.com/dandeliondino/terrain-autotiler) -- archived advanced terrain matching algorithm
- [Better Terrain](https://github.com/Portponky/better-terrain) -- active terrain plugin for Godot 4
- [godot_parser](https://github.com/stevearc/godot_parser) -- Python .tscn/.tres parser (inactive, uncertain Godot 4 format=3 support)
- [godot-resource-parser](https://github.com/fernforestgames/godot-resource-parser) -- TypeScript .tscn/.tres parser (archived Jan 2026)
- [tscn2json](https://github.com/saperio/tscn2json) -- Node.js .tscn to JSON converter
- [godot-ci](https://github.com/abarichello/godot-ci) -- Docker images for headless export
- [godot-build-pipeline-python](https://github.com/rk042/godot-build-pipeline-python) -- Python Godot build automation
- [Coding-Solo/godot-mcp](https://github.com/Coding-Solo/godot-mcp) -- MCP server for Godot
- [ee0pdt/Godot-MCP](https://github.com/ee0pdt/Godot-MCP) -- MCP server with scene/script integration
- [GodotEnv](https://github.com/chickensoft-games/GodotEnv) -- .NET version/addon manager
- [gdvm](https://github.com/patricktcoakley/gdvm) -- Rust version manager
- [Proposal #13048](https://github.com/godotengine/godot-proposals/issues/13048) -- structured error output for headless mode
- [Proposal #9306](https://github.com/godotengine/godot-proposals/issues/9306) -- scaffolding functionality for Godot binary
- [Aseprite Tags docs](https://www.aseprite.org/docs/tags/) -- animation direction and tag properties
- [Agentic CLI Design principles](https://dev.to/uenyioha/writing-cli-tools-that-ai-agents-actually-want-to-use-39no) -- structured output patterns for agent-native tools
- [Using TileSets](https://docs.godotengine.org/en/stable/tutorials/2d/using_tilesets.html) -- official terrain peering bit documentation

---
*Feature research for: Godot engine CLI tooling / agent-native game engine automation*
*Researched: 2026-03-27*
