---
name: gdauto:fix-scene
description: Diagnose and fix common Godot scene layout issues -- container sizing, input blocking, off-screen nodes, type mismatches
arguments:
  - name: scene
    description: Path to the .tscn file to diagnose
    required: true
allowed_tools:
  - Bash
  - Read
  - Grep
  - Glob
  - Edit
---

# gdauto:fix-scene -- Scene Layout Diagnostics and Fixes

Diagnose and repair common Godot scene layout issues that cause
invisible nodes, broken input, collapsed containers, and rendering
problems. These are the issues that text-format validation misses
but break the game visually.

## Diagnosis Workflow

Run each check against `{{ scene }}`. Collect all findings before
proposing fixes. Use auto-godot CLI commands for structured inspection.

### Step 1: Structural validation

```bash
auto-godot scene validate '{{ scene }}'
```

If this fails, fix structural issues first before continuing.

### Step 2: Get the full node tree

```bash
auto-godot scene list-nodes --scene '{{ scene }}'
```

Save the output -- you will reference it in every subsequent check.

### Step 3: Run diagnostic checks

Execute ALL of the following checks against the scene. For each check,
use `auto-godot scene inspect-node` or `auto-godot scene find-nodes`
as needed.

#### Check A: Node2D children in Control containers

**Problem**: CenterContainer, VBoxContainer, HBoxContainer, GridContainer,
MarginContainer, and ScrollContainer only layout Control-derived children.
Node2D-derived nodes (Sprite2D, AnimatedSprite2D, CharacterBody2D, etc.)
are ignored by container layout.

**How to detect**: For each container node (type contains "Container"),
inspect its children. If any child inherits Node2D, flag it.

Common Node2D types that get misplaced:
- Sprite2D, AnimatedSprite2D
- CharacterBody2D, StaticBody2D, RigidBody2D
- Area2D, CollisionShape2D
- Camera2D, Path2D, Line2D

**Fix**: Wrap the Node2D child in a Control node with `mouse_filter = 2`.

#### Check B: Missing size_flags on container children

**Problem**: Children of VBoxContainer, HBoxContainer, GridContainer need
`size_flags_vertical = 3` (FILL+EXPAND) or `size_flags_horizontal = 3`
to fill available space. Without these flags, children collapse to
minimum size.

**How to detect**: For each VBox/HBox/Grid container, inspect children.
If a Control child has no explicit `size_flags_vertical` or
`size_flags_horizontal` property set, flag it.

- VBoxContainer children typically need `size_flags_vertical = 3`
- HBoxContainer children typically need `size_flags_horizontal = 3`
- ScrollContainer children need BOTH flags set to 3

**Fix**:
```bash
auto-godot scene set-property --scene '{{ scene }}' --node '<name>' --property 'size_flags_vertical=3'
```

#### Check C: Input blocking by overlays

**Problem**: Later siblings in the scene tree render on top and block
mouse input. Non-interactive nodes that overlap interactive ones
swallow clicks.

**How to detect**: Look for nodes that:
1. Are positioned after interactive nodes (Button, TextureButton, etc.)
   in sibling order
2. Do NOT have `mouse_filter = 2` (IGNORE)
3. Are Control-derived (only Controls receive input)

Common culprits: Label, Panel, TextureRect used as decorative overlays.

**Fix**:
```bash
auto-godot scene set-property --scene '{{ scene }}' --node '<name>' --property 'mouse_filter=2'
```

#### Check D: Invisible PanelContainer

**Problem**: PanelContainer has no visual appearance by default. Without
a Theme or StyleBoxFlat override, it renders as invisible.

**How to detect**: Find all PanelContainer nodes. If a PanelContainer has
no `theme` or `theme_override_styles/panel` property, flag it.

**Fix**: Use `auto-godot theme create` to generate a theme, or set
a StyleBoxFlat override directly.

#### Check E: Off-screen nodes

**Problem**: Nodes with position values far outside the viewport are
invisible to the player.

**How to detect**: Inspect nodes with `position` properties. If x or y
exceeds 4096 or is negative beyond -4096, flag as likely off-screen.
For the root node, check if anchor_preset is set for Control roots.

**Fix**:
```bash
auto-godot scene set-property --scene '{{ scene }}' --node '<name>' --property 'position=Vector2(0, 0)'
```

#### Check F: Node2D root for UI scenes

**Problem**: UI-heavy scenes (containing mostly Control nodes, buttons,
labels, containers) should use a Control root with `full_rect` anchor
preset, not Node2D. Node2D roots ignore anchoring and container layout.

**How to detect**: If the root node is Node2D or Node3D, count the
proportion of Control-derived descendants. If >50% are Controls,
suggest switching to a Control root.

**Fix**: This requires scene recreation. Suggest using:
```bash
auto-godot scene create-simple --root-type Control --root-name Root -o new_scene.tscn
```
Then migrate child nodes.

#### Check G: Empty containers

**Problem**: Containers with no children serve no purpose and may
indicate incomplete scene construction.

**How to detect**: Find all container-type nodes with zero children
in the node tree.

**Fix**: Either add children or remove the empty container.

## Report Format

After all checks complete, produce a report:

```
=== Scene Diagnosis: {{ scene }} ===

Structure: VALID / INVALID
Nodes: N total

Findings:
  [A] WARN  Node2D child under container: <parent> > <child> (<type>)
  [B] WARN  Missing size_flags: <node> in <container> (needs size_flags_vertical=3)
  [C] WARN  Input blocker: <node> overlaps interactive siblings (set mouse_filter=2)
  [D] WARN  Invisible panel: <node> has no theme or style override
  [E] WARN  Off-screen: <node> at position (<x>, <y>)
  [F] INFO  UI scene with Node2D root: consider Control root with full_rect
  [G] INFO  Empty container: <node> (<type>) has no children

Auto-fixable: N findings
Manual review: M findings
```

## Applying Fixes

After reporting, ask before applying fixes. Group fixes by type:

1. **Safe auto-fixes** (apply without asking):
   - Setting `mouse_filter = 2` on non-interactive overlays
   - Adding missing `size_flags` on container children

2. **Ask first** (require confirmation):
   - Moving off-screen nodes to origin
   - Wrapping Node2D children in Control wrappers
   - Changing root node type

3. **Manual only** (report but do not fix):
   - Empty containers (might be intentional placeholders)
   - Root type changes (requires scene restructuring)

After applying fixes, re-run `auto-godot scene validate` to confirm
the scene is still structurally valid.
