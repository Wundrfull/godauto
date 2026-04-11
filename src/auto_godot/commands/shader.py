"""Create and manage shader resources."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rich_click as click

from auto_godot.errors import ProjectError
from auto_godot.formats.tres import (
    GdResource,
    serialize_tres_file,
)
from auto_godot.output import emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def shader(ctx: click.Context) -> None:
    """Create and manage shader resources."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Built-in shader templates for common game effects
_SHADER_TEMPLATES: dict[str, tuple[str, str]] = {
    "flash": (
        "canvas_item",
        'shader_type canvas_item;\n'
        'uniform vec4 flash_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);\n'
        'uniform float flash_amount : hint_range(0.0, 1.0) = 0.0;\n'
        'void fragment() {\n'
        '\tvec4 tex = texture(TEXTURE, UV);\n'
        '\tCOLOR = mix(tex, flash_color, flash_amount);\n'
        '\tCOLOR.a = tex.a;\n'
        '}\n'
    ),
    "outline": (
        "canvas_item",
        'shader_type canvas_item;\n'
        'uniform vec4 outline_color : source_color = vec4(0.0, 0.0, 0.0, 1.0);\n'
        'uniform float outline_width : hint_range(0.0, 10.0) = 1.0;\n'
        'void fragment() {\n'
        '\tvec4 tex = texture(TEXTURE, UV);\n'
        '\tfloat a = tex.a;\n'
        '\tvec2 size = TEXTURE_PIXEL_SIZE * outline_width;\n'
        '\ta += texture(TEXTURE, UV + vec2(-size.x, 0)).a;\n'
        '\ta += texture(TEXTURE, UV + vec2(size.x, 0)).a;\n'
        '\ta += texture(TEXTURE, UV + vec2(0, -size.y)).a;\n'
        '\ta += texture(TEXTURE, UV + vec2(0, size.y)).a;\n'
        '\ta = min(a, 1.0);\n'
        '\tvec4 outline = vec4(outline_color.rgb, a * outline_color.a);\n'
        '\tCOLOR = mix(outline, tex, tex.a);\n'
        '}\n'
    ),
    "dissolve": (
        "canvas_item",
        'shader_type canvas_item;\n'
        'uniform float dissolve_amount : hint_range(0.0, 1.0) = 0.0;\n'
        'uniform float edge_width : hint_range(0.0, 0.2) = 0.05;\n'
        'uniform vec4 edge_color : source_color = vec4(1.0, 0.5, 0.0, 1.0);\n'
        'void fragment() {\n'
        '\tvec4 tex = texture(TEXTURE, UV);\n'
        '\tfloat noise = fract(sin(dot(UV, vec2(12.9898, 78.233))) * 43758.5453);\n'
        '\tif (noise < dissolve_amount) {\n'
        '\t\tdiscard;\n'
        '\t} else if (noise < dissolve_amount + edge_width) {\n'
        '\t\tCOLOR = edge_color;\n'
        '\t} else {\n'
        '\t\tCOLOR = tex;\n'
        '\t}\n'
        '}\n'
    ),
    "grayscale": (
        "canvas_item",
        'shader_type canvas_item;\n'
        'uniform float amount : hint_range(0.0, 1.0) = 1.0;\n'
        'void fragment() {\n'
        '\tvec4 tex = texture(TEXTURE, UV);\n'
        '\tfloat gray = dot(tex.rgb, vec3(0.299, 0.587, 0.114));\n'
        '\tCOLOR.rgb = mix(tex.rgb, vec3(gray), amount);\n'
        '\tCOLOR.a = tex.a;\n'
        '}\n'
    ),
    "pixelate": (
        "canvas_item",
        'shader_type canvas_item;\n'
        'uniform float pixel_size : hint_range(1.0, 32.0) = 4.0;\n'
        'void fragment() {\n'
        '\tvec2 size = vec2(textureSize(TEXTURE, 0));\n'
        '\tvec2 grid_uv = round(UV * size / pixel_size) * pixel_size / size;\n'
        '\tCOLOR = texture(TEXTURE, grid_uv);\n'
        '}\n'
    ),
    "color_replace": (
        "canvas_item",
        'shader_type canvas_item;\n'
        'uniform vec4 target_color : source_color = vec4(1.0, 0.0, 0.0, 1.0);\n'
        'uniform vec4 replace_color : source_color = vec4(0.0, 0.0, 1.0, 1.0);\n'
        'uniform float threshold : hint_range(0.0, 1.0) = 0.1;\n'
        'void fragment() {\n'
        '\tvec4 tex = texture(TEXTURE, UV);\n'
        '\tfloat dist = distance(tex.rgb, target_color.rgb);\n'
        '\tif (dist < threshold) {\n'
        '\t\tCOLOR = vec4(replace_color.rgb, tex.a);\n'
        '\t} else {\n'
        '\t\tCOLOR = tex;\n'
        '\t}\n'
        '}\n'
    ),
}


