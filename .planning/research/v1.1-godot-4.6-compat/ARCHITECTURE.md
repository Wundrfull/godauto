# Architecture: Godot 4.6 Compatibility Changes

**Domain:** Godot engine version migration for CLI tooling
**Researched:** 2026-03-28

## Architecture Assessment

The existing gdauto architecture requires no structural changes for Godot 4.6 compatibility. The changes are localized to data model updates and builder behavior.

## Affected Components

```
                     +------------------+
                     | CLI Commands     |  (commands/sprite.py)
                     | (Click handlers) |  No architectural change.
                     +--------+---------+  load_steps computation removed.
                              |
              +---------------+---------------+
              |               |               |
    +---------+----+ +--------+------+ +------+-------+
    | Sprite       | | Scene         | | TileSet      |
    | Builders     | | Builder       | | Builder      |
    | (spriteframes| | (builder.py)  | | (builder.py) |
    |  splitter,   | |               | |              |
    |  atlas)      | | load_steps    | | load_steps   |
    | load_steps   | | removed.      | | removed.     |
    | removed.     | | unique_id opt.| |              |
    +---------+----+ +--------+------+ +------+-------+
              |               |               |
              +---------------+---------------+
                              |
                     +--------+----------+
                     | Format Layer       |
                     | tres.py / tscn.py  |
                     | common.py          |
                     +--------+----------+
                              |
                     Parser: No change (already handles
                             optional load_steps and
                             arbitrary header attrs).

                     Serializer:
                       _build_tres_from_model(): skip
                         load_steps when None.
                       _build_tscn_from_model(): skip
                         load_steps when None; emit
                         unique_id when present.

                     Round-trip: No change (raw section
                       preservation handles all attributes
                       automatically).
```

## Data Model Changes

### SceneNode (tscn.py)

```python
# Current (v1.0)
@dataclass
class SceneNode:
    name: str
    type: str | None
    parent: str | None
    properties: dict[str, Any] = field(default_factory=dict)
    instance: str | None = None
    owner: str | None = None
    groups: list[str] | None = None
    raw_section: Section | None = None

# Proposed (v1.1) -- add unique_id field
@dataclass
class SceneNode:
    name: str
    type: str | None
    parent: str | None
    properties: dict[str, Any] = field(default_factory=dict)
    instance: str | None = None
    owner: str | None = None
    groups: list[str] | None = None
    unique_id: int | None = None        # NEW: Godot 4.6+ node tracking
    raw_section: Section | None = None
```

### GdResource and GdScene (tres.py, tscn.py)

No structural changes. The `load_steps: int | None` fields remain. Builders will set them to `None` instead of computing values.

## Serializer Changes

### _build_tres_from_model (tres.py)

The existing code already skips `load_steps` when `None`:
```python
if resource.load_steps is not None:
    parts.append(f"load_steps={resource.load_steps}")
```
No serializer change needed. The change is in the builders that construct GdResource instances.

### _build_tscn_from_model (tscn.py)

Same for load_steps. For unique_id, add emission:
```python
# In node serialization:
if node.unique_id is not None:
    parts.append(f"unique_id={node.unique_id}")
```

## Validator Changes

### sprite/validator.py

`_check_load_steps()` already handles `None`:
```python
def _check_load_steps(resource: GdResource, warnings: list[str]) -> None:
    if resource.load_steps is None:
        return  # Already handles missing load_steps
```

Consider removing the function entirely or adding a note that load_steps is deprecated in 4.6.

## No Architectural Patterns Changed

- Parser state machine: unchanged
- Round-trip fidelity via raw sections: unchanged
- Builder -> GdResource -> serializer pipeline: unchanged
- CLI command structure: unchanged
- Test fixtures and golden file comparison: approach unchanged (files updated, not mechanism)

## Scalability Considerations

These changes do not affect scalability. The parser already handles files of any size and arbitrary header attributes. The builder changes remove computation rather than adding it.

## Sources

- Analysis based on codebase review of: `src/gdauto/formats/tres.py`, `src/gdauto/formats/tscn.py`, `src/gdauto/formats/common.py`, `src/gdauto/scene/builder.py`, `src/gdauto/sprite/spriteframes.py`, `src/gdauto/tileset/builder.py`, `src/gdauto/sprite/validator.py`
- [TSCN file format docs](https://github.com/godotengine/godot-docs/blob/master/engine_details/file_formats/tscn.rst)
