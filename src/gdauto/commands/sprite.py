"""Sprite sheet and SpriteFrames tools."""

from __future__ import annotations

import rich_click as click


@click.group(invoke_without_command=True)
@click.pass_context
def sprite(ctx: click.Context) -> None:
    """Sprite sheet and SpriteFrames tools."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
