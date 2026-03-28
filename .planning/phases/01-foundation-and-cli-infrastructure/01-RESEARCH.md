# Phase 1: Foundation and CLI Infrastructure - Research

**Researched:** 2026-03-27
**Domain:** Python CLI tooling, Godot text file format parsing, project management
**Confidence:** HIGH

## Summary

Phase 1 is a greenfield build of a Python CLI tool (gdauto) with three major subsystems: (1) a custom parser for Godot's .tscn/.tres text file formats, (2) a Click-based CLI framework with --json support and rich-click formatting, and (3) project management commands (info, validate, create) plus a Godot backend wrapper.

The Godot text format (format=3 for Godot 4.x) is well-specified: bracket-section headers, key=value properties, nested GDScript-like value literals (Vector2, Rect2, Color, etc.), and string-based resource IDs in the `Type_xxxxx` pattern (5 random alphanumeric characters). The UID system uses base-34 encoding of 64-bit random values (character set: a-y, 0-8; 'z' and '9' are never used due to an off-by-one bug that cannot be fixed for compatibility). The parser must handle round-trip fidelity including comment and whitespace preservation. The project.godot file is INI-like but has important quirks: global keys before any section header (e.g., `config_version=5`), Godot value constructors as values (e.g., `PackedStringArray(...)`), and multi-line values with nested `Object(...)` constructors. Standard configparser cannot handle this without significant preprocessing; a custom parser is recommended for project.godot as well.

The Click 8.3.1 + rich-click 1.9.7 stack is stable and well-suited. Global flags (--json, --verbose, --quiet, --no-color) should be defined on the root group and propagated via Click's context object. The `uv` package manager (0.11.2 current) with hatchling build backend handles project initialization, dependency management, and entry point registration through pyproject.toml.

**Primary recommendation:** Build three layered subsystems in order: (1) pyproject.toml + CLI skeleton with global flag infrastructure, (2) custom .tscn/.tres parser with typed value models and round-trip fidelity, (3) project commands and resource inspection on top of the parser. Use uv for all package management. Target Python >= 3.12.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Section-based flat model. GdResource/GdScene at the top with ordered lists of ExtResource, SubResource, and property sections. Mirrors the .tres/.tscn file structure 1:1. Round-trip fidelity is the priority; feature modules handle their own lookups.
- **D-02:** Typed dataclasses for Godot value types (Vector2, Rect2, Color, Transform2D, etc.) with full arithmetic support (addition, subtraction, multiplication, dot product, length, contains, intersection, etc.).
- **D-03:** Godot-native string serialization in JSON output. Vector2(0, 0) becomes "Vector2(0, 0)" in JSON. Matches what Godot users see in .tres files.
- **D-04:** Lenient parser: preserve unknown sections and values as raw strings, warn on stderr. Forward-compatible with future Godot versions and custom resources.
- **D-05:** Preserve comments and blank lines for round-trip fidelity (FMT-06). Editing an existing file should not produce spurious diffs.
- **D-06:** Single module per format: tscn.py owns .tscn parse + serialize, tres.py owns .tres parse + serialize.
- **D-07:** Full load into memory (no streaming/lazy API). Godot files are typically small. Simple API, optimize later if a real bottleneck emerges.
- **D-08:** Match Godot's exact resource ID format (Type_xxxxx pattern with the same character set). Generated files should be indistinguishable from Godot-generated ones.
- **D-09:** Opinionated built-in template with recommended folder structure: project.godot, main scene, icon.svg, plus folders (scenes/, scripts/, assets/, sprites/, tilesets/), .gitignore, .gdignore.
- **D-10:** Built-in template only for v1. No custom template support in this phase.
- **D-11:** Godot 4.5 defaults: config_version=5, format=3.
- **D-12:** Argument only, no interactive prompts. `gdauto project create my-game` creates the project. Fails if no name given. Agent-native.
- **D-13:** Rich formatted output via rich-click. Colored tables, tree views for node hierarchies. Degrades gracefully to plain text when piped or in no-color mode.
- **D-14:** Three verbosity levels: default (normal), --verbose/-v (extra detail: file paths, timing, parse stats), --quiet/-q (suppress all except errors).
- **D-15:** Always include fix suggestions in error messages. Every error has an actionable hint. Helps both humans and AI agents recover.
- **D-16:** Short flags for common options: -j/--json, -v/--verbose, -q/--quiet, -o/--output.
- **D-17:** Godot binary discovery: auto-discover from PATH by default. GODOT_PATH environment variable as override. --godot-path flag as highest priority. Resolution order: flag > env > PATH.
- **D-18:** --json is a global flag on the main Click group, inherited by all subcommands via Click context. Single implementation point, guaranteed consistency.
- **D-19:** Both --no-color flag and NO_COLOR environment variable respected. Rich-click handles this natively.
- **D-20:** Validate Godot binary version (>= 4.5) on first use, cache result for the session. Subsequent commands skip the check.

