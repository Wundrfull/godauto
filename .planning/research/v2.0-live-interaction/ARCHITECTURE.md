# Architecture Patterns: v2.0 Live Game Interaction

**Domain:** Godot remote debugger protocol bridge
**Researched:** 2026-03-29

## Recommended Architecture

### System Overview

```
+------------------+          TCP (port 6007)          +------------------+
|   gdauto CLI     | <-------------------------------> |  Godot Game      |
|                  |    Binary Variant messages         |                  |
|  [Python]        |                                    |  [GDScript]      |
|                  |                                    |                  |
|  asyncio TCP     |    Game connects as client         |  RemoteDebugger  |
|  server listens  | <---- --remote-debug flag -------> |  PeerTCP client  |
|                  |                                    |                  |
|  VariantCodec    |    Length-prefixed frames           |  Built-in scene  |
|  encode/decode   | <-------------------------------> |  debugger capture |
|                  |                                    |                  |
|  DebugClient     |    "gdauto:" custom messages       |  GDScript autoload|
|  high-level API  | <-------------------------------> |  custom capture   |
+------------------+                                    +------------------+
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `debugger/variant.py` | Encode/decode Godot binary Variant format. Pure functions, no I/O. | protocol.py (provides bytes in/out) |
| `debugger/protocol.py` | TCP server lifecycle, message framing (length-prefix read/write), raw send/receive of Variant Arrays. | variant.py (serialization), client.py (message dispatch) |
| `debugger/client.py` | High-level API: connect_to_game(), request_scene_tree(), get_property(), set_property(), inject_input(). Request-response correlation with timeouts. | protocol.py (message transport), assertions.py (verification) |
| `debugger/assertions.py` | Verification layer: wait_for_property(), assert_node_exists(), assert_property_equals(). Polling-based with configurable intervals and timeouts. | client.py (property queries) |
| `debugger/inject.py` | Auto-inject GDScript autoload into project.godot. Remove it on cleanup. | Existing formats/project_godot.py (INI manipulation) |
| `debugger/autoload.gd` | GDScript: register "gdauto" capture, handle inject_input/get_info/call_method. Respond via EngineDebugger.send_message(). | Godot EngineDebugger API |
| `commands/debug.py` | Click command group: `gdauto debug connect`, `debug tree`, `debug get`, `debug set`, `debug input`, `debug assert`. Calls asyncio.run(). | client.py, assertions.py, existing output.py |
| `backend.py` (extended) | New method: launch_with_debugger(). Starts game process with --remote-debug flag. | Existing binary discovery + new subprocess management |

### Data Flow: Sending a Command

```
1. CLI: User runs `gdauto debug get --node /root/Player --property position`
2. commands/debug.py: Parse args, call asyncio.run(client.get_property(...))
3. client.py: Build message ["scene:inspect_objects", [object_id], false]
4. protocol.py: Encode Array via variant.py, prepend 4-byte length, write to socket
5. TCP wire: [length][encoded Variant Array] --> Godot game
6. Godot: SceneDebugger._msg_inspect_objects() processes, sends response
7. TCP wire: [length][encoded response] <-- game
8. protocol.py: Read 4-byte length, read payload, decode via variant.py
9. client.py: Parse response, extract property value, return to CLI
10. commands/debug.py: Format output via emit() (JSON or human-readable)
```

### Data Flow: Injecting Input

```
1. CLI: User runs `gdauto debug input --action ui_accept --pressed`
2. commands/debug.py: Parse args, call asyncio.run(client.inject_input(...))
3. client.py: Build message ["gdauto:inject_action", "ui_accept", true]
4. protocol.py: Encode and send over TCP
5. Godot autoload: Capture receives "inject_action" command
6. GDScript: Creates InputEventAction, calls Input.parse_input_event()
7. Godot autoload: Sends ["gdauto:inject_action_result", true] response
8. client.py: Receives confirmation, returns success
```

## Patterns to Follow

### Pattern 1: Layered Protocol Abstraction

**What:** Separate raw byte I/O (protocol.py) from Variant encoding (variant.py) from semantic commands (client.py).

**When:** Always. This mirrors the existing gdauto architecture where the parser layer is separate from the data model layer and the CLI command layer.

**Example:**
```python
# variant.py -- pure encoding, no I/O
def encode_variant(value: GodotVariant) -> bytes: ...
def decode_variant(data: bytes) -> tuple[GodotVariant, int]: ...

# protocol.py -- I/O framing, no business logic
class DebuggerProtocol:
    async def send_message(self, message: list[GodotVariant]) -> None:
        payload = encode_variant(message)  # variant.py
        header = struct.pack('<I', len(payload))
        self._writer.write(header + payload)
        await self._writer.drain()

    async def recv_message(self) -> list[GodotVariant]:
        header = await self._reader.readexactly(4)
        length = struct.unpack('<I', header)[0]
        payload = await self._reader.readexactly(length)
        result, _ = decode_variant(payload)
        return result

# client.py -- semantic commands
class DebugClient:
    async def get_scene_tree(self) -> SceneTree:
        await self._protocol.send_message(["scene:request_scene_tree"])
        response = await self._wait_for("scene:scene_tree", timeout=5.0)
        return parse_scene_tree(response)
