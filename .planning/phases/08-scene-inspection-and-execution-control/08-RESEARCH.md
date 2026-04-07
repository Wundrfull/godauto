# Phase 8: Scene Inspection and Execution Control - Research

**Researched:** 2026-04-06
**Domain:** Godot remote debugger scene inspection, property access, output capture, execution control
**Confidence:** HIGH

## Summary

Phase 8 builds seven new CLI subcommands on top of Phase 7's TCP session and Variant codec: `debug tree`, `debug get`, `debug output`, `debug pause`, `debug resume`, `debug step`, and `debug speed`. All the hard protocol and codec work is done; this phase is primarily about sending the right debugger commands, parsing their responses into structured data, and wiring up CLI output.

The Godot debugger protocol routes scene-related commands through a "scene:" capture prefix. Commands sent from gdauto use the form `scene:request_scene_tree`, `scene:inspect_objects`, `scene:suspend_changed`, `scene:next_frame`, and `scene:speed_changed`. The game responds with `scene:scene_tree` and `scene:inspect_objects` messages that the existing recv_loop dispatches to pending futures. The scene tree response is a flat depth-first array of 6 fields per node (child_count, name, type_name, id, scene_file_path, view_flags) that must be parsed recursively. Property inspection returns (id, class_name, property_array) where each property has 6 fields (name, type, hint, hint_string, usage, value).

The existing DebugSession already has output_buffer and error_buffer populated by the recv_loop. The `debug output` command reads these buffers. Execution control commands (pause/resume/step/speed) are fire-and-forget sends with state confirmation via `debug_enter`/`debug_exit` messages. Session persistence via `.gdauto/session.json` enables commands to auto-connect and reuse sessions.

**Primary recommendation:** Build a `debugger/inspector.py` module with async functions for scene tree parsing, property resolution, and execution control; wire these into thin CLI commands in `commands/debug.py`. Use the existing DebugSession.send_command() for all protocol interactions. Session persistence is the one new infrastructure piece.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Inspection commands (tree, get, output) auto-connect: launch game and connect if no session exists. Each command is independently runnable without requiring a prior `debug connect`.
- D-02: Sessions persist after command completion with an inactivity timeout. Follow-up commands reuse the existing session without relaunching the game.
- D-03: Session file lives in the project directory at `.gdauto/session.json`. Visible to agents, easy to discover.
- D-04: `.gdauto/` is auto-added to `.gitignore` when a session starts, preventing accidental commits of session state.
- D-05: `debug tree` returns a nested JSON hierarchy mirroring Godot's scene tree structure: `{"name": "Main", "type": "Node2D", "path": "/root/Main", "children": [...]}`.
- D-06: Each node includes: type (Node2D, Label, etc.), class_name (if custom script), instance_id (Godot object ID), script_path (attached GDScript, if any), groups (list of group names).
- D-07: `debug tree` supports `--depth N` flag to limit tree traversal depth. Default: unlimited.
- D-08: `debug output` defaults to snapshot mode (return buffered output, then exit). `--follow` flag streams continuously (like `tail -f`).
- D-09: Claude's Discretion: whether to separate print() from errors (--errors flag) or combine them with a type field in --json output.
- D-10: Claude's Discretion: whether `debug step` auto-pauses the running game first or requires the game to already be paused.
- D-11: Claude's Discretion: speed command interface (multiplier flag vs positional argument).
- D-12: All execution control commands (pause, resume, step, speed) return current game state in their --json output: `{"paused": true, "speed": 1.0, "frame": 1234}`.
- D-13: `--project` flag on subcommands, not global (carried from Phase 7).
- D-14: Short verb names: tree, get, output, pause, resume, step, speed (carried from Phase 7).
- D-15: Default port 6007 matching Godot editor (carried from Phase 7).

