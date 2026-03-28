"""Manage Godot projects (info, validate, create)."""

from __future__ import annotations

import rich_click as click


@click.group(invoke_without_command=True)
@click.pass_context
def project(ctx: click.Context) -> None:
    """Manage Godot projects (info, validate, create)."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
