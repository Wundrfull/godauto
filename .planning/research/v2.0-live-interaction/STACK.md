# Technology Stack: v2.0 Live Game Interaction

**Project:** gdauto
**Milestone:** v2.0 Live Game Interaction
**Researched:** 2026-03-29
**Scope:** Stack additions for connecting to Godot's remote debugger protocol, reading/modifying game state, injecting input events, and building an assertion layer.

## Architecture Decision: Two-Component System

The live interaction feature requires **two components working together**:

1. **Python TCP Server** (in gdauto): Listens on port 6007, accepts connections from the Godot game process, sends/receives binary Variant-encoded messages.
2. **GDScript Autoload Plugin** (shipped with gdauto, injected into the target project): Registers custom debugger captures via `EngineDebugger.register_message_capture()` to handle automation commands (input injection, property queries beyond what the built-in scene debugger provides).

**Why this architecture:** Godot's debugger protocol uses a server-client model where the **editor/tool runs the TCP server** and the **game connects as a client** via `--remote-debug tcp://host:port`. gdauto replaces the editor as the server. The built-in `scene:` captures already provide scene tree inspection, object property get/set, and live editing. A lightweight GDScript autoload extends this with input injection (`Input.parse_input_event()`) and custom game state queries that the built-in debugger does not expose.

## Godot Remote Debugger Wire Protocol

**Confidence: HIGH** (verified against Godot engine source code: `remote_debugger_peer.cpp`, `scene_debugger.h/.cpp`, `remote_debugger.cpp`, and the godot-vscode-plugin TypeScript implementation)

### Connection Model

| Aspect | Detail |
|--------|--------|
| Transport | TCP (also supports Unix sockets, but TCP is the standard) |
| Default port | 6007 (configurable) |
| Who listens | The **tool/editor** runs the TCP server |
| Who connects | The **game** connects as client via `--remote-debug tcp://host:port` |
| Launch command | `godot --path /project --remote-debug tcp://127.0.0.1:6007` |

### Packet Format (Wire Level)

Every message on the wire is a **length-prefixed Godot Variant Array**:

```
[4 bytes: uint32 LE payload_length] [payload_length bytes: encode_variant(Array)]
```

- Length prefix: 4 bytes, **little-endian** uint32, encodes payload size (NOT including the 4-byte prefix itself)
- Payload: A Godot Variant of type Array, serialized via `encode_variant()`
- Maximum message size: 8 MiB (8 << 20 = 8,388,608 bytes)
- All values are little-endian
- All data is padded to 4-byte boundaries

### Variant Binary Encoding (Godot 4.x Type IDs)

Each encoded Variant starts with a 4-byte type header:
- Lower 16 bits: type ID
- Upper 16 bits: flags (e.g., `ENCODE_FLAG_64 = 1 << 16`)

| ID | Type | Encoding |
|----|------|----------|
| 0 | NIL | No additional data |
| 1 | BOOL | 4 bytes (0 or 1) |
| 2 | INT | 4 bytes (32-bit) or 8 bytes (64-bit if ENCODE_FLAG_64) |
| 3 | FLOAT | 4 bytes (32-bit) or 8 bytes (64-bit if ENCODE_FLAG_64) |
| 4 | STRING | 4-byte length + UTF-8 bytes + padding to 4-byte boundary |
| 5 | VECTOR2 | 8 bytes (2x float32) |
| 6 | VECTOR2I | 8 bytes (2x int32) |
| 7 | RECT2 | 16 bytes (4x float32) |
| 8 | RECT2I | 16 bytes (4x int32) |
| 9 | VECTOR3 | 12 bytes (3x float32) |
| 10 | VECTOR3I | 12 bytes (3x int32) |
| 11 | TRANSFORM2D | 24 bytes (6x float32) |
| 12 | VECTOR4 | 16 bytes (4x float32) |
| 13 | VECTOR4I | 16 bytes (4x int32) |
| 14 | PLANE | 16 bytes (4x float32) |
| 15 | QUATERNION | 16 bytes (4x float32) |
| 16 | AABB | 24 bytes (6x float32) |
| 17 | BASIS | 36 bytes (9x float32) |
| 18 | TRANSFORM3D | 48 bytes (12x float32) |
| 19 | PROJECTION | 64 bytes (16x float32) |
| 20 | COLOR | 16 bytes (4x float32: r, g, b, a) |
| 21 | STRING_NAME | Same as STRING |
| 22 | NODE_PATH | Complex: sub-name count + flags + strings |
| 23 | RID | 8 bytes (uint64) |
| 24 | OBJECT | Null, instance-ID-only (8 bytes), or full serialization |
| 25 | CALLABLE | Not serializable |
| 26 | SIGNAL | Not serializable |
| 27 | DICTIONARY | 4-byte count + alternating key/value Variants |
| 28 | ARRAY | 4-byte count + sequential Variants |
| 29-38 | PACKED_*_ARRAY | 4-byte count + typed elements |