### Claude's Discretion
- D-09: Output/error separation approach
- D-10: Step auto-pause behavior
- D-11: Speed command interface

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCENE-01 | Retrieve live scene tree as structured JSON showing all nodes, types, and paths | Scene tree protocol verified: `scene:request_scene_tree` command, response is flat depth-first array with 6 fields per node (child_count, name, type_name, id, scene_file_path, view_flags). Recursive parsing into nested JSON hierarchy documented. |
| SCENE-02 | Read any node property by NodePath (e.g., /root/Main/ScoreLabel.text) | Property inspection protocol verified: `scene:inspect_objects` with object_id, response contains property arrays with 6 fields each (name, type, hint, hint_string, usage, value). Requires NodePath-to-object-ID resolution via scene tree. |
| SCENE-03 | Capture game print() output and runtime errors through debugger connection | Already implemented in Phase 7: DebugSession._recv_loop dispatches "output" and "error" messages to output_buffer and error_buffer. Phase 8 wraps these in a CLI command. |
| EXEC-01 | Pause and resume the running game | Protocol verified: `scene:suspend_changed` with boolean parameter. Game responds with `debug_enter` (paused) or `debug_exit` (resumed). |
| EXEC-02 | Step one frame at a time while paused | Protocol verified: `scene:next_frame` with no parameters. Advances one frame while suspended. |
| EXEC-03 | Set game speed (e.g., 10x for fast-forwarding idle timers) | Protocol verified: `scene:speed_changed` with float parameter (time scale multiplier). Sets Engine.user_time_scale. |
</phase_requirements>

## Standard Stack

### Core (no new dependencies)

Phase 8 adds zero new dependencies. Everything builds on Phase 7's existing stack:

| Module | Purpose | Already Exists |
|--------|---------|----------------|
| `debugger/session.py` | TCP session, send_command, recv_loop, output/error buffers | Yes (Phase 7) |
| `debugger/protocol.py` | Message framing, encode/decode | Yes (Phase 7) |
| `debugger/variant.py` | Variant binary codec for 24+ Godot types | Yes (Phase 7) |
| `debugger/connect.py` | async_connect workflow with readiness polling | Yes (Phase 7) |
| `debugger/errors.py` | DebuggerError hierarchy | Yes (Phase 7) |
| `debugger/models.py` | GodotStringName, GodotNodePath | Yes (Phase 7) |
| `commands/debug.py` | Click debug group with connect subcommand | Yes (Phase 7) |
| `output.py` | emit/emit_error with GlobalConfig | Yes (v1.0) |
| `backend.py` | GodotBackend with launch_game | Yes (Phase 7) |

### New Modules (Phase 8)

| Module | Purpose |
|--------|---------|
| `debugger/inspector.py` | Async functions: get_scene_tree, get_property, parse scene tree response, resolve NodePath to object ID |
| `debugger/execution.py` | Async functions: pause, resume, step_frame, set_speed; state tracking |
| `debugger/session_file.py` | Session persistence: write/read/cleanup `.gdauto/session.json`; .gitignore management |
| New dataclasses in `debugger/models.py` | SceneNode, NodeProperty, GameState, SessionInfo |

## Architecture Patterns

### New Module Structure

```
src/gdauto/
  debugger/
    inspector.py          # NEW: scene tree + property inspection
    execution.py          # NEW: pause/resume/step/speed
    session_file.py       # NEW: .gdauto/session.json persistence
    models.py             # EXTEND: SceneNode, NodeProperty, GameState, SessionInfo
    session.py            # EXTEND: drain_output/drain_errors convenience methods
    connect.py            # MINOR: support session file creation after connect
    __init__.py           # EXTEND: export new public API
  commands/
    debug.py              # EXTEND: add 7 new subcommands
```

### Pattern 1: Scene Tree Response Parsing

**What:** The `scene:scene_tree` response is a flat depth-first array. Each node is 6 consecutive values: `[child_count, name, type_name, id, scene_file_path, view_flags]`. Parsing requires recursive descent with a shared offset counter.

**When to use:** Every `debug tree` invocation.

**Wire format (verified from godot-vscode-plugin TypeScript helpers.ts):**

```
Response data array layout (flat, depth-first):
  [child_count_0, name_0, type_0, id_0, scene_path_0, view_flags_0,
   child_count_1, name_1, type_1, id_1, scene_path_1, view_flags_1,
   ...]
```

**Python implementation pattern:**

```python
# Source: godot-vscode-plugin/src/debugger/godot4/helpers.ts (parse_next_scene_node)
@dataclass
class SceneNode:
    name: str
    type_name: str
    instance_id: int
    scene_file_path: str
    view_flags: int
    path: str  # computed: absolute NodePath
    children: list[SceneNode]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": self.type_name,
            "path": self.path,
            "instance_id": self.instance_id,
            "scene_file_path": self.scene_file_path,
            "children": [c.to_dict() for c in self.children],
        }


def parse_scene_tree(data: list, offset: int = 0, parent_path: str = "") -> tuple[SceneNode, int]:
    """Parse a single node and its children from the flat response array."""
    child_count = data[offset]
    name = data[offset + 1]
    type_name = data[offset + 2]
    instance_id = data[offset + 3]
    scene_file_path = data[offset + 4]
    view_flags = data[offset + 5]
    offset += 6

    path = f"{parent_path}/{name}" if parent_path else f"/{name}"

    children = []
    for _ in range(child_count):
        child, offset = parse_scene_tree(data, offset, path)
        children.append(child)

    node = SceneNode(
        name=name,
        type_name=type_name,
        instance_id=instance_id,
        scene_file_path=scene_file_path,
        view_flags=view_flags,
        path=path,
        children=children,
    )
    return node, offset
```

