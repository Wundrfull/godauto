# Pitfalls Research

**Domain:** Godot CLI tooling, Python-based .tscn/.tres generation, Aseprite bridge, TileSet automation
**Researched:** 2026-03-27
**Confidence:** HIGH (most pitfalls verified through official Godot issues, engine docs, and community tools)

## Critical Pitfalls

### Pitfall 1: Generating Invalid Resource IDs That Cause Silent Breakage

**What goes wrong:**
Godot 4 uses string-based resource IDs (e.g., `"AtlasTexture_abc12"` for sub_resources, `"1_ftki2"` for ext_resources) instead of Godot 3's sequential integers. External tools that generate IDs using the wrong format, reuse IDs, or use predictable patterns will produce .tres/.tscn files that either fail to load or cause subtle reference corruption when Godot re-saves them. Godot silently rewrites IDs on save, creating noisy diffs and breaking version control workflows.

**Why it happens:**
The ID generation algorithm is not formally documented. Developers copy-paste from examples, use sequential counters (like `"1"`, `"2"`, `"3"`), or hardcode IDs without understanding Godot 4's alphanumeric convention. The format changed from integers (3.x format=2) to strings (4.x format=3), and many tutorials and parsers still show the old format.

**How to avoid:**
- Generate IDs using the `Type_xxxxx` pattern for sub_resources where `xxxxx` is a random 5-character alphanumeric string (lowercase + digits)
- Generate ext_resource IDs using `N_xxxxx` pattern where N is a sequential number and xxxxx is random
- Use Python's `secrets` or `random` module to generate the alphanumeric suffix; never use sequential or predictable IDs
- Write a dedicated `generate_resource_id(prefix)` function used everywhere, never inline ID creation
- Add a unit test that generates 10,000 IDs and asserts zero collisions
- Add an E2E test that loads every generated .tres in Godot, saves it, and verifies the diff is empty (Godot did not rewrite the IDs)

**Warning signs:**
- Godot rewrites your .tres files on open/save (file changes without user edits)
- `load()` succeeds but references between sub_resources are broken
- Git diffs show ID changes in files you did not modify

**Phase to address:**
Phase 1 (core file format library). The ID generator is foundational; every other feature depends on it.

---

### Pitfall 2: Ignoring Godot 4.4+ UID System for Generated Resources

**What goes wrong:**
Godot 4.0+ uses 64-bit UIDs (formatted as `uid://xxxxxxxxxxxxx` in base36) stored in file headers and companion `.uid` files. Externally generated .tres/.tscn files that omit the `uid=` field from the header still load, but Godot assigns them a UID on first open. This breaks `uid://` references from other files, causes UID collisions if the same file is generated on multiple machines, and creates phantom diffs in version control. Starting with Godot 4.4, scripts and shaders also get companion `.uid` files.

**Why it happens:**
UIDs feel optional because files load without them. The UID system is designed for Godot's internal use and external tools rarely consider it. The base36 encoding of a 64-bit CSPRNG value is not standard and easy to get wrong.

