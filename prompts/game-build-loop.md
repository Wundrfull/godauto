# Game Build Loop: Iterative Game Creation with Gap Discovery

A self-contained guide for building a game using auto-godot + pixel-mcp + Aseprite on a fresh machine. Claude attempts to build the entire game without the Godot editor, logging every blocker for later tool development.

## Prerequisites

You need these installed before starting:

| Tool | Required | How to get it |
|------|----------|---------------|
| **Python 3.12+** | Yes | https://python.org or `winget install Python.Python.3.12` |
| **uv** | Yes | `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` or `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Godot 4.5+** (console build) | Yes | https://godotengine.org/download -- grab the "console" or "headless" build for your OS |
| **Aseprite** | Yes | https://www.aseprite.org/ (Steam or direct purchase; has CLI built in) |
| **Claude Code** | Yes | `npm install -g @anthropic-ai/claude-code` |
| **Git** | Yes | https://git-scm.com/ |

## Step 1: Clone and install auto-godot

```bash
git clone https://github.com/wundrfull/auto-godot.git
cd auto-godot
uv sync --dev
```

Verify it works:
```bash
uv run auto-godot --version
uv run auto-godot --help
```

You should see all command groups: project, scene, script, sprite, tileset, animation, audio, etc.

## Step 2: Set up pixel-mcp

pixel-mcp is an MCP server that lets Claude create pixel art through Aseprite headlessly.

```bash
# Download the latest release for your platform
# https://github.com/willibrandon/pixel-mcp/releases

# Windows: download pixel-mcp.exe
# macOS/Linux: download the appropriate binary

# Place it somewhere on your system, e.g.:
# Windows: C:\tools\pixel-mcp.exe
# macOS/Linux: ~/tools/pixel-mcp
```

Create the pixel-mcp config file:

**Windows:** `%USERPROFILE%\.config\pixel-mcp\config.json`
**macOS/Linux:** `~/.config/pixel-mcp/config.json`

```json
{
  "aseprite_path": "REPLACE_WITH_YOUR_ASEPRITE_PATH",
  "temp_dir": "REPLACE_WITH_A_TEMP_DIR",
  "timeout": 30
}
```

Example paths:
- **Windows (Steam):** `"aseprite_path": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Aseprite\\Aseprite.exe"`
- **Windows (direct):** `"aseprite_path": "C:\\Program Files\\Aseprite\\Aseprite.exe"`
- **macOS:** `"aseprite_path": "/Applications/Aseprite.app/Contents/MacOS/aseprite"`
- **Linux:** `"aseprite_path": "/usr/bin/aseprite"` or wherever you installed it

## Step 3: Configure Claude Code MCP servers

Add pixel-mcp to your Claude Code settings so it's available as MCP tools.

Edit your Claude Code settings (`.claude/settings.json` in your home directory or project):

```json
{
  "mcpServers": {
    "pixel-mcp": {
      "command": "REPLACE_WITH_PATH_TO_PIXEL_MCP_BINARY"
    }
  }
}
```

## Step 4: Set environment variables

Claude needs to know where your tools live. Set these in your shell profile or before launching Claude Code:

```bash
# Path to Godot console binary (for headless operations)
export GODOT_PATH="/path/to/Godot_v4.6-stable_console"

# Path to Aseprite binary (for sprite export)
export ASEPRITE_PATH="/path/to/aseprite"
```

**Windows PowerShell:**
```powershell
$env:GODOT_PATH = "C:\path\to\Godot_v4.6-stable_win64_console.exe"
$env:ASEPRITE_PATH = "C:\Program Files (x86)\Steam\steamapps\common\Aseprite\Aseprite.exe"
```

## Step 5: Create the game project repo

```bash
mkdir cookie-cosmos
cd cookie-cosmos
git init
```

## Step 6: Create CLAUDE.md

Create this file at `cookie-cosmos/CLAUDE.md` so Claude has the right context:

