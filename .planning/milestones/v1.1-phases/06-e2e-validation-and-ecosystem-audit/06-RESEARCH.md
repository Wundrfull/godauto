# Phase 6: E2E Validation and Ecosystem Audit - Research

**Researched:** 2026-03-29
**Domain:** Godot 4.6.1 binary validation, headless E2E testing, ecosystem positioning
**Confidence:** HIGH

## Summary

Phase 6 validates Phase 5 format changes against a real Godot binary and documents godauto's ecosystem position. The work splits cleanly into two domains: (1) E2E tests that confirm SpriteFrames, TileSet, and scene files load correctly in headless Godot 4.6.1 with the new format (no load_steps, unique_id preserved), and (2) a documentation update to README.md and SKILL.md claiming Godot 4.5+ compatibility and summarizing what godauto uniquely provides.

The existing E2E test infrastructure is mature: 4 tests already exist in `tests/e2e/` using the `@pytest.mark.requires_godot` marker, `conftest.py` auto-skip hook, and `GodotBackend` fixture. The pattern (generate resource, write to tmp_path with project.godot, create GDScript validator, run headless Godot, check stdout) is proven and needs only extension, not redesign. Phase 6 adds new tests to this existing framework: an atlas-bounds edge case for TileSet, a round-trip fidelity test for Godot 4.6-generated .tscn files, and possibly explicit "no load_steps" verification.

The critical risk is that Godot is not available on the current development machine (confirmed: `godot` not on PATH). Per decision D-02, this is acceptable: the tests are written and committed, they skip gracefully, and they run whenever Godot is available. The phase is not blocked on binary availability.

**Primary recommendation:** Add 3-4 new E2E tests following the existing pattern in `tests/e2e/`, update README.md with a factual "Ecosystem Position" section, and update compatibility claims to "Godot 4.5+".

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** E2E tests use the existing `@pytest.mark.requires_godot` marker and `conftest.py` auto-skip infrastructure from Phase 4. Tests are written to validate against any Godot >= 4.5 binary on PATH. No version-specific test branching.
- **D-02:** If no Godot binary is available on this machine, tests skip gracefully. The tests exist as a validation contract: they run whenever Godot is available (CI, other dev machines). We do not block the phase on binary availability.
- **D-03:** Add specific E2E tests for: (a) SpriteFrames .tres loads in Godot without load_steps, (b) TileSet .tres loads without load_steps, (c) scene .tscn with unique_id round-trips correctly, (d) TileSet atlas bounds edge case (tiles at texture boundary).
- **D-04:** Add a "Ecosystem Position" section to README.md documenting what godauto uniquely provides vs what other tools cover. Short, factual, not marketing copy.
- **D-05:** The audit is a one-time documentation task, not a recurring check. Internal notes in SKILL.md output are not needed; README is the right place for ecosystem positioning.
- **D-06:** README and SKILL.md claim "Godot 4.5+" (open-ended floor, no ceiling). This is the simplest and most accurate: we test against 4.5+ and have no known incompatibilities with any 4.x release.
- **D-07:** No compatibility matrix. The tool targets text file formats which are stable across 4.x. A matrix would imply version-specific differences that don't exist.

### Claude's Discretion
- Exact E2E test fixture design (what specific resources to generate and validate)
- TileSet atlas bounds test: exact tile size and texture dimensions for edge case
- README ecosystem section wording and structure
- Whether to update pyproject.toml classifiers for Godot version compatibility

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VAL-01 | E2E tests pass against Godot 4.6.1 binary (SpriteFrames, TileSet, scene load tests) | Existing E2E tests (4 tests in tests/e2e/) already cover SpriteFrames, TileSet, and scene loading; Phase 5 removed load_steps from all builders; tests currently skip (no Godot on PATH) but are structurally ready; see Architecture Patterns for new test additions |
| VAL-02 | TileSet atlas bounds validated under Godot 4.6 stricter checking (tiles outside texture rejected) | Godot's TileSetAtlasSource has `has_tiles_outside_texture()` and `clear_tiles_outside_texture()` methods; the E2E test should create a TileSet where tile dimensions exactly fill the texture to verify no false-positive "outside texture" errors; see Common Pitfalls section |
| VAL-03 | Round-trip fidelity verified for Godot 4.6-generated .tscn/.tres files (parse and re-serialize without spurious diffs) | The parser uses raw_line preservation for round-trip fidelity (common.py line 279); Phase 5 verified byte-identical round-trip in unit tests; E2E test should create a .tscn in Godot 4.6, parse it with gdauto, re-serialize, and diff; see Architecture Patterns for test design |
| ECO-01 | Document which godauto capabilities remain unique vs what ecosystem tools now provide | Ecosystem research confirms: no competing headless CLI tool generates SpriteFrames from Aseprite JSON or automates TileSet terrain; MCP servers (GDAI MCP, Godot MCP Pro, godot-mcp-cli) all require running editor; GDToolkit is GDScript-only (lint/format); godot-ci is Docker export only; see Ecosystem Findings section |
| ECO-02 | Update SKILL.md output and README with Godot 4.6.1 compatibility claims | README needs "Godot 4.5+" claim in install section and new Ecosystem Position section; SKILL.md generator output header already derives from CLI help text (no hardcoded version); generator.py only needs changes if we want explicit version claims in output |
</phase_requirements>