```

### Pattern 2: Request-Response Correlation

**What:** The debugger protocol is asynchronous (game sends messages at any time, not just in response to commands). Use an event-based dispatch system to correlate requests with responses.

**When:** Any command that expects a response (scene tree request, property inspection, etc.).

**Example:**
```python
class DebugClient:
    def __init__(self, protocol: DebuggerProtocol) -> None:
        self._waiters: dict[str, asyncio.Future] = {}
        self._protocol = protocol

    async def _dispatch_loop(self) -> None:
        """Background task that routes incoming messages to waiters."""
        while self._connected:
            message = await self._protocol.recv_message()
            command = message[0]
            if command in self._waiters:
                self._waiters[command].set_result(message[1:])

    async def _wait_for(
        self, command: str, timeout: float = 5.0
    ) -> list[GodotVariant]:
        future = asyncio.get_event_loop().create_future()
        self._waiters[command] = future
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._waiters.pop(command, None)
```

### Pattern 3: Autoload Injection/Cleanup

**What:** Before launching the game, inject the gdauto autoload into project.godot. After the session ends (or on error), remove it.

**When:** Every debug session.

**Example:**
```python
# inject.py
def inject_autoload(project_path: Path) -> None:
    """Add gdauto autoload to project.godot [autoload] section."""
    # Copy autoload.gd to project's addons/gdauto/ directory
    # Add to [autoload] section: gdauto_bridge="*res://addons/gdauto/autoload.gd"

def remove_autoload(project_path: Path) -> None:
    """Remove gdauto autoload from project.godot."""
    # Remove from [autoload] section
    # Optionally remove the copied .gd file
```

### Pattern 4: Sync CLI over Async Protocol

**What:** Click commands are synchronous. Wrap async debugger operations with `asyncio.run()` at the CLI boundary.

**When:** Every CLI command in commands/debug.py.

**Example:**
```python
@debug.command()
@click.argument("node_path")
@click.pass_context
def tree(ctx: click.Context, node_path: str) -> None:
    """Dump the live scene tree."""
    result = asyncio.run(_get_tree(ctx, node_path))
    emit(result, _format_tree, ctx)

async def _get_tree(ctx: click.Context, node_path: str) -> dict:
    async with debug_session(ctx) as client:
        return await client.get_scene_tree()
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Blocking TCP in the Main Thread

**What:** Using synchronous `socket.recv()` in the main thread while also needing to monitor the game process.

**Why bad:** Blocks indefinitely if the game crashes or disconnects. Cannot handle timeouts gracefully. Cannot process unsolicited game messages (errors, output) while waiting for a specific response.

**Instead:** Use asyncio with `readexactly()` and `wait_for()` for proper timeout handling and concurrent I/O.

### Anti-Pattern 2: OS-Level Input Injection

**What:** Using PyAutoGUI, pynput, or xdotool to simulate keyboard/mouse at the OS level.

**Why bad:** Requires the game window to be focused, breaks in headless/CI environments, fragile window coordinates, platform-specific code.

**Instead:** Inject input inside Godot via `Input.parse_input_event()` through the debugger protocol. Works headless, platform-independent, pixel-perfect.

### Anti-Pattern 3: Polling for State Changes

**What:** Continuously requesting the scene tree or property values in a tight loop to detect changes.

**Why bad:** Wastes bandwidth, high latency, misses transient states.

**Instead:** Use the built-in `scene:suspend_changed` to pause the game at specific points, inspect state, then resume. For assertions, use a polling interval (e.g., 100ms) with a timeout, not a tight loop.

### Anti-Pattern 4: Assuming Message Order

**What:** Assuming the next message received is always the response to the last command sent.

**Why bad:** The game sends unsolicited messages: `output` (print statements), `error` (runtime errors), `debug_enter` (breakpoint hits). These can arrive between your request and its response.

**Instead:** Use command-name-based dispatch (Pattern 2 above). Route each incoming message to the correct waiter based on its command prefix.

### Anti-Pattern 5: Hardcoding Port 6007

**What:** Always using port 6007 without making it configurable.

**Why bad:** If the Godot editor is running, it is already listening on 6007. Two listeners on the same port cause "address already in use" errors.

**Instead:** Make the port configurable with a default, and implement port auto-selection (find a free port) as a fallback.

## Scalability Considerations

| Concern | Single test | Test suite (10+ tests) | CI pipeline |
|---------|-------------|------------------------|-------------|
| Connection management | One game launch, one TCP session | Launch/connect/disconnect per test, or keep game running across tests | Must handle clean teardown even on test failure |
| Port allocation | Fixed port fine | Need port auto-selection to avoid conflicts between parallel test runs | Unique ports per CI job, or sequential execution |
| Game startup time | 2-5 seconds acceptable | Dominates test suite time if restarting per test; prefer keeping game running | Pre-launch game in setup, run all tests, teardown |
| Message throughput | Trivial | Hundreds of messages; no concern at <1K messages | Same; protocol handles 8 MiB per message |
| Timeout handling | 5-second default | Configurable per-command; flaky on slow CI | Increase timeouts for CI, add retry logic |

## Sources

- [Godot remote_debugger_peer.cpp](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger_peer.cpp) -- Packet format, threading model
- [Godot scene_debugger.h](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.h) -- Message handler signatures
- [godot-vscode-plugin server_controller.ts](https://github.com/godotengine/godot-vscode-plugin/blob/master/src/debugger/godot4/server_controller.ts) -- TCP server pattern, buffer splitting, message dispatch
- [PlayGodot](https://github.com/Randroids-Dojo/PlayGodot) -- Architecture reference for external Python game automation
- [Python asyncio docs](https://docs.python.org/3/library/asyncio.html) -- TCP server, StreamReader/StreamWriter patterns