### Debugger Message Structure

Messages are Variant Arrays with this structure:

```
Array[0]: String  -- command name (e.g., "scene:request_scene_tree")
Array[1]: int     -- thread ID (Godot 4.2+, may be absent in older versions)
Array[2..N]:      -- command-specific parameters
```

**Message routing uses colon-delimited prefixes:** A message like `"scene:request_scene_tree"` routes to the `"scene"` capture, which receives `"request_scene_tree"` as the command and the remaining array elements as data.

### Key Built-in Scene Debugger Messages

**Outbound (tool to game):**

| Message | Parameters | Purpose |
|---------|------------|---------|
| `scene:request_scene_tree` | (none) | Request full scene tree dump |
| `scene:inspect_objects` | `[Array<ObjectID>, bool update_selection]` | Request property data for objects |
| `scene:set_object_property` | `[ObjectID, String property, Variant value]` | Set a property on a live object |
| `scene:live_node_prop` | `[int node_id, StringName property, Variant value]` | Set property via live edit system |
| `scene:live_node_call` | `[int node_id, StringName method, ...]` | Call method on live node |
| `scene:live_create_node` | `[...]` | Create node in live scene |
| `scene:live_remove_node` | `[...]` | Remove node from live scene |
| `scene:rq_screenshot` | (none) | Request screenshot |
| `scene:suspend_changed` | `[bool suspended]` | Pause/resume game |
| `scene:speed_changed` | `[float speed]` | Change game speed |

**Inbound (game to tool, responses):**

| Message | Data | Purpose |
|---------|------|---------|
| `scene:scene_tree` | Serialized SceneDebuggerTree (flat list, depth-first) | Scene tree dump |
| `scene:inspect_objects` | Serialized object properties | Object property data |
| `output` | `[Array<String> lines, Array<int> types]` | Console output |
| `error` | Serialized ErrorMessage | Runtime errors |
| `debug_enter` | `[bool can_continue, String error, bool has_stack, int thread_id]` | Breakpoint hit |

### No Handshake Required

The protocol has **no handshake sequence**. The game connects via TCP and immediately begins exchanging Variant Array messages. The editor/tool can start sending commands as soon as the TCP connection is accepted.

## Recommended Stack Additions

### Core: TCP Server and Protocol

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| asyncio (stdlib) | stdlib | TCP server, event loop, async I/O | Python's standard async framework. Provides `asyncio.start_server()` for TCP listener, `StreamReader.readexactly()` for length-prefixed framing, and `StreamWriter` for sending. No external dependency. Handles concurrent message processing without threading. Used by the VSCode plugin (Node.js equivalent) and is the standard pattern for binary protocol clients in Python. | HIGH |
| struct (stdlib) | stdlib | Binary encoding/decoding | `struct.pack('<I', length)` for 4-byte little-endian uint32 length prefix. `struct.pack('<i', value)` for int32, `struct.pack('<f', value)` for float32, `struct.pack('<d', value)` for float64. Standard Python tool for binary protocols. Zero dependency. | HIGH |

