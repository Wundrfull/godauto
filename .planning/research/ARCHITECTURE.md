# Architecture Research

**Domain:** Python CLI tooling for Godot game engine automation
**Researched:** 2026-03-27
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
+-----------------------------------------------------------------------+
|                         CLI Layer (Click)                              |
|  +----------+ +--------+ +--------+ +---------+ +--------+ +--------+ |
|  | project  | | export | | sprite | | tileset | | scene  | |resource| |
|  +----+-----+ +---+----+ +---+----+ +----+----+ +---+----+ +---+----+ |
|       |           |          |            |          |          |      |
+-------+-----------+----------+------------+----------+----------+-----+
        |           |          |            |          |          |
+-------+-----------+----------+------------+----------+----------+-----+
|                      Domain Logic Layer                               |
|  +------------------+  +------------------+  +---------------------+  |
|  | Aseprite Bridge  |  | TileSet Builder  |  | Scene/Resource Ops  |  |
|  | (aseprite.py)    |  | (tileset_ops.py) |  | (scene_ops.py)     |  |
|  +--------+---------+  +--------+---------+  +----------+---------+  |
|           |                     |                       |            |
+-----------------------------------------------------------------------+
            |                     |                       |
+-----------------------------------------------------------------------+
|                      File Format Layer                                |
|  +-------------+  +-------------+  +------------------+              |
|  | tscn.py     |  | tres.py     |  | godot_config.py  |              |
|  | (scene I/O) |  | (resource   |  | (project.godot   |              |
|  |             |  |  I/O)       |  |  INI parser)     |              |
|  +------+------+  +------+------+  +--------+---------+              |
|         |                |                   |                       |
|  +------+----------------+-------------------+                       |
|  |        Shared: value_types.py             |                       |
|  |  (Vector2, Rect2, Color, NodePath, etc.)  |                       |
|  +-------------------------------------------+                       |
+-----------------------------------------------------------------------+
            |
+-----------------------------------------------------------------------+
|                     Backend Layer                                     |
|  +---------------------------+  +----------------------------------+  |
|  | godot_backend.py          |  | Filesystem (pathlib)             |  |
|  | (binary discovery,        |  | (read/write .tscn, .tres,       |  |
|  |  subprocess, --headless,  |  |  project.godot, sprite sheets)  |  |
|  |  timeout, error parsing)  |  |                                  |  |
|  +---------------------------+  +----------------------------------+  |
+-----------------------------------------------------------------------+
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `cli.py` | Click entry point, group registration, global options (--json, --verbose) | Click group with `invoke_without_command=True`, version option |
| `project.py` | Project info, validate, create commands | Click subgroup under `cli`; calls `godot_config.py` and `godot_backend.py` |
| `export.py` | Build/export pipeline commands | Click subgroup; delegates to `godot_backend.py` for all work |
| `sprite.py` | Aseprite import, sprite splitting, atlas creation | Click subgroup; delegates to `aseprite.py` bridge and `tres.py` writer |
| `tileset.py` | TileSet creation, terrain assignment, physics, inspect | Click subgroup; delegates to `tileset_ops.py` and `tres.py` writer |
| `scene.py` | Scene listing, creation from definitions | Click subgroup; delegates to `tscn.py` parser/writer |
| `resource.py` | Generic resource inspection (dump any .tres/.tscn as JSON) | Click subgroup; delegates to `tscn.py` / `tres.py` parser |
| `formats/tscn.py` | Parse and generate .tscn (scene) files | State machine tokenizer + section-based parser; produces/consumes Python dicts |
| `formats/tres.py` | Parse and generate .tres (resource) files | Shares core parser with tscn.py (same bracket-section format, different header) |
| `formats/godot_config.py` | Parse project.godot and export_presets.cfg | Extended INI parser that handles Godot value types (Vector2, Color, etc.) |
| `formats/value_types.py` | Serialize/deserialize Godot value types | Converts between Python types and Godot text representations |
| `formats/aseprite.py` | Parse Aseprite JSON export metadata | Pure JSON parsing; maps frames, tags, durations to internal data model |
| `domain/tileset_ops.py` | Terrain peering bit calculation, atlas source building | Pure Python; encodes layout conventions (47-tile, 16-tile, RPG Maker) |
| `domain/aseprite_bridge.py` | Convert Aseprite data to SpriteFrames resource model | Pure Python; duration conversion (ms to FPS), direction handling, loop logic |
| `domain/scene_ops.py` | Scene tree construction from JSON/YAML definitions | Pure Python; builds node hierarchies, resolves resource references |
| `godot_backend.py` | All Godot binary interactions | subprocess wrapper; binary discovery via `shutil.which`, timeout, error parsing |

