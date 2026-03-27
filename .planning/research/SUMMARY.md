# Project Research Summary

**Project:** gdauto
**Domain:** Agent-native CLI tooling for Godot game engine automation
**Researched:** 2026-03-27
**Confidence:** HIGH

## Executive Summary

gdauto is a Python CLI tool that automates Godot Engine workflows that currently require the editor GUI. The core value proposition is an Aseprite-to-SpriteFrames bridge -- converting Aseprite JSON metadata into valid Godot .tres resource files without requiring a running Godot instance. The secondary differentiator is TileSet terrain automation, replacing hours of manual peering bit assignment with deterministic layout mapping. The tool is designed agent-native from the start: every command produces structured JSON output, uses non-zero exit codes, and is fully non-interactive. Experts build tools in this space by separating pure file manipulation (no Godot binary needed) from headless engine invocation (subprocess wrapping), and gdauto follows this exact pattern.

The recommended approach is a lean Python stack (Click + rich-click, stdlib for everything else, custom Godot file format parser) organized in three layers: CLI surface, domain logic, and file format I/O. The most consequential decision is building a custom .tscn/.tres parser rather than depending on the abandoned godot_parser library. This is justified: the Godot text format is well-specified and bounded (~6 constructs), the existing library targets Godot 3.x format=2 and is unmaintained, and gdauto's core value depends on correct file generation where we must control the output. The parser is estimated at 500-800 lines of Python.

The key risks are: (1) generating invalid resource IDs or missing UIDs that cause Godot to silently rewrite files, creating version control noise; (2) botching Aseprite frame duration conversion for variable-timing animations; (3) getting terrain peering bit mappings wrong for the 47-tile blob layout, which is reverse-engineered from community conventions rather than official documentation; and (4) headless Godot's well-documented import race condition breaking E2E tests. All four risks have clear mitigation strategies documented in the pitfalls research, and all map to specific phases where they must be addressed.

## Key Findings

### Recommended Stack

The stack is deliberately minimal: only two runtime dependencies (click and rich-click), with Pillow as an optional extra for image manipulation commands. Everything else uses the Python standard library. Python >= 3.12 is required for modern type hints and performance improvements. uv manages the project (dependencies, virtualenvs, lockfile). ruff and mypy handle code quality.

**Core technologies:**
- **Python >= 3.12 + Click 8.3 + rich-click 1.9:** CLI framework mandated by PROJECT.md, with drop-in rich formatting for human-readable help
- **Custom .tscn/.tres parser:** Hand-rolled state machine parser (~500-800 LoC) replacing the abandoned godot_parser library; gives full control over Godot 4.x format=3, round-trip fidelity, and UID support
- **stdlib dataclasses:** Internal data models without Pydantic overhead (6x faster instantiation, zero dependencies); validation happens at the parser level
- **stdlib configparser:** project.godot INI-style parsing with minor preprocessing for Godot quirks
- **Pillow 12.1 (optional):** Only needed for atlas compositing and sheet splitting; core Aseprite bridge requires zero image manipulation
- **uv + pyproject.toml + hatchling:** Modern Python project management; single config file for everything

### Expected Features

**Must have (table stakes):**
- `--json` flag on every command (agent-native contract)
- Structured error messages with error codes and suggested fixes
- Non-zero exit codes on failure
- Godot binary discovery with `--godot-path` override and `GODOT_BINARY` env var
- Headless export (release/debug/pack) with auto-import-before-export
- Force re-import with retry logic for Godot's timing bugs
- Resource inspection (dump any .tres/.tscn as JSON)
- Project info (dump project.godot as JSON)
- Project validation (missing resources, broken references, script errors)

**Should have (differentiators):**
- `sprite import-aseprite` -- THE core differentiator; no headless CLI tool does this today
- `tileset auto-terrain` -- deterministic peering bit assignment for standard layouts (47-tile blob, 16-tile minimal, RPG Maker)
- `tileset create` -- sprite sheet to TileSet resource without the editor
- `tileset assign-physics` -- batch collision assignment by tile range
- `sprite split` and `sprite create-atlas` -- sprite sheet manipulation
- `scene create` -- generate .tscn from JSON definitions without Godot running

