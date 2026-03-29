# Pitfalls Research: Live Game Interaction via Godot Debugger Protocol

**Domain:** Adding stateful TCP debugger bridge to existing synchronous CLI tool
**Researched:** 2026-03-29
**Confidence:** HIGH (Godot source code, official issues, prior art PlayGodot all cross-referenced)

## Critical Pitfalls

### Pitfall 1: No Protocol Version Negotiation

**What goes wrong:**
Godot's remote debugger protocol has no version negotiation or compatibility handshake. The TCP peer implementation in `remote_debugger_peer.cpp` simply opens a connection and starts sending/receiving length-prefixed binary Variant arrays. When Godot changes the protocol between versions (as happened between 3.x and 4.0, where the entire message format switched from flat parameters to array-based parameters, and new Variant types like Projection, Callable, RID, and Signal were added), clients break silently. The VSCode plugin required a complete rewrite for Godot 4.0 (PR #400, then again PR #452) because the protocol shifted under it with zero warning.

**Why it happens:**
The debugger protocol is an internal implementation detail of Godot, not a public API. The Godot team does not document protocol changes in release notes, does not version the wire format, and does not guarantee backwards compatibility. The `scene:request_scene_tree` message format in Godot 4.x differs from Godot 3.x's `request_scene_tree`, but nothing in the protocol tells you which version you are talking to.

**How to avoid:**
- Probe for Godot version at connection time by sending known-safe messages and checking responses
- Build a version detection layer that identifies which Godot release is connected before issuing commands
- Design the serialization layer as swappable; isolate all Variant encoding/decoding behind an interface so version-specific quirks can be handled per-version
- Pin minimum supported version to Godot 4.5 (matching existing gdauto constraint) and test against 4.5 and 4.6 specifically
- Monitor Godot's `core/debugger/` and `scene/debugger/` directories in the main repository for changes between releases

