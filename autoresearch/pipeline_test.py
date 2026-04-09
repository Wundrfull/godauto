"""Pipeline test: attempt to build an idle clicker game with gdauto.

Runs each step of the game creation pipeline in an isolated temp directory.
Outputs a single integer: number of steps that succeeded.
Also writes a blockers log with details on what failed and why.

Usage:
    uv run python autoresearch/pipeline_test.py
    # Outputs: METRIC: <N>/<total>
    # Also writes: autoresearch/pipeline_blockers.log
"""

from __future__ import annotations

import json
import os
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from click.testing import CliRunner

from gdauto.cli import cli

BLOCKERS_LOG = Path(__file__).parent / "pipeline_blockers.log"


@dataclass
class StepResult:
    name: str
    category: str
    passed: bool
    exit_code: int
    output: str
    command: list[str]


@dataclass
class PipelineRunner:
    project_dir: Path
    runner: CliRunner = field(default_factory=CliRunner)
    results: list[StepResult] = field(default_factory=list)

    def run(self, name: str, category: str, args: list[str]) -> StepResult:
        """Run a gdauto command and record the result."""
        try:
            result = self.runner.invoke(cli, args, catch_exceptions=False)
            step = StepResult(
                name=name,
                category=category,
                passed=result.exit_code == 0,
                exit_code=result.exit_code,
                output=(result.output or "")[:500],
                command=args,
            )
        except SystemExit as exc:
            step = StepResult(
                name=name,
                category=category,
                passed=False,
                exit_code=getattr(exc, "code", 1) or 1,
                output=f"SystemExit: {exc}",
                command=args,
            )
        except Exception as exc:
            step = StepResult(
                name=name,
                category=category,
                passed=False,
                exit_code=-1,
                output=f"{type(exc).__name__}: {exc}",
                command=args,
            )
        self.results.append(step)
        return step

    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    def total_count(self) -> int:
        return len(self.results)


