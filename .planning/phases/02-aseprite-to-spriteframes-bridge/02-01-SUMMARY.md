---
phase: 02-aseprite-to-spriteframes-bridge
plan: 01
subsystem: sprite
tags: [aseprite, spriteframes, json-parser, atlas-texture, animation, godot-tres]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: GdResource/ExtResource/SubResource dataclasses, serialize_tres, Rect2/StringName/ExtResourceRef/SubResourceRef value types, generate_uid/uid_to_text/generate_resource_id, ValidationError
provides:
  - Aseprite JSON parser (parse_aseprite_json) with AsepriteData, AsepriteFrame, AsepriteTag, AsepriteMeta, AniDirection, FrameRect dataclasses
  - SpriteFrames GdResource builder (build_spriteframes) with build_animation_for_tag, compute_animation_timing, expand_pingpong, expand_pingpong_reverse, compute_margin
  - 6 Aseprite JSON test fixtures for downstream testing
affects: [02-02, 02-03, 02-04, sprite-cli]

# Tech tracking
tech-stack:
  added: []
  patterns: [frozen-dataclass-enum-pattern, gcd-based-animation-timing, spatial-sort-for-hash-format]

key-files:
  created:
    - src/gdauto/formats/aseprite.py
    - src/gdauto/sprite/__init__.py
    - src/gdauto/sprite/spriteframes.py
    - tests/unit/test_aseprite_parser.py
    - tests/unit/test_spriteframes_builder.py
    - tests/fixtures/aseprite_simple.json
    - tests/fixtures/aseprite_hash.json
    - tests/fixtures/aseprite_trimmed.json
    - tests/fixtures/aseprite_pingpong.json
    - tests/fixtures/aseprite_variable_duration.json
    - tests/fixtures/aseprite_no_tags.json
  modified: []

key-decisions:
  - "AniDirection enum mirrors Aseprite's string values for direct mapping"
  - "Hash format frames sorted by (x, y) position for consistent ordering"
  - "build_animation_for_tag is public to support per-tag partial failure handling in Plan 02"
  - "compute_margin returns None for untrimmed frames rather than zero Rect2"

patterns-established:
  - "Frozen dataclass + Enum pattern for Aseprite domain models (matches Phase 1 convention)"
  - "GCD-based FPS computation: reduce(math.gcd, durations) to find base FPS, then per-frame multipliers"
  - "Builder function delegates per-tag work to stay under 30-line limit"

requirements-completed: [SPRT-01, SPRT-02, SPRT-03, SPRT-04, SPRT-05, SPRT-06, SPRT-12]

# Metrics
duration: 7min
completed: 2026-03-28
---

# Phase 02 Plan 01: Aseprite Parser and SpriteFrames Builder Summary

**Aseprite JSON parser with array/hash auto-detection and SpriteFrames GdResource builder with all 4 animation directions, GCD-based timing, and trimmed sprite margins**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-28T06:12:51Z
- **Completed:** 2026-03-28T06:19:50Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- Aseprite JSON parser handles both array and hash frame formats with auto-detection and spatial sorting
- SpriteFrames builder produces GdResource instances that serialize to valid Godot .tres format (verified via round-trip parse)
- All 4 animation directions (forward, reverse, pingpong, pingpong_reverse) produce correct frame sequences
- GCD-based timing handles both uniform and variable frame durations
- Trimmed sprite margins compute correctly as Rect2 values
- 63 tests (28 parser + 35 builder) all passing; 375 total suite tests pass with zero regressions

## Task Commits

Each task was committed atomically (TDD: red then green):

1. **Task 1: Aseprite JSON parser and test fixtures**
   - `990d539` (test: failing tests + 6 fixtures)
   - `b2d83f8` (feat: Aseprite parser implementation)
2. **Task 2: SpriteFrames GdResource builder**
   - `563d17a` (test: failing tests for builder)
   - `8e90e05` (feat: SpriteFrames builder implementation)

## Files Created/Modified
- `src/gdauto/formats/aseprite.py` - Aseprite JSON parser with 6 dataclasses and parse_aseprite_json
- `src/gdauto/sprite/__init__.py` - Sprite package init
- `src/gdauto/sprite/spriteframes.py` - SpriteFrames GdResource builder with 6 public functions
- `tests/unit/test_aseprite_parser.py` - 28 tests for parser (array, hash, trimmed, directions, errors, warnings)
- `tests/unit/test_spriteframes_builder.py` - 35 tests for builder (timing, expansion, margin, per-tag, full pipeline, round-trip)
- `tests/fixtures/aseprite_simple.json` - 4-frame forward animation, array format
- `tests/fixtures/aseprite_hash.json` - Same content, hash format (auto-detection test)
- `tests/fixtures/aseprite_trimmed.json` - 2 trimmed frames with spriteSourceSize offsets
- `tests/fixtures/aseprite_pingpong.json` - 4 frames with pingpong and pingpong_reverse tags
- `tests/fixtures/aseprite_variable_duration.json` - 3 frames with [100, 200, 100] ms durations
- `tests/fixtures/aseprite_no_tags.json` - 3 frames with no frameTags (tests default animation)

## Decisions Made
- AniDirection enum values match Aseprite's exact strings for zero-translation parsing
- Hash format frames sorted by (x, y) spatial position, not dict key order, for reliable frame sequencing
- build_animation_for_tag exposed as public function (not inlined) for Plan 02 per-tag failure handling
- compute_margin returns None for untrimmed frames, avoiding unnecessary zero-margin Rect2 in output
- String repeat field (Aseprite Pitfall 4) converted via int() with default "0"

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - all data paths are fully wired.

## Next Phase Readiness
- Aseprite parser and SpriteFrames builder are ready for Plan 02 (CLI command wiring)
- All test fixtures available for downstream integration testing
- build_animation_for_tag public API ready for per-tag error handling in Plan 02

## Self-Check: PASSED

All 11 created files verified present. All 4 commit hashes verified in git log.

---
*Phase: 02-aseprite-to-spriteframes-bridge*
*Completed: 2026-03-28*