### Claude's Discretion
- Shared bracket-section syntax organization: whether to extract common parsing logic into a base module or keep it per-format
- UID generation strategy: whether to generate UIDs for new resources or preserve-only
- Resource inspect metadata: whether JSON output includes a metadata wrapper (file path, format version, warnings) or raw resource data only
- Resource inspect human display: syntax-highlighted Godot format vs structured table/tree view

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CLI-01 | Click-based CLI entry point with command groups: project, export, sprite, tileset, scene, resource | Click 8.3.1 group/subcommand pattern with invoke_without_command=True; rich-click drop-in replacement |
| CLI-02 | Every command supports --json flag switching to structured JSON output | Global --json flag on root group via ctx.ensure_object pattern; D-18 locks this approach |
| CLI-03 | Every command has --help with AI-parseable descriptions | rich-click provides formatted help; Click's help_option_names and docstrings |
| CLI-04 | All errors produce non-zero exit codes | Click's sys.exit integration; ctx.exit(code) pattern |
| CLI-05 | With --json, errors produce {"error": "message", "code": "ERROR_CODE"} with fix suggestions | Custom exception handler wrapping Click's error mechanism; D-15 requires fix hints |
| FMT-01 | Custom state-machine parser for .tscn format=3 | Bracket-section format documented; section types: gd_scene, ext_resource, sub_resource, node, connection, editable |
| FMT-02 | Custom state-machine parser for .tres format=3 | Same bracket format with gd_resource header; section types: gd_resource, ext_resource, sub_resource, resource |
| FMT-03 | Godot value type serializer/deserializer | Vector2, Vector2i, Vector3, Rect2, Color, Transform2D, StringName, arrays, dicts; D-02 requires typed dataclasses with arithmetic |
| FMT-04 | Resource ID generation matching Godot 4.x format | 5-char alphanumeric IDs from RandomPCG, format: Type_xxxxx; D-08 requires exact match |
| FMT-05 | UID generation and .uid companion file support for Godot 4.4+ | Base-34 encoding (a-y, 0-8) of 63-bit random values; uid:// prefix; .uid files are single-line text |
| FMT-06 | Round-trip fidelity: parse and re-serialize without spurious diffs | D-05 requires comment/blank line preservation; state machine must track whitespace |
| FMT-07 | resource inspect command dumps .tres/.tscn as structured JSON | Parser output + JSON serialization with D-03 Godot-native string format for value types |
| PROJ-01 | project info reads project.godot, outputs project metadata as JSON | Custom INI-like parser needed; global keys before sections, Godot value constructors |
| PROJ-02 | project validate checks res:// paths resolve, detects missing resources, orphan scripts | Requires parser + filesystem walk; res:// path resolution against project root |
| PROJ-03 | project validate optionally runs Godot --check-only for script syntax validation | GodotBackend wrapper with --check-only flag; D-20 version validation |
| PROJ-04 | project create scaffolds new projects from built-in template | D-09/D-10/D-11/D-12 lock template structure, Godot 4.5 defaults, argument-only interface |
| PROJ-05 | Godot backend wrapper: discovers binary, validates version, manages timeouts, parses stderr | D-17 discovery order (flag > env > PATH); D-20 version caching; subprocess.run with timeout |
| TEST-01 | Unit tests for all pure Python logic run without Godot binary | pytest 9.0.2 with markers; unit tests in tests/unit/, e2e in tests/e2e/ |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Tech stack**: Python 3.10+, Click >= 8.0, pytest >= 7.0 (CLAUDE.md minimum; recommended stack says Python >= 3.12)
- **Engine compatibility**: Godot 4.5+ binary on PATH (for E2E tests and headless commands only)
- **Independence**: No Godot dependency for file manipulation commands
- **Error contract**: All errors produce non-zero exit codes and actionable messages; --json errors produce `{"error": "message", "code": "ERROR_CODE"}`
- **File validity**: Generated .tres/.tscn files must be loadable by Godot without modification
- **Code style**: No em dashes, no emojis, type hints on all signatures, docstrings on public functions, functions under 30 lines, comments on non-obvious logic only
- **Custom parser over godot_parser**: Locked decision; stevearc/godot_parser rejected
- **dataclasses over Pydantic**: Locked decision; no Pydantic dependency
- **Pillow is optional**: Not needed in Phase 1 at all (only needed for sprite create-atlas/split)
- **rich-click**: Drop-in via `import rich_click as click`
- **uv**: Preferred package manager; pyproject.toml with hatchling build backend
- **ruff**: Single tool for linting + formatting
- **mypy**: Strict mode type checking

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | >= 3.12 (target 3.13) | Runtime | 3.12+ gives modern type syntax (PEP 695), f-string improvements, 15% perf boost. 3.13 locally installed. configparser `allow_unnamed_section` available in 3.13+ (useful for project.godot). |
| Click | 8.3.1 | CLI framework | CLAUDE.md mandates Click. Current stable. Groups, pass_context, invoke_without_command. Dropped Python 3.9 support. |
| rich-click | 1.9.7 | CLI help formatting | Drop-in replacement: `import rich_click as click`. Colored help, grouped options, tables. Degrades gracefully. |
| rich | (transitive) | Terminal formatting | Transitive dependency via rich-click. Used directly for human-readable output (tables, trees, syntax highlighting). |
| dataclasses | stdlib | Internal data models | Locked decision. Godot value types, parser data structures. Zero dependency. |
| configparser | stdlib | project.godot parsing (partial) | Handles INI-like sections. Requires preprocessing for global keys and Godot value types. |
| json | stdlib | JSON output, Aseprite metadata | All --json CLI output and future Aseprite JSON parsing. |
| pathlib | stdlib | File path handling | Cross-platform path operations for res:// resolution. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hatchling | 1.29.0 | Build backend | pyproject.toml build system. Generates console_scripts entry point. |
| pytest | 9.0.2 | Test runner | Unit and E2E tests. Markers for @pytest.mark.requires_godot. |
| pytest-cov | 7.1.0 | Coverage | Reports parser and CLI branch coverage. |
| ruff | 0.15.8 | Lint + format | Replaces flake8, black, isort. Single tool, Rust-powered. |
| mypy | 1.19.1 | Static type checking | Strict mode for all modules. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom .tscn/.tres parser | stevearc/godot_parser 0.1.7 | Locked out: inactive, Godot 4 issues, whitespace bugs |
| Custom project.godot parser | configparser alone | configparser cannot handle global keys before sections (config_version=5), multi-line Object() values, or Godot type constructors without heavy preprocessing. Custom line-based parser is simpler. |
| dataclasses | Pydantic v2 | Locked out: unnecessary validation overhead for internal data |
| Click 8.3 | Typer | CLAUDE.md specifies Click; Typer wraps Click anyway |
| hatchling | setuptools | hatchling is modern, works with uv natively, simpler config |

