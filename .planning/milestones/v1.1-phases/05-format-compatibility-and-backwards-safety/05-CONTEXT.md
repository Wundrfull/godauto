# Phase 5: Format Compatibility and Backwards Safety - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Update all generators and parsers so godauto's output matches Godot 4.6.1 conventions (no load_steps, unique_id on scene nodes) while remaining loadable by Godot 4.5. Update golden files and validators to match.

</domain>

<decisions>
## Implementation Decisions

### load_steps Removal
- **D-01:** Drop load_steps from all output unconditionally. Set load_steps=None in all 7 builder call sites. Never write it. Godot 4.5 tolerates omission. Simplest approach with no version branching.
- **D-02:** Do NOT strip load_steps during round-trip parsing. If a 4.5 file has load_steps, preserve it in the parsed model (for inspection), just don't write it in new files.

### unique_id Handling
- **D-03:** Claude's discretion on unique_id approach: preserve on round-trip, and decide whether scene create should generate them based on technical analysis of Godot's expected format and the non-deterministic export issue (#115971).

### format=4 Support
- **D-04:** Claude's discretion on format=4 depth. Options: accept-without-error (best-effort raw passthrough) or full PackedVector4Array implementation. Pick based on effort vs likelihood.

### Golden File Strategy
- **D-05:** Claude's discretion on golden file approach: single set (4.6 format) vs two sets. Pick what's practical for the test infrastructure.

### Claude's Discretion
- unique_id generation strategy for scene create (preserve-only vs generate sequential)
- format=4 implementation depth (best-effort vs full parsing)
- Golden file versioning strategy (single set vs multi-version)
- Validator update approach for _check_load_steps() (remove, make no-op, or keep as legacy warning)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### File Format Changes
- `.planning/research/STACK.md` -- Godot 4.6/4.6.1 change impact analysis
- `.planning/research/ARCHITECTURE.md` -- Architecture integration points and backwards compatibility strategy
- `.planning/research/PITFALLS.md` -- Migration pitfalls with codebase-specific file references

### Source Files Affected
- `src/gdauto/formats/tres.py` -- GdResource dataclass (load_steps field), tres serializer
- `src/gdauto/formats/tscn.py` -- GdScene dataclass (load_steps field), SceneNode dataclass (needs unique_id), tscn serializer
- `src/gdauto/formats/common.py` -- Header attribute parsing (already handles format= and load_steps=)
- `src/gdauto/sprite/spriteframes.py` -- SpriteFrames builder (load_steps=N)
- `src/gdauto/sprite/splitter.py` -- Splitter builder (load_steps=N, two call sites)
- `src/gdauto/sprite/atlas.py` -- Atlas builder (load_steps=N)
- `src/gdauto/sprite/validator.py` -- _check_load_steps() validator
- `src/gdauto/commands/sprite.py` -- import-aseprite command (load_steps=N)
- `src/gdauto/tileset/builder.py` -- TileSet builder (load_steps=3)
- `src/gdauto/scene/builder.py` -- Scene builder (load_steps=N)
- `tests/fixtures/golden/` -- Golden reference files (need updating)

### Prior Phase Context
- `.planning/milestones/v1.0-phases/01-foundation-and-cli-infrastructure/01-CONTEXT.md` -- Parser model, round-trip fidelity decision
- `.planning/milestones/v1.0-phases/02-aseprite-to-spriteframes-bridge/02-CONTEXT.md` -- Validation pattern (load_steps mismatch as warning)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/gdauto/formats/tres.py` -- GdResource already has load_steps as Optional[int]; serializer already skips when None
- `src/gdauto/formats/tscn.py` -- GdScene already has load_steps as Optional[int]; serializer already skips when None
- `src/gdauto/formats/common.py` -- _extract_header_attrs() parses all bracket-section attributes generically
- `tests/unit/test_golden_files.py` -- normalize_for_comparison() with UID normalization patterns

### Established Patterns
- Builder functions construct GdResource/GdScene with explicit field values
- Serializer skips optional fields when None (load_steps, uid)
- Validators separate fatal issues from non-fatal warnings
- Golden file tests use normalize_for_comparison() for UID stripping

### Integration Points
- All 7 builder call sites pass load_steps=N explicitly; change to load_steps=None
- SceneNode dataclass needs unique_id: int | None field
- _extract_node() in tscn.py needs to read unique_id from header attrs
- _build_tscn_from_model() needs to emit unique_id when present

</code_context>

<specifics>
## Specific Ideas

- The fix for load_steps is mechanical: 7 call sites set load_steps=None instead of computing it
- Serializer in tres.py:188 and tscn.py:221 already has the `if load_steps is not None` guard
- The validator _check_load_steps() can be updated to no-op when load_steps is None (already does this)
- SceneNode unique_id follows the same pattern as other optional attributes (uid on resources)
- format=4 is only relevant for round-trip of user files; godauto never generates format=4

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 05-format-compatibility-and-backwards-safety*
*Context gathered: 2026-03-29*
