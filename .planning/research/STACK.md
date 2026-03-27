# Technology Stack

**Project:** gdauto
**Researched:** 2026-03-27
**Overall confidence:** HIGH

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Python | >= 3.12 | Runtime | 3.12 added improved type hints (PEP 695), f-string improvements, 15% perf boost over 3.11. 3.13 added 3x faster dataclass creation. Floor at 3.12 because Click 8.3 dropped 3.9 support anyway, and we get modern typing syntax (type aliases, generics) for free. Ceiling: don't require 3.14 yet (beta). | HIGH |
| Click | 8.3.x | CLI framework | PROJECT.md mandates Click. 8.3.0 (Sep 2025) is current stable, requires Python 3.10+. Battle-tested with 38.7% of Python CLI projects. Supports command groups, pass_context, invoke_without_command, and `--json` flag patterns from CLI-METHODOLOGY.md. | HIGH |
| rich-click | 1.9.x | CLI help formatting | Drop-in Click replacement (`import rich_click as click`) for beautiful help output. Zero code change for existing Click commands. Adds color, tables, grouped options in `--help`. v1.9.7 (Jan 2026) added 100+ themes. Agents ignore formatting; humans appreciate it. | HIGH |

### File Format Parsing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Custom parser (built in-house) | n/a | .tscn/.tres parsing and generation | stevearc/godot_parser (0.1.7) is the only Python option but has critical problems: inactive maintenance, open issue about Godot 4 support (#9), whitespace fidelity issues (#14), performance problems with large files (#4), and a pyparsing dependency that adds weight without matching our exact needs. The Godot text format is well-specified and relatively simple (bracket sections, key=value pairs, nested GDScript-like literals). A hand-rolled recursive descent or state machine parser (as specified in CLI-METHODOLOGY.md) gives us full control over format=3 compatibility, round-trip fidelity, and performance. ~500-800 lines of Python. | HIGH |
| configparser (stdlib) | stdlib | project.godot parsing | project.godot is INI-style. Python's configparser handles it natively with no dependencies. Small quirks (Godot uses `config_version=5` headers and bracket-less global section) are easily handled with `read_string()` and a prepended `[DEFAULT]` section. No reason to add a dependency for this. | HIGH |
| json (stdlib) | stdlib | Aseprite JSON metadata, --json output | Aseprite exports JSON via `aseprite -b --data`. Python's built-in json module parses it. No third-party JSON library needed (orjson is overkill for <1MB metadata files). Also used for all --json CLI output. | HIGH |

### Data Modeling

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| dataclasses (stdlib) | stdlib | Internal data models | Godot file structures (GdResource, GdScene, SubResource, ExtResource, Node, animations, terrain sets) are internal data that has already been validated by the parser. Dataclasses are 6x faster to instantiate than Pydantic models. No external dependency. Type hints provide IDE support. Python 3.13 improved dataclass creation 3x. | HIGH |
| Pydantic | NOT USED | -- | Pydantic (v2.12.5 current) adds validation overhead we don't need at internal boundaries. Our validation happens at the parser level and at CLI input (Click handles argument validation). Adding a 2MB+ dependency for internal models is wasteful. Reserve Pydantic for API-edge projects. | HIGH |

### Image Processing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Pillow | 12.1.x | Sprite sheet operations | Needed for `sprite create-atlas` (compositing multiple images into atlas textures) and `sprite split` (slicing sprite sheets). 12.1.1 (Feb 2026) is current. Supports PNG, WebP, and all formats Godot imports. Note: Pillow is NOT needed for the core `sprite import-aseprite` command (that reads JSON metadata and writes .tres text; no pixel manipulation). Only required for atlas creation and sheet splitting. Mark as optional dependency. | HIGH |

### Testing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| pytest | 9.0.x | Test runner | PROJECT.md mandates pytest >= 7.0. Current stable is 9.0.2. Supports markers (`@pytest.mark.requires_godot` for E2E tests), fixtures, parametrize, and native TOML config in pyproject.toml. | HIGH |
| pytest-cov | 7.1.x | Coverage reporting | Standard coverage plugin. Reports which parser paths and CLI branches are exercised. | MEDIUM |

### Code Quality

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| ruff | latest (0.11.x) | Linting + formatting | Replaces flake8, black, isort, pyupgrade in a single Rust-powered tool. 10-100x faster than alternatives. Runs in <1s on projects this size. Configure in pyproject.toml. | HIGH |
| mypy | 1.19.x | Static type checking | Catches type errors in parser logic, data model usage, and CLI handlers. All function signatures have type hints per CLI-METHODOLOGY.md. Strict mode catches issues before runtime. | HIGH |

