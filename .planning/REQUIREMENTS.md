# Requirements: godauto v1.1

**Defined:** 2026-03-29
**Milestone:** v1.1 Godot 4.6 Compatibility and Audit
**Core Value:** Ensure godauto generates files compatible with Godot 4.6.1 while maintaining 4.5 backwards compatibility, and verify the tool's ecosystem position remains unique.

## v1.1 Requirements

### Format Compatibility

- [ ] **COMPAT-01**: All generators stop emitting `load_steps` in .tscn/.tres headers (affects SpriteFrames builder, TileSet builder, scene builder, and any other file generators)
- [ ] **COMPAT-02**: `SceneNode` dataclass captures `unique_id` integer attribute; parser reads it from [node] headers, serializer emits it when present
- [ ] **COMPAT-03**: Parser accepts both format=3 and format=4 .tscn/.tres files without error (format=4 used for PackedVector4Array/base64 PackedByteArray)
- [ ] **COMPAT-04**: Golden files updated to match Godot 4.6.1 output format (no load_steps, unique_id preserved in scene golden files)

### Backwards Compatibility

- [ ] **BACK-01**: Generated files remain loadable by Godot 4.5 (verify dropping load_steps is safe; Godot 4.5 tolerates omission)
- [ ] **BACK-02**: GodotBackend version validation accepts >= 4.5 and works correctly with 4.6.x binaries

### Validation and Testing

- [ ] **VAL-01**: E2E tests pass against Godot 4.6.1 binary (SpriteFrames, TileSet, scene load tests)
- [ ] **VAL-02**: TileSet atlas bounds validated under Godot 4.6 stricter checking (tiles outside texture rejected)
- [ ] **VAL-03**: Round-trip fidelity verified for Godot 4.6-generated .tscn/.tres files (parse and re-serialize without spurious diffs)

### Ecosystem Audit

- [ ] **ECO-01**: Document which godauto capabilities remain unique vs what ecosystem tools now provide (Godot MCP servers, editor plugins, other CLI tools)
- [ ] **ECO-02**: Update SKILL.md output and README with Godot 4.6.1 compatibility claims

## Future Requirements

Deferred to v1.2+:
- Full Tiled .tmx/.tmj map-to-TileMap .tscn conversion
- Scene editing (add/remove nodes, set properties, attach scripts, wire signals)
- PyPI publishing and distribution polish
- Addon/plugin management via Asset Library API
- Watch mode / file watcher for CI pipelines

## Out of Scope

| Feature | Reason |
|---------|--------|
| Godot 4.7+ support | Not yet released; audit covers 4.5-4.6.1 range |
| format=4 generation | godauto never generates PackedVector4Array/base64 resources; only needs to parse them |
| unique_id generation for new scenes | Let Godot assign these; godauto only preserves existing values |
| GUI or TUI interface | Contradicts agent-native design |
| Godot 3.x support | Different file format, shrinking user base |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| COMPAT-01 | Phase 5 | Pending |
| COMPAT-02 | Phase 5 | Pending |
| COMPAT-03 | Phase 5 | Pending |
| COMPAT-04 | Phase 5 | Pending |
| BACK-01 | Phase 5 | Pending |
| BACK-02 | Phase 5 | Pending |
| VAL-01 | Phase 6 | Pending |
| VAL-02 | Phase 6 | Pending |
| VAL-03 | Phase 6 | Pending |
| ECO-01 | Phase 6 | Pending |
| ECO-02 | Phase 6 | Pending |

**Coverage:**
- v1.1 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0

---
*Requirements defined: 2026-03-29*
