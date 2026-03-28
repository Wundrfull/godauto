# Phase 2: Aseprite-to-SpriteFrames Bridge - Research

**Researched:** 2026-03-28
**Domain:** Aseprite JSON parsing, Godot SpriteFrames .tres generation, sprite sheet manipulation
**Confidence:** HIGH

## Summary

This phase implements the core value proposition of gdauto: converting Aseprite sprite sheet exports into valid Godot SpriteFrames .tres resources entirely in Python. The research covers three commands (import-aseprite, split, create-atlas) plus a validation command (validate). The Aseprite JSON format is well-documented with known field structures, and the Godot SpriteFrames .tres format has been verified against both the existing sample fixture and the Godot engine source code (`sprite_frames.cpp`).

The key technical challenges are: (1) GCD-based FPS calculation for variable-duration frames, (2) ping-pong frame duplication since Godot SpriteFrames has no native ping-pong mode, (3) AtlasTexture margin calculation for trimmed sprites, and (4) correct serialization of the `animations` array with StringName syntax and SubResource references. All of these are well-understood algorithms with no external dependencies for the core import-aseprite command.

**Primary recommendation:** Build three modules: `src/gdauto/formats/aseprite.py` (JSON parser with dataclasses), `src/gdauto/sprite/` package (spriteframes builder, atlas packer, sheet splitter), and command handlers in `src/gdauto/commands/sprite.py`. The core import-aseprite pipeline is pure Python with zero dependencies beyond stdlib + click. Atlas creation and sheet splitting require Pillow (already declared as optional `[image]` extra).

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Support both Aseprite JSON export formats: json-hash (keyed by filename) and json-array (ordered list). Detect format automatically from the JSON structure.
- **D-02:** When no animation tags are defined in the Aseprite export, create a single animation named "default" containing all frames. Matches Godot's SpriteFrames convention.
- **D-03:** Lenient validation with warnings: accept any valid JSON with expected top-level keys (frames, meta). Warn on missing optional fields (slices, layers). Consistent with Phase 1 D-04 lenient parser philosophy.
- **D-04:** Full support for trimmed sprite data (spriteSourceSize offsets). Parse spriteSourceSize and sourceSize fields, adjust atlas regions and apply offsets per SPRT-06.
- **D-05:** File input only (no stdin piping). Accept a path to a .json file. Image path resolved relative to the JSON file's directory (matching Aseprite's default export behavior).
- **D-06:** Output path auto-derived from input: replace .json with .tres (character.json -> character.tres). Allow -o/--output override. Follows CLI-METHODOLOGY.md patterns.
- **D-07:** Reference image in place. The generated .tres references the sprite sheet at its current res:// path. User is responsible for placing the image in their Godot project tree. No file copying.
- **D-08:** GCD-based base FPS for variable-duration frames. Compute GCD of all frame durations within each animation, derive base FPS (1000/GCD), set per-frame duration multipliers (frame_ms/GCD). Per-animation GCD, not global.
- **D-09:** Ping-pong animations handled by frame duplication. Duplicate the reversed middle frames in the SpriteFrames animation (A-B-C-B pattern). Godot SpriteFrames has no native ping-pong mode.
- **D-10:** Aseprite repeat count mapping: 0 (infinite) -> loop=true, N>0 -> loop=false. The exact repeat count is lost but the loop intent is preserved.
- **D-11:** Animation speed always derived from actual frame durations. 100ms -> 10 FPS, 200ms -> 5 FPS. All duration multipliers will be 1.0 for uniform-duration animations.
- **D-12:** Simple shelf/strip packing for sprite create-atlas. Row-based: place sprites left-to-right, next row when full. Deterministic and sufficient for game sprite sheets. Requires Pillow (optional dependency).
- **D-13:** Atlas dimensions default to power-of-two (512, 1024, 2048, 4096) for GPU compatibility. --no-pot flag to allow arbitrary sizes.
- **D-14:** sprite split with no JSON metadata requires --frame-size WxH (e.g., --frame-size 32x32). Grid-based division. Requires Pillow for reading image dimensions.
- **D-15:** All three sprite commands (import-aseprite, split, create-atlas) are in Phase 2 scope per ROADMAP.
- **D-16:** Validation is a separate command (sprite validate), not built into import-aseprite. Keeps import-aseprite Godot-binary-independent. sprite validate loads .tres in headless Godot to verify animations, frame counts, texture references.
- **D-17:** Partial failures generate output with warnings. If 3 of 5 animation tags parse successfully and 2 have issues, output the .tres with valid animations, warn about skipped tags on stderr, exit code 0. User gets partial output they can inspect.
- **D-18:** Import guide is built-in help text on `gdauto sprite import-aseprite --help`. Covers correct Aseprite export settings, common pitfalls, recommended workflow. Always available, no extra artifact.