### Project Management

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| uv | 0.11.x | Package and project management | 10-100x faster than pip. Manages virtualenvs, dependencies, lock files, and Python versions. Uses pyproject.toml natively. Generates uv.lock for reproducible installs. Modern standard for new Python projects in 2026. | HIGH |
| pyproject.toml | PEP 621 | Project metadata and tool config | Single file for project metadata, dependencies, Click entry points, pytest config, ruff config, mypy config. No setup.py, setup.cfg, or requirements.txt needed. | HIGH |

### Build and Distribution

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| hatchling | latest | Build backend | Modern, fast build backend. Works with uv and pyproject.toml. Supports version management via hatch-vcs. Preferred over setuptools for new projects. | MEDIUM |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| CLI framework | Click 8.3 | Typer | PROJECT.md already specifies Click. Typer wraps Click anyway. Click gives more explicit control over command groups, pass_context patterns, and --json flag implementation. Typer's type-hint-based approach is elegant but less transparent for the complex subcommand structure gdauto needs. |
| CLI framework | Click 8.3 | argparse | No command groups, no composability, verbose boilerplate. Not suitable for a CLI with 6+ command groups. |
| .tscn/.tres parser | Custom parser | stevearc/godot_parser 0.1.7 | Inactive maintenance (no release in 12+ months). Open Godot 4 compatibility issue. Whitespace fidelity bugs. Performance issues with large files. Adds pyparsing dependency. Our format is well-specified; building our own gives us full control and zero maintenance risk from upstream abandonment. |
| .tscn/.tres parser | Custom parser | lark-parser 1.3.1 | Lark is a general-purpose parser generator. Overkill for Godot's format which has no ambiguity and relatively flat structure. A hand-rolled parser is simpler, faster, and has no dependency. Lark would be justified if the format were complex (like GDScript itself), but bracket-section + key=value is straightforward. |
| Data models | dataclasses | Pydantic v2 | Unnecessary validation overhead for internal data. 6x slower instantiation. Large dependency tree. Our data enters validated through the parser; we don't need runtime re-validation. |
| Data models | dataclasses | attrs | Similar to dataclasses but adds a dependency. stdlib dataclasses are sufficient for our needs. attrs' validators overlap with what the parser already does. |
| Package manager | uv | Poetry | Poetry is mature but slower. uv is the modern standard, handles lockfiles, and is from the same team as ruff (Astral). Faster cold installs, simpler workflow. |
| Package manager | uv | pip + requirements.txt | No lockfile, no virtualenv management, no Python version management. Legacy workflow. |
| Formatter | ruff | black + isort + flake8 | Three tools vs one. ruff replaces all three, runs 100x faster, configured in one pyproject.toml section. |
| Image processing | Pillow | opencv-python | Massive dependency (100MB+) for simple crop/composite operations. Pillow is 10MB and handles everything we need. |
| project.godot parser | configparser | tomllib | project.godot is INI-style, not TOML. Despite superficial similarity, Godot's format has quirks (section keys with colons, GDScript value literals) that tomllib would reject. configparser with minor preprocessing handles it correctly. |

## Dependency Classification

### Core (always installed)

```
click>=8.3,<9.0
rich-click>=1.9,<2.0
```

### Optional (feature-gated)

```
# Install with: pip install gdauto[image]
Pillow>=12.0,<13.0
```

### Development

```
pytest>=9.0,<10.0
pytest-cov>=7.0,<8.0
ruff>=0.11
mypy>=1.19
```

## Installation

```bash
# With uv (recommended)
uv init gdauto
uv add click "rich-click>=1.9"
uv add --optional image "Pillow>=12.0"
uv add --dev pytest pytest-cov ruff mypy

# With pip
pip install -e ".[dev]"
pip install -e ".[image]"      # adds Pillow
pip install -e ".[dev,image]"  # everything
```

## pyproject.toml Skeleton

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "gdauto"
version = "0.1.0"
description = "Agent-native CLI for Godot Engine"
requires-python = ">=3.12"
license = "Apache-2.0"
dependencies = [
    "click>=8.3,<9.0",
    "rich-click>=1.9,<2.0",
]

[project.optional-dependencies]
image = ["Pillow>=12.0,<13.0"]
dev = [
    "pytest>=9.0,<10.0",
    "pytest-cov>=7.0,<8.0",
    "ruff>=0.11",
    "mypy>=1.19",
]

