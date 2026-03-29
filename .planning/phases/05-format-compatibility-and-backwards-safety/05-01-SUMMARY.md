---
phase: 05-format-compatibility-and-backwards-safety
plan: 01
subsystem: formats
tags: [godot-4.6, tscn-parser, values-parser, load_steps, unique_id, PackedVector4Array]

# Dependency graph
requires:
  - phase: 03-tileset-automation-and-export-pipeline
    provides: TileSet builder, SpriteFrames builder, scene builder
provides:
  - unique_id field on SceneNode with parse/serialize support
  - PackedVector4Array dataclass with parse/serialize support
  - load_steps=None on all 7 generator call sites
affects: [05-02, golden-file-updates, e2e-tests]

# Tech tracking
tech-stack:
  added: []
  patterns: [load_steps omission for Godot 4.6 forward compatibility]

key-files:
  created: []
  modified:
    - src/gdauto/formats/tscn.py
    - src/gdauto/formats/values.py
    - src/gdauto/sprite/spriteframes.py
    - src/gdauto/sprite/splitter.py
    - src/gdauto/sprite/atlas.py
    - src/gdauto/commands/sprite.py
    - src/gdauto/tileset/builder.py
    - src/gdauto/scene/builder.py
    - tests/unit/test_scene_builder.py
    - tests/unit/test_sprite_split.py
    - tests/unit/test_spriteframes_builder.py
    - tests/unit/test_tileset_builder.py

key-decisions:
  - "Set load_steps=None unconditionally in all generators (not conditional on format version); Godot 4.5 tolerates omission"
  - "unique_id stored as int, not string; Godot uses plain integer in node headers"
  - "PackedVector4Array uses same flat-float pattern as PackedVector2Array"
  - "Updated 4 unit tests to assert load_steps is None rather than computed values"

patterns-established:
  - "Generators always set load_steps=None; parser preserves load_steps from parsed files for inspection"

requirements-completed: [COMPAT-01, COMPAT-02, COMPAT-03, BACK-01]

# Metrics
duration: 6min
completed: 2026-03-29
---

# Phase 5 Plan 1: Format Compatibility and Backwards Safety Summary

**unique_id on SceneNode, PackedVector4Array parser support, and load_steps removal from all 7 generators for Godot 4.6.1 compatibility**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-29T05:04:23Z
- **Completed:** 2026-03-29T05:10:38Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments
- SceneNode now has unique_id field: parsed from [node] headers, emitted during serialization, included in JSON output
- PackedVector4Array dataclass added to values.py with full parse/serialize round-trip support
- All 7 generator call sites (spriteframes, splitter x2, atlas, commands/sprite, tileset, scene) now produce load_steps=None
- 637 unit tests pass (excluding golden file tests which will be updated in Plan 02)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add unique_id to SceneNode and PackedVector4Array to value parser** - `1f9137e` (feat)
2. **Task 2: Remove load_steps from all 7 generator call sites and update validator** - `d5dfa66` (feat)

## Files Created/Modified
- `src/gdauto/formats/tscn.py` - Added unique_id field to SceneNode, extraction in _extract_node, emission in _build_tscn_from_model, inclusion in to_dict
- `src/gdauto/formats/values.py` - Added PackedVector4Array dataclass, added to _GODOT_TYPES, added parser handler
- `src/gdauto/sprite/spriteframes.py` - Set load_steps=None, removed computation
- `src/gdauto/sprite/splitter.py` - Set load_steps=None in both split_sheet_grid and split_sheet_json
- `src/gdauto/sprite/atlas.py` - Set load_steps=None in _build_atlas_resource
- `src/gdauto/commands/sprite.py` - Set load_steps=None in _build_resource
- `src/gdauto/tileset/builder.py` - Set load_steps=None (was hardcoded 3)
- `src/gdauto/scene/builder.py` - Set load_steps=None (was conditional computation)
- `tests/unit/test_scene_builder.py` - Updated test to assert load_steps is None
- `tests/unit/test_sprite_split.py` - Updated test to assert load_steps is None
- `tests/unit/test_spriteframes_builder.py` - Updated test to assert load_steps is None
- `tests/unit/test_tileset_builder.py` - Updated test to assert load_steps is None

## Decisions Made
- Set load_steps=None unconditionally in all generators (not conditional on format version); Godot 4.5 tolerates omission per D-01 and BACK-01
- unique_id stored as int (not string); Godot uses plain integer in node headers (no quotes)
- PackedVector4Array follows same flat-float tuple pattern as PackedVector2Array
- Updated 4 existing unit tests that asserted specific load_steps values to assert None instead

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated 4 unit tests asserting load_steps values**
- **Found during:** Task 2 (load_steps removal)
- **Issue:** Unit tests for scene builder, sprite split, spriteframes builder, and tileset builder asserted specific load_steps numeric values that are now None
- **Fix:** Updated test assertions from computed values to `assert resource.load_steps is None`
- **Files modified:** tests/unit/test_scene_builder.py, tests/unit/test_sprite_split.py, tests/unit/test_spriteframes_builder.py, tests/unit/test_tileset_builder.py
- **Verification:** All 637 unit tests pass
- **Committed in:** d5dfa66 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix for test assertions)
**Impact on plan:** Test updates were a direct consequence of the load_steps removal. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all functionality is fully wired.

## Next Phase Readiness
- Golden file tests (excluded in this plan) will need updating in Plan 02 since generated output no longer contains load_steps
- unique_id round-trip verified; parser tests already pass
- PackedVector4Array parses and serializes correctly; format=4 files with this type are now supported

---
*Phase: 05-format-compatibility-and-backwards-safety*
*Completed: 2026-03-29*
