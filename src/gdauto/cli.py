"""Click root group with global flags and command group registration.

This is the main entry point for the gdauto CLI. All global flags
(--json, --verbose, --quiet, --no-color, --godot-path) are defined here
and propagated to subcommands via Click's context object.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import rich_click as click

from gdauto import __version__
from gdauto.backend import GodotBackend
from gdauto.commands.export import export
from gdauto.commands.project import project
from gdauto.commands.resource import resource
from gdauto.commands.scene import scene
from gdauto.commands.sprite import sprite
from gdauto.commands.tileset import tileset
from gdauto.errors import GdautoError, GodotBinaryError
from gdauto.export.pipeline import import_with_retry
from gdauto.output import GlobalConfig, emit, emit_error


@click.group(invoke_without_command=True)
@click.option("-j", "--json", "json_mode", is_flag=True, help="Output as JSON.")
@click.option("-v", "--verbose", is_flag=True, help="Show extra detail.")
@click.option("-q", "--quiet", is_flag=True, help="Suppress all output except errors.")
@click.option("--no-color", is_flag=True, help="Disable colored output.")
@click.option(
    "--godot-path",
    type=click.Path(),
    envvar="GODOT_PATH",
    help="Path to Godot binary (overrides PATH discovery).",
)
@click.version_option(version=__version__, prog_name="gdauto")
@click.pass_context
def cli(
    ctx: click.Context,
    json_mode: bool,
    verbose: bool,
    quiet: bool,
    no_color: bool,
    godot_path: str | None,
) -> None:
    """gdauto: Agent-native CLI for Godot Engine.

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
        godot_path=godot_path,
    )

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


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
    except (GdautoError, GodotBinaryError) as exc:
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


# Register command groups
cli.add_command(project)
cli.add_command(resource)
cli.add_command(export)
cli.add_command(sprite)
cli.add_command(tileset)
cli.add_command(scene)
cli.add_command(import_cmd, name="import")
