# Decision Log

Architectural and design decisions for auto-godot, with rationale.
New decisions should be appended at the bottom with the next sequential number.

## ADR-001: Click over Typer for CLI framework

**Date:** 2026-03-28  
**Status:** Approved

Click provides explicit control over command groups, `pass_context` patterns,
and the `--json` flag implementation. Typer wraps Click with type-hint decorators,
but its elegance obscures the complex subcommand structure (17+ command groups
with per-command JSON output). Click's verbosity is a feature here: each command's
options, arguments, and context flow are visible in the code.

## ADR-002: Custom .tscn/.tres parser over godot_parser

**Date:** 2026-03-28  
**Status:** Approved

stevearc/godot_parser (v0.1.7) has unresolved Godot 4 compatibility issues,
whitespace fidelity bugs, and no maintenance activity. Godot's text format is
well-specified: bracket sections, key=value pairs, and nested GDScript-like
literals. A hand-rolled state machine parser gives full round-trip fidelity,
format=3 compatibility, and zero upstream maintenance risk in ~500-800 lines.

## ADR-003: Dataclasses over Pydantic for internal models

**Date:** 2026-03-28  
**Status:** Approved

Internal data structures (GdResource, GdScene, SubResource, ExtResource, Node)
are already validated by the parser. No runtime re-validation needed. Dataclasses
are 6x faster to instantiate, have zero dependencies, and provide IDE type-hint
support. Pydantic's 2MB+ overhead is justified for API boundaries, not for
internal models already validated at the parser level.

## ADR-004: No Godot binary required for file manipulation

**Date:** 2026-03-28  
**Status:** Approved

The core value is generating valid .tres/.tscn files entirely in Python. Commands
like sprite import-aseprite, tileset create, and resource inspect operate on text
files without needing the engine. Headless Godot is only required for import
re-indexing, script validation, and E2E tests. This enables agent automation in
CI/CD environments without Godot installation.

## ADR-005: Pillow as optional dependency

**Date:** 2026-03-28  
**Status:** Approved

The core sprite import-aseprite command reads JSON metadata and writes .tres text
with no pixel operations. Pillow (10MB) is only needed for sprite create-atlas
(compositing) and sprite split (slicing). Marking it optional via `[image]` extra
keeps the core CLI lean for headless/agent use.

## ADR-006: Python 3.12+ minimum version

**Date:** 2026-03-28  
**Status:** Approved

Python 3.12 added PEP 695 type aliases, f-string improvements, and a 15%
performance boost. Click 8.3 already requires 3.10+. Python 3.13 added 3x faster
dataclass creation, matching the internal model strategy. 3.12 is the practical
floor: modern syntax without requiring unstable beta versions.

## ADR-007: Rename from gdauto to auto-godot

**Date:** 2026-04-10  
**Status:** Completed

"auto-godot" immediately signals "Godot automation tool" while "gdauto" was
ambiguous. The rebrand renamed the Python package (gdauto to auto_godot), CLI
entry point (gdauto to auto-godot), and updated 145 files. Naming follows
agent-friendly conventions: dash-separated public names, underscore-separated
Python modules.

## ADR-008: Agent-native --json flag on every command

**Date:** 2026-03-28  
**Status:** Mandated

Every command supports `--json` as a global flag producing structured output.
Errors use `{"error": "message", "code": "ERROR_CODE", "fix": "suggestion"}`.
This makes auto-godot composable for LLMs (parse JSON), CI/CD (check exit codes),
and humans (read formatted tables). Non-negotiable per CLI-METHODOLOGY.md.

## ADR-009: configparser for project.godot parsing

**Date:** 2026-03-28  
**Status:** Approved

project.godot is INI-style with Godot-specific quirks: section keys with colons,
bracket-less global section, GDScript value literals. Python's stdlib configparser
handles the base format natively. Minor preprocessing (prepending a default section
header, handling special keys) covers the quirks. TOML parsers would reject the
format. Zero external dependencies.

## ADR-010: rich-click for formatted help output

**Date:** 2026-03-28  
**Status:** Approved

Drop-in Click replacement (`import rich_click as click`) adds colored help text,
tables, and grouped options without code changes. Agents ignore formatting and use
`--json`. Humans get readable `--help` output. Rich + rich-click total ~2.3MB,
the only non-trivial core dependency.

## ADR-011: Claude Code integration shipped with the repo

**Date:** 2026-04-11  
**Status:** Approved

Ship `.claude/` directory with CLAUDE.md conventions, path-scoped rules
(scene-building, sprite-pipeline), reusable skills (validate, fix-scene,
build-game), a custom gdauto-expert agent, and PostToolUse hooks for output
validation. This persistent knowledge layer prevents AI agents from hitting the
same gotchas repeatedly. Skills and agents are lazy-loaded, so they add zero
overhead when not invoked. Driven by findings from the Cookie Cosmos production
build where 12+ errors surfaced at once in phase 10 due to no incremental
validation. See issue #29 for the full strategy.
