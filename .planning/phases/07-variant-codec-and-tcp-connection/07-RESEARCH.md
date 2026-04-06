# Phase 7: Variant Codec and TCP Connection - Research

**Researched:** 2026-04-05
**Domain:** Godot remote debugger binary protocol, Variant encoding/decoding, async TCP server, game process management
**Confidence:** HIGH (protocol details verified from Godot C++ source, VS Code plugin TypeScript reference, and PlayGodot Python reference implementation)

## Summary

Phase 7 builds the binary protocol foundation for live game interaction. This requires three tightly coupled components: (1) a Variant binary codec that encodes/decodes Godot's 39 type IDs with byte-exact fidelity, (2) a TCP server that accepts incoming connections from a Godot game launched with `--remote-debug`, and (3) connection lifecycle management including game launch, readiness detection, unsolicited message draining, and clean disconnect.

The most important finding from this research is a critical correction to the wire protocol format documented in the earlier project research. The message format over the wire is a **3-element Array: [command_name: String, thread_id: int, data: Array]**, not a 2-element array. This was confirmed directly from `remote_debugger.cpp` source (`_put_msg` function) and corroborated by the PlayGodot reference implementation. The earlier ARCHITECTURE.md documented the message as `[message_type, ...payload]` which would produce silent message drops from Godot's parser. Additionally, the Godot 4.x Variant type IDs are significantly different from Godot 3.x; the earlier research listed Godot 3 IDs (e.g., Color=14, NodePath=15, Object=17) but the actual Godot 4 IDs are Color=20, NodePath=22, Object=24 with 10+ new types inserted in the middle range.

**Primary recommendation:** Build the Variant codec first as a pure, stateless encode/decode module with exhaustive golden-byte tests generated from Godot's own `var_to_bytes()`. Only after the codec passes byte-exact verification should the TCP server and connection lifecycle be built on top of it. Use the Godot 4.x type IDs (0-38) from `variant.h`, not the Godot 3 IDs from the binary serialization docs page.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Debug commands use `--project` flag on subcommands (not a global flag). Example: `gdauto debug connect --project ./my-game`
- D-02: `debug connect` is a combined command: starts TCP server, launches game, waits for connection. No separate launch/connect split.
- D-03: Default port is 6007 (matching Godot editor default). Override with `--port`.
- D-04: Debug subcommands use short verb names: `connect`, `tree`, `get`, `set`, `call`, `input`, `assert`, `wait`, `test`, `output`, `pause`, `resume`, `step`, `speed`, `disconnect`.
- D-05: `debug connect` accepts `--scene` flag to launch a specific scene instead of project's default main scene.
- D-06: CLI help for the debug group: "Live game interaction via Godot's remote debugger protocol. Connect to a running game, inspect state, inject input, and verify behavior."
- D-14: Comprehensive Variant codec covering 25+ of 39 Godot types. All common types including Rect2, Transform2D, Basis, Packed*Array, etc. Future-proof for game state inspection. Estimated ~600 lines.
- D-15: Validation via golden byte tests: generate reference bytes from Godot's var_to_bytes(), compare against Python encoder output. This catches encoding bugs that round-trip-only tests would miss.

### Claude's Discretion
- D-07: Session model (background server vs self-contained commands). Research recommended hybrid: self-contained for Phase 7 MVP, background server for multi-command workflows.
- D-08: Session timeout (auto-shutdown after inactivity vs explicit disconnect). Claude picks reasonable default.
- D-09: Single session only vs multiple sessions. Single session is likely sufficient.
- D-10: Session file location (project directory vs temp directory).
- D-11: `debug connect` blocking behavior (foreground vs background).
- D-12: Protocol error verbosity.
- D-13: Game crash handling.
- Connect output format (success message content and structure)
- Debug command naming: short verbs selected
- Session model implementation details
- Error verbosity defaults
- Crash recovery behavior

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROTO-01 | Variant binary codec encodes and decodes all Godot types needed for debugger communication | Godot 4 type IDs (0-38) verified from variant.h; encoding rules verified from marshalls.cpp; PlayGodot variant.py and VS Code VariantDecoder provide Python/TypeScript reference implementations; golden byte testing strategy defined |
| PROTO-02 | TCP server accepts incoming Godot debugger connections with length-prefixed binary framing | Wire format confirmed: 4-byte LE uint32 length prefix + Variant payload; gdauto is TCP server (asyncio.start_server), game is client; verified from remote_debugger_peer.cpp |
| PROTO-03 | Background receive loop drains unsolicited messages to prevent TCP buffer flooding | Performance data arrives ~60/sec; 8 MiB buffer limit confirmed; continuous recv_loop with future-based dispatch pattern documented from PlayGodot reference |
| PROTO-04 | Game launch integrates with existing GodotBackend, adding non-blocking subprocess with --remote-debug flag | GodotBackend.run() uses blocking subprocess.run; new launch_game() uses subprocess.Popen; game launched with `godot --path <project> --remote-debug tcp://127.0.0.1:<port>` |
| PROTO-05 | Connection lifecycle manages connect, readiness detection, timeout, and clean disconnect | Game retry logic: 6 attempts (1ms to 1000ms backoff); readiness detection by polling scene tree; cleanup via signal handlers + atexit; session file for state tracking |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Tech stack**: Python 3.10+, Click >= 8.0, pytest >= 7.0
- **Engine compatibility**: Godot 4.5+ binary on PATH (for E2E tests and headless commands only)
- **Error contract**: All errors produce non-zero exit codes and actionable messages; --json errors produce `{"error": "message", "code": "ERROR_CODE", "fix": "suggestion"}`
- **File validity**: Generated .tres/.tscn files must be loadable by Godot without modification
- **Code style**: No em dashes, no emojis, type hints on all signatures, docstrings on public functions, functions under 30 lines, comments on non-obvious logic only
- **Custom parser**: Hand-rolled (no godot_parser dependency); same principle applies to Variant codec
- **Zero new dependencies**: v2.0 adds no new pip dependencies; all stdlib (asyncio, struct, subprocess)
- **Data models**: dataclasses (stdlib), not Pydantic
- **Async pattern**: asyncio.run() at Click boundary; existing 28 commands stay synchronous

