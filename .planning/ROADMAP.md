# Roadmap: gdauto

## Milestones

- **v1.0** -- Phases 1-4 (shipped 2026-03-29)
- **v1.1 Godot 4.6 Compatibility and Audit** -- Phases 5-6 (in progress)

## Phases

<details>
<summary>v1.0 (Phases 1-4) -- SHIPPED 2026-03-29</summary>

- [x] Phase 1: Foundation and CLI Infrastructure (5/5 plans) -- File format parser, CLI skeleton, Godot backend wrapper, project commands
- [x] Phase 2: Aseprite-to-SpriteFrames Bridge (4/4 plans) -- completed 2026-03-28
- [x] Phase 3: TileSet Automation and Export Pipeline (4/4 plans) -- TileSet create, auto-terrain, export/import pipeline
- [x] Phase 4: Scene Commands, Test Suite, and Agent Discoverability (3/3 plans) -- completed 2026-03-29

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

### v1.1 Godot 4.6 Compatibility and Audit

- [ ] **Phase 5: Format Compatibility and Backwards Safety** - Update generators, parser, and golden files for Godot 4.6.1 format changes while maintaining 4.5 compatibility
- [ ] **Phase 6: E2E Validation and Ecosystem Audit** - Verify all changes against Godot 4.6.1 binary and audit ecosystem position

## Phase Details

### Phase 5: Format Compatibility and Backwards Safety
**Goal**: Generated .tres/.tscn files match Godot 4.6.1 conventions with no regressions for Godot 4.5 users
**Depends on**: Phase 4 (v1.0 complete)
**Requirements**: COMPAT-01, COMPAT-02, COMPAT-03, COMPAT-04, BACK-01, BACK-02
**Success Criteria** (what must be TRUE):
  1. Running `gdauto sprite import-aseprite` produces .tres files without `load_steps` in the header
  2. Running `gdauto scene create` produces .tscn files without `load_steps` and with `unique_id` on each node
  3. Parsing a Godot 4.6-saved .tscn file (with `unique_id` and no `load_steps`) and re-serializing it produces byte-identical output
  4. All golden file comparison tests pass against the updated output format
  5. Generated files (without `load_steps`) load without error in both Godot 4.5 and 4.6.1
**Plans**: 2 plans

Plans:
- [ ] 05-01-PLAN.md -- Parser and format layer changes (unique_id, PackedVector4Array, load_steps removal)
- [ ] 05-02-PLAN.md -- Test infrastructure update and golden file regeneration

### Phase 6: E2E Validation and Ecosystem Audit
**Goal**: Confirmed compatibility with Godot 4.6.1 binary and documented ecosystem position
**Depends on**: Phase 5
**Requirements**: VAL-01, VAL-02, VAL-03, ECO-01, ECO-02
**Success Criteria** (what must be TRUE):
  1. Full E2E test suite passes against Godot 4.6.1 binary (SpriteFrames load, TileSet load, scene load, export pipeline)
  2. TileSet fixtures with atlas bounds at texture edges load without validation errors in Godot 4.6.1
  3. A Godot 4.6-generated .tscn file round-trips through `resource inspect` without spurious diffs
  4. SKILL.md and README reflect Godot 4.6.1 compatibility and document which capabilities remain unique in the ecosystem
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 5 -> 6

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation and CLI Infrastructure | v1.0 | 5/5 | Complete | 2026-03-27 |
| 2. Aseprite-to-SpriteFrames Bridge | v1.0 | 4/4 | Complete | 2026-03-28 |
| 3. TileSet Automation and Export Pipeline | v1.0 | 4/4 | Complete | 2026-03-28 |
| 4. Scene Commands, Test Suite, and Agent Discoverability | v1.0 | 3/3 | Complete | 2026-03-29 |
| 5. Format Compatibility and Backwards Safety | v1.1 | 0/2 | In progress | - |
| 6. E2E Validation and Ecosystem Audit | v1.1 | 0/0 | Not started | - |