### Core: Variant Codec (Build In-House)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Custom Variant codec | n/a | Encode/decode Godot binary Variant format | **Build this ourselves.** The only Python library (gdtype-python by anetczuk) has 70 commits total, no releases on PyPI, no clear maintenance status, uncertain Godot 4.5+ compatibility with newer type IDs (Vector4, Vector4i, Projection, PackedVector4Array added in recent Godot versions, ID 12-13 and 19 and 38). The format is well-documented (official Binary Serialization API docs + confirmed against VSCode plugin source). The type table has 39 entries; each is a straightforward struct.pack/unpack. Estimated 400-600 lines of Python. Same rationale as the custom .tscn/.tres parser: full control, zero maintenance risk, exact Godot 4.5+ compatibility. | HIGH |

**Why not gdtype-python:** Similar reasoning to why we built a custom .tscn/.tres parser instead of using stevearc/godot_parser:
- Not on PyPI (must vendor or copy source)
- 70 commits, no tagged releases, last activity unclear
- Written for Godot 4.0 beta; may not handle newer type IDs (Vector4, Vector4i, Projection, StringName, PackedVector4Array)
- No active community or issues being triaged
- The format is simple and fully documented; building our own is safer than depending on an unmaintained library

### Core: GDScript Autoload Plugin

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| GDScript autoload | Godot 4.5+ | Game-side automation capture | A small GDScript file (~100-200 lines) that registers a custom debugger capture via `EngineDebugger.register_message_capture("gdauto", callable)`. Handles commands the built-in scene debugger cannot: `gdauto:inject_input` (calls `Input.parse_input_event()`), `gdauto:get_tree_info` (custom scene queries), `gdauto:call_method` (arbitrary method calls with return values). Responds via `EngineDebugger.send_message()`. gdauto auto-injects this as an autoload into project.godot before launching the game. | HIGH |

### Supporting: Process Management

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| subprocess (stdlib) | stdlib | Launch Godot game process | Already used in gdauto's `backend.py` for headless invocations. Extended to launch with `--remote-debug tcp://127.0.0.1:{port}` flag. No new dependency needed. | HIGH |
| asyncio.subprocess (stdlib) | stdlib | Async process management | `asyncio.create_subprocess_exec()` for non-blocking game launch and stdout/stderr capture while the event loop handles TCP communication. Alternative to sync subprocess when we need concurrent game process + TCP server management. | HIGH |

### Supporting: Timeout and Retry

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| asyncio.wait_for (stdlib) | stdlib | Command timeouts | `asyncio.wait_for(coroutine, timeout=N)` for timing out commands that the game never responds to. Standard asyncio pattern. | HIGH |
| asyncio.Event (stdlib) | stdlib | Response synchronization | Wait for specific response messages from the game. `event.wait()` with timeout for request-response correlation. | HIGH |

### Supporting: Testing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| pytest-asyncio | 0.26.x | Async test support | Needed for testing async TCP server/client code. Provides `@pytest.mark.asyncio` decorator and async fixtures. Current stable: 0.26.0 (Jan 2026). The only new dev dependency. | HIGH |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Variant codec | Custom (in-house) | gdtype-python | Not on PyPI, uncertain Godot 4.5+ compat, unmaintained, no releases. Same reasoning as custom .tscn/.tres parser. |
| Variant codec | Custom (in-house) | pietrum/godot-binary-serialization (JS) | JavaScript library, not Python. Useful as reference implementation only. |
| TCP framework | asyncio (stdlib) | trio | External dependency, smaller ecosystem, no benefit for our use case (single connection, straightforward protocol). asyncio is stdlib. |
| TCP framework | asyncio (stdlib) | socket (stdlib, sync) | Blocking I/O would require threading for concurrent game process management + TCP communication. asyncio is cleaner for this pattern. |
| TCP framework | asyncio (stdlib) | twisted | Massive dependency, enterprise-grade, overkill for a single-connection binary protocol. |
| Game-side bridge | GDScript autoload | Custom Godot fork (PlayGodot approach) | PlayGodot requires a custom Godot build with C++ automation captures. We target stock Godot 4.5+. GDScript autoload achieves the same via EngineDebugger API without engine modification. |
| Game-side bridge | GDScript autoload | GDExtension / C# module | Heavier than needed. GDScript autoload is ~100 lines, zero compilation step, auto-injectable via project.godot manipulation (which gdauto already does). |
| Message protocol | Built-in debugger + custom capture | WebSocket sidecar | Adding a WebSocket server inside the game is an alternative architecture, but it duplicates what the debugger protocol already provides and requires more game-side code. The debugger protocol is the designed integration point. |
| Serialization | Godot binary Variant | JSON over TCP | Would require building a JSON serialization layer in GDScript. Binary Variant is native to the debugger protocol, type-safe, and handles all Godot types including Vector2, Color, NodePath without custom marshaling. |