**Confidence:** HIGH (verified from Godot VS Code plugin TypeScript implementation, cross-referenced with Godot C++ scene_debugger.h RemoteNode struct)

### Pattern 2: Property Inspection via Object ID

**What:** `scene:inspect_objects` takes `[object_id_array, update_bool]`. Response is `[id, class_name, [[name, type, hint, hint_string, usage, value], ...]]`. Properties with `usage == 128` are category separators, not actual properties.

**When to use:** Every `debug get` invocation.

**Flow:**
1. Query scene tree to get the full node list
2. Find node matching the requested NodePath
3. Use its instance_id to call `scene:inspect_objects`
4. Parse response, find matching property name
5. Return the property value

```python
# Source: godot-vscode-plugin/src/debugger/godot4/server_controller.ts
@dataclass
class NodeProperty:
    name: str
    type: int
    hint: int
    hint_string: str
    usage: int
    value: object

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "value": self.value, "type": self.type}


def parse_object_properties(data: list) -> tuple[int, str, list[NodeProperty]]:
    """Parse inspect_objects response into (id, class_name, properties)."""
    obj_id = data[0]
    class_name = data[1]
    raw_props = data[2]
    props = []
    for i in range(0, len(raw_props), 6):
        name = raw_props[i]
        prop_type = raw_props[i + 1]
        hint = raw_props[i + 2]
        hint_string = raw_props[i + 3]
        usage = raw_props[i + 4]
        value = raw_props[i + 5]
        if usage == 128:  # category separator, skip
            continue
        props.append(NodeProperty(name, prop_type, hint, hint_string, usage, value))
    return obj_id, class_name, props
```

**Confidence:** HIGH (verified from godot-vscode-plugin server_controller.ts and Godot scene_debugger_object.cpp)

### Pattern 3: Execution Control Commands

**What:** Three fire-and-forget commands control game execution. The game sends `debug_enter`/`debug_exit` messages to confirm state changes.

**Commands (verified from Godot scene_debugger.cpp):**

| gdauto Command | Protocol Message | Parameters | Game Response |
|----------------|------------------|------------|---------------|
| `debug pause` | `scene:suspend_changed` | `[true]` | `debug_enter` |
| `debug resume` | `scene:suspend_changed` | `[false]` | `debug_exit` |
| `debug step` | `scene:next_frame` | `[]` | Frame advances, stays paused |
| `debug speed` | `scene:speed_changed` | `[float_multiplier]` | None (immediate effect) |

**State tracking pattern:**

```python
@dataclass
class GameState:
    paused: bool = False
    speed: float = 1.0
    frame: int = 0

    def to_dict(self) -> dict[str, object]:
        return {"paused": self.paused, "speed": self.speed, "frame": self.frame}
```

Track state by listening for `debug_enter` and `debug_exit` messages in the recv_loop. These are already discarded as "unknown unsolicited messages" in the current session.py; Phase 8 must add handlers for them.

**Confidence:** HIGH (command names and parameters verified from Godot source scene_debugger.cpp)

### Pattern 4: Session Persistence

**What:** `.gdauto/session.json` stores connection metadata so subsequent commands reuse the session without relaunching the game.

**Session file format:**

```json
{
    "host": "127.0.0.1",
    "port": 6007,
    "game_pid": 12345,
    "thread_id": 1,
    "project_path": "/path/to/project",
    "created_at": "2026-04-06T12:00:00Z",
    "timeout": 300
}
```

**Auto-connect flow for every inspection/control command:**

```python
async def ensure_session(project_path: Path, port: int, ...) -> tuple[DebugSession, subprocess.Popen | None]:
    """Load existing session or create new one."""
    session_info = read_session_file(project_path)
    if session_info and _is_process_alive(session_info.game_pid):
        # Reconnect to existing game
        session = DebugSession(port=session_info.port)
        await session.start()
        await session.wait_for_connection(timeout=5.0)
        return session, None
    # No existing session; do full connect workflow
    result = await async_connect(project_path, port, scene=None, backend=backend)
    write_session_file(project_path, result)
    return session, process
```