## Standard Stack

No new dependencies are needed for this phase. All work uses the existing test and documentation infrastructure.

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 | E2E test runner | Already installed; `@pytest.mark.requires_godot` marker infrastructure exists |
| GodotBackend | (internal) | Headless Godot invocation | `src/gdauto/backend.py`; binary discovery, version validation, subprocess management |

### Supporting (already installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-cov | 7.1.0 | Coverage for E2E tests | Optional; `uv run pytest --cov=gdauto` |

**No installation required.** All dependencies are already in the project.

## Architecture Patterns

### Existing E2E Test Structure
```
tests/
  e2e/
    __init__.py
    conftest.py                    # requires_godot auto-skip, godot_backend fixture
    test_e2e_spriteframes.py       # SpriteFrames load validation
    test_e2e_tileset.py            # TileSet + terrain load validation
    test_e2e_scene.py              # Scene instantiation validation
```

### Pattern 1: E2E Validation GDScript (established)
**What:** Generate a resource, write a GDScript that loads and validates it, run in headless Godot, check stdout for VALIDATION_OK/VALIDATION_FAIL.
**When to use:** All E2E tests in this phase.
**Example (from existing test_e2e_spriteframes.py):**
```python
@pytest.mark.requires_godot
def test_spriteframes_loads_in_godot(
    tmp_path: Path, godot_backend: GodotBackend
) -> None:
    # 1. Build resource
    resource = build_spriteframes(aseprite_data, "res://test_sheet.png")
    # 2. Write to tmp_path
    serialize_tres_file(resource, tmp_path / "test.tres")
    # 3. Write project.godot (minimal, required for res:// paths)
    (tmp_path / "project.godot").write_text(_PROJECT_GODOT)
    # 4. Write validation GDScript
    script_path = tmp_path / "validate.gd"
    script_path.write_text(_build_validation_script("test.tres"))
    # 5. Run headless Godot
    result = godot_backend.run(
        ["--headless", "--script", str(script_path)],
        project_path=tmp_path,
    )
    # 6. Assert
    assert "VALIDATION_OK" in result.stdout
```

### Pattern 2: Round-Trip Fidelity Test (new for VAL-03)
**What:** Create a .tscn file with Godot 4.6 features (unique_id on nodes), parse it with gdauto's parser, serialize it back, verify the output matches the input (modulo normalization).
**When to use:** VAL-03 round-trip verification.
**Design:**
```python
@pytest.mark.requires_godot
def test_tscn_round_trip_fidelity(
    tmp_path: Path, godot_backend: GodotBackend
) -> None:
    # 1. Create a scene via gdauto (contains unique_id from Phase 5)
    definition = {"root": {"name": "RoundTrip", "type": "Node2D", "children": [
        {"name": "Child", "type": "Sprite2D", "properties": {"position": "Vector2(10, 20)"}},
    ]}}
    scene = build_scene(definition)
    tscn_path = tmp_path / "test_scene.tscn"
    serialize_tscn_file(scene, tscn_path)

    # 2. Load in Godot (which adds unique_id to nodes), re-save
    # Use a GDScript that loads the scene and saves it back
    # 3. Parse the Godot-saved file with gdauto
    # 4. Serialize back
    # 5. Compare: the gdauto re-serialized version should match Godot's save
```