**Defer (v2+):**
- Scene creation from definitions (complex node type validation)
- Project scaffolding with genre-specific templates
- SKILL.md auto-generation (tool must be feature-complete first)
- Tiled .tmx/.tmj import (adds parser complexity for a secondary workflow)
- Live game interaction, RL/ML integration, addon management, GUI/TUI (explicitly anti-features)

### Architecture Approach

The architecture follows a strict three-layer separation: CLI surface (Click command modules as thin orchestrators), domain logic (pure Python functions with zero I/O), and file format layer (parser/generator with zero domain knowledge). Commands operate in one of two modes: "direct" (pure Python file manipulation, no Godot needed) or "headless" (subprocess invocation via a centralized backend wrapper). A Click context object carries shared state (output format, verbosity, lazy-initialized Godot backend), and a dual-mode output formatter ensures the `--json` contract is never broken.

**Major components:**
1. **File Format Layer** (`formats/`) -- tokenizer, section parser, value type (de)serializer for .tscn/.tres; INI parser for project.godot; Aseprite JSON parser
2. **Domain Logic Layer** (`domain/`) -- Aseprite-to-SpriteFrames bridge (duration conversion, direction handling, trim offsets), TileSet builder (peering bit lookup tables, collision shapes), scene builder
3. **CLI Surface Layer** (root package) -- Click command groups (sprite, tileset, scene, project, export, resource), output formatter, Click context object
4. **Backend Layer** (`godot_backend.py`) -- centralized subprocess wrapper for all Godot binary interactions (discovery, timeout, error parsing, retry logic)

### Critical Pitfalls

1. **Invalid resource IDs and missing UIDs** -- Godot 4 uses `Type_xxxxx` alphanumeric IDs and `uid://` base36 UIDs. Omitting or mis-formatting these causes silent file rewrites and version control noise. Mitigation: dedicated ID/UID generators with collision testing and golden-file E2E tests from Phase 1.

2. **Wrong Aseprite duration conversion** -- Naive ms-to-FPS conversion fails for variable-timing animations. Mitigation: compute GCD of all frame durations, set animation speed to `1000/GCD`, compute per-frame duration multipliers. Test with uniform, variable, very slow, and very fast frame timing.

3. **Trimmed sprite offset handling** -- Aseprite's `spriteSourceSize` offsets are silently ignored in untrimmed-only implementations, causing frame jitter. Mitigation: always check `trimmed` field, apply offsets via AtlasTexture margin. Test with both trimmed and untrimmed fixtures.

4. **Headless import race condition** -- Godot's `--import` with `--quit` exits before import completes (issue #77508). Mitigation: use `--quit-after 2` or timeout wrapper, verify `.godot/imported/` contents, implement retry logic in backend wrapper.

5. **Wrong terrain peering bit mappings** -- No official Godot documentation maps grid positions to peering bits for standard layouts. Mitigation: use TileBitTools' archived mapping data as reference, build lookup tables (not computed logic), E2E test by painting terrain in Godot and verifying transitions.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation (Parser, CLI Skeleton, Backend)
**Rationale:** Every feature depends on the file format parser and CLI framework. The parser is the highest-risk component (custom build, complex edge cases) and must be proven correct before any domain logic builds on it. UID and resource ID generation are foundational -- getting them wrong infects every subsequent phase.
**Delivers:** Working .tscn/.tres parser/generator with round-trip fidelity, Godot value type serialization, project.godot parser, Click CLI skeleton with `--json` infrastructure, output formatter, Godot backend wrapper with timeout and retry logic, `resource inspect` command, `project info` command.
**Addresses features:** `--json` flag infrastructure, structured errors, exit codes, Godot binary discovery, resource inspection, project info.
**Avoids pitfalls:** Invalid resource IDs (Pitfall 1), missing UIDs (Pitfall 2), regex parser (Pitfall 6), format version instability (Pitfall 8), headless import race condition (Pitfall 5), file overwrite without warning.

### Phase 2: Aseprite-to-SpriteFrames Bridge (Core Value)
**Rationale:** This is the primary differentiator -- no other CLI tool converts Aseprite exports to Godot SpriteFrames without the editor. It exercises the parser/generator from Phase 1 with a concrete, well-specified use case (Aseprite JSON is fully documented). Shipping this first validates the architecture and provides immediate user value.
**Delivers:** `sprite import-aseprite` command with full animation support (named animations from tags, per-frame variable durations, all four Aseprite directions, loop/repeat handling, trimmed sprite offsets), plus E2E tests loading generated .tres in Godot.
**Addresses features:** Aseprite-to-SpriteFrames bridge (P1 differentiator).
**Avoids pitfalls:** Duration conversion errors (Pitfall 3), trimmed sprite misalignment (Pitfall 4), missing frameTags handling, ping-pong direction support.