**Installation:**
```bash
uv init --package --build-backend hatchling gdauto
cd gdauto
uv add click rich-click
uv add --dev pytest pytest-cov ruff mypy
```

**Version verification:** All versions verified against PyPI on 2026-03-27:
- click: 8.3.1 (current)
- rich-click: 1.9.7 (Jan 2026)
- hatchling: 1.29.0 (current)
- pytest: 9.0.2 (current)
- pytest-cov: 7.1.0 (current)
- ruff: 0.15.8 (current; CLAUDE.md says 0.11.x but that is stale)
- mypy: 1.19.1 (current; CLAUDE.md says 1.19.x, confirmed)

## Architecture Patterns

### Recommended Project Structure

```
gdauto/
  pyproject.toml              # All config: deps, entry points, ruff, mypy, pytest
  src/
    gdauto/
      __init__.py             # Package version, metadata
      cli.py                  # Click entry point, root group, global options
      commands/
        __init__.py
        project.py            # project info, validate, create
        resource.py           # resource inspect
        export.py             # (stub for Phase 3)
        sprite.py             # (stub for Phase 2)
        tileset.py            # (stub for Phase 2/3)
        scene.py              # (stub for Phase 4)
      formats/
        __init__.py
        values.py             # Godot value types: Vector2, Rect2, Color, etc.
        tscn.py               # .tscn parser + serializer (D-06)
        tres.py               # .tres parser + serializer (D-06)
        common.py             # Shared bracket-section parsing (Claude's discretion)
        project_cfg.py        # project.godot parser
        uid.py                # UID generation and .uid file handling
      backend.py              # GodotBackend wrapper (subprocess, discovery, version check)
      errors.py               # Custom exceptions with error codes and fix suggestions
      output.py               # Output formatting: JSON mode, human mode, verbosity
  tests/
    __init__.py
    unit/
      __init__.py
      test_values.py          # Godot value type parse/serialize/arithmetic
      test_tscn_parser.py     # .tscn parsing round-trip
      test_tres_parser.py     # .tres parsing round-trip
      test_project_cfg.py     # project.godot parsing
      test_uid.py             # UID generation and encoding
      test_cli.py             # Click CLI integration (CliRunner)
      test_project_commands.py # project info/validate/create
      test_resource_inspect.py # resource inspect
    e2e/
      __init__.py
      test_godot_backend.py   # Real Godot invocation tests
    fixtures/
      sample.tscn             # Known-good .tscn file
      sample.tres             # Known-good .tres file
      sample_project/         # Minimal Godot project for testing
        project.godot
        icon.svg
```

**Note on src layout:** Using `src/gdauto/` layout (not flat `gdauto/`) because uv --package defaults to this, it prevents accidental imports of the source directory, and hatchling handles it natively. CLI-METHODOLOGY.md shows a flat layout but the src layout is the modern Python standard and should be preferred.

### Pattern 1: Click Global Flags via Context Object

**What:** Define all global flags (--json, --verbose, --quiet, --no-color, --godot-path) on the root group and store them in a context object accessible to all subcommands.

**When to use:** Every command needs access to output mode and verbosity settings.

**Example:**
```python
# src/gdauto/cli.py
import rich_click as click
from dataclasses import dataclass

@dataclass
class GlobalConfig:
    """Global configuration passed through Click context."""
    json_mode: bool = False
    verbose: bool = False
    quiet: bool = False
    godot_path: str | None = None

@click.group(invoke_without_command=True)
@click.option("-j", "--json", "json_mode", is_flag=True, help="Output as JSON")
@click.option("-v", "--verbose", is_flag=True, help="Extra detail in output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-error output")
@click.option("--no-color", is_flag=True, help="Disable colored output")
@click.option("--godot-path", envvar="GODOT_PATH", help="Path to Godot binary")
@click.version_option()
@click.pass_context
def cli(ctx: click.Context, json_mode: bool, verbose: bool, quiet: bool,
        no_color: bool, godot_path: str | None) -> None:
    """gdauto: Agent-native CLI for Godot Engine."""
    ctx.ensure_object(dict)
    ctx.obj = GlobalConfig(
        json_mode=json_mode,
        verbose=verbose,
        quiet=quiet,
        godot_path=godot_path,
    )
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

# Subcommand accesses global config:
@project.command()
@click.argument("path", default=".")
@click.pass_context
def info(ctx: click.Context, path: str) -> None:
    """Show project metadata."""
    config: GlobalConfig = ctx.obj
    # ... use config.json_mode, config.verbose, etc.
```

### Pattern 2: Structured Error Handling with Fix Suggestions

**What:** Custom exception hierarchy with error codes and actionable fix text. A centralized error handler formats errors for both human and JSON modes.

**When to use:** Every error path in every command.

**Example:**
```python
# src/gdauto/errors.py
from dataclasses import dataclass

@dataclass
class GdautoError(Exception):
    """Base error with structured output support."""
    message: str
    code: str
    fix: str | None = None

    def to_dict(self) -> dict:
        result = {"error": self.message, "code": self.code}
        if self.fix:
            result["fix"] = self.fix
        return result

class FileNotFoundError(GdautoError):
    """A required file was not found."""
    pass

class ParseError(GdautoError):
    """Failed to parse a Godot file."""
    pass

class GodotBinaryError(GdautoError):
    """Godot binary not found or wrong version."""
    pass
```

### Pattern 3: Output Abstraction (JSON vs Human)

**What:** A single output function that switches between JSON and human-readable output based on global config.

**When to use:** Every command that produces output.