## Recommended Project Structure

```
gdauto/
  pyproject.toml              # PEP 621 project metadata, entry points
  setup.cfg                   # Optional: backwards compat
  gdauto/
    __init__.py               # Package version, metadata
    __main__.py               # python -m gdauto support
    cli.py                    # Click entry point, group registration
    godot_backend.py          # Subprocess wrapper for Godot binary
    project.py                # project info, validate, create
    export.py                 # export release, debug, pack
    sprite.py                 # sprite import-aseprite, split, create-atlas
    tileset.py                # tileset create, auto-terrain, assign-physics, inspect
    scene.py                  # scene list, create
    resource.py               # resource inspect
    output.py                 # --json / human output formatting helpers
    formats/
      __init__.py
      parser.py               # Shared bracket-section tokenizer + parser
      tscn.py                 # .tscn-specific logic (gd_scene, nodes, connections)
      tres.py                 # .tres-specific logic (gd_resource, sub_resource)
      godot_config.py         # project.godot / export_presets.cfg parser
      value_types.py          # Godot value type serialization (Vector2, Rect2, etc.)
      aseprite.py             # Aseprite JSON metadata parser
    domain/
      __init__.py
      sprite_frames.py        # Aseprite-to-SpriteFrames conversion logic
      tileset_builder.py      # TileSet construction, terrain bit calculation
      scene_builder.py        # Scene tree construction from definitions
      collision_shapes.py     # Physics collision shape generation for tiles
  tests/
    __init__.py
    conftest.py               # Shared fixtures, pytest marks
    unit/
      __init__.py
      test_parser.py          # Bracket-section parser tests
      test_value_types.py     # Godot value serialization round-trip tests
      test_tscn.py            # .tscn parse/generate tests
      test_tres.py            # .tres parse/generate tests
      test_godot_config.py    # project.godot parser tests
      test_aseprite.py        # Aseprite JSON parsing tests
      test_sprite_frames.py   # Aseprite-to-SpriteFrames conversion tests
      test_tileset_builder.py # TileSet construction tests
      test_terrain_bits.py    # Peering bit calculation tests
      test_scene_builder.py   # Scene construction tests
      test_cli_commands.py    # Click CliRunner tests for all commands
    e2e/
      __init__.py
      conftest.py             # Godot binary fixture, skip logic
      test_export.py          # Real exports via headless Godot
      test_import.py          # Resource import with retry
      test_generated_load.py  # Load generated .tres/.tscn in Godot
      test_project_validate.py # Validate real project structures
    fixtures/
      aseprite/               # Sample Aseprite JSON exports + sprite sheets
      tilesets/                # Sample tileset images (16px, 32px)
      scenes/                 # Sample .tscn files for parse testing
      resources/              # Sample .tres files for parse testing
      projects/               # Minimal Godot project structures
  SKILL.md                    # AI agent discoverability document
```

### Structure Rationale