## Standard Stack

### Core (All stdlib, zero new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncio | stdlib (Python 3.13) | TCP server, async I/O, background recv loop | start_server() and StreamReader/StreamWriter provide exact abstraction needed for single-connection TCP server |
| struct | stdlib | Binary encoding/decoding | Godot Variant format uses LE packed integers/floats; struct.pack/unpack with '<' format strings handles all encoding |
| subprocess | stdlib | Non-blocking game launch | subprocess.Popen (not .run) for concurrent game execution alongside TCP server |
| dataclasses | stdlib | Debugger models | SceneNode, DebugSession config; consistent with v1.0 internal data pattern |
| signal | stdlib | Cleanup handlers | SIGINT/SIGTERM handlers for bridge script cleanup on crash |
| atexit | stdlib | Exit cleanup | Fallback cleanup for normal exit paths |
| json | stdlib | Session files, --json output | Session state persistence, CLI output formatting |
| pathlib | stdlib | File operations | Bridge script paths, project path handling |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncio | trio | Adds dependency; structured concurrency overkill for single-connection server |
| asyncio.run() boundary | asyncclick 8.3.0.7 | Replaces entire Click stack with fork; risks breaking 28 existing sync commands |
| Custom Variant codec | gdtype-python | Last updated Sept 2022; targets Godot 4.0 beta; unknown Python 3.12+ compat |
| asyncio.start_server | socketserver | Synchronous; cannot handle bidirectional async communication |
| JSON session file | SQLite/Redis | Extreme overkill for PID + port + state tracking |

## Architecture Patterns

### Recommended Project Structure
```
src/gdauto/
  debugger/                     # NEW: Debugger bridge package
    __init__.py                 # Public API exports
    variant.py                  # Variant binary encoder/decoder (~600 lines)
    protocol.py                 # Message framing (length-prefix, 3-element Array wrapping)
    session.py                  # Async TCP server + session lifecycle
    models.py                   # Dataclasses for connection state, message types
    errors.py                   # DebuggerError subclasses
  commands/
    debug.py                    # NEW: Click command group for debug commands
```

### Modified Components
```
src/gdauto/
  cli.py                        # Add: cli.add_command(debug)
  backend.py                    # Add: launch_game() method (non-blocking subprocess.Popen)
  errors.py                     # Add: DebuggerConnectionError, DebuggerTimeoutError, ProtocolError
```

### Pattern 1: Stateless Variant Codec
**What:** Pure function pair with no mutable state.
**When to use:** All binary encoding/decoding operations.
**Example:**
```python
# Source: Verified from Godot variant.h + marshalls.cpp + PlayGodot variant.py
import struct
from enum import IntEnum

class VariantType(IntEnum):
    """Godot 4.x Variant type IDs (from variant.h)."""
    NIL = 0
    BOOL = 1
    INT = 2
    FLOAT = 3
    STRING = 4
    VECTOR2 = 5
    VECTOR2I = 6
    RECT2 = 7
    RECT2I = 8
    VECTOR3 = 9
    VECTOR3I = 10
    TRANSFORM2D = 11
    VECTOR4 = 12
    VECTOR4I = 13
    PLANE = 14
    QUATERNION = 15
    AABB = 16
    BASIS = 17
    TRANSFORM3D = 18
    PROJECTION = 19
    COLOR = 20
    STRING_NAME = 21
    NODE_PATH = 22
    RID = 23
    OBJECT = 24
    CALLABLE = 25
    SIGNAL = 26
    DICTIONARY = 27
    ARRAY = 28
    PACKED_BYTE_ARRAY = 29
    PACKED_INT32_ARRAY = 30
    PACKED_INT64_ARRAY = 31
    PACKED_FLOAT32_ARRAY = 32
    PACKED_FLOAT64_ARRAY = 33
    PACKED_STRING_ARRAY = 34
    PACKED_VECTOR2_ARRAY = 35
    PACKED_VECTOR3_ARRAY = 36
    PACKED_COLOR_ARRAY = 37
    PACKED_VECTOR4_ARRAY = 38

ENCODE_FLAG_64 = 1 << 16
ENCODE_FLAG_OBJECT_AS_ID = 1 << 16

def encode(value: object) -> bytes:
    """Encode a Python value as a Godot Variant binary blob."""
    ...

def decode(data: bytes, offset: int = 0) -> tuple[object, int]:
    """Decode a Godot Variant from binary data at offset.

    Returns (decoded_value, bytes_consumed).
    """
    ...
```

