# Domain Pitfalls: v2.0 Live Game Interaction via Debugger Bridge

**Domain:** Godot remote debugger protocol client, TCP session management, binary protocol encoding, game automation
**Researched:** 2026-03-29
**Scope:** Pitfalls specific to implementing a Godot debugger bridge in Python, integrating async TCP into a synchronous CLI, and automating game interaction
**Confidence:** MEDIUM (protocol details verified from source, but implementation pitfalls are based on analysis and reference implementations, not firsthand experience)

---

## Critical Pitfalls

Mistakes that cause complete feature failure or data corruption in the target project.

---

### Pitfall 1: gdauto Must Be the TCP Server, Not the Client

**What goes wrong:**
The natural assumption is that gdauto (the tool) connects TO the game. This is backwards. In Godot's architecture, the editor runs a TCP server on port 6007, and the game connects to it as a client via `--remote-debug tcp://host:port`. If you implement gdauto as a TCP client, nothing connects and the feature is dead on arrival.

**Why it happens:**
Most protocol client implementations (HTTP, database, etc.) are clients. The Godot debugger model is unusual: the tool is the server and the game is the client. This is because in the editor workflow, the editor starts first (always listening), and games come and go.

**Consequences:**
- Complete failure: no connection, no debugging, no interaction
- Wasted implementation time if discovered late

**Prevention:**
- Implement `asyncio.start_server()` in the session module, NOT `asyncio.open_connection()`
- Start the TCP server BEFORE launching the game process
- Accept the incoming connection from the game
- The `--remote-debug tcp://127.0.0.1:<port>` flag tells the game where to connect TO

**Detection:**
- Game launches but no connection is established
- TCP connection refused errors in Godot's console output

**Verified from:** `remote_debugger_peer.cpp` shows `stream->connect_to_host(ip, debug_port)`, confirming the game initiates the connection.

---

### Pitfall 2: Variant Encoding Must Be Exact, Byte-for-Byte

**What goes wrong:**
The Godot Variant binary format has specific padding, alignment, and encoding rules. A single byte off causes the entire message to be unreadable. Godot's decoder will reject malformed packets silently (the decoded Variant must be of type Array; anything else is discarded). There's no error message; the game just ignores the command.

**Why it happens:**
Binary protocol bugs are invisible. Unlike text protocols where you can inspect the wire, binary encoding errors manifest as "nothing happens" or corrupted data.

Specific encoding traps:
1. **String padding:** String data must be padded to 4-byte boundaries. A 5-byte string requires 3 padding bytes. The padding bytes should be zero.
2. **Type header flags:** The `ENCODE_FLAG_64` flag (bit 16) changes the encoding size for int and float. Sending a 32-bit int when the flag says 64-bit corrupts the stream.
3. **Array encoding:** The Array type header is followed by a 4-byte element count, then each element is a full Variant (with its own type header). Off-by-one in element count corrupts everything.
4. **Little-endian:** All values are little-endian. Using `struct.pack('>I', ...)` instead of `struct.pack('<I', ...)` produces valid-looking but wrong bytes.
5. **NodePath encoding:** NodePath has a complex multi-field encoding (name count, subname count, flags, then concatenated name strings). Getting this wrong corrupts scene tree queries.

**Consequences:**
- Commands silently ignored (no error from Godot, just no response)
- Partial messages corrupt the TCP stream, causing all subsequent messages to fail
- Debugging binary protocol issues is extremely time-consuming

**Prevention:**
- Build a comprehensive test suite with golden byte sequences for EVERY Variant type used
- Use Godot itself to generate reference encoded bytes: write a GDScript that uses `var_to_bytes()` and prints hex output, then compare against Python encoder output
- Test round-trip: encode in Python -> decode in Python -> verify identical to input
- Add hex dump logging for all wire traffic during development
- Keep the codec stateless: `encode(value) -> bytes` and `decode(data, offset) -> (value, consumed)` with no mutable state
- Reference the godot-vscode-plugin TypeScript VariantDecoder for encoding edge cases

**Detection:**
- Commands produce no response (silent ignore)
- Responses decode as garbage
- "Malformed packet" or "Invalid variant type" in Godot debug output (if Godot is run with --verbose)

---

### Pitfall 3: Bridge Script Cleanup Failure Corrupts User's Project

**What goes wrong:**
The GDScript bridge autoload (`gdauto_bridge.gd`) is injected into the target project before launching the game and must be removed after the session ends. If gdauto crashes, the process is killed, or the user interrupts with Ctrl+C, the bridge script and its autoload entry remain in `project.godot`. The next time the user opens their project in the Godot editor, they see an unexpected autoload singleton. If they delete it manually and forget to clean up the .gd file, an orphan script remains.