- **`formats/`:** Isolated file I/O layer with zero domain knowledge. The parser reads bytes and produces Python data structures. The writer takes Python data structures and writes valid Godot text. This separation means parser bugs are isolated from domain logic bugs, and the parser can be tested exhaustively with synthetic data.
- **`domain/`:** Pure business logic with zero file I/O. Functions take data models in and return data models out. The Aseprite bridge takes parsed Aseprite metadata and returns a SpriteFrames model; it never touches the filesystem. This makes every domain function trivially unit-testable.
- **Command modules at package root:** Each Click command file (`sprite.py`, `tileset.py`, etc.) is a thin orchestration layer: parse CLI args, call domain logic, call format writer, handle output formatting. Under 30 lines per command function.
- **`tests/unit/` vs `tests/e2e/`:** Unit tests exercise formats and domain with synthetic data (no Godot needed). E2E tests exercise the full pipeline through headless Godot. This split means CI runs unit tests everywhere and E2E tests only where Godot is installed.
- **`tests/fixtures/`:** Real-world test data (Aseprite exports, tileset images, minimal Godot projects) committed to the repo for reproducible tests.

## Architectural Patterns

### Pattern 1: Two-Mode Execution (Direct File vs. Headless Godot)

**What:** Commands operate in one of two modes. "Direct" mode reads/writes Godot text files with pure Python (no binary needed). "Headless" mode invokes the Godot binary for operations requiring the engine runtime. The mode is determined by the command, not a flag; users never choose.

**When to use:** Every command. sprite, tileset, resource, and scene commands are direct-mode. export, import, and project validate (for script syntax checking) are headless-mode.

**Trade-offs:** Direct mode is faster, has no external dependency, and works in any environment. Headless mode can do things direct mode cannot (run GDScript, perform exports, validate import cache). The boundary must be clear: never invoke Godot when pure file manipulation suffices.

**Example:**
```python
# Direct mode: no Godot binary needed
def import_aseprite(input_json: Path, sheet_image: Path, output: Path) -> dict:
    """Parse Aseprite JSON, generate SpriteFrames .tres file."""
    metadata = parse_aseprite_json(input_json)
    sprite_frames = build_sprite_frames(metadata, sheet_image)
    write_tres(sprite_frames, output)
    return {"output": str(output), "animations": len(sprite_frames.animations)}

# Headless mode: requires Godot binary
def export_release(preset: str, output_path: Path, project_path: Path) -> dict:
    """Export project using Godot's headless mode."""
    backend = GodotBackend()
    result = backend.export_release(preset, output_path, project_path)
    return {"output": str(output_path), "stdout": result.stdout}
```

### Pattern 2: Layered Parser (Tokenizer, Section Parser, Value Deserializer)

**What:** The Godot file format parser is split into three composable stages. Stage 1 (tokenizer) reads raw text and emits tokens: section headers, key-value pairs, and blank lines. Stage 2 (section parser) groups tokens into typed sections (ext_resource, sub_resource, node, connection, resource). Stage 3 (value deserializer) converts Godot-typed string values into Python objects (e.g., `"Rect2(0, 0, 32, 32)"` becomes a Python Rect2 namedtuple or dataclass).

**When to use:** All .tscn and .tres file operations. The three stages share a common tokenizer but diverge at the section level (scenes have nodes/connections; resources have a [resource] section).

**Trade-offs:** More code than a single-pass regex approach, but handles nested structures (arrays of dictionaries containing SubResource references), multiline values, and the full range of Godot value types correctly. The existing godot-parser library (v0.1.7) exists but is based on "visual inspection of Godot files" rather than spec, and at v0.1.x maturity it may have edge cases. Building our own parser gives us full control over the output data model and lets us optimize for the specific resource types we generate (SpriteFrames, TileSet).

**Build vs. Buy decision:** Build our own. Rationale: (1) godot-parser is at 0.1.7, low maturity, (2) our use case is more generation-heavy than parse-heavy, so we need a writer-first design, (3) the format is well-specified and bounded (five section types, known value types), (4) our parser only needs to handle format=3 (Godot 4.x), (5) owning the parser means we control the data model that domain logic consumes. If parsing proves harder than expected, we can adopt godot-parser as a fallback for the low-level read path and keep our own writer.

