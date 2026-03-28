"""Build and export Godot projects.

Provides release, debug, and pack export commands that wrap Godot's
headless export with automatic import-cache handling and retry logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rich_click as click

from gdauto.backend import GodotBackend
from gdauto.errors import GdautoError, GodotBinaryError
from gdauto.export.pipeline import export_project
from gdauto.output import GlobalConfig, emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def export(ctx: click.Context) -> None:
    """Build and export Godot projects."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _do_export(
    ctx: click.Context,
    preset: str,
    output: str,
    project: str,
    no_import: bool,
    mode: str,
) -> None:
    """Shared export logic for release, debug, and pack commands."""
    config: GlobalConfig = ctx.obj
    backend = GodotBackend(binary_path=config.godot_path)
    project_path = Path(project)
    try:
        export_project(
            backend,
            project_path,
            preset,
            output,
            mode=mode,
            auto_import=not no_import,
        )
    except (GdautoError, GodotBinaryError) as exc:
        emit_error(exc, ctx)
        return
    emit(
        {"preset": preset, "output": output, "mode": mode},
        _print_export_result,
        ctx,
    )


def _print_export_result(data: dict[str, Any], verbose: bool = False) -> None:
    """Display export result in human-readable format."""
    click.echo(f"Exported {data['mode']} build: {data['output']}")


@export.command("release")
@click.argument("preset")
@click.option(
    "-o", "--output",
    type=click.Path(),
    required=True,
    help="Output file path for the exported build.",
)
@click.option(
    "--project",
    type=click.Path(),
    default=".",
    help="Project directory. Default: current directory.",
)
@click.option(
    "--no-import",
    is_flag=True,
    default=False,
    help="Disable automatic resource import before export.",
)
@click.pass_context
def release(
    ctx: click.Context,
    preset: str,
    output: str,
    project: str,
    no_import: bool,
) -> None:
    """Export a release build using the named preset.

    Runs Godot's headless export with --export-release. Automatically
    imports resources first if the import cache is missing.
    """
    _do_export(ctx, preset, output, project, no_import, mode="release")


@export.command("debug")
@click.argument("preset")
@click.option(
    "-o", "--output",
    type=click.Path(),
    required=True,
    help="Output file path for the exported build.",
)
@click.option(
    "--project",
    type=click.Path(),
    default=".",
    help="Project directory. Default: current directory.",
)
@click.option(
    "--no-import",
    is_flag=True,
    default=False,
    help="Disable automatic resource import before export.",
)
@click.pass_context
def debug(
    ctx: click.Context,
    preset: str,
    output: str,
    project: str,
    no_import: bool,
) -> None:
    """Export a debug build using the named preset.

    Runs Godot's headless export with --export-debug. Automatically
    imports resources first if the import cache is missing.
    """
    _do_export(ctx, preset, output, project, no_import, mode="debug")


@export.command("pack")
@click.argument("preset")
@click.option(
    "-o", "--output",
    type=click.Path(),
    required=True,
    help="Output .pck file path.",
)
@click.option(
    "--project",
    type=click.Path(),
    default=".",
    help="Project directory. Default: current directory.",
)
@click.option(
    "--no-import",
    is_flag=True,
    default=False,
    help="Disable automatic resource import before export.",
)
@click.pass_context
def pack(
    ctx: click.Context,
    preset: str,
    output: str,
    project: str,
    no_import: bool,
) -> None:
    """Export a pack (.pck) file using the named preset.

    Runs Godot's headless export with --export-pack. Automatically
    imports resources first if the import cache is missing.
    """
    _do_export(ctx, preset, output, project, no_import, mode="pack")