**Important:** gdauto is the TCP server, not client. "Reconnecting" means starting a new server and having the game reconnect. However, the game only connects once at launch. This means session persistence actually means: check if the game process is still alive, and if so, the session is still active. Between CLI invocations, the TCP connection closes. The background daemon approach (ARCHITECTURE.md Option D) is needed for true session reuse.

**Simpler MVP approach:** Each command does the full connect workflow (start server, launch game, wait for connection, execute command, close). The session file tracks the game PID so we can check if a game is already running and avoid launching a duplicate. If a game is already running, we still need to establish a new TCP connection for each command invocation because the TCP server dies when the CLI process exits.

**Revised session persistence strategy:**
1. On first command: launch game + connect. Write session file with game PID and port.
2. On subsequent commands: check session file. If game PID is alive, start TCP server on same port, but the game has already established its connection and won't reconnect to a new server.
3. **Problem:** The game connects once at boot. It does NOT reconnect if the server disappears and reappears.

**Resolution:** The session persistence model from D-01/D-02 requires either:
- (a) A background daemon that keeps the TCP server alive across CLI invocations, OR
- (b) Each command is self-contained: launch game, connect, execute, tear down (no reuse)

Option (a) adds significant complexity. Option (b) contradicts D-02 (sessions persist).

**Recommended approach:** Implement a lightweight background server process. The first command that needs a session spawns a background process (subprocess.Popen with the TCP server loop). This background process:
- Accepts the game connection and keeps it alive
- Listens on a second localhost port for CLI commands (inter-process communication)
- Forwards commands to the game and returns responses
- Times out after inactivity (D-02)
- Writes `.gdauto/session.json` with both game port and IPC port

This is the daemon approach from ARCHITECTURE.md Option D, but scoped tightly: the daemon is a thin relay, not a full CLI. CLI commands connect to the daemon via a simple JSON-over-TCP protocol for command forwarding.

**Alternative simpler approach:** Keep the game running but use Godot's reconnection capability. Check if `--remote-debug` causes the game to retry connections periodically. If so, each CLI invocation just starts the server and waits for the game to reconnect.

**Confidence for session persistence design:** MEDIUM -- the session reuse model requires careful design. The protocol constraint (game connects once) means simple session file checking is insufficient. A daemon or reconnection mechanism is needed.

### Pattern 5: Auto-connect Flow

**What:** D-01 says inspection commands auto-connect without requiring `debug connect`. Each command checks for a session and creates one if needed.

**Implementation:** A shared decorator or helper function that wraps the async command body:

```python
async def with_session(
    project_path: Path,
    port: int,
    backend: GodotBackend,
    fn: Callable[[DebugSession], Awaitable[T]],
) -> T:
    """Run fn with a connected DebugSession, auto-connecting if needed."""
    async with DebugSession(port=port) as session:
        process = backend.launch_game(project_path, port)
        await session.wait_for_connection(timeout=30.0)
        await _poll_readiness(session)
        try:
            return await fn(session)
        finally:
            process.terminate()
            process.wait(timeout=5)
```

### Anti-Patterns to Avoid

- **Exposing raw object IDs in CLI interface:** Users should only work with NodePaths like `/root/Main/ScoreLabel`. Object IDs are internal and ephemeral. (Pitfall 7 from PITFALLS.md)
- **Sending multiple commands without waiting for responses:** The protocol has no request IDs. Serialize all commands. (Pitfall 5)
- **Assuming scene tree is ready immediately after connection:** Poll with backoff. (Pitfall 6)
- **Parsing properties array without skipping category separators:** Properties with `usage == 128` are categories, not real properties.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Scene tree response parsing | Ad-hoc index math | Structured recursive parser with offset object | Off-by-one in flat array parsing corrupts all subsequent nodes |
| NodePath to object ID resolution | Manual tree traversal each time | Cached path-to-ID map per session | Repeated tree queries are slow; cache invalidates on scene change |
| Session file locking | Custom file locking | `fcntl.flock()` on Unix, `msvcrt.locking()` on Windows, or a simple PID-based check | Race conditions between concurrent CLI invocations |
| .gitignore management | Manual string insertion | Check-and-append pattern with newline handling | Duplicate entries, missing newlines, file encoding issues |

## Common Pitfalls