**Example:**
```python
# Stage 1: Tokenize
tokens = tokenize_godot_file(text)
# -> [SectionHeader("gd_resource", {"type": "SpriteFrames", "format": "3"}),
#     SectionHeader("sub_resource", {"type": "AtlasTexture", "id": "AtlasTexture_abc"}),
#     KeyValue("atlas", 'ExtResource("1_sheet")'),
#     KeyValue("region", 'Rect2(0, 0, 32, 32)'),
#     ...]

# Stage 2: Group into sections
sections = parse_sections(tokens)
# -> GodotFile(header=..., ext_resources=[...], sub_resources=[...], resource={...})

# Stage 3: Deserialize values
file_data = deserialize_values(sections)
# -> GodotFile where region is now Rect2(x=0, y=0, w=32, h=32) as a Python object
```

### Pattern 3: Click Context Object for Shared State

**What:** A context object passed through Click's `@click.pass_context` / `ctx.ensure_object()` mechanism carries shared configuration: output format (JSON vs. human), verbosity level, Godot binary path override, and the lazily-initialized GodotBackend instance. Command functions receive this context and use it without needing global state.

**When to use:** Every command. The context object is created once at the top-level group and flows downward.

**Trade-offs:** Slightly more boilerplate than global variables, but enables testability (inject mock context in tests) and avoids import-time side effects. Click's CliRunner passes custom context objects directly, making unit tests straightforward.

**Example:**
```python
class GdautoContext:
    def __init__(self):
        self.json_output: bool = False
        self.verbose: bool = False
        self.godot_binary: str | None = None
        self._backend: GodotBackend | None = None

    @property
    def backend(self) -> GodotBackend:
        if self._backend is None:
            self._backend = GodotBackend(binary=self.godot_binary)
        return self._backend

pass_context = click.make_pass_decorator(GdautoContext, ensure=True)

@cli.group()
@click.option("--json", "json_output", is_flag=True)
@click.option("--godot", "godot_binary", envvar="GODOT_BINARY")
@pass_context
def sprite(ctx, json_output, godot_binary):
    ctx.json_output = json_output
    ctx.godot_binary = godot_binary
```

### Pattern 4: Output Formatter (Dual-Mode Rendering)

**What:** A thin output module that every command calls to render results. In JSON mode, it serializes the result dict with `json.dumps`. In human mode, it formats tables, summaries, or colored text. The command function never calls `click.echo` directly for data output; it returns a dict and the formatter handles presentation.

**When to use:** Every command that produces output.

**Trade-offs:** Adds one level of indirection, but ensures the `--json` contract is never broken and human output can evolve independently. Also simplifies testing: assert on the returned dict, not on string output.

**Example:**
```python
def emit(data: dict, ctx: GdautoContext, human_formatter=None):
    """Emit command output in JSON or human-readable format."""
    if ctx.json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    elif human_formatter:
        human_formatter(data)
    else:
        for key, value in data.items():
            click.echo(f"{key}: {value}")
```

## Data Flow

### Core Data Flow: Aseprite to SpriteFrames (Primary Use Case)

