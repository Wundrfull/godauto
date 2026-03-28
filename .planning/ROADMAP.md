# Roadmap: gdauto

## Overview

gdauto delivers an agent-native CLI for Godot engine automation in four phases. Phase 1 builds the foundation: a custom Godot file format parser, CLI skeleton with --json infrastructure, Godot backend wrapper, and project management commands. Phase 2 delivers the core value proposition: the Aseprite-to-SpriteFrames bridge that no other headless tool provides. Phase 3 adds the second differentiator (TileSet terrain automation) alongside the export pipeline for CI/CD use. Phase 4 completes the tool with scene commands, comprehensive E2E testing, and SKILL.md agent discoverability.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation and CLI Infrastructure** - File format parser, CLI skeleton with --json, Godot backend wrapper, project commands, resource inspection
- [ ] **Phase 2: Aseprite-to-SpriteFrames Bridge** - Core value: convert Aseprite JSON exports to valid Godot SpriteFrames .tres resources
- [ ] **Phase 3: TileSet Automation and Export Pipeline** - TileSet creation, terrain peering bits, physics assignment, headless export/import commands
- [ ] **Phase 4: Scene Commands, Test Suite, and Agent Discoverability** - Scene list/create, comprehensive E2E tests, golden file validation, SKILL.md generation

## Phase Details

### Phase 1: Foundation and CLI Infrastructure
**Goal**: Users can install gdauto and use it to inspect Godot projects and resources; the parser, CLI framework, and backend wrapper are proven correct and ready for domain features
**Depends on**: Nothing (first phase)
**Requirements**: CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, FMT-01, FMT-02, FMT-03, FMT-04, FMT-05, FMT-06, FMT-07, PROJ-01, PROJ-02, PROJ-03, PROJ-04, PROJ-05, TEST-01
**Success Criteria** (what must be TRUE):
  1. User can run `gdauto --help` and see command groups (project, export, sprite, tileset, scene, resource) with descriptions parseable by AI agents
  2. User can run `gdauto resource inspect <file>` on any .tres or .tscn file and get valid JSON output describing its contents
  3. User can run `gdauto project info` in a Godot project and get project name, version, autoloads, and settings as JSON
  4. User can run `gdauto project validate` and get a report of missing resources, broken references, and (with Godot binary) script syntax errors
  5. All commands produce structured JSON errors with `--json` flag, non-zero exit codes on failure, and the parser round-trips .tres/.tscn files without introducing spurious diffs
**Plans:** 3/5 plans executed

Plans:
- [x] 01-01-PLAN.md -- Python package scaffolding, CLI skeleton with global flags, error handling, output abstraction
- [x] 01-02-PLAN.md -- Godot value type dataclasses with parsing, serialization, and arithmetic
- [x] 01-03-PLAN.md -- Custom .tscn/.tres parser with round-trip fidelity, UID and resource ID generation
- [ ] 01-04-PLAN.md -- project.godot parser and Godot backend wrapper
- [ ] 01-05-PLAN.md -- Project commands (info, validate, create), resource inspect, integration tests

### Phase 2: Aseprite-to-SpriteFrames Bridge
**Goal**: Users can convert Aseprite sprite sheet exports into valid Godot SpriteFrames resources from the command line, with full animation support, entirely without the Godot editor
**Depends on**: Phase 1
**Requirements**: SPRT-01, SPRT-02, SPRT-03, SPRT-04, SPRT-05, SPRT-06, SPRT-07, SPRT-08, SPRT-09, SPRT-10, SPRT-11, SPRT-12
**Success Criteria** (what must be TRUE):
  1. User can run `gdauto sprite import-aseprite` with an Aseprite JSON export and get a .tres SpriteFrames file that loads in Godot without modification, with named animations matching Aseprite tags
  2. Variable-duration animations convert correctly: per-frame timing is preserved via GCD-based base FPS with duration multipliers, and all four Aseprite directions (forward, reverse, ping-pong, ping-pong reverse) work
  3. User can run `gdauto sprite split` on a sprite sheet (with or without JSON metadata) and get a valid SpriteFrames resource, and `gdauto sprite create-atlas` batches multiple images into an atlas
  4. Generated SpriteFrames pass validation in headless Godot: animation names exist, frame counts match source, no broken texture references
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD
- [ ] 02-03: TBD

### Phase 3: TileSet Automation and Export Pipeline
**Goal**: Users can automate TileSet creation and terrain configuration from the command line, and export Godot projects headlessly for CI/CD pipelines
**Depends on**: Phase 2
**Requirements**: TILE-01, TILE-02, TILE-03, TILE-04, TILE-05, TILE-06, TILE-07, TILE-08, TILE-09, EXPT-01, EXPT-02, EXPT-03, EXPT-04, EXPT-05
**Success Criteria** (what must be TRUE):
  1. User can run `gdauto tileset create` with a sprite sheet and tile size and get a valid .tres TileSet, then run `gdauto tileset auto-terrain` to assign peering bits for 47-tile blob, 16-tile minimal, or RPG Maker layouts
  2. User can run `gdauto tileset assign-physics` to batch assign collision shapes to tile ranges, and `gdauto tileset inspect` to dump any TileSet as JSON
  3. User can run `gdauto export release|debug|pack` with a named preset and get structured error reporting; export auto-runs import when cache is missing
  4. User can run `gdauto import` to force re-import with retry logic that handles known Godot timing bugs, and generated TileSets pass validation in headless Godot with correct terrain painting behavior
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD
- [ ] 03-03: TBD

### Phase 4: Scene Commands, Test Suite, and Agent Discoverability
**Goal**: The tool is feature-complete with scene manipulation commands, has comprehensive test coverage validating all generated resources, and is fully discoverable by AI agents via SKILL.md
**Depends on**: Phase 3
**Requirements**: SCEN-01, SCEN-02, CLI-06, TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. User can run `gdauto scene list` to enumerate all scenes in a project with node trees and dependencies, and `gdauto scene create` to generate .tscn files from JSON/YAML definitions
  2. A SKILL.md file is auto-generated from the CLI command tree, containing all command names, arguments, options, and help text in a format AI agents can use for tool discovery
  3. E2E test suite loads all generated resource types (.tres SpriteFrames, .tres TileSets, .tscn scenes) in headless Godot and validates correctness; golden file tests verify output stability against known-good reference files
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation and CLI Infrastructure | 3/5 | In Progress|  |
| 2. Aseprite-to-SpriteFrames Bridge | 0/3 | Not started | - |
| 3. TileSet Automation and Export Pipeline | 0/3 | Not started | - |
| 4. Scene Commands, Test Suite, and Agent Discoverability | 0/2 | Not started | - |