**Warning signs:**
- Variant decode errors: `"strlen < 0 || strlen + pad > len"` returning `ERR_FILE_EOF` (issue #94212)
- Corrupted headers: `"(header & 0xFF) >= Variant::VARIANT_MAX"` (indicates version mismatch in type IDs)
- Silently empty responses where data was expected
- Messages that worked on one Godot version returning no response on another

**Phase to address:**
Phase 1 (Protocol Foundation). Version detection must be the first thing implemented after raw TCP connection. Every subsequent feature depends on knowing the exact Godot version.

---

### Pitfall 2: Binary Variant Serialization Is Harder Than It Looks

**What goes wrong:**
Godot's binary Variant format (documented at `docs.godotengine.org/en/stable/tutorials/io/binary_serialization_api.html`) requires encoding 29+ type IDs with specific padding, flag handling, and nested structures. The `ENCODE_FLAG_64` flag (bit 0 of the upper 16 bits of the 4-byte header) switches integers and floats between 32-bit and 64-bit representations. The VSCode plugin's Godot 4 debugger fix (PR #400) explicitly noted that "Variants need to handle ENCODE_FLAG_64, only handled correctly for decoding. Encoding is done without this flag (bigint is the only exception)." Typed arrays of resources trigger encoding errors in Godot itself (issue #90721: `"Condition '!p_full_objects' is true"`). Dynamically growing typed arrays cause buffer corruption during remote inspection (issue #94212, still unresolved).

**Why it happens:**
- The format specification is incomplete: the docs describe atomic types well but gloss over edge cases in Object, RID, and resource serialization
- No existing Python implementation exists to reference (PlayGodot has one in its `variant.py` but requires a custom Godot fork; pietrum/godot-binary-serialization is JavaScript and 60-70% complete)
- The encoding must match `marshalls.cpp` byte-for-byte; any deviation causes silent corruption or crashes on the Godot side
- 4-byte padding rules interact subtly with string lengths and nested structures

**How to avoid:**
- Study PlayGodot's `variant.py` as a reference implementation (it is the only known Python Variant serializer for Godot 4)
- Write exhaustive round-trip tests: encode a value in Python, decode it in Godot via a test scene, verify equality, and vice versa
- Start with only the types needed for scene tree inspection (String, int, float, bool, Array, Dictionary, NodePath) and add others incrementally
- Use `struct.pack('<...')` consistently (little-endian) and enforce 4-byte alignment at every boundary
- Test with Godot's own `bytes_to_var()` / `var_to_bytes()` as the ground truth validator
- Never encode Object or RID types from the Python side; these are Godot-internal and should only be received, not sent

**Warning signs:**
- Godot logs `"Error when trying to decode Variant"` when receiving from Python client
- Connection drops immediately after sending a malformed packet
- Integer values arriving as wrong numbers (32-bit vs 64-bit flag mismatch)
- Strings decoded with garbage trailing bytes (padding error)

**Phase to address:**
Phase 1 (Protocol Foundation). The Variant serializer is the lowest-level building block. Everything above it (messages, commands, responses) depends on byte-perfect serialization.

---

### Pitfall 3: gdauto Must Be the TCP Server, Not the Client

**What goes wrong:**
Developers assume they can connect to a running Godot instance as a TCP client. This is backwards. In Godot's architecture, the editor (or any debug server) listens on a port, and the game connects to it as a client using `--remote-debug tcp://host:port`. If gdauto tries to connect to the game, there is nothing listening. gdauto must bind a TCP port and then launch the Godot game with `--remote-debug tcp://127.0.0.1:<port>` pointing back to gdauto.

**Why it happens:**
Most debugger protocols (Chrome DevTools Protocol, GDB remote serial protocol, LLDB) have the debuggee listen and the debugger connect. Godot inverts this: the debug server (editor) listens, and the debuggee (game) connects. This inversion is not intuitive and is poorly documented (the official docs still lack a guide on remote debugging per issue #11245 in godot-docs).

**How to avoid:**
- gdauto opens a TCP server socket on a configurable port (default 6007)
- gdauto then launches the Godot game binary with `--remote-debug tcp://127.0.0.1:<port>`
- gdauto waits for the game to connect (with a timeout)
- After connection, gdauto owns the lifecycle: it can send commands and read responses
- Handle the case where the port is already in use (another editor or gdauto instance); auto-increment or fail with a clear error

**Warning signs:**
- `Connection refused` when trying to connect to the game process
- TCP connect hangs indefinitely (nothing is listening on the game side)
- Port 6007 already bound by the Godot editor, causing `EADDRINUSE`

**Phase to address:**
Phase 1 (Protocol Foundation). The connection architecture must be correct from the start; getting this wrong means rewriting the entire transport layer.

---

### Pitfall 4: Sync-to-Async Bridge in a Click CLI

**What goes wrong:**
gdauto's 28 existing commands are synchronous Click handlers. The debugger bridge requires a long-lived TCP connection with asynchronous message handling (Godot sends unsolicited messages like breakpoint hits, scene tree changes, and error reports). Mixing asyncio with synchronous Click commands causes one of: (a) blocking the event loop on synchronous file operations, (b) losing messages while waiting synchronously for a specific response, (c) `RuntimeWarning: coroutine was never awaited` when Click invokes an async handler.

Click has no built-in async support (tracked in Click issue #2033, open since 2021). The common workaround is `asyncio.run()` inside each command, but this creates a new event loop per command invocation, making it impossible to maintain a persistent connection across commands.

**Why it happens:**
gdauto was designed as a stateless, fire-and-forget CLI (parse files, write files, exit). The debugger bridge is fundamentally stateful (connect, send multiple commands, wait for responses, maintain session). These are architecturally incompatible paradigms that require a deliberate integration strategy.

**How to avoid:**
- Create a `DebugSession` context manager that owns the asyncio event loop and TCP connection
- Use `asyncio.run()` at the command level (each `gdauto debug *` command starts and stops a session)
- For commands that need multiple round-trips (e.g., `debug inspect-tree` then `debug set-property`), support a `--session-file` that stores connection info for reconnection, or provide a `debug shell` REPL mode that maintains a single session
- Keep all existing synchronous commands untouched; the async machinery lives only in the new `debug` command group
- Use `asyncio.wait_for(coro, timeout=N)` for every network operation; never await without a timeout
- Consider whether the debugger commands should shell out to a long-running subprocess (sidestep the async problem entirely)

**Warning signs:**
- Tests hanging because an event loop is blocked
- `RuntimeError: This event loop is already running` (nested asyncio.run calls)
- Messages from Godot arriving but being silently dropped because no one is reading the socket

**Phase to address:**
Phase 1 (Protocol Foundation) for the architecture decision. Phase 2 (Commands) for the actual Click integration. The async strategy must be decided before writing any commands.

---

### Pitfall 5: Input Injection Does Not Work in Headless Mode

**What goes wrong:**
`Input.parse_input_event()` silently fails when Godot runs with `--headless`. The `DisplayServerHeadless` has no window concept, so input events are never delivered to the scene tree. This is a fundamental architectural limitation in Godot, confirmed open since 2023 (issue #73557). The Godot developer Markus Sauermann explained: "Display server is responsible for delivering events from Input to the Window," and the headless display server has no window.

This means gdauto cannot inject input events (key presses, mouse clicks) into a headless Godot instance, which is the exact CI/CD scenario where automated testing is most valuable.

**Why it happens:**
Developers assume `--headless` means "no visible window" but that the engine still processes input normally. In reality, headless mode strips the entire display server, including the input delivery pipeline. This is not a bug; it is a design decision: headless mode is for import/export/server tasks, not interactive gameplay.

**How to avoid:**
- For CI: use Xvfb (X Virtual FrameBuffer) on Linux or a virtual display on Windows to provide a display server without a physical monitor. The `godot-setup` GitHub Action (lihop/godot-setup) handles this automatically.
- For local development: launch the game in windowed mode (not headless) with `--remote-debug` flag
- Alternatively, use `Viewport.push_input(event)` instead of `Input.parse_input_event()` for single-viewport scenarios (partial workaround, does not solve all cases)
- Design the input injection system to work via the debugger protocol's `scene:set_object_property` and `scene:live_node_call` messages, bypassing the input system entirely where possible (e.g., calling `button.emit_signal("pressed")` instead of simulating a click)
- Document clearly that `gdauto debug` commands require a windowed Godot instance or Xvfb, never `--headless`

**Warning signs:**
- Input injection commands "succeed" (no error) but nothing happens in the game
- CI tests pass when developers run them locally but fail in headless CI
- Mouse position queries return (0,0) or stale values

**Phase to address:**
Phase 2 (Input Injection) and Phase 4 (CI Integration). The input injection architecture must account for this from the start, and CI pipeline setup must include virtual display configuration.

---

### Pitfall 6: Remote Scene Tree Performance Degrades Catastrophically in Large Scenes

**What goes wrong:**
Requesting the scene tree via the debugger protocol in projects with many nodes causes severe performance degradation. At 3,000 nodes, the response becomes noticeably slow. At 28,000 nodes, each request takes approximately 3 seconds. At 90,000 nodes, the system becomes "unusable" (issue #78645, open). The root cause: Godot sends the entire scene tree on every request, not incremental diffs. Additionally, the remote scene tree refresh mechanism in Godot 4.4.beta1-2 caused the entire editor to freeze every 1-2 seconds (issue #102525, fixed in 4.4.beta3).

**Why it happens:**
The scene debugger's `_msg_request_scene_tree` handler serializes every node in the tree into a single response message. There is no pagination, filtering, or delta compression. The 8MB output buffer in `remote_debugger_peer.cpp` can overflow with very large trees (at 108,935 nodes, a buffer overflow was observed that paradoxically made things faster by truncating the data).

**How to avoid:**
- Never request the full scene tree by default; provide `--max-depth` and `--path` filters that limit what is queried
- Cache the scene tree locally and only refresh on demand or at intervals
- For verification/assertion commands, query individual node properties via `scene:inspect_object` rather than requesting the entire tree
- Implement a timeout on scene tree requests (5 seconds default) with a clear error message explaining the scene is too large
- Consider implementing a GDScript autoload helper that provides filtered tree snapshots via `EngineDebugger.send_message`, bypassing the built-in full-tree mechanism

**Warning signs:**
- `gdauto debug tree` takes more than 2 seconds to return
- Memory usage spikes when processing scene tree responses
- TCP connection appears to stall during tree requests

**Phase to address:**
Phase 2 (Scene Tree Commands). Must be designed with filtering from day one; adding filtering later requires API changes.

---

### Pitfall 7: Connection Lifecycle Bugs (Game Crashes, Orphaned Sockets, Reconnection)

**What goes wrong:**
When the game process crashes, exits unexpectedly, or is killed by the user, the TCP connection breaks. If gdauto does not handle this gracefully: (a) socket resources leak (file descriptors accumulate), (b) the next `gdauto debug` command fails with `EADDRINUSE` because the previous server socket is still bound, (c) gdauto hangs waiting for a response that will never arrive. On Windows specifically, TCP socket error 10054 (WSAECONNRESET) occurs when the game crashes (mentioned in issue #27444). Port 6007 can also be held by orphaned processes (the Godot editor, OpenJDK processes from Android export, or previous gdauto instances).

**Why it happens:**
- TCP connections have no built-in "heartbeat"; a crashed game does not send a FIN packet, so the server does not learn about the crash until it tries to send/receive
- `SO_REUSEADDR` / `SO_REUSEPORT` are platform-specific and do not always prevent `EADDRINUSE` (especially on Windows where TIME_WAIT is aggressive)
- Click CLI commands do not have cleanup hooks by default; if a command is interrupted with Ctrl+C, socket cleanup may not run

**How to avoid:**
- Set `SO_REUSEADDR` on the server socket immediately after creation
- Implement a heartbeat: send a no-op message every N seconds and expect a response within M seconds; if no response, consider the connection dead
- Use `try/finally` or `atexit` handlers to close sockets, even on Ctrl+C
- Set TCP keepalive options (`SO_KEEPALIVE`, with aggressive keepalive intervals for local connections)
- On connection loss, print a clear error: "Game process disconnected (exit/crash). Re-run gdauto debug to start a new session."
- Never silently retry; if the game crashed, the user needs to know
- Use `socket.settimeout()` or `asyncio.wait_for()` on all receive operations; never block indefinitely

**Warning signs:**
- `gdauto debug` hangs after the game window closes
- `EADDRINUSE` on consecutive debug sessions
- Resource monitor shows orphaned TCP connections in CLOSE_WAIT state

**Phase to address:**
Phase 1 (Protocol Foundation) for socket lifecycle. Phase 3 (Session Management) for reconnection and cleanup.

---

### Pitfall 8: The Debugger Protocol Requires a GDScript Autoload for Full Functionality

**What goes wrong:**
The built-in scene debugger commands (`scene:request_scene_tree`, `scene:inspect_object`, `scene:set_object_property`) provide read access and basic property modification. However, they do not support: (a) input injection, (b) arbitrary method calls on nodes, (c) signal emission, (d) custom queries (e.g., "find all nodes of type X"). PlayGodot solved this by forking Godot and adding C++ automation commands. Without a custom Godot build, gdauto must add a GDScript autoload that registers custom captures via `EngineDebugger.register_message_capture()` and handles commands like `gdauto:inject_input`, `gdauto:call_method`, `gdauto:query_nodes`.

This means gdauto v2.0 is no longer "zero dependency on Godot for file operations." It requires a GDScript helper to be loaded into the game project for live interaction features.

**Why it happens:**
The debugger protocol's built-in commands are designed for the editor's inspector, not for external automation. The message set covers scene tree browsing and property editing, but not input injection or arbitrary code execution. The `EngineDebugger.register_message_capture()` API exists precisely for extending the protocol from GDScript, but it requires code running inside the game.

**How to avoid:**
- Ship a minimal GDScript autoload file (`gdauto_bridge.gd`) that games can add to their project
- Provide a `gdauto debug init` command that copies the autoload script into the target project and registers it in `project.godot`
- Design the autoload to be version-aware (check gdauto protocol version on connect)
- Keep the autoload minimal (under 200 lines) to minimize intrusiveness
- Make it opt-in: basic features (tree inspection, property reading) work without the autoload; advanced features (input injection, method calls) require it
- Document clearly which commands need the autoload and which do not

**Warning signs:**
- Input injection commands fail silently (no registered capture for `gdauto:*` messages)
- `EngineDebugger.send_message()` calls in the autoload return with no effect (debugger not connected)
- Version mismatch between autoload script and gdauto CLI version

**Phase to address:**
Phase 1 (Protocol Foundation) for the architecture decision. Phase 2 (Input Injection / Method Calls) for the autoload implementation. This is a fundamental design choice that affects every subsequent phase.

---

### Pitfall 9: Testing Debugger-Dependent Features in CI Is Extremely Fragile

**What goes wrong:**
Tests that require a running Godot instance connected via TCP are inherently flaky because they depend on: (a) a Godot binary being available, (b) a TCP port being free, (c) the game launching and connecting within a timeout, (d) the game's scene tree being in the expected state, (e) no other process grabbing the port between allocation and connection. Any of these can fail in CI environments where resources are constrained, port allocation is unpredictable, and process scheduling is non-deterministic.

**Why it happens:**
The existing gdauto test suite uses `@pytest.mark.requires_godot` for E2E tests that need the Godot binary. The debugger tests are strictly harder: they need the binary, a running game instance, a successful TCP connection, and synchronized state. Each additional dependency multiplies the failure surface.

**How to avoid:**
- Layer the test pyramid aggressively:
  - Unit tests: Variant serializer round-trips (no Godot needed, pure Python)
  - Unit tests: Message framing encode/decode (no Godot needed)
  - Integration tests: TCP server lifecycle (use a mock client, no Godot needed)
  - Integration tests: Mock debugger protocol (Python server + Python client playing both roles)
  - E2E tests: Actual Godot connection (few tests, heavily timeouoted, `@pytest.mark.requires_godot`)
- Use dynamic port allocation (`port=0` lets the OS pick a free port) to avoid port conflicts
- Set aggressive timeouts on E2E tests (10 seconds per test, not 60)
- Create a minimal Godot test project (1-2 nodes, no heavy assets) specifically for debugger tests
- Retry E2E tests once on failure (CI flake tolerance) but never more; repeated retries hide real bugs
- Run E2E tests in a separate CI job that can fail without blocking the main test suite
- On Linux CI: use Xvfb via `xvfb-run` or the `godot-setup` GitHub Action. On Windows CI: Godot's windowed mode works without a display server but may need `--rendering-driver opengl3` to avoid GPU-dependent failures

**Warning signs:**
- E2E tests pass locally but fail in CI more than 10% of the time
- Tests pass individually but fail when run in parallel (port conflicts)
- Test suite takes more than 60 seconds (connection timeouts accumulating)
- Tests depend on specific node names or tree structure that changes between test project versions

**Phase to address:**
Phase 1 (Protocol Foundation) for the test architecture. Every phase should maintain the test pyramid discipline. Phase 4 (CI Integration) for the CI pipeline configuration.

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hard-coding port 6007 | Simpler config | Conflicts with Godot editor, other gdauto instances, CI parallelism | Never; always make port configurable from day one |
| Synchronous socket reads in Click commands | Simpler code, no asyncio | Blocks on slow responses, hangs on game crash, drops unsolicited messages | Early prototyping only; must refactor before any user-facing release |
| Skipping Variant types you "don't need" | Faster initial implementation | Crashes on unexpected response data (Godot sends what it sends, not what you expect) | OK for Phase 1 if you handle unknown types gracefully (skip with warning, don't crash) |
| Testing only against one Godot version | Faster CI | Silent breakage when users run different Godot versions | Never for release; test at least 4.5 and 4.6 |
| Bundling the autoload directly into target project without cleanup | Quick integration | Leaves gdauto artifacts in user projects after uninstall | Never; provide `gdauto debug clean` to remove autoload |
| Using `time.sleep()` for synchronization | Easy timing control | Flaky tests, wastes CI time, hides race conditions | Never; use event-based synchronization (wait for specific message) |

## Integration Gotchas

Common mistakes when connecting to the Godot debugger protocol.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| TCP connection | Connecting as client to game process | gdauto must be the TCP server; game connects to gdauto via `--remote-debug` |
| Binary serialization | Assuming 32-bit integers (ignoring ENCODE_FLAG_64) | Check flag bit in header; support both 32-bit and 64-bit integer/float encoding |
| Message framing | Reading until newline or fixed size | Read 4-byte length prefix, then read exactly that many bytes; messages are length-prefixed binary |
| Scene tree messages | Using Godot 3.x message names (`request_scene_tree`) | Godot 4.x prefixes with `scene:` (e.g., `scene:request_scene_tree`) |
| Property modification | Sending complex objects (Resources, Nodes) as values | Only primitive types (String, int, float, bool) are reliably editable via remote inspector |
| Input events | Using `Input.parse_input_event()` in headless mode | Use `Viewport.push_input()` or call node methods directly via debugger protocol; headless has no input pipeline |
| Connection timing | Sending commands immediately after TCP accept | Wait for Godot to send initial handshake data (scene tree setup messages); sending too early can desync the protocol state |
| Buffer sizes | Using small receive buffers | Godot uses 8MB input/output buffers; scene tree responses for large scenes can be several MB |

## Performance Traps

Patterns that work at small scale but fail as scenes grow.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full scene tree requests | 3+ second response time, memory spikes | Filter by path and depth; query individual nodes instead | 3,000+ nodes |
| Polling for property changes | High CPU, network congestion | Use debugger protocol notifications; poll only when no notification mechanism exists | Polling interval < 100ms with many properties |
| Serializing entire game state | Response exceeds 8MB buffer, connection drops | Request specific subtrees or properties; never request "everything" | Any non-trivial game scene |
| Synchronous request-response for every command | CLI feels slow, latency accumulates | Batch related queries into single operations; pipeline requests | 5+ round-trips per user command |
| Logging all protocol traffic | Disk fills, I/O bottleneck | Log at DEBUG level only, with truncation for large payloads | Any real game traffic |

## Security Considerations

Domain-specific security issues for a debugger bridge.

| Concern | Risk | Prevention |
|---------|------|------------|
| Debugger port open on 0.0.0.0 | Remote code execution via `scene:live_node_call` and method invocation | Bind to 127.0.0.1 only by default; require explicit `--bind` flag for non-loopback |
| Autoload script in shipped game | Debug functionality accessible in production builds | Autoload should check `OS.is_debug_build()` and disable itself in release; `gdauto debug clean` removes it |
| Arbitrary GDScript execution via debugger | Unintended side effects, data corruption | Scope autoload commands to specific safe operations; do not expose `eval()` or `Expression.execute()` |
| Port number predictability | Other processes on same machine can connect | Use random high ports by default; authenticate connections with a session token exchanged via stdout |

## UX Pitfalls

Common user experience mistakes for a debugger CLI tool.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent connection failures | User runs `gdauto debug tree` and gets no output, no error | Always emit a status message: "Connecting to Godot on port 6007..." then "Connected" or "Failed: reason" |
| Requiring manual autoload setup | Users must edit project.godot and copy scripts before first use | Provide `gdauto debug init` that handles everything; detect missing autoload and prompt |
| No session state feedback | User does not know if the game is still connected | Include connection status in `--json` output; provide `gdauto debug status` command |
| Dumping raw Variant data | Node properties as unformatted binary type names | Map Godot Variant types to human-readable Python equivalents; format Vector2 as "(x, y)" not "type_id=5" |
| Long timeouts on failure | User waits 30 seconds to learn the game is not running | Default timeout of 5 seconds for connection, 10 seconds for commands; configurable via `--timeout` |
| Breaking existing commands | Adding async machinery corrupts existing sync command behavior | Strict isolation: new `debug` command group only; zero changes to existing commands |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **TCP Connection:** Often missing graceful shutdown on Ctrl+C -- verify socket is released and port is free after interruption
- [ ] **Variant Serializer:** Often missing ENCODE_FLAG_64 handling -- verify 64-bit integers and doubles round-trip correctly
- [ ] **Scene Tree:** Often missing handling of very large trees -- verify timeout and error behavior at 10,000+ nodes
- [ ] **Property Modification:** Often missing type coercion -- verify that setting a float property with an int value works (Godot is strict about Variant types)
- [ ] **Input Injection:** Often missing coordinate system awareness -- verify mouse coordinates match the game's viewport resolution, not screen resolution
- [ ] **Autoload Bridge:** Often missing cleanup command -- verify `gdauto debug clean` removes all traces from the project
- [ ] **Error Messages:** Often missing Godot-side error context -- verify that when Godot logs an error, gdauto surfaces it to the user
- [ ] **CI Tests:** Often missing virtual display setup -- verify E2E tests run on headless Linux CI with Xvfb
- [ ] **Windows Support:** Often missing handling of WSAECONNRESET (error 10054) -- verify game crash does not leave gdauto hanging on Windows
- [ ] **Multiple Sessions:** Often missing port conflict handling -- verify two gdauto instances on different ports can debug different games simultaneously

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Protocol version mismatch | MEDIUM | Add version probe at connection time; isolate version-specific code behind adapter pattern; write migration guide for new Godot versions |
| Variant serializer bug | LOW | Fix the specific type encoding; round-trip test catches it; no architectural change needed |
| Wrong connection direction | HIGH | Requires rewriting transport layer from client to server; this is why getting it right in Phase 1 matters |
| Async/sync bridge failure | HIGH | If wrong pattern chosen, every command must be rewritten; spike-test the async strategy in Phase 1 before committing |
| Input injection in headless | MEDIUM | Switch from headless to Xvfb in CI; document the requirement; add error detection for headless mode |
| Scene tree performance | LOW | Add filtering parameters to commands; does not require protocol changes |
| Connection lifecycle bugs | MEDIUM | Add heartbeat, timeout, cleanup handlers; mostly additive changes |
| Missing autoload | LOW | Add detection and `debug init` command; no architectural change |
| Flaky CI tests | MEDIUM | Restructure test pyramid; add mock protocol tests; reduce E2E test count; takes time but not risky |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| No protocol version negotiation | Phase 1: Protocol Foundation | Version detection test against Godot 4.5 and 4.6 binaries |
| Variant serialization bugs | Phase 1: Protocol Foundation | Round-trip tests for all 20+ supported Variant types; validated by Godot's `bytes_to_var()`/`var_to_bytes()` |
| Wrong connection direction (server vs client) | Phase 1: Protocol Foundation | Integration test: gdauto binds port, launches Godot, game connects, tree response received |
| Sync-to-async bridge | Phase 1: Protocol Foundation | Spike test: Click command that opens session, sends 3 commands, receives responses, closes cleanly |
| Input injection headless limitation | Phase 2: Input Injection | Test with `--headless` (expect clear error) and with Xvfb (expect success) |
| Scene tree performance | Phase 2: Scene Tree Commands | Performance test with 5,000-node test project; timeout within 5 seconds |
| Connection lifecycle bugs | Phase 1: Protocol Foundation | Test: launch game, kill game process, verify gdauto recovers cleanly within 5 seconds |
| Autoload requirement | Phase 1: Protocol Foundation (decision) / Phase 2: Implementation | `gdauto debug init` creates autoload; `gdauto debug tree` works without autoload; `gdauto debug inject-key` requires autoload and says so |
| CI test flakiness | Every phase | CI pass rate above 95%; E2E tests isolated in separate job; mock tests cover protocol logic |

## Sources

- [Godot remote_debugger_peer.cpp source](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger_peer.cpp) -- TCP buffer sizes, message framing, threading model
- [Godot scene_debugger.h source](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.h) -- Complete list of scene debugger message handlers
- [PlayGodot (Randroids-Dojo/PlayGodot)](https://github.com/Randroids-Dojo/PlayGodot) -- Python client reference implementation using debugger protocol with custom Godot fork
- [Godot Binary Serialization API docs](https://docs.godotengine.org/en/stable/tutorials/io/binary_serialization_api.html) -- Variant type IDs, encoding format, flag system
- [Godot issue #73557: Input.parse_input_event doesn't work in headless mode](https://github.com/godotengine/godot/issues/73557) -- Confirmed open, architectural limitation
- [Godot issue #90721: Variant encoding errors with typed arrays](https://github.com/godotengine/godot/issues/90721) -- Fixed in 4.3 but illustrates serialization fragility
- [Godot issue #94212: Variant decode errors in remote inspector](https://github.com/godotengine/godot/issues/94212) -- Unresolved; buffer corruption with dynamic arrays
- [Godot issue #78645: Remote scene tree unusably slow in large scenes](https://github.com/godotengine/godot/issues/78645) -- Open; full tree sent on every request
- [Godot issue #102525: Editor freezes with remote scene tree refresh](https://github.com/godotengine/godot/issues/102525) -- Fixed in 4.4.beta3
- [Godot issue #91359: Remote debugger only works once](https://github.com/godotengine/godot/issues/91359) -- Open; orphaned processes block port
- [Godot VSCode plugin PR #400: Debugger fixes for Godot 4.0](https://github.com/godotengine/godot-vscode-plugin/pull/400) -- ENCODE_FLAG_64 handling, protocol changes
- [Godot VSCode plugin: Scene Tree and Inspector architecture](https://deepwiki.com/godotengine/godot-vscode-plugin/4.4-scene-tree-and-inspector) -- Message format, property type limitations
- [Godot proposal #2608: Editor listen-only debug mode](https://github.com/godotengine/godot-proposals/issues/2608) -- Implemented; `--debug-server` flag, PR #69164
- [Godot issue #20020: Multiple debugger port conflicts](https://github.com/godotengine/godot/issues/20020) -- Port allocation problems
- [EngineDebugger API (Godot 4.5)](https://docs.godotengine.org/en/4.5/classes/class_enginedebugger.html) -- register_message_capture, send_message
- [Click issue #2033: Basic async support](https://github.com/pallets/click/issues/2033) -- Open since 2021; no built-in async
- [godot-setup GitHub Action (lihop/godot-setup)](https://github.com/lihop/godot-setup) -- Xvfb setup for CI
- [GdUnit4 CI pipeline guidance](https://medium.com/@kpicaza/ci-tested-gut-for-godot-4-fast-green-and-reliable-c56f16cde73d) -- Xvfb workaround for headless testing
- [pietrum/godot-binary-serialization](https://github.com/pietrum/godot-binary-serialization) -- JavaScript reference for Variant encoding (60-70% complete)

---
*Pitfalls research for: Adding live game debugger interaction to gdauto CLI*
*Researched: 2026-03-29*