```
User runs:
  gdauto sprite import-aseprite --input sheet.json --sheet sheet.png --output frames.tres

    |
    v
[cli.py / sprite.py]  Parse CLI args via Click
    |
    v
[formats/aseprite.py]  Read and parse Aseprite JSON metadata
    |                   -> AsepriteData(frames=[], meta=Meta(tags=[], size=...))
    v
[domain/sprite_frames.py]  Convert to SpriteFrames model
    |   - Group frames by animation tag
    |   - Compute Rect2 atlas regions from frame x/y/w/h
    |   - Convert per-frame ms durations to Godot FPS
    |   - Handle direction (forward/reverse/ping-pong)
    |   - Handle loop settings (repeat count)
    |   -> SpriteFramesResource(animations=[Animation(name, frames, speed, loop)])
    v
[formats/tres.py]  Serialize to .tres text format
    |   - Write [gd_resource type="SpriteFrames" format=3] header
    |   - Write [ext_resource] for sprite sheet texture
    |   - Write [sub_resource] for each AtlasTexture
    |   - Write [resource] with animations array
    |   -> Valid .tres file on disk
    v
[output.py]  Emit result
    |   -> JSON: {"output": "frames.tres", "animations": 3, ...}
    |   -> Human: "Created frames.tres with 3 animations (idle, walk, attack)"
    v
stdout (exit code 0)
```

### Core Data Flow: TileSet Terrain Auto-Assignment

```
User runs:
  gdauto tileset auto-terrain --input tileset.png --tile-size 16 --layout blob47 --output tileset.tres

    |
    v
[cli.py / tileset.py]  Parse CLI args
    |
    v
[domain/tileset_builder.py]  Build TileSet model
    |   - Calculate grid dimensions from image size and tile size
    |   - Look up peering bit layout for blob47 convention
    |   - For each tile position, assign terrain peering bits
    |   -> TileSetResource(tile_size, atlas_sources=[], terrain_sets=[])
    v
[formats/tres.py]  Serialize to .tres
    |   -> Valid TileSet .tres file
    v
[output.py]  Emit result
```

### Core Data Flow: Headless Godot Invocation (Export)

```
User runs:
  gdauto export release --preset "Linux" --output build/game.x86_64

    |
    v
[cli.py / export.py]  Parse CLI args, get context
    |
    v
[godot_backend.py]  Invoke Godot headless
    |   - Resolve binary: ctx.godot_binary or shutil.which("godot")
    |   - Build command: [binary, "--headless", "--export-release", "Linux", "build/game.x86_64"]
    |   - Set --path to project directory
    |   - Run subprocess with timeout
    |   - Parse stdout/stderr for errors
    |   - Return GodotResult(returncode, stdout, stderr)
    v
[export.py]  Interpret result
    |   - Check return code
    |   - Parse any error messages from stderr
    |   -> {"output": "build/game.x86_64", "preset": "Linux", "success": true}
    v
[output.py]  Emit result
```

### Error Flow

```
Any command
    |
    v
Exception raised (GodotError, FileNotFoundError, ValidationError, etc.)
    |
    v
[cli.py error handler]
    |
    +-- --json mode: {"error": "message", "code": "GODOT_NOT_FOUND"}
    |                 exit code 1
    |
    +-- human mode:  "Error: Godot binary not found on PATH."
                     "Install Godot 4.5+ from https://godotengine.org/download/"
                     exit code 1
```

### Key Data Flows

1. **File parse flow:** Raw text -> tokenizer -> section parser -> value deserializer -> Python data model. Reversible: data model -> value serializer -> section writer -> text output.
2. **Command flow:** CLI args -> Click parsing -> context setup -> domain logic -> format I/O -> output formatting -> stdout.
3. **Backend flow:** Command -> GodotBackend.run() -> subprocess.run() with timeout -> result parsing -> structured return or GodotError.

## Scaling Considerations

These are not "users at scale" considerations (this is a CLI tool, not a service). Instead, these address project complexity scaling.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 5 commands, 1 developer | Flat package, all command modules at root. One parser module. |
| 15+ commands, contributors | Split into formats/ and domain/ subpackages as described. Add plugin system for custom commands. |
| Community adoption | Add SKILL.md for AI discoverability. Add shell completion. Consider entry_points for pip install. |

### Scaling Priorities

