"""Generate and manage GDScript files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rich_click as click

from gdauto.errors import ProjectError
from gdauto.output import emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def script(ctx: click.Context) -> None:
    """Generate and manage GDScript files."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Common Godot base classes for validation
_BASE_CLASSES = {
    "Node", "Node2D", "Node3D", "Control", "CanvasLayer",
    "CharacterBody2D", "CharacterBody3D", "RigidBody2D", "RigidBody3D",
    "StaticBody2D", "StaticBody3D", "Area2D", "Area3D",
    "Sprite2D", "Sprite3D", "AnimatedSprite2D", "AnimatedSprite3D",
    "Camera2D", "Camera3D", "Light2D",
    "AudioStreamPlayer", "AudioStreamPlayer2D", "AudioStreamPlayer3D",
    "Timer", "HTTPRequest", "TileMapLayer",
    "Resource", "RefCounted", "Object",
    "Label", "Button", "TextureButton", "TextureRect",
    "Panel", "PanelContainer", "MarginContainer",
    "HBoxContainer", "VBoxContainer", "GridContainer",
    "ScrollContainer", "TabContainer", "CenterContainer",
    "LineEdit", "TextEdit", "RichTextLabel",
    "ProgressBar", "HSlider", "VSlider", "SpinBox",
    "ColorRect", "SubViewport", "SubViewportContainer",
    "Path2D", "PathFollow2D", "Path3D", "PathFollow3D",
    "CPUParticles2D", "GPUParticles2D",
    "CPUParticles3D", "GPUParticles3D",
    "RayCast2D", "RayCast3D",
    "CollisionShape2D", "CollisionShape3D",
    "NavigationAgent2D", "NavigationAgent3D",
}


def _generate_script(
    extends: str,
    class_name: str | None,
    signals: list[str],
    exports: list[tuple[str, str, str]],
    onready: list[tuple[str, str, str]],
    with_ready: bool,
    with_process: bool,
    with_input: bool,
    with_physics: bool,
) -> str:
    """Generate GDScript source code from parameters."""
    lines: list[str] = []

    if class_name:
        lines.append(f"class_name {class_name}")
    lines.append(f"extends {extends}")
    lines.append("")

    if signals:
        for sig in signals:
            lines.append(f"signal {sig}")
        lines.append("")

    if exports:
        for var_name, var_type, default in exports:
            if default:
                lines.append(f"@export var {var_name}: {var_type} = {default}")
            else:
                lines.append(f"@export var {var_name}: {var_type}")
        lines.append("")

    if onready:
        for var_name, var_type, node_path in onready:
            lines.append(f'@onready var {var_name}: {var_type} = ${node_path}')
        lines.append("")

    # Generate lifecycle methods
    methods: list[tuple[str, str]] = []
    if with_ready:
        methods.append(("_ready", "pass"))
    if with_process:
        methods.append(("_process", "pass"))
    if with_physics:
        methods.append(("_physics_process", "pass"))
    if with_input:
        methods.append(("_unhandled_input", "pass"))

    for i, (method_name, body) in enumerate(methods):
        if method_name == "_process":
            lines.append(f"func {method_name}(delta: float) -> void:")
        elif method_name == "_physics_process":
            lines.append(f"func {method_name}(delta: float) -> void:")
        elif method_name == "_unhandled_input":
            lines.append(f"func {method_name}(event: InputEvent) -> void:")
        else:
            lines.append(f"func {method_name}() -> void:")
        lines.append(f"\t{body}")
        if i < len(methods) - 1:
            lines.append("")
            lines.append("")

    # Ensure file ends with newline
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    return text