### Claude's Discretion

- Specific Aseprite export pitfalls to detect and warn about (SPRT-12): researcher identifies the most impactful ones from community forums and Godot docs
- Internal module organization: whether Aseprite parsing, SpriteFrames generation, and atlas packing live in one module or multiple
- Error message wording and fix suggestion text
- Test fixture design for Aseprite JSON samples

### Deferred Ideas (OUT OF SCOPE)

None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SPRT-01 | Parse Aseprite JSON metadata (frame regions, durations, animation tags, slices) | Aseprite JSON format fully documented: hash and array variants, frameTags with direction/repeat/color/data fields |
| SPRT-02 | Compute atlas texture regions (Rect2) from Aseprite frame x, y, w, h data | Direct mapping: `frame.x/y/w/h` -> `Rect2(x, y, w, h)` using existing `values.Rect2` dataclass |
| SPRT-03 | Convert per-frame duration (ms) to Godot FPS with GCD-based multipliers | Algorithm documented: GCD of all durations per animation; base_fps = 1000/gcd; multiplier = duration/gcd |
| SPRT-04 | Handle all four Aseprite directions: forward, reverse, ping-pong, ping-pong reverse | Exact direction strings confirmed from Aseprite source: "forward", "reverse", "pingpong", "pingpong_reverse" |
| SPRT-05 | Handle loop settings from Aseprite repeat counts | Repeat field confirmed: absent or 0 = loop, >0 = no loop (per D-10). Field is string in JSON, only present when >0 |
| SPRT-06 | Handle trimmed sprites with spriteSourceSize offsets | AtlasTexture margin calculation confirmed: `Rect2(sss.x, sss.y, sourceSize.w - frame.w, sourceSize.h - frame.h)` |
| SPRT-07 | Write valid .tres SpriteFrames resource | Format verified against Godot source and sample fixture; uses `_build_tres_from_model()` path in existing tres.py |
| SPRT-08 | sprite split: grid-based or JSON-defined sprite sheet splitting | Requires Pillow for image dimensions; outputs SpriteFrames .tres with one "default" animation |
| SPRT-09 | sprite create-atlas: batch multiple images into atlas with metadata | Shelf packing algorithm (D-12); Pillow for compositing; outputs atlas image + .tres |
| SPRT-10 | Validation pipeline: verify generated SpriteFrames in headless Godot | Uses existing GodotBackend.run() with GDScript validation script |
| SPRT-11 | Import guide documentation | Built-in --help text per D-18; researched Aseprite export settings and common pitfalls |
| SPRT-12 | Common import failure preventions | 6 pitfalls identified from community forums and Aseprite issue tracker |

</phase_requirements>

## Standard Stack

### Core (no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| click | 8.3.x (installed) | CLI command definitions | Already in pyproject.toml; all commands follow established Click patterns from Phase 1 |
| rich-click | 1.9.x (installed) | Formatted help text | Drop-in click import; provides rich --help output for the import guide (SPRT-11) |
| json (stdlib) | stdlib | Aseprite JSON parsing | Aseprite exports <1MB JSON; no need for orjson or ujson |
| math (stdlib) | stdlib | GCD calculation | `math.gcd()` for frame duration GCD computation |
| pathlib (stdlib) | stdlib | File path resolution | Image path resolution relative to JSON file directory |
| dataclasses (stdlib) | stdlib | Aseprite data models | Frozen dataclasses for parsed Aseprite data, consistent with Phase 1 value types |

### Optional (feature-gated)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pillow | >=12.0 (in pyproject.toml) | Image I/O for split and create-atlas | Only for `sprite split` and `sprite create-atlas`; NOT needed for `import-aseprite` |

### No New Dependencies

Phase 2 adds zero new dependencies. Everything needed is either stdlib, already installed (click, rich-click), or already declared optional (Pillow). The core import-aseprite command needs only stdlib + click.

