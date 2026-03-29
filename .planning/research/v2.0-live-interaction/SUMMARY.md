# Research Summary: v2.0 Live Game Interaction

**Domain:** Godot remote debugger protocol bridge for automated game testing
**Researched:** 2026-03-29
**Overall confidence:** HIGH

## Executive Summary

Godot's remote debugger protocol is a well-documented binary TCP protocol where the editor/tool runs a TCP server on port 6007 and the game connects as a client via the `--remote-debug tcp://host:port` command-line flag. Messages are length-prefixed Variant Arrays using Godot's binary serialization format (4-byte little-endian length header followed by `encode_variant()` payload). The protocol has no handshake; messages flow immediately after TCP connection.

The built-in `scene:` debugger capture already provides scene tree inspection (`scene:request_scene_tree`), object property reading (`scene:inspect_objects`), property modification (`scene:set_object_property`), live editing operations, game speed control, and screenshot capture. This covers approximately 60% of what we need without any game-side code. The remaining 40% (input injection, custom game state queries, method invocation) requires a lightweight GDScript autoload that registers a custom `"gdauto"` capture via `EngineDebugger.register_message_capture()`.

The entire feature can be built with **zero new runtime dependencies**. Python's stdlib provides everything needed: `asyncio` for the TCP server and event loop, `struct` for binary encoding/decoding, `subprocess` for game process management. A custom Variant codec (~400-600 lines) handles the binary serialization, following the same build-in-house philosophy as gdauto's existing .tscn/.tres parser. Only `pytest-asyncio` is added as a dev dependency.

The primary architectural risk is correctly implementing the Godot 4.x Variant type table (39 types with specific IDs that differ from Godot 3.x documentation) and handling asynchronous message dispatch (unsolicited game messages interleave with command responses). Both risks are well-mitigated by the godot-vscode-plugin TypeScript implementation serving as a verified reference.

## Key Findings

**Stack:** Zero new runtime dependencies. Python stdlib (asyncio, struct, subprocess) plus a custom Variant codec. GDScript autoload for game-side input injection.

**Architecture:** Two-component system: Python TCP server (accepts game connection) + GDScript autoload (extends debugger with automation commands). Layered protocol abstraction: variant codec -> message framing -> high-level client API -> CLI commands.

**Critical pitfall:** The TCP server/client direction is counter-intuitive: gdauto must LISTEN (be the server), and the Godot game CONNECTS to gdauto. Getting this wrong means complete failure. The Godot 4.x type IDs differ significantly from 3.x; using the wrong table corrupts all messages.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Protocol Foundation** - Build the Variant codec and TCP protocol layer first
   - Addresses: Variant binary encoding/decoding (all 39 types), TCP server with message framing, basic send/receive
   - Avoids: Type ID mismatch pitfall (comprehensive unit tests), partial read pitfall (readexactly pattern), endianness pitfall (little-endian throughout)
   - Can be tested in isolation with mock data; no running Godot needed for unit tests

2. **Connection and Scene Inspection** - Connect to a real Godot game and read state
   - Addresses: Launch game with --remote-debug, accept TCP connection, scene tree retrieval, property reading/modification
   - Avoids: Server/client direction pitfall (TCP server started before game launch), port conflict pitfall (configurable port), game startup timing pitfall (wait for ready)
   - Requires Godot binary; E2E tests with @pytest.mark.requires_godot

3. **Input Injection and Automation** - GDScript autoload for game-side automation
   - Addresses: Auto-inject autoload into project.godot, input event injection (key, mouse, action), custom game state queries
   - Avoids: Autoload cleanup pitfall (context manager + atexit), unsolicited message pitfall (background dispatch loop)
   - New GDScript code; integration testing required

4. **Assertion Layer and CLI** - Verification commands and full CLI integration
   - Addresses: wait_for_property, assert_node_exists, assert_property_equals, game speed control, screenshot capture, full debug command group
   - Avoids: Float precision pitfall (epsilon-based comparison), object ID transience pitfall (re-query before acting)
   - End-to-end: launch game, interact, verify, report

**Phase ordering rationale:**
- Phase 1 has zero Godot dependency (pure Python codec + protocol); fastest to develop and test
- Phase 2 introduces first Godot dependency; validates that our codec actually works with the real engine
- Phase 3 depends on Phase 2 (connection must work before injecting input) and introduces GDScript
- Phase 4 depends on all previous phases; the assertion layer needs property reading (Phase 2) and input injection (Phase 3)

**Research flags for phases:**
- Phase 1: Unlikely to need more research; Variant format is fully documented and cross-referenced
- Phase 2: May need deeper research into SceneDebuggerTree serialization format (flat list encoding) when implementing tree parsing
- Phase 3: May need deeper research into specific InputEvent types and their Variant serialization (InputEventKey properties, mouse button indices)
- Phase 4: Standard patterns; assertion polling is well-understood

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new runtime deps; stdlib-only approach. Variant format documented in official docs + confirmed in VSCode plugin source + Godot engine source. |
| Features | HIGH | Built-in scene debugger provides 60% of capability. Feature gaps (input injection) addressable via documented EngineDebugger API. |
| Architecture | HIGH | Two-component (Python server + GDScript autoload) pattern proven by PlayGodot (custom fork) and GDAI MCP (editor plugin). Our approach uses stock Godot. |
| Pitfalls | HIGH | Wire protocol fully reverse-engineered from source. Server/client direction confirmed across multiple sources. Type ID table verified against VSCode plugin. |

## Gaps to Address

- **SceneDebuggerTree flat list format:** The exact serialization of the tree response (`scene:scene_tree`) needs detailed analysis during Phase 2 implementation. We know it is a "flat list depth first" encoding but the exact field structure per node is not fully documented.
- **Thread ID handling:** Godot 4.2+ added a thread ID field in message arrays. Need to test with Godot 4.5/4.6 to confirm exact position and whether it is always present.
- **Autoload timing guarantees:** The exact order of autoload `_ready()` vs game `_ready()` vs debugger connection establishment needs testing. The GDScript autoload's `_ready()` should fire early (autoloads load before scene), but this needs verification.
- **Windows-specific behavior:** TCP server behavior on Windows (firewall prompts, port binding semantics) may differ from Linux/macOS. gdauto targets Windows primarily (per dev environment).
- **Godot 4.5 vs 4.6 protocol differences:** Need to verify that the protocol is stable across minor versions. The type ID table should be stable, but message parameters might differ.

## Sources

- [Godot remote_debugger_peer.cpp](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger_peer.cpp)
- [Godot remote_debugger.cpp](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger.cpp)
- [Godot scene_debugger.h](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.h)
- [Godot scene_debugger.cpp](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.cpp)
- [Godot Binary Serialization API](https://docs.godotengine.org/en/stable/tutorials/io/binary_serialization_api.html)
- [godot-vscode-plugin](https://github.com/godotengine/godot-vscode-plugin) (TypeScript reference implementation)
- [PlayGodot](https://github.com/Randroids-Dojo/PlayGodot) (Python game automation via custom Godot fork)
- [GDAI MCP](https://github.com/3ddelano/gdai-mcp-plugin-godot) (AI-driven Godot editor automation)
- [gdtype-python](https://github.com/anetczuk/gdtype-python) (evaluated, not recommended)
- [EngineDebugger API](https://docs.godotengine.org/en/stable/classes/class_enginedebugger.html)
- [Godot Debugger Plugins PR #39440](https://github.com/godotengine/godot/pull/39440)
