# Project Research Summary

**Project:** gdauto v2.0 — Live Game Interaction via Debugger Bridge
**Domain:** Godot remote debugger protocol, CLI-based game automation, agent-native testing
**Researched:** 2026-03-29
**Confidence:** MEDIUM

## Executive Summary

gdauto v2.0 adds live game interaction by implementing a TCP server that speaks Godot's binary Variant protocol. The key architectural insight — confirmed directly from Godot's C++ source — is that gdauto must act as the TCP *server*, not the client. The game, launched with `--remote-debug tcp://127.0.0.1:<port>`, connects to gdauto exactly as it would connect to the Godot editor. All communication uses length-prefixed binary frames carrying Godot Variant-encoded Arrays. This is architecturally distinct from everything gdauto does today: it introduces a long-lived async TCP session alongside a synchronous Click CLI, requiring a deliberate `asyncio.run()` boundary pattern.

The recommended approach adds zero new pip dependencies. The Variant binary codec (~300-500 lines using Python's `struct` module) mirrors the same "build vs buy" decision that drove the custom .tscn/.tres parser: the only existing Python library (gdtype-python) is 3.5 years stale and targets a Godot 4.0 beta. Input injection — the highest-risk feature — is handled via a GDScript autoload bridge injected into the target project before launch and removed after, avoiding the need for a custom Godot fork. The async boundary is managed by `asyncio.run()` at each Click command handler, keeping the existing 28 synchronous commands untouched.

The three biggest risks are: (1) Variant encoding correctness — a single alignment error causes silent message drops with no diagnostic feedback from Godot; (2) bridge script cleanup on crash — orphaned autoload entries corrupt the user's project and erode trust; (3) input injection timing — injected events are queued for the next game frame, making immediate assertions flaky. All three have documented mitigations but require deliberate upfront investment: a golden-byte codec test suite, signal handler and atexit cleanup infrastructure, and the `pause + inject + step + assert` pattern as the canonical testing model.

## Key Findings

### Recommended Stack

v2.0 adds zero new pip dependencies to gdauto's ~2.3MB core footprint. The entire debugger bridge is built on Python stdlib: `asyncio` for the TCP server and async communication, `struct` for binary encoding/decoding, `subprocess.Popen` for non-blocking game process management, and `dataclasses` for models. asyncclick was explicitly evaluated and rejected (would replace all of Click with a fork, risking 28 existing commands). gdtype-python was evaluated and rejected (3.5 years stale). trio and anyio were rejected (overkill for a single-connection server).

**Core technologies:**
- `asyncio` (stdlib): TCP server via `start_server()`, background recv loop, future-based response correlation — zero cost
- `struct` (stdlib): Godot Variant binary encoding (little-endian, 4-byte padding, type headers) — replaces abandoned gdtype-python
- `subprocess.Popen` (stdlib): Non-blocking game process launch — distinct from existing blocking `subprocess.run()` in GodotBackend
- `dataclasses` (stdlib): `SceneNode`, `NodeProperty`, `RemoteSceneTree` models — consistent with v1.0 internal data pattern

### Expected Features

**Must have (table stakes):**
- Variant binary encoder/decoder — every debugger message requires it; nothing works without it
- TCP server accepting Godot's connection — foundation for all interaction
- Game launch with `--remote-debug` flag — extends existing `GodotBackend`
- Scene tree retrieval (`scene:request_scene_tree`) — foundation for game state inspection
- Node property reading (`scene:inspect_object`) — required to verify score and label values
- Connection lifecycle management (connect, timeout, clean disconnect) — stable session throughout test
- Structured JSON output for all commands — required by v1.0 agent-native contract

**Should have (differentiators):**
- Input event injection via GDScript bridge — click button to trigger game logic (no editor, no fork)
- Node property modification at runtime (`scene:live_node_prop`) — change values during a session
- Assertion/verification DSL (`debug assert --node <path> --property <name> --equals <val>`) — scriptable verification
- Wait-for-condition with timeout (`debug wait ... --timeout`) — handle async game state changes
- Execution control: pause, resume, step frame, speed scale — deterministic test control
- Method invocation on nodes (`scene:live_node_call`) — call game logic directly

**Defer to post-MVP:**
- Screenshot capture — requires viewport texture extraction, complex encoding pipeline
- Replay/record sessions — can be layered on top of primitive inject/read operations
- Multi-instance connections — single connection model is sufficient for v2.0
- Signal monitoring (await specific game signals)
- Background daemon mode for interactive exploration

### Architecture Approach

The debugger bridge lives in a new `src/gdauto/debugger/` package, cleanly separated from existing commands. It follows a strict layered architecture: `variant.py` (pure encode/decode, no state) feeds `protocol.py` (length-prefix framing) feeds `session.py` (async TCP server, background recv loop, future-based correlation) feeds `commands.py` (high-level async methods). A standalone `bridge.py` handles GDScript autoload injection and cleanup. Click commands in `commands/debug.py` are thin wrappers calling `asyncio.run()` at the boundary.

The MVP uses a self-contained per-command model: each `debug` command is responsible for launching the game, accepting the connection, performing its operation, and tearing down. A background daemon model is deferred as a post-MVP enhancement for interactive workflows.

**Major components:**
1. `debugger/variant.py` — pure `encode(value) -> bytes` / `decode(data, offset) -> (value, consumed)`, no mutable state
2. `debugger/protocol.py` — length-prefix framing, Array wrapping/unwrapping, buffer size enforcement (8 MiB)
3. `debugger/session.py` — async TCP server, continuous background recv loop, future-based request/response correlation
4. `debugger/commands.py` — high-level async methods: `get_scene_tree()`, `set_property()`, `inject_input()`, `assert_property()`
5. `debugger/bridge.py` — generate and inject `gdauto_bridge.gd` autoload; cleanup with signal handlers + atexit
6. `debugger/models.py` — `SceneNode`, `NodeProperty`, `RemoteSceneTree` dataclasses
7. `commands/debug.py` — Click command group; `asyncio.run()` boundary; delegates to `commands.py`, formats via `output.py`

### Critical Pitfalls

1. **gdauto is the TCP server, not the client** — use `asyncio.start_server()` and start it BEFORE launching the game; the game calls `connect_to_host()` per `remote_debugger_peer.cpp`; implementing this backwards means zero connections
2. **Variant encoding must be byte-exact or messages are silently dropped** — build golden byte test fixtures from Godot's own `var_to_bytes()` before writing any protocol code; test strings of length 1, 4, 5, 8 (4-byte boundary cases); test 32-bit vs 64-bit int flag handling
3. **Bridge script cleanup on crash corrupts the user's project** — register signal handlers (SIGINT, SIGTERM), `atexit`, and a startup stale-artifact check; use a `.gdauto-session.json` marker file; place bridge in `.gdauto/` subdirectory
4. **Unsolicited messages flood the TCP buffer and freeze the game** — the background recv loop must run from the moment of connection and drain all messages continuously; never read directly from the socket in command handlers; buffer output/error messages with size limits
5. **Input injection timing requires `pause + inject + step + assert`** — `Input.parse_input_event()` queues for the next frame; assert immediately after inject is always flaky; this pattern must be the canonical documented approach

## Implications for Roadmap

Based on combined research, suggested phase structure:

### Phase 1: Variant Codec and Protocol Foundation

**Rationale:** Everything else is blocked until binary encoding works correctly. This is the highest-risk component and the "silent ignore" failure mode makes it impossible to debug from higher layers. Building and validating the codec first allows thorough unit testing in complete isolation with known byte sequences before any network code exists.
**Delivers:** `debugger/variant.py` (encode/decode for ~10 types needed by debugger messages), `debugger/protocol.py` (framing), `debugger/models.py` (dataclasses), `debugger/errors.py` (error hierarchy extension). No network code; everything testable via `pytest`.
**Addresses:** Variant binary encoder/decoder (table stakes)
**Avoids:** Pitfall 2 (encoding byte alignment errors) — golden byte tests from Godot's `var_to_bytes()` built in this phase

### Phase 2: TCP Server and Game Launch

**Rationale:** Once the codec is validated, build the session layer. The server-not-client architecture (Pitfall 1) is established here. The background recv loop (Pitfall 4) is built from connection day one, not retrofitted. Non-blocking game launch extends the existing `GodotBackend`. Windows TCP edge cases (Pitfall 8) are tested from the first integration test.
**Delivers:** `debugger/session.py` (async TCP server, continuous recv loop, future-based correlation), `backend.py` modification (non-blocking `launch_game()`), `gdauto debug connect` command (minimal: launch, accept, report status, disconnect)
**Uses:** `asyncio.start_server()`, `subprocess.Popen`, `asyncio.run()` at Click boundary
**Implements:** Session architecture, async/sync bridge pattern

### Phase 3: Read Game State

**Rationale:** With a working connection, prove the read path end-to-end. Scene tree retrieval and property reading have confirmed reference implementations (VS Code plugin) and are lower-risk than input injection. Boot-timing issues (Pitfall 6) and object ID ephemerality (Pitfall 7) are addressed here with the NodePath-based API design.
**Delivers:** `gdauto debug tree`, `gdauto debug get --node <path> --property <name>`, `gdauto debug output` (game print capture), NodePath-based API (no raw object IDs in CLI), boot-readiness polling with exponential backoff
**Addresses:** Scene tree retrieval, node property reading, error/output capture (all table stakes)
**Avoids:** Pitfall 6 (game not ready after TCP connect), Pitfall 7 (ephemeral object IDs)

### Phase 4: Bridge Script and Input Injection

**Rationale:** Input injection is the second-highest-risk feature and the primary differentiator. The GDScript bridge approach is the recommended path (stock Godot, no fork), but it requires project.godot mutation and thorough cleanup logic. Bridge cleanup (Pitfall 3) must be fully hardened before input injection is usable. The bridge and cleanup infrastructure are built together in this phase.
**Delivers:** `debugger/bridge.py` (autoload generation, injection, cleanup), `gdauto debug input` command, signal handlers + atexit cleanup, startup stale-artifact detection, `gdauto debug set` (property modification), `gdauto debug pause/resume/step/speed`
**Addresses:** Input event injection, node property modification, execution control (all differentiators)
**Avoids:** Pitfall 3 (bridge cleanup on crash), Pitfall 9 (input timing non-determinism)

### Phase 5: Verification Layer and End-to-End Validation

**Rationale:** With read and write both proven, build the assertion and test-scripting layer that closes the "write-code-to-test-it" loop for agents. This is pure Python logic on top of proven infrastructure, so protocol risk is near zero. The idle clicker end-to-end scenario is the acceptance test for this phase.
**Delivers:** `gdauto debug assert --node <path> --property <name> --equals <val>`, `gdauto debug wait --timeout`, `gdauto debug call --method`, idle clicker E2E demo test, `--json` output validation across all debug commands
**Addresses:** Assertion/verification DSL, wait-for-condition, method invocation (all differentiators)
**Avoids:** Pitfall 8 (Windows process/TCP behavior) via explicit Windows E2E coverage, Pitfall 11 (asyncio.run() reentrancy in pytest)

### Phase Ordering Rationale

- **Codec first, network second:** Silent encoding failures are undetectable from higher layers. Validating the codec in isolation eliminates the worst debugging scenarios before any async code exists.
- **Read before write:** Scene inspection has confirmed reference implementations; input injection does not. Proving the read path validates the TCP architecture before tackling the higher-risk write path.
- **Bridge cleanup before bridge injection:** Project mutation risk requires the cleanup infrastructure to be rock-solid before the feature ships. Building injection and cleanup together in Phase 4 ensures they are tested as a unit.
- **Windows from Phase 2:** The developer's primary platform is Windows. Async TCP and process management have Windows-specific edge cases that compound severely if deferred.
- **CLI integration throughout:** Each phase adds CLI commands. The internal API need not fully stabilize before CLI wrappers are added — commands grow incrementally with each phase.

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 1 (Variant Codec):** The scene tree response binary layout and `inspect_object` property array field order are undocumented and require empirical reverse-engineering against a live Godot 4.5+ binary. Write a GDScript probe script that encodes known data with `var_to_bytes()` and compare output to Python decoder.
- **Phase 4 (Input Injection):** Whether `scene:live_node_call` can invoke `Input.parse_input_event()` on the Input singleton (without a bridge script) is unconfirmed. Test this first; if it works, `bridge.py` scope shrinks significantly.

Phases with standard patterns (research-phase not required):

- **Phase 3 (Read Game State):** `scene:request_scene_tree` and `scene:inspect_object` are used by the VS Code plugin and Godot editor. Implementation follows directly from TypeScript reference code.
- **Phase 5 (Verification Layer):** Pure Python assertion logic on top of proven infrastructure. No new protocol territory.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All additions are stdlib; no external library decisions introduce uncertainty; zero new pip dependencies is a well-supported conclusion |
| Features | MEDIUM | Table stakes and differentiators are well-defined from Godot source and competitive analysis; input injection on stock Godot (without fork) is the primary open question |
| Architecture | MEDIUM | TCP server/client inversion is verified from Godot source; per-command self-contained model is pragmatic judgment, not a validated pattern; scene tree response format needs empirical verification |
| Pitfalls | MEDIUM | Protocol pitfalls derived from source code analysis and reference implementations, not firsthand Python debugger client experience; Windows-specific behavior needs runtime validation |

**Overall confidence:** MEDIUM

### Gaps to Address

- **Scene tree response binary layout:** The flat depth-first array format from `request_scene_tree` needs empirical testing against a live game. Write a GDScript probe and compare byte output to the Python decoder. Resolve in Phase 1 testing.
- **`inspect_object` property array field order:** The exact field layout (name, value, type, hint, hint_string, usage) needs empirical verification before `debug get` can be reliable. Resolve in Phase 3 before shipping.
- **Input injection via `live_node_call`:** Whether the stock debugger protocol can invoke `Input.parse_input_event()` on the Input singleton is unconfirmed. Test as the first step of Phase 4; if confirmed, bridge.py complexity is reduced.
- **Windows asyncio port reuse behavior:** `SO_REUSEADDR` semantics differ between Windows and Unix. Test port binding and release on Windows from Phase 2 onward; use `127.0.0.1` (not `localhost`) to avoid IPv6 resolution issues.
- **Game boot readiness signal:** No documented "scene tree ready" message exists. The recommended polling approach needs validation that retrying `request_scene_tree` before the scene is ready does not corrupt the protocol stream.

## Sources

### Primary (HIGH confidence)
- [Godot `remote_debugger_peer.cpp`](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger_peer.cpp) — TCP client behavior (game connects TO server), message framing, 8 MiB buffer limits, connection retry logic
- [Godot `scene_debugger.h/.cpp`](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.h) — Full inventory of 40+ scene debugger commands and message types
- [Godot `remote_debugger.cpp`](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger.cpp) — Core command dispatch, capture-prefix routing, core command list
- [Godot Binary Serialization API docs](https://docs.godotengine.org/en/stable/tutorials/io/binary_serialization_api.html) — Variant type IDs (0-38), encoding rules, padding, endianness
- [Python asyncio streams docs](https://docs.python.org/3/library/asyncio-stream.html) — `start_server()`, `StreamReader`/`StreamWriter` API
- [Python struct module docs](https://docs.python.org/3/library/struct.html) — Binary packing format strings for codec implementation

### Secondary (MEDIUM confidence)
- [godot-vscode-plugin](https://github.com/godotengine/godot-vscode-plugin) — Official VS Code TypeScript debugger; VariantDecoder, scene tree parser, inspector flow — primary reference implementation
- [PlayGodot](https://github.com/Randroids-Dojo/PlayGodot) — Python game automation proof-of-concept; validates TCP server approach and GDScript bridge concept, requires custom Godot fork
- [Godot PR #103297](https://github.com/godotengine/godot/pull/103297) — Scene debugger message timing issues; validates Pitfall 6 (boot readiness race condition)
- [Godot PR #53241](https://github.com/godotengine/godot/pull/53241) — Auto-increment debugger port behavior; validates port conflict handling design
- [asyncclick PyPI](https://pypi.org/project/asyncclick/) — Evaluated and rejected; documents risk of replacing Click stack

### Tertiary (LOW confidence)
- [gdtype-python](https://github.com/anetczuk/gdtype-python) — Stale Python Variant serializer; evaluated and rejected; useful only to confirm what NOT to do
- [pietrum/godot-binary-serialization](https://github.com/pietrum/godot-binary-serialization) — JavaScript Variant codec; useful as encoding edge case cross-reference
- [Godot MCP Pro article](https://dev.to/y1uda/i-built-a-godot-mcp-server-because-existing-ones-couldnt-let-ai-test-my-game-47dl) — Competitive landscape context; confirms gap gdauto fills

---
*Research completed: 2026-03-29*
*Ready for roadmap: yes*