**How to avoid:**
- Always include `uid="uid://..."` in the `[gd_resource]` or `[gd_scene]` header
- Generate UIDs using a CSPRNG (Python's `secrets.token_bytes(8)`) encoded in base36 matching Godot's format
- Never reuse UIDs across different resource paths
- Never create human-readable or mnemonic UIDs
- Store generated UIDs deterministically (hash of file path + project name) so regenerating the same file produces the same UID
- Test: generate a .tres, open in Godot, close, verify the UID in the header is unchanged

**Warning signs:**
- Godot adds or changes the `uid=` field when you open a generated .tres
- `uid://` references in other .tscn files resolve to the wrong resource
- Merge conflicts in UID values

**Phase to address:**
Phase 1 (core file format library). UID generation must be baked into the format writer from day one.

---

### Pitfall 3: Botching Aseprite Duration-to-SpriteFrames Speed Conversion

**What goes wrong:**
Aseprite stores per-frame durations in milliseconds (e.g., 100ms, 150ms, 200ms). Godot's SpriteFrames uses a combination of animation-level FPS (`speed`) and per-frame duration multipliers (a float defaulting to 1.0). Naive conversion (dividing 1000 by milliseconds to get FPS) only works when all frames in an animation have the same duration. Mixed-duration animations (common in hand-drawn pixel art: idle holds, attack anticipation frames) require computing a base FPS and then calculating per-frame duration multipliers. Getting this wrong produces animations that play at the wrong speed or lose their timing character entirely.

**Why it happens:**
Simple animations (uniform 100ms frames = 10 FPS) work correctly with naive conversion, so the bug is not caught until an artist provides animations with variable frame timing. Existing Godot plugins (Aseprite Wizard, Aseprite Animation Importer) handle this in GDScript but their logic is not obvious from the Aseprite JSON alone.

**How to avoid:**
- Compute the GCD (greatest common divisor) of all frame durations in each animation tag
- Set the animation's `speed` to `1000 / GCD` FPS
- Set each frame's `duration` multiplier to `frame_ms / GCD`
- Example: frames at [100ms, 100ms, 200ms, 100ms] -> GCD=100, speed=10.0 FPS, durations=[1.0, 1.0, 2.0, 1.0]
- Alternative approach: use a common base FPS (e.g., the fastest frame's rate) and compute multipliers relative to it
- Test with: uniform timing, variable timing, very slow frames (500ms+), very fast frames (16ms), and single-frame animations

**Warning signs:**
- Animations play too fast or too slow compared to Aseprite preview
- "Hold" frames (long duration) play the same speed as action frames
- Animation total duration does not match Aseprite's timeline

**Phase to address:**
Phase 2 (Aseprite bridge). Must be correct before the sprite import command ships.

---

### Pitfall 4: Mishandling Aseprite Trimmed Sprites and Source Size Offsets

**What goes wrong:**
When Aseprite exports with trimming enabled (`--trim` or Trim Cels/Trim Sprite in GUI), the JSON metadata includes `trimmed: true` and a `spriteSourceSize` field with x/y offsets indicating where the trimmed frame sits within the original canvas. If the tool ignores these offsets and uses only the `frame` coordinates for atlas regions, sprites will be misaligned: characters shift position between frames, idle animations "jitter," and attack animations have wrong hitbox alignment.

**Why it happens:**
Untrimmed exports (the simpler case) work fine with just the `frame` field. Many tutorials only show untrimmed examples. The `spriteSourceSize` field looks optional until you test with actual artist-exported sheets that use trimming to save atlas space.

**How to avoid:**
- Always check the `trimmed` field in Aseprite JSON
- When `trimmed` is true, use `spriteSourceSize.x` and `spriteSourceSize.y` as the frame offset
- Store the offset in the generated SpriteFrames (Godot's AtlasTexture supports `margin` for this purpose, using `Rect2` with the offset applied)
- Test with: untrimmed sheets, trim-sprite sheets, trim-cels sheets (each frame trimmed differently), and sheets with padding
- Include a fixture set of trimmed and untrimmed exports in the test suite

**Warning signs:**
- Sprites "jump" or shift between animation frames
- Characters appear offset from their collision shapes
- Works perfectly with untrimmed sheets but breaks with artist-provided trimmed sheets

**Phase to address:**
Phase 2 (Aseprite bridge). Must handle both trimmed and untrimmed from the start.

---

### Pitfall 5: Headless Godot Import Race Condition Breaking E2E Tests

**What goes wrong:**
Godot's `--headless --import` has a well-documented timing bug: using `--quit` or `--quit-after 1` causes the process to exit before the import scan thread completes. Resources appear unimported, the `.godot/imported/` directory is incomplete, and subsequent headless operations (export, script execution) fail with "Failed loading resource" errors. This affects all CI pipelines and E2E test harnesses.

**Why it happens:**
Godot's import system uses deferred calls (`call_deferred()`) that require at least one additional frame to execute. The `--quit` flag exits before those deferred calls run. This has been an open issue since Godot 4.0 (issue #77508) and remains problematic across 4.x versions.

**How to avoid:**
- Always use `--quit-after 2` (or higher) instead of `--quit` when running `--import`
- Better: omit `--quit` entirely and use a timeout wrapper that kills the process after a delay (e.g., 30 seconds)
- In `godot_backend.py`, implement retry logic for import: run import, check `.godot/imported/` for expected files, retry if incomplete
- For E2E tests, run a single import step in the test fixture setup (once per session, not per test)
- Never use `--editor --headless --quit` as a substitute for `--import`; it is less reliable
- Cache the `.godot` directory between CI runs when possible

**Warning signs:**
- E2E tests fail intermittently with "Failed loading resource"
- `.godot/imported/` directory is smaller than expected
- Tests pass locally (where the editor has been opened) but fail in CI (fresh clone)

**Phase to address:**
Phase 1 (backend wrapper). The `godot_backend.py` must handle this from the start since E2E tests depend on it.

---

### Pitfall 6: Building a Regex-Based Parser Instead of a State Machine

**What goes wrong:**
The Godot .tscn/.tres format looks deceptively simple (bracket sections with key=value pairs), tempting developers to parse it with regex. This breaks on: multi-line values (arrays, dictionaries spanning lines), nested data structures (animation frames contain sub-objects), string values containing brackets or equals signs, escaped characters, and inline GDScript expressions in resource values. The parser produces corrupt output, silently drops data, or crashes on real-world files.

**Why it happens:**
Simple .tres files (a basic texture resource) parse fine with regex. The format is line-oriented enough that a few patterns seem to cover it. But SpriteFrames and TileSet resources contain complex nested structures (arrays of dictionaries of arrays) that span dozens of lines. The godot_parser Python library explicitly warns it was built via "visual inspection" and reverse engineering because the format's edge cases are not fully documented.

**How to avoid:**
- Implement a proper tokenizer + state machine parser
- Define clear states: HEADER, SECTION_HEADER, KEY_VALUE, MULTILINE_VALUE, NESTED_STRUCTURE
- Track bracket nesting depth for array/dictionary values
- Handle string quoting rules (double quotes, `&"string_name"` syntax for StringName)
- Handle Godot-specific value types: `Vector2(x, y)`, `Rect2(x, y, w, h)`, `Color(r, g, b, a)`, `ExtResource("id")`, `SubResource("id")`
- Do NOT depend on godot_parser: it targets Godot 3.x format=2, was last updated September 2023, and lacks format=3 features like string IDs and UIDs
- Build a comprehensive test fixture set by creating resources in Godot and saving them as .tres, then verifying round-trip parsing

**Warning signs:**
- Parser works on simple resources but fails on SpriteFrames or TileSet .tres files
- Multi-line array values get truncated
- Generated files cause Godot to report parse errors or silently drop properties

**Phase to address:**
Phase 1 (core format library). The parser/generator is the foundation; everything else is built on it.

---

### Pitfall 7: Getting TileSet Terrain Peering Bit Mappings Wrong

**What goes wrong:**
The 47-tile blob layout has a specific mapping between grid positions and peering bit configurations. If the mapping table is wrong (even one tile), Godot's terrain painting will produce visual glitches: wrong corners, missing edges, "hole" tiles appearing where they should not. Because there are 47 unique configurations for 8-bit corner+side matching, manual verification is impractical and errors only appear in specific neighbor configurations that may not be tested.

**Why it happens:**
There is no official Godot document specifying "grid position (row, col) maps to these peering bits" for standard layouts. The mapping is reverse-engineered from community tilesets, Godot 3.x autotile documentation (which used a different system), and tools like TileBitTools and Tilesetter. Different tileset artists use slightly different grid arrangements, and the RPG Maker layout differs from the "standard" blob layout.

**How to avoid:**
- Use TileBitTools' template data as a reference (it is archived but the mapping data is valid)
- Build a lookup table (not computed logic) that maps `(row, col)` to a set of peering bits for each supported layout
- Support at minimum: 47-tile blob (corner+side), 16-tile minimal (side-only), RPG Maker A2
- Test each layout by: generating a TileSet .tres, loading it in Godot, painting a test pattern (solid rectangle, L-shape, single tile, line), and visually verifying all transitions
- Include a `--layout` flag so users explicitly specify which convention their tileset follows (never auto-detect without a fallback)
- Allow manual peering bit override via a JSON mapping file for non-standard layouts

**Warning signs:**
- Corner tiles appear where edge tiles should be (or vice versa)
- Auto-painted terrain has "holes" or incorrect transitions at specific configurations
- Works for simple shapes (straight walls) but fails at T-junctions or diagonal corners

**Phase to address:**
Phase 3 (TileSet automation). Requires careful verification with multiple tileset layouts before shipping.

---

### Pitfall 8: Assuming Godot File Format Stability Across Minor Versions

**What goes wrong:**
While Godot 4.x uses `format=3` throughout, the serialization of specific resource types changes between minor versions. Godot 4.3 introduced Base64 encoding for PackedByteArray (previously inline), and Godot 4.4 added companion `.uid` files for scripts. TileSet serialization structure has changed as new features were added (e.g., physics layers, navigation layers, custom data layers). A tool that hardcodes the output format based on one Godot version will produce files that older versions cannot load or that newer versions silently upgrade (creating diff noise).

**Why it happens:**
`format=3` looks like a stable version number, suggesting all 4.x versions use the same format. In practice, `format=3` is a container format; the resource-type-specific serialization within it evolves. The Godot documentation does not maintain a changelog of per-type format changes.

**How to avoid:**
- Target a minimum Godot version (4.5+ per PROJECT.md) and test against that version specifically
- For each resource type gdauto generates (SpriteFrames, TileSet), create a "golden file" test: generate the .tres, load in the target Godot version, save from Godot, and compare
- Avoid using features only available in newer versions unless explicitly enabled by a `--godot-version` flag
- Keep the format writer modular so resource-type-specific serialization can be updated independently
- Document which Godot versions each generated format is compatible with

**Warning signs:**
- Generated files load in your Godot version but not in a user's older version
- Godot silently rewrites or upgrades the file on load
- Users report "invalid resource" errors on versions you did not test against

**Phase to address:**
Phase 1 (core format library), with ongoing validation in every subsequent phase.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using godot_parser instead of building own parser | Saves 2-3 weeks of parser development | Library targets format=2 (Godot 3.x), unmaintained since Sept 2023, missing UID support, string IDs, and format=3 features | Never for this project. The format gap is too large. |
| Hardcoding SpriteFrames .tres output as string templates | Ship Aseprite bridge fast | Cannot handle varying numbers of animations, frames, or sub_resources; breaks on edge cases; unmaintainable | MVP/prototype only; replace with structured writer before v1.0 |
| Skipping UID generation (let Godot assign UIDs) | Simpler code, fewer dependencies | Version control noise, UID collisions in team workflows, breaks uid:// references from other files | Never for files intended to be committed to a project |
| Using subprocess.run without timeout | Simpler backend code | Godot can hang indefinitely on import or broken projects; CI pipelines stuck forever | Never. Always use timeout parameter. |
| Flattening per-frame durations to uniform FPS | Simpler animation conversion | Loses artist-intended timing; animations feel "wrong" but subtly, making it hard to diagnose | Only if explicitly documented as --uniform-fps mode |
| Testing only with synthetic .tres fixtures | Fast test suite, no Godot dependency | Real Godot files have edge cases (ordering, whitespace, comments) that synthetic fixtures miss | Unit tests only; E2E tests must use real Godot-generated files |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Godot headless binary | Assuming `godot` is on PATH and is the right version | Use `shutil.which("godot")` with fallback to common install locations; validate version with `--version` output; support `GODOT_BINARY` environment variable override |
| Godot `--import` | Using `--quit` flag, causing premature exit before import completes | Use `--quit-after 2` or a timeout wrapper; verify import success by checking `.godot/imported/` contents |
| Godot `--export-release` | Running export on a project that has never been opened in the editor | Run `--headless --import` first (with `--quit-after` delay); ensure `.godot/` directory exists with import cache |
| Aseprite JSON | Assuming `frameTags` always exists in JSON output | Aseprite JSON omits `frameTags` (as empty array or missing key) when no tags are defined; create a single "default" animation containing all frames |
| Aseprite JSON | Assuming `"direction"` is always `"forward"` | Handle all four directions: `"forward"`, `"reverse"`, `"pingpong"`, `"pingpong_reverse"`; for ping-pong, duplicate frames in reversed order in the SpriteFrames output |
| Aseprite JSON | Hardcoding frame filename patterns | Filenames vary by export settings: `"sprite 0.ase"`, `"sprite (Tag) 0.ase"`, `"Layer 1 (Tag) 0.ase"`; parse by array index, not filename |
| TileSet generation | Assuming square tiles (same width and height) | Support rectangular tiles; tile_size is `Vector2i(w, h)` not a single int |
| File paths in .tres | Using OS-native paths (backslash on Windows) | Godot always uses `res://` paths with forward slashes; generated resources must use Godot's path convention |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading entire sprite sheet image into memory for atlas calculations | High memory usage, slow processing | Only read image dimensions (PIL/Pillow `Image.open().size`), not pixel data; atlas region math is pure coordinate arithmetic | Sprite sheets larger than 4096x4096 (common for animation-heavy games) |
| Spawning a new Godot subprocess per command in batch operations | Each invocation takes 2-5 seconds for startup; batch of 50 tilesets takes 4 minutes | Batch operations into a single GDScript that processes all items; or use pure-Python file generation (no Godot needed) | Any batch operation over ~10 items |
| Re-parsing .tres files for each sub-command in a pipeline | Redundant I/O and parsing overhead | Parse once, pass the in-memory representation through the pipeline; only serialize at the end | Complex pipelines (inspect + modify + validate) |
| Running E2E tests that each launch a separate Godot instance | Test suite takes 10+ minutes | Use pytest session-scoped fixtures for Godot import; batch validation into a single Godot script that checks all generated files | Test suite with more than 20 E2E tests |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Passing user-supplied file paths directly to subprocess args | Path traversal; on Windows, command injection via filenames with special characters | Validate all paths with `pathlib.Path.resolve()`; reject paths containing `..` or shell metacharacters; use list-form subprocess (never `shell=True`) |
| Loading .tres files that contain embedded GDScript | .tres files can contain inline scripts; a malicious .tres could execute code when loaded by Godot | gdauto's Python parser never executes content; but warn users if a .tres contains script blocks; document that `resource inspect` is read-only |
| Trusting Aseprite JSON file paths without validation | JSON `meta.image` field could reference paths outside the project directory | Resolve image paths relative to the JSON file's directory; reject absolute paths and paths with `..` |
| Running `godot --script` with user-supplied script paths | Arbitrary GDScript execution | Only run scripts from gdauto's own template directory; never pass user-supplied paths to `--script` |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Failing silently when Aseprite JSON has no frameTags | User gets a .tres with zero animations; no error message | Detect missing/empty frameTags, create a "default" animation from all frames, and print a warning: "No animation tags found; created 'default' animation with all N frames" |
| Producing valid .tres that Godot loads but looks wrong | User cannot tell if the tool worked until they open the editor | Add a `--validate` flag that loads the generated file in headless Godot and confirms it parses without errors; print summary: "Generated SpriteFrames with 3 animations (idle: 4 frames, walk: 6 frames, attack: 5 frames)" |
| Error messages that say "failed" without context | User cannot diagnose the problem | Include: what was attempted, what went wrong, what file/line, and a suggested fix. Example: "Failed to parse sprite sheet: expected 8 columns of 32px tiles but image width (250px) is not divisible by tile width (32px). Check your --tile-size argument." |
| Requiring Godot binary for operations that do not need it | Users who only want Aseprite-to-SpriteFrames conversion must install Godot | Clearly separate pure-Python commands (sprite, tileset, resource inspect) from headless commands (export, import, validate); only require Godot binary for the latter |
| Not showing progress for long operations | User thinks the tool is hung during batch TileSet generation | Use Click's `click.progressbar()` for batch operations; for headless Godot operations, stream stderr in real time |
| Overwriting existing files without warning | User loses their manually-edited TileSet | Default to refusing to overwrite; require `--force` flag; or write to a new file and let user diff/merge |

## "Looks Done But Isn't" Checklist

- [ ] **SpriteFrames generation:** Often missing per-frame duration multipliers when frames have variable timing; verify by comparing total animation duration against Aseprite's timeline
- [ ] **SpriteFrames generation:** Often missing `trimmed` sprite offset handling; verify with a trimmed export where frames have different trim rectangles
- [ ] **SpriteFrames generation:** Often missing ping-pong direction support; verify by exporting an Aseprite file with `"direction": "pingpong"` tag
- [ ] **SpriteFrames generation:** Often missing the `loop` property (defaults to true); verify with Aseprite's repeat-count feature (repeat=1 means no loop)
- [ ] **TileSet generation:** Often missing physics layer assignment; verify that collision shapes are present by checking the generated .tres for physics_layer_0 entries
- [ ] **TileSet generation:** Often has wrong peering bits for corner tiles in 47-tile blob; verify by painting an L-shaped area in Godot and checking all four inner corners
- [ ] **File format:** Often missing `load_steps` count or setting it wrong; verify it equals (ext_resource count + sub_resource count + 1)
- [ ] **File format:** Often missing `uid=` in header; verify by opening in Godot, closing without changes, and checking that the header was not modified
- [ ] **File format:** Often using wrong line endings; Godot expects LF (Unix), not CRLF (Windows); verify on Windows machines
- [ ] **CLI behavior:** Often missing `--json` output on error paths (only success is JSON); verify by triggering each error condition with `--json` flag
- [ ] **Backend wrapper:** Often missing timeout on subprocess; verify by pointing at a non-existent project path and confirming the process does not hang

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong resource IDs | LOW | Regenerate the .tres file; Godot will also fix IDs on re-save but this creates VCS noise |
| Missing UIDs | LOW | Open generated files in Godot; it assigns UIDs automatically. But commit the UID changes to avoid future noise |
| Wrong animation timing | LOW | Regenerate with corrected conversion formula; no downstream damage since SpriteFrames are self-contained |
| Trimmed sprite misalignment | LOW | Regenerate with offset handling; may need to re-test scenes using the SpriteFrames |
| Regex parser hitting edge case | HIGH | Must rewrite parser as state machine; all downstream format generation code may need adjustment since internal data model changes |
| Wrong peering bit mapping | MEDIUM | Fix the lookup table and regenerate; but users may have manually edited the TileSet after initial generation, losing their changes |
| Headless import race condition | LOW | Add retry logic to backend wrapper; re-run affected E2E tests |
| Format incompatibility with older Godot | MEDIUM | Add version-conditional output logic; re-test against target versions; communicate minimum version requirements |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Invalid resource IDs | Phase 1: Core format library | E2E test: generate .tres, load in Godot, save, verify no ID changes in diff |
| Missing UIDs | Phase 1: Core format library | E2E test: generate .tres, open/close in Godot, verify header unchanged |
| Regex-based parser | Phase 1: Core format library | Unit test: parse Godot-generated SpriteFrames and TileSet .tres files with complex nested structures; round-trip test |
| Format version instability | Phase 1: Core format library | Golden file tests against minimum supported Godot version (4.5+) |
| Duration conversion errors | Phase 2: Aseprite bridge | Unit test: variable-timing animations match expected FPS + duration multipliers; E2E: compare animation playback duration |
| Trimmed sprite offsets | Phase 2: Aseprite bridge | Unit test with trimmed fixture; E2E: visual spot-check of frame alignment |
| Ping-pong direction | Phase 2: Aseprite bridge | Unit test: verify frame order for all four Aseprite direction types |
| Missing frameTags handling | Phase 2: Aseprite bridge | Unit test: Aseprite JSON with empty/missing frameTags produces single default animation |
| Wrong peering bit mapping | Phase 3: TileSet automation | E2E test: generate TileSet, paint terrain in Godot via GDScript, capture tile selections, verify against expected |
| Headless import race condition | Phase 1: Backend wrapper | E2E test: import on a fresh project (no .godot dir), verify all resources present in imported/ |
| File overwrite without warning | Phase 1: CLI framework | Unit test: verify commands refuse to overwrite without --force |

## Sources

- [godotengine/godot#77508: Import fails with --quit](https://github.com/godotengine/godot/issues/77508) -- headless import race condition
- [godotengine/godot#69511: CLI export reimport failure](https://github.com/godotengine/godot/issues/69511) -- export without prior import
- [godotengine/godot#71521: Headless export on unopened project](https://github.com/godotengine/godot/issues/71521) -- first-run import cache issue
- [godotengine/godot#95287: Headless export without .godot freezes](https://github.com/godotengine/godot/issues/95287) -- Godot 4.3 freeze on missing .godot
- [godotengine/godot-proposals#7670: Terrain matching algorithm](https://github.com/godotengine/godot-proposals/issues/7670) -- terrain peering bit algorithm failures
- [godotengine/godot#77172: ExtResource IDs change after saving](https://github.com/godotengine/godot/issues/77172) -- ID rewriting on save
- [godotengine/godot#89909: get_terrain_peering_bit returns error](https://github.com/godotengine/godot/issues/89909) -- peering bit API issues
- [UID changes in Godot 4.4](https://godotengine.org/article/uid-changes-coming-to-godot-4-4/) -- UID system evolution
- [stevearc/godot_parser](https://github.com/stevearc/godot_parser) -- Python parser (format=2 only, unmaintained since Sept 2023)
- [dandeliondino/tile_bit_tools](https://github.com/dandeliondino/tile_bit_tools) -- TileBitTools (archived, but mapping data is reference material)
- [TSCN file format docs (4.4)](https://docs.godotengine.org/en/4.4/contributing/development/file_formats/tscn.html) -- official format documentation
- [Aseprite Wizard](https://github.com/viniciusgerevini/godot-aseprite-wizard) -- reference implementation for Aseprite-to-SpriteFrames conversion
- [Click exception handling](https://click.palletsprojects.com/en/stable/exceptions/) -- Click exit code and error handling patterns
- [Aseprite spriteSourceSize issue #2600](https://github.com/aseprite/aseprite/issues/2600) -- trimmed sprite JSON bugs
- [Portponky/better-terrain](https://github.com/Portponky/better-terrain) -- alternative terrain system documenting native system's limitations

---
*Pitfalls research for: Godot CLI tooling (gdauto)*
*Researched: 2026-03-27*