def run_pipeline(base_dir: Path) -> PipelineRunner:
    """Attempt to build a full idle clicker game with gdauto commands."""
    # project create puts files in base_dir/IdleClicker/
    p = PipelineRunner(project_dir=base_dir)

    p.run("Create project", "project",
          ["project", "create", "IdleClicker", "--output", str(base_dir)])

    # After create, the project lives in base_dir/IdleClicker/
    project_dir = base_dir / "IdleClicker"
    pd = str(project_dir)
    pg = str(project_dir / "project.godot")
    ms = str(project_dir / "scenes" / "main.tscn")

    p.run("Set display 720x1280 portrait", "project",
          ["project", "set-display", "--width", "720", "--height", "1280",
           "--stretch-mode", "canvas_items", "--stretch-aspect", "keep",
           "--texture-filter", "nearest", pg])

    p.run("Set rendering to mobile", "project",
          ["project", "set-rendering", "--method", "mobile", pg])

    p.run("Add click input action", "project",
          ["project", "add-input", "--action", "click",
           "--key", "space", "--mouse", "left", pg])

    p.run("Add ui_upgrade input", "project",
          ["project", "add-input", "--action", "ui_upgrade",
           "--key", "u", pg])

    p.run("Name physics layer 1", "project",
          ["project", "add-layer", "--type", "2d_physics", "--index", "1",
           "--name", "clickables", pg])

    # ── Phase 2: Main Scene ─────────────────────────────────────────
    # scene create needs a JSON definition file
    # project create already made scenes/ dir, but ensure it exists
    scene_def = project_dir / "scenes" / "main_def.json"
    (project_dir / "scenes").mkdir(parents=True, exist_ok=True)
    scene_def.write_text(json.dumps({
        "root": {
            "name": "Main",
            "type": "Control",
            "children": []
        }
    }))

    p.run("Create main scene", "scene",
          ["scene", "create", str(scene_def), "--output", ms])

    p.run("Add VBoxContainer layout", "scene",
          ["scene", "add-node", "--scene", ms,
           "--parent", "Main", "--type", "VBoxContainer", "--name", "Layout"])

    p.run("Add score Label", "scene",
          ["scene", "add-node", "--scene", ms,
           "--parent", "Layout", "--type", "Label", "--name", "ScoreLabel"])

    p.run("Set score label text", "scene",
          ["scene", "set-property", "--scene", ms,
           "--node", "ScoreLabel", "--parent", "Layout",
           "--property", "text=Score: 0"])

    p.run("Add click Button", "scene",
          ["scene", "add-node", "--scene", ms,
           "--parent", "Layout", "--type", "Button", "--name", "ClickButton"])

    p.run("Set button text", "scene",
          ["scene", "set-property", "--scene", ms,
           "--node", "ClickButton", "--parent", "Layout",
           "--property", "text=CLICK ME!"])

    p.run("Add upgrade Button", "scene",
          ["scene", "add-node", "--scene", ms,
           "--parent", "Layout", "--type", "Button", "--name", "UpgradeButton"])

    p.run("Set upgrade button text", "scene",
          ["scene", "set-property", "--scene", ms,
           "--node", "UpgradeButton", "--parent", "Layout",
           "--property", "text=Upgrade (10 coins)"])

    p.run("Add coins-per-sec Label", "scene",
          ["scene", "add-node", "--scene", ms,
           "--parent", "Layout", "--type", "Label", "--name", "RateLabel"])

    p.run("Set rate label text", "scene",
          ["scene", "set-property", "--scene", ms,
           "--node", "RateLabel", "--parent", "Layout",
           "--property", "text=0 coins/sec"])

    # ── Phase 3: Game Scripts ───────────────────────────────────────
    scripts_dir = project_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    autoload_dir = scripts_dir / "autoload"
    autoload_dir.mkdir(parents=True, exist_ok=True)

    p.run("Create main game script", "script",
          ["script", "create", "--extends", "Control", "--class-name", "Main",
           "--ready", "--process",
           str(scripts_dir / "main.gd")])

    p.run("Attach main script to root", "script",
          ["script", "attach", "--scene", ms,
           "--node", "Main",
           "--script", "res://scripts/main.gd"])

    p.run("Create game manager autoload", "script",
          ["script", "create", "--extends", "Node", "--class-name", "GameManager",
           "--ready",
           str(autoload_dir / "game_manager.gd")])

    p.run("Register game manager autoload", "project",
          ["project", "add-autoload",
           "--name", "GameManager",
           "--path", "res://scripts/autoload/game_manager.gd", pg])

    # ── Phase 4: Signal Connections ─────────────────────────────────
    p.run("Connect click button pressed", "signal",
          ["signal", "connect", "--scene", ms,
           "--signal", "pressed",
           "--from", "ClickButton",
           "--to", ".",
           "--method", "_on_click_button_pressed"])

    p.run("Connect upgrade button pressed", "signal",
          ["signal", "connect", "--scene", ms,
           "--signal", "pressed",
           "--from", "UpgradeButton",
           "--to", ".",
           "--method", "_on_upgrade_button_pressed"])

    p.run("List signals to verify", "signal",
          ["signal", "list", ms])

    # ── Phase 5: Timer for Passive Income ───────────────────────────
    p.run("Add passive income timer", "scene",
          ["scene", "add-timer", "--scene", ms,
           "--parent", "Main", "--name", "IncomeTimer",
           "--wait", "1.0", "--autostart",
           "--connect", "_on_income_timer_timeout"])

    # ── Phase 6: Audio ──────────────────────────────────────────────
    p.run("Create audio bus layout", "audio",
          ["audio", "create-bus-layout",
           "--bus", "SFX:Master", "--bus", "Music:Master",
           str(project_dir / "default_bus_layout.tres")])

    p.run("Add click sound player", "audio",
          ["audio", "add-player", "--scene", ms,
           "--parent", "Main", "--name", "ClickSound",
           "--bus", "SFX"])

    p.run("Add bg music player", "audio",
          ["audio", "add-player", "--scene", ms,
           "--parent", "Main", "--name", "BGMusic",
           "--bus", "Music", "--autoplay"])

    # ── Phase 7: Visual Effects ─────────────────────────────────────
    p.run("Add click particle effect", "particle",
          ["particle", "add", "--scene", ms,
           "--parent", "Main", "--name", "ClickParticles",
           "--preset", "sparkle"])

    (project_dir / "theme").mkdir(parents=True, exist_ok=True)

    p.run("Create UI theme", "theme",
          ["theme", "create",
           "--font-size", "24",
           "--base-color", "#1a1a2e",
           "--text-color", "#e0e0e0",
           "--accent-color", "#ffd700",
           str(project_dir / "theme" / "game_theme.tres")])

    p.run("Create button stylebox", "theme",
          ["theme", "create-stylebox",
           "--bg-color", "#ffd700",
           "--corner-radius", "8",
           "--border-width", "2",
           "--border-color", "#b8860b",
           str(project_dir / "theme" / "button_style.tres")])

    # ── Phase 8: Animations ─────────────────────────────────────────
    (project_dir / "animations").mkdir(parents=True, exist_ok=True)

    p.run("Create score popup animation", "animation",
          ["animation", "create-library",
           "--name", "popup", "--length", "0.5",
           str(project_dir / "animations" / "score_popup.tres")])

    p.run("Add scale track to popup", "animation",
          ["animation", "add-track",
           "--library", str(project_dir / "animations" / "score_popup.tres"),
           "--animation", "popup",
           "--property", "ScoreLabel:scale",
           "--keyframe", "0=1.0",
           "--keyframe", "0.25=1.2",
           "--keyframe", "0.5=1.0"])

    # ── Phase 9: Shader Effects ─────────────────────────────────────
    (project_dir / "shaders").mkdir(parents=True, exist_ok=True)

    p.run("Create flash shader", "shader",
          ["shader", "create",
           "--template", "flash",
           str(project_dir / "shaders" / "flash.tres")])

    p.run("Create shader material", "shader",
          ["shader", "create-material",
           "--shader", "res://shaders/flash.tres",
           str(project_dir / "shaders" / "flash_material.tres")])

    # ── Phase 10: Scene Composition ─────────────────────────────────
    hud_def = project_dir / "scenes" / "hud_def.json"
    hs = str(project_dir / "scenes" / "hud.tscn")
    hud_def.write_text(json.dumps({
        "root": {
            "name": "HUD",
            "type": "CanvasLayer",
            "children": []
        }
    }))

    p.run("Create HUD subscene", "scene",
          ["scene", "create", str(hud_def), "--output", hs])

    p.run("Add HUD label", "scene",
          ["scene", "add-node", "--scene", hs,
           "--parent", "HUD", "--type", "Label", "--name", "FPSLabel"])

    p.run("Instance HUD into main", "scene",
          ["scene", "add-instance", "--scene", ms,
           "--parent", "Main",
           "--instance", "res://scenes/hud.tscn",
           "--name", "HUD"])

    # ── Phase 11: Camera ────────────────────────────────────────────
    p.run("Add camera to main", "scene",
          ["scene", "add-camera", "--scene", ms,
           "--parent", "Main", "--name", "Camera",
           "--zoom", "1.0"])

    # ── Phase 12: Node Groups ───────────────────────────────────────
    p.run("Group click button as clickable", "scene",
          ["scene", "add-group", "--scene", ms,
           "--node", "ClickButton",
           "--group", "clickables"])

    p.run("Duplicate upgrade button", "scene",
          ["scene", "duplicate-node", "--scene", ms,
           "--node", "UpgradeButton",
           "--new-name", "UpgradeButton2"])

    # ── Phase 13: Resource Creation ─────────────────────────────────
    (project_dir / "resources").mkdir(parents=True, exist_ok=True)

    p.run("Create upgrade curve", "resource",
          ["resource", "create-curve",
           "--point", "0,1", "--point", "0.5,2", "--point", "1,10",
           str(project_dir / "resources" / "upgrade_curve.tres")])

    p.run("Create gradient for UI", "resource",
          ["resource", "create-gradient",
           "--stop", "0:#1a1a2e", "--stop", "0.5:#16213e", "--stop", "1:#0f3460",
           str(project_dir / "resources" / "bg_gradient.tres")])

    # ── Phase 14: Advanced Game Features ───────────────────────────
    # These test capabilities needed for a real game but not yet in gdauto

    # 14a: Set anchor presets on UI nodes (full rect, center, etc.)
    p.run("Set button anchor preset", "scene",
          ["scene", "set-property", "--scene", ms,
           "--node", "Layout", "--parent", "Main",
           "--property", "anchor_preset=15"])

    # 14b: Set size flags for UI layout control
    p.run("Set layout size flags", "scene",
          ["scene", "set-property", "--scene", ms,
           "--node", "ScoreLabel", "--parent", "Layout",
           "--property", "size_flags_horizontal=3"])

    # 14c: Assign theme resource to root Control
    p.run("Assign theme to main", "scene",
          ["scene", "set-resource", "--scene", ms,
           "--node", "Main",
           "--property", "theme",
           "--resource", "res://theme/game_theme.tres",
           "--type", "Theme"])

    # 14d: Set main scene in project.godot
    p.run("Set main scene", "project",
          ["project", "set-main-scene",
           "--scene", "res://scenes/main.tscn", pg])

    # 14e: Add AnimationPlayer node
    p.run("Add AnimationPlayer node", "scene",
          ["scene", "add-node", "--scene", ms,
           "--parent", "Main", "--type", "AnimationPlayer",
           "--name", "AnimPlayer"])

    # 14f: Script with game logic content (not just boilerplate)
    p.run("Create script with signals and exports", "script",
          ["script", "create",
           "--extends", "Control",
           "--class-name", "ClickHandler",
           "--signal", "clicked",
           "--signal", "score_changed(amount: int)",
           "--export", "click_value:int=1",
           "--export", "upgrade_cost:int=10",
           "--onready", "score_label:Label=ScoreLabel",
           "--onready", "click_button:Button=ClickButton",
           "--ready", "--process", "--input",
           str(scripts_dir / "click_handler.gd")])

    # 14g: Remove a node from the scene
    p.run("Remove duplicate button", "scene",
          ["scene", "remove-node", "--scene", ms,
           "--name", "UpgradeButton2"])

    # 14h: Rename a node
    p.run("Rename a node", "scene",
          ["scene", "rename-node", "--scene", ms,
           "--node", "RateLabel", "--parent", "Layout",
           "--new-name", "CoinsPerSecLabel"])

    # 14i: Reorder children (move node to be first child)
    p.run("Reorder node to first child", "scene",
          ["scene", "reorder-node", "--scene", ms,
           "--node", "ScoreLabel", "--parent", "Layout",
           "--index", "0"])

    # 14j: List resources used in a scene
    p.run("List scene resources", "resource",
          ["resource", "list", "--scene", ms])

    # 14k: Create a StyleBoxFlat and assign via scene set-resource
    p.run("Assign stylebox to button", "scene",
          ["scene", "set-resource", "--scene", ms,
           "--node", "ClickButton", "--parent", "Layout",
           "--property", "theme_override_styles/normal",
           "--resource", "res://theme/button_style.tres",
           "--type", "StyleBoxFlat"])

    # 14l: Bulk set multiple properties at once
    p.run("Bulk set node properties", "scene",
          ["scene", "set-property", "--scene", ms,
           "--node", "Main",
           "--property", "anchor_left=0.0",
           "--property", "anchor_right=1.0",
           "--property", "anchor_top=0.0",
           "--property", "anchor_bottom=1.0"])

    # 14m: Create a ColorRect for background
    p.run("Add background ColorRect", "scene",
          ["scene", "add-node", "--scene", ms,
           "--parent", "Main", "--type", "ColorRect", "--name", "Background",
           "--property", "color=Color(0.1, 0.1, 0.18, 1)"])

    # 14n: Create a TextureRect node
    p.run("Add TextureRect for UI art", "scene",
          ["scene", "add-node", "--scene", ms,
           "--parent", "Main", "--type", "TextureRect", "--name", "CoinIcon"])

    # 14o: Project set-main-scene to use our main scene
    p.run("Set window title", "project",
          ["project", "set-config", "--section", "application",
           "--key", "config/name", "--value", "Idle Clicker", pg])

    # ── Phase 15: Advanced Scene Operations ──────────────────────────

    # 15a: Move a node to a different parent
    p.run("Move node to different parent", "scene",
          ["scene", "move-node", "--scene", ms,
           "--node", "Camera", "--new-parent", "Layout"])

    # 15b: Create a scene directly from CLI args (no JSON file needed)
    shop_scene = str(project_dir / "scenes" / "shop.tscn")
    p.run("Create scene from CLI args", "scene",
          ["scene", "create-simple", "--root-type", "Control", "--root-name", "Shop",
           "--output", shop_scene])

    # 15c: Copy properties from one node to another
    p.run("Copy node properties", "scene",
          ["scene", "copy-properties", "--scene", ms,
           "--from-node", "ClickButton", "--to-node", "UpgradeButton",
           "--parent", "Layout"])

    # 15d: List all node types used in a scene
    p.run("List node types in scene", "scene",
          ["scene", "list-types", ms])

    # 15e: Set multiple resources at once (e.g., theme + material)
    p.run("Set material on button", "scene",
          ["scene", "set-resource", "--scene", ms,
           "--node", "ClickButton", "--parent", "Layout",
           "--property", "material",
           "--resource", "res://shaders/flash_material.tres",
           "--type", "ShaderMaterial"])

    # 15f: Add margin container for UI padding
    p.run("Add MarginContainer", "scene",
          ["scene", "add-node", "--scene", ms,
           "--parent", "Main", "--type", "MarginContainer", "--name", "Margins",
           "--property", "theme_override_constants/margin_left=20",
           "--property", "theme_override_constants/margin_right=20"])

    # 15g: Script edit: add a method to existing script
    p.run("Add method to script", "script",
          ["script", "add-method", "--file", str(scripts_dir / "main.gd"),
           "--name", "_on_click_button_pressed",
           "--body", "score += click_value\nscore_label.text = str(score)"])

    # 15h: Script edit: add a variable to existing script
    p.run("Add variable to script", "script",
          ["script", "add-var", "--file", str(scripts_dir / "main.gd"),
           "--name", "score", "--type", "int", "--value", "0"])

    # 15i: Script edit: add an export variable
    p.run("Add export to script", "script",
          ["script", "add-export", "--file", str(scripts_dir / "main.gd"),
           "--name", "click_value", "--type", "int", "--value", "1"])

    # 15j: Script edit: add a signal declaration
    p.run("Add signal to script", "script",
          ["script", "add-signal", "--file", str(scripts_dir / "main.gd"),
           "--name", "score_changed",
           "--params", "new_score: int"])

    # 15k: Inspect a specific node
    p.run("Inspect specific node", "scene",
          ["scene", "inspect-node", "--scene", ms,
           "--node", "ClickButton", "--parent", "Layout"])

    # 15l: Project add-plugin (enable a plugin in project.godot)
    p.run("Enable a plugin", "project",
          ["project", "add-plugin", "--name", "gut",
           "--path", "res://addons/gut/plugin.cfg", pg])

    # 15m: Scene set-anchor (set anchor preset on Control node)
    p.run("Set full rect anchor", "scene",
          ["scene", "set-anchor", "--scene", ms,
           "--node", "Main", "--preset", "full_rect"])

    # 15n: Scene from template (create common scene patterns)
    ui_scene = str(project_dir / "scenes" / "ui_panel.tscn")
    p.run("Create UI panel from template", "scene",
          ["scene", "from-template", "--template", "ui-panel",
           "--output", ui_scene,
           "--title", "Upgrades"])

    # ── Phase 16: Script Content Validation ──────────────────────────
    # Read the generated main.gd to verify the edits landed
    p.run("List script methods", "script",
          ["script", "list-methods", str(scripts_dir / "main.gd")])

    p.run("List script variables", "script",
          ["script", "list-vars", str(scripts_dir / "main.gd")])

    # ── Phase 17: Advanced Project Config ────────────────────────────
    # Set window title via set-config
    p.run("Set window title", "project",
          ["project", "set-config", "--section", "application",
           "--key", "config/name", "--value", '"Idle Clicker"', pg])

    # Set icon path
    p.run("Set project icon", "project",
          ["project", "set-config", "--section", "application",
           "--key", "config/icon", "--value", '"res://icon.svg"', pg])

    # ── Phase 18: Scene Tree Operations ──────────────────────────────
    # Count total nodes across all scenes
    p.run("Count nodes across project", "scene",
          ["scene", "count-nodes", pd])

    # Get scene tree as JSON (global --json flag before subcommand)
    p.run("Get scene tree JSON", "scene",
          ["--json", "scene", "list-nodes", ms])

    # ── Phase 19: Build a complete shop scene with template ─────────
    p.run("Create shop from template", "scene",
          ["scene", "from-template", "--template", "ui-panel",
           "--output", str(project_dir / "scenes" / "shop.tscn"),
           "--title", "Upgrades"])

    # Add buttons to the shop content area
    p.run("Add shop upgrade 1", "scene",
          ["scene", "add-node", "--scene", str(project_dir / "scenes" / "shop.tscn"),
           "--parent", "Content", "--type", "Button", "--name", "Upgrade1",
           "--property", "text=Auto Clicker ($50)"])

    p.run("Add shop upgrade 2", "scene",
          ["scene", "add-node", "--scene", str(project_dir / "scenes" / "shop.tscn"),
           "--parent", "Content", "--type", "Button", "--name", "Upgrade2",
           "--property", "text=Double Click ($100)"])

    # Create shop script
    p.run("Create shop script", "script",
          ["script", "create", "--extends", "PanelContainer",
           "--class-name", "Shop", "--ready",
           str(scripts_dir / "shop.gd")])

    p.run("Add shop vars", "script",
          ["script", "add-var", "--file", str(scripts_dir / "shop.gd"),
           "--name", "upgrades", "--type", "Dictionary", "--value", "{}"])

    p.run("Add shop signal", "script",
          ["script", "add-signal", "--file", str(scripts_dir / "shop.gd"),
           "--name", "upgrade_purchased",
           "--params", "upgrade_name: String, cost: int"])

    p.run("Add shop buy method", "script",
          ["script", "add-method", "--file", str(scripts_dir / "shop.gd"),
           "--name", "_on_upgrade_pressed",
           "--params", "upgrade_name: String",
           "--body", 'var cost: int = upgrades[upgrade_name]\n\tupgrade_purchased.emit(upgrade_name, cost)'])

    p.run("Attach shop script", "script",
          ["script", "attach",
           "--scene", str(project_dir / "scenes" / "shop.tscn"),
           "--node", "Panel",
           "--script", "res://scripts/shop.gd"])

    # Instance shop into main
    p.run("Instance shop into main", "scene",
          ["scene", "add-instance", "--scene", ms,
           "--parent", "Main",
           "--instance", "res://scenes/shop.tscn",
           "--name", "Shop"])

    # ── Phase 20: Create player-2d scene from template ───────────
    p.run("Create player scene", "scene",
          ["scene", "from-template", "--template", "player-2d",
           "--output", str(project_dir / "scenes" / "player.tscn")])

    p.run("Create player script", "script",
          ["script", "create", "--extends", "CharacterBody2D",
           "--class-name", "Player",
           "--export", "speed:float=200.0",
           "--export", "jump_force:float=400.0",
           "--ready", "--physics",
           str(scripts_dir / "player.gd")])

    # ── Phase 21: Search and Query ─────────────────────────────────
    # Find all buttons in the main scene
    p.run("Find nodes by type", "scene",
          ["scene", "find-nodes", "--scene", ms, "--type", "Button"])

    # Find all nodes with a specific property value
    p.run("Find nodes with property", "scene",
          ["scene", "find-nodes", "--scene", ms, "--property", "text"])

    # ── Phase 22: Save System Setup ────────────────────────────────
    p.run("Create save manager script", "script",
          ["script", "create", "--extends", "Node",
           "--class-name", "SaveManager",
           "--signal", "game_saved",
           "--signal", "game_loaded",
           "--ready",
           str(autoload_dir / "save_manager.gd")])

    p.run("Add save path var", "script",
          ["script", "add-var", "--file", str(autoload_dir / "save_manager.gd"),
           "--name", "SAVE_PATH", "--type", "String",
           "--value", '"user://save.json"'])

    p.run("Add save method", "script",
          ["script", "add-method", "--file", str(autoload_dir / "save_manager.gd"),
           "--name", "save_game",
           "--params", "data: Dictionary",
           "--body", 'var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)\n\tfile.store_string(JSON.stringify(data))\n\tgame_saved.emit()'])

    p.run("Add load method", "script",
          ["script", "add-method", "--file", str(autoload_dir / "save_manager.gd"),
           "--name", "load_game",
           "--return-type", "Dictionary",
           "--body", 'if not FileAccess.file_exists(SAVE_PATH):\n\t\treturn {}\n\tvar file := FileAccess.open(SAVE_PATH, FileAccess.READ)\n\tvar json := JSON.new()\n\tjson.parse(file.get_as_text())\n\tgame_loaded.emit()\n\treturn json.data'])

    p.run("Register save manager autoload", "project",
          ["project", "add-autoload",
           "--name", "SaveManager",
           "--path", "res://scripts/autoload/save_manager.gd", pg])

    # List the save manager methods to verify
    p.run("Verify save manager methods", "script",
          ["script", "list-methods", str(autoload_dir / "save_manager.gd")])

    # ── Phase 23: Game State with Autoloads ─────────────────────────
    p.run("Add score var to game manager", "script",
          ["script", "add-var", "--file", str(autoload_dir / "game_manager.gd"),
           "--name", "score", "--type", "int", "--value", "0"])

    p.run("Add coins_per_sec var", "script",
          ["script", "add-var", "--file", str(autoload_dir / "game_manager.gd"),
           "--name", "coins_per_sec", "--type", "float", "--value", "0.0"])

    p.run("Add click method to game manager", "script",
          ["script", "add-method", "--file", str(autoload_dir / "game_manager.gd"),
           "--name", "add_click",
           "--params", "value: int",
           "--body", "score += value"])

    p.run("Add passive income method", "script",
          ["script", "add-method", "--file", str(autoload_dir / "game_manager.gd"),
           "--name", "tick_passive",
           "--params", "delta: float",
           "--body", "score += int(coins_per_sec * delta)"])

    # ── Phase 24: Scene Dependency Validation ────────────────────────
    p.run("Final project validation", "project",
          ["project", "validate", pd])

    p.run("Final project stats", "project",
          ["project", "stats", pd])

    p.run("Final project info", "project",
          ["project", "info", pg])

    # ── Phase 25: Asset Pipeline (Aseprite -> Godot) ───────────────

    # Create mock Aseprite JSON export (simulates what Aseprite CLI produces)
    sprites_dir = project_dir / "assets" / "sprites" / "cookie"
    sprites_dir.mkdir(parents=True, exist_ok=True)

    aseprite_json = sprites_dir / "cookie.json"
    aseprite_json.write_text(json.dumps({
        "frames": [
            {"frame": {"x": 0, "y": 0, "w": 32, "h": 32}, "rotated": False,
             "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": 32, "h": 32},
             "sourceSize": {"w": 32, "h": 32}, "duration": 100},
            {"frame": {"x": 32, "y": 0, "w": 32, "h": 32}, "rotated": False,
             "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": 32, "h": 32},
             "sourceSize": {"w": 32, "h": 32}, "duration": 100},
            {"frame": {"x": 64, "y": 0, "w": 32, "h": 32}, "rotated": False,
             "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": 32, "h": 32},
             "sourceSize": {"w": 32, "h": 32}, "duration": 100},
            {"frame": {"x": 96, "y": 0, "w": 32, "h": 32}, "rotated": False,
             "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": 32, "h": 32},
             "sourceSize": {"w": 32, "h": 32}, "duration": 200},
        ],
        "meta": {
            "app": "http://www.aseprite.org/",
            "version": "1.3.17",
            "image": "cookie_sheet.png",
            "format": "RGBA8888",
            "size": {"w": 128, "h": 32},
            "scale": "1",
            "frameTags": [
                {"name": "idle", "from": 0, "to": 1, "direction": "forward",
                 "color": "#000000ff", "repeat": "0", "data": ""},
                {"name": "bounce", "from": 2, "to": 3, "direction": "pingpong",
                 "color": "#000000ff", "repeat": "0", "data": ""},
            ],
            "layers": [{"name": "Layer 1", "opacity": 255, "blendMode": "normal"}],
            "slices": []
        }
    }))

    # Create dummy PNG files so project validation passes
    # (In real workflow, Aseprite CLI would create these)
    (sprites_dir / "cookie_sheet.png").write_bytes(b'\x89PNG\r\n\x1a\n')

    # 25a: Import Aseprite JSON to SpriteFrames .tres
    cookie_tres = str(sprites_dir / "cookie.tres")
    p.run("Import Aseprite JSON to SpriteFrames", "sprite",
          ["sprite", "import-aseprite", str(aseprite_json),
           "-o", cookie_tres,
           "--res-path", "res://assets/sprites/cookie/cookie_sheet.png"])

    # 25b: Validate the generated SpriteFrames
    p.run("Validate imported SpriteFrames", "sprite",
          ["sprite", "validate", cookie_tres])

    # 25c: List animations in SpriteFrames
    p.run("List SpriteFrames animations", "sprite",
          ["sprite", "list-animations", cookie_tres])

    # 25d: Add AnimatedSprite2D to a scene and assign SpriteFrames
    p.run("Add AnimatedSprite2D node", "scene",
          ["scene", "add-node", "--scene", ms,
           "--parent", "Main", "--type", "AnimatedSprite2D",
           "--name", "CookieSprite"])

    p.run("Assign SpriteFrames to AnimatedSprite2D", "scene",
          ["scene", "set-resource", "--scene", ms,
           "--node", "CookieSprite",
           "--property", "sprite_frames",
           "--resource", "res://assets/sprites/cookie/cookie.tres",
           "--type", "SpriteFrames"])

    # 25e: Create a second Aseprite mock for cursor/click effect
    click_sprites_dir = project_dir / "assets" / "sprites" / "click_fx"
    click_sprites_dir.mkdir(parents=True, exist_ok=True)

    click_json = click_sprites_dir / "click_fx.json"
    click_json.write_text(json.dumps({
        "frames": [
            {"frame": {"x": 0, "y": 0, "w": 16, "h": 16}, "rotated": False,
             "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": 16, "h": 16},
             "sourceSize": {"w": 16, "h": 16}, "duration": 50},
            {"frame": {"x": 16, "y": 0, "w": 16, "h": 16}, "rotated": False,
             "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": 16, "h": 16},
             "sourceSize": {"w": 16, "h": 16}, "duration": 50},
            {"frame": {"x": 32, "y": 0, "w": 16, "h": 16}, "rotated": False,
             "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": 16, "h": 16},
             "sourceSize": {"w": 16, "h": 16}, "duration": 50},
        ],
        "meta": {
            "app": "http://www.aseprite.org/",
            "version": "1.3.17",
            "image": "click_fx_sheet.png",
            "format": "RGBA8888",
            "size": {"w": 48, "h": 16},
            "scale": "1",
            "frameTags": [
                {"name": "pop", "from": 0, "to": 2, "direction": "forward",
                 "color": "#000000ff", "repeat": "0", "data": ""},
            ],
            "layers": [{"name": "Layer 1", "opacity": 255, "blendMode": "normal"}],
            "slices": []
        }
    }))

    (click_sprites_dir / "click_fx_sheet.png").write_bytes(b'\x89PNG\r\n\x1a\n')
    click_tres = str(click_sprites_dir / "click_fx.tres")
    p.run("Import click effect sprites", "sprite",
          ["sprite", "import-aseprite", str(click_json),
           "-o", click_tres,
           "--res-path", "res://assets/sprites/click_fx/click_fx_sheet.png"])

    p.run("Validate click effect SpriteFrames", "sprite",
          ["sprite", "validate", click_tres])

    # 25f: Aseprite export command (wraps Aseprite CLI)
    # This will fail if Aseprite is not available, but tests the command exists
    p.run("Export from Aseprite (command exists)", "sprite",
          ["sprite", "export", "--help"])

    # 25g: Batch export (command exists)
    p.run("Batch export (command exists)", "sprite",
          ["sprite", "export-all", "--help"])

    # ── Phase 26: Cross-cutting Operations ──────────────────────────

    # Verify the generated main.tscn has expected node count
    p.run("Verify main scene node count", "scene",
          ["scene", "list-nodes", ms])

    # Verify shop scene exists and has nodes
    p.run("Verify shop scene", "scene",
          ["scene", "list-nodes", str(project_dir / "scenes" / "shop.tscn")])

    # Find all instances in main scene
    p.run("Find instances in main", "scene",
          ["scene", "find-nodes", "--scene", ms, "--type", ""])

    # Inspect the main root node (should have theme + script)
    p.run("Inspect main root", "scene",
          ["scene", "inspect-node", "--scene", ms, "--node", "Main"])

    # List types across the main scene
    p.run("List main types", "scene",
          ["scene", "list-types", ms])

    # List resources in main scene (should have theme, material, script, etc.)
    p.run("List main resources", "resource",
          ["resource", "list", "--scene", ms])

    # ── Phase 26: File Validation ───────────────────────────────────
    # Verify the generated scene files are structurally valid
    p.run("Validate main scene structure", "scene",
          ["scene", "validate", ms])

    p.run("Validate shop scene structure", "scene",
          ["scene", "validate", str(project_dir / "scenes" / "shop.tscn")])

    p.run("Validate HUD scene structure", "scene",
          ["scene", "validate", str(project_dir / "scenes" / "hud.tscn")])

    # Final scene listing
    p.run("List all scenes", "scene",
          ["scene", "list", pd])

    p.run("List nodes in main scene", "scene",
          ["scene", "list-nodes", ms])

    p.run("Inspect main scene", "resource",
          ["resource", "inspect", ms])

    p.run("Validate project", "project",
          ["project", "validate", pd])

    p.run("Project stats", "project",
          ["project", "stats", pd])

    p.run("Project info", "project",
          ["project", "info", pg])

    # ── Phase 15: Export Setup ──────────────────────────────────────
    p.run("Create export preset", "preset",
          ["preset", "create", "--platform", "windows", pd])

    p.run("List export presets", "preset",
          ["preset", "list", pd])

    return p