class _RawStr:
    """Wraps a raw string so serialize_value uses __str__ without quoting."""

    def __init__(self, raw: str) -> None:
        self._raw = raw

    def __str__(self) -> str:
        return self._raw

    def __repr__(self) -> str:
        return self._raw


@shader.command("create")
@click.option(
    "--template", "template_name", default=None,
    type=click.Choice(sorted(_SHADER_TEMPLATES)),
    help="Use a built-in shader template",
)
@click.option(
    "--code", "shader_code", default=None,
    help="Custom shader code (inline GLSL string)",
)
@click.option(
    "--file", "shader_file", default=None,
    type=click.Path(exists=True),
    help="Read shader code from a .gdshader file",
)
@click.argument("output_path", type=click.Path())
@click.pass_context
def create(
    ctx: click.Context,
    template_name: str | None,
    shader_code: str | None,
    shader_file: str | None,
    output_path: str,
) -> None:
    """Create a Shader .tres resource from a template or custom code.

    Examples:

      auto-godot shader create --template flash shaders/flash.tres

      auto-godot shader create --template outline shaders/outline.tres

      auto-godot shader create --file shaders/custom.gdshader shaders/custom_shader.tres
    """
    try:
        if template_name:
            _shader_type, code = _SHADER_TEMPLATES[template_name]
        elif shader_file:
            code = Path(shader_file).read_text(encoding="utf-8")
        elif shader_code:
            code = shader_code
        else:
            raise ProjectError(
                message="No shader source specified",
                code="NO_SHADER_SOURCE",
                fix="Provide --template, --code, or --file",
            )

        resource = GdResource(
            type="Shader",
            format=3,
            uid=None,
            load_steps=None,
            ext_resources=[],
            sub_resources=[],
            resource_properties={"code": code},
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        serialize_tres_file(resource, out)

        data = {
            "created": True,
            "path": str(out),
            "template": template_name,
            "code_length": len(code),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            src = data["template"] or "custom"
            click.echo(f"Created shader at {data['path']} ({src}, {data['code_length']} chars)")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


@shader.command("create-material")
@click.option(
    "--shader", "shader_path", required=True,
    help="res:// path to the Shader .tres resource",
)
@click.argument("output_path", type=click.Path())
@click.pass_context
def create_material(
    ctx: click.Context,
    shader_path: str,
    output_path: str,
) -> None:
    """Create a ShaderMaterial .tres that references a Shader resource.

    Examples:

      auto-godot shader create-material --shader res://shaders/flash.tres materials/flash_material.tres
    """
    try:
        from auto_godot.formats.tres import ExtResource
        from auto_godot.formats.values import ExtResourceRef

        resource = GdResource(
            type="ShaderMaterial",
            format=3,
            uid=None,
            load_steps=2,
            ext_resources=[ExtResource(
                type="Shader",
                path=shader_path,
                id="1_shader",
                uid=None,
            )],
            sub_resources=[],
            resource_properties={
                "shader": ExtResourceRef("1_shader"),
            },
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        serialize_tres_file(resource, out)

        data = {
            "created": True,
            "path": str(out),
            "shader": shader_path,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Created ShaderMaterial at {data['path']} (shader={data['shader']})")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


@shader.command("list-templates")
@click.pass_context
def list_templates(ctx: click.Context) -> None:
    """List available built-in shader templates."""
    templates = []
    for name, (shader_type, code) in sorted(_SHADER_TEMPLATES.items()):
        # Count uniforms
        uniform_count = code.count("uniform ")
        templates.append({
            "name": name,
            "type": shader_type,
            "uniforms": uniform_count,
            "lines": code.count("\n"),
        })

    data = {
        "templates": templates,
        "count": len(templates),
    }

    def _human(data: dict[str, Any], verbose: bool = False) -> None:
        click.echo(f"Shader templates ({data['count']}):")
        for t in data["templates"]:
            click.echo(f"  {t['name']} ({t['type']}, {t['uniforms']} uniforms, {t['lines']} lines)")

    emit(data, _human, ctx)
