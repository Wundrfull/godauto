"""Build and export Godot projects."""

from __future__ import annotations

import rich_click as click


@click.group(invoke_without_command=True)
@click.pass_context
def export(ctx: click.Context) -> None:
    """Build and export Godot projects."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