**Example:**
```python
# src/gdauto/output.py
import json
import sys
import rich_click as click

def emit(data: dict, human_fn: callable, ctx: click.Context) -> None:
    """Output data as JSON or human-readable format."""
    config = ctx.obj
    if config.json_mode:
        click.echo(json.dumps(data, indent=2))
    else:
        human_fn(data, verbose=config.verbose)

def emit_error(error: GdautoError, ctx: click.Context) -> None:
    """Output an error in the appropriate format."""
    config = ctx.obj
    if config.json_mode:
        click.echo(json.dumps(error.to_dict()), err=True)
    else:
        click.secho(f"Error: {error.message}", fg="red", err=True)
        if error.fix:
            click.secho(f"Fix: {error.fix}", fg="yellow", err=True)
    ctx.exit(1)
```

### Pattern 4: Parser State Machine Structure

**What:** A line-based state machine parser for .tscn/.tres format that tracks current section, accumulates multi-line values, preserves comments and blank lines.

**When to use:** The core of FMT-01 and FMT-02 implementation.

**Example (conceptual):**
```python
# Parser states
# HEADER: reading the first [gd_scene...] or [gd_resource...] line
# SECTION_HEADER: reading a [ext_resource...], [sub_resource...], [node...], etc.
# PROPERTIES: reading key = value pairs within a section
# MULTILINE_VALUE: accumulating a value that spans multiple lines (brackets not balanced)

@dataclass
class ParseState:
    mode: str  # "header" | "properties" | "multiline"
    bracket_depth: int  # Track nested {}, [], () for multi-line detection
    current_section: Section | None
    buffer: list[str]  # For multi-line value accumulation
    comments: list[str]  # Comments before current section (for round-trip)
```

### Anti-Patterns to Avoid