1. **First bottleneck: parser correctness.** The parser must handle every valid .tres/.tscn that Godot 4.5+ produces. Build the parser test suite with real-world files from diverse projects early. A parser bug that silently produces invalid output is the worst failure mode.
2. **Second bottleneck: value type coverage.** Godot has many value types (Vector2, Vector2i, Vector3, Rect2, Rect2i, Color, Transform2D, Transform3D, Basis, AABB, NodePath, StringName, PackedByteArray, etc.). Each needs a serialize/deserialize pair. Prioritize the types used by SpriteFrames and TileSet (Rect2, Vector2i, StringName, Array, Dictionary), add others as needed.

## Anti-Patterns

### Anti-Pattern 1: Regex-Based Full File Parsing

**What people do:** Use regex to extract sections and values from .tscn/.tres files.
**Why it's wrong:** The format has nested arrays of dictionaries containing resource references, multiline string values, and values like `[{"frames": [{"texture": SubResource("AtlasTexture_abc")}]}]` that break regex. A regex-based parser will silently drop or mangle nested structures.
**Do this instead:** Use a state machine tokenizer that tracks bracket depth and string context, then parse sections structurally.

### Anti-Pattern 2: Calling subprocess Directly from Command Handlers

**What people do:** Scatter `subprocess.run(["godot", "--headless", ...])` calls throughout command modules.
**Why it's wrong:** Binary discovery logic, timeout handling, error parsing, and platform-specific quirks get duplicated. Testing requires mocking subprocess everywhere.
**Do this instead:** Route all Godot invocations through `godot_backend.py`. Mock one class in tests.

### Anti-Pattern 3: Mixing File I/O with Domain Logic

**What people do:** Read the Aseprite JSON, compute SpriteFrames, and write the .tres file all in one function.
**Why it's wrong:** Cannot unit test the conversion logic without real files. Cannot reuse the conversion logic for a different output format. Makes the function too long and too coupled.
**Do this instead:** Three separate layers: parse input (formats/), transform data (domain/), write output (formats/). Each layer is independently testable.

### Anti-Pattern 4: Treating project.godot as Standard INI

**What people do:** Use Python's `configparser` directly, which works for string and numeric values but silently corrupts Godot-typed values like `Vector2(100, 200)` or `PackedStringArray("a", "b")`.
**Why it's wrong:** `configparser` treats everything after `=` as a plain string and may mangle quoting, line continuations, or Godot-specific syntax. It also doesn't handle Godot's feature override dot notation (`setting.windows="value"`).
**Do this instead:** Write a thin INI-like parser that preserves Godot value types as opaque strings unless specifically asked to deserialize them. For reading, this is safe. For writing, round-trip the original text and only modify targeted keys.

### Anti-Pattern 5: Eager GodotBackend Initialization

**What people do:** Initialize the GodotBackend (which calls `shutil.which("godot")`) at import time or at CLI startup.
**Why it's wrong:** Direct-mode commands (sprite, tileset, resource) do not need a Godot binary. Failing to find Godot should not prevent these commands from running.
**Do this instead:** Lazy initialization via a property on the context object. The backend is only created when a headless-mode command actually needs it.

## Integration Points

### External Tools

| Tool | Integration Pattern | Notes |
|------|---------------------|-------|
| Godot binary | subprocess via `godot_backend.py` | Must support 4.5+; binary discovered via PATH or --godot flag or GODOT_BINARY env var |
| Aseprite CLI | Not called directly; we consume its JSON output | User runs `aseprite -b` separately; gdauto only reads the JSON + PNG output |
| pytest | CliRunner for unit tests; subprocess for E2E | E2E tests marked with `@pytest.mark.requires_godot` |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| CLI commands <-> domain logic | Function calls with typed data models (dataclasses) | Commands never pass raw strings to domain functions; always parsed first |
| Domain logic <-> format layer | Function calls with typed data models | Domain returns a resource model; format layer serializes it |
| CLI commands <-> godot_backend | Method calls on GodotBackend instance | Backend returns GodotResult or raises GodotError |
| Format parser <-> value_types | Function calls for (de)serialization | Parser calls `deserialize_value("Rect2(0,0,32,32)")` -> Rect2 dataclass |

