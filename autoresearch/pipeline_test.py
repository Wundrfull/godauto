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

    # ── Phase 15: Inspection & Validation ───────────────────────────
    p.run("List scenes in project", "scene",
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
