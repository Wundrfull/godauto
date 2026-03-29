# Architecture: Live Game Interaction via Godot Debugger Protocol

**Domain:** Godot remote debugger bridge for CLI-based game interaction
**Researched:** 2026-03-29
**Overall Confidence:** MEDIUM (protocol details verified from Godot source, integration patterns based on established asyncio practices, no existing Python debugger client to reference)

## Executive Summary

Adding live game interaction to gdauto requires implementing a TCP server that speaks Godot's binary Variant protocol. The game (launched with `--remote-debug tcp://127.0.0.1:<port>`) acts as a TCP client and connects to our server. Messages are length-prefixed binary frames carrying Godot Variant-encoded Arrays. There is no handshake or authentication; the game begins sending data immediately after TCP connection.

This is architecturally different from everything gdauto does today. All existing commands are synchronous one-shot invocations: parse a file, write a file, run a subprocess. The debugger bridge introduces a long-lived TCP session with bidirectional async communication. The key architectural decision is how to bridge this async, stateful world with Click's synchronous command model.

**Recommendation:** Keep Click synchronous. Use `asyncio.run()` at the boundary of each debugger command to enter the async world. Build the debugger client as a standalone async module (`gdauto.debugger`) that knows nothing about Click. Click commands are thin wrappers that create a session, issue commands, and format output. Do NOT adopt asyncclick; it replaces all of Click with a fork and risks breaking existing synchronous commands.

**The game is the TCP client, gdauto is the TCP server.** This is counterintuitive but matches Godot's architecture: the editor listens on port 6007, and the game connects to it. gdauto must do the same.

---

## Connection Architecture

### Who Connects to Whom

```
gdauto (TCP Server)              Godot Game (TCP Client)
  listen(0.0.0.0:6007)
  accept()              <------  connect(tcp://127.0.0.1:6007)
  recv/send             <------>  recv/send
```

**Verified from source:** `remote_debugger_peer.cpp` shows the game calls `stream->connect_to_host(ip, debug_port)` with retry logic (6 attempts, 1ms to 1000ms backoff). The editor side (`EditorDebuggerNode`) calls `server->start()` then polls `server->is_connection_available()` to accept connections.

**Confidence:** HIGH (directly from Godot C++ source)

### Launch Sequence

1. gdauto starts TCP server on port (default 6007, configurable)
2. gdauto launches the Godot game via subprocess: `godot --path <project> --remote-debug tcp://127.0.0.1:<port>`
3. Game boots, connects to our TCP server
4. Connection accepted; session begins
5. Commands flow bidirectionally
6. On disconnect/quit, game process terminates

This means the existing `GodotBackend.run()` method (which uses `subprocess.run` with blocking wait) cannot be used directly; the game process must run concurrently while we communicate over TCP.

---

## Wire Protocol

### Message Framing

Every message on the wire follows this format:

```
[4 bytes: uint32 LE message_length][message_length bytes: encoded Variant]
```

- The 4-byte prefix is the byte length of the payload (NOT including the prefix itself)
- The payload is a Godot Variant encoded using the binary serialization API
- The top-level Variant MUST be of type Array
- Buffer limits: 8 MiB + 4 bytes input, 8 MiB output (per Godot source)

**Confidence:** HIGH (verified from `remote_debugger_peer.cpp`)

### Variant Binary Encoding

Each Variant is encoded as:

```
[4 bytes: type_header][variable bytes: type-specific data]
```

The type header's lower 16 bits are the type ID, upper 16 bits are flags (e.g., `ENCODE_FLAG_64 = 1 << 16` for 64-bit int/float). All values are little-endian. Data is padded to 4-byte boundaries.

Key type IDs for debugger communication:

| ID | Type | Encoding |
|----|------|----------|
| 0 | null | No data |
| 1 | bool | 4-byte int (0 or 1) |
| 2 | int | 4 or 8 bytes (flag-dependent) |
| 3 | float | 4 or 8 bytes (flag-dependent) |
| 4 | String | 4-byte length + UTF-8 bytes (padded to 4) |
| 5 | Vector2 | 2x 4-byte floats |
| 7 | Vector3 | 3x 4-byte floats |
| 14 | Color | 4x 4-byte floats (RGBA) |
| 15 | NodePath | Variable (name count + subname count + flags + strings) |
| 17 | Object | null (0) or EncodedObjectAsID (object_id as uint64) |
| 18 | Dictionary | 4-byte count + (key, value) pairs |
| 19 | Array | 4-byte count + elements |