## Build Order (Suggested Phase Sequence)

Dependencies between components dictate the build order:

```
Phase 1: Foundation
  value_types.py  (no dependencies; enables everything else)
      |
  parser.py + tres.py + tscn.py  (depends on value_types)
      |
  godot_config.py  (depends on value_types)
      |
  cli.py + output.py + godot_backend.py  (framework; depends on nothing domain-specific)

Phase 2: Aseprite-to-SpriteFrames (core value proposition)
  aseprite.py  (depends on nothing; pure JSON parsing)
      |
  sprite_frames.py  (depends on value_types for Rect2, etc.)
      |
  sprite.py CLI commands  (depends on aseprite.py, sprite_frames.py, tres.py, cli.py)
      |
  Unit tests + E2E load test for generated .tres

Phase 3: TileSet Automation (second key differentiator)
  tileset_builder.py + collision_shapes.py  (depends on value_types)
      |
  tileset.py CLI commands  (depends on tileset_builder.py, tres.py)
      |
  Unit tests + E2E load test

Phase 4: Project and Export (headless Godot integration)
  project.py  (depends on godot_config.py, godot_backend.py)
      |
  export.py  (depends on godot_backend.py)
      |
  E2E tests (require Godot binary)

Phase 5: Scene and Resource Inspection (utility commands)
  scene_builder.py  (depends on tscn.py)
      |
  scene.py + resource.py  (depends on tscn.py, tres.py)

Phase 6: Polish
  SKILL.md generation
  Shell completion
  Error message refinement
```

**Phase ordering rationale:**
- value_types and the parser must come first because every other component depends on them for reading and writing Godot files.
- The Aseprite bridge (Phase 2) is the core value proposition and has the clearest specification (Aseprite JSON is well-documented). Ship this first to validate the architecture.
- TileSet automation (Phase 3) exercises the same parser/writer infrastructure with a more complex resource type, validating that the architecture generalizes.
- Headless Godot integration (Phase 4) is deferred because it requires external binary setup and its commands are independent of the file manipulation pipeline.
- Scene/resource inspection (Phase 5) builds on the parser established in Phase 1 and benefits from all bug fixes discovered in Phases 2-3.

## Sources

- [Click Documentation: Complex Applications](https://click.palletsprojects.com/en/stable/complex/) (HIGH confidence, official docs)
- [Click Documentation: Testing](https://click.palletsprojects.com/en/stable/testing/) (HIGH confidence, official docs)
- [GDToolkit Architecture (DeepWiki)](https://deepwiki.com/Scony/godot-gdscript-toolkit) (HIGH confidence, analysis of open source project)
- [godot-parser GitHub](https://github.com/stevearc/godot_parser) (HIGH confidence, primary source)
- [Godot TSCN File Format Docs](https://docs.godotengine.org/en/4.4/contributing/development/file_formats/tscn.html) (HIGH confidence, official Godot docs)
- [Godot ProjectSettings (DeepWiki)](https://deepwiki.com/godotengine/godot/3.3-project-settings) (MEDIUM confidence, third-party analysis of official source)
- [Simon Willison: CLI Tools in Python](https://simonwillison.net/2023/Sep/30/cli-tools-python/) (MEDIUM confidence, experienced practitioner)
- [Simon Willison: pytest-subprocess](https://til.simonwillison.net/pytest/pytest-subprocess) (HIGH confidence, practical reference)
- [State Machine Parser Patterns](https://etutorials.org/Programming/Python.+Text+processing/Chapter+4.+Parsers+and+State+Machines/) (MEDIUM confidence, established reference)

---
*Architecture research for: Python CLI tooling for Godot game engine automation*
*Researched: 2026-03-27*