## Architecture Patterns

### Recommended Module Structure

```
src/gdauto/
  formats/
    aseprite.py          # Aseprite JSON parser -> dataclasses (SPRT-01)
  sprite/
    __init__.py
    spriteframes.py      # SpriteFrames .tres builder (SPRT-02 through SPRT-07)
    atlas.py             # Atlas packer for create-atlas (SPRT-09)
    splitter.py          # Sheet splitter for split (SPRT-08)
    validator.py         # Headless Godot validation (SPRT-10)
  commands/
    sprite.py            # Click commands (extend existing stub)
```

### Rationale for Module Split

Separating `formats/aseprite.py` from `sprite/spriteframes.py` follows the Phase 1 pattern where `formats/tres.py` (parser/serializer) is separate from `commands/resource.py` (CLI handler). The Aseprite parser is a pure data layer; the SpriteFrames builder is the transformation logic; the commands are the CLI interface.

### Pattern 1: Aseprite JSON Parser (formats/aseprite.py)

**What:** Parse Aseprite JSON into typed dataclasses. Detect hash vs array format automatically.
**When to use:** Any code that reads Aseprite export data.

```python
# Source: Aseprite JSON API + ase-file-specs.md + Aseprite source (doc/anidir.cpp)
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json

class AniDirection(Enum):
    FORWARD = "forward"
    REVERSE = "reverse"
    PING_PONG = "pingpong"
    PING_PONG_REVERSE = "pingpong_reverse"

@dataclass(frozen=True, slots=True)
class FrameRect:
    """Atlas region for a single frame on the sprite sheet."""
    x: int
    y: int
    w: int
    h: int

@dataclass(frozen=True, slots=True)
class AsepriteFrame:
    """A single frame from the Aseprite export."""
    filename: str
    frame: FrameRect          # Position on sprite sheet
    trimmed: bool
    sprite_source_size: FrameRect  # spriteSourceSize (trim offset)
    source_size: tuple[int, int]   # sourceSize (w, h) original dimensions
    duration: int              # milliseconds

@dataclass(frozen=True, slots=True)
class AsepriteTag:
    """An animation tag from frameTags."""
    name: str
    from_frame: int           # inclusive start index
    to_frame: int             # inclusive end index
    direction: AniDirection
    repeat: int               # 0 = not specified (infinite), >0 = play N times
    color: str | None = None
    data: str | None = None

@dataclass(frozen=True)
class AsepriteMeta:
    """Metadata section of the Aseprite JSON export."""
    app: str
    version: str
    image: str                # Sprite sheet filename
    format: str               # e.g., "RGBA8888"
    size: tuple[int, int]     # (w, h) of the sprite sheet
    scale: str
    frame_tags: list[AsepriteTag] = field(default_factory=list)
    slices: list[dict] = field(default_factory=list)

@dataclass(frozen=True)
class AsepriteData:
    """Complete parsed Aseprite JSON export."""
    frames: list[AsepriteFrame]
    meta: AsepriteMeta

def parse_aseprite_json(path: Path) -> AsepriteData:
    """Parse an Aseprite JSON export file.

    Auto-detects json-hash vs json-array format based on
    whether 'frames' is a dict (hash) or list (array).
    """
    ...
```

### Pattern 2: SpriteFrames Builder (sprite/spriteframes.py)

**What:** Transform AsepriteData into a GdResource representing a SpriteFrames .tres file.
**When to use:** The core pipeline from SPRT-01 through SPRT-07.

```python
# Source: Godot sprite_frames.cpp, sample.tres fixture
from gdauto.formats.tres import GdResource, ExtResource, SubResource
from gdauto.formats.values import Rect2, StringName, SubResourceRef, ExtResourceRef
from gdauto.formats.uid import generate_uid, uid_to_text, generate_resource_id

def build_spriteframes(
    aseprite: AsepriteData,
    image_path: str,          # res:// path to sprite sheet
) -> GdResource:
    """Build a SpriteFrames GdResource from parsed Aseprite data.

    Creates:
    - One ExtResource for the sprite sheet texture
    - One AtlasTexture SubResource per frame
    - The animations array in the [resource] section
    """
    ...
```

### Pattern 3: GCD-Based FPS Calculation (SPRT-03)

