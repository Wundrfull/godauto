# Phase 4: Scene Commands, Test Suite, and Agent Discoverability - Research

**Researched:** 2026-03-28
**Domain:** Scene file manipulation, E2E testing, CLI introspection, AI agent discoverability
**Confidence:** HIGH

## Summary

Phase 4 completes gdauto with three distinct feature areas: scene commands (list and create), comprehensive E2E testing with golden file validation, and SKILL.md auto-generation. All three areas build on well-established patterns from Phases 1-3 and require no new dependencies.

The scene commands reuse the existing GdScene/SceneNode dataclasses from `formats/tscn.py` and the `_build_tscn_from_model()` serializer. Scene list needs to walk a project directory (pattern established in `project validate`) and parse each .tscn file to extract node trees and cross-scene PackedScene references. Scene create takes JSON input (pattern from `sprite import-aseprite`) describing a node tree and builds a GdScene programmatically, then serializes it.

SKILL.md generation is straightforward: Click's `to_info_dict(ctx)` method returns a complete recursive JSON-serializable dictionary of the entire command tree, including command names, help text, parameter types, defaults, and nesting. A `gdauto skill generate` command walks this structure and renders markdown. The existing CLI already provides all the metadata needed; no additional annotations are required.

E2E tests follow the pattern from `sprite/validator.py` and `tileset/validator.py`: generate a GDScript that loads the resource in headless Godot and prints structured VALIDATION_OK/VALIDATION_FAIL output. Golden file tests commit known-good .tres/.tscn reference outputs and compare generated output after normalizing randomly-generated UIDs and resource IDs.

**Primary recommendation:** Structure the phase into three plans: (1) scene list and scene create commands, (2) SKILL.md generation command, (3) E2E test suite and golden file validation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** JSON file input for scene create. Pass a .json file describing the node tree. Consistent with Aseprite JSON input pattern from Phase 2. Agent-friendly (agents generate JSON easily).
- **D-02:** Full property passthrough. Any property as key-value pairs in JSON, serialized directly to .tscn node properties. Supports every Godot node type without hardcoding property lists.
- **D-03:** No CLI flags for simple trees. JSON-only input keeps the interface consistent and avoids a second code path.
- **D-04:** Full node tree by default. Show complete node hierarchy for each scene. --depth N flag available to limit tree depth for large scenes.
- **D-05:** Comprehensive metadata per scene: file path, root node type, node count, script references, resource dependencies, sub-scene (PackedScene) references.
- **D-06:** Cross-scene dependency graph. Detect PackedScene references across all .tscn files. Show which scenes instance other scenes for full project structure understanding.
- **D-07:** @pytest.mark.requires_godot marker on all E2E tests. Tests skip gracefully when no Godot binary is found. CI installs Godot to run full suite. Local devs without Godot still run all unit tests.
- **D-08:** Validate all resource types in headless Godot: SpriteFrames .tres, TileSet .tres, and .tscn scenes. Full confidence that every generated file loads without modification.
- **D-09:** Committed golden files in tests/fixtures/golden/. Known-good .tres/.tscn reference outputs checked into the repo. Tests compare generated output byte-for-byte (ignoring UIDs). Explicit, reviewable in PRs.
- **D-10:** Auto-generated from Click introspection at runtime. `gdauto skill generate` command walks the Click command tree, extracts all command names, arguments, options, help text. Always in sync with CLI.
- **D-11:** One usage example per command in SKILL.md. Agents can copy-paste concrete examples. More useful for agent workflows than signatures alone.