**Why it happens:**
Cleanup logic runs in `__aexit__` or `finally` blocks, which don't execute on SIGKILL, power loss, or unhandled exceptions that bypass the normal teardown path.

**Consequences:**
- Orphan files in the user's project
- Extra autoload entry in project.godot
- Confusion and loss of trust in the tool
- Potential merge conflicts if project.godot is under version control

**Prevention:**
1. **Startup cleanup check:** Every `debug` command checks for stale bridge artifacts before doing anything. If `gdauto_bridge.gd` exists and no session is active, remove it.
2. **Signal handlers:** Register `signal.signal(signal.SIGINT, cleanup)` and `signal.signal(signal.SIGTERM, cleanup)` to catch interrupts.
3. **atexit handler:** Register `atexit.register(cleanup)` for normal exit paths.
4. **Marker file:** Write a `.gdauto-session.json` file that includes the bridge script path. On startup, check for stale session files and clean up.
5. **Atomic project.godot modification:** Read, modify, write project.godot atomically. Keep a backup before modification and restore on failure.
6. **Bridge script location:** Place the bridge script in a `.gdauto/` subdirectory within the project (easily identifiable as tool-generated), not mixed with user scripts.

**Detection:**
- `project.godot` contains `[autoload]` entry for `GdautoBridge`
- `.gdauto/gdauto_bridge.gd` file exists when no session is active
- `gdauto debug launch` warns about stale artifacts

---

### Pitfall 4: Unsolicited Messages Flood the TCP Buffer

**What goes wrong:**
The game sends messages continuously, not just in response to commands. Performance data (`performance:profile_frame`) arrives every frame (~60 times/second). Print output arrives whenever `print()` is called. Errors arrive on runtime exceptions. If the receive loop doesn't drain these messages, the TCP receive buffer fills (8 MiB), the game's send blocks, and the game freezes.

**Why it happens:**
The debugger protocol is not request-response; it's bidirectional with unsolicited messages. The editor handles this by continuously polling in its main loop. A CLI tool that only reads when expecting a response will miss all unsolicited traffic.

**Consequences:**
- Game freezes (blocked on TCP send)
- Commands time out waiting for responses that are buried behind queued messages
- Memory grows unbounded if messages are buffered without limits

**Prevention:**
- Start a background `_recv_loop` task immediately after connection
- The recv loop must run continuously, dispatching messages to appropriate handlers:
  - Expected responses -> resolve pending futures
  - Performance data -> discard or log (configurable)
  - Output messages -> buffer for user display (with size limit)
  - Error messages -> buffer for error reporting
- Never wait for a response by reading directly from the socket; always wait on a future that the recv loop resolves
- Set buffer size limits on output/error buffers (e.g., keep last 1000 messages)

**Detection:**
- Game freezes after a few seconds of connection
- Commands that worked individually fail when sent in sequence
- Debugging shows large amounts of unread data in the TCP buffer

---

## Moderate Pitfalls

Mistakes that cause incorrect behavior, poor UX, or significant debugging difficulty.

---

### Pitfall 5: Message Response Correlation Without Request IDs

**What goes wrong:**
The Godot debugger protocol has no request IDs. If you send `scene:request_scene_tree` and `scene:inspect_object` in quick succession, there's no way to match the response `scene_tree` to the first request and the `inspect_object` response to the second. If the scene tree response arrives after the inspect_object response (due to processing time), your correlation logic breaks.

**Why it happens:**
The protocol was designed for the editor, which sends one request at a time and waits for the response before sending the next.

**Prevention:**
- Serialize all commands: send one command, wait for its response, then send the next
- Use a simple state machine: `IDLE -> AWAITING_RESPONSE(type) -> IDLE`
- If a response arrives for an unexpected type, log it and continue waiting
- Set reasonable timeouts (5-10 seconds) for each response
- Do NOT pipeline commands (send multiple without waiting)

**Detection:**
- Responses appear to be for the wrong command
- Assertion failures when parsing response data that doesn't match expected format

---

### Pitfall 6: Game Boot Time Creates Connection Race Condition

**What goes wrong:**
After launching the game process, it takes 2-5 seconds to boot, initialize the scene tree, and connect to the debugger. If gdauto starts sending commands immediately after accepting the TCP connection, the game may not have its scene tree ready yet. Early `request_scene_tree` commands return empty or partial data.

**Why it happens:**
The game connects to the debugger early in its boot sequence, before the main scene is fully loaded and the first frame has been rendered. PR #103297 in Godot specifically addresses "scene debugger messages arriving before scene tree exists."

**Consequences:**
- Empty or partial scene tree returned
- Object IDs not yet valid
- Intermittent test failures (passes when game boots fast, fails when slow)

