# Roadmap: gdauto

## Milestones

- v1.0 MVP -- Phases 1-4 (shipped 2026-03-29)
- v1.1 Godot 4.6 Compatibility and Audit -- Phases 5-6 (shipped 2026-03-29)
- v2.0 Live Game Interaction -- Phases 7-10 (in progress)

## Phases

<details>
<summary>v1.0 (Phases 1-4) -- SHIPPED 2026-03-29</summary>

- [x] Phase 1: Foundation and CLI Infrastructure (5/5 plans) -- File format parser, CLI skeleton, Godot backend wrapper, project commands
- [x] Phase 2: Aseprite-to-SpriteFrames Bridge (4/4 plans) -- completed 2026-03-28
- [x] Phase 3: TileSet Automation and Export Pipeline (4/4 plans) -- TileSet create, auto-terrain, export/import pipeline
- [x] Phase 4: Scene Commands, Test Suite, and Agent Discoverability (3/3 plans) -- completed 2026-03-29

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>v1.1 (Phases 5-6) -- SHIPPED 2026-03-29</summary>

- [x] Phase 5: Format Compatibility and Backwards Safety (2/2 plans) -- completed 2026-03-29
- [x] Phase 6: E2E Validation and Ecosystem Audit (2/2 plans) -- completed 2026-03-29

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

### v2.0 Live Game Interaction

**Milestone Goal:** Enable Claude Code to connect to a running Godot instance via the remote debugger protocol, read game state, inject player input, and verify behavior, closing the write-code-to-test-it loop without a human in the middle.

- [x] **Phase 7: Variant Codec and TCP Connection** - Binary protocol codec, TCP server, game launch, connection lifecycle (completed 2026-04-06)
- [ ] **Phase 8: Scene Inspection and Execution Control** - Read live scene tree, node properties, game output; pause/resume/step/speed
- [ ] **Phase 9: Game Interaction and Bridge System** - Modify properties, inject input, invoke methods via GDScript autoload bridge
- [ ] **Phase 10: Verification Layer and End-to-End Validation** - Assert/wait conditions, E2E test workflow, --json contract for all debug commands

## Phase Details

### Phase 7: Variant Codec and TCP Connection
**Goal**: gdauto can launch a Godot game, accept its debugger connection over TCP, and exchange binary-encoded messages reliably
**Depends on**: Phase 6 (existing GodotBackend infrastructure)
**Requirements**: PROTO-01, PROTO-02, PROTO-03, PROTO-04, PROTO-05
**Success Criteria** (what must be TRUE):
  1. Running `gdauto debug connect` launches a game, accepts its TCP connection, reports connection status, and disconnects cleanly
  2. The Variant codec round-trips all required Godot types (null, bool, int, float, String, StringName, Vector2, Vector3, Color, NodePath, Array, Dictionary) through encode/decode with byte-exact fidelity verified against Godot's own `var_to_bytes()` output
  3. Unsolicited messages (performance, output, errors) from the game are drained continuously without blocking the connection or flooding the buffer
  4. Connection timeout, game crash, and clean disconnect all produce actionable error messages with non-zero exit codes
**Plans**: TBD

### Phase 8: Scene Inspection and Execution Control
**Goal**: Users can observe live game state and control execution timing for deterministic testing
**Depends on**: Phase 7
**Requirements**: SCENE-01, SCENE-02, SCENE-03, EXEC-01, EXEC-02, EXEC-03
**Success Criteria** (what must be TRUE):
  1. Running `gdauto debug tree` returns the complete live scene tree as structured JSON showing all nodes with their types and paths
  2. Running `gdauto debug get --node /root/Main/ScoreLabel --property text` returns the current value of any node property by NodePath
  3. Running `gdauto debug output` captures game `print()` output and runtime errors through the debugger connection
  4. User can pause, resume, single-step one frame, and set game speed (e.g., 10x) through CLI commands, enabling the `pause + inject + step + assert` deterministic testing pattern
**Plans**: TBD

### Phase 9: Game Interaction and Bridge System
**Goal**: Users can modify game state and inject player input programmatically, with the bridge script infrastructure managed automatically
**Depends on**: Phase 8
**Requirements**: INTERACT-01, INTERACT-02, INTERACT-03, INTERACT-04
**Success Criteria** (what must be TRUE):
  1. Running `gdauto debug set --node /root/Main/ScoreLabel --property text --value "100"` modifies a node property at runtime and the change is observable in the game
  2. Running `gdauto debug input` injects mouse clicks at positions and key presses into the running game via the GDScript autoload bridge
  3. Running `gdauto debug call --node /root/Main --method add_score --args 10` invokes methods on nodes by NodePath
  4. The GDScript bridge autoload is injected into the project before launch and cleaned up after session end, including crash recovery (signal handlers, atexit, stale artifact detection on next startup)
**Plans**: TBD

### Phase 10: Verification Layer and End-to-End Validation
**Goal**: Users can write automated game tests that launch, interact, assert, and report results in a single workflow
**Depends on**: Phase 9
**Requirements**: VERIFY-01, VERIFY-02, VERIFY-03, VERIFY-04
**Success Criteria** (what must be TRUE):
  1. Running `gdauto debug assert --node /root/Main/ScoreLabel --property text --equals "10"` returns a structured pass/fail result
  2. Running `gdauto debug wait --node /root/Main/ScoreLabel --property text --equals "10" --timeout 5000` blocks until the condition is met or times out, with clear pass/fail reporting
  3. A single `gdauto debug test` command can launch a game, perform interactions, verify assertions, and report structured results (the idle clicker E2E scenario passes)
  4. All debug commands (`connect`, `tree`, `get`, `set`, `input`, `call`, `assert`, `wait`, `test`, `output`, `pause`, `resume`, `step`, `speed`) support `--json` output consistent with gdauto's existing error contract
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 7 -> 8 -> 9 -> 10

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation and CLI Infrastructure | v1.0 | 5/5 | Complete | 2026-03-27 |
| 2. Aseprite-to-SpriteFrames Bridge | v1.0 | 4/4 | Complete | 2026-03-28 |
| 3. TileSet Automation and Export Pipeline | v1.0 | 4/4 | Complete | 2026-03-28 |
| 4. Scene Commands, Test Suite, and Agent Discoverability | v1.0 | 3/3 | Complete | 2026-03-29 |
| 5. Format Compatibility and Backwards Safety | v1.1 | 2/2 | Complete | 2026-03-29 |
| 6. E2E Validation and Ecosystem Audit | v1.1 | 2/2 | Complete | 2026-03-29 |
| 7. Variant Codec and TCP Connection | v2.0 | 1/1 | Complete   | 2026-04-06 |
| 8. Scene Inspection and Execution Control | v2.0 | 0/0 | Not started | - |
| 9. Game Interaction and Bridge System | v2.0 | 0/0 | Not started | - |
| 10. Verification Layer and End-to-End Validation | v2.0 | 0/0 | Not started | - |
