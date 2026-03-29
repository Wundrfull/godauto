# Technology Stack: Godot 4.6 Compatibility Audit

**Project:** gdauto v1.1
**Researched:** 2026-03-28

## Stack Assessment

No stack changes are required for the Godot 4.6 compatibility audit. The existing v1.0 technology stack is fully adequate.

## Current Stack (Unchanged)

| Technology | Version | Status for 4.6 |
|------------|---------|-----------------|
| Python | >= 3.12 | No change needed |
| Click | 8.3.x | No change needed |
| rich-click | 1.9.x | No change needed |
| Custom .tscn/.tres parser | n/a | Needs format updates (load_steps, unique_id) |
| configparser (stdlib) | stdlib | No change needed for project.godot |
| json (stdlib) | stdlib | No change needed |
| dataclasses (stdlib) | stdlib | SceneNode needs new field |
| Pillow | 12.1.x (optional) | No change needed |
| pytest | 9.0.x | No change needed; golden files need updating |
| ruff | 0.11.x | No change needed |
| mypy | 1.19.x | No change needed |
| uv | 0.11.x | No change needed |

## New Dependencies

None required. The changes are entirely within existing code (parser updates, builder updates, golden file updates).

## Godot Binary Version

| Engine Version | Support Level |
|----------------|---------------|
| Godot 4.5.x | Baseline (read/write compat maintained) |
| Godot 4.6.0 | Full support (load_steps removal, unique_id) |
| Godot 4.6.1 | Full support (no additional format changes) |
| Godot 4.7+ | Unknown (monitor for future format changes) |

## Testing Infrastructure

The only infrastructure change is ensuring the E2E test environment has Godot 4.6.1 available on PATH. The existing `@pytest.mark.requires_godot` marker and `godot_backend.py` wrapper handle binary discovery. The wrapper should be updated to detect and report the Godot version in test output for clarity.

## Sources

- No new stack research needed; assessment based on v1.0 STACK.md and Godot 4.6 changelog analysis