## What NOT to Add

| Technology | Why Not |
|------------|---------|
| websockets (pip) | No WebSocket communication needed; debugger protocol is raw TCP with binary Variant encoding |
| protobuf / msgpack | Godot uses its own Variant binary format, not protobuf or msgpack |
| Pydantic | Same reasoning as existing stack: internal data validated by protocol codec, not user input |
| grpcio | No gRPC; this is a custom binary protocol |
| aiohttp | No HTTP involved |
| gdtype-python | Vendor risk; build our own (see above) |
| PyAutoGUI / pynput | Input injection happens inside Godot via `Input.parse_input_event()`, not at the OS level |

## Integration Points with Existing gdauto

### Existing code to extend:

| Module | Change | Reason |
|--------|--------|--------|
| `backend.py` (GodotBackend) | Add `launch_with_debugger(project_path, port)` method | Launches game with `--remote-debug` flag; reuses binary discovery and version validation |
| `cli.py` | Register new `debug` command group | New command group: `gdauto debug connect`, `gdauto debug tree`, `gdauto debug get-property`, `gdauto debug set-property`, `gdauto debug inject-input`, `gdauto debug assert` |
| `errors.py` | Add `DebuggerError`, `ConnectionError`, `TimeoutError` subclasses | Structured errors for debugger operations |
| `output.py` | No changes needed | Existing `emit()` / `emit_error()` / `--json` pattern handles new command output |
| `commands/__init__.py` | Import new `debug` command group | Standard registration pattern |

### New modules to create:

| Module | Responsibility |
|--------|---------------|
| `src/gdauto/debugger/__init__.py` | Package for all debugger protocol code |
| `src/gdauto/debugger/variant.py` | Godot Variant binary encoder/decoder (~400-600 lines) |
| `src/gdauto/debugger/protocol.py` | TCP server, message framing, send/receive (~200-300 lines) |
| `src/gdauto/debugger/client.py` | High-level API: connect, request_tree, get_property, set_property, inject_input (~300-400 lines) |
| `src/gdauto/debugger/assertions.py` | Assertion/verification layer: wait_for_property, assert_node_exists, assert_property_equals (~200 lines) |
| `src/gdauto/commands/debug.py` | Click command group with subcommands |
| `src/gdauto/debugger/autoload.gd` | GDScript autoload for game-side automation capture (~100-200 lines) |
| `src/gdauto/debugger/inject.py` | Project.godot manipulation to auto-inject the autoload |

### Estimated new code:

| Category | Lines |
|----------|-------|
| Variant codec | 400-600 |
| TCP protocol layer | 200-300 |
| High-level client API | 300-400 |
| Assertion layer | 150-250 |
| CLI commands | 200-300 |
| GDScript autoload | 100-200 |
| Autoload injection | 50-100 |
| Tests | 800-1200 |
| **Total** | **2200-3350** |

## Dependency Changes to pyproject.toml

```toml
# CORE: No new runtime dependencies needed!
# asyncio, struct, subprocess, json are all stdlib

[project.optional-dependencies]
# Existing
image = ["Pillow>=12.0"]

# Development only (new addition)
dev = [
    "pytest>=9.0",
    "pytest-cov>=7.0",
    "pytest-asyncio>=0.26",  # NEW: async test support
    "ruff",
    "mypy>=1.19",
]
```

**Zero new runtime dependencies.** The entire debugger protocol stack uses Python stdlib (`asyncio`, `struct`, `socket`, `subprocess`, `json`). Only `pytest-asyncio` is added as a dev dependency for testing async code.