### Claude's Discretion
- SKILL.md format (structured markdown vs YAML blocks): pick what works best for LLM consumption
- External resource reference support in scene create: pick based on existing parser capabilities (res:// paths, ext_resource generation)
- Scene JSON schema details: node tree structure, property naming convention, how children are expressed
- E2E test fixture design: which specific resources to generate and validate
- Golden file comparison logic: how to normalize UIDs and timestamps for stable comparison
- scene list human output format: tree rendering style (indentation, connectors, colors)

### Deferred Ideas (OUT OF SCOPE)
None. Discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCEN-01 | `gdauto scene list` enumerates all scenes in a project, dumps node trees, shows dependencies between scenes and scripts | GdScene parser (tscn.py) exists; project directory walking pattern from project validate; SceneNode has instance attr for PackedScene detection |
| SCEN-02 | `gdauto scene create` creates .tscn scene files from JSON node tree definitions with node hierarchy, property assignments, script references | GdScene + SceneNode dataclasses + `_build_tscn_from_model()` serializer exist; JSON input pattern from sprite import-aseprite; values.py handles all Godot property types |
| CLI-06 | SKILL.md auto-generated from CLI command tree (names, arguments, options, help text) | Click's `to_info_dict(ctx)` provides complete recursive command tree as JSON; verified on actual gdauto CLI |
| TEST-02 | E2E tests marked with @pytest.mark.requires_godot that load generated .tres/.tscn in headless Godot | Marker already configured in pyproject.toml; validator pattern from sprite/validator.py and tileset/validator.py provides GDScript template |
| TEST-03 | Validation tests that verify peering bit assignments match expected patterns for all supported layouts | Existing unit tests in test_tileset_terrain.py cover peering bits; E2E validates via headless Godot load |
| TEST-04 | Generated .tres/.tscn files validated against known-good reference outputs | Golden file approach: generate, normalize UIDs, compare to committed reference files in tests/fixtures/golden/ |
</phase_requirements>

## Standard Stack

No new dependencies. Phase 4 uses only libraries already in the project.

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Click | 8.3.1 | CLI framework, command introspection | Already installed; `to_info_dict()` and `list_commands()`/`get_command()` provide complete tree traversal for SKILL.md generation |
| rich-click | 1.9.7 | CLI help formatting | Already installed; rich_click commands expose same Click introspection API (RichArgument, RichOption inherit from Click base) |
| Rich | 14.3.3 | Tree rendering for scene list | Already installed (transitive via rich-click); `rich.tree.Tree` for human-readable node hierarchy display |
| pytest | 9.0.2 | Test framework | Already in dev dependencies; `@pytest.mark.requires_godot` marker already configured in pyproject.toml |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json (stdlib) | stdlib | Scene definition input, SKILL.md example generation | Scene create reads JSON definitions; SKILL.md --json output |
| re (stdlib) | stdlib | UID normalization in golden file comparison | Strip uid://, resource IDs for deterministic comparison |
| pathlib (stdlib) | stdlib | Project directory walking for scene list | rglob("*.tscn") pattern from project validate |
| tempfile (stdlib) | stdlib | E2E test GDScript generation | Pattern from sprite/validator.py headless validation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| rich.tree.Tree for scene list | Plain indentation | Rich Tree gives connectors and colors for free; already a transitive dependency |
| JSON for scene definitions | YAML | D-01 locks JSON; consistent with Aseprite JSON input; no PyYAML dependency needed |
| Byte-for-byte golden comparison | AST comparison | Byte comparison after UID normalization is simpler and catches serialization regressions |

## Architecture Patterns

### Recommended Project Structure (new files)
```
src/gdauto/
  scene/
    __init__.py          # Empty or re-exports
    builder.py           # build_scene() from JSON definition -> GdScene
    lister.py            # walk project, parse scenes, build dependency graph
  skill/
    __init__.py          # Empty or re-exports
    generator.py         # walk Click tree -> SKILL.md markdown
  commands/
    scene.py             # scene list, scene create subcommands (modify existing stub)
    skill.py             # skill generate command (new)
tests/
  unit/
    test_scene_builder.py
    test_scene_list.py
    test_skill_generator.py
  e2e/
    __init__.py          # New directory
    conftest.py          # @pytest.mark.requires_godot auto-skip fixture
    test_e2e_spriteframes.py
    test_e2e_tileset.py
    test_e2e_scene.py
  fixtures/
    golden/
      spriteframes_simple.tres   # Known-good reference output
      tileset_basic.tres         # Known-good reference output
      scene_basic.tscn           # Known-good reference output
    scene_definition.json        # Test input for scene create
```

### Pattern 1: Scene Builder (JSON -> GdScene)
**What:** Reads a JSON definition file and constructs a GdScene dataclass with SceneNodes, ExtResources, and SubResources
**When to use:** `gdauto scene create` command
**Example:**
```python
# Source: Follows tileset/builder.py pattern
from gdauto.formats.tscn import GdScene, SceneNode, serialize_tscn_file
from gdauto.formats.tres import ExtResource
from gdauto.formats.uid import generate_uid, uid_to_text
from gdauto.formats.values import parse_value

def build_scene(definition: dict) -> GdScene:
    """Build a GdScene from a JSON definition dict."""
    nodes = _build_nodes(definition["root"])
    ext_resources = _build_ext_resources(definition.get("resources", []))
    load_steps = len(ext_resources) + 1  # ext_resources + self

    return GdScene(
        format=3,
        uid=uid_to_text(generate_uid()),
        load_steps=load_steps if ext_resources else None,
        ext_resources=ext_resources,
        sub_resources=[],
        nodes=nodes,
        connections=[],
    )
```

### Pattern 2: Scene JSON Definition Schema
**What:** The JSON structure that scene create accepts
**When to use:** Input for `gdauto scene create`
```json
{
  "root": {
    "name": "Player",
    "type": "CharacterBody2D",
    "properties": {
      "position": "Vector2(100, 200)"
    },
    "children": [
      {
        "name": "Sprite",
        "type": "Sprite2D",
        "properties": {
          "position": "Vector2(0, 0)"
        }
      },
      {
        "name": "CollisionShape",
        "type": "CollisionShape2D"
      }
    ]
  },
  "resources": [
    {
      "type": "Script",
      "path": "res://scripts/player.gd",
      "assign_to": "Player",
      "property": "script"
    }
  ]
}
```

**Key design decisions for JSON schema (Claude's Discretion):**
- `children` array for hierarchy (natural tree structure in JSON)
- Properties as string values matching Godot serialization format (parsed via `parse_value()`)
- External resources listed separately with `assign_to` mapping to node name
- Node `parent` path computed automatically from tree position during flattening

### Pattern 3: Scene Lister (Project Directory -> Dependency Graph)
**What:** Walk all .tscn files in a project directory, parse each, and build a dependency graph
**When to use:** `gdauto scene list` command
```python
# Source: Follows project validate directory walking pattern
from gdauto.formats.tscn import parse_tscn_file, GdScene, SceneNode

def list_scenes(project_root: Path) -> list[dict]:
    """Walk project directory and enumerate all .tscn scenes."""
    scenes = []
    for tscn_path in project_root.rglob("*.tscn"):
        scene = parse_tscn_file(tscn_path)
        scenes.append(_summarize_scene(tscn_path, scene, project_root))
    return scenes

def _summarize_scene(path: Path, scene: GdScene, root: Path) -> dict:
    """Extract metadata from a parsed scene."""
    # Instance references: nodes with instance attr set
    instances = [
        node for node in scene.nodes if node.instance is not None
    ]
    # Script references: ext_resources with type="Script"
    scripts = [
        ext for ext in scene.ext_resources if ext.type == "Script"
    ]
    return {
        "path": str(path.relative_to(root)),
        "root_type": scene.nodes[0].type if scene.nodes else None,
        "node_count": len(scene.nodes),
        "scripts": [s.path for s in scripts],
        "instances": [_resolve_instance(inst, scene) for inst in instances],
    }
```

### Pattern 4: Click Introspection for SKILL.md
**What:** Use `to_info_dict()` to get complete CLI tree and render as markdown
**When to use:** `gdauto skill generate` command
```python
# Verified by running on actual gdauto CLI
import click
from gdauto.cli import cli

def generate_skill_md() -> str:
    """Generate SKILL.md content from Click command tree."""
    ctx = click.Context(cli, info_name="gdauto")
    info = cli.to_info_dict(ctx)
    return _render_skill(info)

def _render_skill(info: dict) -> str:
    """Render a Click info dict as SKILL.md markdown."""
    lines = ["# gdauto", "", info.get("help", ""), ""]
    lines.append("## Commands")
    lines.append("")
    _render_commands(info, "gdauto", lines)
    return "\n".join(lines)
```

**Key finding:** `to_info_dict(ctx)` returns a dict with keys: `name`, `params`, `help`, `epilog`, `short_help`, `hidden`, `deprecated`, `commands` (recursive), `chain`. Each param has: `name`, `param_type_name` (argument/option), `opts` (flag names), `type` (with `name` subfield), `required`, `default`, `help`, `is_flag`, `multiple`, `nargs`. This is everything needed for SKILL.md generation.

### Pattern 5: Golden File Comparison
**What:** Normalize UIDs and resource IDs in generated output, then compare to committed reference
**When to use:** TEST-04 golden file tests
```python
import re

_UID_RE = re.compile(r'uid://[a-y0-8]+')
_RESOURCE_ID_RE = re.compile(r'(\w+)_[a-zA-Z0-9_]{5}')

def normalize_for_comparison(text: str) -> str:
    """Strip randomly-generated UIDs and resource IDs for stable comparison."""
    text = _UID_RE.sub('uid://NORMALIZED', text)
    text = _RESOURCE_ID_RE.sub(r'\1_XXXXX', text)
    return text
```

### Pattern 6: E2E Test with Headless Godot
**What:** Generate a resource, write it to disk, load it in headless Godot via GDScript
**When to use:** TEST-02 E2E validation
```python
# Source: Follows sprite/validator.py and tileset/validator.py patterns
@pytest.mark.requires_godot
def test_spriteframes_loads_in_godot(tmp_path, godot_backend):
    """Generate a SpriteFrames and validate it loads in headless Godot."""
    # 1. Generate the resource using existing builder
    # 2. Write to tmp_path
    # 3. Create GDScript that loads and validates
    # 4. Run via godot_backend.run(["--script", script_path])
    # 5. Parse stdout for VALIDATION_OK
```

### Anti-Patterns to Avoid
- **Hardcoding node types in scene create:** D-02 mandates full property passthrough. Do not maintain an allowlist of Godot node types or properties. Accept any type string and any property key-value pairs.
- **Parsing scene files with regex:** Use the existing `parse_tscn_file()` parser. It handles all edge cases (nested values, multi-line properties, quoted strings).
- **Manual SKILL.md maintenance:** D-10 mandates auto-generation from Click introspection. Never hand-edit SKILL.md; always regenerate.
- **Hardcoded golden file paths:** Use `Path(__file__).parent.parent / "fixtures" / "golden"` relative to test file, matching existing FIXTURES pattern in test_tscn_parser.py.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Node tree rendering | Custom ASCII tree drawing | `rich.tree.Tree` | Rich is already a dependency; Tree handles indentation, connectors, Unicode box-drawing characters, and color |
| CLI command tree traversal | Manual Click Group recursion | `cli.to_info_dict(ctx)` | Returns complete recursive dict with all metadata; verified to include params, help, commands, etc. |
| .tscn parsing | Regex-based scene parser | `parse_tscn_file()` from formats/tscn.py | Already handles all Godot 4.x format=3 features; round-trip tested |
| .tscn generation | String template concatenation | `_build_tscn_from_model()` from formats/tscn.py | Already handles header, ext_resources, sub_resources, nodes, connections; correct formatting |
| UID generation | Custom random ID generation | `generate_uid()`, `uid_to_text()` from formats/uid.py | Matches Godot's base-34 encoding algorithm exactly |
| Resource ID generation | Manual random strings | `generate_resource_id()` from formats/uid.py | Matches Godot's Type_xxxxx format |
| Property value serialization | Custom value formatting | `serialize_value()` from formats/values.py | Handles all Godot types (Vector2, Rect2, Color, arrays, dicts, etc.) |
| Property value parsing | Custom value parsing | `parse_value()` from formats/values.py | Already handles all Godot constructor syntax |

**Key insight:** Phase 4 is heavily a composition phase. Nearly all building blocks exist from Phases 1-3. The scene builder assembles existing dataclasses and serializers. The scene lister wraps existing parsers with directory walking. SKILL.md generation wraps Click's built-in introspection. E2E tests reuse the GDScript validation pattern from both validators.

## Common Pitfalls

### Pitfall 1: Node Parent Path Computation in Scene Create
**What goes wrong:** The JSON definition uses a nested `children` array, but .tscn format uses flat `parent` path strings (`.` for root children, `Parent/Child` for deeper nesting). Getting parent path computation wrong produces invalid scenes.
**Why it happens:** The tree-to-flat conversion requires tracking the path from root to each node.
**How to avoid:** Build the parent path during recursive tree traversal. Root node has `parent=None`. Direct children of root have `parent="."`. Deeper children use `parent="ParentName"` or `parent="ParentName/ChildName"` etc. Test with 3+ levels of nesting.
**Warning signs:** Godot fails to load the scene, or nodes appear at wrong positions in the tree.

### Pitfall 2: SceneNode Instance Attribute Detection
**What goes wrong:** Scene list fails to detect PackedScene instances because the `instance` attribute on SceneNode is an `ExtResource("id")` string reference, not a direct path.
**Why it happens:** The instance attribute in .tscn is `instance=ExtResource("1_abc")`, which the parser stores as a raw string value. To resolve the actual scene path, you must look up the corresponding ext_resource by ID.
**How to avoid:** When a node has `instance` set, parse the ExtResource reference, look up the ext_resource with that ID, and use its `path` field for the dependency graph.
**Warning signs:** Dependency graph shows ExtResource IDs instead of scene paths.

### Pitfall 3: Golden File UID Normalization Regex
**What goes wrong:** The UID normalization regex is too broad or too narrow, causing either false matches (normalizing non-UID strings) or missed matches (leaving random UIDs in comparison).
**Why it happens:** UIDs use base-34 charset (a-y, 0-8), and resource IDs use alphanumeric + underscore with exactly 5 chars. These patterns can overlap with property values.
**How to avoid:** Use anchored patterns: UIDs always follow `uid="uid://..."` in headers or `uid://...` standalone. Resource IDs always follow `id="Type_xxxxx"` format with known type prefixes. Normalize at the header attribute level, not via blind text replacement.
**Warning signs:** Golden file tests fail intermittently, or pass when they should detect regressions.

### Pitfall 4: Click Context Creation for Introspection
**What goes wrong:** Creating a Click Context outside of an actual CLI invocation can fail if commands expect `ctx.obj` to be populated (GlobalConfig).
**Why it happens:** The `gdauto skill generate` command runs inside a normal CLI invocation, so `ctx.obj` exists. But if testing the generator directly, `ctx.obj` may be None.
**How to avoid:** Create the introspection context separately: `ctx = click.Context(cli, info_name="gdauto")`. Do not rely on the current invocation context for introspection. The `to_info_dict()` method does not execute callbacks; it only reads metadata.
**Warning signs:** AttributeError on ctx.obj when running `to_info_dict()`.

### Pitfall 5: E2E Test Godot Skip Logic
**What goes wrong:** E2E tests fail in CI or on dev machines where Godot is not installed, instead of skipping gracefully.
**Why it happens:** The `@pytest.mark.requires_godot` marker only marks the test; it does not automatically skip. You need a conftest.py that maps the marker to actual skip logic.
**How to avoid:** Create `tests/e2e/conftest.py` with an autouse fixture or a `pytest_collection_modifyitems` hook that adds `pytest.mark.skipif(not shutil.which("godot"), reason="Godot not on PATH")` to tests marked `requires_godot`.
**Warning signs:** Test suite errors (not skips) when Godot is absent.

### Pitfall 6: Rich Tree Import Path
**What goes wrong:** Importing `from rich.tree import Tree` when Rich is only a transitive dependency via rich-click.
**Why it happens:** Rich is not listed as a direct dependency in pyproject.toml; it comes via rich-click.
**How to avoid:** This is safe because rich-click directly depends on rich, and we already use `from rich.console import Console` and `from rich.table import Table` in project commands. Rich is effectively a guaranteed transitive dependency.
**Warning signs:** None expected; this is safe.

## Code Examples

### Example 1: Scene JSON Definition (Input Format)
```json
{
  "root": {
    "name": "Level",
    "type": "Node2D",
    "children": [
      {
        "name": "Player",
        "type": "CharacterBody2D",
        "properties": {
          "position": "Vector2(100, 200)"
        },
        "children": [
          {
            "name": "Sprite",
            "type": "Sprite2D",
            "properties": {
              "position": "Vector2(0, 0)"
            }
          },
          {
            "name": "CollisionShape",
            "type": "CollisionShape2D"
          }
        ]
      },
      {
        "name": "TileMap",
        "type": "TileMapLayer"
      }
    ]
  },
  "resources": [
    {
      "type": "Script",
      "path": "res://scripts/player.gd",
      "assign_to": "Player",
      "property": "script"
    }
  ]
}
```

### Example 2: Expected .tscn Output (from above input)
```
[gd_scene load_steps=2 format=3 uid="uid://abc123"]

[ext_resource type="Script" uid="uid://def456" path="res://scripts/player.gd" id="Script_abc12"]

[node name="Level" type="Node2D"]

[node name="Player" type="CharacterBody2D" parent="."]
script = ExtResource("Script_abc12")
position = Vector2(100, 200)

[node name="Sprite" type="Sprite2D" parent="Player"]
position = Vector2(0, 0)

[node name="CollisionShape" type="CollisionShape2D" parent="Player"]

[node name="TileMap" type="TileMapLayer" parent="."]
```

### Example 3: SKILL.md Output Format (Claude's Discretion: Structured Markdown)
```markdown
# gdauto

Agent-native CLI for Godot Engine.

## Global Options

- `--json` / `-j`: Output as JSON
- `--verbose` / `-v`: Show extra detail
- `--quiet` / `-q`: Suppress all output except errors
- `--godot-path PATH`: Path to Godot binary

## Commands

### gdauto project info [PATH]
Show project metadata (name, version, autoloads, settings).

**Arguments:**
- `PATH` (optional, default: `.`): Project directory or project.godot path

**Example:**
```
gdauto project info ./my-game
gdauto project info --json
```

### gdauto sprite import-aseprite JSON_FILE
Convert Aseprite JSON export to Godot SpriteFrames .tres resource.

**Arguments:**
- `JSON_FILE` (required): Path to Aseprite JSON metadata file

**Options:**
- `-o, --output PATH`: Output .tres path (default: replaces .json with .tres)
- `--res-path TEXT`: Godot res:// path for the sprite sheet texture

**Example:**
```
gdauto sprite import-aseprite character.json
gdauto sprite import-aseprite character.json -o sprites/character.tres
```
```

**Rationale for structured markdown over YAML blocks:** LLMs consume markdown natively with higher fidelity than YAML. Markdown sections with headers, bold labels, and code blocks are the most reliable format for agent tool discovery. YAML would require parsing, while markdown is directly readable.

### Example 4: conftest.py for E2E Tests
```python
# Source: follows @pytest.mark.requires_godot convention from D-07
import shutil
import pytest

def pytest_collection_modifyitems(config, items):
    """Auto-skip tests marked requires_godot when Godot is absent."""
    if shutil.which("godot"):
        return  # Godot available; run all tests
    skip_godot = pytest.mark.skip(reason="Godot binary not found on PATH")
    for item in items:
        if "requires_godot" in item.keywords:
            item.add_marker(skip_godot)
```

### Example 5: E2E Scene Validation GDScript
```gdscript
extends SceneTree

func _init() -> void:
    var scene = load("SCENE_PATH")
    if scene == null:
        print("VALIDATION_FAIL: Could not load scene")
        quit(1)
    var instance = scene.instantiate()
    if instance == null:
        print("VALIDATION_FAIL: Could not instantiate scene")
        quit(1)
    print("VALIDATION_OK: nodes=" + str(_count_nodes(instance)))
    instance.queue_free()
    quit(0)

func _count_nodes(node: Node) -> int:
    var count = 1
    for child in node.get_children():
        count += _count_nodes(child)
    return count
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `load_steps` in gd_scene header | Deprecated in Godot 4.6+ (still accepted) | Godot 4.6 | Include it for backward compatibility but do not require it; the parser already handles optional load_steps |
| `unique_id` on nodes | Added in Godot 4.6+ for stable node identification | Godot 4.6 | Scene create does not need to generate unique_id (Godot adds it on first editor save); scene list should display it if present |
| `to_info_dict()` on Click commands | Available in Click 8.x | Click 8.0 | Replaces manual command tree walking; provides complete recursive metadata |

## Project Constraints (from CLAUDE.md)

- **Tech stack**: Python 3.12+, Click >= 8.0, pytest >= 7.0
- **Engine compatibility**: Godot 4.5+ binary on PATH (for E2E tests and headless commands only)
- **Independence**: No Godot dependency for file manipulation commands (scene list and scene create must work without Godot)
- **Error contract**: All errors produce non-zero exit codes and actionable messages; --json errors produce `{"error": "message", "code": "ERROR_CODE"}`
- **File validity**: Generated .tscn files must be loadable by Godot without modification
- **Code style**: No em dashes, no emojis, type hints on all signatures, docstrings on public functions, functions under 30 lines, comments on non-obvious logic only

## Open Questions

1. **How to handle ext_resource references in the scene JSON definition?**
   - What we know: D-02 mandates full property passthrough. The existing parser handles `ExtResource("id")` as a value type (`ExtResourceRef`). The `resources` array in the JSON definition maps external resources to nodes.
   - What's unclear: Should the JSON definition allow inline `ExtResource()` strings in property values (and have the builder parse them), or should resources always be declared in the top-level `resources` array?
   - Recommendation: Support both. Top-level `resources` array for explicit ext_resource declarations with node assignment. Also support `ExtResource()` syntax in property value strings, which `parse_value()` already handles. This gives agents maximum flexibility.

2. **What happens with scene create and resource IDs being random?**
   - What we know: `generate_resource_id()` uses CSPRNG, producing different IDs each run. This is correct behavior for Godot (IDs just need to be unique within a file).
   - What's unclear: Should scene create support user-provided resource IDs for deterministic output?
   - Recommendation: No. Random IDs match Godot's own behavior. Golden file tests normalize IDs anyway. Deterministic IDs would add complexity with no user benefit.

3. **Where should the `skill` command group live?**
   - What we know: D-10 specifies `gdauto skill generate` as the command.
   - What's unclear: Should `skill` be a command group (allowing future subcommands) or a simple command?
   - Recommendation: Make it a command group with `generate` as the first subcommand. Future subcommands (e.g., `skill validate`, `skill diff`) could be added without breaking the CLI interface.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All code | Yes | 3.12+ | -- |
| Click | CLI, SKILL.md generation | Yes | 8.3.1 | -- |
| rich-click | CLI rendering | Yes | 1.9.7 | -- |
| Rich (transitive) | Scene list tree display | Yes | 14.3.3 | -- |
| pytest | Test suite | Yes | 9.0.2 | -- |
| Godot | E2E tests only | No | -- | Tests skip via @pytest.mark.requires_godot; all unit tests run without it |

**Missing dependencies with no fallback:**
- None. All core dependencies are available.

**Missing dependencies with fallback:**
- Godot binary: Not on PATH. E2E tests will skip gracefully (D-07). Scene commands (list, create) do not require Godot.

## Sources

### Primary (HIGH confidence)
- Click 8.3.1 `to_info_dict()` API: Verified by running on actual gdauto CLI; returns recursive dict with `name`, `params`, `help`, `commands`, `short_help`, `hidden`, `deprecated` keys
- Click `list_commands()` and `get_command()` API: Verified by running on actual gdauto CLI; successfully enumerates all 7 command groups and 20+ subcommands
- Godot .tscn format specification: From [godot-docs/engine_details/file_formats/tscn.rst](https://github.com/godotengine/godot-docs/blob/master/engine_details/file_formats/tscn.rst); node attributes: name, type, parent, instance, owner, unique_id, groups
- Existing codebase: `formats/tscn.py` (GdScene, SceneNode, parse_tscn, serialize_tscn), `formats/tres.py` (GdResource, ExtResource, SubResource), `formats/values.py` (parse_value, serialize_value), `formats/uid.py` (generate_uid, generate_resource_id)
- Existing validators: `sprite/validator.py`, `tileset/validator.py` (GDScript generation + headless validation pattern)
- pyproject.toml: `requires_godot` marker already configured; pytest 9.0.2, Click 8.3.1 confirmed

### Secondary (MEDIUM confidence)
- [Click Help Pages documentation](https://click.palletsprojects.com/en/stable/documentation/) -- Cloudflare blocked; relied on direct API testing instead
- [TSCN File Format documentation](https://docs.godotengine.org/en/4.4/contributing/development/file_formats/tscn.html) -- Cloudflare blocked; used GitHub RST source
- [Click Advanced Groups](https://click.palletsprojects.com/en/stable/commands/) -- list_commands/get_command pattern
- [Click command introspection DEV article](https://dev.to/rodrigo_estrada_79e6022e9/how-to-build-an-interactive-chat-for-your-python-cli-using-introspection-click-and-rich-formatting-4l9a)

### Tertiary (LOW confidence)
- None. All findings verified against actual codebase or official sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies; all verified installed and working
- Architecture: HIGH -- all patterns follow existing codebase conventions (builder pattern from tileset, JSON input from sprite, directory walking from project validate, validation from sprite/tileset validators)
- Pitfalls: HIGH -- based on analysis of actual code (SceneNode.instance attribute behavior, Click context creation, pytest marker mechanics)
- SKILL.md generation: HIGH -- `to_info_dict()` verified by running on actual gdauto CLI; complete recursive output confirmed

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stable; no fast-moving dependencies)