### Pitfall 1: Scene Tree Response Is Flat, Not Nested

**What goes wrong:** The scene tree response data is a flat array of values (6 per node, depth-first), not a nested structure. Treating it as nested JSON or as a list of node objects leads to incorrect parsing.
**Why it happens:** The Godot protocol serializes trees as flat arrays for wire efficiency. The VS Code plugin reconstructs the tree recursively.
**How to avoid:** Use the recursive parse_scene_tree pattern with a mutable offset counter. Test with trees of varying depths (0, 1, 5+ levels).
**Warning signs:** Child nodes appear as siblings; tree depth is always 1.

### Pitfall 2: inspect_objects vs inspect_object Command Names

**What goes wrong:** The Godot source registers both `inspect_objects` (plural, batch) and `inspect_object` (singular). Using the wrong one gets no response.
**Why it happens:** The handler map has separate entries. The VS Code plugin uses `inspect_objects`.
**How to avoid:** Use `scene:inspect_objects` with `[object_ids_array, update_boolean]`. Even for single objects, wrap the ID in an array.
**Warning signs:** Command times out with no response.

### Pitfall 3: Property Category Separators (usage == 128)

**What goes wrong:** The property array from `inspect_objects` includes category separators (entries where `usage == 128`) mixed with real properties. Including these as properties shows garbage in output.
**Why it happens:** Godot's editor uses these to create collapsible sections in the Inspector panel. They are metadata, not property values.
**How to avoid:** Skip entries where `usage == 128` during property parsing.
**Warning signs:** Properties named "Node", "CanvasItem", "Control" with null values appearing in output.

### Pitfall 4: Game Only Connects Once

**What goes wrong:** Attempting session reuse by starting a new TCP server and expecting the game to reconnect. The game connects once at boot and does not retry.
**Why it happens:** Godot's remote_debugger_peer.cpp shows 6 connection attempts at startup with increasing delay (1ms to 1000ms), then gives up. No reconnection logic exists.
**How to avoid:** Either keep the TCP connection alive across CLI invocations (daemon), or accept that each command invocation launches a fresh game. Session files track running game PIDs, not reusable connections.
**Warning signs:** Second command hangs forever waiting for connection.

### Pitfall 5: debug_enter/debug_exit Must Be Handled

**What goes wrong:** The current recv_loop discards `debug_enter` and `debug_exit` as "unknown unsolicited messages". Phase 8 needs these to track pause/resume state and confirm execution control commands worked.
**Why it happens:** Phase 7 only needed to handle command responses, output, and errors.
**How to avoid:** Add `debug_enter` and `debug_exit` handlers to _dispatch() in session.py. Track game paused state in the session.
**Warning signs:** Execution control commands appear to succeed but GameState never updates.

### Pitfall 6: Speed Changes Are Immediate and Persistent

**What goes wrong:** Setting speed to 10x and forgetting to reset it. The speed persists for the entire game session.
**Why it happens:** `Engine.user_time_scale` is global state in the Godot engine.
**How to avoid:** Document in CLI help that speed changes persist. Consider having `debug speed` print the current speed before and after changes.
**Warning signs:** Game runs at unexpected speed in subsequent test steps.

### Pitfall 7: Output Buffer Format

**What goes wrong:** The `output` message from Godot contains two arrays: strings and types. `[["message1", "message2"], [0, 0]]`. Treating the data array as a single flat list of strings misses the type information.
**Why it happens:** Godot batches output messages and includes type flags (0=LOG, 1=ERROR, 2=LOG_RICH).
**How to avoid:** Parse the output data as `[strings_array, types_array]` and zip them together.
**Warning signs:** Output shows array brackets or nested lists instead of plain text.

## Discretion Recommendations

### D-09: Output/Error Separation

**Recommendation:** Combine output and errors in a single stream with a `type` field in `--json` mode. Add `--errors-only` flag that filters to errors only.

Rationale: Agents parsing `--json` can filter on the type field themselves. A single stream preserves chronological order, which is critical for debugging. The `--errors-only` flag is a convenience for humans. In human mode, prefix errors with `[ERROR]` for visual distinction.

```json
{"messages": [
  {"text": "Score: 10", "type": "output"},
  {"text": "Null reference in main.gd:42", "type": "error"}
]}
```

### D-10: Step Auto-Pause

**Recommendation:** `debug step` should auto-pause if the game is currently running. The `pause + step` sequence is the only workflow that makes sense; requiring explicit pause first adds friction for no safety benefit.