### Pattern 3: TileSet Atlas Bounds Edge Case (new for VAL-02)
**What:** Create a TileSet where tiles exactly fill the texture boundaries (no gap, no overflow), load in Godot, verify no "tiles outside texture" error.
**When to use:** VAL-02 atlas bounds validation.
**Design:**
```python
@pytest.mark.requires_godot
def test_tileset_atlas_bounds_edge(
    tmp_path: Path, godot_backend: GodotBackend
) -> None:
    # Create a TileSet with tiles that exactly fill texture bounds
    # For a 64x64 texture with 16x16 tiles: 4 columns x 4 rows = 16 tiles
    # This is the edge case: no pixel gap between last tile and texture edge
    resource = build_tileset(
        image_res_path="res://tileset.png",
        tile_width=16,
        tile_height=16,
        columns=4,
        rows=4,
    )
    # The GDScript validation should check has_tiles_outside_texture()
```

### Anti-Patterns to Avoid
- **Version-specific test branching:** D-01 explicitly prohibits this. Write tests that work against any Godot >= 4.5 binary.
- **Blocking on Godot availability:** D-02 says tests skip when binary is absent. Never use `pytest.skip` conditionally on version; the conftest.py hook handles this.
- **Asserting exact Godot output format:** Godot may output diagnostic lines to stderr. Only check for the specific VALIDATION_OK/VALIDATION_FAIL markers in stdout.
- **Creating dummy texture files for TileSet E2E:** The existing TileSet E2E tests reference `res://tileset.png` but do not create the actual image. Godot loads the TileSet .tres structurally without needing the texture file physically present (the TileSet definition is valid even without the texture). However, if atlas bounds validation checks require the texture, create a minimal PNG with Pillow or embed a 1x1 PNG.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| E2E test skip logic | Custom skip decorators | `@pytest.mark.requires_godot` + conftest.py hook | Already implemented in Phase 4; auto-skips when `shutil.which("godot")` returns None |
| Godot binary discovery | PATH search + version parse | `GodotBackend.ensure_binary()` | Handles explicit path, GODOT_PATH env var, and PATH; validates version >= 4.5 |
| GDScript generation for validation | Inline f-strings in tests | Dedicated `_build_*_validation_script()` helper functions | Pattern established in all 3 existing E2E test files; keeps test bodies clean |
| Project.godot boilerplate | Repeated string literals | `_PROJECT_GODOT` module constant | Already defined in each E2E test module; config_version=5, minimal [application] section |

## Common Pitfalls

### Pitfall 1: TileSet Atlas Bounds May Require Actual Texture File
**What goes wrong:** The TileSet atlas bounds validation in Godot's `create_tile()` path checks whether tiles are within texture dimensions. If no actual texture file exists at the referenced path, Godot may skip bounds validation entirely (treating it as a 0x0 texture) or emit errors about missing resources rather than testing what we want.
**Why it happens:** Godot's `TileSetAtlasSource` needs to know the texture dimensions to validate atlas bounds. With no texture file, it cannot perform the check.
**How to avoid:** For the atlas bounds edge case test, create a minimal PNG file at `res://tileset.png` in tmp_path using either: (a) a hardcoded bytes literal for a minimal valid PNG, or (b) Pillow if available. A 64x64 single-color PNG is 89 bytes when minimal. The existing E2E tests for basic TileSet loading may not hit this issue because they only check `load()` success, not tile-level validation.
**Warning signs:** Godot stderr contains "Failed loading resource" or the validation script does not exercise atlas bounds checking.

### Pitfall 2: Headless Godot May Not Execute Resource Import
**What goes wrong:** When running with `--headless --script`, Godot may not auto-import resources in the project. If the validation GDScript uses `load("res://...")`, the resource may fail to load because Godot has not run its import pass.
**Why it happens:** The `--script` flag runs the script immediately without the editor's import pass. Resources in `res://` need to be either already imported (`.godot/imported/` exists) or not require import (like .tres text resources which Godot loads directly).
**How to avoid:** For .tres/.tscn files, Godot loads them as text resources directly without needing an import pass. This is why the existing E2E tests work: `load("res://test_spriteframes.tres")` reads the text file directly. For tests involving textures that need import (like the atlas bounds test), run `godot_backend.import_resources(tmp_path)` first, or write the GDScript to use `load()` on the .tres file (which references the texture by path but does not require the texture to be imported for structural validation).
**Warning signs:** `load()` returns null in the GDScript; stderr shows "No loader found" or "Failed to load resource".

