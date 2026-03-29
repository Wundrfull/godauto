# Architecture Research: Godot 4.6/4.6.1 Compatibility Audit

**Domain:** Godot 4.6.x engine changes impacting gdauto v1.0 architecture
**Researched:** 2026-03-28
**Overall Confidence:** HIGH (verified against Godot source code, official docs, PRs)

## Executive Summary

Godot 4.6 introduces three changes that directly affect gdauto's file format layer, one change that affects the backend layer, and zero changes to the CLI flag interface. The changes range from trivial (load_steps removal) to moderate (unique_id node attribute, format=4 awareness). None require architectural rewrites; all integrate cleanly into the existing state-machine parser and dataclass models.

The critical finding: **format=3 remains the default for most files**. Godot 4.6 can write format=4 headers, but only when a file contains PackedVector4Array or base64-encoded PackedByteArray data. Since gdauto generates SpriteFrames, TileSets, and simple scenes (none of which use PackedVector4Array or large PackedByteArray), our generated files will still use format=3. However, our parser must **accept** format=4 files to maintain round-trip fidelity on user projects that contain these types.

---

## Q1: Did the .tscn/.tres format version change from format=3?

### Answer: Yes, conditionally. FORMAT_VERSION is now 4, with FORMAT_VERSION_COMPAT at 3.

**Confidence:** HIGH (verified in Godot source: `resource_format_text.h`)

**What changed (introduced in Godot 4.3, still current in 4.6):**

```
// resource_format_text.h (current master, matches 4.6)
FORMAT_VERSION = 4
FORMAT_VERSION_COMPAT = 3
```

**When Godot writes format=4 vs format=3:**
- `format=4`: Written when the file contains PackedVector4Array values OR base64-encoded PackedByteArray (large byte arrays)
- `format=3`: Written for everything else (the vast majority of files)

**Format=4 features:**
1. `PackedVector4Array(x1, y1, z1, w1, x2, y2, z2, w2, ...)` constructor (flat float list)
2. Base64-encoded PackedByteArray, likely serialized as a different constructor form

**Impact on gdauto parser:**

| Component | File | Current Behavior | Required Change |
|-----------|------|------------------|-----------------|
| `parse_tres()` | `formats/tres.py:148` | `format=int(header.attrs.get("format", "3"))` | Accept both 3 and 4; no code change needed (already reads as int) |
| `parse_tscn()` | `formats/tscn.py:180` | `format=int(header.attrs.get("format", "3"))` | Same; already handles any integer |
| `_build_tres_from_model()` | `formats/tres.py:190` | Writes `format={resource.format}` | Preserves original format value; correct |
| `_build_tscn_from_model()` | `formats/tscn.py:223` | Writes `format={scene.format}` | Preserves original format value; correct |
| Value parser | `formats/values.py` | No PackedVector4Array handler | **ADD**: PackedVector4Array parser |

**What to build:**
- Add `PackedVector4Array` to the value parser's constructor dispatch (`values.py:_parse_constructor`)
- Add `PackedByteArrayB64` or base64-encoded `PackedByteArray` parsing if Godot uses a distinct constructor name (needs verification with actual 4.6 files)
- Our generated files always use format=3 (we never produce PackedVector4Array or large PackedByteArray), so serialization code needs no changes