This is consistent with gdauto's design philosophy: minimal dependencies, stdlib-first approach, custom implementations for Godot-specific formats.

## Key Design Decisions

### Why asyncio over sync socket + threading

The debugger interaction involves three concurrent concerns: (1) TCP server listening for game connection, (2) sending commands and receiving responses, (3) monitoring game process stdout/stderr. asyncio handles all three in a single event loop without thread synchronization complexity. The Click CLI commands call `asyncio.run()` at the top level, keeping the CLI interface synchronous from the user's perspective.

### Why custom Variant codec over vendoring gdtype-python

Same philosophy as the custom .tscn/.tres parser: the format is well-documented, the existing library has maintenance/compatibility concerns, and we need exact control over Godot 4.5+ type support. The Variant binary format has 39 type IDs, each with straightforward encoding. The godot-vscode-plugin TypeScript implementation serves as an additional reference alongside the official Godot documentation.

### Why GDScript autoload over pure protocol approach

The built-in `scene:` captures provide scene tree inspection and property modification, but they do NOT provide: input injection, arbitrary method calls with return values, custom game state queries, or action mapping inspection. A lightweight GDScript autoload (~100-200 lines) registers a `"gdauto"` capture that handles these automation commands. gdauto auto-injects this autoload into `project.godot` before launching (gdauto already has full project.godot read/write capability via its configparser-based parser).

### Why TCP server (not client) in Python

In Godot's debugger architecture, the **tool/editor is always the TCP server** and the **game is always the TCP client**. When you run `godot --remote-debug tcp://host:port`, the game connects TO that address. gdauto must listen on a port and accept the game's connection, exactly as the Godot editor does. This is not negotiable; it is how the protocol works.

## Sources

- [Godot remote_debugger_peer.cpp](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger_peer.cpp) -- Wire protocol implementation, packet format, buffer sizes
- [Godot remote_debugger.cpp](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger.cpp) -- Message types, capture routing, core/profiler captures
- [Godot scene_debugger.h](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.h) -- All scene debugger message handlers (40+ message types)
- [Godot scene_debugger.cpp](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.cpp) -- Message parameter details, scene tree serialization format
- [Godot Binary Serialization API docs](https://docs.godotengine.org/en/stable/tutorials/io/binary_serialization_api.html) -- Official Variant encoding specification
- [godot-vscode-plugin variants.ts](https://github.com/godotengine/godot-vscode-plugin/blob/master/src/debugger/godot4/variables/variants.ts) -- Godot 4.x type ID enum (0-38), encoding flags
- [godot-vscode-plugin variant_decoder.ts](https://github.com/godotengine/godot-vscode-plugin/blob/master/src/debugger/godot4/variables/variant_decoder.ts) -- TypeScript Variant decoder (reference implementation)
- [godot-vscode-plugin variant_encoder.ts](https://github.com/godotengine/godot-vscode-plugin/blob/master/src/debugger/godot4/variables/variant_encoder.ts) -- TypeScript Variant encoder (reference implementation)
- [godot-vscode-plugin server_controller.ts](https://github.com/godotengine/godot-vscode-plugin/blob/master/src/debugger/godot4/server_controller.ts) -- TCP server, message framing, split_buffers pattern
- [PlayGodot](https://github.com/Randroids-Dojo/PlayGodot) -- Python game automation via custom Godot fork (architecture reference, not dependency)
- [gdtype-python](https://github.com/anetczuk/gdtype-python) -- Python Variant codec (evaluated, not recommended)
- [EngineDebugger API](https://docs.godotengine.org/en/stable/classes/class_enginedebugger.html) -- GDScript debugger API for custom captures
- [Godot Debugger Plugins PR #39440](https://github.com/godotengine/godot/pull/39440) -- Debugger capture/profiler plugin architecture
- [Python asyncio docs](https://docs.python.org/3/library/asyncio.html) -- TCP server, StreamReader/StreamWriter, subprocess
- [Python struct docs](https://docs.python.org/3/library/struct.html) -- Binary packing format strings