Rationale: If an agent sends `debug step` on a running game, the intent is unambiguous: pause and advance one frame. Requiring a separate `debug pause` first doubles the commands for the most common use case. The returned GameState JSON confirms `"paused": true` regardless.

### D-11: Speed Command Interface

**Recommendation:** Use a positional argument: `debug speed 10` (not `debug speed --multiplier 10`). Include `debug speed` with no argument to query current speed.

Rationale: The command is always about a single numeric value. A flag adds verbosity for no disambiguation benefit. Positional is shorter and more natural for agents and humans alike.

```
gdauto debug speed 10        # set to 10x
gdauto debug speed 0.5       # set to half speed  
gdauto debug speed            # query current speed (returns {"speed": 10.0})
```

## Code Examples

### Complete CLI Command Pattern (debug tree)

```python
# Source: established pattern from commands/debug.py (Phase 7)
@debug.command("tree")
@click.option("--project", type=click.Path(exists=True), default=".",
              help="Path to Godot project directory.")
@click.option("--port", type=int, default=6007,
              help="TCP port for debugger connection.")
@click.option("--depth", type=int, default=None,
              help="Maximum tree depth to display. Default: unlimited.")
@click.option("--timeout", type=float, default=30.0,
              help="Connection timeout in seconds.")
@click.pass_context
def debug_tree(ctx: click.Context, project: str, port: int,
               depth: int | None, timeout: float) -> None:
    """Get the live scene tree from a running game."""
    config: GlobalConfig = ctx.obj
    backend = GodotBackend(binary_path=config.godot_path)
    try:
        result = asyncio.run(
            _async_debug_tree(Path(project), port, depth, timeout, backend)
        )
    except (DebuggerError, GdautoError) as exc:
        emit_error(exc, ctx)
        return
    emit(result, _print_scene_tree, ctx)
```

### Scene Tree Request/Response Flow

```python
# Source: Godot scene_debugger.cpp (command registration) +
#         godot-vscode-plugin helpers.ts (response parsing)
async def get_scene_tree(
    session: DebugSession, max_depth: int | None = None,
) -> SceneNode:
    """Request and parse the full scene tree from the connected game."""
    data = await session.send_command("scene:request_scene_tree", [])
    root, _ = parse_scene_tree(data, offset=0, parent_path="")
    if max_depth is not None:
        root = _prune_depth(root, max_depth)
    return root
```

### Property Access by NodePath

```python
# Source: Godot scene_debugger_object.cpp (response format)
async def get_property(
    session: DebugSession,
    node_path: str,
    property_name: str,
) -> object:
    """Get a single property value from a node by its path."""
    tree = await get_scene_tree(session)
    node = _find_node_by_path(tree, node_path)
    if node is None:
        raise DebuggerError(
            message=f"Node not found: {node_path}",
            code="DEBUG_NODE_NOT_FOUND",
            fix=f"Check that {node_path} exists in the running scene tree",
        )
    data = await session.send_command(
        "scene:inspect_objects", [[node.instance_id], False],
    )
    _, _, props = parse_object_properties(data)
    for prop in props:
        if prop.name == property_name:
            return prop.value
    raise DebuggerError(
        message=f"Property '{property_name}' not found on {node_path}",
        code="DEBUG_PROPERTY_NOT_FOUND",
        fix=f"Check property name; available properties can be listed with debug get --node {node_path}",
    )
```

### Execution Control