### Pattern 2: 3-Element Wire Message Format (CRITICAL)
**What:** Every message on the wire is a 3-element Variant Array.
**When to use:** All message send/receive operations.
**CRITICAL CORRECTION:** The earlier project research (ARCHITECTURE.md) documented the message format as `[message_type, ...payload]`. This is WRONG for the wire format. The actual wire format is:
```python
# Source: remote_debugger.cpp _put_msg function
# Wire format: [command_name: String, thread_id: int, data: Array]
#
# Example: requesting scene tree
# ["scene:request_scene_tree", 1, []]
#
# Example: game sending output
# ["output", 1, ["Hello from game!"]]

def encode_message(command: str, data: list, thread_id: int = 1) -> bytes:
    """Encode a debugger message for transmission.

    Wraps as: 4-byte LE length prefix + Variant Array [command, thread_id, data]
    """
    payload = encode([command, thread_id, data])
    return struct.pack("<I", len(payload)) + payload

def decode_message(data: bytes) -> tuple[str, int, list]:
    """Decode a received debugger message.

    Returns (command_name, thread_id, data_array).
    """
    array, _ = decode(data)
    return array[0], array[1], array[2]
```

### Pattern 3: Async Session with Background Recv Loop
**What:** TCP server with continuous message draining and future-based response correlation.
**When to use:** All debugger session management.
**Example:**
```python
# Source: PlayGodot native_client.py + asyncio streams docs
class DebugSession:
    async def __aenter__(self) -> DebugSession:
        self._server = await asyncio.start_server(
            self._handle_connection, "127.0.0.1", self.port
        )
        return self

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._connected.set()
        self._recv_task = asyncio.create_task(self._recv_loop())

    async def _recv_loop(self) -> None:
        """Continuously drain messages, dispatching to handlers."""
        while not self._reader.at_eof():
            size_data = await self._reader.readexactly(4)
            size = struct.unpack("<I", size_data)[0]
            payload = await self._reader.readexactly(size)
            command, thread_id, data = decode_message(payload)

            # Capture thread_id from first message
            if self._thread_id is None:
                self._thread_id = thread_id

            # Dispatch
            if command in self._pending:
                self._pending.pop(command).set_result(data)
            elif command == "output":
                self._output_buffer.append(data)
            elif command == "error":
                self._error_buffer.append(data)
            # Discard performance:profile_frame silently
```

### Pattern 4: asyncio.run() at Click Boundary
**What:** Keep Click commands synchronous; enter async world at each command handler.
**When to use:** Every debug CLI command.
**Example:**
```python
# Source: Click issue #2033, asyncio docs
@debug.command("connect")
@click.option("--project", type=click.Path(exists=True), default=".")
@click.option("--port", type=int, default=6007)
@click.option("--scene", type=str, default=None)
@click.pass_context
def debug_connect(
    ctx: click.Context, project: str, port: int, scene: str | None
) -> None:
    """Start TCP server, launch game, wait for connection."""
    config: GlobalConfig = ctx.obj
    try:
        result = asyncio.run(_async_connect(project, port, scene, config))
    except DebuggerError as exc:
        emit_error(exc, ctx)
        return
    emit(result, _print_connect_status, ctx)
```

### Anti-Patterns to Avoid
- **Using Godot 3 type IDs:** The binary serialization docs page at godotengine.org still shows Godot 3 IDs in some places. Always use the Godot 4 enum from variant.h (Color=20, not 14; NodePath=22, not 15; Dictionary=27, not 18; Array=28, not 19).
- **2-element message arrays:** The wire format is 3 elements [command, thread_id, data], not 2 elements. Sending 2-element arrays will be silently rejected by Godot.
- **Blocking TCP in Click handlers:** Use asyncio, not synchronous socket.recv().
- **Reading directly from socket in command code:** Always go through the recv_loop and futures; direct reads will miss unsolicited messages.
- **Global singleton session:** Click commands are separate invocations; session state must persist externally.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Binary packing | Custom byte manipulation | `struct.pack/unpack` with '<' format | struct handles endianness, alignment, and type conversion correctly; hand-rolling leads to off-by-one padding bugs |
| TCP server | Raw socket management | `asyncio.start_server()` + StreamReader/StreamWriter | Handles buffering, backpressure, and async I/O; raw sockets require manual buffer management |
| Event loop | Threading + locks | `asyncio` event loop with tasks and futures | asyncio is designed for this exact use case; threading adds deadlock risk |
| JSON session state | Custom file format | `json.dumps/loads` to `.gdauto-session.json` | Session state is PID + port + status; JSON is human-readable for debugging |

**Key insight:** The Variant codec IS the hand-rolled component for this phase, justified by the same reasoning as the custom .tscn/.tres parser: the format is well-specified, we need full control over encoding accuracy, and the only Python alternative (gdtype-python) is abandoned.