**What:** Convert variable per-frame millisecond durations to Godot's base FPS + duration multipliers.
**When to use:** Every animation conversion.

```python
# Source: CONTEXT.md D-08, D-11
import math
from functools import reduce

def compute_animation_timing(
    durations_ms: list[int],
) -> tuple[float, list[float]]:
    """Compute base FPS and per-frame duration multipliers.

    For uniform durations (all 100ms): returns (10.0, [1.0, 1.0, ...])
    For variable durations (100ms, 200ms): gcd=100, base_fps=10.0,
      multipliers=[1.0, 2.0]

    Returns:
        (base_fps, duration_multipliers)
    """
    if not durations_ms:
        return (1.0, [])
    gcd = reduce(math.gcd, durations_ms)
    base_fps = 1000.0 / gcd
    multipliers = [d / gcd for d in durations_ms]
    return (base_fps, multipliers)
```

### Pattern 4: Ping-Pong Frame Expansion (SPRT-04)

**What:** Expand ping-pong animations by duplicating reversed middle frames.
**When to use:** When `direction` is `pingpong` or `pingpong_reverse`.

```python
# Source: CONTEXT.md D-09
def expand_pingpong(frame_indices: list[int]) -> list[int]:
    """Expand frame indices for ping-pong playback.

    Input [0, 1, 2, 3] -> Output [0, 1, 2, 3, 2, 1]
    (reversed middle frames appended, excluding first and last)
    """
    if len(frame_indices) <= 2:
        return frame_indices
    return frame_indices + frame_indices[-2:0:-1]

def expand_pingpong_reverse(frame_indices: list[int]) -> list[int]:
    """Expand frame indices for ping-pong reverse playback.

    Input [0, 1, 2, 3] -> Output [3, 2, 1, 0, 1, 2]
    (starts reversed, then forward middle frames)
    """
    if len(frame_indices) <= 2:
        return list(reversed(frame_indices))
    reversed_frames = list(reversed(frame_indices))
    return reversed_frames + frame_indices[1:-1]
```

### Pattern 5: SpriteFrames .tres Serialization Format

**What:** The exact structure Godot expects for a SpriteFrames .tres file.
**When to use:** Building the GdResource for serialization.

```
# Source: Godot sprite_frames.cpp (_get_animations, _set_animations)
# and tests/fixtures/sample.tres

[gd_resource type="SpriteFrames" load_steps=N format=3 uid="uid://..."]

[ext_resource type="Texture2D" uid="uid://..." path="res://sprites/sheet.png" id="1_sheet"]

[sub_resource type="AtlasTexture" id="AtlasTexture_xxxxx"]
atlas = ExtResource("1_sheet")
region = Rect2(0, 0, 32, 32)

[sub_resource type="AtlasTexture" id="AtlasTexture_yyyyy"]
atlas = ExtResource("1_sheet")
region = Rect2(32, 0, 32, 32)
margin = Rect2(2, 3, 4, 5)  # Only present for trimmed sprites

[resource]
animations = [{
"frames": [{
"duration": 1.0,
"texture": SubResource("AtlasTexture_xxxxx")
}, {
"duration": 2.0,
"texture": SubResource("AtlasTexture_yyyyy")
}],
"loop": true,
"name": &"idle",
"speed": 10.0
}, {
"frames": [{
"duration": 1.0,
"texture": SubResource("AtlasTexture_xxxxx")
}],
"loop": false,
"name": &"attack",
"speed": 8.0
}]
```

**Critical serialization details:**
- `load_steps` = 1 (ext_resource for texture) + N (AtlasTexture sub_resources) + 1 (the resource itself)
- Animation names use StringName syntax: `&"idle"` not `"idle"`
- Frame `"duration"` is a float multiplier relative to base speed, not milliseconds
- Frame `"texture"` uses `SubResource("id")` references
- The `animations` array is a Godot Array of Dictionaries
- Each dictionary has exactly 4 keys: `frames`, `loop`, `name`, `speed`
- `speed` is FPS as a float

### Pattern 6: AtlasTexture Margin for Trimmed Sprites (SPRT-06)

**What:** When Aseprite exports with trim enabled, frames have offset data that must be preserved.
**When to use:** When `frame.trimmed == true` in the Aseprite JSON.