@script.command()
@click.option("--extends", default="Node2D", help="Base class to extend (default: Node2D)")
@click.option("--class-name", default=None, help="Optional class_name declaration")
@click.option("--signal", "signals", multiple=True, help="Signal declarations (e.g., 'died' or 'health_changed(amount: int)')")
@click.option("--export", "exports", multiple=True, help="Exported vars as 'name:type=default' (e.g., 'speed:float=100.0')")
@click.option("--onready", "onready_vars", multiple=True, help="@onready vars as 'name:Type=NodePath' (e.g., 'sprite:Sprite2D=Sprite2D')")
@click.option("--ready/--no-ready", default=True, help="Include _ready() method (default: yes)")
@click.option("--process/--no-process", default=False, help="Include _process() method")
@click.option("--input/--no-input", "with_input", default=False, help="Include _unhandled_input() method")
@click.option("--physics/--no-physics", default=False, help="Include _physics_process() method")
@click.argument("output_path", type=click.Path())
@click.pass_context
def create(
    ctx: click.Context,
    extends: str,
    class_name: str | None,
    signals: tuple[str, ...],
    exports: tuple[str, ...],
    onready_vars: tuple[str, ...],
    ready: bool,
    process: bool,
    with_input: bool,
    physics: bool,
    output_path: str,
) -> None:
    """Generate a GDScript file with boilerplate.

    Examples:

      gdauto script create --extends CharacterBody2D --export "speed:float=200.0" scripts/player.gd

      gdauto script create --extends Control --signal "clicked" --ready --process scripts/ui/hud.gd
    """
    try:
        parsed_exports = _parse_exports(exports)
        parsed_onready = _parse_onready(onready_vars)

        source = _generate_script(
            extends=extends,
            class_name=class_name,
            signals=list(signals),
            exports=parsed_exports,
            onready=parsed_onready,
            with_ready=ready,
            with_process=process,
            with_input=with_input,
            with_physics=physics,
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(source, encoding="utf-8")

        data = {
            "created": True,
            "path": str(out),
            "extends": extends,
            "class_name": class_name,
            "signals": list(signals),
            "exports": [f"{n}:{t}={d}" if d else f"{n}:{t}" for n, t, d in parsed_exports],
            "lines": source.count("\n"),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Created {data['path']} (extends {data['extends']}, {data['lines']} lines)")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


def _parse_exports(exports: tuple[str, ...]) -> list[tuple[str, str, str]]:
    """Parse 'name:type=default' strings into (name, type, default) tuples."""
    result: list[tuple[str, str, str]] = []
    for exp in exports:
        default = ""
        if "=" in exp:
            left, default = exp.split("=", 1)
        else:
            left = exp

        if ":" not in left:
            raise ProjectError(
                message=f"Invalid export format: '{exp}'. Expected 'name:type' or 'name:type=default'",
                code="INVALID_EXPORT_FORMAT",
                fix="Use format 'name:type=default', e.g., 'speed:float=100.0' or 'health:int'",
            )
        name, var_type = left.split(":", 1)
        result.append((name.strip(), var_type.strip(), default.strip()))
    return result


@script.command("attach")
@click.option("--scene", "scene_path", required=True, type=click.Path(exists=True), help="Scene file to modify")
@click.option("--node", "node_name", required=True, help="Node name to attach the script to")
@click.option("--script", "script_path", required=True, help="res:// path to the script (e.g., res://scripts/player.gd)")
@click.option("--parent", "parent_path", default=None, help="Parent node path to disambiguate")
@click.pass_context
def attach(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    script_path: str,
    parent_path: str | None,
) -> None:
    """Attach a GDScript to a node in a scene file.

    Creates the ext_resource reference and sets the script property on the
    target node. If the script is already attached, reports it.

    Examples:

      gdauto script attach --scene scenes/main.tscn --node Player --script res://scripts/player.gd

      gdauto script attach --scene scenes/level.tscn --node Enemy --script res://scripts/enemy.gd --parent Enemies
    """
    try:
        from gdauto.formats.tscn import ExtResource, parse_tscn, serialize_tscn
        from gdauto.formats.values import ExtResourceRef
        import re

        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene = parse_tscn(text)

        # Find target node
        target = None
        for node in scene.nodes:
            if node.name == node_name:
                if parent_path is None or node.parent == parent_path:
                    target = node
                    break

        if target is None:
            raise ProjectError(
                message=f"Node '{node_name}' not found in scene",
                code="NODE_NOT_FOUND",
                fix="Check the node name and parent path",
            )

        # Check if script already attached
        if "script" in target.properties:
            raise ProjectError(
                message=f"Node '{node_name}' already has a script attached",
                code="SCRIPT_EXISTS",
                fix="Remove the existing script first or choose a different node",
            )

        # Add ext_resource for the script
        existing_ids = {ext.id for ext in scene.ext_resources}
        counter = 1
        ext_id = f"{counter}_script"
        while ext_id in existing_ids:
            counter += 1
            ext_id = f"{counter}_script"

        scene.ext_resources.append(ExtResource(
            type="Script",
            path=script_path,
            id=ext_id,
            uid=None,
        ))

        target.properties["script"] = ExtResourceRef(ext_id)

        # Update load_steps
        scene.load_steps = len(scene.ext_resources) + len(scene.sub_resources) + 1

        scene._raw_header = None
        scene._raw_sections = None
        output = serialize_tscn(scene)
        path.write_text(output, encoding="utf-8")

        data = {
            "attached": True,
            "node": node_name,
            "script": script_path,
            "scene": scene_path,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Attached {data['script']} to '{data['node']}'")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


def _parse_onready(onready_vars: tuple[str, ...]) -> list[tuple[str, str, str]]:
    """Parse 'name:Type=NodePath' strings into (name, type, path) tuples."""
    result: list[tuple[str, str, str]] = []
    for var in onready_vars:
        if "=" not in var:
            raise ProjectError(
                message=f"Invalid onready format: '{var}'. Expected 'name:Type=NodePath'",
                code="INVALID_ONREADY_FORMAT",
                fix="Use format 'name:Type=NodePath', e.g., 'sprite:Sprite2D=Sprite2D'",
            )
        left, node_path = var.split("=", 1)
        if ":" not in left:
            raise ProjectError(
                message=f"Invalid onready format: '{var}'. Expected 'name:Type=NodePath'",
                code="INVALID_ONREADY_FORMAT",
                fix="Use format 'name:Type=NodePath', e.g., 'sprite:Sprite2D=Sprite2D'",
            )
        name, var_type = left.split(":", 1)
        result.append((name.strip(), var_type.strip(), node_path.strip()))
    return result
