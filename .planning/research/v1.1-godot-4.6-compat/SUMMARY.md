# Research Summary: Godot 4.6/4.6.1 Compatibility Audit

**Domain:** Godot engine CLI tooling compatibility with Godot 4.6.x
**Researched:** 2026-03-28
**Overall confidence:** HIGH

## Executive Summary

Godot 4.6 (released Jan 2026) and its maintenance patch 4.6.1 introduce one breaking file format change and one additive format change that directly affect gdauto. The breaking change is the removal of `load_steps` from .tscn and .tres file headers (PR #103352). The additive change is the introduction of `unique_id` integer attributes on scene nodes (PR #106837). All other changes in 4.6/4.6.1 are either editor-only, runtime-only, or affect domains gdauto does not touch.

The `load_steps` removal is the highest priority because gdauto v1.0 computes and writes `load_steps` in every generated file across 8 source files (18 code references). While Godot 4.6 still reads files containing `load_steps`, it strips the attribute on resave, meaning gdauto-generated files will produce unnecessary diffs when loaded in Godot 4.6. The fix is straightforward: stop emitting `load_steps` in all builders. Preliminary analysis suggests Godot 4.5 also tolerates missing `load_steps` (it was never functionally required), meaning we can simply drop it without version branching.

The `unique_id` addition is lower priority because it is purely additive. Godot 4.6 adds `unique_id=NNNN` to node headers in .tscn files to enable robust node tracking across renames and reparenting in inherited scenes. gdauto's parser already handles this via raw section preservation, but the `SceneNode` dataclass does not expose it, and model-based serialization drops it. Adding the field is a small change with good value for round-trip fidelity.

No changes were found to the SpriteFrames resource format, TileSet resource format, export CLI arguments, import pipeline behavior, or project.godot structure that would break existing gdauto functionality. The 4.6.1 patch is purely stability fixes with no format implications.

## Key Findings

**Stack:** No stack changes needed. Python, Click, custom parser all remain appropriate. No new dependencies required.

**Architecture:** The version-awareness needed for `load_steps` is minimal; the simplest path is to just stop emitting it. No architectural restructuring needed.

**Critical pitfall:** Generating files with `load_steps` that Godot 4.6 strips on resave creates friction for users who see unexpected diffs in version control.

## Implications for Roadmap

Based on research, the v1.1 audit milestone should have a simple two-phase structure:

1. **Phase 1: Format Compatibility Fixes** -- Address the load_steps removal and unique_id addition
   - Addresses: load_steps removal (MUST-FIX), unique_id support (SHOULD-SUPPORT)
   - Avoids: over-engineering version branching (just drop load_steps for all targets)
   - Scope: 8 source files, golden files, validator update
   - Effort: Small (mostly deletion of code)

2. **Phase 2: Validation and Testing** -- Verify all commands against Godot 4.6.1
   - Addresses: E2E test suite run against 4.6.1 binary, golden file updates
   - Avoids: TileSet editor strictness regressions
   - Scope: Test suite updates, any discovered edge cases
   - Effort: Small to medium (depends on E2E failures)

**Phase ordering rationale:**
- Phase 1 must come first because golden files cannot be updated until the format changes are made.
- Phase 2 depends on Phase 1 being complete; E2E tests need to run against the new output format.

**Research flags for phases:**
- Phase 1: Standard work, unlikely to need additional research. The changes are well-documented.
- Phase 2: May need research if E2E tests reveal unexpected 4.6 behavioral changes not documented in release notes.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| load_steps removal | HIGH | Verified via PR, proposal, docs issue, migration guide |
| unique_id addition | HIGH | Verified via PR, docs RST, format specification |
| SpriteFrames format unchanged | HIGH | No changes found in changelog, PRs, or release notes |
| TileSet format unchanged | HIGH | Only editor bug fixes; no format changes |
| Export CLI unchanged | MEDIUM | No new CLI flags found, but delta patch feature not fully documented |
| Import pipeline unchanged | MEDIUM | No changes found, but limited documentation |
| project.godot format | HIGH | Only new defaults for new projects; no structural changes |

## Gaps to Address

- Verify Godot 4.5 loads files without `load_steps` (needed to confirm we can drop it unconditionally vs. needing version branching)
- Confirm exact `unique_id` integer format (32-bit signed? unsigned? range?)
- Check if delta PCK patching introduces any new CLI flags not yet documented
- Run full E2E suite against 4.6.1 to discover any undocumented behavioral changes