```python
# Source: Aseprite Wizard plugin issue #39, verified against Godot AtlasTexture docs
# margin = Rect2(sss_x, sss_y, source_w - frame_w, source_h - frame_h)

def compute_margin(
    sprite_source_size: FrameRect,
    source_size: tuple[int, int],
    frame: FrameRect,
) -> Rect2 | None:
    """Compute AtlasTexture margin for trimmed sprites.

    Returns None if not trimmed (no margin needed).
    """
    margin_x = float(sprite_source_size.x)
    margin_y = float(sprite_source_size.y)
    margin_w = float(source_size[0] - frame.w)
    margin_h = float(source_size[1] - frame.h)
    if margin_x == 0 and margin_y == 0 and margin_w == 0 and margin_h == 0:
        return None
    return Rect2(margin_x, margin_y, margin_w, margin_h)
```

### Anti-Patterns to Avoid

- **Global GCD across animations:** D-08 specifies per-animation GCD, not global. Each animation tag has its own base FPS. A global GCD would produce unnecessarily high FPS for simple animations.
- **Relying on Godot ping-pong mode:** Godot SpriteFrames has no built-in ping-pong; AnimatedSprite2D does not have a ping-pong property. Frames must be physically duplicated in the animation (D-09).
- **Copying the sprite sheet image:** D-07 says reference in place with `res://` path. Never copy or move the image file.
- **Using Pillow for import-aseprite:** The core command must work without Pillow. Only split and create-atlas need image I/O.
- **Building raw .tres strings:** Use the existing `_build_tres_from_model()` in tres.py. Construct GdResource, ExtResource, SubResource dataclasses and let the serializer handle formatting.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| .tres serialization | Custom string builder | `tres._build_tres_from_model()` | Already handles header, ext_resources, sub_resources, properties with correct formatting |
| Rect2 serialization | String formatting | `values.Rect2.to_godot()` | Handles float formatting with `_fmt_float` for Godot-exact output |
| UID generation | Random string | `uid.generate_uid()` + `uid_to_text()` | Matches Godot's base-34 encoding algorithm |
| Resource ID generation | Random suffix | `uid.generate_resource_id("AtlasTexture")` | Matches Godot's `Type_xxxxx` format |
| SubResource references | Raw string | `values.SubResourceRef(id).to_godot()` | Type-safe, consistent serialization |
| StringName formatting | `&"name"` strings | `values.StringName(name).to_godot()` | Proper escaping, consistent with Phase 1 |
| GCD computation | Custom loop | `functools.reduce(math.gcd, durations)` | stdlib, one-liner, handles edge cases |
| Error reporting | print/sys.stderr | `errors.GdautoError` subclass + `output.emit_error()` | Structured JSON + human output with fix suggestions |

**Key insight:** Phase 1 built all the serialization infrastructure. Phase 2's job is to construct the right GdResource instances and let the existing serializer do the formatting.

## Common Pitfalls

### Pitfall 1: Aseprite Hash Keys Include File Extension and Frame Number

**What goes wrong:** JSON-hash format uses keys like `"character 0.ase"` or `"character (Layer) 0.ase"`. Naive parsing assumes simple names.
**Why it happens:** Aseprite generates filename-based keys with embedded spaces, layer names, and frame numbers.
**How to avoid:** For json-hash, extract frame index from the key using a regex pattern or sort by the frame's position on the sheet. For json-array, use list index directly.
**Warning signs:** Frame order doesn't match expected animation sequence.

### Pitfall 2: Off-by-One in frameTags from/to Indices

**What goes wrong:** frameTags use inclusive ranges (`"from": 0, "to": 3` means frames 0, 1, 2, 3 = 4 frames). Treating `to` as exclusive loses the last frame.
**Why it happens:** Common programming convention is exclusive upper bounds, but Aseprite uses inclusive.
**How to avoid:** Slice frames as `frames[tag.from_frame : tag.to_frame + 1]`.
**Warning signs:** Animations missing their last frame.

### Pitfall 3: Trimmed Sprites with Zero-Size Frames

**What goes wrong:** When Aseprite trims a completely transparent frame, the frame has w=0, h=0 in the JSON. This creates an invalid AtlasTexture region.
**Why it happens:** Full trim mode removes all transparent pixels, leaving nothing for empty frames.
**How to avoid:** Detect zero-size frames, warn the user, and either skip the frame or use the sourceSize as the region (producing a transparent frame).
**Warning signs:** Godot reports "Invalid atlas region" when loading.

