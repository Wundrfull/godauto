"""Create and manage Godot Theme resources."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rich_click as click

from auto_godot.errors import ProjectError
from auto_godot.formats.tres import (
    GdResource,
    SubResource,
    serialize_tres_file,
)
from auto_godot.formats.values import Color
from auto_godot.output import emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def theme(ctx: click.Context) -> None:
    """Create and manage Godot Theme resources."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# StyleBox types
_STYLEBOX_TYPES = {"flat", "empty", "line", "texture"}


def _parse_color(color_str: str) -> Color:
    """Parse a color string into a Godot Color.

    Accepts hex (#RRGGBB, #RRGGBBAA) or named colors.
    """
    named_colors = {
        "white": Color(1, 1, 1, 1),
        "black": Color(0, 0, 0, 1),
        "red": Color(1, 0, 0, 1),
        "green": Color(0, 1, 0, 1),
        "blue": Color(0, 0, 1, 1),
        "yellow": Color(1, 1, 0, 1),
        "transparent": Color(0, 0, 0, 0),
        "gray": Color(0.5, 0.5, 0.5, 1),
        "grey": Color(0.5, 0.5, 0.5, 1),
    }

    lower = color_str.lower().strip()
    if lower in named_colors:
        return named_colors[lower]

    if lower.startswith("#"):
        hex_str = lower[1:]
        if len(hex_str) == 6:
            r = int(hex_str[0:2], 16) / 255.0
            g = int(hex_str[2:4], 16) / 255.0
            b = int(hex_str[4:6], 16) / 255.0
            return Color(r, g, b, 1)
        elif len(hex_str) == 8:
            r = int(hex_str[0:2], 16) / 255.0
            g = int(hex_str[2:4], 16) / 255.0
            b = int(hex_str[4:6], 16) / 255.0
            a = int(hex_str[6:8], 16) / 255.0
            return Color(r, g, b, a)

    raise ProjectError(
        message=f"Invalid color: '{color_str}'",
        code="INVALID_COLOR",
        fix="Use hex (#RRGGBB or #RRGGBBAA) or named colors (white, black, red, green, blue, yellow, transparent)",
    )


def _build_stylebox_flat(
    bg_color: Color,
    border_color: Color | None,
    border_width: int,
    corner_radius: int,
    content_margin: int,
) -> dict[str, Any]:
    """Build properties for a StyleBoxFlat sub-resource."""
    props: dict[str, Any] = {
        "bg_color": bg_color,
    }
    if border_color is not None and border_width > 0:
        props["border_color"] = border_color
        props["border_width_left"] = border_width
        props["border_width_top"] = border_width
        props["border_width_right"] = border_width
        props["border_width_bottom"] = border_width
    if corner_radius > 0:
        props["corner_radius_top_left"] = corner_radius
        props["corner_radius_top_right"] = corner_radius
        props["corner_radius_bottom_right"] = corner_radius
        props["corner_radius_bottom_left"] = corner_radius
    if content_margin > 0:
        props["content_margin_left"] = float(content_margin)
        props["content_margin_top"] = float(content_margin)
        props["content_margin_right"] = float(content_margin)
        props["content_margin_bottom"] = float(content_margin)
    return props