**Confidence:** HIGH (official Godot binary serialization docs + godot-docs RST source)

### Message Format (Application Layer)

Debugger messages are Variant Arrays with this structure:

```
Array[
    String message_type,    // e.g. "scene:request_scene_tree"
    ... payload values ...  // message-specific arguments
]
```

Messages use a prefix-based routing system. The prefix before the colon identifies the "capture" (subsystem), and the suffix is the command. Messages without a prefix go to the core debugger.

**Confidence:** MEDIUM (inferred from `remote_debugger.cpp` capture dispatch system and `scene_debugger.cpp` handler registration)

---

## Debugger Command Inventory

### Scene Commands (prefix: "scene:")

These are the commands gdauto needs to implement v2.0 features.

| Command | Direction | Args | Purpose |
|---------|-----------|------|---------|
| `request_scene_tree` | Server -> Game | none | Request full scene tree dump |
| `inspect_object` | Server -> Game | [object_id: int] | Request all properties of a node |
| `inspect_objects` | Server -> Game | [object_ids: Array, update: bool] | Batch inspect multiple nodes |
| `set_object_property` | Server -> Game | [object_id: int, property: String, value: Variant] | Set a property on a live node |
| `set_object_property_field` | Server -> Game | [object_id: int, property: String, value: Variant, field: String] | Set a specific field within a property |
| `suspend_changed` | Server -> Game | [suspended: bool] | Pause/resume game |
| `next_frame` | Server -> Game | none | Step one frame when suspended |
| `speed_changed` | Server -> Game | [speed: float] | Set time scale |
| `save_node` | Server -> Game | [object_id: int, path: String] | Save a node as PackedScene |

### Live Edit Commands (prefix: "scene:")

These operate on cached nodes and are used by the editor's live editing feature.

| Command | Direction | Args | Purpose |
|---------|-----------|------|---------|
| `live_set_root` | Server -> Game | [path: NodePath, scene_file: String] | Set live edit context |
| `live_node_path` | Server -> Game | [id: int, path: NodePath] | Map node ID to path |
| `live_node_prop` | Server -> Game | [id: int, property: String, value: Variant] | Set property on cached node |
| `live_node_call` | Server -> Game | [id: int, method: String, args...] | Call method on node |
| `live_create_node` | Server -> Game | [id: int, type: String, name: String] | Create new node |
| `live_remove_node` | Server -> Game | [id: int] | Remove node |

### Core Debugger Commands (no prefix)

| Command | Direction | Args | Purpose |
|---------|-----------|------|---------|
| `continue` | Server -> Game | none | Resume from breakpoint |
| `break` | Server -> Game | none | Force pause |
| `evaluate` | Server -> Game | [expression: String, frame: int] | Evaluate GDScript expression |
| `reload_scripts` | Server -> Game | [paths: Array] | Reload specific scripts |

### Game -> Server Messages

| Message | Meaning |
|---------|---------|
| `debug_enter` | Game hit breakpoint or pause |
| `debug_exit` | Game resumed |
| `scene_tree` (response) | Scene tree data (flat depth-first array) |
| `inspect_object` (response) | Object property data |
| `output` | Print/log output from game |
| `error` | Runtime error |
| `performance:profile_frame` | Per-frame metrics |

**Confidence:** HIGH for scene commands (verified from `scene_debugger.h` and `.cpp`), MEDIUM for exact response formats (inferred from source, not tested)

---

## Input Injection Strategy

### The Problem

The stock Godot debugger protocol does NOT have a dedicated "inject input event" command. This is the biggest gap for the v2.0 goal of simulating player input.

### Available Approaches

**Approach 1: GDScript Automation Autoload (Recommended)**

Deploy a small GDScript autoload (`gdauto_bridge.gd`) into the target project. This script:
- Listens for custom properties set via `set_object_property`
- Translates property changes into `Input.parse_input_event()` calls
- Reports game state back via the debugger's output channel

