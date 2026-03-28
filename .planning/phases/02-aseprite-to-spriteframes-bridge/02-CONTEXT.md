# Phase 2: Aseprite-to-SpriteFrames Bridge - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Convert Aseprite sprite sheet JSON exports into valid Godot SpriteFrames .tres resources with full animation support (named animations, per-frame timing, atlas texture regions, loop settings), entirely in Python with no Godot binary required. Also includes sprite sheet splitting (grid-based) and atlas creation (multi-image compositing). Validation against headless Godot is a separate command, not part of the import pipeline.

</domain>

<decisions>
## Implementation Decisions

### Aseprite JSON Handling
- **D-01:** Support both Aseprite JSON export formats: json-hash (keyed by filename) and json-array (ordered list). Detect format automatically from the JSON structure.
- **D-02:** When no animation tags are defined in the Aseprite export, create a single animation named "default" containing all frames. Matches Godot's SpriteFrames convention.
- **D-03:** Lenient validation with warnings: accept any valid JSON with expected top-level keys (frames, meta). Warn on missing optional fields (slices, layers). Consistent with Phase 1 D-04 lenient parser philosophy.
- **D-04:** Full support for trimmed sprite data (spriteSourceSize offsets). Parse spriteSourceSize and sourceSize fields, adjust atlas regions and apply offsets per SPRT-06.
- **D-05:** File input only (no stdin piping). Accept a path to a .json file. Image path resolved relative to the JSON file's directory (matching Aseprite's default export behavior).
- **D-06:** Output path auto-derived from input: replace .json with .tres (character.json -> character.tres). Allow -o/--output override. Follows CLI-METHODOLOGY.md patterns.
- **D-07:** Reference image in place. The generated .tres references the sprite sheet at its current res:// path. User is responsible for placing the image in their Godot project tree. No file copying.

### Animation Conversion
- **D-08:** GCD-based base FPS for variable-duration frames. Compute GCD of all frame durations within each animation, derive base FPS (1000/GCD), set per-frame duration multipliers (frame_ms/GCD). Per-animation GCD, not global.
- **D-09:** Ping-pong animations handled by frame duplication. Duplicate the reversed middle frames in the SpriteFrames animation (A-B-C-B pattern). Godot SpriteFrames has no native ping-pong mode.
- **D-10:** Aseprite repeat count mapping: 0 (infinite) -> loop=true, N>0 -> loop=false. The exact repeat count is lost but the loop intent is preserved.
- **D-11:** Animation speed always derived from actual frame durations. 100ms -> 10 FPS, 200ms -> 5 FPS. All duration multipliers will be 1.0 for uniform-duration animations.

### Atlas and Sprite Split
- **D-12:** Simple shelf/strip packing for sprite create-atlas. Row-based: place sprites left-to-right, next row when full. Deterministic and sufficient for game sprite sheets. Requires Pillow (optional dependency).
- **D-13:** Atlas dimensions default to power-of-two (512, 1024, 2048, 4096) for GPU compatibility. --no-pot flag to allow arbitrary sizes.
- **D-14:** sprite split with no JSON metadata requires --frame-size WxH (e.g., --frame-size 32x32). Grid-based division. Requires Pillow for reading image dimensions.
- **D-15:** All three sprite commands (import-aseprite, split, create-atlas) are in Phase 2 scope per ROADMAP.

### Validation and Error Recovery
- **D-16:** Validation is a separate command (sprite validate), not built into import-aseprite. Keeps import-aseprite Godot-binary-independent. sprite validate loads .tres in headless Godot to verify animations, frame counts, texture references.
- **D-17:** Partial failures generate output with warnings. If 3 of 5 animation tags parse successfully and 2 have issues, output the .tres with valid animations, warn about skipped tags on stderr, exit code 0. User gets partial output they can inspect.
- **D-18:** Import guide is built-in help text on `gdauto sprite import-aseprite --help`. Covers correct Aseprite export settings, common pitfalls, recommended workflow. Always available, no extra artifact.

### Claude's Discretion
- Specific Aseprite export pitfalls to detect and warn about (SPRT-12): researcher identifies the most impactful ones from community forums and Godot docs
- Internal module organization: whether Aseprite parsing, SpriteFrames generation, and atlas packing live in one module or multiple
- Error message wording and fix suggestion text
- Test fixture design for Aseprite JSON samples

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### CLI Architecture
- `CLI-METHODOLOGY.md` -- Click CLI patterns, --json flag implementation, output conventions, error handling standards

### Godot Engine
- `GODOT-RESEARCH.md` -- Aseprite JSON output structure, SpriteFrames .tres format, AtlasTexture sub-resources, animation properties

### Project Requirements
- `.planning/REQUIREMENTS.md` -- Phase 2 requirements: SPRT-01 through SPRT-12

### Phase 1 Foundation
- `.planning/phases/01-foundation-and-cli-infrastructure/01-CONTEXT.md` -- Decisions D-01 through D-20 that carry forward (parser model, output style, CLI conventions)
- `src/gdauto/formats/tres.py` -- GdResource, ExtResource, SubResource: the .tres writer this phase builds on
- `src/gdauto/formats/values.py` -- Rect2, Vector2, ExtResourceRef, SubResourceRef: value types for atlas regions
- `src/gdauto/formats/uid.py` -- UID generation and resource ID generation for new .tres files
- `src/gdauto/commands/sprite.py` -- Stub command group to be populated with import-aseprite, split, create-atlas, validate

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/gdauto/formats/tres.py` -- GdResource dataclass and serialize_tres() for writing valid .tres files. Phase 2 constructs GdResource instances and serializes them.
- `src/gdauto/formats/values.py` -- Rect2 for atlas texture regions, ExtResourceRef/SubResourceRef for resource references, serialize_value() for property values
- `src/gdauto/formats/uid.py` -- generate_uid()/uid_to_text() for .tres UIDs, generate_resource_id() for AtlasTexture sub-resource IDs
- `src/gdauto/output.py` -- emit()/emit_error() for JSON/human output switching, GlobalConfig for flag propagation
- `src/gdauto/errors.py` -- GdautoError hierarchy with to_dict() and fix suggestions

### Established Patterns
- Command groups defined in `src/gdauto/commands/` with `@click.group(invoke_without_command=True)`
- Global flags (-j, -v, -q, --no-color, --godot-path) inherited via Click context
- Error handling: raise GdautoError subclass, emit_error() formats for JSON or human output
- Parse functions return dataclasses; serialize functions accept dataclasses and return strings

### Integration Points
- `src/gdauto/commands/sprite.py` -- existing stub group, add import-aseprite, split, create-atlas, validate as subcommands
- `src/gdauto/backend.py` -- GodotBackend for the sprite validate command (headless Godot validation)
- `pyproject.toml` -- Pillow is already declared as optional dependency under [image] extra

</code_context>

<specifics>
## Specific Ideas

- The core value proposition is the Aseprite-to-SpriteFrames bridge: this is what no other headless tool provides
- Generated .tres files must be loadable by Godot without modification (indistinguishable from editor-generated)
- import-aseprite must work without Godot binary (pure Python file manipulation)
- sprite validate is the only command in this phase that requires Godot binary
- create-atlas and split require Pillow (optional [image] dependency), import-aseprite does not

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 02-aseprite-to-spriteframes-bridge*
*Context gathered: 2026-03-28*
