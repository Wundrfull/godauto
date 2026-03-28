"""Inspect and manipulate Godot resources (.tres, .tscn)."""

from __future__ import annotations

import rich_click as click


@click.group(invoke_without_command=True)
@click.pass_context
def resource(ctx: click.Context) -> None:
    """Inspect and manipulate Godot resources (.tres, .tscn)."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
