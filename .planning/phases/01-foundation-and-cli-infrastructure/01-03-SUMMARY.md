---
phase: 01-foundation-and-cli-infrastructure
plan: 03
subsystem: formats
tags: [parser, tscn, tres, uid, round-trip, state-machine, base-34, dataclass]

# Dependency graph
requires:
  - phase: 01-02
    provides: "Godot value type dataclasses with parse_value/serialize_value for property parsing"
provides:
  - "Shared bracket-section parser (parse_sections, serialize_sections) for .tres/.tscn format=3"
  - "GdResource dataclass with parse_tres/serialize_tres for .tres files"
  - "GdScene dataclass with parse_tscn/serialize_tscn for .tscn files"
  - "ExtResource, SubResource, SceneNode, Connection dataclasses"
  - "UID generation and base-34 encoding/decoding (uid_to_text, text_to_uid)"
  - "Resource ID generation in Type_xxxxx format (generate_resource_id)"
  - ".uid companion file read/write"
  - "to_dict() methods for JSON-serializable output on GdResource and GdScene"
affects: [02-aseprite-bridge, 03-tileset-terrain, 04-scenes-validation]

# Tech tracking
tech-stack:
  added: [secrets]
  patterns: [state-machine-parser, raw-line-roundtrip, dual-storage-properties, bracket-depth-tracking]

key-files:
  created:
    - src/gdauto/formats/common.py
    - src/gdauto/formats/uid.py
    - src/gdauto/formats/tres.py
    - src/gdauto/formats/tscn.py
    - tests/unit/test_uid.py
    - tests/unit/test_tres_parser.py
    - tests/unit/test_tscn_parser.py
    - tests/fixtures/sample.tres
    - tests/fixtures/sample.tscn
  modified: []

key-decisions:
  - "UID encoding uses prepend (not append) to match Godot's id_to_text C++ algorithm, producing MSB-first output"
  - "HeaderAttributes stores raw_line for byte-identical round-trip header serialization"
  - "Properties stored as dual (parsed, raw) tuples; raw strings used for serialization, parsed values for inspection"
  - "ExtResource and SubResource defined in tres.py, imported by tscn.py (shared data models per D-06)"

patterns-established:
  - "Raw-line round-trip: section headers store original text to avoid reordering or requoting on serialization"
  - "Dual property storage: (key, parsed_value) for access + (key, raw_string) for round-trip fidelity"
  - "Bracket depth tracking with string-escape awareness for multi-line value accumulation"
  - "parse_X / serialize_X function pairs per format module (tres.py, tscn.py)"

requirements-completed: [FMT-01, FMT-02, FMT-04, FMT-05, FMT-06, TEST-01]

# Metrics
duration: 8min
completed: 2026-03-28
---

# Phase 1 Plan 3: Custom Parser Summary

**State-machine .tscn/.tres parser with bracket-depth tracking, base-34 UID encoding, and byte-identical round-trip fidelity via raw-line preservation**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-28T01:07:43Z
- **Completed:** 2026-03-28T01:15:45Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Built shared bracket-section parser (common.py) with line-by-line state machine handling IDLE, PROPERTIES, and MULTILINE states
- Implemented base-34 UID encoding/decoding matching Godot's exact algorithm (prepend-based, a-y + 0-8 character set, no z or 9)
- Achieved byte-identical round-trip on both sample.tres and sample.tscn fixture files
- 85 tests covering UID round-trip, header parsing, bracket depth, multi-line values, comment preservation, to_dict serialization

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement shared bracket-section parser, UID module, and resource ID generation** - `180712d` (feat)
2. **Task 2: Implement .tres and .tscn parsers with round-trip fidelity tests** - `49721ca` (feat)