@theme.command("create")
@click.option(
    "--base-color", default="#2d2d3d",
    help="Base background color (hex or name, default: #2d2d3d)",
)
@click.option(
    "--accent-color", default="#478cbf",
    help="Accent/highlight color (hex or name, default: #478cbf - Godot blue)",
)
@click.option(
    "--text-color", default="#ffffff",
    help="Default text color (hex or name, default: white)",
)
@click.option(
    "--font-size", default=14, type=int,
    help="Default font size (default: 14)",
)
@click.option(
    "--border-width", default=1, type=int,
    help="Border width for panels and buttons (default: 1)",
)
@click.option(
    "--corner-radius", default=4, type=int,
    help="Corner radius for rounded elements (default: 4)",
)
@click.option(
    "--margin", default=8, type=int,
    help="Content margin for panels (default: 8)",
)
@click.argument("output_path", type=click.Path())
@click.pass_context
def create(
    ctx: click.Context,
    base_color: str,
    accent_color: str,
    text_color: str,
    font_size: int,
    border_width: int,
    corner_radius: int,
    margin: int,
    output_path: str,
) -> None:
    """Create a Godot Theme .tres with common UI styles.

    Generates StyleBoxFlat resources for Panel, Button (normal/hover/pressed),
    and Label styles with consistent colors and spacing.

    Examples:

      auto-godot theme create ui/game_theme.tres

      auto-godot theme create --base-color "#1a1a2e" --accent-color "#e94560" --font-size 16 ui/dark_theme.tres
    """
    try:
        bg = _parse_color(base_color)
        accent = _parse_color(accent_color)
        text = _parse_color(text_color)

        # Derived colors
        bg_lighter = Color(
            min(bg.r + 0.1, 1), min(bg.g + 0.1, 1), min(bg.b + 0.1, 1), bg.a
        )
        bg_darker = Color(
            max(bg.r - 0.05, 0), max(bg.g - 0.05, 0), max(bg.b - 0.05, 0), bg.a
        )
        accent_hover = Color(
            min(accent.r + 0.1, 1), min(accent.g + 0.1, 1), min(accent.b + 0.1, 1), accent.a
        )
        accent_pressed = Color(
            max(accent.r - 0.1, 0), max(accent.g - 0.1, 0), max(accent.b - 0.1, 0), accent.a
        )
        border = Color(
            min(bg.r + 0.2, 1), min(bg.g + 0.2, 1), min(bg.b + 0.2, 1), bg.a
        )

        sub_resources: list[SubResource] = []

        # Panel normal style
        sub_resources.append(SubResource(
            type="StyleBoxFlat", id="panel_normal",
            properties=_build_stylebox_flat(bg, border, border_width, corner_radius, margin),
        ))

        # Button normal
        sub_resources.append(SubResource(
            type="StyleBoxFlat", id="button_normal",
            properties=_build_stylebox_flat(bg_lighter, border, border_width, corner_radius, 4),
        ))

        # Button hover
        sub_resources.append(SubResource(
            type="StyleBoxFlat", id="button_hover",
            properties=_build_stylebox_flat(accent_hover, accent, border_width, corner_radius, 4),
        ))

        # Button pressed
        sub_resources.append(SubResource(
            type="StyleBoxFlat", id="button_pressed",
            properties=_build_stylebox_flat(accent_pressed, accent, border_width, corner_radius, 4),
        ))

        # Button focus
        sub_resources.append(SubResource(
            type="StyleBoxFlat", id="button_focus",
            properties=_build_stylebox_flat(bg_lighter, accent, 2, corner_radius, 4),
        ))

        # LineEdit/TextEdit normal
        sub_resources.append(SubResource(
            type="StyleBoxFlat", id="input_normal",
            properties=_build_stylebox_flat(bg_darker, border, border_width, corner_radius, 4),
        ))

        # Build resource properties (theme overrides per control type)
        resource_props: dict[str, Any] = {}

        # Panel styles
        resource_props["Panel/styles/panel"] = _sub_ref("panel_normal")

        # Button styles
        resource_props["Button/styles/normal"] = _sub_ref("button_normal")
        resource_props["Button/styles/hover"] = _sub_ref("button_hover")
        resource_props["Button/styles/pressed"] = _sub_ref("button_pressed")
        resource_props["Button/styles/focus"] = _sub_ref("button_focus")

        # Button colors
        resource_props["Button/colors/font_color"] = text
        resource_props["Button/colors/font_hover_color"] = text
        resource_props["Button/colors/font_pressed_color"] = text

        # Button font size
        resource_props["Button/font_sizes/font_size"] = font_size

        # Label
        resource_props["Label/colors/font_color"] = text
        resource_props["Label/font_sizes/font_size"] = font_size

        # LineEdit
        resource_props["LineEdit/styles/normal"] = _sub_ref("input_normal")
        resource_props["LineEdit/colors/font_color"] = text
        resource_props["LineEdit/font_sizes/font_size"] = font_size

        resource = GdResource(
            type="Theme",
            format=3,
            uid=None,
            load_steps=len(sub_resources) + 1,
            ext_resources=[],
            sub_resources=sub_resources,
            resource_properties=resource_props,
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        serialize_tres_file(resource, out)

        data = {
            "created": True,
            "path": str(out),
            "base_color": base_color,
            "accent_color": accent_color,
            "text_color": text_color,
            "font_size": font_size,
            "stylebox_count": len(sub_resources),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Created theme at {data['path']} "
                f"(base={data['base_color']}, accent={data['accent_color']}, "
                f"{data['stylebox_count']} styleboxes)"
            )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


def _sub_ref(sub_id: str) -> Any:
    """Create a SubResource reference."""
    from auto_godot.formats.values import SubResourceRef
    return SubResourceRef(sub_id)


@theme.command("create-stylebox")
@click.option(
    "--bg-color", required=True,
    help="Background color (hex or name)",
)
@click.option(
    "--border-color", default=None,
    help="Border color (hex or name)",
)
@click.option(
    "--border-width", default=0, type=int,
    help="Border width in pixels (default: 0)",
)
@click.option(
    "--corner-radius", default=0, type=int,
    help="Corner radius in pixels (default: 0)",
)
@click.option(
    "--margin", default=0, type=int,
    help="Content margin in pixels (default: 0)",
)
@click.argument("output_path", type=click.Path())
@click.pass_context
def create_stylebox(
    ctx: click.Context,
    bg_color: str,
    border_color: str | None,
    border_width: int,
    corner_radius: int,
    margin: int,
    output_path: str,
) -> None:
    """Create a standalone StyleBoxFlat .tres resource.

    Examples:

      auto-godot theme create-stylebox --bg-color "#1a1a2e" --corner-radius 8 --margin 12 ui/panel_bg.tres

      auto-godot theme create-stylebox --bg-color red --border-color white --border-width 2 ui/alert.tres
    """
    try:
        bg = _parse_color(bg_color)
        border = _parse_color(border_color) if border_color else None

        props = _build_stylebox_flat(bg, border, border_width, corner_radius, margin)

        resource = GdResource(
            type="StyleBoxFlat",
            format=3,
            uid=None,
            load_steps=None,
            ext_resources=[],
            sub_resources=[],
            resource_properties=props,
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        serialize_tres_file(resource, out)

        data = {
            "created": True,
            "path": str(out),
            "bg_color": bg_color,
            "border_color": border_color,
            "corner_radius": corner_radius,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Created StyleBoxFlat at {data['path']} (bg={data['bg_color']})")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)