## Godot 4 Variant Type ID Reference (CRITICAL)

This table supersedes any Godot 3-era type IDs found in earlier research documents. Verified from `variant.h` in the Godot engine repository.

| ID | Type | Encoding Size | Python Mapping | Phase 7 Priority |
|----|------|---------------|----------------|------------------|
| 0 | NIL | 4 (header only) | None | MUST |
| 1 | BOOL | 4+4 | bool | MUST |
| 2 | INT | 4+4 (32-bit) or 4+8 (64-bit with flag) | int | MUST |
| 3 | FLOAT | 4+4 (32-bit) or 4+8 (64-bit with flag) | float | MUST |
| 4 | STRING | 4+4+len+pad | str | MUST |
| 5 | VECTOR2 | 4+8 (2x float32) | tuple[float, float] | MUST |
| 6 | VECTOR2I | 4+8 (2x int32) | tuple[int, int] | SHOULD |
| 7 | RECT2 | 4+16 (4x float32) | tuple[float, float, float, float] | SHOULD |
| 8 | RECT2I | 4+16 (4x int32) | tuple[int, int, int, int] | SHOULD |
| 9 | VECTOR3 | 4+12 (3x float32) | tuple[float, float, float] | MUST |
| 10 | VECTOR3I | 4+12 (3x int32) | tuple[int, int, int] | SHOULD |
| 11 | TRANSFORM2D | 4+24 (6x float32) | tuple of 6 floats | SHOULD |
| 12 | VECTOR4 | 4+16 (4x float32) | tuple[float, float, float, float] | NICE |
| 13 | VECTOR4I | 4+16 (4x int32) | tuple[int, int, int, int] | NICE |
| 14 | PLANE | 4+16 (4x float32) | tuple of 4 floats | NICE |
| 15 | QUATERNION | 4+16 (4x float32) | tuple of 4 floats | NICE |
| 16 | AABB | 4+24 (6x float32) | tuple of 6 floats | NICE |
| 17 | BASIS | 4+36 (9x float32) | tuple of 9 floats | SHOULD |
| 18 | TRANSFORM3D | 4+48 (12x float32) | tuple of 12 floats | NICE |
| 19 | PROJECTION | 4+64 (16x float32) | tuple of 16 floats | NICE |
| 20 | COLOR | 4+16 (4x float32 RGBA) | tuple[float, float, float, float] | MUST |
| 21 | STRING_NAME | Same as STRING (4+4+len+pad) | str (tagged) | MUST |
| 22 | NODE_PATH | Variable (names+subnames+flags) | str | MUST |
| 23 | RID | 4+8 (uint64) | int | SHOULD |
| 24 | OBJECT | Variable (null=4, as_id=8, full=variable) | int or None | MUST |
| 25 | CALLABLE | Not serializable | skip | SKIP |
| 26 | SIGNAL | Not serializable | skip | SKIP |
| 27 | DICTIONARY | 4+4+pairs | dict | MUST |
| 28 | ARRAY | 4+4+elements | list | MUST |
| 29-38 | Packed*Array | 4+4+elements | list/bytes | SHOULD (29,30,32,34) |

**MUST types (Phase 7 minimum):** NIL, BOOL, INT, FLOAT, STRING, VECTOR2, VECTOR3, COLOR, STRING_NAME, NODE_PATH, OBJECT, DICTIONARY, ARRAY (13 types)

**SHOULD types (D-14 comprehensive):** Add VECTOR2I, VECTOR3I, RECT2, RECT2I, TRANSFORM2D, BASIS, RID, PACKED_BYTE_ARRAY, PACKED_INT32_ARRAY, PACKED_FLOAT32_ARRAY, PACKED_STRING_ARRAY (11 more, total 24)

**NICE types (future-proofing to 25+):** Add VECTOR4, VECTOR4I, PLANE, QUATERNION, AABB, TRANSFORM3D, PROJECTION, remaining Packed*Arrays

## String Encoding Detail (Critical for Correctness)

```
[4 bytes: type header (0x04000000 for String)]
[4 bytes: UTF-8 byte length (LE uint32)]
[N bytes: UTF-8 encoded string data]
[0-3 bytes: null padding to align to 4-byte boundary]
```

Padding formula: `pad = (4 - (length % 4)) % 4`

Examples:
- "" (0 bytes): header + length(0) = 8 bytes total
- "a" (1 byte): header + length(1) + "a" + 3 pad bytes = 12 bytes
- "test" (4 bytes): header + length(4) + "test" + 0 pad bytes = 12 bytes
- "hello" (5 bytes): header + length(5) + "hello" + 3 pad bytes = 16 bytes

StringName (type 21) uses identical encoding but with type header 0x15000000.

## NodePath Encoding Detail

NodePath uses the "new format" (Godot 4) with three header uint32s:

```
[4 bytes: type header (0x16000000 for NodePath)]
[4 bytes: name_count | 0x80000000]  -- MSB set indicates new format
[4 bytes: subname_count]
[4 bytes: flags]  -- bit 0 = absolute path
[name_count + subname_count strings, each as: 4-byte length + UTF-8 + padding]
```