```markdown
## Project

Cookie Cosmos -- an idle clicker game built entirely via CLI tools (no Godot editor).

## Toolchain

- **auto-godot** -- CLI for Godot file manipulation. Installed at: [your auto-godot path]
  Run with: `uv run --project /path/to/auto-godot auto-godot <command>`
  Or if installed globally: `auto-godot <command>`
- **pixel-mcp** -- MCP server for Aseprite pixel art creation (available as MCP tools)
- **Aseprite CLI** -- Headless sprite export via `aseprite -b` (no GUI window opens)
- **Godot 4.6** -- Game engine. Console binary at GODOT_PATH env var.

## Asset Pipeline

1. Create pixel art with pixel-mcp MCP tools (create_canvas, draw_pixels, etc.)
2. Export from Aseprite: `auto-godot sprite export art/<name>.aseprite -o assets/sprites/<name>`
3. Import to Godot: `auto-godot sprite import-aseprite assets/sprites/<name>/<name>.json`
4. Assign to scene: `auto-godot scene set-resource --scene <scene> --node <node> --property sprite_frames --resource res://assets/sprites/<name>/<name>.tres --type SpriteFrames`

## Directory Layout

- `art/` -- Raw .aseprite source files (created by pixel-mcp)
- `assets/sprites/` -- Exported PNGs, JSONs, and .tres SpriteFrames
- `scenes/` -- Godot .tscn scene files
- `scripts/` -- GDScript files
- `scripts/autoload/` -- Singleton managers
- `theme/` -- UI theme resources
- `shaders/` -- Shader resources
- `animations/` -- Animation library resources

## Constraints

- NEVER open the Godot editor GUI. Everything is CLI only.
- NEVER write .tscn, .tres, or project.godot files by hand. Use auto-godot commands.
- ALL pixel art is created through pixel-mcp MCP tools.
- Log every blocker to blockers.md with the format described in the build prompt.
```

## Step 7: Verify everything works

```bash
# In the cookie-cosmos directory:
uv run --project /path/to/auto-godot auto-godot --version
# Should print version

uv run --project /path/to/auto-godot auto-godot project create TestProject --output .
# Should create TestProject/ with project.godot

# Clean up test
rm -rf TestProject/

# Verify Aseprite CLI (no GUI opens)
"$ASEPRITE_PATH" --version
# Should print Aseprite version