**Prevention:**
- After accepting the connection, wait for the game to signal readiness
- Option A: Wait for the first `scene_tree` unsolicited message (game sends one after the scene tree is initialized, if the editor requested it)
- Option B: Poll `request_scene_tree` with retries until a non-empty tree is returned
- Option C: Wait for the first `performance:profile_frame` message (indicates the game's main loop is running)
- Option D: Send `scene:request_scene_tree` with exponential backoff (100ms, 200ms, 400ms, ...) until a valid response arrives
- Set a maximum wait time (e.g., 30 seconds) and fail with a clear error if the game doesn't respond

**Detection:**
- Empty scene tree on first query after connection
- "Object not found" errors when trying to inspect nodes
- Tests pass on fast machines, fail on slow CI

---

### Pitfall 7: Object IDs Are Ephemeral and Non-Persistent

**What goes wrong:**
Godot Object IDs (used with `inspect_object`, `set_object_property`, etc.) are runtime-only. They change every time the game is launched. They cannot be stored across sessions or predicted from the scene file. An object ID obtained from `request_scene_tree` in one session is meaningless in the next session.

**Why it happens:**
Object IDs are internal memory addresses or instance counters assigned at runtime. They are not serialized in .tscn files or otherwise stable.

**Consequences:**
- Cached object IDs from a previous query become invalid after scene changes
- Test scripts cannot use hardcoded object IDs
- Must re-query the scene tree and resolve paths to IDs every time

**Prevention:**
- Use NodePath (e.g., `/root/Main/ScoreLabel`) as the user-facing identifier, not Object ID
- Implement a `resolve_node_path(path: str) -> int` method that queries the scene tree and returns the current object ID for a given path
- Cache the path-to-ID mapping per session but invalidate it on scene changes
- Never expose raw Object IDs in the CLI interface; always accept NodePath strings

**Detection:**
- "Object not found" errors when using IDs from a previous query
- Inconsistent behavior between test runs

---

### Pitfall 8: Windows-Specific TCP and Process Issues

**What goes wrong:**
Several things work differently on Windows:
1. `signal.SIGTERM` and `signal.SIGINT` handling differs from Unix
2. `asyncio.start_server()` defaults differ (e.g., address reuse flags)
3. `subprocess.Popen.terminate()` on Windows sends `SIGTERM` (actually `TerminateProcess`), which can't be caught by the game
4. Port binding failures on Windows may require `SO_REUSEADDR` or waiting for TIME_WAIT
5. File paths in project.godot use forward slashes (`res://`) but subprocess paths use backslashes

**Why it happens:**
The developer's primary platform is Windows (per the dev environment). Python's cross-platform abstractions work for most cases but have edge cases in async I/O and process management.

**Consequences:**
- Bridge cleanup fails on Windows due to signal handling differences
- Port 6007 remains bound after a crash, preventing the next session
- Game process doesn't terminate cleanly

**Prevention:**
- Test on Windows from day one (not "port to Windows later")
- Use `127.0.0.1` instead of `localhost` (avoids IPv6 resolution issues on Windows)
- Set `SO_REUSEADDR` on the server socket to allow quick port reuse
- Use `subprocess.Popen.kill()` as a fallback after `terminate()` with a timeout
- Use `pathlib.Path` for all path operations and `.as_posix()` when writing to project.godot
- Add a port-availability check before starting the server

**Detection:**
- "Address already in use" errors on Windows
- Game process remains running after gdauto exits
- Cleanup fails silently on Ctrl+C

---

### Pitfall 9: Input Injection Timing Is Non-Deterministic

**What goes wrong:**
Input events injected via the bridge script go through Godot's input pipeline, which processes events once per frame. If you inject a mouse click and immediately check the resulting state, the game may not have processed the click yet (it arrives in the next frame's input polling). Tests that inject input and immediately assert state changes will be flaky.

**Why it happens:**
`Input.parse_input_event()` queues the event for the next `_input()` / `_unhandled_input()` dispatch cycle. The event is not processed synchronously; it requires at least one frame tick.

**Consequences:**
- Flaky tests: sometimes the assertion runs before the input is processed
- Race conditions between input injection and state verification
- Need to "wait a frame" after every input injection

**Prevention:**
- After injecting input, always wait at least one frame before asserting state
- Implement a `wait_frames(n)` command that pauses execution for N game frames
- For deterministic testing: pause the game, inject input, step one frame, then assert
- The pause/step/assert pattern eliminates all timing uncertainty:
  ```
  pause() -> inject_input(click_at(100, 200)) -> step_frame() -> assert(score == 1)
  ```
- Document that `pause + inject + step + assert` is the recommended testing pattern

**Detection:**
- Tests pass 90% of the time, fail 10%
- Adding sleep() makes tests pass (but is the wrong fix)
- Tests pass when game FPS is high, fail when low

---

## Minor Pitfalls

Mistakes that cause inconvenience or suboptimal UX but do not affect correctness.

