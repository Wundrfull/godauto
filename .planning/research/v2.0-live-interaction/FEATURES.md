# Feature Landscape: v2.0 Live Game Interaction

**Domain:** Godot remote debugger protocol bridge for automated game testing
**Researched:** 2026-03-29

## Table Stakes

Features that make the live interaction feature actually useful. Missing any of these makes the feature incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Connect to running Godot instance | Core purpose; without this, nothing else works | Medium | TCP server listening on configurable port, accept game connection, handle disconnects |
| Read scene tree at runtime | Primary use case: understand what exists in the running game | Medium | Uses built-in `scene:request_scene_tree` message; parse SceneDebuggerTree flat list format |
| Read node properties at runtime | Needed to inspect game state: positions, health, scores, visibility | Medium | Uses built-in `scene:inspect_objects` message; returns serialized property data |
| Modify node properties at runtime | Needed to manipulate game state for testing: set positions, toggle visibility | Medium | Uses built-in `scene:set_object_property` message; takes ObjectID + property name + value |
| Inject input events (key, mouse, action) | Core testing feature: simulate player interaction without human/OS-level input | High | Requires GDScript autoload with `Input.parse_input_event()`. Supports InputEventKey, InputEventMouseButton, InputEventAction |
| Launch game with debugger flag | Must automate the full workflow: launch + connect + interact | Low | Extend existing `backend.py` to add `--remote-debug tcp://host:port` flag |
| Auto-inject GDScript autoload | The custom capture autoload must be injected without manual user setup | Medium | Manipulate project.godot [autoload] section + copy .gd file to project; cleanup on exit |
| Timeout handling | Commands must not hang forever if game crashes or disconnects | Low | asyncio.wait_for() with configurable timeout on every command |
| Clean disconnection and cleanup | Must remove autoload from project.godot, kill game process on exit/error | Medium | Context manager pattern; atexit handler; signal handling for Ctrl+C |
| --json output on all commands | Existing gdauto contract: every command supports structured JSON output | Low | Reuse existing emit()/emit_error() pattern from output.py |

## Differentiators

Features that set this apart from alternatives. Not strictly required for MVP but provide significant value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Assertion/verification layer | `gdauto debug assert --node /root/Player --property health --equals 100` enables automated game testing without writing test scripts | High | Polling-based: repeatedly query property, compare, timeout. Needs wait_for_property(), assert_node_exists(), assert_property_equals() |
| Game speed control | Pause, resume, speed up, slow down the running game | Low | Built-in `scene:suspend_changed` (pause/resume) and `scene:speed_changed` (speed multiplier). Single message each. |
| Screenshot capture | Capture game screenshot for visual verification or documentation | Low | Built-in `scene:rq_screenshot` message. Save response to file. |
| Live node creation/removal | Create or remove nodes in the running scene tree | Medium | Built-in `scene:live_create_node` and `scene:live_remove_node`. Useful for injecting test fixtures. |
| Method invocation on nodes | Call arbitrary methods on live nodes (e.g., `player.take_damage(10)`) | High | Requires GDScript autoload capture. Must handle return values, argument serialization, error reporting. |
| Session management (keep-alive) | Keep game running across multiple CLI invocations for interactive debugging | High | Would require a persistent server daemon or named pipe. Defer to post-MVP. |
| End-to-end test runner | `gdauto test run --script test_idle_clicker.yaml` that launches game, executes steps, verifies assertions, reports pass/fail | Very High | Orchestrates launch + inject + multiple commands + assertions + cleanup. The "ultimate" feature but large scope. |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| OS-level input injection (PyAutoGUI) | Requires window focus, breaks headless/CI, platform-specific, fragile coordinates | Inject via `Input.parse_input_event()` inside Godot through debugger protocol |
| Custom Godot fork or build | Forces users off stock Godot, massive maintenance burden, defeats purpose of "works with any Godot 4.5+" | Use GDScript autoload + EngineDebugger API, which works on stock Godot |
| Visual record/replay system | Screen recording and pixel-based replay is brittle, huge scope, wrong abstraction level | Use structured assertions on node properties and game state |
| GDScript test framework | Building a full test framework that runs inside Godot (like GUT or GdUnit4) | gdauto tests from outside; complement, do not replace, in-engine test frameworks |
| Editor plugin integration | Building an EditorDebuggerPlugin that runs inside Godot editor | gdauto is a CLI tool that replaces the editor for automation purposes |
| Breakpoint/step debugging | Single-stepping through GDScript, variable inspection at breakpoints | Use Godot editor or VSCode plugin for interactive debugging; gdauto is for automation |
| Network/multiplayer testing | Testing multiplayer games with multiple connected clients | Entirely different problem; defer indefinitely |
| GPU/rendering validation | Screenshot pixel comparison, shader output validation | Requires vision model integration; out of scope for protocol-level tool |

## Feature Dependencies

```
Launch game with debugger -----> Connect to instance (TCP server)
                                      |
                                      v
Auto-inject autoload ----------> Read scene tree
                                      |
                    +-----------------+------------------+
                    |                 |                  |
                    v                 v                  v
             Read properties   Modify properties   Inject input
                    |                 |                  |
                    v                 v                  v
            Assertion layer    Live node edit    Game speed control
                    |
                    v
            E2E test runner (orchestrates all of the above)
```

Key dependency: **Auto-inject autoload** must happen before any input injection commands work. Scene tree reading and property get/set use built-in captures and work without the autoload.

## MVP Recommendation

**Phase 1: Protocol Foundation**
1. Variant binary codec (encode/decode all 39 type IDs)
2. TCP server with message framing
3. Connect to a manually-launched Godot game
4. Read scene tree
5. Read/set node properties

**Phase 2: Automation**
6. GDScript autoload for custom capture
7. Auto-inject autoload into project.godot
8. Launch game from gdauto with --remote-debug
9. Inject input events (key, mouse, action)
10. Game speed control (pause/resume/speed)
11. Clean teardown and cleanup

**Phase 3: Verification**
12. Assertion layer (wait_for_property, assert_node_exists, assert_property_equals)
13. Screenshot capture
14. End-to-end workflow: launch, interact, verify, report

**Defer:**
- Session management (keep-alive daemon): Complex, post-MVP
- E2E test runner with YAML scripts: Build on top of assertion layer in a later milestone
- Live node creation/removal: Nice-to-have, not critical path
- Method invocation: High complexity, defer unless needed for testing

## Sources

- [Godot scene_debugger.h](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.h) -- Complete list of built-in scene debugger messages
- [Godot EngineDebugger API](https://docs.godotengine.org/en/stable/classes/class_enginedebugger.html) -- GDScript API for custom captures
- [PlayGodot](https://github.com/Randroids-Dojo/PlayGodot) -- Feature reference for game automation (input injection, scene inspection, property modification)
- [GDAI MCP](https://github.com/3ddelano/gdai-mcp-plugin-godot) -- Feature reference for AI-driven Godot automation (editor-side, different architecture but similar feature set)