[project.scripts]
gdauto = "gdauto.cli:cli"

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "requires_godot: marks tests requiring Godot binary on PATH",
]

[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
```

## Key Design Decisions

### Why custom parser over godot_parser

The decision to build our own .tscn/.tres parser instead of depending on stevearc/godot_parser is the most consequential stack choice. Rationale:

1. **Maintenance risk:** godot_parser has had no releases in 12+ months, has 4 unresolved issues, and the maintainer described limited availability. Depending on an inactive library for our core functionality creates a single point of failure.

2. **Godot 4 compatibility:** Issue #9 showed format=3 files caused ParseException. A colon-in-key-names fix was committed but the library hasn't been tested against the full Godot 4.5/4.6 format surface (terrain sets, SpriteFrames with new animation properties, uid references).

3. **Round-trip fidelity:** Issue #14 shows whitespace changes on re-save. Our generated .tres/.tscn files must be loadable by Godot without modification. Whitespace fidelity matters for version control diffs.

4. **Scope match:** We don't need a general-purpose parser. We need to parse specific resource types (SpriteFrames, TileSet) and generate valid .tres/.tscn output. A focused parser that understands our exact use cases is simpler and more reliable.

5. **Complexity budget:** The Godot text format is ~6 constructs: file header, ext_resource, sub_resource, node, resource, connection. Values are GDScript-like literals (strings, numbers, Vector2, Rect2, arrays, dictionaries). A recursive descent parser for this is ~500-800 lines. Not a significant effort.

### Why dataclasses over Pydantic

Pydantic's validation pipeline adds measurable overhead (6x slower instantiation). Our data flow is: raw text -> parser validates syntax -> dataclasses hold structure -> generator writes text. Validation happens exactly once, at parse time, where we control it. Re-validating at the model layer is redundant.

### Why Pillow is optional

The core value proposition (Aseprite JSON to SpriteFrames .tres) requires zero image manipulation. It reads JSON metadata and writes a text file. Pillow is only needed for atlas compositing (`sprite create-atlas`) and sheet slicing (`sprite split`), which are secondary commands. Keeping Pillow optional means the core tool installs with only two dependencies (click + rich-click).

## Runtime Dependencies Summary

| Dependency | Size | Required For | Optional? |
|------------|------|-------------|-----------|
| click | ~100KB | All CLI commands | No (core) |
| rich-click | ~200KB | Formatted help output | No (core) |
| rich | ~2MB | Transitive via rich-click | No (core, transitive) |
| Pillow | ~10MB | sprite create-atlas, sprite split | Yes (image extra) |
| **Total (core)** | **~2.3MB** | | |
| **Total (all)** | **~12.3MB** | | |

Zero-dependency count for file parsing (custom parser), data models (stdlib dataclasses), config reading (stdlib configparser), JSON handling (stdlib json), and subprocess management (stdlib subprocess).

## Sources

- [Click PyPI](https://pypi.org/project/click/) - v8.3.0 confirmed, Python 3.10+ required
- [Click changelog](https://click.palletsprojects.com/en/stable/changes/) - 8.2.0 dropped Python 3.7-3.9, 8.3.0 is latest stable
- [rich-click PyPI](https://pypi.org/project/rich-click/) - v1.9.7, Jan 2026
- [stevearc/godot_parser GitHub](https://github.com/stevearc/godot_parser) - v0.1.7, inactive, Godot 4 issue #9
- [godot_parser issue #9](https://github.com/stevearc/godot_parser/issues/9) - Godot 4 parse failures, partial fix
- [godot_parser issue #14](https://github.com/stevearc/godot_parser/issues/14) - Whitespace fidelity problems
- [Pillow PyPI](https://pypi.org/project/pillow/) - v12.1.1, Feb 2026
- [pytest PyPI](https://pypi.org/project/pytest/) - v9.0.2
- [ruff PyPI](https://pypi.org/project/ruff/) - latest Mar 2026
- [mypy docs](https://mypy.readthedocs.io/) - v1.19.1
- [uv docs](https://docs.astral.sh/uv/) - v0.11.2, Mar 2026
- [pyparsing PyPI](https://pypi.org/project/pyparsing/) - v3.3.2, Jan 2026
- [Pydantic PyPI](https://pypi.org/project/pydantic/) - v2.12.5
- [Click entry points docs](https://click.palletsprojects.com/en/stable/entry-points/) - pyproject.toml console_scripts