### Pitfall 3: Round-Trip Test Depends on Godot Saving The File
**What goes wrong:** The round-trip fidelity test (VAL-03) requires Godot to load a .tscn, potentially modify it (adding unique_id to nodes), and save it back. Getting Godot to save a file in headless mode requires a GDScript that uses `ResourceSaver.save()` or `save_scene()`. This is more complex than the existing load-only validation scripts.
**Why it happens:** The existing E2E pattern only loads and inspects resources. Saving requires additional GDScript logic and correct ResourceSaver API usage.
**How to avoid:** Two approaches:
  1. **Simpler (recommended):** Instead of having Godot save the file, verify round-trip in Python only. Parse a hand-crafted .tscn that includes unique_id (simulating a 4.6-generated file), serialize it back, and diff. This is already tested in Phase 5 unit tests (test_format_compat.py::TestUniqueIdRoundTrip). The E2E test adds value by confirming Godot can *load* the round-tripped file.
  2. **Full E2E:** Write a GDScript that loads the .tscn as PackedScene, re-saves it, then have Python parse the Godot-saved version and compare.
**Warning signs:** ResourceSaver API errors in GDScript; file permissions issues in tmp_path.

### Pitfall 4: README Ecosystem Claims That Become Stale
**What goes wrong:** Naming specific competing tools (GDAI MCP, Godot MCP Pro, etc.) in README creates claims that become outdated as the ecosystem evolves.
**Why it happens:** The Godot MCP ecosystem is moving rapidly. New tools may emerge that overlap with godauto.
**How to avoid:** Per D-04, keep the section "short, factual, not marketing copy." Focus on capability categories (headless file generation, editor-required tools, CI containers, GDScript linters) rather than naming individual projects. Name categories, not competitors.
**Warning signs:** README makes direct product comparisons that could become outdated within months.

## Ecosystem Findings

Research confirms godauto occupies a unique niche. No competing tool provides headless Aseprite-to-SpriteFrames conversion or programmatic TileSet terrain configuration. The ecosystem breaks into clear categories:

### Category Map (HIGH confidence)

| Category | Tools | What They Do | Overlaps With godauto? |
|----------|-------|-------------|------------------------|
| GDScript quality | GDToolkit (gdlint, gdformat) | Lint and format GDScript files | No overlap; godauto operates on resource/scene files, not scripts |
| CI/CD containers | godot-ci (barichello, samuelhwilliams) | Docker images with headless Godot for export | Partial overlap: godauto `export` also wraps headless export. Docker images provide the environment; godauto provides the commands |
| MCP servers | GDAI MCP, Godot MCP Pro, godot-mcp-cli, Godot Sentinel | AI-assisted editor control; require running Godot editor | No overlap on core features; MCP servers need running editor, godauto operates without editor. Different paradigm. |
| Version management | GodotEnv | Install and switch Godot versions | No overlap; orthogonal tool |

### godauto's Unique Capabilities (no equivalent exists)
1. Aseprite JSON to SpriteFrames .tres generation (pure Python, no Godot binary)
2. TileSet terrain peering bit automation (blob-47, minimal-16, RPGMaker layouts)
3. TileSet physics collision batch assignment
4. .tscn/.tres round-trip parse and serialize with format fidelity
5. SKILL.md generation for AI agent discoverability

### Recommended README Section Structure
```markdown
## Ecosystem Position

godauto fills a specific gap in the Godot tooling ecosystem: headless,
editor-free file manipulation.

| Need | Existing Solutions | godauto's Approach |
|------|-------------------|-------------------|
| GDScript quality | GDToolkit (gdlint, gdformat) | Not covered (different domain) |
| CI/CD export | Docker images with headless Godot | `gdauto export` wraps headless binary with retry logic |
| Editor automation | MCP servers (require running editor) | No editor needed; direct file manipulation |
| Aseprite to SpriteFrames | None | `gdauto sprite import-aseprite` |
| TileSet terrain automation | None (manual editor clicking) | `gdauto tileset auto-terrain` |
| Resource inspection | Editor only | `gdauto resource inspect --json` |
```

## Code Examples

