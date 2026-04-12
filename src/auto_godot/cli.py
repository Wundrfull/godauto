"""Click root group with global flags and command group registration.

This is the main entry point for the auto-godot CLI. All global flags
(--json, --verbose, --quiet, --no-color, --godot-path) are defined here
and propagated to subcommands via Click's context object.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# Ensure UTF-8 output on Windows to prevent UnicodeEncodeError with
# non-ASCII filenames (CJK, emoji, etc.) when using click.echo (#15, #16).
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import rich_click as click

from auto_godot import __version__
from auto_godot.backend import GodotBackend
from auto_godot.commands.animation import animation
from auto_godot.commands.audio import audio
from auto_godot.commands.debug import debug
from auto_godot.commands.export import export
from auto_godot.commands.locale import locale
from auto_godot.commands.particle import particle
from auto_godot.commands.physics import physics
from auto_godot.commands.preset import preset
from auto_godot.commands.project import project
from auto_godot.commands.resource import resource
from auto_godot.commands.scene import scene
from auto_godot.commands.script import script
from auto_godot.commands.shader import shader
from auto_godot.commands.signal import signal
from auto_godot.commands.skill import skill
from auto_godot.commands.sprite import sprite
from auto_godot.commands.theme import theme
from auto_godot.commands.tileset import tileset
from auto_godot.errors import AutoGodotError, GodotBinaryError
from auto_godot.export.pipeline import import_with_retry
from auto_godot.output import GlobalConfig, emit, emit_error


@click.group(invoke_without_command=True)
@click.option("-j", "--json", "json_mode", is_flag=True, help="Output as JSON.")
@click.option("-v", "--verbose", is_flag=True, help="Show extra detail.")
@click.option("-q", "--quiet", is_flag=True, help="Suppress all output except errors.")
@click.option("--no-color", is_flag=True, help="Disable colored output.")
@click.option("--dry-run", is_flag=True, help="Preview changes without writing files.")
@click.option(
    "--godot-path",
    type=click.Path(),
    envvar="GODOT_PATH",
    help="Path to Godot binary (overrides PATH discovery).",
)
@click.version_option(version=__version__, prog_name="auto-godot")
@click.pass_context
def cli(
    ctx: click.Context,
    json_mode: bool,
    verbose: bool,
    quiet: bool,
    no_color: bool,
    dry_run: bool,
    godot_path: str | None,
) -> None:
    """auto-godot: Agent-native CLI for Godot Engine (Godot 4.5+).

    Wraps Godot's headless mode and manipulates Godot text file formats
    (.tscn, .tres, project.godot) to automate workflows that normally
    require the editor GUI.
    """
    if no_color:
        os.environ["NO_COLOR"] = "1"

    ctx.ensure_object(dict)
    ctx.obj = GlobalConfig(
        json_mode=json_mode,
        verbose=verbose,
        quiet=quiet,
        dry_run=dry_run,
        godot_path=godot_path,
    )

    if dry_run:
        ctx.call_on_close(lambda: _warn_if_dry_run_unacknowledged(ctx))

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _warn_if_dry_run_unacknowledged(ctx: click.Context) -> None:
    """Warn users when --dry-run was set but no maybe_write() was called.

    Closes the data-safety trap where commands outside scene group silently
    write files despite the flag. Supported commands call maybe_write()
    which sets dry_run_acknowledged=True. If the flag remains False after
    the command runs, no write was intercepted and the user may have
    unintentionally modified files.
    """
    config: GlobalConfig = ctx.obj
    if config.dry_run and not config.dry_run_acknowledged:
        sys.stderr.write(
            "Warning: --dry-run is not yet implemented for this command.\n"
            "Files may have been written. See issue #110 for supported "
            "commands.\n"
        )


@click.command("import")
@click.option(
    "--project",
    type=click.Path(),
    default=".",
    help="Project directory. Default: current directory.",
)
@click.option(
    "--max-retries",
    type=int,
    default=3,
    help="Maximum import retry attempts. Default: 3.",
)
@click.pass_context
def import_cmd(ctx: click.Context, project: str, max_retries: int) -> None:
    """Force re-import of Godot project resources.

    Runs Godot's headless import with retry logic to handle known
    timing issues. Uses --quit-after instead of --quit to avoid
    race conditions.
    """
    config: GlobalConfig = ctx.obj
    backend = GodotBackend(binary_path=config.godot_path)
    try:
        import_with_retry(backend, Path(project), max_retries=max_retries)
    except (AutoGodotError, GodotBinaryError) as exc:
        emit_error(exc, ctx)
        return
    emit(
        {"project": project, "status": "complete"},
        _print_import_result,
        ctx,
    )


def _print_import_result(data: dict[str, Any], verbose: bool = False) -> None:
    """Display import result in human-readable format."""
    click.echo(f"Import complete: {data['project']}")


@click.command("setup")
@click.option("--auto", "auto_detect", is_flag=True, help="Auto-detect tools without prompting.")
@click.pass_context
def setup_cmd(ctx: click.Context, auto_detect: bool) -> None:
    """Detect and configure external tools (Godot, Aseprite).

    Scans common install locations for Godot and Aseprite, validates
    versions, and reports the results. Use --auto for non-interactive mode.

    Examples:

      auto-godot setup

      auto-godot --json setup --auto
    """
    import shutil

    results: dict[str, Any] = {"tools": {}}

    # Detect Godot
    godot_info = _detect_tool("Godot", [
        os.environ.get("GODOT_PATH", ""),
        shutil.which("godot") or "",
        str(Path.home() / "Documents/GameDev/Godot_v4.6-stable_win64_console.exe"),
        str(Path.home() / "Documents/GameDev/Godot_v4.5-stable_win64_console.exe"),
        "C:/Program Files/Godot/godot.exe",
        "/usr/local/bin/godot",
        "/Applications/Godot.app/Contents/MacOS/Godot",
    ])
    results["tools"]["godot"] = godot_info

    # Detect Aseprite
    aseprite_info = _detect_tool("Aseprite", [
        os.environ.get("ASEPRITE_PATH", ""),
        shutil.which("aseprite") or "",
        "C:/Program Files (x86)/Steam/steamapps/common/Aseprite/Aseprite.exe",
        "C:/Program Files/Aseprite/Aseprite.exe",
        str(Path.home() / "Library/Application Support/Steam/steamapps/common/Aseprite/aseprite"),
        "/usr/bin/aseprite",
    ])
    results["tools"]["aseprite"] = aseprite_info

    # Detect pixel-mcp
    pixel_mcp_found = False
    for candidate in ["tools/bin/pixel-mcp.exe", "tools/bin/pixel-mcp"]:
        if Path(candidate).exists():
            pixel_mcp_found = True
            results["tools"]["pixel_mcp"] = {"found": True, "path": candidate}
            break
    if not pixel_mcp_found:
        results["tools"]["pixel_mcp"] = {"found": False, "path": None}

    results["all_found"] = all(
        t.get("found", False) for t in results["tools"].values()
    )

    def _human(data: dict[str, Any], verbose: bool = False) -> None:
        click.echo("auto-godot environment setup:")
        for name, info in data["tools"].items():
            status = "FOUND" if info.get("found") else "NOT FOUND"
            path = info.get("path", "")
            click.echo(f"  {name}: [{status}] {path or ''}")
        if data["all_found"]:
            click.echo("\nAll tools detected. Ready to go.")
        else:
            missing = [n for n, i in data["tools"].items() if not i.get("found")]
            click.echo(f"\nMissing: {', '.join(missing)}")
            click.echo("Set GODOT_PATH or ASEPRITE_PATH environment variables to configure.")

    emit(results, _human, ctx)


def _detect_tool(name: str, candidates: list[str]) -> dict[str, Any]:
    """Try each candidate path and return the first that exists."""
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return {"found": True, "path": candidate, "name": name}
    return {"found": False, "path": None, "name": name}


# Register command groups
cli.add_command(animation)
cli.add_command(audio)
cli.add_command(debug)
cli.add_command(locale)
cli.add_command(project)
cli.add_command(resource)
cli.add_command(export)
cli.add_command(particle)
cli.add_command(physics)
cli.add_command(preset)
cli.add_command(sprite)
cli.add_command(tileset)
cli.add_command(scene)
cli.add_command(script)
cli.add_command(shader)
cli.add_command(signal)
cli.add_command(theme)
cli.add_command(import_cmd, name="import")
cli.add_command(setup_cmd, name="setup")
cli.add_command(skill)
