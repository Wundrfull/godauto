---
name: gdauto:validate
description: Incremental project validation -- text-format checks, scene/sprite/tileset validation, and headless Godot runtime test
arguments:
  - name: path
    description: Path to Godot project directory (defaults to current directory)
    required: false
    default: "."
allowed_tools:
  - Bash
  - Read
  - Glob
  - Grep
---

# gdauto:validate -- Incremental Project Validation

Run multi-layer validation on a Godot project. Catches issues that
text-format validation alone misses: UID mismatches, broken resource
imports, class_name conflicts, and serialization bugs.

## Validation Layers

Execute each layer in order. Collect all errors and warnings before
reporting. Do not stop at the first failure -- run all layers so the
report is complete.

### Layer 1: Project structure (no Godot binary needed)

```bash
auto-godot project validate {{ path }} --check-only 2>&1
```

Capture exit code and stdout/stderr. Non-zero exit means issues found.

### Layer 2: Scene validation (no Godot binary needed)

Find all .tscn files in the project and validate each one:

```bash
for f in $(find {{ path }} -name '*.tscn' -not -path '*/.godot/*' -not -path '*/.import/*'); do
  echo "--- $f ---"
  auto-godot scene validate "$f" 2>&1
done
```

Record each file's pass/fail status and any warnings.

### Layer 3: SpriteFrames validation (no Godot binary needed)

Find all .tres files that contain SpriteFrames and validate them:

```bash
for f in $(grep -rl 'type="SpriteFrames"' {{ path }} --include='*.tres' | grep -v '\.godot/' | grep -v '\.import/'); do
  echo "--- $f ---"
  auto-godot sprite validate "$f" 2>&1
done
```

If no SpriteFrames .tres files exist, skip this layer and note it.

### Layer 4: Tileset validation (no Godot binary needed)

Find all .tres files that contain TileSet and validate them:

```bash
for f in $(grep -rl 'type="TileSet"' {{ path }} --include='*.tres' | grep -v '\.godot/' | grep -v '\.import/'); do
  echo "--- $f ---"
  auto-godot tileset validate "$f" 2>&1
done
```

If no TileSet .tres files exist, skip this layer and note it.

### Layer 5: Headless Godot import (requires Godot binary)

Trigger resource import to sync UIDs and generate .import files:

```bash
cd {{ path }} && godot --headless --import 2>&1
```

Parse output for lines containing `ERROR` or `WARNING`. These indicate
resources that Godot cannot load despite passing text-format checks.

If `godot` is not on PATH and GODOT_PATH is not set, skip this layer
and note that headless validation was skipped. Do not fail.

### Layer 6: Headless Godot runtime load test (requires Godot binary)

Run the engine briefly to catch runtime load errors:

```bash
cd {{ path }} && godot --headless --quit-after 3 2>&1
```

Parse output for:
- `ERROR` lines: these are hard failures (missing resources, class conflicts)
- `WARNING` lines: these are soft issues (deprecated features, minor problems)
- `Failed to load resource` patterns
- `class_name already in use` patterns
- `Invalid UID` patterns
- `Cannot instance scene` patterns

If Godot is not available, skip and note it.

## Report Format

After all layers complete, produce a summary report:

```
=== Validation Report: {{ path }} ===

Layer 1 (project structure): PASS / FAIL (N issues)
Layer 2 (scenes):            PASS / FAIL (N/M scenes passed)
Layer 3 (SpriteFrames):      PASS / FAIL / SKIPPED (N/M resources passed)
Layer 4 (TileSets):          PASS / FAIL / SKIPPED (N/M resources passed)
Layer 5 (headless import):   PASS / FAIL / SKIPPED (N errors, M warnings)
Layer 6 (runtime load):      PASS / FAIL / SKIPPED (N errors, M warnings)

Issues found:
  - [Layer N] file:line -- description
  - [Layer N] file:line -- description
  ...

Verdict: ALL CLEAR / N issues to fix
```

List every issue with its source layer and specific file reference.
Group errors before warnings. If all layers pass, report "ALL CLEAR".

## When to Run

- After any batch of scene or resource changes
- After sprite export or import operations
- Before declaring a build phase complete
- After resolving validation errors (to confirm the fix)

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Layer 5/6 skipped | Godot binary not found | Set GODOT_PATH or add godot to PATH |
| `Failed to load resource` | Missing .import file | Layer 5 should fix this; re-run |
| `Invalid UID` after file move | Stale .import file | Delete the .import file, re-run Layer 5 |
| `class_name already in use` | Duplicate class_name or autoload collision | Rename one of the conflicting scripts |
| Layer 2 pass but Layer 6 fail | Text-valid but runtime-invalid | Check ExtResource serialization and res:// paths |