### E2E Test: Atlas Bounds Edge Case Validation GDScript
```gdscript
extends SceneTree

func _init() -> void:
    var res = load("res://test_tileset.tres")
    if res == null:
        print("VALIDATION_FAIL: Could not load TileSet")
        quit(1)
    if not res is TileSet:
        print("VALIDATION_FAIL: Resource is not TileSet, got " + res.get_class())
        quit(1)
    var sources = res.get_source_count()
    if sources == 0:
        print("VALIDATION_FAIL: No atlas sources found")
        quit(1)
    # Check atlas bounds (VAL-02)
    var atlas: TileSetAtlasSource = res.get_source(0)
    if atlas.has_tiles_outside_texture():
        print("VALIDATION_FAIL: Tiles outside texture detected")
        quit(1)
    print("VALIDATION_OK: sources=" + str(sources) + " bounds=valid")
    quit(0)
```

### E2E Test: Round-Trip Fidelity Approach
```python
@pytest.mark.requires_godot
def test_roundtrip_fidelity(tmp_path: Path, godot_backend: GodotBackend) -> None:
    """Parse a .tscn with unique_id, re-serialize, load in Godot."""
    # Hand-craft a 4.6-style .tscn with unique_id
    tscn_content = (
        "[gd_scene format=3]\n\n"
        '[node name="Root" type="Node2D" unique_id=42]\n\n'
        '[node name="Child" type="Sprite2D" parent="." unique_id=99]\n'
        "position = Vector2(10, 20)\n"
    )
    # Parse and re-serialize (round-trip)
    scene = parse_tscn(tscn_content)
    roundtripped = serialize_tscn(scene)

    # Write the round-tripped version and validate it loads
    tscn_path = tmp_path / "test_scene.tscn"
    tscn_path.write_text(roundtripped)
    (tmp_path / "project.godot").write_text(_PROJECT_GODOT)

    script = _build_scene_validation_script("test_scene.tscn", "Node2D")
    (tmp_path / "validate.gd").write_text(script)

    result = godot_backend.run(
        ["--headless", "--script", str(tmp_path / "validate.gd")],
        project_path=tmp_path,
    )
    assert "VALIDATION_OK" in result.stdout
```

### Minimal PNG for Atlas Bounds Test
```python
# 64x64 single-color PNG (minimal valid image for TileSet texture)
# Can be generated without Pillow using raw PNG bytes
import struct
import zlib

def create_minimal_png(path: Path, width: int = 64, height: int = 64) -> None:
    """Create a minimal valid PNG file for TileSet testing."""
    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"
    # IHDR chunk
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = _png_chunk(b"IHDR", ihdr_data)
    # IDAT chunk (minimal: all black pixels)
    raw_data = b""
    for _ in range(height):
        raw_data += b"\x00" + b"\x00\x00\x00" * width  # filter byte + RGB
    compressed = zlib.compress(raw_data)
    idat = _png_chunk(b"IDAT", compressed)
    # IEND chunk
    iend = _png_chunk(b"IEND", b"")
    path.write_bytes(sig + ihdr + idat + iend)

def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    return length + chunk_type + data + crc
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| .tres/.tscn with load_steps | .tres/.tscn without load_steps | Godot 4.6 (Jan 2026) | Phase 5 already removed load_steps from all generators |
| [node] without unique_id | [node] with unique_id=N | Godot 4.6 (Jan 2026) | Phase 5 added unique_id support to parser and serializer |
| No headless CLI tools for Godot | godauto (this project) | 2025 | Still no competing headless CLI tool; MCP servers require editor |
| Manual TileSet terrain | Still manual in editor | Unchanged | godauto's `tileset auto-terrain` remains the only CLI option |

## Open Questions

1. **Does the atlas bounds test require a real texture file?**
   - What we know: Godot's `TileSetAtlasSource` has `has_tiles_outside_texture()` which needs texture dimensions. The existing E2E TileSet tests reference `res://tileset.png` without creating the file and succeed (they only test `load()`, not bounds).
   - What's unclear: Whether Godot computes tile bounds on `load()` when no texture is present, or defers to when the texture is accessed.
   - Recommendation: Create a minimal PNG in the atlas bounds test. Cost is low (a few lines with struct/zlib or Pillow) and eliminates ambiguity. If the test passes without it, the PNG can be removed.

2. **Should pyproject.toml classifiers be updated for Godot version?**
   - What we know: PyPI classifiers have no standard Godot classifier. There is no `Framework :: Godot` trove classifier.
   - What's unclear: Whether any custom classifier or keyword would provide discoverability benefit.
   - Recommendation: Skip classifiers; add "Godot 4.5+" to the PyPI description (pyproject.toml `[project]` description field) and README. No trove classifier exists for Godot.