gdauto already has all the infrastructure to do this:
- `configparser`-based project.godot manipulation (add autoload entry)
- .gd file generation (write the bridge script)
- Cleanup after session (remove autoload entry, delete script)

The bridge script approach is what PlayGodot also uses (though they do it in C++ in a Godot fork). A GDScript autoload achieves the same result without requiring a modified engine.

**Approach 2: `live_node_call` for Method Invocation**

Use the `live_node_call` debugger command to call `Input.parse_input_event()` directly on the Input singleton. This avoids needing a bridge script but depends on:
- The live edit system being active
- Correctly encoding InputEvent subclass instances as Variant (complex)
- The node ID mapping being set up correctly

**Risk:** InputEvent objects contain nested types (Vector2 for position, etc.) that must be correctly serialized as Variants. The live_node_call mechanism is designed for simple property changes in the editor, not for constructing complex objects.

**Approach 3: `evaluate` Command**

Use the debugger's expression evaluation to run GDScript like:
```gdscript
var ev = InputEventMouseButton.new(); ev.position = Vector2(100, 200); ev.pressed = true; Input.parse_input_event(ev)
```

**Risk:** Expression evaluation requires the game to be paused at a breakpoint. It cannot be used during normal game execution.

### Recommendation

Use **Approach 1** (GDScript autoload bridge) as the primary strategy for v2.0. It works with stock Godot, requires no engine modifications, and provides a clean interface for input injection.

The bridge script pattern also opens the door for custom game state queries beyond what the debugger protocol exposes (e.g., "get the score", "check if the player is alive").

**Confidence:** MEDIUM (approach is sound but untested; PlayGodot validates the concept with a different implementation)

---

## Component Architecture

### New Components

```
src/gdauto/
  debugger/                     # NEW: Debugger bridge package
    __init__.py                 # Public API: connect(), DebugSession
    variant.py                  # Variant binary encoder/decoder
    protocol.py                 # Message framing (length-prefix, Array wrapping)
    session.py                  # Async TCP server + session lifecycle
    commands.py                 # High-level command methods (get_tree, set_property, etc.)
    bridge.py                   # GDScript autoload bridge generation + injection
    models.py                   # Dataclasses for scene tree, node info, properties
    errors.py                   # DebuggerError subclasses
  commands/
    debug.py                    # NEW: Click command group for debugger commands
```

### Modified Components

```
src/gdauto/
  cli.py                        # Add: cli.add_command(debug)
  backend.py                    # Add: launch_game() method (non-blocking subprocess)
  errors.py                     # Add: DebuggerConnectionError, DebuggerTimeoutError
  output.py                     # No changes needed (emit/emit_error work as-is)
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `debugger/variant.py` | Encode/decode Godot Variant binary format | `protocol.py` |
| `debugger/protocol.py` | Frame/unframe messages (length prefix + Array wrapping) | `session.py`, `variant.py` |
| `debugger/session.py` | TCP server lifecycle, async send/recv, connection state | `protocol.py`, `commands.py` |
| `debugger/commands.py` | High-level async methods: `get_scene_tree()`, `set_property()`, `inject_input()` | `session.py`, `models.py` |
| `debugger/bridge.py` | Generate and inject gdauto_bridge.gd autoload into target project | `formats/project_cfg.py` |
| `debugger/models.py` | Dataclasses: `SceneNode`, `NodeProperty`, `RemoteSceneTree` | `commands.py` |
| `debugger/errors.py` | Error types for connection, timeout, protocol failures | All debugger modules |
| `commands/debug.py` | Click command group: `debug connect`, `debug tree`, `debug get`, `debug set`, `debug input`, `debug assert` | `debugger/commands.py`, `output.py` |
| `backend.py` (modified) | Add `launch_game()` for non-blocking game process management | `commands/debug.py` |

---

## Data Flow

### Session Lifecycle

```
1. User: gdauto debug connect --project ./my-game
   |
   v
2. bridge.py: inject gdauto_bridge.gd into project, add autoload to project.godot
   |
   v
3. session.py: start TCP server on port 6007
   |
   v