```python
# Source: Godot scene_debugger.cpp (_msg_suspend_changed, _msg_next_frame, _msg_speed_changed)
async def pause_game(session: DebugSession) -> GameState:
    """Pause the running game."""
    await session.send_command("scene:suspend_changed", [True], timeout=5.0)
    return GameState(paused=True, speed=session.current_speed)

async def resume_game(session: DebugSession) -> GameState:
    """Resume the paused game."""
    await session.send_command("scene:suspend_changed", [False], timeout=5.0)
    return GameState(paused=False, speed=session.current_speed)

async def step_frame(session: DebugSession) -> GameState:
    """Advance one frame (auto-pauses if running)."""
    if not session.game_paused:
        await session.send_command("scene:suspend_changed", [True], timeout=5.0)
    await session.send_command("scene:next_frame", [], timeout=5.0)
    return GameState(paused=True, speed=session.current_speed)

async def set_speed(session: DebugSession, multiplier: float) -> GameState:
    """Set the game speed multiplier."""
    await session.send_command("scene:speed_changed", [multiplier], timeout=5.0)
    session.current_speed = multiplier
    return GameState(paused=session.game_paused, speed=multiplier)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Godot 3 debugger protocol | Godot 4 protocol with typed arrays and new Variant IDs | Godot 4.0 (2023) | Type IDs shifted; all codec work targets Godot 4.x |
| Single `inspect_object` | Batch `inspect_objects` with array of IDs | Godot 4.2+ | Can inspect multiple nodes in one round trip |
| No view_flags in scene tree | view_flags field added to RemoteNode | Godot PR #65118 (2022) | 6 fields per node instead of 4; includes visibility state |
| Editor-only scene debugging | VS Code plugin implements full scene tree + inspector | 2023-2025 | Validates that non-editor clients can use the protocol |

## Protocol Command Reference

### Commands gdauto Sends (Server -> Game)

| Command | Parameters | Expected Response | Notes |
|---------|------------|-------------------|-------|
| `scene:request_scene_tree` | `[]` | `scene:scene_tree` with flat node array | Response dispatched to pending future by command name |
| `scene:inspect_objects` | `[[object_id], false]` | `scene:inspect_objects` with property data | Note: response command matches request command name |
| `scene:suspend_changed` | `[true]` or `[false]` | `debug_enter` or `debug_exit` (unsolicited) | Fire-and-forget; state confirmed via debug_enter/exit |
| `scene:next_frame` | `[]` | None (frame advances, game stays paused) | Only works when game is already paused |
| `scene:speed_changed` | `[float]` | None (immediate effect) | Sets Engine.user_time_scale; 1.0 = normal |

### Messages Game Sends (Game -> Server)

| Message | Data Format | Current Handler |
|---------|-------------|-----------------|
| `scene:scene_tree` | Flat depth-first array, 6 fields per node | Dispatched to pending future (existing) |
| `scene:inspect_objects` | `[id, class_name, [[name, type, hint, hint_string, usage, value], ...]]` | Dispatched to pending future (existing) |
| `debug_enter` | `[can_continue, error_string, has_stack, thread_id]` | **NEEDS HANDLER** (currently discarded) |
| `debug_exit` | `[]` (empty) | **NEEDS HANDLER** (currently discarded) |
| `output` | `[[strings], [types]]` where types: 0=LOG, 1=ERROR, 2=LOG_RICH | Already buffered (existing) |
| `error` | `[error, error_descr, source_file, source_line, source_func, warning, hr, min, sec, msec, callstack]` | Already buffered (existing) |

## Session Persistence Design

### Architecture Decision: Daemon vs Per-Command

The core constraint: the Godot game connects to gdauto's TCP server once at boot and does not reconnect. This means the TCP server must survive across CLI invocations for session reuse (D-02).

**Recommended approach: In-process async server with session reuse within a single CLI invocation chain.**

For the MVP, adopt a pragmatic middle ground:
1. Each command does the full connect workflow if no session exists
2. The session file (`session.json`) tracks the game PID
3. If a game is already running (PID alive), kill it and relaunch (clean state)
4. For the `pause + inject + step + assert` workflow, a single command can chain operations internally

This defers true cross-process session reuse (daemon) while delivering all 6 requirements. The session file still serves its purpose: detecting stale game processes, preventing duplicate launches, and tracking port allocation.

**Session file operations:**

```python
# .gdauto/session.json management
def write_session_file(project_path: Path, info: SessionInfo) -> None:
    """Write session metadata and ensure .gdauto/ is in .gitignore."""
    gdauto_dir = project_path / ".gdauto"
    gdauto_dir.mkdir(exist_ok=True)
    _ensure_gitignore(project_path)
    (gdauto_dir / "session.json").write_text(json.dumps(info.to_dict(), indent=2))

def read_session_file(project_path: Path) -> SessionInfo | None:
    """Read session file, returning None if missing or invalid."""
    path = project_path / ".gdauto" / "session.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
        return SessionInfo(**data)
    except (json.JSONDecodeError, TypeError):
        return None

def cleanup_session(project_path: Path) -> None:
    """Remove session file and .gdauto directory if empty."""
    path = project_path / ".gdauto" / "session.json"
    if path.is_file():
        path.unlink()
    gdauto_dir = project_path / ".gdauto"
    if gdauto_dir.is_dir() and not any(gdauto_dir.iterdir()):
        gdauto_dir.rmdir()