3. **How should the SKILL.md generator reflect compatibility?**
   - What we know: The generator (`src/gdauto/skill/generator.py`) derives output from the Click command tree. It does not hardcode any Godot version claim. The CLI help text in `src/gdauto/cli.py` contains the root help string.
   - What's unclear: Whether the SKILL.md output should mention "Godot 4.5+" in its header or whether the README claim is sufficient (D-05 says README is the right place).
   - Recommendation: Per D-05, README is the right place for ecosystem positioning. The SKILL.md generator can remain unchanged unless the CLI root help text is updated (which would flow through automatically).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Godot binary | E2E tests (VAL-01, VAL-02, VAL-03) | NOT AVAILABLE | -- | Tests skip via `@pytest.mark.requires_godot`; tests are committed as a contract for when Godot is available |
| Python 3.12+ | All | Available | 3.13.0 | -- |
| pytest | Test runner | Available | 9.0.2 | -- |
| uv | Package manager | Available | -- | -- |
| Pillow | Optional: minimal PNG for atlas test | Available (optional dep) | -- | Use raw struct/zlib PNG generation (no dependency) |

**Missing dependencies with no fallback:**
- None. Godot absence is handled gracefully per D-02.

**Missing dependencies with fallback:**
- Godot binary: tests skip but are committed. When Godot becomes available (CI, another machine), tests execute automatically.

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| E2E test patterns | HIGH | 4 existing E2E tests establish the pattern; conftest.py skip infrastructure proven |
| Atlas bounds risk | MEDIUM | Godot has `has_tiles_outside_texture()` API confirmed, but exact behavior with missing texture files is not binary-verified |
| Round-trip fidelity | HIGH | Phase 5 unit tests verify byte-identical round-trip; E2E confirmation is incremental |
| Ecosystem position | HIGH | Research confirms no competing headless CLI tool exists; multiple sources cross-referenced |
| Documentation changes | HIGH | README structure is well-understood; changes are additive |

## Sources

### Primary (HIGH confidence)
- `tests/e2e/conftest.py` -- Auto-skip infrastructure, godot_backend fixture (read directly)
- `tests/e2e/test_e2e_spriteframes.py` -- Existing SpriteFrames E2E pattern (read directly)
- `tests/e2e/test_e2e_tileset.py` -- Existing TileSet E2E pattern (read directly)
- `tests/e2e/test_e2e_scene.py` -- Existing scene E2E pattern (read directly)
- `src/gdauto/backend.py` -- GodotBackend binary discovery and subprocess management (read directly)
- `.planning/phases/05-format-compatibility-and-backwards-safety/05-VERIFICATION.md` -- Phase 5 verification proving format changes are correct (read directly)
- `.planning/research/SUMMARY.md` -- Ecosystem findings, stack validation (read directly)
- `.planning/research/PITFALLS.md` -- TileSet atlas bounds warning, format migration pitfalls (read directly)
- [TileSetAtlasSource docs (GitHub raw)](https://raw.githubusercontent.com/godotengine/godot-docs/master/classes/class_tilesetatlassource.rst) -- `has_tiles_outside_texture()` and `clear_tiles_outside_texture()` methods confirmed

### Secondary (MEDIUM confidence)
- [GDAI MCP](https://gdaimcp.com/) -- Requires running editor, 163 MCP tools
- [Godot MCP Pro](https://godotengine.org/asset-library/asset/4961) -- Requires running editor, 23 tool categories
- [GDToolkit (Scony/godot-gdscript-toolkit)](https://github.com/Scony/godot-gdscript-toolkit) -- GDScript linter/formatter, v4.2.2
- [godot-ci (abarichello)](https://github.com/abarichello/godot-ci) -- Docker image for CI export
- [godot-mcp-cli](https://github.com/nguyenchiencong/godot-mcp-cli) -- MCP CLI requiring editor

### Tertiary (LOW confidence)
- [Godot issue #112271 (tiles outside texture)](https://github.com/godotengine/godot/issues/98991) -- Referenced in project research as TileSet strictness concern; milestoned for 4.6 but exact resolution status uncertain

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies; existing infrastructure covers everything
- Architecture: HIGH -- extending proven E2E test pattern; documentation changes are additive
- Pitfalls: MEDIUM -- atlas bounds behavior with missing textures is theoretically sound but not binary-verified

**Research date:** 2026-03-29
**Valid until:** 2026-04-30 (60 days; ecosystem positions are slow-moving)
