# Feature Landscape: Live Game Interaction via Debugger Bridge

**Domain:** Godot engine runtime interaction, remote debugger protocol, agent-native game testing
**Researched:** 2026-03-29
**Overall confidence:** MEDIUM (protocol is undocumented; implementation details from source code analysis and reference implementations)

## Context

gdauto v2.0 adds live game interaction: connect to a running Godot instance, read game state, inject input, and verify behavior. This closes the "write code, launch, test, verify" loop for AI agents. The target validation scenario is an idle clicker game: launch, click a button, verify score increments, check label text updates.

Existing tools in this space: PlayGodot (Python, requires custom Godot fork), Godot MCP Pro (Node.js + WebSocket + editor plugin, 84 tools, $5), GDAI MCP (editor plugin, no runtime control), Coding-Solo/godot-mcp (launch + capture output only, no game interaction), godot-vscode-plugin (TypeScript, DAP-based, editor-integrated). None provide a standalone CLI tool with no editor dependency.

---

## Table Stakes

Features users expect for any debugger bridge claiming "live game interaction." Missing any of these makes the product non-functional for the stated goal.

| Feature | Why Expected | Complexity | Dependencies | Idle Clicker Validation |
|---------|-------------|------------|--------------|------------------------|
| TCP connection to Godot debugger port | Foundation for all interaction; Godot's `--remote-debug tcp://host:port` is the only external connection point | High | Godot Variant binary serialization (encode/decode), TCP socket management, connection lifecycle | Required: must connect before any interaction |
| Godot Variant binary encoder/decoder | All debugger messages use Variant-encoded Arrays; without this, no communication is possible | High | Binary serialization spec (type IDs 0-38, little-endian, 4-byte padding, length-prefixed framing) | Required: every message requires Variant encoding |
| Scene tree retrieval | Reading the node hierarchy is the foundation of game state inspection; maps to `scene:request_scene_tree` | Medium | TCP connection, Variant codec | Required: find the Button and Label nodes |
| Node property reading | Reading node properties (text, position, visibility, custom vars) at runtime; maps to `scene:inspect_object` | Medium | Scene tree retrieval (need object IDs), Variant codec | Required: read Label.text to verify score |
| Game launch with debugger connection | Start Godot with `--remote-debug` flag and establish connection; extends existing GodotBackend | Medium | Existing backend.py (binary discovery, subprocess management) | Required: must launch game to test it |
| Connection lifecycle management | Connect, reconnect on failure, clean disconnect, timeout handling; the connection is stateful TCP | Medium | TCP connection | Required: stable connection throughout test |
| Structured JSON output for all commands | Agent-native contract from v1.0; all debugger commands must support `--json` | Low | Existing output.py patterns | Required: agents consume JSON, not human text |

### Complexity Notes

**TCP + Variant codec (HIGH):** This is the hardest part of v2.0. Godot's debugger protocol is entirely undocumented. The wire format is: 4-byte length prefix (little-endian uint32) followed by a Variant-encoded Array. The Array contains `[message_name: String, data: Array]`. The Variant binary format has 39 type IDs (0=NIL through 38=PACKED_VECTOR4_ARRAY), each with specific encoding rules. Godot 4 added Vector4, Vector4i, Projection, StringName, and Callable types not present in Godot 3. The binary serialization spec is documented at `docs.godotengine.org/en/stable/tutorials/io/binary_serialization_api.html` and the source at `core/io/marshalls.cpp`. Reference implementations exist in JavaScript (pietrum/godot-binary-serialization, godot-vscode-plugin VariantDecoder) and Python (PlayGodot). All packets are padded to 4 bytes. The type header uses lower 16 bits for type ID and upper 16 bits for flags (bit 0 = ENCODE_FLAG_64 for 64-bit int/float).

**Scene tree retrieval (MEDIUM):** Godot 4 uses `scene:request_scene_tree` message. Response arrives as `scene:scene_tree` with serialized node hierarchy. The VS Code plugin parses this with `parse_next_scene_node()`. Godot 4 prefix convention: `scene:*` for scene debugger, `servers:*` for performance, core messages have no prefix.

---

## Differentiators