For NodePath("/root/Main/Label:text"):
- name_count = 3 (root, Main, Label), flag 0x80000000 set
- subname_count = 1 (text)
- flags = 1 (absolute path)
- Then 4 strings: "root", "Main", "Label", "text"

For NodePath("") (empty):
- name_count = 0 | 0x80000000
- subname_count = 0
- flags = 0

## Integer Encoding Detail

```
# 32-bit (fits in int32 range):
[4 bytes: type header 0x02000000]
[4 bytes: signed int32 LE]

# 64-bit (outside int32 range, or always for safe round-trip):
[4 bytes: type header 0x02000000 | ENCODE_FLAG_64]  = 0x00010002
[8 bytes: signed int64 LE]
```

PlayGodot's approach: check if value fits in `[-2^31, 2^31-1]`; use 32-bit if yes, 64-bit otherwise.

## Float Encoding Detail

```
# 32-bit:
[4 bytes: type header 0x03000000]
[4 bytes: IEEE 754 float32 LE]

# 64-bit (with ENCODE_FLAG_64):
[4 bytes: type header 0x03000000 | ENCODE_FLAG_64]  = 0x00010003
[8 bytes: IEEE 754 float64 LE]
```

PlayGodot always encodes floats as 64-bit (double) for accuracy. Godot sends floats as 32-bit by default unless the engine was compiled with `float=64`. For the encoder: use 64-bit to avoid precision loss. For the decoder: handle both based on the flag bit.

## Array and Dictionary Encoding

```
# Array:
[4 bytes: type header 0x1C000000]  -- type 28
[4 bytes: element_count & 0x7FFFFFFF]  -- MSB is shared flag (ignore)
[N elements: each a full Variant encoding]

# Dictionary:
[4 bytes: type header 0x1B000000]  -- type 27
[4 bytes: pair_count & 0x7FFFFFFF]  -- MSB is shared flag (ignore)
[N pairs: alternating key Variant, value Variant]
```

**Typed arrays/dicts (Godot 4.4+):** The high bits of the type header may contain container type metadata. For decoding, check if bits 16-17 are non-zero and read the type info accordingly. For encoding, use untyped containers (metadata bits = 0).

## Wire Protocol: Message Framing

```
[4 bytes: LE uint32 payload_length]  -- length of the Variant data that follows
[payload_length bytes: Variant-encoded Array]  -- always type ARRAY (28)
```

The payload is always a Variant of type ARRAY containing exactly 3 elements:
```
Array[
    String: command_name,     // e.g., "scene:request_scene_tree"
    int: thread_id,           // captured from first received message
    Array: data               // command-specific arguments
]
```

Buffer limits (from remote_debugger_peer.cpp):
- Maximum message size: 8 MiB (8 << 20 = 8,388,608 bytes)
- Input buffer: 8 MiB + 4 bytes
- Output buffer: 8 MiB

## Connection Sequence

1. gdauto starts TCP server on 127.0.0.1:port (default 6007)
2. gdauto launches game: `godot --path <project> --remote-debug tcp://127.0.0.1:<port>` (optionally with `<scene.tscn>` for --scene)
3. Game boots, attempts TCP connection with 6 retries (1ms, 10ms, 100ms, 1000ms, 1000ms, 1000ms backoff)
4. gdauto accepts connection, stores reader/writer, starts recv_loop
5. Game sends initial messages; gdauto captures thread_id from first message
6. gdauto polls for readiness (send `scene:request_scene_tree`, retry until non-empty response)
7. Session is ready for commands

## Common Pitfalls

### Pitfall 1: Godot 4 Type IDs vs Godot 3 Type IDs
**What goes wrong:** Using type IDs from the binary serialization docs page (which may still reference Godot 3 numbering) or from the earlier ARCHITECTURE.md research. In Godot 3, Color was type 14, NodePath was 15, Object was 17, Dictionary was 18, Array was 19. In Godot 4, these are Color=20, NodePath=22, Object=24, Dictionary=27, Array=28. Using wrong IDs produces garbage that Godot silently discards.
**Why it happens:** Godot 4 inserted 10 new types (Vector2i, Rect2i, Vector3i, Vector4, Vector4i, Plane, Quaternion, Projection, StringName, callable/signal) between the old types, shifting all subsequent IDs.
**How to avoid:** Use ONLY the type IDs from the `VariantType` IntEnum defined above, sourced from `variant.h`. Cross-reference against the VS Code plugin `GDScriptTypes` enum.
**Warning signs:** Decoding produces unexpected type names; encoding commands get no response.

### Pitfall 2: 2-Element vs 3-Element Wire Messages
**What goes wrong:** Sending messages as `[command, data]` instead of `[command, thread_id, data]`. The earlier ARCHITECTURE.md documented the format as a 2-element array. Godot's `_poll_messages` expects exactly 3 elements and validates `cmd[0] is STRING, cmd[1] is INT, cmd[2] is ARRAY`.
**Why it happens:** The binary serialization docs describe the Variant format but not the debugger wire protocol. The wire protocol is only documented in C++ source.
**How to avoid:** Always encode messages as 3-element arrays. Capture thread_id from the first received message and include it in all outgoing messages.
**Warning signs:** Commands sent but no response received; Godot logs may show parse errors if --verbose is enabled on the game.

