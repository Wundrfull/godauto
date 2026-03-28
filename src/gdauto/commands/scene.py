"""Scene file operations."""

from __future__ import annotations

import rich_click as click


@click.group(invoke_without_command=True)
@click.pass_context
def scene(ctx: click.Context) -> None:
    """Scene file operations."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
