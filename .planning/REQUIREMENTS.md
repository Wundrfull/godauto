# Requirements: gdauto

**Defined:** 2026-03-29
**Core Value:** Aseprite-to-SpriteFrames bridge: read Aseprite's JSON export and generate valid Godot .tres SpriteFrames resources with named animations, correct frame durations, atlas texture regions, and loop settings, entirely in Python with no Godot binary required.

## v2.0 Requirements

Requirements for Live Game Interaction milestone. Each maps to roadmap phases.

### Protocol Foundation

- [x] **PROTO-01**: Variant binary codec encodes and decodes all Godot types needed for debugger communication (null, bool, int, float, String, StringName, Vector2, Vector3, Color, NodePath, Object, Array, Dictionary)
- [ ] **PROTO-02**: TCP server accepts incoming Godot debugger connections with length-prefixed binary framing
- [ ] **PROTO-03**: Background receive loop drains unsolicited messages (performance, output, errors) to prevent TCP buffer flooding
- [ ] **PROTO-04**: Game launch integrates with existing GodotBackend, adding non-blocking subprocess with --remote-debug flag
- [ ] **PROTO-05**: Connection lifecycle manages connect, readiness detection, timeout, and clean disconnect

### Scene Inspection

- [ ] **SCENE-01**: User can retrieve the live scene tree as structured JSON showing all nodes, types, and paths
- [ ] **SCENE-02**: User can read any node property by NodePath (e.g., /root/Main/ScoreLabel.text)
- [ ] **SCENE-03**: User can capture game print() output and runtime errors through the debugger connection

### Game Interaction

- [ ] **INTERACT-01**: User can modify node properties at runtime (e.g., set Label.text, Button.disabled)
- [ ] **INTERACT-02**: User can inject input events (mouse clicks at position, key presses) via GDScript autoload bridge
- [ ] **INTERACT-03**: User can invoke methods on nodes by NodePath (e.g., call add_score(10) on /root/Main)
- [ ] **INTERACT-04**: GDScript bridge autoload is injected before launch and cleaned up after session (including crash recovery)

### Execution Control

- [ ] **EXEC-01**: User can pause and resume the running game
- [ ] **EXEC-02**: User can step one frame at a time while paused
- [ ] **EXEC-03**: User can set game speed (e.g., 10x for fast-forwarding idle timers)

### Verification Layer

- [ ] **VERIFY-01**: User can assert a node property equals/contains/matches an expected value with pass/fail result
- [ ] **VERIFY-02**: User can wait for a condition (property reaches value) with configurable timeout
- [ ] **VERIFY-03**: End-to-end test workflow: launch game, interact, verify, report results in a single command
- [ ] **VERIFY-04**: All debug commands support --json output consistent with gdauto's existing contract

## Future Requirements

Deferred to future milestones. Tracked but not in current roadmap.

### Visual Observation (Computer Use Integration)

- **VISUAL-01**: Screenshot capture of running game for visual verification
- **VISUAL-02**: Integration with Claude Computer Use API for visual game testing

### Advanced Automation

- **AUTO-01**: Replay/record gameplay sessions for regression testing
- **AUTO-02**: Signal monitoring (await specific Godot signals)
- **AUTO-03**: Custom GDScript expression evaluation during runtime
- **AUTO-04**: Multi-instance debugger (connect to multiple games simultaneously)

### RL/ML Pipeline

- **RLML-01**: Scaffolding/config generation for Godot RL Agents projects
- **RLML-02**: Training loop management via CLI

### Particle and Shader Generation

- **PARTICLE-01**: Generate .tres files for GPUParticles2D/3D from presets (fire, smoke, sparks)
- **SHADER-01**: Generate shader .tres from templates

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| GDScript breakpoint debugging (step, locals, call stack) | VS Code plugin and editor do this well; no agent value |
| Visual editor scene manipulation (live node creation/deletion) | Editor territory; gdauto has file-level scene commands |
| Performance profiling (FPS, draw calls, physics) | Specialized workflow; agents don't profile games |
| Camera override and viewport manipulation | No value for headless testing |
| Full DAP (Debug Adapter Protocol) implementation | Unnecessary; native Godot protocol is sufficient |
| WebSocket transport | TCP only, matching Godot's --remote-debug flag |
| Custom Godot fork or GDExtension plugin | Must work with stock Godot 4.5+ |
| Godot 3.x debugger support | Targets Godot 4.5+ only |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PROTO-01 | Phase 7 | Complete |
| PROTO-02 | Phase 7 | Pending |
| PROTO-03 | Phase 7 | Pending |
| PROTO-04 | Phase 7 | Pending |
| PROTO-05 | Phase 7 | Pending |
| SCENE-01 | Phase 8 | Pending |
| SCENE-02 | Phase 8 | Pending |
| SCENE-03 | Phase 8 | Pending |
| EXEC-01 | Phase 8 | Pending |
| EXEC-02 | Phase 8 | Pending |
| EXEC-03 | Phase 8 | Pending |
| INTERACT-01 | Phase 9 | Pending |
| INTERACT-02 | Phase 9 | Pending |
| INTERACT-03 | Phase 9 | Pending |
| INTERACT-04 | Phase 9 | Pending |
| VERIFY-01 | Phase 10 | Pending |
| VERIFY-02 | Phase 10 | Pending |
| VERIFY-03 | Phase 10 | Pending |
| VERIFY-04 | Phase 10 | Pending |

**Coverage:**
- v2.0 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0

---
*Requirements defined: 2026-03-29*
*Last updated: 2026-03-29 after roadmap creation*