# Verify pixel-mcp (in Claude Code, you should see MCP tools like create_canvas)
```

## Step 8: Launch Claude Code and paste the prompt

```bash
cd cookie-cosmos
claude
```

Paste everything below the `---` line as your first message to Claude Code.

---

## THE PROMPT

You are building a complete idle clicker game in Godot 4.6 using ONLY command-line tools. You must never open the Godot editor GUI. Your entire workflow uses three tools:

1. **auto-godot** -- CLI for Godot file manipulation (scenes, scripts, project config, resources)
2. **pixel-mcp** -- MCP server for creating pixel art in Aseprite (create_canvas, draw_pixels, draw_rectangle, draw_circle, set_palette, add_layer, export_spritesheet, etc.)
3. **Aseprite CLI** -- Headless sprite export (`aseprite -b` for batch mode, no GUI needed)

### Your Goal

Build a playable idle clicker game called "Cookie Cosmos" with these features:

**Core gameplay:**
- A large cookie in the center that the player clicks for points
- Score display showing current cookies
- Cookies-per-second display for passive income
- Click multiplier that increases with upgrades

**Upgrade shop (3 tiers):**
- Auto-Clicker ($50): adds 1 cookie/sec passive income
- Double Click ($200): doubles click value
- Golden Cookie ($1000): 10x click value for 10 seconds (cooldown)

**Visual polish:**
- Animated cookie sprite (idle wobble + click squish)
- Particle burst on click
- Score popup text that floats up and fades
- Background gradient or pattern
- UI theme with consistent colors (dark blue bg, gold accents)

**Audio (placeholder setup):**
- Click sound effect node
- Background music node
- Upgrade purchase sound

**Save system:**
- Auto-save on upgrade purchase
- Save/load via JSON to user://

### Rules

1. **Use auto-godot for ALL Godot file operations.** Never write .tscn, .tres, or project.godot files by hand. Use `auto-godot scene create-simple`, `auto-godot scene add-node`, `auto-godot script create`, etc.

2. **Use pixel-mcp MCP tools for ALL art creation.** Create sprites, animations, and UI art through the MCP server tools (create_canvas, draw_pixels, set_palette, add_layer, export_spritesheet, etc.).

3. **Use Aseprite CLI for sprite export.** After pixel-mcp creates .aseprite files, export with:
   ```
   auto-godot sprite export art/cookie.aseprite -o assets/sprites/cookie
   ```
   Or directly: `$ASEPRITE_PATH -b art/cookie.aseprite --sheet assets/sprites/cookie/cookie_sheet.png --data assets/sprites/cookie/cookie.json --format json-array --sheet-type packed --trim --list-tags`

4. **Use auto-godot sprite import-aseprite for Godot integration:**
   ```
   auto-godot sprite import-aseprite assets/sprites/cookie/cookie.json -o assets/sprites/cookie/cookie.tres
   ```

5. **Log EVERY blocker.** When you cannot do something with the available tools, write it to `blockers.md` with this exact format:
   ```markdown
   ## BLOCKER: [short description]
   - **What I tried:** [exact command or MCP tool call]
   - **What happened:** [error message or limitation encountered]
   - **What I needed:** [the ideal command/tool that would unblock this]
   - **Workaround:** [what I did instead, or "none -- fully blocked"]
   - **Category:** [auto-godot | pixel-mcp | aseprite | godot | workflow]
   - **Impact:** [critical | high | medium | low]
   ```

6. **Log progress.** After completing (or attempting) each phase, append to `progress.md`:
   ```markdown
   ## Phase N: [phase name]
   - **Status:** [complete | partial | blocked]
   - **What worked:** [list of successful steps]
   - **Blockers hit:** [count and references to blockers.md]
   - **Files created:** [list]
   ```

### Build Phases

Execute these phases in order. Push as far as you can in each phase before moving to the next. Do NOT skip phases even if earlier ones have blockers.

**Phase 1: Project Scaffold**
- `auto-godot project create CookieCosmos --output .`
- Configure display (720x1280 portrait, canvas_items stretch, nearest filter)
- Configure rendering (mobile)
- Set up input actions (click, ui_upgrade)
- Name physics layers
- Set the main scene

**Phase 2: Create Pixel Art**
Using pixel-mcp MCP tools:
- Create a 64x64 cookie sprite with idle animation (4 frames, gentle wobble/rotate)
- Create a 64x64 cookie sprite with click animation (3 frames, squish and bounce back)
- Create a 16x16 particle sprite (small sparkle/star, 3 frames)
- Create a 32x32 upgrade icon set (3 icons for the 3 upgrades)
- Create UI panel background art (9-patch or simple panel)
- Use a warm palette: browns for cookie, gold for accents, deep blue for background
- Export all from Aseprite using `auto-godot sprite export` or Aseprite CLI batch mode

**Phase 3: Import Assets into Godot**
- `auto-godot sprite import-aseprite` for each sprite JSON
- `auto-godot sprite validate` each generated .tres
- `auto-godot sprite list-animations` to verify animation names, frame counts, FPS

**Phase 4: Build Main Scene**
- Create main scene with Control root using `auto-godot scene create-simple`
- Add VBoxContainer layout for score/buttons
- Add score Label, cookies/sec Label
- Add AnimatedSprite2D for cookie (assign SpriteFrames via `auto-godot scene set-resource`)
- Add a TextureButton or Button overlaying the cookie for click detection
- Add CPUParticles2D for click burst via `auto-godot particle add`
- Set anchor presets via `auto-godot scene set-anchor --preset full_rect`
- Create and assign UI theme via `auto-godot theme create` + `auto-godot scene set-resource`

**Phase 5: Build Shop Scene**
- Create shop scene using `auto-godot scene from-template --template ui-panel`
- Add 3 upgrade buttons with labels showing name and cost
- Add labels for upgrade descriptions and current level
- Create shop script with signal for purchases

**Phase 6: Write Game Scripts**
Using `auto-godot script create`, `auto-godot script add-method`, `auto-godot script add-var`, `auto-godot script add-export`, `auto-godot script add-signal`:
- Main scene script: click handling, score display update, passive income tick
- GameManager autoload: score state, upgrade tracking, click value calculation
- SaveManager autoload: save_game(data) and load_game() via JSON to user://save.json
- Shop script: upgrade purchase logic, cost display, afford/disable checking

**Phase 7: Wire Everything Together**
- Connect button pressed signals via `auto-godot signal connect`
- Instance shop into main scene via `auto-godot scene add-instance`
- Attach scripts to nodes via `auto-godot script attach`
- Register autoloads via `auto-godot project add-autoload`
- Set main scene via `auto-godot project set-main-scene`
- Add Timer nodes via `auto-godot scene add-timer` for passive income and auto-save

**Phase 8: Audio Setup**
- Create audio bus layout via `auto-godot audio create-bus-layout` (Master, SFX, Music)
- Add AudioStreamPlayer nodes via `auto-godot audio add-player` (click sound, bg music, upgrade sound)
- Wire audio playback into game scripts

**Phase 9: Visual Polish**
- Create score popup animation via `auto-godot animation create-library` + `auto-godot animation add-track`
- Add cookie scale animation on click
- Add background ColorRect via `auto-godot scene add-node`
- Set anchor presets on all UI elements via `auto-godot scene set-anchor`
- Create and assign shader effects if desired via `auto-godot shader create`

**Phase 10: Validation and Testing**
- `auto-godot scene validate` every .tscn file
- `auto-godot project validate` the entire project
- `auto-godot project stats` for a project overview
- `auto-godot scene list-nodes` on every scene
- `auto-godot resource list --scene` on main scene to verify all resources resolve
- `auto-godot scene count-nodes` for total node count
- Attempt to run the game headlessly: `$GODOT_PATH --headless --path . --quit-after 5` (just checks it loads without crash)

### After All Phases

Write a final summary to `summary.md`:

```markdown
# Cookie Cosmos Build Summary