### Phase 3: TileSet Automation (Second Differentiator)
**Rationale:** The second major value proposition. Exercises the parser/generator with a more complex resource type (TileSet has terrain sets, physics layers, atlas sources). Depends on Phase 1 parser being battle-tested through Phase 2. The peering bit mapping is the highest-risk aspect and needs dedicated E2E verification.
**Delivers:** `tileset create` (sprite sheet to TileSet), `tileset auto-terrain` (peering bit assignment for blob47/minimal16/RPG Maker layouts), `tileset assign-physics` (batch collision shapes), `tileset inspect` (TileSet as JSON).
**Addresses features:** TileSet creation, terrain auto-configuration, physics assignment, TileSet inspection.
**Avoids pitfalls:** Wrong peering bit mapping (Pitfall 7). Requires careful E2E testing with multiple layout conventions.

### Phase 4: Headless Godot Integration (Export and Import)
**Rationale:** Export and import commands are table stakes for CI/CD use but are independent of the file manipulation pipeline. Deferring them lets Phases 2-3 focus on pure Python correctness without Godot binary dependency complexity. The backend wrapper from Phase 1 provides the foundation.
**Delivers:** `export release`, `export debug`, `export pack` commands with structured error reporting, `import` (force re-import with retry), `project validate` combining file-system scanning with optional `--check-only`.
**Addresses features:** Headless export, force re-import, project validation.
**Avoids pitfalls:** Import race condition (Pitfall 5, verified in E2E), export-without-prior-import failure.

### Phase 5: Sprite Utilities and Scene Commands
**Rationale:** Lower-priority commands that build on the proven parser and domain logic. Sprite split and atlas creation share frame region logic with the Aseprite bridge. Scene commands are useful but less differentiated.
**Delivers:** `sprite split`, `sprite create-atlas` (requires Pillow optional dependency), `scene create` (from JSON definitions), `scene list` (project auditing), SKILL.md auto-generation.
**Addresses features:** Sprite sheet splitting, atlas creation, scene creation, scene listing, agent discoverability.

### Phase 6: Polish and Community Readiness
**Rationale:** Error message refinement, shell completion, documentation, and packaging for distribution. This phase prepares the tool for community adoption.
**Delivers:** Shell completion, refined error messages with actionable suggestions, comprehensive documentation, PyPI packaging, project scaffolding templates.

### Phase Ordering Rationale

- **Parser first** because every file manipulation command depends on it. A parser bug is catastrophic; an Aseprite bridge bug is isolated.
- **Aseprite bridge second** because it is the clearest specification (Aseprite JSON is well-documented), the strongest differentiator (zero competition), and the best validation of the parser architecture.
- **TileSet third** because it exercises the parser with a more complex resource type, validating that the architecture generalizes beyond SpriteFrames.
- **Export/import fourth** because these are well-understood patterns (subprocess wrapping) with low architectural risk, and they are independent of the file manipulation pipeline.
- **Utilities last** because they reuse infrastructure from earlier phases and are not differentiators.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (Parser):** Needs phase research. The Godot text format has underdocumented edge cases (multiline values, StringName syntax, PackedByteArray encoding). Build the test fixture set from real Godot-generated files early. The UID generation algorithm (base36-encoded 64-bit CSPRNG) needs verification against Godot source code.
- **Phase 2 (Aseprite Bridge):** Needs phase research. Aseprite Wizard's GDScript source is the best reference implementation for duration conversion and direction handling. Study its edge cases before implementing.
- **Phase 3 (TileSet Automation):** Needs phase research. Peering bit mappings are reverse-engineered. TileBitTools' archived data is the primary reference. Must validate against Godot 4.5's terrain painting algorithm.

