---
phase: 02-aseprite-to-spriteframes-bridge
plan: 02
subsystem: cli
tags: [click, aseprite, spriteframes, tres, cli-command]

# Dependency graph
requires:
  - phase: 02-01
    provides: "Aseprite JSON parser, SpriteFrames builder, .tres serializer"
provides:
  - "import-aseprite CLI subcommand (gdauto sprite import-aseprite)"
  - "SPRT-11 import guide as built-in --help text"
  - "Partial failure handling for invalid animation tags (D-17)"
  - "JSON output mode for structured import results"
affects: [02-03, 02-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-tag partial failure with warnings on stderr"
    - "Lenient parser that skips invalid tags instead of failing"
    - "warnings.catch_warnings for capturing parser-level warnings in CLI"

key-files:
  created:
    - tests/unit/test_sprite_import_command.py
  modified:
    - src/gdauto/commands/sprite.py
    - src/gdauto/formats/aseprite.py

key-decisions:
  - "Made aseprite parser lenient on invalid tag directions (skip with warning) to support D-17 partial failure without breaking existing parser API"
  - "All-tags-failed detection uses warning count + empty frame_tags to distinguish from genuinely tagless JSON"

patterns-established:
  - "CLI command import guide pattern: comprehensive docstring with \\b sections for SETTINGS, OPTIONS, PITFALLS, EXAMPLES"
  - "Partial failure pattern: parser skips invalid items, command captures warnings, outputs valid result with warnings on stderr"

requirements-completed: [SPRT-07, SPRT-11]

# Metrics
duration: 6min
completed: 2026-03-28
---

# Phase 02 Plan 02: CLI Command Wiring Summary

**import-aseprite CLI subcommand with import guide help text, partial failure handling, and JSON output mode**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-28T06:24:57Z
- **Completed:** 2026-03-28T06:31:17Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments
- Wired `gdauto sprite import-aseprite` CLI command connecting parser, builder, and serializer
- Comprehensive import guide in --help with Aseprite export settings, common pitfalls, and examples (SPRT-11)
- Per-tag partial failure: invalid tags skipped with warnings, valid tags still produce output (D-17)
- JSON output mode with output_path, animation_count, frame_count, image_path, warnings
- All 19 CLI integration tests passing; full suite of 394 tests passing with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): failing tests** - `e84513d` (test)
2. **Task 1 (GREEN): import-aseprite implementation** - `f3784c4` (feat)

_TDD task with RED and GREEN commits._

## Files Created/Modified
- `src/gdauto/commands/sprite.py` - import-aseprite subcommand with --output, --res-path options, import guide help text, partial failure handling
- `src/gdauto/formats/aseprite.py` - Made _parse_meta lenient on invalid tags (skip with warning instead of raising)
- `tests/unit/test_sprite_import_command.py` - 19 CLI integration tests covering basic usage, options, JSON mode, errors, help text, and partial failure

## Decisions Made
- Made aseprite parser lenient on invalid tag directions: `_parse_meta` now catches `ValidationError` from `_parse_tag` and skips invalid tags with a `warnings.warn()` call, rather than raising and aborting. This supports D-17 partial failure semantics without breaking the parser's existing public API.
- All-tags-failed detection: when warnings were captured AND `frame_tags` is empty after parsing, the command infers all tags were invalid and exits non-zero. This correctly distinguishes from genuinely tagless JSON (no frameTags key), which falls through to "default" animation creation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Made aseprite parser lenient on invalid tag directions**
- **Found during:** Task 1 (implementing partial failure tests)
- **Issue:** `parse_aseprite_json` raised `ValidationError` on any invalid tag direction, preventing per-tag partial failure handling in the command. The command could never see partially-parsed data.
- **Fix:** Changed `_parse_meta` to catch `ValidationError` from `_parse_tag` and skip invalid tags with `warnings.warn()`. Valid tags still parse normally; invalid ones are filtered out with a warning message.
- **Files modified:** `src/gdauto/formats/aseprite.py`
- **Verification:** Partial failure test passes (valid tags produce .tres, invalid tags filtered); existing parser tests still pass (394 total)
- **Committed in:** f3784c4 (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary change to support D-17 partial failure semantics. No scope creep; the change makes the parser more robust.

## Issues Encountered
- `rich_click.testing.CliRunner` does not accept `mix_stderr=False` like standard Click's CliRunner. Adjusted partial failure test to not rely on separate stderr capture, instead checking .tres content for correct tag filtering.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- import-aseprite command is fully functional end-to-end
- Ready for Plan 03 (Godot validation with E2E tests) and Plan 04 (edge cases and error polish)
- Parser's lenient tag handling enables future error-tolerant workflows

## Known Stubs
None - all data paths are fully wired.

## Self-Check: PASSED

- All 3 created/modified files exist on disk
- Both task commits (e84513d, f3784c4) found in git log
- 394 tests passing across full test suite