---

### Pitfall 10: Port 6007 Conflicts with Godot Editor

**What goes wrong:**
If the Godot editor is running with "Keep Debug Server Open" enabled, it's already listening on port 6007. gdauto trying to bind the same port fails with "Address already in use."

**Prevention:**
- Default to port 6007 but allow `--port` override
- Check if the port is available before binding; if not, suggest an alternative port
- Consider auto-incrementing ports (6007, 6008, 6009...) like Godot's own auto-increment PR #53241
- Document that the Godot editor must not be running on the same port

**Detection:**
- "Address already in use" error on launch
- User has Godot editor open

---

### Pitfall 11: asyncio.run() Is Not Reentrant

**What goes wrong:**
If a Click command handler calls `asyncio.run()`, it creates a new event loop. If for some reason this is called from an already-running event loop (e.g., during testing with pytest-asyncio, or if a future enhancement wraps gdauto in an async context), it raises `RuntimeError: cannot be called when another event loop is running`.

**Prevention:**
- Use a helper function that checks for an existing event loop:
  ```python
  def run_async(coro):
      try:
          loop = asyncio.get_running_loop()
      except RuntimeError:
          return asyncio.run(coro)
      else:
          # Already in an async context, create a new thread
          import concurrent.futures
          with concurrent.futures.ThreadPoolExecutor() as pool:
              return pool.submit(asyncio.run, coro).result()
  ```
- For tests, use pytest-asyncio and call the async functions directly, not through the run_async wrapper
- Document that `gdauto debug` commands cannot be called from within an existing asyncio event loop

**Detection:**
- RuntimeError in test suites using pytest-asyncio
- Error when embedding gdauto in async applications

---

### Pitfall 12: Scene Tree Path Format Differences Between Godot Versions

**What goes wrong:**
The exact format of NodePath strings in scene tree responses may differ between Godot 4.5 and 4.6. Property paths, subpaths, and relative vs absolute paths may be serialized differently. Hardcoded path patterns in tests or assertions may break on version upgrades.

**Prevention:**
- Always use absolute paths starting from `/root/`
- Normalize path separators and trailing slashes before comparison
- Test against both Godot 4.5 and 4.6 in E2E tests
- Use path-based matching (startswith, endswith) rather than exact equality when possible

**Detection:**
- Assertion failures on specific Godot versions
- NodePath resolution returns "not found" for paths that visually appear correct

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Variant codec | Encoding byte alignment off by one (Pitfall 2) | Golden byte tests against Godot's own var_to_bytes() output |
| Variant codec | String padding missing or wrong (Pitfall 2) | Test strings of length 1, 4, 5, 8 (boundary cases) |
| TCP server | Implemented as client instead of server (Pitfall 1) | Verify from source before writing any code |
| TCP server | Port conflict with Godot editor (Pitfall 10) | --port flag with auto-increment fallback |
| Session management | Bridge cleanup on crash (Pitfall 3) | Signal handlers + startup cleanup check |
| Session management | Unsolicited message flood (Pitfall 4) | Background recv loop from connection start |
| Scene inspection | Game not ready after connection (Pitfall 6) | Poll with backoff for non-empty scene tree |
| Scene inspection | Object IDs change between sessions (Pitfall 7) | NodePath-based API, never expose raw IDs |
| Input injection | Timing non-determinism (Pitfall 9) | Pause + inject + step + assert pattern |
| Input injection | Bridge script cleanup failure (Pitfall 3) | Multiple cleanup mechanisms |
| CLI integration | asyncio.run() not reentrant (Pitfall 11) | Helper function with fallback |
| Testing | Windows-specific failures (Pitfall 8) | Test on Windows from day one |

---

## Sources

- [Godot `remote_debugger_peer.cpp`](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger_peer.cpp) - TCP client behavior, buffer sizes
- [Godot `scene_debugger.cpp`](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.cpp) - Scene debugger message handlers
- [Godot Binary Serialization API](https://github.com/godotengine/godot-docs/blob/master/tutorials/io/binary_serialization_api.rst) - Variant encoding spec
- [PR #103297: Scene debugger message timing](https://github.com/godotengine/godot/pull/103297) - Messages before scene tree exists
- [PR #53241: Auto-increment debugger port](https://github.com/godotengine/godot/pull/53241) - Port conflict handling
- [PlayGodot](https://github.com/Randroids-Dojo/PlayGodot) - Reference for what works (and requires a fork for input)
- [godot-vscode-plugin](https://github.com/godotengine/godot-vscode-plugin) - TypeScript implementation reference
- [Python asyncio docs](https://docs.python.org/3/library/asyncio.html) - Event loop limitations
- [Godot InputEvent docs](https://docs.godotengine.org/en/stable/tutorials/inputs/inputevent.html) - parse_input_event() behavior