Phases with standard patterns (skip research-phase):
- **Phase 4 (Export/Import):** Well-documented. godot-ci Docker images and Godot's CLI tutorial cover all flags. The only non-obvious aspect (import race condition) is already documented in pitfalls.
- **Phase 5 (Utilities):** Standard patterns. Sprite splitting is coordinate arithmetic. Atlas creation uses bin-packing (well-known algorithm).
- **Phase 6 (Polish):** Standard patterns. Click shell completion is documented. PyPI packaging via hatchling is standard.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies verified on PyPI with current versions. Only two runtime dependencies. No speculative choices. |
| Features | HIGH (core), MEDIUM (differentiators) | Table stakes are well-understood from competitor analysis. Aseprite bridge value proposition is clear (zero competition). TileSet automation confidence is medium due to undocumented peering bit conventions. |
| Architecture | HIGH | Three-layer separation (CLI / domain / formats) is standard for Python CLI tools. Click patterns are well-documented. The main architectural risk is the custom parser, which is mitigated by the format's bounded complexity. |
| Pitfalls | HIGH | Most pitfalls verified through official Godot GitHub issues and community tools. Import race condition is documented in issue #77508. ID format changes documented in issue #77172. Duration conversion studied from Aseprite Wizard source. |

**Overall confidence:** HIGH

### Gaps to Address

- **Godot 4.5 format specifics:** The research targets "4.5+" but Godot 4.5 may introduce format changes not yet documented. Validate generated files against the specific Godot 4.5 release during Phase 1 E2E testing.
- **UID generation algorithm:** The exact base36 encoding Godot uses needs verification against engine source code. A wrong encoding produces UIDs that Godot silently rewrites. Validate in Phase 1 with golden-file tests.
- **Peering bit lookup tables:** No authoritative source exists for grid-position-to-peering-bit mappings. TileBitTools is archived and may have bugs. Must be verified empirically by generating TileSets and painting terrain in Godot during Phase 3.
- **Aseprite repeat count mapping:** Aseprite's `repeat` field in tags (added in Aseprite 1.3) maps to SpriteFrames' `loop` property, but the exact semantics (repeat=0 means infinite, repeat=1 means play once) need verification against Aseprite's documentation and Godot's behavior.
- **Windows line endings:** Godot expects LF line endings. Verify that the file writer produces LF on Windows (Python's `open()` with `newline='\n'` or binary mode).

## Sources

### Primary (HIGH confidence)
- [Godot TSCN File Format Docs](https://docs.godotengine.org/en/4.4/contributing/development/file_formats/tscn.html) -- official format specification
- [Godot Command Line Tutorial](https://docs.godotengine.org/en/latest/tutorials/editor/command_line_tutorial.html) -- headless flags and export workflow
- [Click Documentation](https://click.palletsprojects.com/en/stable/) -- CLI framework patterns, testing, complex applications
- [godotengine/godot#77508](https://github.com/godotengine/godot/issues/77508) -- headless import race condition
- [godotengine/godot#77172](https://github.com/godotengine/godot/issues/77172) -- ExtResource ID rewriting on save
- [UID changes in Godot 4.4](https://godotengine.org/article/uid-changes-coming-to-godot-4-4/) -- UID system documentation
- [Click PyPI](https://pypi.org/project/click/) -- v8.3.0, Python 3.10+ requirement confirmed
- [Pillow PyPI](https://pypi.org/project/pillow/) -- v12.1.1, Feb 2026

### Secondary (MEDIUM confidence)
- [Aseprite Wizard](https://github.com/viniciusgerevini/godot-aseprite-wizard) -- reference implementation for duration conversion and direction handling
- [TileBitTools](https://github.com/dandeliondino/tile_bit_tools) -- archived, but peering bit mapping data is the best available reference
- [stevearc/godot_parser](https://github.com/stevearc/godot_parser) -- evaluated and rejected; format=2 only, unmaintained
- [godot-resource-parser](https://github.com/fernforestgames/godot-resource-parser) -- TypeScript parser, archived Jan 2026; confirms demand for external parsing tools
- [GDToolkit Architecture (DeepWiki)](https://deepwiki.com/Scony/godot-gdscript-toolkit) -- reference for Python tool architecture in Godot ecosystem

### Tertiary (LOW confidence)
- Community tileset layout conventions -- multiple sources with minor disagreements on exact grid positions; needs empirical validation
- Godot 4.5 format specifics -- not yet released at time of research; format stability assumed based on 4.x track record

---
*Research completed: 2026-03-27*
*Ready for roadmap: yes*