**Second change: load_steps removed from output (PR #103352, Godot 4.6).**

Godot 4.6 no longer writes `load_steps=N` in file headers. When reading, the parser still accepts and ignores the field.

| File Header (4.5) | File Header (4.6) |
|--------------------|--------------------|
| `[gd_resource type="SpriteFrames" load_steps=15 format=3 uid="uid://abc"]` | `[gd_resource type="SpriteFrames" format=3 uid="uid://abc"]` |

**Impact on gdauto:**

| Component | File | Impact | Action |
|-----------|------|--------|--------|
| `parse_tres()` | `formats/tres.py:142-143` | Reads load_steps from header attrs; None if absent | No change needed (already handles None) |
| `parse_tscn()` | `formats/tscn.py:176-177` | Same pattern | No change needed |
| `_build_tres_from_model()` | `formats/tres.py:188-189` | Conditionally writes load_steps | **CHANGE**: Make load_steps omission the default for 4.6+ |
| `_build_tscn_from_model()` | `formats/tscn.py:221-222` | Conditionally writes load_steps | **CHANGE**: Same |
| `build_spriteframes()` | `sprite/spriteframes.py:191` | Sets `load_steps=1 + len(all_subs) + 1` | **CHANGE**: Set to None for 4.6+ output |
| Round-trip serialization | `formats/common.py:291-344` | Uses raw_line; preserves whatever was in original | No change (correct: preserves original) |

**Backwards compatibility decision:** When generating new files, omit `load_steps` by default (matching 4.6 behavior). When round-tripping existing files, preserve whatever was there (already handled by raw_line preservation). Godot 4.5 accepts files without `load_steps` (it was always optional for the engine), so omitting it is safe for 4.5+ compatibility.

---

## Q2: Did UID format or generation change?

### Answer: No changes between 4.5 and 4.6.

**Confidence:** HIGH (verified against Godot source `core/io/resource_uid.cpp`)

**Current Godot UID encoding (unchanged since 4.0, with a minor 4.4 edge case fix):**
- Base-34 encoding using characters: `a-y` (25) + `0-8` (9) = 34
- Off-by-one bug means 'z' and '9' are never used (GH-83843, cannot fix without breaking compat)
- 63-bit maximum value: `(1 << 63) - 1`
- Text format: `uid://<base34-encoded-value>`

**Our implementation (`formats/uid.py`) matches exactly:**
```python
CHARS = "abcdefghijklmnopqrstuvwxy012345678"  # 34 chars
BASE = len(CHARS)  # 34
MAX_UID = (1 << 63) - 1  # 63-bit maximum
```

**One edge case fixed in Godot 4.4 (PR #100976):** The value 0 now encodes as `uid://a` instead of `uid://`. Our `uid_to_text()` already handles this correctly (the do/while loop always produces at least one character).

**Verification against Godot source:**

| Aspect | Godot Source | Our uid.py | Match? |
|--------|-------------|------------|--------|
| Character set | `a-y, 0-8` | `CHARS = "abcdefghijklmnopqrstuvwxy012345678"` | YES |
| Base | 34 (char_count + ('9'-'0') = 25+9) | `BASE = 34` | YES |
| Max value | `0x7FFFFFFFFFFFFFFF` | `(1 << 63) - 1` | YES |
| Encoding direction | LSB first, prepend to string | LSB first, prepend | YES |
| Zero encoding | `uid://a` (post-4.4 fix) | Produces `uid://a` (correct) | YES |
| `.uid` file format | `uid://...\n` | `uid_text + "\n"` | YES |

**No changes needed to `formats/uid.py`.**

The Godot 4.4 UID generalization (`.uid` sidecar files for .gd, .gdshader, etc.) does not affect gdauto because we only generate .tres/.tscn files, which store UIDs inline in their headers. We already write .uid companion files via `write_uid_file()` and this behavior is unchanged.

---

## Q3: Did project.godot structure change?

### Answer: config_version remains 5. No structural changes.

**Confidence:** HIGH (verified in Godot source `core/config/project_settings.h`)

```cpp
// project_settings.h (current master, matches 4.6)
static const int CONFIG_VERSION = 5;
```

The `config_version=5` value has been stable across all of Godot 4.x. Project.godot files from 4.5 and 4.6 use the same structure.

**New project settings may exist** (Jolt Physics defaults for new projects, D3D12 default on Windows), but these are key-value pairs under existing sections. Our `project_cfg.py` parser reads arbitrary sections and key-value pairs, so new settings are automatically handled.

**Impact on gdauto:**

| Component | File | Impact |
|-----------|------|--------|
| `parse_project_config()` | `formats/project_cfg.py` | No change needed |
| `serialize_project_config()` | `formats/project_cfg.py` | No change needed |
| `project info` command | `commands/project.py` | No change needed |
| `project validate` command | `commands/project.py` | No change needed |

**No changes needed to project.godot handling.**

---

## Q4: Did headless binary flags change?

### Answer: No changes to the flags gdauto uses.

**Confidence:** HIGH (verified against Godot 4.6 command line docs)

**All flags used by gdauto remain unchanged:**

| Flag | gdauto Usage | 4.6 Status | Notes |
|------|-------------|------------|-------|
| `--headless` | `GodotBackend.run()` | Unchanged | Still `--display-driver headless --audio-driver Dummy` |
| `--version` | `GodotBackend._check_version()` | Unchanged | Still outputs version string |
| `--import` | `GodotBackend.import_resources()` | Unchanged | Still implies `--editor` and `--quit` |
| `--quit-after N` | `GodotBackend.import_resources()` | Unchanged | Still available, still needed for import timing |
| `--export-release` | `export_project()` | Unchanged | Implies `--import` |
| `--export-debug` | `export_project()` | Unchanged | Implies `--import` |
| `--export-pack` | `export_project()` | Unchanged | Implies `--import` |
| `--check-only` | `GodotBackend.check_only()` | Unchanged | Extended availability only |
| `--path` | `GodotBackend.run()` | Unchanged | Project directory specification |

**Notable 4.6 headless improvements (no gdauto impact):**
- Fix for hang when importing Blender files in headless mode
- `--headless` now disables embedded mode in the main instance argument list

**One behavior note:** Godot 4.6 added `--import` implying `--quit` (this was already the case in 4.5). Our `import_resources()` method uses `--import --quit-after N` which is redundant but harmless (both flags work together).

**Impact on gdauto:**

| Component | File | Impact |
|-----------|------|--------|
| `GodotBackend.run()` | `backend.py` | No change needed |
| `GodotBackend.import_resources()` | `backend.py` | No change needed |
| `GodotBackend.check_only()` | `backend.py` | No change needed |
| `export_project()` | `export/pipeline.py` | No change needed |
| Version validation | `backend.py:82-115` | Already accepts 4.6 (checks >= 4.5) |

**No changes needed to the backend layer.**

---

## Q5: How should we implement backwards compatibility?

### Recommendation: Version-detect at generation time, not at parse time.

**Confidence:** HIGH (design recommendation based on findings)

### Strategy: "Parse anything, generate current"

**Parsing (reading files):** Accept format=3 and format=4 indiscriminately. The parser should not care about the format version because:
1. Our state-machine parser already handles both (the section structure is identical)
2. The only difference in format=4 is new value types (PackedVector4Array, base64 PackedByteArray)
3. Round-trip fidelity is maintained by raw_line/raw_properties preservation regardless of format version

**Generation (writing files):** Default to 4.6 conventions:
- Omit `load_steps` from generated file headers
- Write `format=3` (we never produce PackedVector4Array)
- Include `unique_id` on nodes if present in input (preserve on round-trip)

**Version detection in backend:** The existing `_check_version()` method in `backend.py` already extracts major.minor from the Godot binary. Expose this as a property for use by generators:

```python
# backend.py (new property)
@property
def version_tuple(self) -> tuple[int, int] | None:
    """Return (major, minor) if version has been checked, else None."""
    if self._version is None:
        return None
    match = _VERSION_RE.search(self._version)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    return None
```

**Where to use version detection:**

| Decision | Where | Logic |
|----------|-------|-------|
| Include load_steps? | `spriteframes.py`, `tileset/builder.py`, `scene/builder.py` | Omit always (safe for 4.5+, matches 4.6 behavior) |
| Include unique_id? | `scene/builder.py` (if creating scenes) | Only when round-tripping 4.6 files that already have them |
| format=3 or format=4? | All generators | Always format=3 (we never use format=4 features) |

**Why NOT detect at parse time:** The parser's job is to faithfully represent the file content, not to make version-dependent decisions. A file with `format=4` and `unique_id` attributes parses the same way as `format=3` without them. The extra attributes are simply additional header fields that our generic attr parser already handles.

---

## Q6: Cleanest approach for format differences without breaking round-trip fidelity?

### Answer: The existing architecture already handles this correctly.

**Confidence:** HIGH (verified against code)

**Our round-trip strategy (already implemented):**

1. **Raw preservation path** (parse then re-serialize unmodified files):
   - `common.py:serialize_sections()` uses `raw_line` for headers and `raw_properties` for values
   - If a 4.6 file has no `load_steps` and includes `unique_id`, the raw lines preserve this exactly
   - If a 4.5 file has `load_steps`, it stays in the output
   - Zero changes needed for this path

2. **Model-to-text path** (generate new files from data):
   - `_build_tres_from_model()` and `_build_tscn_from_model()` construct headers from data fields
   - Only change: make `load_steps` conditional (omit when None)
   - `format` is already read from the data model and written verbatim

**The architecture diagram for format handling:**

```
Input file (4.5 or 4.6)
    |
    v
parse_sections() --> HeaderAttributes(raw_line="[gd_scene format=3 uid=\"...\"]")
                     Section(header=..., raw_properties=[...])
    |
    v
[Unmodified?] ---YES---> serialize_sections() uses raw_line --> byte-identical output
    |
    NO (new file or modified)
    |
    v
_build_tscn_from_model() / _build_tres_from_model()
    |
    v
Uses data model fields (format=3, uid=..., load_steps=None)
    |
    v
Output: 4.6-style header (no load_steps, format=3)
```

---

## Changes Required: File-by-File Impact Analysis

### Files That Need Changes

| File | Change | Complexity | Reason |
|------|--------|------------|--------|
| `formats/values.py` | Add PackedVector4Array parser and dataclass | Low | Accept format=4 files that contain this type |
| `formats/tres.py:182-219` | Make load_steps conditional in `_build_tres_from_model()` | Trivial | Omit when None, matching 4.6 behavior |
| `formats/tscn.py:215-268` | Make load_steps conditional in `_build_tscn_from_model()` | Trivial | Same |
| `formats/tscn.py:122-134` | Read `unique_id` from node header attrs | Low | Parse the integer attribute for round-trip |
| `formats/tscn.py:32-43` | Add `unique_id: int | None = None` to SceneNode | Trivial | Store the attribute in data model |
| `formats/tscn.py:246-255` | Write `unique_id` in `_build_tscn_from_model()` | Low | Emit when present |
| `sprite/spriteframes.py:191` | Set `load_steps=None` | Trivial | Stop generating load_steps |
| `tileset/builder.py` | Set `load_steps=None` if applicable | Trivial | Same |

### Files That Need NO Changes

| File | Reason |
|------|--------|
| `formats/common.py` | Parser already handles arbitrary header attrs; raw_line preserves any format |
| `formats/uid.py` | UID encoding unchanged between 4.5 and 4.6 |
| `formats/project_cfg.py` | config_version=5, no structural changes |
| `backend.py` | All CLI flags unchanged, version check already accepts 4.6 |
| `export/pipeline.py` | Export flags unchanged |
| `formats/aseprite.py` | Aseprite format unrelated to Godot version |
| `sprite/atlas.py` | Image processing unrelated to Godot version |
| `sprite/splitter.py` | Image processing unrelated to Godot version |
| `sprite/validator.py` | Validates structure, not version-specific |
| All command files | CLI interface unchanged |

### New Files (Optional)

| File | Purpose | Priority |
|------|---------|----------|
| `tests/golden/spriteframes_46.tres` | Golden file without load_steps for 4.6 output | HIGH |
| `tests/golden/*.tscn` (updated) | Regenerate golden files without load_steps | HIGH |
| `tests/test_format_compat.py` | Tests for format=4 parsing, unique_id round-trip | HIGH |

---

## New Value Types for format=4 Parsing

### PackedVector4Array

Add to `formats/values.py`:

```python
@dataclass(frozen=True, slots=True)
class PackedVector4Array:
    """Packed array of 4D vector components as flat floats."""
    values: tuple[float, ...]

    def to_godot(self) -> str:
        items = ", ".join(_fmt_float(v) for v in self.values)
        return f"PackedVector4Array({items})"
```

Register in `_parse_constructor()`:
```python
if type_name == "PackedVector4Array":
    if not inner:
        return PackedVector4Array(())
    args = _split_args(inner)
    return PackedVector4Array(tuple(float(x) for x in args))
```

Add to `_GODOT_TYPES` tuple and `serialize_value()`.

### Base64 PackedByteArray (LOW priority)

Godot 4.3+ can write base64-encoded PackedByteArray. The exact constructor name in text format needs verification with actual files (likely `PackedByteArray` with a base64 string argument, but could use a distinct name). This only appears in files with large byte arrays (embedded audio, mesh data), which gdauto does not generate or typically encounter.

**Recommendation:** Defer base64 PackedByteArray support. If encountered, the existing lenient parser returns the raw string (D-04), which preserves the data for round-trip. Add explicit support only if users report issues.

---

## Unique Node IDs (unique_id attribute)

### What It Is

Godot 4.6 adds an integer `unique_id` attribute to `[node]` headers in .tscn files. This tracks nodes across renames and moves in inherited/instantiated scenes.

**Format:**
```
[node name="Player" type="CharacterBody2D" parent="." unique_id=1234567890]
```

The `unique_id` is a 32-bit integer, stored as an unquoted value in the node header.

### Backwards Compatibility

- Files with `unique_id` can be opened in older Godot versions (the attribute is simply ignored)
- Files without `unique_id` work fine in Godot 4.6 (IDs are assigned on re-save)

### Impact on gdauto

**Parsing:** Our `parse_section_header()` in `common.py` already reads all `key=value` pairs from headers into `attrs: dict[str, str]`. The `unique_id` attribute is automatically captured. The `_extract_node()` function in `tscn.py` should explicitly extract it into the `SceneNode` dataclass for completeness.

**Round-trip:** If a file has `unique_id`, the `raw_line` preserves it exactly. If we build from model, we should emit it when present.

**Generation:** gdauto's `scene create` command builds scenes from JSON definitions. We should NOT generate `unique_id` values because:
1. They are scene-local identifiers managed by the Godot editor
2. Godot assigns them on first save/re-save
3. Generating arbitrary IDs could conflict with Godot's own ID allocation

---

## AnimationLibrary Serialization Change (GH-110502)

Godot 4.6 changed AnimationLibrary serialization to avoid using Dictionary. This affects the internal serialization of AnimationLibrary resources when saved by the Godot editor.

**Impact on gdauto:** NONE. gdauto does not generate AnimationLibrary resources. If round-tripping .tres files that contain AnimationLibrary data, the raw_line preservation handles the new serialization format transparently (the key-value pairs are different, but our parser reads them generically).

---

## Suggested Build Order

Based on dependency analysis:

### Phase 1: Parser Hardening (no behavior change, accept more input)
1. Add `PackedVector4Array` dataclass and parser support to `values.py`
2. Add `unique_id` field to `SceneNode` dataclass in `tscn.py`
3. Extract `unique_id` in `_extract_node()` in `tscn.py`
4. Write tests: parse a format=4 .tres file, parse a .tscn with unique_id
5. Verify: existing tests still pass (no regressions)

**Rationale:** Parser changes are the foundation; everything else depends on correct parsing.

### Phase 2: Generator Updates (behavior change, new output format)
1. Make `load_steps` conditional in `_build_tres_from_model()` and `_build_tscn_from_model()`
2. Update `build_spriteframes()` to set `load_steps=None`
3. Update tileset builder to set `load_steps=None` (if it sets load_steps)
4. Update scene builder to emit `unique_id` when present in model
5. Regenerate golden files without `load_steps`
6. Update golden file comparison tests

**Rationale:** Generator changes produce different output; golden files must be updated in the same step.

### Phase 3: E2E Validation
1. Run E2E tests with Godot 4.6.1 binary
2. Verify generated .tres/.tscn files load in Godot 4.6.1
3. Verify generated files also load in Godot 4.5 (backwards compat)
4. Test round-trip: open 4.6 file, parse, serialize, compare

**Rationale:** E2E tests require the Godot binary and should run after all code changes.

---

## Backwards Compatibility Matrix

| Scenario | gdauto Output | Godot 4.5 | Godot 4.6 |
|----------|---------------|-----------|-----------|
| SpriteFrames .tres (new) | format=3, no load_steps | Loads OK | Loads OK |
| TileSet .tres (new) | format=3, no load_steps | Loads OK | Loads OK |
| Scene .tscn (new) | format=3, no load_steps, no unique_id | Loads OK | Loads OK |
| Round-trip 4.5 file | Preserves load_steps (raw_line) | Loads OK | Loads OK |
| Round-trip 4.6 file | Preserves no load_steps, unique_id (raw_line) | Loads OK* | Loads OK |

*Godot 4.5 ignores unknown attributes like `unique_id` in node headers.

---

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| format=4 files with base64 PackedByteArray fail to round-trip | Medium | Low (gdauto rarely encounters these) | Lenient parser returns raw string; add explicit support later |
| Removing load_steps breaks a downstream tool | Low | Very Low (load_steps was always optional) | Document the change; load_steps was never required by Godot |
| unique_id values in generated scenes conflict with Godot | Medium | N/A (we don't generate them) | Explicitly do NOT generate unique_id |
| Golden file tests fail after load_steps removal | Low | Certain (expected) | Regenerate all golden files in Phase 2 |

---

## Sources

- [Godot resource_format_text.h](https://github.com/godotengine/godot/blob/master/scene/resources/resource_format_text.h) -- FORMAT_VERSION=4, FORMAT_VERSION_COMPAT=3 (HIGH confidence)
- [Godot resource_uid.cpp](https://github.com/godotengine/godot/blob/master/core/io/resource_uid.cpp) -- UID encoding algorithm verified, base-34, unchanged (HIGH confidence)
- [Godot project_settings.h](https://github.com/godotengine/godot/blob/master/core/config/project_settings.h) -- CONFIG_VERSION=5, unchanged (HIGH confidence)
- [PR #103352: Remove load_steps](https://github.com/godotengine/godot/pull/103352) -- load_steps no longer written in 4.6 (HIGH confidence)
- [PR #106837: Add unique Node IDs](https://github.com/godotengine/godot/pull/106837) -- unique_id attribute in node headers, 32-bit integer (HIGH confidence)
- [PR #89186: Base64 PackedByteArray](https://github.com/godotengine/godot/pull/89186) -- format=4 trigger, merged in 4.3 (HIGH confidence)
- [PR #85474: PackedVector4Array](https://github.com/godotengine/godot/pull/85474) -- format=4 trigger, merged in 4.3 (HIGH confidence)
- [PR #100976: Fix UID encoding](https://github.com/godotengine/godot/pull/100976) -- 0 encodes as uid://a, merged in 4.4 (HIGH confidence)
- [GH-110502: AnimationLibrary serialization](https://github.com/godotengine/godot/pull/110502) -- Dictionary avoidance, internal change only (MEDIUM confidence)
- [TSCN format docs (master)](https://github.com/godotengine/godot-docs/blob/master/engine_details/file_formats/tscn.rst) -- unique_id documented, load_steps deprecated (HIGH confidence)
- [Godot 4.6 release page](https://godotengine.org/releases/4.6/) -- Unique Node IDs feature announcement (HIGH confidence)
- [Godot 4.6.1 maintenance release](https://godotengine.org/article/maintenance-release-godot-4-6-1/) -- No format changes, NodePath hash fix (HIGH confidence)
- [GDQuest Godot 4.6 workflow changes](https://www.gdquest.com/library/godot_4_6_workflow_changes/) -- Breaking changes list (HIGH confidence)
- [Godot command line tutorial (raw)](https://raw.githubusercontent.com/godotengine/godot-docs/master/tutorials/editor/command_line_tutorial.rst) -- CLI flags verified unchanged (HIGH confidence)
- [GH-11707: load_steps documentation issue](https://github.com/godotengine/godot-docs/issues/11707) -- Confirms load_steps removed in 4.6 (HIGH confidence)