4. backend.py: launch_game() -> subprocess.Popen(godot --path ./my-game --remote-debug tcp://127.0.0.1:6007)
   |
   v
5. session.py: accept() -> game connects
   |
   v
6. session.py: enter command loop (ready for user commands)
   |
   v
7. User: gdauto debug tree (or other commands, using session file/socket for state)
   |
   v
8. commands.py: send "scene:request_scene_tree" -> receive scene tree response
   |
   v
9. User: gdauto debug disconnect
   |
   v
10. session.py: close TCP connection
    |
    v
11. backend.py: terminate game process
    |
    v
12. bridge.py: remove autoload from project.godot, delete gdauto_bridge.gd
```

### Command Data Flow (e.g., `debug tree`)

```
Click command (debug.py)
  |-- asyncio.run(async_get_tree())
       |-- session.send_message("scene:request_scene_tree", [])
       |    |-- protocol.encode_message(["scene:request_scene_tree"])
       |    |    |-- variant.encode(Array["scene:request_scene_tree"])
       |    |    |-- returns: bytes (length-prefixed)
       |    |-- tcp_writer.write(encoded_bytes)
       |
       |-- response = session.recv_message(timeout=5.0)
       |    |-- tcp_reader.read(4) -> message_length
       |    |-- tcp_reader.read(message_length) -> payload
       |    |-- variant.decode(payload) -> Array[...]
       |    |-- returns: decoded Variant data
       |
       |-- models.parse_scene_tree(response) -> RemoteSceneTree
       |-- return RemoteSceneTree as dict
  |
  |-- emit(tree_dict, human_formatter, ctx)
```

---

## Session State Management

### The Problem

Click commands are one-shot: each invocation is a separate process. A debugger session must persist across multiple command invocations.

### Options Analyzed

**Option A: Long-running foreground process**

One `gdauto debug connect` command that starts an interactive REPL-like loop. All commands happen within this single process.

- Pro: Simple; no inter-process communication needed
- Con: Blocks the terminal; incompatible with agent workflows where commands are issued one at a time
- Con: Cannot be used from Claude Code (which runs individual CLI commands)

**Option B: Background daemon with session file**

`gdauto debug connect` starts a background TCP server process, writes a session file (`.gdauto-session.json`) with PID, port, and connection state. Subsequent commands read the session file and communicate with the daemon.

- Pro: Matches CLI-native workflow; each command is independent
- Con: Daemon management complexity (PID files, zombie processes, cleanup)
- Con: Adds IPC between CLI commands and daemon

**Option C: Per-command connection reuse via session file (Recommended)**

`gdauto debug launch` starts the game with `--remote-debug` and writes a session file. Each subsequent command (`debug tree`, `debug set`, etc.) reads the session file, connects to the game directly (or maintains a connection pool), performs the operation, and exits. The session file tracks: game PID, port, bridge script state.

Wait: this doesn't work because gdauto IS the server, not the client. The game connects TO us.

**Option D: Background server process (Recommended)**

`gdauto debug launch` spawns a background process that:
1. Starts the TCP server
2. Launches the game
3. Accepts the game's connection
4. Listens on a local Unix/TCP socket for commands from subsequent CLI invocations
5. Writes session info to `.gdauto-session.json`

Subsequent commands (`debug tree`, `debug set`) connect to the background server via the local socket, issue commands, receive responses, and exit.

- Pro: Clean CLI interface; each command is independent
- Pro: Compatible with agent workflows
- Con: Two levels of networking (game <-> server <-> CLI commands)
- Con: More complex implementation

**Option E: Single-command workflow with embedded session (Simplest viable)**

Each debugger command is self-contained: it starts the server, launches the game, waits for connection, performs the operation, and tears down. For multi-command workflows, a `debug run` command accepts a script/sequence of operations.

- Pro: No daemon, no session files, no IPC
- Con: Slow (game boot per command); only works for simple operations
- Con: Fine for `debug run-script` but bad for interactive exploration

### Recommendation: Hybrid of D and E

**Phase 1 (MVP):** Implement Option E. Each command is self-contained. A `debug run` command accepts a YAML/JSON script defining a sequence of operations (launch, wait, interact, assert, quit). This covers the primary use case: automated game testing from an agent.

**Phase 2 (Enhancement):** Implement Option D. Add `debug launch` (background server) and `debug connect` (attach to existing session) for interactive exploration workflows.

The rationale: the v2.0 milestone's stated goal is "closing the write-code-to-test-it loop" for agents. Agents issue a single command with a test script, not interactive exploratory sessions. Option E serves this directly.

**Confidence:** MEDIUM (architectural judgment call; the hybrid approach is pragmatic but untested)

---

## Async/Sync Bridge Pattern

### The Approach

Keep Click commands synchronous. Use `asyncio.run()` at the boundary of each debugger command handler. The async code lives entirely within the `debugger/` package.

```python
# commands/debug.py
@debug.command("tree")
@click.pass_context
def debug_tree(ctx: click.Context, ...) -> None:
    """Get the live scene tree from a running game."""
    config: GlobalConfig = ctx.obj
    try:
        result = asyncio.run(_async_debug_tree(...))
    except DebuggerError as exc:
        emit_error(exc, ctx)
        return
    emit(result, _print_scene_tree, ctx)


async def _async_debug_tree(...) -> dict:
    """Async implementation of debug tree command."""
    async with DebugSession(port=port) as session:
        await session.launch_game(project_path, backend)
        await session.wait_for_connection(timeout=10.0)
        tree = await session.get_scene_tree()
        return tree.to_dict()
```

### Why Not asyncclick

asyncclick (v8.3.0.7) replaces `import click` with `import asyncclick`, making ALL commands async. This creates risk:
- Existing 28 synchronous commands would need validation under the new runtime
- rich-click compatibility is unverified with asyncclick
- asyncclick requires Python 3.11+ (our floor is 3.12, so compatible, but adds a dependency)
- The async event loop overhead is unnecessary for file-manipulation commands

`asyncio.run()` in individual command handlers is simpler, lower-risk, and keeps the existing CLI stack untouched.

**Confidence:** HIGH (standard Python pattern, no external dependency needed)

---

## Variant Codec Implementation

### Build vs Reuse

**Existing library: gdtype-python**
- Last commit: September 2022 (3.5 years stale)
- Targets Godot 4.0 beta (not 4.5+)
- Unknown Python 3.12+ compatibility
- Two functions: `serialize()` and `deserialize()`
- No type stubs, no tests visible for Godot 4.x types

**Recommendation: Build a custom Variant codec.**

Rationale (same logic that justified the custom .tscn/.tres parser):
1. The codec is well-specified (official Godot docs enumerate every type ID)
2. We only need ~10 of 29 types for debugger communication (null, bool, int, float, String, Vector2, Vector3, Array, Dictionary, NodePath, Object/EncodedObjectAsID)
3. Full control over error handling and type mapping to Python types
4. No risk from abandoned upstream
5. ~300-500 lines of Python using `struct.pack/unpack`

The codec is a pure function pair: `encode(value) -> bytes` and `decode(data, offset) -> (value, bytes_consumed)`. It maps:

| Godot Type | Python Type |
|------------|-------------|
| null | None |
| bool | bool |
| int | int |
| float | float |
| String | str |
| Vector2 | tuple[float, float] or dataclass |
| Vector3 | tuple[float, float, float] or dataclass |
| Array | list |
| Dictionary | dict |
| NodePath | str (with path parsing) |
| Object (EncodedObjectAsID) | int (object_id) |

**Confidence:** HIGH (the binary serialization format is stable and well-documented)

---

## Patterns to Follow

### Pattern 1: Context Manager for Session Lifecycle

```python
class DebugSession:
    async def __aenter__(self) -> DebugSession:
        self._server = await asyncio.start_server(
            self._handle_connection, "127.0.0.1", self.port
        )
        return self

    async def __aexit__(self, *args) -> None:
        if self._game_process:
            self._game_process.terminate()
        self._server.close()
        await self._server.wait_closed()
        self._cleanup_bridge()
```

**Why:** Ensures cleanup (game process termination, TCP server shutdown, bridge script removal) even on exceptions. Matches the existing pattern where `GodotBackend` is created per-command.

### Pattern 2: Request-Response Correlation

The debugger protocol does not have request IDs. Responses are correlated by message type, not by request ID. This means:

- Send `scene:request_scene_tree` -> wait for the next `scene_tree` response
- Send `scene:inspect_object` -> wait for the next `inspect_object` response
- Only one outstanding request of each type at a time

Implement this with an asyncio event/future per expected response type:

```python
class DebugSession:
    _pending: dict[str, asyncio.Future]

    async def request_scene_tree(self) -> RemoteSceneTree:
        future = self._loop.create_future()
        self._pending["scene_tree"] = future
        await self._send("scene:request_scene_tree", [])
        return await asyncio.wait_for(future, timeout=5.0)
```

### Pattern 3: Message Dispatch Loop

A background task reads messages from the TCP connection and dispatches them:

```python
async def _recv_loop(self) -> None:
    while self._connected:
        msg_type, args = await self._protocol.read_message(self._reader)
        if msg_type in self._pending:
            self._pending.pop(msg_type).set_result(args)
        elif msg_type == "output":
            self._output_buffer.append(args)
        elif msg_type == "error":
            self._error_buffer.append(args)
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Blocking TCP in Click Handlers

**What:** Using synchronous `socket.recv()` in Click command handlers.
**Why bad:** Blocks the entire process; no timeout control; cannot handle concurrent sends and receives (the game sends unsolicited messages like `output` and `performance` data).
**Instead:** Use asyncio with `asyncio.run()` at the Click boundary.

### Anti-Pattern 2: Global Singleton Session

**What:** A module-level `DebugSession` instance shared across commands.
**Why bad:** Click commands are separate process invocations. A global variable dies with the process.
**Instead:** Session state lives in a background process (Phase 2) or is reconstructed per command from a session file.

### Anti-Pattern 3: Mixing Bridge Script with User Code

**What:** Modifying user's existing GDScript files to add automation hooks.
**Why bad:** Risk of corrupting user code; merge conflicts; hard to clean up.
**Instead:** The bridge is a standalone .gd file added as an autoload, completely separate from user code. Clean removal on session end.

### Anti-Pattern 4: Assuming Response Ordering

**What:** Assuming the next message received is the response to the last command sent.
**Why bad:** The game sends unsolicited messages (performance data, print output, errors) at any time.
**Instead:** Dispatch messages by type and use futures for expected responses.

---

## Scalability and Complexity Considerations

| Concern | MVP (single game) | Future (multiple games) |
|---------|-------------------|-------------------------|
| Connections | 1 game, 1 session | Multiple game instances on different ports |
| Protocol overhead | Negligible (debugger messages are small) | Same |
| Latency | <10ms local TCP | Same for local; network latency for remote |
| Memory | ~16 MiB buffers (matching Godot's allocation) | Per-connection |
| Game boot time | 2-5 seconds | Parallelizable |
| Bridge cleanup | Must always run (even on crash) | `atexit` handler + signal handler |

---

## Build Order (Dependency Graph)

The following build order respects component dependencies:

```
Phase 1: Variant Codec + Protocol Layer
  variant.py (no deps, pure encode/decode)
  protocol.py (depends on variant.py)
  models.py (no deps, pure dataclasses)
  errors.py (extends gdauto.errors)

Phase 2: Session + Connection Management
  session.py (depends on protocol.py)
  backend.py modifications (add launch_game)

Phase 3: Bridge Script System
  bridge.py (depends on formats/project_cfg.py, file I/O)

Phase 4: High-Level Commands
  commands.py (depends on session.py, models.py, bridge.py)

Phase 5: CLI Integration
  commands/debug.py (depends on commands.py, output.py)
  cli.py modification (add debug group)

Phase 6: Assertion/Verification Layer
  Additional commands in commands.py for assert/verify patterns
  Test script runner (YAML/JSON test script execution)
```

Each phase can be independently tested:
- Phase 1: Unit tests with known binary data (golden byte sequences)
- Phase 2: Integration tests with a mock TCP client
- Phase 3: Unit tests (file generation + project.godot manipulation)
- Phase 4: Integration tests with a real Godot game instance
- Phase 5: CLI runner tests (CliRunner)
- Phase 6: E2E tests with sample game projects

---

## Key Risks and Open Questions

### Risk 1: Variant Encoding Edge Cases
The binary serialization spec covers 29 types. We plan to implement ~10. If a game sends an unexpected type in a response, the decoder must handle it gracefully (skip or error, not crash).

**Mitigation:** Implement a fallback that reads the type header, computes the data size, and skips unknown types with a warning.

### Risk 2: Message Ordering and Timing
The game sends unsolicited messages (performance data, print output). If we don't drain these, the TCP buffer fills and the game blocks.

**Mitigation:** The recv_loop must always be running and draining messages into buffers, regardless of whether a command is waiting for a response.

### Risk 3: Bridge Script Cleanup on Crash
If gdauto crashes mid-session, the bridge script and autoload entry remain in the project.

**Mitigation:** Use `atexit` handler, signal handlers (SIGINT, SIGTERM), and a cleanup check on next `debug launch` that detects and removes stale bridge artifacts.

### Risk 4: Input Injection via Bridge Requires Game Cooperation
The bridge script must be loaded by the game to inject input. If the project's autoload system is broken or the bridge script has a syntax error, input injection fails silently.

**Mitigation:** Validate the bridge script with `godot --check-only` before launching the game. Include error reporting in the bridge script that sends diagnostics via the debugger output channel.

### Open Question 1: Scene Tree Response Format
The exact binary format of the scene tree response (from `request_scene_tree`) is described as "flat list depth first" in the Godot source comments but the exact field layout needs to be reverse-engineered by sending the command and inspecting the response bytes. This will require empirical testing in Phase 2.

### Open Question 2: Property Serialization Completeness
`inspect_object` returns property names, values, types, and hints as a serialized array. The exact layout of this array (field order, delimiter patterns) needs empirical verification.

### Open Question 3: Windows Named Pipes vs TCP
For the Phase 2 daemon, inter-process communication between CLI commands and the background server could use Unix sockets (not available on Windows) or localhost TCP. Since gdauto runs on Windows (per the dev environment), localhost TCP is the safe choice.

---

## Sources

### Verified (HIGH confidence)
- [Godot `remote_debugger_peer.cpp`](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger_peer.cpp) - TCP client implementation, message framing, buffer sizes
- [Godot `scene_debugger.cpp`](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.cpp) - Scene debugger commands and handlers
- [Godot `scene_debugger.h`](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.h) - Public API surface
- [Godot `remote_debugger.cpp`](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger.cpp) - Core debugger commands and capture system
- [Godot Binary Serialization API docs](https://github.com/godotengine/godot-docs/blob/master/tutorials/io/binary_serialization_api.rst) - Variant type IDs and encoding
- [Godot InputEvent docs](https://docs.godotengine.org/en/stable/tutorials/inputs/inputevent.html) - Input.parse_input_event() API

### Reference Implementations (MEDIUM confidence)
- [PlayGodot](https://github.com/Randroids-Dojo/PlayGodot) - Python game automation via debugger protocol (requires forked Godot)
- [godot-vscode-plugin](https://github.com/godotengine/godot-vscode-plugin) - TypeScript debugger client with VariantDecoder
- [gdtype-python](https://github.com/anetczuk/gdtype-python) - Python Variant serializer (stale, Godot 4.0 beta era)
- [godot-binary-serialization (JS)](https://github.com/pietrum/godot-binary-serialization) - JavaScript Variant codec
- [godot-binary-serialization (Rust)](https://crates.io/crates/godot-binary-serialization) - Rust Variant codec

### Architecture Patterns (MEDIUM confidence)
- [asyncclick PyPI](https://pypi.org/project/asyncclick/) - Async Click fork (evaluated, not recommended)
- [Click async integration issue #2033](https://github.com/pallets/click/issues/2033) - Discussion of asyncio.run() pattern
- [Python asyncio streams docs](https://docs.python.org/3/library/asyncio-stream.html) - TCP client/server with asyncio
- [Godot DeepWiki: VSCode plugin debugging](https://deepwiki.com/godotengine/godot-vscode-plugin/4-debugging) - Debugger architecture overview
