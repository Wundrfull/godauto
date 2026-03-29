# Phase 6: E2E Validation and Ecosystem Audit - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Verify Phase 5 format changes against Godot 4.6.1 binary (E2E tests), validate TileSet atlas bounds under stricter 4.6 checking, confirm round-trip fidelity for 4.6-generated files, and document godauto's ecosystem position with updated compatibility claims in README and SKILL.md.

</domain>

<decisions>
## Implementation Decisions

### E2E Test Scope
- **D-01:** E2E tests use the existing `@pytest.mark.requires_godot` marker and `conftest.py` auto-skip infrastructure from Phase 4. Tests are written to validate against any Godot >= 4.5 binary on PATH. No version-specific test branching.
- **D-02:** If no Godot binary is available on this machine, tests skip gracefully. The tests exist as a validation contract: they run whenever Godot is available (CI, other dev machines). We do not block the phase on binary availability.
- **D-03:** Add specific E2E tests for: (a) SpriteFrames .tres loads in Godot without load_steps, (b) TileSet .tres loads without load_steps, (c) scene .tscn with unique_id round-trips correctly, (d) TileSet atlas bounds edge case (tiles at texture boundary).

### Ecosystem Audit Format
- **D-04:** Add a "Ecosystem Position" section to README.md documenting what godauto uniquely provides vs what other tools cover. Short, factual, not marketing copy.
- **D-05:** The audit is a one-time documentation task, not a recurring check. Internal notes in SKILL.md output are not needed; README is the right place for ecosystem positioning.

### Compatibility Claims
- **D-06:** README and SKILL.md claim "Godot 4.5+" (open-ended floor, no ceiling). This is the simplest and most accurate: we test against 4.5+ and have no known incompatibilities with any 4.x release.
- **D-07:** No compatibility matrix. The tool targets text file formats which are stable across 4.x. A matrix would imply version-specific differences that don't exist.

### Claude's Discretion
- Exact E2E test fixture design (what specific resources to generate and validate)
- TileSet atlas bounds test: exact tile size and texture dimensions for edge case
- README ecosystem section wording and structure
- Whether to update pyproject.toml classifiers for Godot version compatibility

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### E2E Test Infrastructure
- `tests/e2e/conftest.py` -- requires_godot marker, godot_backend fixture
- `tests/e2e/test_e2e_spriteframes.py` -- existing SpriteFrames E2E pattern
- `tests/e2e/test_e2e_tileset.py` -- existing TileSet E2E pattern
- `tests/e2e/test_e2e_scene.py` -- existing scene E2E pattern
- `src/gdauto/backend.py` -- GodotBackend for binary discovery and version validation

### Phase 5 Changes (must be validated)
- `.planning/phases/05-format-compatibility-and-backwards-safety/05-CONTEXT.md` -- format change decisions
- `.planning/phases/05-format-compatibility-and-backwards-safety/05-VERIFICATION.md` -- what was verified automated, what needs binary confirmation

### Documentation
- `README.md` -- needs ecosystem section and compatibility claim update
- `src/gdauto/skill/generator.py` -- SKILL.md generator (compatibility claim in output)

### Research
- `.planning/research/SUMMARY.md` -- ecosystem findings (no competing headless CLI tools)
- `.planning/research/PITFALLS.md` -- TileSet bounds strictness warning

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/e2e/conftest.py` -- pytest_collection_modifyitems hook for requires_godot auto-skip, godot_backend fixture
- `src/gdauto/sprite/validator.py` -- GDScript generation pattern for headless Godot validation
- `src/gdauto/tileset/validator.py` -- TileSet validation with headless Godot load
- `tests/unit/test_format_compat.py` -- 17 format compatibility tests (unit level, no binary)

### Established Patterns
- E2E tests generate resources via builder functions, write to tmp_path, invoke GodotBackend to load
- Validation GDScript: generate a .gd file that loads the resource and prints structured output
- All E2E tests use @pytest.mark.requires_godot and skip when no binary found

### Integration Points
- Add new E2E tests in tests/e2e/ following existing patterns
- Update README.md with ecosystem section
- Potentially update SKILL.md generator output header with version claim

</code_context>

<specifics>
## Specific Ideas

- Research found no competing headless CLI tools; Godot MCP servers all require running editor
- The main E2E risk is TileSet atlas bounds strictness in 4.6 (issue #112271)
- SpriteFrames and scene format stability is HIGH confidence from research
- README ecosystem section should name specific tools checked (Godot MCP Pro, GDAI MCP, GDToolkit, godot-ci) and note what they do vs what godauto does

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 06-e2e-validation-and-ecosystem-audit*
*Context gathered: 2026-03-29*
