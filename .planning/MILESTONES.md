# Milestones

## v1.0 gdauto (Shipped: 2026-03-29)

**Phases completed:** 4 phases, 16 plans, 30 tasks
**Source:** 7,279 LOC Python | **Tests:** 7,458 LOC Python (648 tests)
**Timeline:** 2 days (2026-03-27 to 2026-03-29)

**Key accomplishments:**

1. Custom state-machine parser for .tscn/.tres with round-trip fidelity (zero spurious diffs)
2. Aseprite-to-SpriteFrames bridge: all 4 animation directions, GCD-based variable timing, trim offset support
3. TileSet terrain automation: algorithmic blob-47, minimal-16, and RPG Maker peering bit generation
4. Headless export/import pipeline with exponential backoff retry logic for CI/CD
5. Scene list with cross-scene dependency graph, scene create from JSON definitions
6. SKILL.md auto-generation from Click introspection for AI agent discovery

**Archive:** `.planning/milestones/v1.0-ROADMAP.md`, `.planning/milestones/v1.0-REQUIREMENTS.md`

---

## v1.1 Godot 4.6 Compatibility and Audit (Shipped: 2026-03-29)

**Phases completed:** 2 phases, 4 plans, 8 tasks
**Changes:** 49 files, +5,669/-1,235 lines | 30 commits
**Timeline:** 1 day (2026-03-29)

**Key accomplishments:**

1. Removed load_steps from all generators for Godot 4.6.1 format compatibility
2. Added unique_id round-trip support for scene nodes (parse, preserve, serialize)
3. Added PackedVector4Array parser support for format=4 files
4. 4 new E2E tests validating format changes against headless Godot
5. Documented ecosystem position: no competing headless CLI tools found

**Archive:** `.planning/milestones/v1.1-ROADMAP.md`, `.planning/milestones/v1.1-REQUIREMENTS.md`

---