Features that set gdauto apart from existing tools. Not expected, but create the unique value proposition.

| Feature | Value Proposition | Complexity | Dependencies | Idle Clicker Validation |
|---------|-------------------|------------|--------------|------------------------|
| No editor dependency | Unlike every MCP server (requires editor running) and PlayGodot (requires custom fork), gdauto acts as the debugger server itself, receiving connections from stock Godot | High | Must implement TCP server that speaks Godot debug protocol, not just client | Core differentiator: `gdauto debug launch` starts game, game connects back |
| No custom Godot fork required | PlayGodot requires building a custom Godot binary. gdauto works with any stock Godot 4.5+ release | Critical | Limits us to what the stock debugger protocol supports (no custom automation commands) | Users install nothing extra |
| Node property modification at runtime | Change Label.text, Button.disabled, position, custom script variables while game runs; maps to `scene:live_node_prop` | Medium | Scene tree retrieval, object ID resolution, Variant encoding of new values | Write to Label.text to verify round-trip |
| Input event injection | Simulate mouse clicks, key presses, and named input actions; requires sending serialized InputEvent objects | High | Must construct InputEventMouseButton/InputEventKey as Variant-encoded Objects, route via debugger message or injected GDScript | Click the "+" button to test score increment |
| Assertion/verification DSL | `gdauto debug assert --node /root/Main/ScoreLabel --property text --equals "1"` for scriptable verification | Medium | Property reading, CLI argument parsing, comparison logic | `assert ScoreLabel.text == "1"` after click |
| Wait-for-condition with timeout | `gdauto debug wait --node /root/Main/Score --property value --gt 0 --timeout 5` blocks until condition met or times out | Medium | Property reading, polling loop, timeout management | Wait for score to update after click |
| Execution control (pause/resume/step) | Pause game, step one frame, resume; maps to `scene:suspend_changed`, `scene:next_frame` | Low | TCP connection, known message format | Pause, step, verify state changes deterministically |
| Game speed manipulation | `gdauto debug speed --scale 10` to fast-forward idle games; maps to `scene:speed_changed` | Low | TCP connection, single message | Fast-forward idle timers for testing |
| Method invocation on nodes | Call arbitrary methods on nodes: `gdauto debug call --node /root/Main --method add_score --args 10`; maps to `scene:live_node_call` | Medium | Object ID resolution, Variant encoding of arguments, method name validation | Call game logic directly for testing |
| Screenshot capture | Capture the current frame as PNG for visual verification; useful for AI agents that can process images | High | Requires either viewport texture extraction via debugger or a game-side autoload that responds to commands | Visual confirmation of game state |

### Key Differentiator Analysis

**Acting as debugger server (not client):** This is the architectural decision that makes or breaks the project. In Godot's model, the editor runs a TCP server on port 6007 and the game connects to it as a client via `--remote-debug tcp://host:6007`. gdauto must act as this server. This means:

1. gdauto opens a TCP server socket on a port (default 6007)
2. gdauto launches Godot with `godot --path <project> --remote-debug tcp://127.0.0.1:6007`
3. Godot's RemoteDebuggerPeerTCP connects to gdauto
4. gdauto sends commands (scene tree requests, property changes, input injection)
5. Godot responds with data (scene tree, property values, errors)

This is exactly what the Godot editor does. The VS Code plugin does this too (it runs a debug server). No formal handshake or authentication is required (confirmed from `remote_debugger_peer.cpp` source). Connection succeeds when TCP status reaches `STATUS_CONNECTED`.

**Input injection risk:** The stock debugger protocol includes `scene:live_node_call` which can invoke methods on nodes. This may allow calling `Input.parse_input_event()` or `get_viewport().push_input()` on the game side without any custom fork. If that path fails, a fallback is to write a tiny GDScript autoload that listens for a custom EngineDebugger message capture and translates it to input events. This autoload could be injected by gdauto into the project's autoload list before launch, then removed after. PlayGodot's approach of patching `remote_debugger.cpp` is more elegant but requires maintaining a custom fork.

---

## Anti-Features