### Pitfall 4: Aseprite Repeat Field is a String, Not Integer

**What goes wrong:** The `repeat` field in frameTags JSON is serialized as a string (e.g., `"repeat": "3"`), not an integer. Comparing `repeat > 0` fails.
**Why it happens:** Aseprite's JSON exporter formats it as a string value (confirmed from `doc_exporter.cpp`).
**How to avoid:** Parse with `int(tag.get("repeat", "0"))`. Handle missing field (absent = infinite loop).
**Warning signs:** All animations incorrectly set to loop=true or loop=false.

### Pitfall 5: load_steps Count Must Be Exact

**What goes wrong:** If `load_steps` in the `[gd_resource]` header doesn't match the actual number of ext_resources + sub_resources + 1, Godot logs a warning or error on load.
**Why it happens:** The count must be computed after all resources are generated, including duplicated ping-pong frames.
**How to avoid:** Calculate after building all AtlasTexture sub_resources: `load_steps = len(ext_resources) + len(sub_resources) + 1`.
**Warning signs:** Godot console shows "Resource file has extra records" or loads partially.

### Pitfall 6: Aseprite JSON Image Path Is Relative to the JSON File

**What goes wrong:** The `meta.image` field contains just the filename (e.g., `"sheet.png"`), not a full path. If the .tres is written to a different directory, the image reference breaks.
**Why it happens:** Aseprite writes the image next to the JSON; the path is relative to the JSON file location.
**How to avoid:** Per D-05 and D-07, resolve the image path relative to the JSON file's directory. The .tres uses a `res://` path that the user controls via --res-path or auto-detection.
**Warning signs:** Godot shows missing texture errors.

## Code Examples

### Complete SpriteFrames .tres Generation Flow

```python
# Source: Verified against Godot sprite_frames.cpp and sample.tres fixture

def build_spriteframes_resource(
    aseprite: AsepriteData,
    image_res_path: str,
) -> GdResource:
    """Build a complete SpriteFrames GdResource."""
    # 1. Create ext_resource for the sprite sheet texture
    sheet_id = "1_sheet"
    sheet_uid = uid_to_text(generate_uid())
    ext = ExtResource(
        type="Texture2D",
        path=image_res_path,
        id=sheet_id,
        uid=sheet_uid,
    )

    # 2. Determine animations (tags or default)
    tags = aseprite.meta.frame_tags
    if not tags:
        tags = [AsepriteTag(
            name="default",
            from_frame=0,
            to_frame=len(aseprite.frames) - 1,
            direction=AniDirection.FORWARD,
            repeat=0,
        )]

    # 3. Build AtlasTexture sub_resources and animation dicts
    sub_resources: list[SubResource] = []
    animations: list[dict] = []

    for tag in tags:
        tag_frames = aseprite.frames[tag.from_frame:tag.to_frame + 1]
        frame_indices = list(range(len(tag_frames)))

        # Expand direction
        if tag.direction == AniDirection.REVERSE:
            frame_indices = list(reversed(frame_indices))
        elif tag.direction == AniDirection.PING_PONG:
            frame_indices = expand_pingpong(frame_indices)
        elif tag.direction == AniDirection.PING_PONG_REVERSE:
            frame_indices = expand_pingpong_reverse(frame_indices)

        # Compute timing
        durations = [tag_frames[i].duration for i in frame_indices]
        # ... rest of timing, sub_resource, animation dict building
```

### Aseprite JSON Hash vs Array Detection

```python
# Source: Aseprite CLI docs, gist examples

def _detect_format(raw: dict) -> str:
    """Detect json-hash vs json-array format."""
    frames = raw.get("frames")
    if isinstance(frames, list):
        return "array"
    if isinstance(frames, dict):
        return "hash"
    raise ValidationError(
        message="Invalid Aseprite JSON: 'frames' must be an array or object",
        code="ASEPRITE_INVALID_FRAMES",
        fix="Export from Aseprite with --format json-array or --format json-hash",
    )
```

### Aseprite JSON frameTag Complete Structure

```json
{
  "frameTags": [
    {
      "name": "idle",
      "from": 0,
      "to": 3,
      "direction": "forward",
      "color": "#000000ff",
      "data": "custom note",
      "repeat": "2"
    },
    {
      "name": "walk",
      "from": 4,
      "to": 9,
      "direction": "pingpong"
    }
  ]
}
```

