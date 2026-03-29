# Technology Stack: Godot 4.6.1 Compatibility Audit

**Project:** gdauto v1.1
**Researched:** 2026-03-28
**Scope:** Delta between Godot 4.5 and 4.6.1 affecting gdauto's parsers, generators, backend wrapper, and export pipeline

## Executive Summary

Godot 4.6 (released January 2026) and 4.6.1 (maintenance, February 2026) introduce two file format changes that directly affect gdauto's parsers and generators, one new CLI flag relevant to our backend wrapper, and zero breaking changes to SpriteFrames or TileSet resource formats. The default format version stays at `format=3` for all resource types gdauto generates. Our core value proposition (Aseprite-to-SpriteFrames bridge) is unaffected; the main work is in the .tscn parser/generator and scene builder.

## File Format Changes (HIGH IMPACT)

### Change 1: `load_steps` Removed from File Headers

**PR:** [godotengine/godot#103352](https://github.com/godotengine/godot/pull/103352)
**Affects:** Both .tscn and .tres file headers
**Confidence:** HIGH (verified via PR, upgrade guide, docs issue [#11707](https://github.com/godotengine/godot-docs/issues/11707))

**What changed:**
- Godot 4.6 no longer **writes** `load_steps=N` in the `[gd_scene]` or `[gd_resource]` file header when saving files
- Godot 4.6 still **reads** `load_steps` from existing files (backward compatible on read)
- The engine now pre-computes resource counts by parsing files instead of using stored metadata, so the attribute is functionally obsolete
- `load_steps` was historically used only for progress bar display during scene loading; the engine never used it for actual logic

**Before (4.5):**
```
[gd_scene load_steps=4 format=3 uid="uid://cecaux1sm7mo0"]
```

**After (4.6):**
```
[gd_scene format=3 uid="uid://cecaux1sm7mo0"]
```

**Impact on gdauto:**

| Module | Impact | Action Required |
|--------|--------|-----------------|
| `formats/tscn.py` parse_tscn() | NONE | Already handles missing load_steps (line 176-177: `if load_steps_str else None`). Parsing works for both formats. |
| `formats/tres.py` parse_tres() | NONE | Already handles missing load_steps (line 142-143: `if load_steps_str else None`). Parsing works for both formats. |
| `formats/tscn.py` _build_tscn_from_model() | MEDIUM | Currently writes `load_steps=N` when present (line 221-222). For 4.6 output, should omit. |
| `formats/tres.py` _build_tres_from_model() | MEDIUM | Currently writes `load_steps=N` when present (line 188-189). For 4.6 output, should omit. |
| `scene/builder.py` build_scene() | MEDIUM | Computes and sets `load_steps` (line 37). For 4.6 target, should set to None. |
| `sprite/spriteframes.py` build_spriteframes() | MEDIUM | Computes and sets `load_steps` (line 191). For 4.6 target, should set to None. |
| `tileset/builder.py` build_tileset() | MEDIUM | Hardcodes `load_steps=3` (line 53). For 4.6 target, should set to None. |

**Recommended approach:** Add a `godot_version` or `target_version` parameter (defaulting to "4.6") that controls whether `load_steps` is written. When targeting 4.6+, omit it. When targeting 4.5, include it. Both versions can READ files with or without it.

### Change 2: `unique_id` Added to Scene Nodes

**PR:** [godotengine/godot#106837](https://github.com/godotengine/godot/pull/106837)
**Affects:** .tscn files only (not .tres)
**Confidence:** HIGH (verified via PR, upgrade guide, determinism issue [#115971](https://github.com/godotengine/godot/issues/115971))

**What changed:**
- Every `[node]` section in .tscn files now has a `unique_id` integer attribute in the header
- The ID is a 32-bit integer, scene-local (unique within one scene, not globally)
- Purpose: enables robust tracking of nodes through renames/moves in inherited and instantiated scenes
- No format version bump; `format=3` is unchanged
- Backward compatible: older Godot versions ignore the attribute; newer versions add it on re-save

**Before (4.5):**
```
[node name="Player" type="CharacterBody2D" parent="."]
```

**After (4.6):**
```
[node name="Player" type="CharacterBody2D" parent="." unique_id=1234567890]
```

**Impact on gdauto:**

| Module | Impact | Action Required |
|--------|--------|-----------------|
| `formats/common.py` parse_section_header() | NONE | Already parses arbitrary key=value attrs from headers into `attrs` dict. `unique_id` will be captured as `attrs["unique_id"] = "1234567890"`. No code change needed for parsing. |
| `formats/common.py` serialize_sections() | NONE | Uses `raw_line` for round-trip fidelity (line 279). Existing unique_id attributes are preserved verbatim. |
| `formats/tscn.py` SceneNode dataclass | LOW | Currently does not have a `unique_id` field. The value is silently captured in `raw_section.header.attrs` but not exposed on the SceneNode model. Should add optional field. |
| `formats/tscn.py` _extract_node() | LOW | Should extract `unique_id` from attrs and populate the new field. |
| `formats/tscn.py` _build_tscn_from_model() | MEDIUM | Does not write `unique_id` in node headers (line 248-253). For 4.6 target, should include it when present. |
| `formats/tscn.py` to_dict() | LOW | Should include `unique_id` in JSON output for resource inspect. |
| `scene/builder.py` build_scene() | LOW | Generated scenes do not need unique_id; Godot assigns them on first open. But optionally generating them would prevent the determinism issue. |
| `scene/lister.py` | LOW | Should expose unique_id in scene listing output. |

**Determinism issue:** [#115971](https://github.com/godotengine/godot/issues/115971) reports that scenes created in 4.5 but exported in 4.6 get non-deterministic unique_ids regenerated on every export. Workaround: re-save scenes in 4.6 to stabilize IDs. This is a Godot engine issue, not a gdauto issue, but users should be warned.

**Recommended approach:** Add `unique_id: int | None = None` to SceneNode. Parse it from attrs, include it in to_dict() and serialization. When building new scenes, optionally generate deterministic IDs (sequential counter starting at 1) so files are stable.

## File Format Non-Changes (Confirmed Stable)

### format= Version Number: Conditionally 4, Default 3

**Confidence:** HIGH (verified via Godot source `resource_format_text.h`, corroborated by ARCHITECTURE.md research)

Godot's internal `FORMAT_VERSION` constant was bumped to 4 (with `FORMAT_VERSION_COMPAT = 3`) in Godot 4.3. However, Godot only writes `format=4` when a file contains `PackedVector4Array` values or base64-encoded `PackedByteArray` data. For all other files (including SpriteFrames, TileSets, and simple scenes that gdauto generates), `format=3` continues to be written.

**Impact on gdauto:**
- **Parsing:** Our parser already reads `format` as an integer (`int(header.attrs.get("format", "3"))`), so it accepts both 3 and 4 without changes.
- **Generation:** gdauto generates SpriteFrames, TileSets, and scenes; none use PackedVector4Array or large PackedByteArray. We continue writing `format=3`. No change needed.
- **Value parser (P3 enhancement):** To fully parse format=4 files from user projects, our value parser should handle `PackedVector4Array(...)` constructors. This is not blocking for compatibility but improves `resource inspect` coverage.

### SpriteFrames Resource Format: Unchanged

**Confidence:** HIGH (no changes found in upgrade guide, changelog, or SpriteFrames docs)

The SpriteFrames .tres resource format (animations array, frame duration multipliers, loop settings, AtlasTexture sub-resources) is identical between 4.5 and 4.6. The animation dict keys (frames, loop, name, speed) are unchanged. Our `sprite/spriteframes.py` builder output remains valid.

### TileSet Resource Format: Unchanged

**Confidence:** MEDIUM (no format changes found; TileMapLayer got rotation support but TileSet format itself unchanged)

The TileSet .tres resource format (TileSetAtlasSource sub-resources, terrain peering bits, physics layers) is unchanged between 4.5 and 4.6. TileMapLayer gained tile rotation support, but this is a runtime/scene feature, not a TileSet resource format change. Our `tileset/builder.py` and `tileset/terrain.py` output remains valid.

### UID System: Unchanged from 4.4

**Confidence:** HIGH (UID generalization happened in 4.4; no further changes in 4.6; verified against Godot source `core/io/resource_uid.cpp`)

The UID system (uid:// text format, .uid companion files, base-34 encoding) is unchanged from 4.4. Our `formats/uid.py` implementation remains correct. Verified: character set (a-y, 0-8), base (34), max value ((1<<63)-1), encoding direction (LSB first, prepend), zero encoding (uid://a) all match.

### project.godot Format: Unchanged

**Confidence:** HIGH (verified: `CONFIG_VERSION = 5` in `core/config/project_settings.h` on master)

The project.godot INI-style format is unchanged. `config_version=5` remains current. New default project settings (Jolt physics for 3D, D3D12 on Windows) only affect newly created projects, not existing ones. Our `formats/project_cfg.py` parser is unaffected.

## CLI / Headless Mode Changes

### New Flag: `--export-patch <preset> <path>` (Present in 4.6 CLI)

**Confidence:** MEDIUM (found in CLI docs extracted from GitHub source)

Exports a patch PCK containing only changed files since a base build. Companion flag `--patches <paths>` specifies base patch files to diff against. This is new CLI surface area gdauto could potentially wrap in the export command group, but it is not required for the compatibility audit.

**Impact on gdauto:**

| Module | Impact | Action Required |
|--------|--------|-----------------|
| `export/pipeline.py` | OPPORTUNITY | Could add `mode="patch"` support with `--export-patch` flag. Not blocking for 4.6 compat. |
| `backend.py` | NONE | The `run()` method passes arbitrary args; no change needed for new flags. |

### New Flag: `--scene <path>` (Added in 4.5)

**PR:** [godotengine/godot#105302](https://github.com/godotengine/godot/pull/105302)
**Added in:** Godot 4.5 (merged May 2025)
**Confidence:** HIGH

Explicit scene path argument replacing the old implicit behavior. Supports UIDs. The old implicit approach is soft-deprecated but still works. gdauto does not currently launch scenes, so no action needed.

### Existing Flags: No Deprecations

**Confidence:** HIGH (verified via GitHub docs source for command_line_tutorial.rst)

All existing flags used by gdauto remain valid and unchanged:
- `--headless`: unchanged
- `--import`: unchanged (still performs resource import and exits; still implied by `--export-release`/`--export-debug`)
- `--export-release <preset> <path>`: unchanged
- `--export-debug <preset> <path>`: unchanged
- `--export-pack <preset> <path>`: unchanged
- `--quit`: unchanged
- `--quit-after <N>`: unchanged
- `--check-only`: unchanged
- `--version`: unchanged
- `--path <directory>`: unchanged

### `--import` Behavior: Unchanged

**Confidence:** MEDIUM (no changes documented; the known race condition with `--quit` vs `--quit-after` still applies)

Our `backend.py` `import_resources()` method uses `--import --quit-after 30` which remains the correct approach. No behavioral changes documented.

## Breaking Changes in Godot 4.6 (Not Affecting gdauto)

These are documented breaking changes that do NOT impact gdauto:

| Change | Why Not Affected |
|--------|------------------|
| AnimationPlayer properties changed from String to StringName | gdauto does not manipulate AnimationPlayer resources |
| Quaternion initializes to identity instead of zero | gdauto does not create Quaternion values |
| Glow blend mode changed to Screen, intensity defaults changed | gdauto does not set rendering properties |
| D3D12 default on Windows (new projects only) | gdauto does not create project.godot rendering settings |
| Jolt Physics default (new projects only) | gdauto does not create project.godot physics settings |
| GLSL shader mat4 to mat3x4 change | gdauto does not handle shaders |
| SpringBoneSimulator3D enum scope changes | gdauto does not handle skeleton modifiers |
| Android directory structure reorganization | gdauto does not manage Android build templates |
| MeshInstance3D default skeleton path changed | gdauto does not create MeshInstance3D nodes |

## Godot 4.6.1 Maintenance Release

**Released:** February 2026
**Fixes:** 38 regressions and bugs from 4.6, contributed by 25 developers
**Confidence:** HIGH (verified via [official release notes](https://godotengine.org/article/maintenance-release-godot-4-6-1/))

No file format changes in 4.6.1. All fixes are runtime/editor bug fixes:
- Animation system use-after-free fixes
- NodePath hash collision fix (GH-115473)
- Unique Resources from Inherited Scenes fix (GH-862)
- Various rendering fixes (MSAA, volumetric fog, sky)
- Platform fixes (Android file descriptors, Wayland leaks)
- GDScript LSP improvements

None of these affect gdauto's file parsing, generation, or CLI invocation.

## Ecosystem Changes (Overlap Assessment)

### Godot MCP Servers (NEW since v1.0)

Multiple MCP servers have appeared in 2025-2026 providing AI assistants with Godot editor control:

| MCP Server | Tools | Overlap with gdauto |
|------------|-------|---------------------|
| Godot MCP Pro | 163 tools | Scene tree operations, node manipulation; requires running editor |
| GDAI MCP | ~95 tools | Scene management, GDScript LSP, DAP debugging; requires running editor |
| Coding-Solo/godot-mcp | ~20 tools | Launch editor, run projects, debug output; requires running editor |

**Key distinction:** All Godot MCP servers require a running Godot editor instance (they communicate via RPC/socket). gdauto operates on files directly without Godot running. The niches do not overlap:
- MCP servers = editor automation (live manipulation of running editor state)
- gdauto = file manipulation (parse, generate, validate .tscn/.tres without Godot)
- gdauto's headless commands (import, export) are the bridge between these worlds

**No Aseprite CLI bridge has emerged.** The Aseprite Wizard plugin (editor-only) and nklbdev's importers (editor-only) remain the only alternatives. gdauto is still the only headless/CLI tool for Aseprite-to-SpriteFrames conversion.

**No TileSet terrain CLI automation has emerged.** All terrain peering bit tools remain editor-only plugins.

### Other Tools (Unchanged since v1.0)

| Tool | Status | Overlap |
|------|--------|---------|
| godot-build-pipeline-python | Exists (basic) | Simple export wrapper; no file manipulation, no retry logic |
| GodotEnv | Active | Version manager only; no file manipulation |
| GDToolkit (gdformat/gdlint) | Active | GDScript linting/formatting only |
| godot-ci Docker images | Active | CI runner only; uses Godot CLI directly |

## Version Compatibility Strategy

### Recommended Approach

Maintain Godot 4.5 as the floor, default to 4.6 output:

```python
# Target version for file generation
class GodotTarget:
    V4_5 = "4.5"  # Write load_steps, omit unique_id
    V4_6 = "4.6"  # Omit load_steps, optionally write unique_id
```

**Parsing:** Always accept both old and new formats (format=3 and format=4). The parser already handles this.

**Generation:** Default to 4.6 output format (no load_steps, format=3). Provide a `--target-version` flag or config option for users on 4.5.

**Round-trip:** The existing raw_line mechanism preserves whatever the input file had (load_steps or not, unique_id or not, format=3 or format=4).

## Summary of Required Changes

### Must Fix (Compatibility)

| Priority | Module | Change | Effort |
|----------|--------|--------|--------|
| P0 | `formats/tscn.py` | Add `unique_id: int \| None` to SceneNode, parse from attrs, include in to_dict() | Small |
| P0 | `formats/tscn.py` | Write `unique_id` in _build_tscn_from_model() node headers when present | Small |
| P1 | `formats/tscn.py` | Omit `load_steps` in _build_tscn_from_model() when targeting 4.6+ | Small |
| P1 | `formats/tres.py` | Omit `load_steps` in _build_tres_from_model() when targeting 4.6+ | Small |
| P1 | `sprite/spriteframes.py` | Set `load_steps=None` when targeting 4.6+ | Small |
| P1 | `tileset/builder.py` | Set `load_steps=None` when targeting 4.6+ | Small |
| P1 | `scene/builder.py` | Set `load_steps=None` when targeting 4.6+ | Small |

### Should Fix (Completeness)

| Priority | Module | Change | Effort |
|----------|--------|--------|--------|
| P2 | `scene/lister.py` | Expose unique_id in scene listing output | Small |
| P2 | Golden files | Update/add golden files for 4.6 format (no load_steps, with unique_id) | Medium |
| P2 | E2E tests | Verify generated files load in Godot 4.6.1 | Medium |

### Could Fix (Opportunity)

| Priority | Module | Change | Effort |
|----------|--------|--------|--------|
| P3 | `formats/values.py` | Add PackedVector4Array constructor parser for format=4 file support | Small |
| P3 | `export/pipeline.py` | Add `mode="patch"` support wrapping `--export-patch` | Medium |
| P3 | `scene/builder.py` | Generate deterministic unique_ids for new scenes | Small |

## Sources

- [Godot 4.6 Release Notes](https://godotengine.org/releases/4.6/) - Official release announcement
- [Upgrading from Godot 4.5 to 4.6 (GitHub source)](https://raw.githubusercontent.com/godotengine/godot-docs/master/tutorials/migrating/upgrading_to_godot_4.6.rst) - Official upgrade guide, complete breaking changes list
- [PR #103352: Remove load_steps](https://github.com/godotengine/godot/pull/103352) - load_steps removal implementation
- [PR #106837: Add unique Node IDs](https://github.com/godotengine/godot/pull/106837) - unique_id implementation
- [Issue #115971: Non-deterministic export](https://github.com/godotengine/godot/issues/115971) - unique_id determinism issue
- [Issue #11707: load_steps docs gap](https://github.com/godotengine/godot-docs/issues/11707) - Documentation not updated for load_steps removal
- [Godot 4.6.1 Maintenance Release](https://godotengine.org/article/maintenance-release-godot-4-6-1/) - 38 bug fixes, no format changes
- [GDQuest: Godot 4.6 Workflow Changes](https://www.gdquest.com/library/godot_4_6_workflow_changes/) - Community analysis of changes
- [TSCN Format Docs (GitHub source)](https://github.com/godotengine/godot-docs/blob/master/engine_details/file_formats/tscn.rst) - Updated with unique_id attribute
- [Command Line Tutorial (GitHub source)](https://raw.githubusercontent.com/godotengine/godot-docs/master/tutorials/editor/command_line_tutorial.rst) - Full CLI reference including --export-patch, --patches
- [PR #105302: --scene flag](https://github.com/godotengine/godot/pull/105302) - New --scene CLI argument (4.5+)
- [Godot resource_format_text.h](https://github.com/godotengine/godot/blob/master/scene/resources/resource_format_text.h) - FORMAT_VERSION=4, FORMAT_VERSION_COMPAT=3
- [Godot resource_uid.cpp](https://github.com/godotengine/godot/blob/master/core/io/resource_uid.cpp) - UID encoding verification
