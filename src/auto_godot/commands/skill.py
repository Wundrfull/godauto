"""SKILL.md generation for AI agent discoverability."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rich_click as click

from auto_godot.output import emit
from auto_godot.skill.generator import generate_skill_md


@click.group(invoke_without_command=True)
@click.pass_context
def skill(ctx: click.Context) -> None:
    """AI agent discoverability tools."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@skill.command("generate")
@click.option(
    "-o", "--output",
    type=click.Path(),
    default="SKILL.md",
    help="Output file path. Default: SKILL.md in current directory.",
)
@click.pass_context
def skill_generate(ctx: click.Context, output: str) -> None:
    """Generate SKILL.md from the CLI command tree.

    Auto-generates a markdown document listing all commands, arguments,
    options, help text, and usage examples. AI agents use this for
    tool discovery.
    """
    content = generate_skill_md()
    output_path = Path(output)
    output_path.write_text(content, encoding="utf-8")
    emit(
        {"path": str(output_path), "size": len(content)},
        _display_skill_result,
        ctx,
    )


def _display_skill_result(data: dict[str, Any], verbose: bool = False) -> None:
    """Display skill generation result in human-readable format."""
    click.echo(f"Generated {data['path']} ({data['size']} bytes)")