### Pitfall 3: String Padding Errors
**What goes wrong:** Forgetting to pad strings to 4-byte boundaries, or padding to the wrong boundary. A 5-byte string needs 3 bytes of null padding. Getting this wrong shifts all subsequent data in the message, corrupting everything after the string.
**Why it happens:** Easy to compute length but forget padding, or apply ceiling division incorrectly.
**How to avoid:** Use `pad = (4 - (length % 4)) % 4` consistently. Test strings of length 0, 1, 2, 3, 4, 5, 7, 8 (all boundary cases). Golden byte tests catch this immediately.
**Warning signs:** First string in a message works, but subsequent values decode as garbage.

### Pitfall 4: Unsolicited Message Flooding
**What goes wrong:** Game sends performance data (~60 messages/second), output messages, and error messages continuously. If the recv_loop is not running, the TCP buffer fills (8 MiB), the game's send blocks, and the game freezes.
**Why it happens:** Debugger protocol is not request-response; it is bidirectional with unsolicited messages. A tool that only reads when expecting a response misses all background traffic.
**How to avoid:** Start the recv_loop immediately on connection acceptance, before sending any commands. Never read directly from the socket outside the recv_loop. Discard `performance:profile_frame` messages silently. Buffer `output` and `error` messages with a size cap (e.g., last 1000).
**Warning signs:** Game freezes after a few seconds; commands time out.

### Pitfall 5: Port 6007 Conflict with Godot Editor
**What goes wrong:** If the Godot editor is running with "Keep Debug Server Open", it already holds port 6007. gdauto's `asyncio.start_server()` fails with "Address already in use".
**Why it happens:** Both tools default to port 6007 per Godot convention.
**How to avoid:** Check port availability before binding. If port is in use, provide a clear error message suggesting `--port <alternative>`. Set `SO_REUSEADDR` on the server socket for quick reuse after crash.
**Warning signs:** "Address already in use" or "OSError: [Errno 98]" at launch.

### Pitfall 6: Game Boot Race Condition
**What goes wrong:** Game connects to TCP server early in its boot sequence, before the main scene is fully loaded. Early `request_scene_tree` commands return empty or partial data.
**Why it happens:** TCP connection happens before scene tree initialization. PR #103297 in Godot addresses this exact issue.
**How to avoid:** After accepting connection, wait for readiness by polling `scene:request_scene_tree` with exponential backoff until a non-empty response arrives. Set a maximum wait time (30 seconds).
**Warning signs:** Empty scene tree on first query; intermittent test failures.

### Pitfall 7: asyncio.run() Not Reentrant
**What goes wrong:** If debug commands are tested with pytest-asyncio, calling `asyncio.run()` from within an already-running event loop raises `RuntimeError: cannot be called when another event loop is running`.
**Why it happens:** asyncio.run() creates a new event loop and cannot nest.
**How to avoid:** Provide a `run_async()` helper that detects existing event loops. For tests, call async functions directly, not through the Click command layer.
**Warning signs:** RuntimeError in test suites.

### Pitfall 8: Windows TCP Specifics
**What goes wrong:** Port binding failures on Windows; game process not terminating cleanly; signal handler differences.
**Why it happens:** Developer's primary platform is Windows. Python's cross-platform abstractions have edge cases in async I/O and process management on Windows.
**How to avoid:** Use `127.0.0.1` not `localhost` (avoids IPv6 resolution). Set `SO_REUSEADDR`. Use `subprocess.Popen.kill()` as fallback after `terminate()` with timeout. Use `pathlib.Path` and `.as_posix()` for paths written to project.godot.
**Warning signs:** "Address already in use" after crash on Windows; game process remains after gdauto exits.

## Code Examples

### Verified: Encoding a String Variant
```python
# Source: Godot marshalls.cpp + PlayGodot variant.py
def _encode_string(value: str) -> bytes:
    """Encode a Python string as a Godot Variant String."""
    utf8 = value.encode("utf-8")
    length = len(utf8)
    pad = (4 - (length % 4)) % 4
    header = struct.pack("<I", VariantType.STRING)
    return header + struct.pack("<I", length) + utf8 + b"\x00" * pad
```

### Verified: Encoding a Complete Debugger Message
```python
# Source: remote_debugger.cpp _put_msg + remote_debugger_peer.cpp
def encode_message(command: str, data: list, thread_id: int = 1) -> bytes:
    """Encode a debugger message with length-prefix framing.

    Wire format: [4-byte LE size] [Variant Array of 3 elements]
    The Array contains: [command_name, thread_id, data_array]
    """
    message_array = [command, thread_id, data]
    payload = encode(message_array)  # Variant encode as type ARRAY (28)
    return struct.pack("<I", len(payload)) + payload
```