**Field presence rules (confirmed from Aseprite source, doc_exporter.cpp):**
- `name`, `from`, `to`, `direction`: Always present
- `repeat`: Only present when > 0 (string type, e.g., `"3"`). Absent means infinite/default.
- `color`, `data`: Present when set by user (userData). May include `properties` dict for extension data.

### Direction String Values (confirmed from Aseprite source, doc/anidir.cpp)

| AniDir Enum | JSON String | Frames 0-3 Expansion |
|-------------|-------------|----------------------|
| FORWARD | `"forward"` | [0, 1, 2, 3] |
| REVERSE | `"reverse"` | [3, 2, 1, 0] |
| PING_PONG | `"pingpong"` | [0, 1, 2, 3, 2, 1] |
| PING_PONG_REVERSE | `"pingpong_reverse"` | [3, 2, 1, 0, 1, 2] |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Godot editor plugins only | No headless CLI tool exists | Current gap | gdauto fills this gap entirely |
| Aseprite Wizard (GDScript editor plugin) | Still requires Godot editor GUI | Ongoing | gdauto provides CLI alternative for CI/CD |
| Manual SpriteFrames creation | Some tools generate .tres | Various | gdauto automates the full pipeline |
| Aseprite tag direction ignored | All 4 directions supported in Aseprite 1.3+ | 2023 | Must handle all 4 values including pingpong_reverse |
| No repeat field in JSON | repeat field added (conditional) | Aseprite 1.3-rc1 | Must handle absent repeat field gracefully |

**Deprecated/outdated:**
- Godot 3.x SpriteFrames format used integer resource IDs (e.g., `ExtResource( 1 )`). Godot 4.x uses string IDs (e.g., `ExtResource("1_sheet")`). Phase 1 parser already handles this.
- Aseprite 1.2.x did not export direction or repeat in JSON. Aseprite 1.3+ does. Our parser should handle both (absent fields = forward, infinite loop).

## Open Questions

1. **How does Godot handle the `margin` property on AtlasTexture for AnimatedSprite3D?**
   - What we know: margin works for AnimatedSprite2D to preserve sprite positioning with trimmed sprites
   - What's unclear: Whether AnimatedSprite3D handles margin identically
   - Recommendation: Test with headless Godot validation (SPRT-10); document 2D focus for now

2. **What is the exact `res://` path format the user should provide?**
   - What we know: D-07 says reference image in place with res:// path
   - What's unclear: Whether to auto-detect the res:// path from project structure or require explicit --res-path
   - Recommendation: Accept the JSON file path; if it's inside a Godot project (has project.godot ancestor), compute res:// automatically. Otherwise require --res-path. Fall back to relative path.

3. **Should duplicate AtlasTexture sub_resources be deduplicated for ping-pong animations?**
   - What we know: Ping-pong duplicates frames (A-B-C-B). Frame B appears twice in the animation.
   - What's unclear: Whether to create one AtlasTexture_B referenced twice, or two identical AtlasTexture sub_resources
   - Recommendation: Create one sub_resource per unique frame, reference it multiple times in the animation. Reduces file size and matches how Godot editor would do it.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | Yes | 3.11.9 (system), managed by uv | -- |
| uv | Package management | Yes | 0.9.7 | -- |
| click | CLI commands | Yes | 8.3.1 | -- |
| Pillow | sprite split, create-atlas | Yes (system), No (uv env) | 12.1.1 (system) | Install with `uv pip install gdauto[image]` |
| Godot | sprite validate only | Not checked | -- | Skip validation tests; mark with @pytest.mark.requires_godot |
| pytest | Testing | Yes | 9.0.2 (uv env) | -- |
| gdauto | Package under test | Yes | 0.1.0 (uv env) | -- |

**Missing dependencies with no fallback:**
- None. All core features work with installed dependencies.

**Missing dependencies with fallback:**
- Pillow not in uv environment: run `uv pip install -e ".[image]"` to install. Split and create-atlas will check for Pillow at import time and raise a clear error with fix suggestion if missing.
- Godot binary not verified on PATH: validate command will raise GodotBinaryError with fix suggestion. All other commands work without Godot.

## Aseprite Export Pitfalls to Detect (SPRT-12)

