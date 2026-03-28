# CLI Generation Methodology for gdauto

This document captures the best architectural patterns and engineering standards from CLI-Anything's HARNESS.md methodology. It serves as a reference skill for GSD subagents building gdauto. Every CLI command, module, and test should follow these patterns.

## Core Architecture

### Namespace Package Structure

gdauto is a PEP 420 namespace package. This means it can coexist with other CLI tools in the same namespace without conflicts.

```
gdauto/
  setup.py
  gdauto/
    __init__.py          # Package version, metadata
    cli.py               # Click entry point, command group registration
    godot_backend.py     # Subprocess wrapper for the Godot binary
    project.py           # Project management commands
    export.py            # Build and export pipeline
    scene.py             # Scene and resource manipulation
    sprite.py            # Sprite/SpriteFrames commands (Aseprite bridge)
    tileset.py           # TileSet/TileMap automation
    session.py           # Undo/redo state management
    formats/
      tscn.py            # .tscn (scene) file parser and generator
      tres.py            # .tres (resource) file parser and generator
      aseprite.py        # Aseprite JSON metadata parser
  tests/
    unit/                # Synthetic data tests, no Godot binary needed
    e2e/                 # Real Godot invocation tests
    fixtures/            # Test assets (sample .ase exports, tilesets, scenes)
  SKILL.md               # AI agent discoverability document
  TEST.md                # Test plan and results
```

### Click CLI Entry Point

The main CLI uses Click >= 8.0 with `invoke_without_command=True`. When called without a subcommand, it prints help. Every command group is registered as a Click group.

```python
import click

@click.group(invoke_without_command=True)
@click.version_option()
@click.pass_context
def cli(ctx):
    """gdauto: Agent-native CLI for Godot Engine."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

@cli.group()
def project():
    """Manage Godot projects."""
    pass

@cli.group()
def sprite():
    """Sprite and animation tools."""
    pass

@cli.group()
def tileset():
    """TileSet and TileMap automation."""
    pass

@cli.group()
def export():
    """Build and export pipeline."""
    pass
```

### The --json Flag (Non-Negotiable)

Every single command must support a `--json` flag that switches output from human-readable to structured JSON. This is what makes the CLI agent-native. AI agents parse JSON; humans read tables.

```python
@project.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.argument("path", default=".")
def info(path, as_json):
    """Show project metadata."""
    data = read_project_godot(path)
    if as_json:
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(f"Project: {data['name']}")
        click.echo(f"Godot version: {data['config_version']}")
```

### Backend Wrapper Pattern

All Godot invocations go through a single backend module. Never call subprocess directly from command handlers. The backend handles binary discovery, timeout management, error parsing, and structured output.

```python
# godot_backend.py
import subprocess
import shutil

class GodotBackend:
    def __init__(self, binary=None, timeout=120):
        self.binary = binary or shutil.which("godot")
        self.timeout = timeout
        if not self.binary:
            raise FileNotFoundError(
                "Godot binary not found on PATH. "
                "Install Godot 4.5+ and add it to your PATH."
            )

    def run(self, args, project_path=None, capture=True):
        """Run a Godot command and return the result."""
        cmd = [self.binary, "--headless"] + args
        if project_path:
            cmd.extend(["--path", str(project_path)])

        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=self.timeout,
        )

        if result.returncode != 0:
            raise GodotError(
                f"Godot exited with code {result.returncode}",
                stdout=result.stdout,
                stderr=result.stderr,
            )
        return result

    def run_script(self, script_path, project_path=None):
        """Run a GDScript file headlessly."""
        return self.run(["--script", str(script_path)], project_path)

    def export_release(self, preset, output_path, project_path=None):
        """Export a project using a named preset."""
        return self.run(
            ["--export-release", preset, str(output_path)],
            project_path,
        )

    def import_resources(self, project_path=None):
        """Force re-import of all project resources."""
        return self.run(["--import"], project_path)
```

### Direct File Manipulation for .tscn and .tres

Many operations do not need Godot running at all. Godot's scene (.tscn) and resource (.tres) files are text-based and parseable. The CLI should directly read and write these files when possible, only invoking Godot headlessly when the engine runtime is actually needed (export, import, running scripts).

The file format uses bracketed sections:
```
[gd_resource type="SpriteFrames" format=3]

[sub_resource type="AtlasTexture" id="AtlasTexture_abc12"]
atlas = ExtResource("1_sheet")
region = Rect2(0, 0, 32, 32)

[resource]
animations = [{
"frames": [{
"duration": 1.0,
"texture": SubResource("AtlasTexture_abc12")
}],
"loop": true,
"name": &"idle",
"speed": 8.0
}]
```

Build a parser/generator module for this format. Do not use regex for the full parse; use a proper state machine that handles nested structures.

### Test Strategy

Tests are split into two tiers:

**Unit tests** (tests/unit/): No Godot binary required. Test file parsing, JSON generation, Aseprite metadata conversion, tileset terrain bit calculation, and all pure Python logic. These must run in CI without any special setup.

**End-to-end tests** (tests/e2e/): Require Godot on PATH. Test actual exports, imports, script execution, and resource generation through the real backend. Mark these with `@pytest.mark.requires_godot` so they can be skipped in environments without Godot.

Every command must have at least one unit test and one E2E test. Test output validation should check:
- Exit codes (0 for success, non-zero for failure)
- JSON output is valid and contains expected keys
- Generated .tres/.tscn files are valid (can be loaded by Godot)
- File magic bytes for binary outputs (PNG headers, ZIP structure for .pck files)

### Error Handling Standards

- All errors must produce a non-zero exit code
- Error messages must be human-readable on stderr
- With --json, errors must produce a JSON object: `{"error": "message", "code": "ERROR_CODE"}`
- Never silently swallow errors
- Include actionable fix suggestions (e.g., "Godot binary not found. Install from https://godotengine.org/download/")

### SKILL.md for AI Discoverability

After building the CLI, generate a SKILL.md file that describes every command, its flags, expected inputs, and example usage. This file is what AI agents read to learn how to use gdauto. Format:

```markdown
# gdauto

Agent-native CLI for Godot Engine.

## Commands

### gdauto project info [PATH]
Show project metadata.
- `--json`: Output as JSON

### gdauto sprite import-aseprite --input FILE --sheet IMAGE
Convert Aseprite export to Godot SpriteFrames.
- `--input`: Path to Aseprite JSON metadata file
- `--sheet`: Path to sprite sheet image
- `--output`: Output .tres file path (default: derives from input name)
- `--json`: Output as JSON
```

## Code Style

- No em dashes in any written content (comments, docs, strings). Use commas, colons, semicolons, or parentheses.
- No emojis in code or docs unless explicitly requested.
- Simple, readable code on first pass. Descriptive variable names. Comments on non-obvious logic.
- Type hints on all function signatures.
- Docstrings on all public functions.
- Max function length: aim for under 30 lines. Extract helpers when functions grow.
- Import ordering: stdlib, third-party, local (enforced by isort conventions).