### Verified: Reading a Framed Message from TCP
```python
# Source: remote_debugger_peer.cpp + PlayGodot native_client.py
async def read_message(
    reader: asyncio.StreamReader,
) -> tuple[str, int, list]:
    """Read one length-prefixed message from the TCP stream.

    Returns (command_name, thread_id, data_array).
    Raises asyncio.IncompleteReadError if connection drops.
    """
    size_data = await reader.readexactly(4)
    size = struct.unpack("<I", size_data)[0]
    if size > 8_388_608:  # 8 MiB limit
        raise ProtocolError(
            message=f"Message too large: {size} bytes (max 8 MiB)",
            code="PROTO_MSG_TOO_LARGE",
            fix="This usually indicates a protocol synchronization error",
        )
    payload = await reader.readexactly(size)
    array, _ = decode(payload, 0)
    return array[0], array[1], array[2]
```

### Verified: GodotBackend.launch_game() Extension
```python
# Source: Existing backend.py pattern + subprocess.Popen docs
def launch_game(
    self,
    project_path: Path,
    port: int = 6007,
    scene: str | None = None,
) -> subprocess.Popen[str]:
    """Launch a Godot game with remote debug connection.

    Uses Popen (non-blocking) instead of run (blocking).
    Returns the Popen object for lifecycle management.
    """
    binary = self.ensure_binary()
    cmd = [
        binary,
        "--path", str(project_path),
        "--remote-debug", f"tcp://127.0.0.1:{port}",
    ]
    if scene is not None:
        cmd.append(scene)
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
```

