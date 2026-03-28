"""TileSet creation and terrain automation."""

from __future__ import annotations

import rich_click as click


@click.group(invoke_without_command=True)
@click.pass_context
def tileset(ctx: click.Context) -> None:
    """TileSet creation and terrain automation."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