Features to explicitly NOT build. Each would add complexity without serving the core use case.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| GDScript breakpoint debugging (step, inspect locals, call stack) | The VS Code plugin and Godot editor already do this well. Reimplementing a full script debugger is enormous scope with no agent value. Agents don't step through code interactively. | Focus on game state inspection and verification, not code debugging. If agents need to debug, they read error output. |
| Visual editor scene manipulation (live node creation/deletion/reparenting) | `scene:live_create_node`, `scene:live_remove_node`, etc. exist in the protocol, but live scene editing is editor territory. gdauto already has `scene create` for file-level manipulation. | Stick to reading state and modifying properties. Node creation belongs in file manipulation commands. |
| Performance profiling (FPS, draw calls, physics frame times) | The profiler protocol (`servers:*` messages) exists but is irrelevant for game testing. Performance profiling is a specialized workflow with its own visualization needs. | Omit entirely. Agents don't profile games. |
| Camera override and viewport manipulation | `scene:override_cameras`, `scene:transform_camera_2d/3d` exist for editor viewport control. No value for headless game testing. | Omit entirely. Screenshots (if implemented) use the game's own camera. |
| Audio debugging/muting | `scene:debug_mute_audio` exists. Irrelevant for automated testing. | Omit. Games can be launched with audio muted via project settings if needed. |
| Full DAP (Debug Adapter Protocol) implementation | The VS Code plugin implements DAP to integrate with VS Code's debugging UI. We don't need DAP; we need a CLI that speaks Godot's native protocol. | Use Godot's native message protocol directly. No DAP adapter needed. |
| WebSocket transport | Some Godot debug tools use WebSocket. The standard protocol is TCP. Adding WebSocket doubles transport complexity for no benefit when both endpoints are localhost. | TCP only, matching Godot's `--remote-debug tcp://` flag. |
| Replay/record gameplay sessions | Recording input sequences for playback is useful but is a major feature that can be layered on later. | Defer to a future milestone. The primitive operations (inject input, read state) are sufficient for v2.0. |
| Custom Godot plugin/autoload injection | MCP servers like tomyud1/godot-mcp require installing a Godot addon. PlayGodot requires a custom fork. Both add friction. | Use only what stock Godot's debugger protocol provides. Zero game-side modification. |
| Multi-instance debugger (connect to multiple games simultaneously) | Over-engineering for v2.0. One game connection at a time is sufficient. | Single connection model. If needed later, add connection multiplexing. |

---

## Feature Dependencies

```
Variant Binary Codec
  |
  +-- TCP Debugger Server
  |     |
  |     +-- Connection Lifecycle Management
  |     |     |
  |     |     +-- Game Launch with --remote-debug
  |     |     |     |
  |     |     |     +-- Scene Tree Retrieval
  |     |     |     |     |
  |     |     |     |     +-- Node Property Reading
  |     |     |     |     |     |
  |     |     |     |     |     +-- Node Property Modification
  |     |     |     |     |     +-- Assertion/Verification Layer
  |     |     |     |     |     +-- Wait-for-Condition
  |     |     |     |     |
  |     |     |     |     +-- Method Invocation
  |     |     |     |
  |     |     |     +-- Input Event Injection
  |     |     |     +-- Execution Control (pause/resume/step)
  |     |     |     +-- Game Speed Manipulation
  |     |     |
  |     |     +-- Error/Output Capture
  |     |
  |     +-- JSON Output (extends existing output.py)
```

### Critical Path

The critical path for the idle clicker test case is:

1. **Variant codec** (encode + decode all needed types)
2. **TCP server** (accept Godot's connection)
3. **Game launch** (subprocess with `--remote-debug` flag)
4. **Scene tree retrieval** (find nodes by path)
5. **Property reading** (read Label.text, score value)
6. **Input injection** (click the button)
7. **Assertion** (verify score changed)

Steps 1-3 are foundation. Steps 4-5 prove "read state." Step 6 proves "write input." Step 7 proves "verify."

---

## MVP Recommendation

### Phase 1: Protocol Foundation (Highest Risk)

Build the Variant codec and TCP debugger server. This is the highest-risk, highest-uncertainty phase. If the protocol implementation fails, everything else is blocked.

Prioritize:
1. **Variant binary encoder/decoder** covering types needed for debugger messages (NIL, BOOL, INT, FLOAT, STRING, STRING_NAME, ARRAY, DICTIONARY, VECTOR2, OBJECT, NODE_PATH; skip exotic types like Projection, AABB initially)
2. **TCP server** that accepts a Godot connection and can exchange messages
3. **Game launch** integration with existing GodotBackend

### Phase 2: Read Game State

Once connected, prove we can read the running game's state:
1. **Scene tree retrieval** (request and parse the node tree)
2. **Node property reading** (inspect individual nodes, get property values)
3. **Error/output capture** (receive print() and error messages from the game)

### Phase 3: Write to Game State

Prove we can affect the running game:
1. **Input event injection** (mouse clicks, key presses)
2. **Node property modification** (change values at runtime)
3. **Execution control** (pause, resume, step frame, speed change)
4. **Method invocation** (call node methods)

### Phase 4: Verification Layer

Build the assertion and testing primitives:
1. **Assertion commands** (compare property values against expected)
2. **Wait-for-condition** (poll until state matches or timeout)
3. **End-to-end workflow** (launch, interact, verify, report results)

### Defer to Post-MVP

- Screenshot capture (requires viewport texture extraction, complex encoding)
- Replay/record sessions
- Multi-instance connections
- Signal monitoring (await specific signals)
- Custom GDScript evaluation/injection

---

## Existing gdauto Capabilities to Leverage

| Existing Capability | How It Helps v2.0 |
|--------------------|--------------------|
| `GodotBackend` (backend.py) | Binary discovery, version validation, subprocess launch; extend with `--remote-debug` flag |
| Error hierarchy (errors.py) | Add `DebuggerError`, `ConnectionError`, `ProtocolError` following established pattern |
| Output formatting (output.py) | JSON output for all debugger commands, consistent with v1.0 contract |
| CLI structure (cli.py, commands/) | Add `debug` command group following existing patterns |
| .tres/.tscn parser knowledge | Understanding of Godot's data types (Vector2, Color, NodePath) informs Variant codec design |
| pytest infrastructure | E2E test patterns with `@pytest.mark.requires_godot` extend naturally to debugger tests |

---

## Competitive Landscape Summary

| Tool | Language | Editor Required | Custom Fork | Runtime Control | Input Injection | CLI | Agent-Native |
|------|----------|----------------|-------------|-----------------|-----------------|-----|-------------|
| Godot Editor | C++ | Yes (is the editor) | No | Full | No | No | No |
| godot-vscode-plugin | TypeScript | No (acts as server) | No | Breakpoints only | No | No | No |
| PlayGodot | Python | No | **Yes** | Full | Full | No (library) | No |
| Godot MCP Pro | Node.js | **Yes** | No | Full | Full | No (MCP) | Partial |
| Coding-Solo/godot-mcp | Python | No | No | Launch only | No | No (MCP) | Partial |
| tomyud1/godot-mcp | Node.js | **Yes** | No | None | No | No (MCP) | Partial |
| **gdauto v2.0** | Python | **No** | **No** | Read + Write | Full | **Yes** | **Yes** |

gdauto's unique position: the only tool that provides full runtime game interaction via CLI without requiring the Godot editor or a custom engine fork. The "agent-native" design (JSON output, scriptable commands, exit codes) is unmatched.

---

## Risk Assessment by Feature

| Feature | Technical Risk | Why | Mitigation |
|---------|---------------|-----|------------|
| Variant binary codec | HIGH | Undocumented protocol, 39 type IDs, encoding edge cases (64-bit flag, Object serialization, NodePath complex format) | Start with minimal type set; use godot-vscode-plugin VariantDecoder and PlayGodot as reference implementations; fuzz test against Godot's own encode/decode |
| TCP server accepting Godot connections | MEDIUM | No handshake documented; must handle connection timing (game may connect before server is ready) | Test with stock Godot binary; exponential backoff on connection; study remote_debugger_peer.cpp for client behavior |
| Input injection via stock protocol | HIGH | Stock debugger protocol may not support input injection natively; PlayGodot needed a custom fork for this | Investigate `scene:live_node_call` to call `Input.parse_input_event()` on game side; fallback: inject a minimal autoload script at launch time |
| Scene tree retrieval | LOW | Well-understood message (`scene:request_scene_tree`); VS Code plugin and editor both use this | Direct implementation from reference code |
| Property reading/modification | LOW-MEDIUM | `scene:inspect_object` and `scene:live_node_prop` are used by editor; may require specific object ID formats | Study VS Code plugin's object inspection flow |
| Assertion layer | LOW | Pure Python logic on top of property reading; no protocol risk | Standard implementation |

---

## Sources

### Official Documentation
- [Godot Binary Serialization API](https://docs.godotengine.org/en/stable/tutorials/io/binary_serialization_api.html) - Wire format specification
- [EngineDebugger class](https://docs.godotengine.org/en/stable/classes/class_enginedebugger.html) - Game-side debugger API
- [EditorDebuggerPlugin class](https://docs.godotengine.org/en/stable/classes/class_editordebuggerplugin.html) - Editor-side debugger plugin API
- [Overview of debugging tools](https://docs.godotengine.org/en/stable/tutorials/scripting/debug/overview_of_debugging_tools.html) - Debugging overview
- [Using InputEvent](https://docs.godotengine.org/en/stable/tutorials/inputs/inputevent.html) - Input event system

### Source Code (HIGH confidence)
- [remote_debugger_peer.cpp](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger_peer.cpp) - TCP connection, wire format, framing
- [remote_debugger.cpp](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger.cpp) - Message handling, command dispatch
- [scene_debugger.h](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.h) - 40+ scene debugger message types
- [engine_debugger.h](https://github.com/godotengine/godot/blob/master/core/debugger/engine_debugger.h) - Core debugger class interface
- [variant.h](https://github.com/godotengine/godot/blob/master/core/variant/variant.h) - Complete Variant type enumeration (0-38)

### Reference Implementations (MEDIUM confidence)
- [godot-vscode-plugin](https://github.com/godotengine/godot-vscode-plugin) - Official VS Code debugger; TypeScript VariantDecoder, scene tree/inspector
- [PlayGodot](https://github.com/Randroids-Dojo/PlayGodot) - Python game automation via debugger protocol (requires custom Godot fork)
- [pietrum/godot-binary-serialization](https://github.com/pietrum/godot-binary-serialization) - JavaScript Variant encoder/decoder
- [godot-binary-serialization (Rust crate)](https://crates.io/crates/godot-binary-serialization) - Rust Variant encoder/decoder

### Ecosystem Analysis (MEDIUM confidence)
- [Godot MCP Pro article](https://dev.to/y1uda/i-built-a-godot-mcp-server-because-existing-ones-couldnt-let-ai-test-my-game-47dl) - Why existing MCP servers fell short
- [Coding-Solo/godot-mcp](https://github.com/Coding-Solo/godot-mcp) - MCP with launch + output capture only
- [LeeSinLiang/godot-mcp](https://github.com/LeeSinLiang/godot-mcp) - MCP with remote debugger connection
- [tomyud1/godot-mcp](https://github.com/tomyud1/godot-mcp) - MCP with WebSocket to editor plugin
- [GdUnit4](https://github.com/godot-gdunit-labs/gdUnit4) - In-engine test framework with SceneRunner, input simulation, assertions
- [Godot-Claude-Skills](https://github.com/Randroids-Dojo/Godot-Claude-Skills) - Claude Code skills for Godot with PlayGodot integration

### Protocol Architecture (HIGH confidence)
- [Debugger refactor PR #36244](https://github.com/godotengine/godot/pull/36244) - Message format: Array with [command_name: String, data: Array]
- [Debugger Plugins PR #39440](https://github.com/godotengine/godot/pull/39440) - EditorDebuggerPlugin capture system
- [Editor-game communication discussion](https://github.com/godotengine/godot-proposals/discussions/10994) - EngineDebugger message patterns
- [Scene debugger messages PR #103297](https://github.com/godotengine/godot/pull/103297) - Message timing issues, message list
- [DAP proposal #1308](https://github.com/godotengine/godot-proposals/issues/1308) - Discussion of switching to DAP (not adopted)
