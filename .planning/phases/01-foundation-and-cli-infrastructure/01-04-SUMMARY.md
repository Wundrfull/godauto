---
phase: 01-foundation-and-cli-infrastructure
plan: 04
subsystem: formats, backend
tags: [parser, project.godot, godot-binary, subprocess, round-trip, state-machine]

# Dependency graph
requires:
  - phase: 01-01
    provides: "GdautoError, GodotBinaryError, ParseError error hierarchy"
provides:
  - "project.godot custom parser with round-trip fidelity (parse_project_config, serialize_project_config, ProjectConfig)"
  - "GodotBackend wrapper with binary discovery (flag > env > PATH), version validation (>= 4.5), and headless subprocess management"
affects: [01-05-project-commands, 02-aseprite-bridge, 03-tileset-automation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Line-based state machine parser (GLOBAL/SECTION/MULTILINE) for INI-like formats"
    - "Raw string value storage at parser layer; interpretation deferred to command layer"
    - "Lazy binary discovery with cached version validation"
    - "Dataclass with _raw_lines for perfect round-trip serialization"

key-files:
  created:
    - src/gdauto/formats/project_cfg.py
    - src/gdauto/backend.py
    - tests/unit/test_project_cfg.py
    - tests/unit/test_backend.py
    - tests/fixtures/sample_project/project.godot
    - tests/fixtures/sample_project/icon.svg
  modified: []

key-decisions:
  - "Custom line-based state machine parser over configparser: handles global keys, Godot constructors, bracket-balanced multi-line values that configparser cannot"
  - "Raw string value storage in project_cfg.py: values like PackedStringArray(...) are preserved as-is, deferring interpretation to command layer (D-04)"
  - "Lazy binary discovery: GodotBackend does not search PATH until ensure_binary() is called, avoiding unnecessary overhead for file-only commands"

patterns-established:
  - "State machine parser pattern: _State enum with GLOBAL/SECTION/MULTILINE transitions, bracket depth tracking with string escape awareness"
  - "Round-trip fidelity via _raw_lines: store original lines at parse time, replay them on serialize"
  - "Binary wrapper pattern: lazy discovery + cached validation + structured error with fix suggestions"

requirements-completed: [PROJ-05, TEST-01]

# Metrics
duration: 6min
completed: 2026-03-28
---

# Phase 01 Plan 04: Project Config Parser and Godot Backend Summary

**Custom project.godot state machine parser with round-trip fidelity and GodotBackend wrapper with flag > env > PATH discovery and >= 4.5 version validation**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-28T01:07:46Z
- **Completed:** 2026-03-28T01:13:19Z
- **Tasks:** 2
- **Files created:** 6

## Accomplishments
- project.godot parser handles global keys, sections, Godot constructors, multi-line bracket-balanced values, semicolon comments, and passes round-trip fidelity test
- GodotBackend discovers binary via explicit path > GODOT_PATH env > shutil.which, validates version >= 4.5, caches result, and raises structured GodotBinaryError with actionable fix suggestions
- 35 total tests (20 parser + 15 backend), all passing with mocked subprocess

## Task Commits

Each task was committed atomically (TDD: test then feat):

1. **Task 1: project.godot parser** - `65534cf` (test: RED) + `5264a3d` (feat: GREEN)
2. **Task 2: GodotBackend wrapper** - `d5ee8e2` (test: RED) + `2a5e735` (feat: GREEN)

_TDD flow: each task had separate RED (failing tests) and GREEN (implementation) commits._

## Files Created/Modified
- `src/gdauto/formats/project_cfg.py` (222 lines) - Custom line-based state machine parser for project.godot with ProjectConfig dataclass, parse_project_config, serialize_project_config
- `src/gdauto/backend.py` (171 lines) - Godot binary wrapper with discovery, version validation, headless subprocess invocation, check_only, import_resources
- `tests/unit/test_project_cfg.py` (176 lines) - 20 tests covering global keys, sections, value preservation, multi-line, comments, round-trip, to_dict
- `tests/unit/test_backend.py` (197 lines) - 15 tests covering discovery priority, version validation, caching, run command construction, error handling, check_only
- `tests/fixtures/sample_project/project.godot` - Known-good project.godot with all edge cases (global keys, constructors, multi-line Object values)
- `tests/fixtures/sample_project/icon.svg` - Minimal SVG placeholder for sample project

## Decisions Made
- Custom line-based parser over configparser: handles global keys before sections, Godot constructor values, and bracket-balanced multi-line values that configparser cannot handle
- Raw string storage for all values: project_cfg.py does not interpret values like PackedStringArray(...); interpretation is deferred to command layer per D-04
- Lazy binary discovery in GodotBackend: PATH/env lookup happens on first ensure_binary() call, not at __init__ time

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed platform-dependent path assertion in test_backend.py**
- **Found during:** Task 2 (GodotBackend implementation)
- **Issue:** Test asserted `"/my/project" in cmd` but on Windows, Path("/my/project") serializes with backslashes
- **Fix:** Changed assertion to `str(Path("/my/project")) in cmd` for cross-platform compatibility
- **Files modified:** tests/unit/test_backend.py
- **Verification:** Test passes on Windows
- **Committed in:** 2a5e735 (Task 2 feat commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor platform fix. No scope creep.

## Issues Encountered
- Worktree needed dev dependencies installed separately (`uv pip install -e ".[dev]"`); `uv sync --group dev` does not work with optional-dependencies (only dependency-groups)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- project_cfg.py and backend.py are ready for Plan 05 (project info and project validate commands)
- ProjectConfig.to_dict() provides JSON-serializable output for `project info --json`
- GodotBackend.check_only() provides the engine for `project validate --check-only`
- No blockers

## Self-Check: PASSED

All 6 created files exist. All 4 commit hashes verified in git log.

---
*Phase: 01-foundation-and-cli-infrastructure*
*Completed: 2026-03-28*