```

### .gitignore Management

```python
def _ensure_gitignore(project_path: Path) -> None:
    """Add .gdauto/ to .gitignore if not already present."""
    gitignore = project_path / ".gitignore"
    marker = ".gdauto/"
    if gitignore.is_file():
        content = gitignore.read_text()
        if marker in content:
            return
        if not content.endswith("\n"):
            content += "\n"
        content += f"{marker}\n"
        gitignore.write_text(content)
    else:
        gitignore.write_text(f"{marker}\n")
```

## Open Questions

1. **Session reuse across CLI invocations**
   - What we know: The game connects once at boot and does not reconnect. True session reuse requires a daemon process.
   - What's unclear: Whether the user expects true cross-process reuse (D-02) in this phase or if MVP per-command sessions are acceptable.
   - Recommendation: Implement per-command sessions for Phase 8 MVP. Document that session reuse is a future enhancement requiring a daemon. The session file still prevents duplicate game launches and tracks state.

2. **D-06 fields: class_name, script_path, groups**
   - What we know: The scene tree response includes name, type_name, id, scene_file_path, view_flags. It does NOT include script_path, groups, or custom class_name.
   - What's unclear: These fields require a secondary `inspect_objects` call per node, which is expensive for large trees.
   - Recommendation: Include the 6 basic fields from the scene tree response in the default `debug tree` output. Add a `--full` flag that does secondary inspection for script_path/groups/class_name (at the cost of O(n) inspect calls). This satisfies D-06 with acceptable performance.

3. **scene:scene_tree vs scene:request_scene_tree response name mismatch**
   - What we know: The command sent is `scene:request_scene_tree` but the response comes as `scene:scene_tree`. The current send_command keys the pending future by command name.
   - What's unclear: Whether send_command needs modification to support response names that differ from request names.
   - Recommendation: Add an optional `response_key` parameter to send_command, or add a convenience method that registers the future under a different key than the command name.

## Sources

### Primary (HIGH confidence)
- [Godot scene_debugger.cpp](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.cpp) - Command registration: suspend_changed, next_frame, speed_changed handler parameter formats; scene: prefix capture routing
- [Godot scene_debugger.h](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.h) - RemoteNode struct fields: child_count, name, type_name, id, scene_file_path, view_flags
- [Godot remote_debugger.cpp](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger.cpp) - Output message format [strings, types]; error message serialization; debug_enter/debug_exit formats
- [Godot scene_debugger_object.cpp](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger_object.cpp) - inspect_objects response format [id, class_name, [[name, type, hint, hint_string, usage, value]]]
- [godot-vscode-plugin helpers.ts](https://github.com/godotengine/godot-vscode-plugin/blob/master/src/debugger/godot4/helpers.ts) - parse_next_scene_node: 6 fields per node, recursive descent, shared offset
- [godot-vscode-plugin server_controller.ts](https://github.com/godotengine/godot-vscode-plugin/blob/master/src/debugger/godot4/server_controller.ts) - Property parsing: destructured as [name, class_name, hint, hint_string, usage, value]; usage==128 is category
- [Godot PR #65118](https://github.com/godotengine/godot/pull/65118) - Added visible and view_flags to RemoteNode serialization

### Secondary (MEDIUM confidence)
- [DeepWiki: godot-vscode-plugin scene tree and inspector](https://deepwiki.com/godotengine/godot-vscode-plugin/4.4-scene-tree-and-inspector) - Architectural overview of scene tree parsing flow
- Phase 7 implementation files in src/gdauto/debugger/ - Verified working TCP session, protocol, variant codec, connect workflow

### Tertiary (LOW confidence)
- Session persistence daemon design - Based on architectural analysis, not proven implementation

## Metadata

**Confidence breakdown:**
- Protocol commands and parameters: HIGH -- verified from Godot C++ source code and VS Code plugin TypeScript implementation
- Scene tree response format: HIGH -- cross-verified between Godot source (RemoteNode struct), VS Code plugin (parse_next_scene_node), and Godot PR #65118
- Property inspection format: HIGH -- verified from scene_debugger_object.cpp and VS Code plugin server_controller.ts
- Execution control: HIGH -- command names and parameter types verified from scene_debugger.cpp handler registration
- Session persistence design: MEDIUM -- architectural analysis sound but implementation approach for cross-process reuse is unproven
- Output message format: HIGH -- verified from remote_debugger.cpp _put_msg("output", ...) implementation

**Research date:** 2026-04-06
**Valid until:** 2026-05-06 (protocol is stable; Godot 4.x debugger format unlikely to change)
