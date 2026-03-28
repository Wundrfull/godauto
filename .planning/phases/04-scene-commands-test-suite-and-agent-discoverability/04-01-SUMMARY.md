---
phase: 04-scene-commands-test-suite-and-agent-discoverability
plan: 01
subsystem: scene
tags: [tscn, scene-builder, scene-lister, cli, click, rich-tree]

# Dependency graph
requires:
  - phase: 01-foundation-and-cli-infrastructure
    provides: "Godot file format parser (tscn.py, tres.py, values.py, common.py, uid.py), CLI framework (click groups, output.py, errors.py)"
provides:
  - "build_scene() JSON dict to GdScene conversion with parent path computation"
  - "list_scenes() project directory enumeration with metadata (scripts, instances, dependencies)"
  - "scene create CLI subcommand (JSON definition to .tscn + .uid)"
  - "scene list CLI subcommand (project dir to scene metadata with --depth)"
  - "Parser fix for constructor-form header attributes (instance=ExtResource())"
affects: [04-02, 04-03]

# Tech tracking
tech-stack:
  added: [rich.tree]
  patterns: [scene-builder-pattern, project-directory-walker, constructor-attr-parsing]

key-files:
  created:
    - src/gdauto/scene/__init__.py
    - src/gdauto/scene/builder.py
    - src/gdauto/scene/lister.py
    - tests/unit/test_scene_builder.py
    - tests/unit/test_scene_list.py
    - tests/unit/test_scene_commands.py
    - tests/fixtures/scene_definition.json
  modified:
    - src/gdauto/commands/scene.py
    - src/gdauto/formats/common.py

key-decisions:
  - "Recursive _collect_children with parent path tracking for arbitrary nesting depth"
  - "Constructor-form header attributes parsed via dedicated regex before quoted/unquoted patterns"
  - "Instance resolution by string parsing of ExtResource() refs from header attrs"

patterns-established:
  - "Scene builder pattern: validate definition, flatten tree, build ext_resources, assign to nodes"
  - "Project directory walker: rglob for .tscn files, parse each, summarize metadata"
  - "Constructor attribute regex: _ATTR_CONSTRUCTOR_RE checked before _ATTR_QUOTED_RE in parse_section_header"

requirements-completed: [SCEN-01, SCEN-02]

# Metrics
duration: 8min
completed: 2026-03-28
---

# Phase 04 Plan 01: Scene Commands Summary

**Scene list and create commands with JSON-to-tscn builder, project directory lister, and 40 passing tests**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-28T23:44:57Z
- **Completed:** 2026-03-28T23:53:25Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments
- Scene builder converts arbitrary-depth JSON node trees to valid GdScene with correct Godot parent paths
- Scene lister walks Godot project directories, detects scripts, resolves instanced scene references
- Full CLI with scene create (JSON input, .tscn + .uid output) and scene list (--depth, --json)
- Fixed parser to correctly handle constructor-form header attributes like instance=ExtResource("id")
- 40 new tests (17 builder + 9 lister + 14 CLI integration), 627 total with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Scene builder and lister modules with unit tests** - `2ab3da7` (test: RED), `7f3ea37` (feat: GREEN)
2. **Task 2: Scene list and scene create CLI commands** - `25d2ec7` (feat)
3. **Task 3: Scene CLI integration tests** - `efb55da` (test)

_Note: Task 1 used TDD with separate RED/GREEN commits_

## Files Created/Modified
- `src/gdauto/scene/__init__.py` - Empty package marker for scene module
- `src/gdauto/scene/builder.py` - build_scene() converts JSON definitions to GdScene instances
- `src/gdauto/scene/lister.py` - list_scenes() enumerates .tscn files with metadata
- `src/gdauto/commands/scene.py` - scene list and scene create CLI subcommands
- `src/gdauto/formats/common.py` - Fixed constructor-form attribute parsing in section headers
- `tests/unit/test_scene_builder.py` - 17 unit tests for build_scene()
- `tests/unit/test_scene_list.py` - 9 unit tests for list_scenes()
- `tests/unit/test_scene_commands.py` - 14 CLI integration tests via CliRunner
- `tests/fixtures/scene_definition.json` - Test fixture with nested hierarchy and script resource

## Decisions Made
- Recursive _collect_children approach for tree flattening (simpler than iterative, handles arbitrary depth)
- Instance resolution by string parsing rather than requiring parse_value() on header attrs (preserves existing parser behavior)
- Constructor attribute regex added to common.py header parser (priority over quoted/unquoted matchers)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed parser header attribute parsing for constructor values**
- **Found during:** Task 1 (scene lister tests)
- **Issue:** Parser's parse_section_header() could not correctly capture constructor-form attribute values like `instance=ExtResource("1_player")`. The unquoted regex stopped at the `(` character, producing `ExtResource(` instead of the full value.
- **Fix:** Added `_ATTR_CONSTRUCTOR_RE` pattern matching `key=Type("value")` and checked it before the existing quoted/unquoted patterns in parse_section_header().
- **Files modified:** src/gdauto/formats/common.py
- **Verification:** Instance resolution test passes; all 627 existing tests pass with no regressions
- **Committed in:** 7f3ea37 (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking issue)
**Impact on plan:** Essential parser fix for instance node detection. No scope creep.

## Issues Encountered
None beyond the parser fix documented above.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all functionality is fully wired with no placeholder data.

## Next Phase Readiness
- Scene builder and lister provide the foundation for any future scene-related commands
- Parser improvement benefits all .tscn parsing, particularly for scene files with instance nodes
- Ready for plan 04-02 (SKILL.md generation) and 04-03 (E2E test suite)

## Self-Check: PASSED

All 8 created files verified present. All 4 commit hashes verified in git log.

---
*Phase: 04-scene-commands-test-suite-and-agent-discoverability*
*Completed: 2026-03-28*
