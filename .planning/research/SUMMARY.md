# Project Research Summary

**Project:** gdauto v1.1 — Godot 4.6.1 Compatibility Audit
**Domain:** Godot engine file format delta; headless CLI tooling for Godot 4.5/4.6
**Researched:** 2026-03-28
**Confidence:** HIGH

## Executive Summary

Godot 4.6 (January 2026) and its 4.6.1 maintenance release (February 2026) introduce two file format changes that directly affect gdauto and a set of well-documented breaking changes that do not. The format changes are: (1) `load_steps` is no longer written in `.tscn`/`.tres` file headers (PR #103352), and (2) every scene node now carries a `unique_id` integer attribute in its `[node]` header (PR #106837). Both are backward-compatible in the sense that Godot 4.6 still reads files with `load_steps` and Godot 4.5 ignores `unique_id`. The recommended strategy is forward-only: stop emitting `load_steps` universally and add `unique_id` support, producing files valid for both engine versions. The `format=3` version number remains unchanged for all files gdauto generates (SpriteFrames, TileSets, simple scenes), and neither SpriteFrames nor TileSet resource structures changed.

The required work is confined to two thin layers: generators (serializers that build file headers) and the test infrastructure (golden files and normalization). The three-layer architecture (CLI / domain / formats) isolates changes cleanly — no architectural rewrites are needed. Eight source files need `load_steps` removed from their output, three need `unique_id` support added, and all golden reference files need regeneration. None of these require algorithmic redesign; all are well-scoped mechanical changes verified directly against Godot source code and merged PRs.

The most significant operational risk is the export determinism regression (issue #115971, "Very Bad" severity): Godot 4.6 assigns non-deterministic `unique_id` values to scene nodes that lack them, causing every export to produce a different binary hash. Generating deterministic `unique_id` values in gdauto-created scenes directly prevents this. The headless import race condition (issue #77508) persists unchanged from prior versions; the existing `--quit-after 30` mitigation already handles it, but adding post-import completeness verification would harden the pipeline. gdauto's niche (headless, no-editor file manipulation) remains uncontested — all Godot MCP servers that emerged in 2025-2026 require a running editor instance.

## Key Findings

### Recommended Stack

No Python dependency changes are required for v1.1. The existing stack (Python 3.12+, Click 8.3, custom state-machine parser, stdlib json/configparser, Pillow for image commands) remains optimal. The custom parser over `stevearc/godot_parser` is validated by this audit: the third-party library would require significant patching for Godot 4.6 format changes, while our in-house parser already handles both old and new formats on read with no changes needed to the parsing path.

**Core technologies:**
- Python 3.12+: runtime — type aliases, improved error messages, 15% perf boost over 3.11
- Click 8.3: CLI framework — mandated, battle-tested, supports `--json` flag and command groups
- Custom .tscn/.tres parser: format layer — full control over format=3/4 compatibility, round-trip fidelity via `raw_line` preservation; `stevearc/godot_parser` has Godot 4 compatibility issues and is unmaintained
- stdlib configparser: project.godot parser — INI-style format, no dependency needed
- stdlib json: Aseprite metadata and `--json` output — no third-party JSON library needed at this scale
- stdlib dataclasses: internal data models — 6x faster than Pydantic, no validation overhead for already-parsed data
- Pillow 12.1.x (optional): atlas creation and sprite splitting only; NOT needed for core Aseprite-to-SpriteFrames bridge
- pytest 9.0.x, ruff, mypy, uv: development tooling — unchanged from v1.0

**No new dependencies needed for v1.1.**

### Expected Features

**Must have (table stakes):**
- Omit `load_steps` from all generated `.tres`/`.tscn` headers — Godot 4.6 strips it on re-save; causes VCS diff noise for every user; affects 8 source files and 18 references
- Parse `unique_id` from `.tscn` node headers — 4.6 scenes contain this attribute; parser must expose it on the `SceneNode` model
- Preserve `unique_id` on round-trip — model-based serialization must emit it when present; raw-line path already handles it correctly
- Update golden files — existing golden files include `load_steps`; new output will not; all golden reference files need regeneration
- Update `_check_load_steps()` sprite validator — validates a now-obsolete attribute; must be skipped or demoted for 4.6 output

**Should have (differentiators):**
- Add `unique_id` field to `SceneNode` dataclass — exposes node IDs in `resource inspect` and `scene list` JSON output for agents
- Write `unique_id` in model-based scene serialization — generated scenes include node IDs when available
- Generate deterministic `unique_id` values in `scene create` — prevents non-deterministic export regression (#115971); use CSPRNG 32-bit int or sequential counter
- Expose `unique_id` in `scene list` JSON output — richer scene analysis for AI agent consumers
- Add import completeness verification after `import_resources()` — checks `.godot/imported/` for expected files, not just directory existence

**Defer (v2+):**
- Version-aware generation flag (`--target-version 4.5`) — most users are on 4.6; 4.5 tolerates omitted `load_steps`; implement only if users on 4.5 report issues
- `--export-patch` wrapper for delta PCK exports — new Godot 4.6 headless flag; useful but not blocking
- TileMapLayer scene data manipulation — complex, editor-focused; tile rotation is a runtime feature
- LibGodot embedding as alternative to subprocess — experimental API, major architectural change
- `gdauto project upgrade-scenes` migration command — useful but Godot editor already does this via "Upgrade Project Files"

### Architecture Approach

The existing three-layer architecture (CLI commands / domain logic / formats layer) handles all Godot 4.6 changes cleanly without restructuring. All file format changes are confined to the formats layer (`tscn.py`, `tres.py`, `values.py`) and the domain builders (`spriteframes.py`, `tileset/builder.py`, `scene/builder.py`). The round-trip architecture already works correctly: the `serialize_sections()` function in `common.py` uses `raw_line` for headers and `raw_properties` for values, meaning any file read and re-written without model modification is byte-identical regardless of Godot version. Only the model-to-text generation path (building new files from `SceneNode`/`GdResource` dataclasses) needs updates.

**Major components:**

1. `formats/` layer (parser + serializer) — reads `.tscn`, `.tres`, `project.godot`; writes generated files; raw-line preservation gives free round-trip fidelity; state-machine parser already accepts arbitrary header attrs
2. Domain builders (`sprite/spriteframes.py`, `tileset/builder.py`, `scene/builder.py`) — construct resource models from domain inputs; these are the source of `load_steps` emission and the target for `unique_id` generation
3. `backend.py` + `export/pipeline.py` — wraps Godot headless binary; all CLI flags unchanged; version detection via `_check_version()` already parses major.minor; can expose as `version_tuple` property for use by generators
4. Test infrastructure (`tests/unit/test_golden_files.py`, `tests/fixtures/golden/`) — golden file comparison with normalization; must be extended with `load_steps` and `unique_id` stripping patterns; all golden reference files need regeneration

**Key pattern: "Parse anything, generate current."** The parser accepts format=3 and format=4 without branching. Generators always write current (4.6-style) output: no `load_steps`, `format=3`, `unique_id` when present. Both directions produce files valid in Godot 4.5 and 4.6.

### Critical Pitfalls

1. **`load_steps` removal is not in Godot 4.6 release notes** — the change was only documented after community report (godot-docs#11707). Users and tool authors expecting it to still be there will be surprised. Prevention: strip from all 8 generator sites; parser remains tolerant of both formats.

2. **Missing `unique_id` causes non-deterministic exports** — Godot 4.6 assigns IDs at export time when a scene lacks them, and the RNG seed is not stable (issue #115971, "Very Bad", milestoned 4.7). Every export of a gdauto-generated scene produces a different binary hash. Prevention: generate `unique_id` values in `scene create`; normalize them in golden file tests.

3. **Golden file drift breaks the test suite symmetrically in both directions** — removing `load_steps` from generated output means existing golden files immediately fail; updating golden files without expanding `normalize_for_comparison()` means `unique_id` values (which change per generation run) will also break tests. Prevention: update normalization patterns first, then regenerate golden files in the same step.

4. **`load_steps` applies to `.tres` as well as `.tscn`** — PR #103352 modified `resource_format_text.cpp`, which handles both. The v1.0 audit only anticipated `.tscn` changes. SpriteFrames and TileSet `.tres` files both currently include `load_steps`. Prevention: apply the same omission logic to `.tres` builders; this is Pitfall 4 from PITFALLS.md, easy to overlook.

5. **`config_version=5` cannot be used for Godot minor version detection** — it has been 5 for all of Godot 4.x. For feature-conditional behavior, use `[application] config/features` in project.godot or binary `--version` output. Prevention: design version detection before implementing any conditional format behavior.

## Implications for Roadmap

Based on research, this v1.1 audit milestone should have three phases. The work is small enough that phases 1 and 2 could be merged if the team prefers fewer milestones.

### Phase 1: Format Compatibility Layer

**Rationale:** All format changes are well-scoped mechanical edits to existing code. The test infrastructure must be updated in the same phase to avoid a broken-tests interim state. Format changes before validation — you cannot validate what you have not built.

**Delivers:** gdauto generates files valid for Godot 4.6.1 with no unnecessary diff noise; round-trip of 4.6 scenes preserves `unique_id`; test suite passes against new output format.

**Addresses:** load_steps removal (8 files), unique_id support (SceneNode dataclass + parser + serializer + builder), golden file regeneration, normalization pattern expansion, sprite validator update, deterministic `unique_id` generation in `scene create`.

**Avoids:** Pitfalls #1, #2, #3, #4 — the four HIGH-severity pitfalls all resolve here.

**Build order within phase:**
1. Expand `normalize_for_comparison()` with `load_steps` and `unique_id` stripping patterns (test infrastructure first)
2. Add `unique_id: int | None = None` to `SceneNode` dataclass; parse in `_extract_node()`
3. Update `_build_tscn_from_model()` to emit `unique_id` when present; make `load_steps` conditional (omit when None)
4. Update `_build_tres_from_model()` — same `load_steps` conditional
5. Set `load_steps=None` in `build_spriteframes()`, `build_tileset()`, `build_scene()`
6. Generate deterministic `unique_id` in `scene/builder.py`
7. Update `_check_load_steps()` in sprite validator
8. Regenerate all golden files

### Phase 2: Parser Hardening and Pipeline Validation

**Rationale:** Parser extension (format=4 PackedVector4Array) and headless import verification are independent of format changes. They harden the tool against real-world files without changing generated output. Doing this second avoids mixing concern layers in Phase 1.

**Delivers:** Parser accepts format=4 files from user projects (no crash on PackedVector4Array); import verification catches incomplete imports that previously silently succeeded.

**Addresses:** PackedVector4Array parser support in `values.py`; import completeness verification in `backend.py`/`export/pipeline.py`; `version_tuple` property exposure on `GodotBackend`; AnimationLibrary format change validation tests (parse, do not convert).

**Avoids:** Pitfall #5 (import race condition with silent success), Pitfall #7 (AnimationLibrary round-trip correctness).

### Phase 3: E2E Validation Against Godot 4.6.1

**Rationale:** E2E tests require the Godot binary and are the authoritative check that file format changes actually work. They should run last, after code and unit tests are stable, to surface any behavioral differences that research missed.

**Delivers:** Confirmed compatibility with Godot 4.6.1 binary; new golden files for 4.6 output format; regression coverage for TileSet bounds strictness edge case and round-trip fidelity for both 4.5 and 4.6 files.

**Addresses:** E2E test suite run against 4.6.1, round-trip fidelity tests (parse a 4.6-saved `.tscn`, serialize back, verify byte-identical), TileSet atlas alignment verification, Godot 4.5 backward compat check (generated files without `load_steps` load cleanly).

**Avoids:** Pitfall #2 residual (verify export determinism with unique_id present), Pitfall #5 (verify import completeness checks work in practice).

### Phase Ordering Rationale

- Format changes first because all test infrastructure depends on them and they are the prerequisite for every validation step.
- Parser hardening second because it is independent of generated output format and operates on a different code surface (value parser vs. builders).
- E2E last because it requires a Godot binary, validates all prior work, and surfaces any behavioral surprises that static analysis cannot catch.
- Phases 1 and 2 have no dependency between them and could be merged or run in parallel if bandwidth allows.

### Research Flags

Phases with standard patterns (research-phase not needed):
- **Phase 1:** All changes are verified via Godot source PRs and upgrade guide. No ambiguity. Direct mechanical edits to known files at known line numbers.
- **Phase 2:** PackedVector4Array is documented in PR #85474 and #89186. Import verification is a test-coverage gap, not an unknown pattern.

Phases that may surface unknowns during execution:
- **Phase 3:** E2E tests may reveal unexpected Godot 4.6 validation strictness (TileSet bounds, `unique_id` ID collision detection). Have the PITFALLS.md "Looks Done But Isn't" checklist available during this phase. The TileSet fix (#112271, "tiles outside texture") is the most likely source of surprises.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No changes from v1.0 stack; all existing dependencies confirmed correct |
| Features | HIGH | load_steps and unique_id changes verified directly via merged PRs and upgrade guide |
| Architecture | HIGH | All changes map to specific file:line locations verified against codebase structure |
| Pitfalls | HIGH | Critical pitfalls cross-referenced across all 4 research documents; severity ratings confirmed against Godot issue tracker |

**Overall confidence:** HIGH

### Gaps to Address

- **Godot 4.5 tolerates missing `load_steps` — needs E2E confirmation:** Research confirms Godot 4.5 recomputes resource counts from file content (not from `load_steps`), so omission should be safe. This is the single assumption that most needs E2E verification.
- **TileSet atlas bounds strictness in 4.6:** The "tiles outside texture" fix (#112271) may produce stricter validation errors when opening TileSets with imprecise atlas dimensions. Cannot be confirmed without a 4.6.1 binary and a test fixture.
- **`unique_id` integer range and uniqueness contract:** Research confirms 32-bit integer, scene-local. If gdauto uses a sequential counter (1, 2, 3...) vs. CSPRNG, the safety of either approach against Godot's ID allocation needs one round of E2E testing to confirm no collision detection fires.
- **Base64 PackedByteArray constructor name in format=4:** Confirmed that format=4 triggers on PackedVector4Array and large PackedByteArray, but the exact text-format constructor name for base64-encoded PackedByteArray needs verification with an actual 4.6 file. Deferred; lenient parser returns raw string as fallback.

## Sources

### Primary (HIGH confidence)
- [PR #103352: Remove load_steps](https://github.com/godotengine/godot/pull/103352) — load_steps removal implementation and scope
- [PR #106837: Add unique Node IDs](https://github.com/godotengine/godot/pull/106837) — unique_id 32-bit integer attribute on [node] headers
- [Godot resource_format_text.h](https://github.com/godotengine/godot/blob/master/scene/resources/resource_format_text.h) — FORMAT_VERSION=4, FORMAT_VERSION_COMPAT=3
- [Godot resource_uid.cpp](https://github.com/godotengine/godot/blob/master/core/io/resource_uid.cpp) — UID encoding algorithm verified unchanged
- [Godot project_settings.h](https://github.com/godotengine/godot/blob/master/core/config/project_settings.h) — CONFIG_VERSION=5, unchanged
- [Command Line Tutorial (GitHub source)](https://raw.githubusercontent.com/godotengine/godot-docs/master/tutorials/editor/command_line_tutorial.rst) — All existing CLI flags verified unchanged
- [Upgrading 4.5 to 4.6 (GitHub docs source)](https://raw.githubusercontent.com/godotengine/godot-docs/master/tutorials/migrating/upgrading_to_godot_4.6.rst) — Official breaking changes list
- [TSCN format docs (master)](https://github.com/godotengine/godot-docs/blob/master/engine_details/file_formats/tscn.rst) — unique_id documented, load_steps deprecated
- [Godot 4.6.1 maintenance release](https://godotengine.org/article/maintenance-release-godot-4-6-1/) — 38 bug fixes, no format changes

### Secondary (MEDIUM confidence)
- [Issue #115971: Non-deterministic exports in 4.6](https://github.com/godotengine/godot/issues/115971) — "Very Bad" severity; unique_id regeneration on export
- [Issue #112332: Duplicate unique scene resource ID](https://github.com/godotengine/godot/issues/112332) — RNG seed instability in generate_scene_unique_id()
- [Issue #77508: Import race condition with --quit](https://github.com/godotengine/godot/issues/77508) — Still open as of 4.6.1; our --quit-after 30 mitigates
- [GDQuest: Godot 4.6 workflow changes](https://www.gdquest.com/library/godot_4_6_workflow_changes/) — Community analysis of breaking changes
- [PR #85474: PackedVector4Array](https://github.com/godotengine/godot/pull/85474) — format=4 trigger (merged 4.3)
- [PR #89186: Base64 PackedByteArray](https://github.com/godotengine/godot/pull/89186) — format=4 trigger (merged 4.3)

### Tertiary (LOW confidence / informational)
- [Issue #116408: Animation events lost 4.6.0 to 4.6.1](https://github.com/godotengine/godot/issues/116408) — gdauto not affected; informational for users
- [GH-110502: AnimationLibrary serialization change](https://godotengine.org/article/dev-snapshot-godot-4-6-beta-1/) — Dictionary avoidance; gdauto parser handles generically
- [godot-docs#11707: load_steps not in release notes](https://github.com/godotengine/godot-docs/issues/11707) — Confirms change was underdocumented

---
*Research completed: 2026-03-28*
*Ready for roadmap: yes*