def write_blockers_log(runner: PipelineRunner) -> None:
    """Write a detailed blockers log with failed steps."""
    lines: list[str] = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines.append(f"# Pipeline Blockers Log - {ts}")
    lines.append(f"# Score: {runner.passed_count()}/{runner.total_count()}")
    lines.append("")

    categories: dict[str, list[StepResult]] = {}
    for r in runner.results:
        categories.setdefault(r.category, []).append(r)

    lines.append("## Summary by Category")
    for cat, results in sorted(categories.items()):
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        status = "PASS" if passed == total else "PARTIAL" if passed > 0 else "FAIL"
        lines.append(f"  {cat}: {passed}/{total} [{status}]")
    lines.append("")

    failed = [r for r in runner.results if not r.passed]
    if failed:
        lines.append(f"## Blockers ({len(failed)} steps failed)")
        lines.append("")
        for r in failed:
            lines.append(f"### BLOCKER: {r.name} [{r.category}]")
            lines.append(f"  Command: gdauto {' '.join(r.command)}")
            lines.append(f"  Exit code: {r.exit_code}")
            if r.output.strip():
                lines.append(f"  Output: {r.output.strip()[:300]}")
            lines.append("")
    else:
        lines.append("## No blockers! All steps passed.")
        lines.append("")

    passed_results = [r for r in runner.results if r.passed]
    lines.append(f"## Passed ({len(passed_results)} steps)")
    for r in passed_results:
        lines.append(f"  OK: {r.name} [{r.category}]")

    BLOCKERS_LOG.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    with TemporaryDirectory(prefix="gdauto_pipeline_") as tmpdir:
        project_dir = Path(tmpdir) / "idle_clicker"
        project_dir.mkdir()
        runner = run_pipeline(project_dir)

    write_blockers_log(runner)
    print(f"METRIC: {runner.passed_count()}/{runner.total_count()}")
    print(runner.passed_count())


if __name__ == "__main__":
    main()
