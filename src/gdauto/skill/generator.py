"""SKILL.md generator using Click CLI introspection.

Walks the entire Click command tree via to_info_dict() and renders a
structured markdown document listing all commands, arguments, options,
help text, and one usage example per command.
"""

from __future__ import annotations

import rich_click as click


def generate_skill_md() -> str:
    """Generate a SKILL.md document from the gdauto CLI command tree.

    Creates a fresh Click context for introspection (not relying on any
    invocation context), calls to_info_dict() to get the full recursive
    command tree, and renders it to markdown.
    """
    from gdauto.cli import cli

    ctx = click.Context(cli, info_name="gdauto")
    info = cli.to_info_dict(ctx)
    return _render_skill(info)


def _render_skill(info: dict) -> str:
    """Build the complete SKILL.md markdown from a to_info_dict() result."""
    lines: list[str] = []

    # Title and root help
    lines.append("# gdauto")
    lines.append("")
    if info.get("help"):
        lines.append(info["help"].strip())
        lines.append("")

    # Global options
    lines.append("## Global Options")
    lines.append("")
    _render_global_options(info.get("params", []), lines)
    lines.append("")

    # Commands section
    lines.append("## Commands")
    lines.append("")

    commands = info.get("commands", {})
    for cmd_name in sorted(commands):
        cmd_info = commands[cmd_name]
        if _should_skip(cmd_info):
            continue
        _render_command(cmd_name, cmd_info, "gdauto", lines)

    return "\n".join(lines)


def _render_global_options(params: list[dict], lines: list[str]) -> None:
    """Render root-level options as a markdown bullet list."""
    for param in params:
        if param.get("param_type_name") != "option":
            continue
        opts = ", ".join(f"`{o}`" for o in param.get("opts", []))
        help_text = param.get("help", "") or ""
        lines.append(f"- {opts}: {help_text}")


def _render_command(
    name: str,
    cmd_info: dict,
    parent_path: str,
    lines: list[str],
) -> None:
    """Render a single command or group with its subcommands recursively."""
    if _should_skip(cmd_info):
        return

    full_path = f"{parent_path} {name}"
    args_str = _format_arguments(cmd_info.get("params", []))
    heading = f"### {full_path}"
    if args_str:
        heading += f" {args_str}"
    lines.append(heading)
    lines.append("")

    # Help text
    help_text = cmd_info.get("help", "")
    if help_text:
        # Take only the first paragraph for conciseness
        first_para = help_text.strip().split("\n\n")[0].strip()
        lines.append(first_para)
        lines.append("")

    # Render params (arguments and options)
    _render_params(cmd_info.get("params", []), lines)

    # Example
    example = _generate_example(full_path, cmd_info.get("params", []))
    if example:
        lines.append("**Example:**")
        lines.append("```")
        lines.append(example)
        lines.append("```")
        lines.append("")

    # Recurse into subcommands
    sub_commands = cmd_info.get("commands", {})
    for sub_name in sorted(sub_commands):
        sub_info = sub_commands[sub_name]
        _render_command(sub_name, sub_info, full_path, lines)


def _format_arguments(params: list[dict]) -> str:
    """Format argument names as uppercase placeholders for the heading."""
    args = []
    for p in params:
        if p.get("param_type_name") == "argument":
            arg_name = p.get("name", "").upper()
            if p.get("required", True):
                args.append(arg_name)
            else:
                args.append(f"[{arg_name}]")
    return " ".join(args)


def _render_params(params: list[dict], lines: list[str]) -> None:
    """Render arguments and options for a command as markdown lists."""
    arguments = [p for p in params if p.get("param_type_name") == "argument"]
    options = [
        p for p in params
        if p.get("param_type_name") == "option" and not _is_help_option(p)
    ]

    if arguments:
        lines.append("**Arguments:**")
        for arg in arguments:
            name = arg.get("name", "").upper()
            req = "required" if arg.get("required", True) else "optional"
            help_text = arg.get("help", "") or ""
            if help_text:
                lines.append(f"- `{name}` ({req}): {help_text}")
            else:
                lines.append(f"- `{name}` ({req})")
        lines.append("")

    if options:
        lines.append("**Options:**")
        for opt in options:
            opts_str = ", ".join(f"`{o}`" for o in opt.get("opts", []))
            help_text = opt.get("help", "") or ""
            lines.append(f"- {opts_str}: {help_text}")
        lines.append("")


def _is_help_option(param: dict) -> bool:
    """Check if a parameter is the built-in --help option."""
    opts = param.get("opts", [])
    return "--help" in opts


# Known example overrides for commands with well-known argument patterns
_EXAMPLE_OVERRIDES: dict[str, str] = {
    "gdauto project info": "gdauto project info ./my-game",
    "gdauto project validate": "gdauto project validate ./my-game",
    "gdauto project create": "gdauto project create my-new-game",
    "gdauto sprite import-aseprite": "gdauto sprite import-aseprite character.json",
    "gdauto sprite split": "gdauto sprite split sheet.png --frame-size 32x32",
    "gdauto sprite create-atlas": (
        "gdauto sprite create-atlas a.png b.png -o atlas.png"
    ),
    "gdauto sprite validate": "gdauto sprite validate character.tres",
    "gdauto resource inspect": "gdauto resource inspect player.tres",
    "gdauto scene list": "gdauto scene list .",
    "gdauto scene create": "gdauto scene create definition.json",
    "gdauto export release": 'gdauto export release --preset "Windows Desktop"',
    "gdauto export debug": 'gdauto export debug --preset "Windows Desktop"',
    "gdauto export pack": "gdauto export pack --preset Export",
    "gdauto skill generate": "gdauto skill generate -o SKILL.md",
}


def _generate_example(command_path: str, params: list[dict]) -> str:
    """Generate one usage example for a command.

    Uses known overrides for commands with well-known patterns. For
    unknown commands, builds an example from argument param names.
    """
    if command_path in _EXAMPLE_OVERRIDES:
        return _EXAMPLE_OVERRIDES[command_path]

    # Build from param names
    parts = [command_path]
    for p in params:
        if p.get("param_type_name") == "argument":
            name = p.get("name", "arg")
            parts.append(f"<{name}>")
    return " ".join(parts)


def _should_skip(cmd_info: dict) -> bool:
    """Return True if a command should be excluded from the output."""
    return bool(cmd_info.get("hidden")) or bool(cmd_info.get("deprecated"))
