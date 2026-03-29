# Feature Landscape: Godot 4.6.1 Compatibility Audit

**Domain:** Godot 4.5-to-4.6.1 delta affecting gdauto CLI tool
**Researched:** 2026-03-28

## Table Stakes

Changes that MUST be made for gdauto to produce valid output when used with Godot 4.6.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Omit load_steps from generated .tres/.tscn headers | Godot 4.6 strips it on re-save; causes unnecessary VCS diffs | Low | 8 files, 18 references; set load_steps=None in all builders |
| Parse unique_id from .tscn node headers | 4.6 scenes contain this attribute; parser must not choke | None | Parser already handles arbitrary attrs; just need model exposure |
| Preserve unique_id on round-trip | Editing 4.6 scenes must not strip unique_id | None | Raw-line round-trip already preserves it; model-based needs update |
| Update golden files | Existing golden files have load_steps; new ones will not | Low | Regenerate golden files or make comparison strip load_steps |
| Update sprite validator | _check_load_steps() validates a now-obsolete attribute | Low | Skip or remove check when targeting 4.6+; demote to info for 4.5 |

## Differentiators

Changes that improve gdauto's compatibility story beyond the minimum.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Add unique_id field to SceneNode dataclass | Expose node IDs in resource inspect, scene list JSON output | Low | `unique_id: int \| None = None` |
| Write unique_id in model-based scene serialization | Generated scenes include node IDs when available | Low | Add to _build_tscn_from_model() node header construction |
| Generate deterministic unique_ids in scene create | Prevents non-deterministic export issue (#115971) | Low | Sequential counter starting at 1, assigned per-scene |
| Version-aware generation (--target-version flag) | Users on 4.5 can still get 4.5-format output | Medium | Global flag controlling load_steps, unique_id behavior |
| Wrap --export-patch CLI flag | New Godot 4.6 feature for delta PCK exports | Medium | Add mode="patch" to export pipeline with --patches support |
| Report unique_id in scene list output | Richer scene analysis for AI agents | Low | Include in JSON output of scene list command |

## Anti-Features

Features to explicitly NOT build for this audit milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Version-branched golden files (4.5 set + 4.6 set) | Doubles test maintenance; 648 tests x 2 | Make golden comparison version-agnostic (ignore load_steps in diff) or target 4.6 only |
| Automatic scene migration (4.5 to 4.6 format) | Godot already does this via "Upgrade Project Files" | Document that users should open projects in Godot 4.6 to upgrade |
| TileMapLayer scene data manipulation | Complex, editor-focused; tile rotation is runtime feature | Keep scope to TileSet .tres generation |
| LibGodot embedding as alternative to subprocess | Major architectural change; experimental API | Track for future milestone |
| Jolt physics default in project create | Cosmetic; only affects new project scaffolding | Defer to future enhancement |

## Feature Dependencies

```
load_steps removal -> golden file updates -> E2E test updates
                   -> validator update (_check_load_steps)

unique_id support -> SceneNode dataclass update -> _extract_node() update
                 -> _build_tscn_from_model() update
                 -> scene list JSON output update

Version targeting -> --target-version flag (optional)
                 -> conditional load_steps behavior
```

## MVP Recommendation

Prioritize in this order:

1. **Drop load_steps from all builders** (table stakes, eliminates VCS noise for all users)
2. **Add unique_id to SceneNode model** (table stakes for correct round-trip of 4.6 scenes)
3. **Update golden files** (table stakes for test suite to pass)
4. **Update validator** (table stakes; _check_load_steps is wrong for 4.6)
5. **Generate unique_ids in scene create** (differentiator; prevents export determinism issue)
6. **Run E2E against 4.6.1** (validation; catches anything the research missed)

Defer: Version-aware generation flag (most users are on 4.6 by now), --export-patch support (nice-to-have), Jolt/D3D12 defaults in project create (cosmetic).

## Sources

- [PR #103352: load_steps removal](https://github.com/godotengine/godot/pull/103352)
- [PR #106837: unique Node IDs](https://github.com/godotengine/godot/pull/106837)
- [Issue #115971: non-deterministic export](https://github.com/godotengine/godot/issues/115971)
- [Godot 4.6 Release Notes](https://godotengine.org/releases/4.6/)
