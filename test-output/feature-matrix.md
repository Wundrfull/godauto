# Feature Matrix -- Idle Clicker Game Build

Tracks pass/fail status of each feature across test runs. Each column is a
timestamped run triggered by a NEW_PUSH to main.

## Art Pipeline (pixel-mcp + Aseprite)

| Feature | Tool Chain | 20260410-221642 | 20260411-001928 |
|---------|-----------|-----------------|-----------------|
| Create click target canvas (32x32+) | pixel-mcp: create_canvas | SKIP | PASS |
| Draw animated frames (idle + clicked) | pixel-mcp: draw_pixels | SKIP | PASS |
| Create currency icon (16x16) | pixel-mcp: create_canvas, draw_pixels | SKIP | PASS |
| Create background texture | pixel-mcp: create_canvas, fill_area | SKIP | PASS |
| Create UI button icons | pixel-mcp: create_canvas, draw_pixels | SKIP | PASS |
| Create effect/particle sprite | pixel-mcp: create_canvas, draw_pixels | SKIP | PASS |
| Export spritesheet PNG | Aseprite CLI: -b --sheet | PASS | PASS |
| Export JSON metadata | Aseprite CLI: --data --format json-array | PASS | PASS |

## auto-godot CLI (core commands)

| Feature | Command | 20260410-221642 | 20260411-001928 |
|---------|---------|-----------------|-----------------|
| Initialize Godot 4.6 project | project create | PASS | PASS |
| Import Aseprite JSON to SpriteFrames .tres | sprite import-aseprite | PASS | PASS |
| Create main menu scene | scene create-simple | PASS | PASS |
| Create game screen scene | scene create-simple | PASS | PASS |
| Create settings scene | scene create-simple | PASS | PASS |
| Add Button nodes | scene add-node | PASS | PASS |
| Add Label nodes | scene add-node | PASS | PASS |
| Add VBoxContainer/HBoxContainer | scene add-node | PASS | PASS |
| Add AnimatedSprite2D | scene add-node | PASS | PASS |
| Generate click handler script | script create | PASS | PASS |
| Generate currency manager singleton | script create | PASS | PASS |
| Generate upgrade system script | script create | PASS | PASS |
| Generate save/load script | script create | PASS | PASS |
| Generate scene transition script | script create | PASS | PASS |
| Create UI theme | theme create | PASS | PASS |
| Create click feedback animation | animation create-library | PASS | PASS |
| Create number popup animation | animation add-track | PASS | PASS |
| Create idle animation | animation add-track | PASS | PASS |
| Script add-method body indentation | script add-method --body | FAIL | -- |
| Project set-config string quoting | project set-config --value | FAIL | -- |

## Godot 4.6 Validation

| Feature | Validation Method | 20260410-221642 | 20260411-001928 |
|---------|------------------|-----------------|-----------------|
| Resources import without errors | --headless --import | PASS | PASS |
| Scene loads without errors | --headless --quit-after 3 | PASS | PASS |
| No class_name conflicts | stderr check | PASS | PASS |
| No missing resource errors | stderr check | PASS | PASS |
| Game runs to main menu | --headless --quit-after 5 | PASS | PASS |

## Run History

| Run Timestamp | Commit SHA | Pass | Fail | Skip | Blocked | Issues Filed |
|---------------|-----------|------|------|------|---------|-------------|
| 20260410-221642 | 677a15f | 79 | 2 | 6 | 0 | 2 bugs |
| 20260411-001928 | bfd9ce2 | 28 | 0 | 0 | 0 | 0 new |

---

Legend:
- PASS: feature worked correctly
- FAIL: feature exists but produced errors or invalid output (files bug issue)
- SKIP: feature/command not yet implemented (files gap issue)
- BLOCKED: depends on another feature that is currently FAIL/SKIP