## Files Created/Modified
- `src/gdauto/formats/common.py` - Shared bracket-section parser: HeaderAttributes, Section, parse_sections, serialize_sections with bracket depth tracking
- `src/gdauto/formats/uid.py` - UID generation (base-34 encoding), resource ID generation (Type_xxxxx), .uid file I/O
- `src/gdauto/formats/tres.py` - .tres parser/serializer: GdResource, ExtResource, SubResource, parse_tres, serialize_tres
- `src/gdauto/formats/tscn.py` - .tscn parser/serializer: GdScene, SceneNode, Connection, parse_tscn, serialize_tscn
- `tests/unit/test_uid.py` - 38 tests for UID, resource ID, section header parsing, bracket depth, multi-line values
- `tests/unit/test_tres_parser.py` - 23 tests for .tres parsing, round-trip, comments, unknown sections, to_dict
- `tests/unit/test_tscn_parser.py` - 24 tests for .tscn parsing, round-trip, nodes, connections, to_dict
- `tests/fixtures/sample.tres` - SpriteFrames .tres fixture with ext_resources, sub_resources, multi-line animations array
- `tests/fixtures/sample.tscn` - Character scene .tscn fixture with nodes, connections, ext_resources

## Decisions Made
- **UID prepend algorithm:** Research documentation showed an append-based algorithm, but testing against the known UID string "uid://cecaux1sm7mo0" revealed a round-trip failure. Analysis of Godot's C++ source (resource_uid.cpp) confirmed the algorithm prepends each character, producing MSB-first output. Fixed to match.
- **Raw header line storage:** To avoid attribute reordering and quoting discrepancies during round-trip serialization, HeaderAttributes stores the original raw_line string. The _format_header function uses this raw line when available, falling back to reconstruction only when raw_line is empty.
- **Dual property storage pattern:** Each property is stored as both (key, parsed_value) and (key, raw_string). Parsed values enable typed access (Vector2 arithmetic, etc.); raw strings enable exact round-trip serialization without re-serializing through serialize_value.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed UID encoding algorithm (append to prepend)**
- **Found during:** Task 1 (UID module implementation)
- **Issue:** Research code used append-based encoding (LSB-first output), but Godot's actual C++ source uses prepend (MSB-first output). Round-trip test with known UID string failed.
- **Fix:** Changed uid_to_text to prepend each character instead of append, matching Godot's id_to_text algorithm
- **Files modified:** src/gdauto/formats/uid.py
- **Verification:** Known UID "uid://cecaux1sm7mo0" round-trips correctly; 100 random UIDs round-trip
- **Committed in:** 180712d (Task 1 commit)

**2. [Rule 1 - Bug] Added raw_line to HeaderAttributes for round-trip header fidelity**
- **Found during:** Task 2 (round-trip test failure)
- **Issue:** _format_header reconstructed headers from attrs dict, losing original attribute order and quoting style. Round-trip test failed because "load_steps=3 format=3 uid=..." became "uid=... load_steps=3 format=3"
- **Fix:** Added raw_line field to HeaderAttributes, stored during parsing. _format_header uses raw_line when available.
- **Files modified:** src/gdauto/formats/common.py
- **Verification:** sample.tres and sample.tscn round-trip byte-identical
- **Committed in:** 49721ca (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes were necessary for round-trip fidelity (FMT-06). The UID algorithm bug was a research documentation error; the header ordering issue was an implementation gap. No scope creep.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all parser functions are fully implemented with real logic and tested against fixture files.

## Next Phase Readiness
- Parser infrastructure is complete and ready for Phase 2 (Aseprite bridge)
- parse_tres and serialize_tres provide the foundation for generating SpriteFrames .tres files
- ExtResource, SubResource, and GdResource dataclasses are the building blocks for resource creation
- UID and resource ID generators ready for new resource creation workflows

## Self-Check: PASSED

- All 9 created files exist on disk
- Commit 180712d found in git log
- Commit 49721ca found in git log
- 85/85 tests passing

---
*Phase: 01-foundation-and-cli-infrastructure*
*Completed: 2026-03-28*