Based on research of Aseprite GitHub issues, community forums, and the Aseprite Wizard plugin issues, these are the most impactful pitfalls gdauto should detect and warn about:

| Pitfall | Detection | Warning Message |
|---------|-----------|-----------------|
| No animation tags defined | `frameTags` absent or empty | "No animation tags found; creating single 'default' animation. Add tags in Aseprite for named animations." |
| Trimmed sprites with zero-size frames | `frame.w == 0 or frame.h == 0` | "Frame N has zero dimensions (fully transparent). Skipping frame. Disable 'Trim' in Aseprite export or add visible pixels." |
| Inconsistent frame sizes across animation | Frames within a tag have different sourceSize | "Frames in animation '{name}' have different source sizes. This may cause visual artifacts." |
| Very high GCD-derived FPS (>120) | `base_fps > 120` | "Animation '{name}' has computed FPS of {fps}. Frame durations may have rounding issues." |
| Hash format with unparseable frame keys | Key doesn't match expected pattern | "Could not determine frame order from hash keys. Consider using --format json-array for export." |
| Missing meta.image field | `meta.image` is absent | "No sprite sheet image path in JSON. Specify --sheet-path explicitly." |

## Project Constraints (from CLAUDE.md)

- **Tech stack**: Python 3.10+, Click >= 8.0, pytest >= 7.0
- **No Godot dependency for file manipulation**: import-aseprite, split, create-atlas must work without Godot binary
- **Error contract**: Non-zero exit codes, actionable messages, --json errors produce structured JSON
- **File validity**: Generated .tres must be loadable by Godot without modification
- **Code style**: No em dashes, no emojis, type hints on all signatures, docstrings on public functions, functions under 30 lines, comments on non-obvious logic only
- **Independence**: Pillow is optional (image extra), not a core dependency

## Sources

### Primary (HIGH confidence)
- Aseprite source code `src/doc/anidir.h` and `src/doc/anidir.cpp` - exact direction string values: "forward", "reverse", "pingpong", "pingpong_reverse"
- Aseprite source code `src/app/doc_exporter.cpp` - frameTag JSON structure with conditional repeat field (string type, only when >0)
- Godot source code `scene/resources/sprite_frames.cpp` - SpriteFrames animation dictionary structure: name (StringName), speed (double), loop (bool), frames (Array of {texture, duration})
- Existing `tests/fixtures/sample.tres` - verified SpriteFrames .tres format with AtlasTexture sub_resources
- Existing Phase 1 source: `formats/tres.py`, `formats/values.py`, `formats/uid.py` - serialization infrastructure

### Secondary (MEDIUM confidence)
- [Aseprite CLI docs](https://www.aseprite.org/docs/cli/) - JSON export flags, --format, --list-tags
- [Aseprite JSON hash format gist](https://gist.github.com/dacap/db18e5747a4b6e208d3c) - hash key format
- [Aseprite JSON array format gist](https://gist.github.com/dacap/a32adb9248320326733a) - array structure
- [Aseprite ase-file-specs](https://github.com/aseprite/aseprite/blob/main/docs/ase-file-specs.md) - Tag chunk: direction values 0-3, repeat field semantics
- [Godot Aseprite Wizard issue #39](https://github.com/viniciusgerevini/godot-aseprite-wizard/issues/39) - AtlasTexture margin calculation for trimmed sprites
- [Aseprite issue #1348](https://github.com/aseprite/aseprite/issues/1348) - repeat/loop field behavior in JSON
- [Aseprite issue #1156](https://github.com/aseprite/aseprite/issues/1156) - direction field in JSON output

### Tertiary (LOW confidence)
- None. All findings verified against primary or secondary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies; all verified installed
- Architecture: HIGH - follows Phase 1 patterns exactly; format verified against Godot source
- Aseprite JSON format: HIGH - verified against Aseprite source code (anidir.cpp, doc_exporter.cpp)
- SpriteFrames .tres format: HIGH - verified against Godot source code (sprite_frames.cpp) and existing fixture
- Pitfalls: MEDIUM - based on community forum reports and issue trackers; the specific trim/margin calculation is HIGH (verified against Aseprite Wizard source)
- Atlas packing (create-atlas): MEDIUM - simple shelf algorithm is well-understood, but no official Godot convention exists

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stable domain; Aseprite and Godot formats change infrequently)