- **Regex-based full parsing:** The format has nested structures (arrays of dicts with Godot constructors). Regex cannot handle arbitrary nesting depth. Use a state machine with bracket depth tracking.
- **configparser for project.godot:** config_version=5 has no section header. Multi-line values with Object() constructors break configparser's assumptions. Build a custom line-based parser.
- **Interleaving parse and serialize logic:** Keep parse (text to model) and serialize (model to text) as separate functions in each module. Shared model in between.
- **Hardcoded output strings in commands:** Always go through the output abstraction. Never directly print JSON or format strings in command handlers.
- **Shadowing Python builtins:** The Click option `--json` will conflict with the `json` module import. Use `as_json` or `json_mode` as the parameter name (D-16 uses `-j/--json` with param name `json_mode`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI argument parsing | Custom argv parser | Click 8.3.1 | Click handles types, defaults, help generation, error messages, shell completion |
| Terminal colors/tables | ANSI escape codes | rich (via rich-click) | Cross-platform, NO_COLOR support, graceful degradation, tree views |
| Project scaffolding dirs | os.makedirs chains | pathlib.Path.mkdir(parents=True) | Cleaner, cross-platform, idempotent with exist_ok |
| Subprocess management | os.system/os.popen | subprocess.run with timeout | Proper error handling, timeout support, capture stdout/stderr separately |
| Random ID generation | custom PRNG | secrets module | CSPRNG for UID generation matching Godot's approach |
| JSON serialization | string concatenation | json.dumps with custom encoder | Handles escaping, unicode, nested structures correctly |
| Test CLI invocation | subprocess in tests | click.testing.CliRunner | In-process testing, captures output, checks exit codes |

**Key insight:** The only truly custom code needed is the .tscn/.tres parser and the Godot value type system. Everything else has a well-tested library solution.

## Discretion Recommendations

### Shared bracket-section syntax (Claude's discretion)

**Recommendation: Extract common parsing into a base module (common.py).**

Rationale: .tscn and .tres share identical syntax for bracket sections, key=value pairs, and multi-line values. The only difference is the header tag (gd_scene vs gd_resource) and which section types are valid. A shared `parse_sections()` function in `common.py` with format-specific validation in `tscn.py`/`tres.py` avoids duplicating 80% of the parser logic. D-06 says "single module per format" for ownership, which is preserved: tscn.py and tres.py each own their parse/serialize API, they just delegate shared bracket parsing to common.py.

### UID generation strategy (Claude's discretion)

**Recommendation: Generate UIDs for new resources; preserve existing UIDs on parse/re-serialize.**

Rationale: FMT-05 requires UID generation and .uid companion file support. When gdauto creates new resources (project create, future sprite import), it should generate valid UIDs matching Godot's format. When round-tripping existing files, UIDs must be preserved exactly. The uid.py module should expose both `generate_uid() -> str` and handle .uid file read/write.

### Resource inspect metadata (Claude's discretion)

**Recommendation: Include a metadata wrapper in JSON output.**

Rationale: Raw resource data alone loses context (which file, what format version, any parse warnings). Wrap with:
```json
{
  "file": "path/to/resource.tres",
  "format": 3,
  "type": "SpriteFrames",
  "uid": "uid://abc123",
  "warnings": [],
  "resource": { ... actual resource data ... }
}
```
Human mode does not need the wrapper; it shows it naturally via headers.

### Resource inspect human display (Claude's discretion)

**Recommendation: Structured tree view using rich.tree, not syntax-highlighted raw text.**

Rationale: The purpose of `resource inspect` is to understand what is in a file, not to view the raw text (users can just `cat` the file for that). A tree view showing sections, sub-resources, ext-resources, and key properties is more useful for both humans and AI agents reading the human output. JSON mode gets the full structured data.

## Godot File Format Specification (format=3)

### .tscn and .tres shared syntax

Both formats use bracket-section headers followed by key=value properties:

```
[header_tag key1=value1 key2=value2]

[section_tag attr1="val" attr2="val"]
property_key = property_value
another_key = another_value
```

**Header tags:**
- `gd_scene` (for .tscn): attributes include `load_steps`, `format`, `uid`
- `gd_resource` (for .tres): attributes include `type`, `load_steps`, `format`, `uid`

**Section tags (shared):**
- `ext_resource`: type, uid, path, id
- `sub_resource`: type, id

**Section tags (.tscn only):**
- `node`: name, type, parent, instance, owner, index, groups, node_paths, unique_id
- `connection`: signal, from, to, method, flags, binds
- `editable`: path

**Section tags (.tres only):**
- `resource` (no attributes; marks the main resource properties section)

### Resource ID format

Godot generates internal resource IDs as `Type_xxxxx` where:
- `Type` is the resource class name (e.g., `AtlasTexture`, `SphereMesh`, `Animation`)
- `_` is a literal underscore separator
- `xxxxx` is a 5-character string from `generate_scene_unique_id()`
- Character set: ASCII letters (a-z, A-Z), digits (0-9), underscore (_)
- Generated via RandomPCG seeded with time-based values
- Collision detection: saver retries on collision

Example IDs: `AtlasTexture_abc12`, `SphereMesh_4w3ye`, `Animation_k8mno`

External resource IDs use a simpler format: just the alphanumeric string, often `"1_sheet"` or similar indexed patterns.

### UID format

- 63-bit random value (masked: `uid & 0x7FFFFFFFFFFFFFFF`)
- Encoded in base-34 (NOT base-36): characters a-y (25) + 0-8 (9) = 34 total
- Off-by-one bug in Godot source: 'z' and '9' are never used, cannot be fixed for compatibility
- Maximum encoded length: 13 characters
- Format: `uid://[encoded_string]` (e.g., `uid://cecaux1sm7mo0`)
- .uid companion files: single line containing just the uid:// string

**id_to_text algorithm (Python equivalent):**
```python
CHARS = "abcdefghijklmnopqrstuvwxy012345678"  # 34 chars: a-y, 0-8
BASE = len(CHARS)  # 34

def uid_to_text(uid: int) -> str:
    if uid < 0:
        return "uid://<invalid>"
    chars = []
    value = uid
    while True:
        chars.append(CHARS[value % BASE])
        value //= BASE
        if value == 0:
            break
    return "uid://" + "".join(chars)

def text_to_uid(text: str) -> int:
    if not text.startswith("uid://"):
        return -1
    uid = 0
    for char in text[6:]:
        uid *= BASE
        if 'a' <= char <= 'y':
            uid += ord(char) - ord('a')
        elif '0' <= char <= '8':
            uid += ord(char) - ord('0') + 25
        else:
            return -1
    return uid & 0x7FFFFFFFFFFFFFFF
```

### project.godot format

INI-like with Godot-specific extensions:

```ini
; Comment lines start with semicolons
config_version=5        ; GLOBAL key, no section header!

[application]
config/name="My Game"
config/description="Description text
that can span multiple lines"
config/tags=PackedStringArray("2d", "demo")
run/main_scene="res://main.tscn"
config/features=PackedStringArray("4.5")
config/icon="res://icon.svg"

[autoload]
GameManager="*res://systems/game_manager.gd"  ; * prefix = singleton
AudioManager="res://systems/audio_manager.tscn"

[input]
move_up={
"deadzone": 0.2,
"events": [Object(InputEventKey,...)]
}

[display]
window/size/viewport_width=1280
window/size/viewport_height=720

[rendering]
renderer/rendering_method="gl_compatibility"
```

**Parsing challenges:**
1. `config_version=5` appears before any section header
2. Values can be Godot constructors: `PackedStringArray(...)`, `Vector2(...)`, `Object(...)`
3. Multi-line values: `{...}` blocks can span many lines
4. Slash-separated keys within sections: `config/name`, `window/size/viewport_width`
5. Comments use `;` (not `#`)
6. String values always quoted with double quotes
7. Boolean values: `true`/`false` (lowercase)
8. Integer values: unquoted numbers

**Recommendation:** Do NOT use configparser for the full parse. Build a custom line-based parser similar to the .tscn parser. It shares the bracket-depth tracking for multi-line values and the Godot value type deserializer.

### Godot value types requiring implementation (FMT-03)

| Type | Example in .tres/.tscn | Python Representation |
|------|----------------------|----------------------|
| Vector2 | `Vector2(1.5, 2.0)` | `Vector2(x=1.5, y=2.0)` dataclass |
| Vector2i | `Vector2i(1, 2)` | `Vector2i(x=1, y=2)` dataclass |
| Vector3 | `Vector3(1.0, 2.0, 3.0)` | `Vector3(x=1.0, y=2.0, z=3.0)` |
| Vector3i | `Vector3i(1, 2, 3)` | `Vector3i(x=1, y=2, z=3)` |
| Rect2 | `Rect2(0, 0, 32, 32)` | `Rect2(x=0, y=0, w=32, h=32)` |
| Rect2i | `Rect2i(0, 0, 32, 32)` | `Rect2i(x=0, y=0, w=32, h=32)` |
| Color | `Color(1, 0.5, 0, 1)` | `Color(r=1.0, g=0.5, b=0.0, a=1.0)` |
| Transform2D | `Transform2D(1, 0, 0, 1, 0, 0)` | `Transform2D(xx, xy, yx, yy, ox, oy)` |
| Transform3D | `Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)` | 3x3 basis + origin |
| StringName | `&"idle"` | `StringName(value="idle")` |
| NodePath | `NodePath("Path/To/Node")` | `NodePath(path="Path/To/Node")` |
| ExtResource ref | `ExtResource("1_sheet")` | Reference type |
| SubResource ref | `SubResource("AtlasTexture_abc12")` | Reference type |
| PackedByteArray | `PackedByteArray(...)` | `bytes` |
| PackedStringArray | `PackedStringArray("a", "b")` | `list[str]` |
| PackedFloat32Array | `PackedFloat32Array(0.0, 1.0)` | `list[float]` |
| PackedInt32Array | `PackedInt32Array(0, 1, 2)` | `list[int]` |
| AABB | `AABB(-1, -1, -1, 2, 2, 2)` | `AABB(x, y, z, sx, sy, sz)` |
| Array | `[1, 2, "three"]` | `list` |
| Dictionary | `{"key": "value"}` | `dict` |
| null | `null` | `None` |
| bool | `true` / `false` | `bool` |

D-02 requires arithmetic operations on Vector2, Rect2, Color, Transform2D at minimum: add, subtract, multiply, dot product, length, contains (Rect2), intersection (Rect2).

D-03 requires that JSON serialization outputs `"Vector2(1.5, 2.0)"` as a string, not `{"x": 1.5, "y": 2.0}`.

## Common Pitfalls

### Pitfall 1: configparser for project.godot

**What goes wrong:** configparser throws MissingSectionHeaderError because `config_version=5` appears before any `[section]`.
**Why it happens:** project.godot is not valid INI. It has global keys, Godot value constructors, and multi-line Object() blocks.
**How to avoid:** Build a custom line-based parser (project_cfg.py) that handles: (a) global keys before sections, (b) semicolon comments, (c) multi-line values via bracket-depth tracking, (d) preserves Godot value types as strings for the parser layer (value type deserialization happens separately).
**Warning signs:** MissingSectionHeaderError, truncated values, lost Object() blocks.

### Pitfall 2: Multi-line value detection in .tscn/.tres

**What goes wrong:** Parser treats the first line of a multi-line value as the complete value, breaking subsequent section detection.
**Why it happens:** Values like arrays `[{...}, {...}]` and input maps `{...}` span multiple lines. The parser needs to track bracket depth.
**How to avoid:** When a `key = value` line is read, check if brackets `[]`, `{}`, `()` are balanced. If not, enter MULTILINE mode and accumulate lines until balanced.
**Warning signs:** Sections appearing inside values, unmatched bracket errors, lost properties.

### Pitfall 3: String quoting inside Godot values

**What goes wrong:** A naive bracket-depth tracker gets confused by brackets inside quoted strings.
**Why it happens:** Values like `"events": [Object(InputEventKey,"resource_name":"")]` contain quoted strings with special characters.
**How to avoid:** The bracket-depth tracker must skip characters inside double-quoted strings. Track `in_string` state, handle escaped quotes `\"`.
**Warning signs:** Premature end of multi-line value, unbalanced bracket false positives.

### Pitfall 4: UID base-34 encoding off-by-one

**What goes wrong:** Using base-36 (a-z, 0-9) generates UIDs that Godot rejects because it uses only base-34 (a-y, 0-8).
**Why it happens:** Godot's source code has an off-by-one bug that makes 'z' and '9' unreachable. This is a known issue documented in their source comments but cannot be fixed for compatibility.
**How to avoid:** Use exactly the character set `abcdefghijklmnopqrstuvwxy012345678` (34 chars). Test by generating many UIDs and verifying none contain 'z' or '9'.
**Warning signs:** Godot warning "Invalid UID" when loading generated files.

### Pitfall 5: Resource ID format mismatch

**What goes wrong:** Generated resource IDs don't match Godot's format, causing files to load but with re-assigned IDs on next save (creating spurious diffs).
**Why it happens:** Using wrong character set, wrong length, or wrong prefix format.
**How to avoid:** Use exactly 5 characters from `[a-zA-Z0-9_]`, prefixed with the resource type name and underscore. Verify by creating a file in Godot and comparing ID patterns.
**Warning signs:** Godot re-saving files with different IDs, git diffs on untouched files.

### Pitfall 6: Click --json parameter name shadows json module

**What goes wrong:** `import json` and `@click.option("--json")` conflict because Click creates a parameter named `json`.
**Why it happens:** Python treats `json` as both the module name and the parameter name.
**How to avoid:** Use `@click.option("--json", "json_mode", ...)` to rename the parameter. D-16 already specifies `-j/--json` which uses Click's `is_flag=True` and can be renamed via the second positional arg.
**Warning signs:** `TypeError: 'bool' object is not callable` when trying to use `json.dumps()`.

### Pitfall 7: Round-trip fidelity with trailing newlines and blank lines

**What goes wrong:** Re-serialized file has different trailing whitespace, extra or missing blank lines between sections.
**Why it happens:** Parser strips whitespace during parse, serializer adds its own formatting.
**How to avoid:** D-05 explicitly requires preserving comments and blank lines. The parser model must store inter-section whitespace (blank lines, comments) as part of the document structure. Serialize using the stored whitespace.
**Warning signs:** `git diff` shows changes on lines that were not semantically modified.

### Pitfall 8: Click group stubs causing import errors

**What goes wrong:** Registering stub command groups (export, sprite, tileset, scene) that import heavy dependencies causes slow startup or import errors.
**Why it happens:** Click evaluates all registered commands at import time.
**How to avoid:** Use lazy loading: register groups with minimal imports, use Click's `@group.command()` decorators that only import handler code when the command is actually invoked. Or use empty groups with placeholder help text for Phase 1 stubs.
**Warning signs:** Slow `gdauto --help`, import errors for uninstalled optional dependencies.

## Code Examples

### pyproject.toml skeleton

```toml
[project]
name = "gdauto"
version = "0.1.0"
description = "Agent-native CLI for Godot Engine"
readme = "README.md"
license = "Apache-2.0"
requires-python = ">=3.12"
dependencies = [
    "click>=8.3",
    "rich-click>=1.9",
]

[project.optional-dependencies]
image = ["Pillow>=12.0"]
dev = [
    "pytest>=9.0",
    "pytest-cov>=7.0",
    "ruff>=0.15",
    "mypy>=1.19",
]

[project.scripts]
gdauto = "gdauto.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "requires_godot: marks tests that need Godot binary on PATH",
]

[tool.ruff]
target-version = "py312"
line-length = 99

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "TCH"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
```

### Godot value type dataclass with arithmetic (D-02)

```python
# src/gdauto/formats/values.py
from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True, slots=True)
class Vector2:
    """Godot Vector2 type with arithmetic support."""
    x: float
    y: float

    def __add__(self, other: Vector2) -> Vector2:
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vector2) -> Vector2:
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Vector2:
        return Vector2(self.x * scalar, self.y * scalar)

    def dot(self, other: Vector2) -> float:
        return self.x * other.x + self.y * other.y

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def to_godot(self) -> str:
        """Serialize to Godot format string (D-03)."""
        return f"Vector2({self.x}, {self.y})"

    def __str__(self) -> str:
        return self.to_godot()

@dataclass(frozen=True, slots=True)
class Rect2:
    """Godot Rect2 type."""
    x: float
    y: float
    w: float
    h: float

    def contains(self, point: Vector2) -> bool:
        return (self.x <= point.x <= self.x + self.w and
                self.y <= point.y <= self.y + self.h)

    def intersection(self, other: Rect2) -> Rect2 | None:
        x1 = max(self.x, other.x)
        y1 = max(self.y, other.y)
        x2 = min(self.x + self.w, other.x + other.w)
        y2 = min(self.y + self.h, other.y + other.h)
        if x2 > x1 and y2 > y1:
            return Rect2(x1, y1, x2 - x1, y2 - y1)
        return None

    def to_godot(self) -> str:
        return f"Rect2({self.x}, {self.y}, {self.w}, {self.h})"
```

### UID generation matching Godot's algorithm (FMT-05)

```python
# src/gdauto/formats/uid.py
import secrets
from pathlib import Path

CHARS = "abcdefghijklmnopqrstuvwxy012345678"  # Godot's base-34
BASE = len(CHARS)  # 34
MAX_UID = (1 << 63) - 1  # 63-bit max

def generate_uid() -> int:
    """Generate a random 63-bit UID matching Godot's format."""
    return secrets.randbelow(MAX_UID + 1)

def uid_to_text(uid: int) -> str:
    """Convert numeric UID to uid:// text format."""
    if uid < 0:
        return "uid://<invalid>"
    chars: list[str] = []
    value = uid
    while True:
        chars.append(CHARS[value % BASE])
        value //= BASE
        if value == 0:
            break
    return "uid://" + "".join(chars)

def text_to_uid(text: str) -> int:
    """Convert uid:// text to numeric UID. Returns -1 on invalid."""
    if not text.startswith("uid://") or text == "uid://<invalid>":
        return -1
    uid = 0
    for char in text[6:]:
        uid *= BASE
        if "a" <= char <= "y":
            uid += ord(char) - ord("a")
        elif "0" <= char <= "8":
            uid += ord(char) - ord("0") + 25
        else:
            return -1
    return uid & MAX_UID

def write_uid_file(path: Path, uid_text: str) -> None:
    """Write a .uid companion file."""
    uid_path = Path(str(path) + ".uid")
    uid_path.write_text(uid_text + "\n")

def read_uid_file(path: Path) -> str | None:
    """Read a .uid companion file. Returns None if not found."""
    uid_path = Path(str(path) + ".uid")
    if uid_path.exists():
        return uid_path.read_text().strip()
    return None
```

### GodotBackend wrapper (PROJ-05)

```python
# src/gdauto/backend.py
import shutil
import subprocess
import re
from dataclasses import dataclass, field
from pathlib import Path
from gdauto.errors import GodotBinaryError

@dataclass
class GodotBackend:
    """Wrapper for Godot binary invocations."""
    binary_path: str | None = None
    timeout: int = 120
    _version: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.binary_path is None:
            self.binary_path = shutil.which("godot")

    def ensure_binary(self) -> str:
        """Find and validate the Godot binary. Cache version."""
        if self.binary_path is None:
            raise GodotBinaryError(
                message="Godot binary not found",
                code="GODOT_NOT_FOUND",
                fix="Install Godot 4.5+ and add it to PATH, "
                    "or set GODOT_PATH environment variable",
            )
        if self._version is None:
            self._version = self._check_version()
        return self.binary_path

    def _check_version(self) -> str:
        """Validate Godot version >= 4.5."""
        result = subprocess.run(
            [self.binary_path, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        version_str = result.stdout.strip()
        # Godot outputs like "4.5.2.stable.official.abc1234"
        match = re.match(r"(\d+)\.(\d+)", version_str)
        if not match:
            raise GodotBinaryError(
                message=f"Cannot parse Godot version: {version_str}",
                code="GODOT_VERSION_PARSE",
                fix="Ensure the binary at the path is a valid Godot executable",
            )
        major, minor = int(match.group(1)), int(match.group(2))
        if major < 4 or (major == 4 and minor < 5):
            raise GodotBinaryError(
                message=f"Godot {version_str} is too old (need >= 4.5)",
                code="GODOT_VERSION_TOO_OLD",
                fix="Update Godot to version 4.5 or later",
            )
        return version_str
```

### Click test with CliRunner

```python
# tests/unit/test_cli.py
from click.testing import CliRunner
from gdauto.cli import cli

def test_help_shows_command_groups():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "project" in result.output
    assert "resource" in result.output
    assert "sprite" in result.output
    assert "tileset" in result.output
    assert "export" in result.output
    assert "scene" in result.output

def test_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "gdauto" in result.output

def test_json_error_format():
    runner = CliRunner()
    result = runner.invoke(cli, ["-j", "resource", "inspect", "nonexistent.tres"])
    assert result.exit_code != 0
    import json
    error = json.loads(result.output)
    assert "error" in error
    assert "code" in error
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Godot 3.x integer resource IDs | Godot 4.x string-based Type_xxxxx IDs | Godot 4.0 (2023) | Parser must handle string IDs, not integers |
| No UIDs in file headers | uid="uid://..." in all .tscn/.tres headers | Godot 4.0 (2022) | Parser must extract and preserve UIDs |
| No .uid companion files | .uid files for scripts/shaders | Godot 4.4 (2025) | FMT-05 requirement; new file type to generate |
| Integer load_steps required | load_steps optional/deprecated | Godot 4.6 (2026) | Parser should handle missing load_steps |
| godot_parser library | Custom parser | 2026 (this project) | stevearc/godot_parser abandoned; we build our own |
| pip + requirements.txt | uv + pyproject.toml | 2024-2026 | Modern Python packaging standard |
| black + isort + flake8 | ruff | 2023-2026 | Single tool, 100x faster |

**Deprecated/outdated:**
- `stevearc/godot_parser 0.1.7`: No release in 12+ months, Godot 4 format=3 issues (#9), whitespace fidelity bugs (#14)
- `Pydantic for internal models`: Unnecessary for this use case; dataclasses are sufficient and faster
- `setup.py / setup.cfg`: Replaced by pyproject.toml with hatchling
- Godot 3.x `format=2` support: Out of scope per REQUIREMENTS.md

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | Runtime | Partial | 3.11.9 (system), 3.13.0 (installed) | Use uv to target 3.13.0 via .python-version |
| uv | Package management | Yes | 0.9.7 (installed, stale) | Upgrade recommended: `uv self update` |
| Git | Version control | Yes | 2.51.0 | -- |
| Godot 4.5+ | E2E tests, --check-only | No | Not on PATH | E2E tests skipped via marker; file-only commands work |
| ruff | Linting/formatting | No (not on PATH) | -- | Installed as dev dependency via `uv add --dev ruff` |
| mypy | Type checking | No (not on PATH) | -- | Installed as dev dependency via `uv add --dev mypy` |

**Missing dependencies with no fallback:**
- None blocking (Godot is optional for Phase 1 core work; E2E tests just get skipped)

**Missing dependencies with fallback:**
- uv 0.9.7 is installed but stale (current: 0.11.2). Run `uv self update` before project init.
- Python 3.13.0 is installed locally; uv should pin to it via `.python-version` file.
- ruff and mypy will be installed as dev dependencies within the project virtualenv.

## Open Questions

1. **project.godot multi-line Object() values**
   - What we know: Input maps use `Object(InputEventKey,...)` with many attributes spanning multiple lines inside `{...}` blocks. The bracket-depth approach handles this.
   - What's unclear: Are there other contexts where multi-line values appear outside of `[input]`? Are there values that use unbalanced brackets inside string literals?
   - Recommendation: Start with bracket-depth tracking + string-escape awareness. Add test cases from real Godot projects. The lenient parser (D-04) can fall back to raw string preservation for unrecognized patterns.

2. **Exact .uid file content format**
   - What we know: .uid files contain a single uid:// string, one per line. They are generated for .gd and .gdshader files in Godot 4.4+.
   - What's unclear: Is there a trailing newline? Is there any header or metadata? Are .tres/.tscn files excluded (since they have uid in their header)?
   - Recommendation: Write .uid files as single line + newline. Only generate for file types that don't embed UIDs in their content. Verify against a real Godot 4.5 project if one becomes available.

3. **resource inspect depth for nested sub-resources**
   - What we know: .tres files can have many sub_resource sections with deep nesting of arrays/dicts in the [resource] section.
   - What's unclear: How deep should the JSON representation go? Should sub-resources be inlined or referenced by ID?
   - Recommendation: Inline sub-resource data within the JSON output, referenced by their section ID. This matches D-01's flat model: the JSON mirrors the file structure.

## Sources

### Primary (HIGH confidence)
- [Godot source: resource_uid.cpp](https://github.com/godotengine/godot/blob/master/core/io/resource_uid.cpp) - UID generation algorithm, base-34 encoding, off-by-one bug documentation
- [Godot source: resource_format_text.cpp](https://github.com/godotengine/godot/blob/master/scene/resources/resource_format_text.cpp) - File format parser, resource ID generation
- [DeepWiki: ResourceSaver and Serialization](https://deepwiki.com/godotengine/godot/5.2-resourcesaver-and-serialization) - generate_scene_unique_id() algorithm: 5-char, ASCII identifier chars, RandomPCG seeded
- [Godot TSCN format docs (GitHub)](https://github.com/godotengine/godot-docs/blob/master/engine_details/file_formats/tscn.rst) - Official format specification for .tscn files
- [Godot demo project: project.godot](https://raw.githubusercontent.com/godotengine/godot-demo-projects/master/2d/role_playing_game/project.godot) - Real project.godot file showing format quirks
- [Click changelog](https://click.palletsprojects.com/en/stable/changes/) - Click 8.3.1 confirmed current stable
- [rich-click PyPI](https://pypi.org/project/rich-click/) - v1.9.7, Jan 2026
- [UID changes article](https://godotengine.org/article/uid-changes-coming-to-godot-4-4/) - .uid companion file introduction in Godot 4.4
- [uv releases](https://github.com/astral-sh/uv/releases) - v0.11.2, Mar 2026

### Secondary (MEDIUM confidence)
- [rich-click GitHub](https://github.com/ewels/rich-click) - Drop-in replacement pattern verified
- [Click commands docs](https://click.palletsprojects.com/en/stable/commands-and-groups/) - pass_context, ensure_object, group patterns
- [ResourceUID docs](https://docs.godotengine.org/en/stable/classes/class_resourceuid.html) - UID API documentation

### Tertiary (LOW confidence)
- .uid file content format (single uid:// line) - inferred from community discussions, not officially documented
- Exact project.godot parsing edge cases with Object() constructors - derived from one example file

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All versions verified against PyPI, libraries well-known and stable
- Architecture: HIGH - Patterns derived from official Click docs, CLAUDE.md decisions, and CLI-METHODOLOGY.md
- Parser specification: HIGH - Verified against Godot source code and official demo projects
- UID generation: HIGH - Algorithm extracted directly from Godot C++ source with off-by-one bug documented
- Pitfalls: HIGH - Identified from actual format analysis, not hypothetical
- project.godot parsing: MEDIUM - Based on one example file; edge cases may exist

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable libraries, Godot format unlikely to change within 30 days)
