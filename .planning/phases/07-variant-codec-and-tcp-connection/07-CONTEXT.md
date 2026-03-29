# Phase 7: Variant Codec and TCP Connection - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the binary protocol foundation for live game interaction: a Godot Variant binary encoder/decoder covering 25+ types, a TCP server that accepts incoming debugger connections from Godot, game launch integration with GodotBackend, and connection lifecycle management (connect, readiness, timeout, disconnect). This phase produces no user-visible CLI commands beyond `debug connect`; it is infrastructure that all subsequent debug phases build on.

</domain>

<decisions>
## Implementation Decisions

### CLI Command Design
- **D-01:** Debug commands use `--project` flag on subcommands (not a global flag). Example: `gdauto debug connect --project ./my-game`
- **D-02:** `debug connect` is a combined command: starts TCP server, launches game, waits for connection. No separate launch/connect split.
- **D-03:** Default port is 6007 (matching Godot editor default). Override with `--port`.
- **D-04:** Debug subcommands use short verb names: `connect`, `tree`, `get`, `set`, `call`, `input`, `assert`, `wait`, `test`, `output`, `pause`, `resume`, `step`, `speed`, `disconnect`.
- **D-05:** `debug connect` accepts `--scene` flag to launch a specific scene instead of project's default main scene.
- **D-06:** CLI help for the debug group: "Live game interaction via Godot's remote debugger protocol. Connect to a running game, inspect state, inject input, and verify behavior."

### Session Model
- **D-07:** Claude's Discretion: session model (background server with session file vs self-contained commands). Research recommended hybrid: self-contained for Phase 7 MVP, background server for multi-command workflows. Claude decides the implementation approach that best serves the agent write-code-test-it loop.
- **D-08:** Claude's Discretion: session timeout (auto-shutdown after inactivity vs explicit disconnect). Claude picks a reasonable default.
- **D-09:** Claude's Discretion: single session only vs multiple sessions. For v2.0 scope (simple cases), single session is likely sufficient.
- **D-10:** Claude's Discretion: session file location (project directory vs temp directory). Claude picks location balancing visibility and cleanliness.
- **D-11:** Claude's Discretion: `debug connect` blocking behavior (foreground vs background). Claude picks based on agent workflow compatibility.

### Error Experience
- **D-12:** Claude's Discretion: protocol error verbosity. Likely: high-level messages for users, protocol details in --verbose mode. --json output includes full error context always.
- **D-13:** Claude's Discretion: game crash handling. Likely: immediate error with last captured output, automatic cleanup of session and bridge artifacts.

### Variant Codec
- **D-14:** Comprehensive Variant codec covering 25+ of 39 Godot types. All common types including Rect2, Transform2D, Basis, Packed*Array, etc. Future-proof for game state inspection. Estimated ~600 lines.
- **D-15:** Validation via golden byte tests: generate reference bytes from Godot's var_to_bytes(), compare against Python encoder output. This catches encoding bugs that round-trip-only tests would miss.

### Claude's Discretion
Areas where user deferred to Claude's judgment:
- Connect output format (success message content and structure)
- Test script format for `debug test` (Phase 10, not Phase 7, but noted for consistency)
- Debug command naming: short verbs selected (tree, get, set, call, etc.)
- Session model implementation details
- Error verbosity defaults
- Crash recovery behavior

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Protocol Specification
- `.planning/research/STACK.md` -- Wire protocol format, Variant type IDs, message framing details
- `.planning/research/ARCHITECTURE.md` -- TCP server architecture, session lifecycle, async/sync bridge pattern, command inventory
- `.planning/research/FEATURES.md` -- Feature dependency graph, competitive landscape, risk assessment

### Pitfalls and Risk Mitigation
- `.planning/research/PITFALLS.md` -- 12 critical pitfalls with prevention strategies (server-not-client, Variant encoding exactness, message flooding, etc.)
- `.planning/research/SUMMARY.md` -- Executive summary with phase structure rationale

### Existing Codebase (Integration Points)
- `src/gdauto/backend.py` -- GodotBackend class: binary discovery, version validation, blocking subprocess.run. Needs non-blocking launch_game() addition.
- `src/gdauto/errors.py` -- Error hierarchy: GdautoError with message/code/fix/to_dict(). New debugger errors follow this pattern.
- `src/gdauto/output.py` -- emit()/emit_error() with GlobalConfig for --json switching. Debug commands use this directly.
- `src/gdauto/cli.py` -- rich_click, command group registration via cli.add_command(). New debug group follows this pattern.
- `src/gdauto/formats/values.py` -- Existing Godot data type knowledge (Vector2, Color, NodePath) informs codec type mapping.

### External References
- [Godot Binary Serialization API](https://docs.godotengine.org/en/stable/tutorials/io/binary_serialization_api.html) -- Official Variant encoding spec
- [Godot remote_debugger_peer.cpp](https://github.com/godotengine/godot/blob/master/core/debugger/remote_debugger_peer.cpp) -- Wire format, TCP client behavior, buffer sizes
- [Godot scene_debugger.h](https://github.com/godotengine/godot/blob/master/scene/debugger/scene_debugger.h) -- Scene debugger message types
- [godot-vscode-plugin VariantDecoder](https://github.com/godotengine/godot-vscode-plugin) -- TypeScript reference implementation for Variant decoding

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `GodotBackend` (backend.py): Binary discovery, version check, subprocess management. Extend with non-blocking launch_game() for debug sessions.
- `GdautoError` hierarchy (errors.py): Consistent error pattern with code/fix/to_dict(). Add DebuggerError, ConnectionError, ProtocolError following same pattern.
- `emit()`/`emit_error()` (output.py): JSON/human output switching. Debug commands use this directly; no new output infrastructure needed.
- `ProjectConfig` (formats/project_cfg.py): project.godot parser with state machine, round-trip fidelity. Used in Phase 9 for bridge script autoload injection, but good to know about for architecture planning.

### Established Patterns
- All CLI commands use `rich_click as click` with `@click.pass_context` for GlobalConfig access.
- Error handling: catch domain errors, call `emit_error()`, return. Non-zero exit codes via `ctx.exit(1)`.
- Data models: `@dataclass` classes with `to_dict()` methods for JSON serialization.
- Package structure: domain packages (sprite/, tileset/, scene/) with `commands/` layer on top.

### Integration Points
- `cli.py`: Add `cli.add_command(debug)` alongside existing 7 command groups.
- `backend.py`: Add `launch_game()` method returning `subprocess.Popen` (non-blocking).
- `errors.py`: Add debugger-specific error classes.
- New package: `src/gdauto/debugger/` with variant.py, protocol.py, session.py, commands.py, models.py, errors.py.

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches. User consistently deferred technical decisions to Claude, indicating trust in research-informed implementation choices.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 07-variant-codec-and-tcp-connection*
*Context gathered: 2026-03-29*
