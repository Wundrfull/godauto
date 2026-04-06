---
phase: 07-variant-codec-and-tcp-connection
plan: 01
subsystem: debugger-codec
tags: [variant, binary-protocol, codec, tdd, debugger]
dependency_graph:
  requires: []
  provides: [variant-codec, debugger-errors, debugger-models]
  affects: [debugger-protocol, debugger-session]
tech_stack:
  added: []
  patterns: [struct-based-binary-encoding, tdd-red-green, dispatch-pattern]
key_files:
  created:
    - src/gdauto/debugger/__init__.py
    - src/gdauto/debugger/variant.py
    - src/gdauto/debugger/errors.py
    - src/gdauto/debugger/models.py
    - tests/unit/test_variant.py
  modified: []
decisions:
  - "Used sentinel object pattern (_NOT_FOUND) for decode dispatch to avoid conflicting with None return from NIL decode"
  - "Split encode/decode into multi-function dispatch chains to comply with 30-line function limit while handling 24+ type IDs"
  - "NodePath encoding uses Godot new format exclusively (MSB set on name_count); legacy format raises ProtocolError"
  - "FLOAT always encodes as 64-bit double (ENCODE_FLAG_64 set); decoder handles both 32-bit and 64-bit"
metrics:
  duration: 11m
  completed: "2026-04-06"
  tasks: 2
  files: 5
  test_count: 137
---

# Phase 7 Plan 1: Variant Binary Codec Summary

Godot 4.x Variant binary encoder/decoder with 137 golden-byte tests covering 24+ types, debugger error hierarchy, and type-safe model wrappers, all stdlib with zero new dependencies.

## What Was Built

### Variant Codec (src/gdauto/debugger/variant.py, 733 lines)
- `encode(value, type_hint=None) -> bytes`: Encodes Python values to Godot binary Variant format
- `decode(data, offset=0) -> (value, bytes_consumed)`: Decodes Godot binary Variant data back to Python
- `VariantType(IntEnum)`: All 39 Godot 4.x type IDs (0-38 from variant.h)
- 13 MUST types: NIL, BOOL, INT, FLOAT, STRING, VECTOR2, VECTOR3, COLOR, STRING_NAME, NODE_PATH, ARRAY, DICTIONARY, OBJECT
- 11 SHOULD types: VECTOR2I, RECT2, RECT2I, VECTOR3I, TRANSFORM2D, BASIS, RID, PACKED_BYTE_ARRAY, PACKED_INT32_ARRAY, PACKED_FLOAT32_ARRAY, PACKED_STRING_ARRAY
- Handles ENCODE_FLAG_64 for int (32/64-bit based on range) and float (always 64-bit)
- Handles typed Array/Dictionary container metadata (Godot 4.4+)
- NodePath new format with names, subnames, and absolute flag

### Error Hierarchy (src/gdauto/debugger/errors.py)
- `DebuggerError(GdautoError)`: Base debugger error
- `DebuggerConnectionError(DebuggerError)`: TCP connection failures
- `DebuggerTimeoutError(DebuggerError)`: Command response timeouts
- `ProtocolError(DebuggerError)`: Encoding/decoding/message errors

### Model Wrappers (src/gdauto/debugger/models.py)
- `GodotStringName`: Distinguishes StringName from plain str for type 21 encoding
- `GodotNodePath`: Distinguishes NodePath from plain str for type 22 encoding

### Test Suite (tests/unit/test_variant.py, 137 tests)
- Golden-byte tests for every supported type (byte-exact encoding verification)
- Round-trip tests for all types (encode then decode)
- Error handling tests (truncated data, unknown type ID, empty input)
- Flag handling tests (32/64-bit int/float, typed container metadata)
- Parametrized string padding boundary tests (lengths 0-8)

## Commits

| Task | Type | Hash | Description |
|------|------|------|-------------|
| 1 | test | f30a1f8 | RED phase: 137 tests (106 failing) with stub encode/decode |
| 2 | feat | 1108d9b | GREEN phase: full encode/decode implementation, all 137 pass |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Function length violations**
- **Found during:** Task 2 implementation
- **Issue:** encode() (80 lines), decode() (70 lines), _encode_node_path() (36 lines), _decode_node_path() (42 lines) exceeded the 30-line maximum from CLAUDE.md
- **Fix:** Split into dispatch helper functions: _encode_with_type_hint(), _encode_by_type(), _dispatch_scalar(), _dispatch_composite(), _dispatch_packed(), _parse_node_path(), _read_string_list(), _assemble_node_path()
- **Files modified:** src/gdauto/debugger/variant.py
- **Commit:** 1108d9b

## Known Stubs

None. All encode/decode paths are fully implemented for the 24 supported types.

## Verification Results

1. `uv run pytest tests/unit/test_variant.py -v`: 137 passed
2. `from gdauto.debugger.variant import encode, decode, VariantType`: import ok
3. `from gdauto.debugger.errors import DebuggerError, ProtocolError`: errors ok
4. `decode(encode(42)) == (42, 8)`: round-trip ok
5. `encode(None) == b'\x00\x00\x00\x00'`: nil golden byte ok

## Self-Check: PASSED

All 6 files found. Both commits (f30a1f8, 1108d9b) verified in git log.