## Completion
- Phases completed: X/10
- Phases partially completed: X/10
- Total blockers logged: N
- Critical blockers (no workaround): N

## Tool Usage Stats
- auto-godot commands used successfully: [list]
- auto-godot commands that failed: [list]
- pixel-mcp tools used: [list]
- Aseprite CLI invocations: N
- Files written by hand (workarounds): N

## Top Blockers (by impact)
1. [blocker description + category]
2. [blocker description + category]
3. [blocker description + category]
4. [blocker description + category]
5. [blocker description + category]

## What Worked Well
[list the smoothest parts of the workflow]

## What Was Hardest
[list the most painful parts, even if eventually worked around]

## Recommended New Tools/Commands
[list specific commands that should be added to auto-godot or pixel-mcp]

## Generated File Inventory
- Scenes (.tscn): [count and list]
- Resources (.tres): [count and list]
- Scripts (.gd): [count and list]
- Sprites (.aseprite): [count and list]
- Exported PNGs: [count and list]
```

### Critical Behaviors

- **Do NOT give up at the first blocker.** Log it and move on to the next step. Come back to blocked steps later if you find a workaround.
- **Do NOT write Godot files by hand** unless completely blocked with no alternative. If you must, log it as a critical blocker with "workaround: wrote file by hand".
- **Do NOT ask the user questions.** Make your best judgment and keep going. Log uncertainty as blockers.
- **Push through ALL 10 phases** even if earlier phases had blockers. Partial progress in every phase is more valuable than perfect completion of phase 1.
- **Be maximally specific in blocker logs.** Bad: "couldn't add texture". Good: "Ran `auto-godot scene set-resource --scene scenes/main.tscn --node CookieSprite --property texture --resource res://assets/sprites/cookie.png --type Texture2D` and got exit code 1: 'Node CookieSprite not found in scene'. The node was added in a previous step but may have a different parent path."
- **Use `--json` flag** on auto-godot commands when you need to parse output for the next step.
- **Verify after every major operation** using `auto-godot scene list-nodes`, `auto-godot scene validate`, `auto-godot resource inspect`.
- **Commit after each phase** with a descriptive message. This creates a history of what was built and when.

### Environment Check

Before starting Phase 1, run these checks and log any failures:

```bash
# auto-godot
auto-godot --version
auto-godot --help

# Aseprite (should print version, no GUI opens)
$ASEPRITE_PATH --version 2>/dev/null || echo "BLOCKER: Aseprite not found at ASEPRITE_PATH"

# Godot (should print version)
$GODOT_PATH --version 2>/dev/null || echo "BLOCKER: Godot not found at GODOT_PATH"

# pixel-mcp (should be available as MCP tools -- try calling get_sprite_info or similar)
```

Now begin with Phase 1. Push as far as you can through all 10 phases. Log everything to blockers.md, progress.md, and finish with summary.md.
