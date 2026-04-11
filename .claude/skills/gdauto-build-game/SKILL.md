---
name: gdauto:build-game
description: Full game build workflow with validation checkpoints at each phase -- encodes lessons from production builds
arguments:
  - name: project
    description: Path to the Godot project directory (defaults to current directory)
    required: false
    default: "."
allowed_tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# gdauto:build-game -- Full Game Build Workflow

Orchestrate a complete game build using auto-godot CLI commands with
validation checkpoints after each phase. This workflow encodes lessons
learned from production builds where blind construction across multiple
phases led to 12+ errors surfacing at once during the first runtime test.

## Core Principle

**Validate early, validate often.** Never build more than one phase
without running validation. The cost of catching an error early is
one fix; the cost of catching it late is debugging 12 interleaved issues.

## Build Phases

### Phase 1: Project Setup

```bash
auto-godot setup --auto
auto-godot project info {{ project }}
```

Verify: Godot binary found, project.godot exists, project version is 4.5+.

If project does not exist yet:
```bash
# Create project structure manually -- auto-godot operates on existing projects
mkdir -p {{ project }}/scenes {{ project }}/scripts {{ project }}/scripts/autoload
mkdir -p {{ project }}/assets/sprites {{ project }}/assets/ui {{ project }}/assets/fonts
```

**CHECKPOINT**: `auto-godot project validate {{ project }}`

### Phase 2: Asset Pipeline

For each sprite/asset needed:

1. Create pixel art (via pixel-mcp Aseprite tools or manual placement)
2. Export from Aseprite to spritesheet + JSON:
   ```bash
   aseprite -b art/<name>.aseprite --sheet assets/sprites/<name>/<name>_sheet.png --data assets/sprites/<name>/<name>.json --format json-array --sheet-type packed
   ```
3. Import into Godot as SpriteFrames:
   ```bash
   auto-godot sprite import-aseprite assets/sprites/<name>/<name>.json -o assets/sprites/<name>/<name>.tres
   ```

**CHECKPOINT after each sprite**:
```bash
auto-godot sprite validate assets/sprites/<name>/<name>.tres
```

**CHECKPOINT after all sprites**:
```bash
auto-godot import --project {{ project }}
```

This syncs UIDs and generates .import files. Without this step,
ExtResource paths will break in scenes.

### Phase 3: Scene Construction

Build scenes incrementally. After EVERY scene modification, validate.

**Create the main scene**:
```bash
auto-godot scene create-simple --root-type <type> --root-name Root -o {{ project }}/scenes/main.tscn
```

Root type selection:
- UI games (clickers, card games, menus): use `Control` root, then
  `auto-godot scene set-anchor --scene ... --node Root --preset full_rect`
- Action/platformer games: use `Node2D` root
- 3D games: use `Node3D` root

**Add nodes**:
```bash
auto-godot scene add-node --scene <path> --name <name> --type <type> --parent <parent> --property 'key=value'
```

**Critical rules** (violations cause silent failures):
- Use single quotes for `--property` values containing `$`:
  `--property 'text=Buy ($50)'`
- Container children need size_flags:
  `--property 'size_flags_vertical=3'`
- Non-interactive overlays need:
  `--property 'mouse_filter=2'`
- AnimatedSprite2D is Node2D, NOT Control. Do not place under
  CenterContainer/VBoxContainer directly.
- `--class-name` must never match an autoload singleton name.

**CHECKPOINT after every 3-5 node additions**:
```bash
auto-godot scene validate {{ project }}/scenes/<name>.tscn
```

### Phase 4: Scripts and Autoloads

**Create scripts**:
```bash
auto-godot script create --path {{ project }}/scripts/<name>.gd --class-name <ClassName> --extends <BaseType>
```

**Attach scripts to nodes**:
```bash
auto-godot scene set-resource --scene <scene> --node <node> --property script --resource 'res://scripts/<name>.gd' --type GDScript
```

**Register autoloads**:
```bash
auto-godot project add-autoload --project {{ project }} --name <Name> --path 'res://scripts/autoload/<name>.gd'
```

**CHECKPOINT**:
```bash
auto-godot project validate {{ project }} --check-only
auto-godot project list-autoloads --project {{ project }}
```

### Phase 5: Signals and Input

**Register input actions**:
```bash
auto-godot project add-input --project {{ project }} --action <name> --key <KEY>
```

**Connect signals** (in GDScript, not via CLI):
Ensure signal connections in scripts match the node names in scenes.

**CHECKPOINT**:
```bash
auto-godot project list-inputs --project {{ project }}
auto-godot project validate {{ project }}
```

### Phase 6: Audio, Particles, Themes (optional)

**Audio**:
```bash
auto-godot audio create-bus --project {{ project }} --name <BusName>
```

**Particles**:
```bash
auto-godot particle create --type <type> -o {{ project }}/scenes/particles/<name>.tscn
```

**Themes**:
```bash
auto-godot theme create --base-font-size 16 -o {{ project }}/assets/ui/theme.tres
```

**CHECKPOINT**: `auto-godot project validate {{ project }}`

### Phase 7: Full Validation

Run the complete validation suite. This is the final gate before
declaring the build complete.

```bash
# Text-format validation (fast, no Godot binary)
auto-godot project validate {{ project }}

# Validate every scene
for f in $(find {{ project }} -name '*.tscn' -not -path '*/.godot/*'); do
  auto-godot scene validate "$f"
done

# Validate every SpriteFrames resource
for f in $(grep -rl 'type="SpriteFrames"' {{ project }} --include='*.tres' | grep -v '\.godot/'); do
  auto-godot sprite validate "$f"
done

# Resource import (requires Godot)
auto-godot import --project {{ project }}

# Runtime load test (requires Godot)
cd {{ project }} && godot --headless --quit-after 3 2>&1
```

Parse the headless Godot output for ERROR and WARNING lines.
If any errors found, diagnose and fix before proceeding.

### Phase 8: Gameplay Test

```bash
auto-godot debug connect --project {{ project }}
auto-godot debug tree --project {{ project }}
auto-godot debug output --project {{ project }}
```

Inspect the live scene tree to verify:
- All nodes are present and typed correctly
- Sprites are visible (not off-screen)
- UI layout is correct (containers have children, size_flags applied)
- No runtime errors in output

## Error Recovery

If validation fails at any checkpoint:

1. Read the error message carefully. auto-godot errors include
   an error code and fix suggestion.
2. Apply the fix using the appropriate auto-godot command.
3. Re-run the checkpoint validation.
4. Only proceed to the next phase after the checkpoint passes.

Common recovery patterns:

| Error | Recovery |
|-------|----------|
| Missing .import files | Run `auto-godot import --project {{ project }}` |
| ExtResource path broken | Check the res:// path matches actual file location |
| class_name conflict | `auto-godot project list-autoloads` to find collisions |
| Node not visible | Use `/gdauto:fix-scene` to diagnose layout issues |
| Script errors | `auto-godot project validate --check-only` for syntax check |

## Workflow Summary

```
Setup --> Assets --> Scenes --> Scripts --> Signals --> Polish --> Validate --> Test
  |         |          |          |           |          |          |
  v         v          v          v           v          v          v
 [CP]     [CP/ea]    [CP/3-5]   [CP]        [CP]      [CP]     [FULL]    [LIVE]
```

CP = checkpoint validation. Never skip checkpoints.