### Verified: Error Hierarchy Extension
```python
# Source: Existing errors.py pattern
@dataclass
class DebuggerError(GdautoError):
    """Base for all debugger-related errors."""

@dataclass
class DebuggerConnectionError(DebuggerError):
    """Raised when TCP connection fails or times out."""

@dataclass
class DebuggerTimeoutError(DebuggerError):
    """Raised when a command response times out."""

@dataclass
class ProtocolError(DebuggerError):
    """Raised when a protocol-level error occurs (bad encoding, invalid message)."""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Godot 3 type IDs (Color=14, NodePath=15) | Godot 4 type IDs (Color=20, NodePath=22) | Godot 4.0 (2023) | All type ID constants must use Godot 4 enum |
| 2-element wire messages [cmd, data] | 3-element wire messages [cmd, thread_id, data] | Godot 4.0 debugger refactor (PR #36244) | Message encoding must include thread_id |
| Untyped containers only | Typed Array/Dictionary with container type flags | Godot 4.4+ | Decoder must handle type metadata bits in header |
| gdtype-python (2022) | Abandoned; build custom | Sept 2022 (last update) | Cannot depend on external codec library |
| PlayGodot (custom Godot fork) | gdauto (stock Godot only) | N/A | Input injection requires GDScript bridge autoload (Phase 9), not engine fork |

## Open Questions

1. **Scene tree response binary layout**
   - What we know: `scene:request_scene_tree` returns a `scene_tree` message. The VS Code plugin parses this with `parse_next_scene_node()`. The data is a "flat list depth first" per Godot source comments.
   - What's unclear: The exact field layout of each node entry in the flat array (node name, class, instance ID, child count, etc.). This is not documented and requires empirical reverse-engineering.
   - Recommendation: Build a GDScript probe that dumps a known scene tree, capture the raw bytes, and reverse-engineer the format. This is Phase 8 work, not Phase 7. Phase 7 only needs to prove the connection works and messages can be exchanged.

2. **Typed Array/Dictionary container metadata**
   - What we know: Godot 4.4+ added typed containers. The type header's bits 16-17 contain container type flags (NONE, BUILTIN, CLASS_NAME, SCRIPT).
   - What's unclear: Whether the stock debugger ever sends typed containers in practice. If it does, the decoder needs to skip/read the type metadata before the element count.
   - Recommendation: Implement defensive decoding: if container type flags are non-zero in Array/Dictionary headers, read and discard the type metadata before proceeding to element count. Test empirically with Godot 4.5+.

3. **Game readiness signal**
   - What we know: No documented "scene tree ready" message exists. The game connects to the debugger early in boot.
   - What's unclear: Whether sending `scene:request_scene_tree` before the scene tree exists causes any protocol errors or just returns an empty response.
   - Recommendation: Implement polling with exponential backoff. If the first request returns empty data, wait and retry. Maximum 30 second timeout.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (via uv) | Runtime | Yes | 3.13.0 | -- |
| asyncio (stdlib) | TCP server | Yes | stdlib | -- |
| struct (stdlib) | Binary encoding | Yes | stdlib | -- |
| Godot binary | E2E tests, golden byte generation | Unknown | Need GODOT_PATH | Mark E2E tests with @pytest.mark.requires_godot |
| uv | Package management | Yes | 0.9.7 | -- |

**Missing dependencies with no fallback:**
- Godot binary not confirmed on PATH or GODOT_PATH. E2E tests and golden byte generation require it. Unit tests for the codec can use hardcoded byte fixtures without Godot.

**Missing dependencies with fallback:**
- None

## Existing Code Integration Points

### backend.py -- Add launch_game()
Current `GodotBackend` has `run()` (blocking subprocess.run) and `ensure_binary()` (discovery + version check). Add `launch_game()` returning `subprocess.Popen` for non-blocking game execution. Reuse `ensure_binary()` for binary discovery.

### errors.py -- Add debugger error classes
Current hierarchy: `GdautoError > ParseError, ResourceNotFoundError, GodotBinaryError, ValidationError, ProjectError`. Add `DebuggerError > DebuggerConnectionError, DebuggerTimeoutError, ProtocolError`. All follow the `@dataclass` pattern with message/code/fix fields and `to_dict()`.

### output.py -- No changes needed
`emit()` and `emit_error()` with `GlobalConfig` for --json switching already handle all debug command output needs. The debug commands use these directly.

### cli.py -- Add debug command group
Current: `cli.add_command(project/resource/export/sprite/tileset/scene/import/skill)`. Add `cli.add_command(debug)` following the same pattern. Import from `gdauto.commands.debug`.

### formats/values.py -- Type knowledge for codec
The existing `Vector2`, `Vector3`, `Color`, `NodePath`, `StringName` etc. dataclasses in `formats/values.py` provide Python representations of Godot types. The Variant codec can reuse these for type mapping (e.g., decoded Vector2 binary -> `values.Vector2` instance), or define its own lighter-weight representations (tuples). Decision: use tuples in the codec for simplicity and zero coupling; conversion to `formats/values.*` types happens at the command layer if needed.

### formats/project_cfg.py -- Needed for Phase 9 bridge injection
Not needed in Phase 7. The `ProjectConfig` parser with its `parse_project_config()`/`serialize_project_config()` will be used in Phase 9 for autoload bridge injection into project.godot.

## Sources

### Primary (HIGH confidence)
- [Godot `variant.h`](https://github.com/godotengine/godot/blob/master/core/variant/variant.h) -- Complete Variant::Type enum with Godot 4 type IDs (0-38)
- [Godot `marshalls.cpp`](https://github.com/godotengine/godot/blob/master/core/io/marshalls.cpp) -- Variant binary encoding/decoding implementation; ENCODE_FLAG_64; String/NodePath/Array/Dictionary encoding rules
- [Godot `remote_debugger.cpp`](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger.cpp) -- Wire message format confirmed as 3-element Array [command, thread_id, data]; message capture dispatch system
- [Godot `remote_debugger_peer.cpp`](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger_peer.cpp) -- TCP client behavior; 8 MiB buffer limits; 4-byte length prefix framing; connection retry logic (6 attempts, 1-1000ms backoff)
- [Godot Binary Serialization API docs](https://docs.godotengine.org/en/stable/tutorials/io/binary_serialization_api.html) -- Official documentation (note: some type IDs may reflect Godot 3 numbering)

### Secondary (MEDIUM confidence)
- [godot-vscode-plugin VariantDecoder](https://github.com/godotengine/godot-vscode-plugin) -- TypeScript reference implementation for Variant decoding; GDScriptTypes enum with Godot 4 IDs; source at `src/debugger/godot4/variables/variant_decoder.ts` and `variants.ts`
- [PlayGodot variant.py](https://github.com/Randroids-Dojo/PlayGodot/blob/main/python/playgodot/variant.py) -- Python reference implementation; VariantType IntEnum; encode/decode functions; confirms float=64-bit encoding strategy
- [PlayGodot native_client.py](https://github.com/Randroids-Dojo/PlayGodot/blob/main/python/playgodot/native_client.py) -- TCP server pattern; asyncio.start_server; message framing; future-based request/response; thread_id capture
- [PlayGodot PROTOCOL.md](https://github.com/Randroids-Dojo/PlayGodot/blob/main/protocol/PROTOCOL.md) -- Wire format documentation; confirms 3-element message format
- [DeepWiki: VS Code plugin Variable Inspection](https://deepwiki.com/godotengine/godot-vscode-plugin/4.3-variable-inspection) -- VariantDecoder architecture overview
- [Godot PR #103297](https://github.com/godotengine/godot/pull/103297) -- Scene debugger message timing issues; validates boot readiness race condition
- [Python asyncio streams docs](https://docs.python.org/3/library/asyncio-stream.html) -- start_server(), StreamReader/StreamWriter API

### Tertiary (LOW confidence)
- [gdtype-python](https://github.com/anetczuk/gdtype-python) -- Stale Python Variant serializer (Sept 2022); Godot 4.0 beta era; evaluated and rejected
- [pietrum/godot-binary-serialization](https://github.com/pietrum/godot-binary-serialization) -- JavaScript Variant codec; useful as cross-reference for encoding edge cases

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib, zero dependency decisions, verified from Python docs
- Architecture: HIGH -- TCP server pattern verified from Godot source and two reference implementations (VS Code plugin + PlayGodot)
- Variant type IDs: HIGH -- verified from variant.h (Godot 4 source) and corroborated by VS Code plugin GDScriptTypes enum
- Wire protocol: HIGH -- 3-element message format confirmed from remote_debugger.cpp _put_msg and PlayGodot reference
- Pitfalls: HIGH -- all documented from source analysis with two independent corroborating references
- Scene tree response format: LOW -- undocumented, requires empirical testing (Phase 8 concern, not Phase 7)

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable protocol, unlikely to change before Godot 4.6 release)
