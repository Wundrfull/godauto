"""Physics body and collision shape management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rich_click as click

from auto_godot.errors import ProjectError
from auto_godot.formats.tres import SubResource
from auto_godot.formats.tscn import (
    SceneNode,
    parse_tscn,
    serialize_tscn,
)
from auto_godot.formats.values import Vector2
from auto_godot.output import emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def physics(ctx: click.Context) -> None:
    """Manage physics bodies and collision shapes."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Physics body types
_BODY_TYPES = {
    "static": "StaticBody2D",
    "rigid": "RigidBody2D",
    "character": "CharacterBody2D",
    "area": "Area2D",
}

# Shape types
_SHAPE_TYPES = {"rectangle", "circle", "capsule", "segment", "world_boundary"}


def _next_sub_resource_id(scene_text: str, prefix: str = "shape") -> str:
    """Find the next available sub_resource ID."""
    import re
    ids = re.findall(r'id="([^"]+)"', scene_text)
    counter = 1
    while f"{prefix}_{counter}" in ids:
        counter += 1
    return f"{prefix}_{counter}"


@physics.command("add-body")
@click.option(
    "--scene", "scene_path", required=True,
    type=click.Path(exists=True),
    help="Path to the .tscn scene file",
)
@click.option(
    "--name", "node_name", required=True,
    help="Name for the physics body node",
)
@click.option(
    "--type", "body_type", required=True,
    type=click.Choice(sorted(_BODY_TYPES)),
    help="Physics body type",
)
@click.option(
    "--shape", "shape_type", default="rectangle",
    type=click.Choice(sorted(_SHAPE_TYPES)),
    help="Collision shape type (default: rectangle)",
)
@click.option(
    "--size", default="32,32",
    help="Shape size as 'width,height' for rectangle/capsule, or 'radius' for circle (default: 32,32)",
)
@click.option(
    "--parent", "parent_path", default=None,
    help="Parent node path (default: root)",
)
@click.pass_context
def add_body(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    body_type: str,
    shape_type: str,
    size: str,
    parent_path: str | None,
) -> None:
    """Add a physics body with collision shape to a scene.

    Examples:

      auto-godot physics add-body --scene scenes/main.tscn --name Player --type character --shape rectangle --size 16,32

      auto-godot physics add-body --scene scenes/main.tscn --name Coin --type area --shape circle --size 12

      auto-godot physics add-body --scene scenes/game.tscn --name Wall --type static --shape rectangle --size 64,16
    """
    try:
        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene = parse_tscn(text)

        parent = parent_path or "."

        # Check for duplicate
        for node in scene.nodes:
            if node.name == node_name and node.parent == parent:
                raise ProjectError(
                    message=f"Node '{node_name}' already exists",
                    code="NODE_EXISTS",
                    fix="Choose a different name",
                )

        # Parse size
        width, height, radius = _parse_size(size, shape_type)

        # Create shape sub-resource
        shape_id = _next_sub_resource_id(text)
        shape_props = _build_shape_properties(shape_type, width, height, radius)
        shape_sub = SubResource(
            type=_shape_resource_type(shape_type),
            id=shape_id,
            properties=shape_props,
        )
        scene.sub_resources.append(shape_sub)

        # Create body node
        godot_type = _BODY_TYPES[body_type]
        scene.nodes.append(SceneNode(
            name=node_name,
            type=godot_type,
            parent=parent,
            properties={},
        ))

        # Create collision shape node
        from auto_godot.formats.values import SubResourceRef
        body_parent = f"{parent}/{node_name}" if parent != "." else node_name
        # Handle root-relative paths
        body_parent = node_name if parent == "." else f"{parent}/{node_name}"

        scene.nodes.append(SceneNode(
            name="CollisionShape2D",
            type="CollisionShape2D",
            parent=body_parent,
            properties={"shape": SubResourceRef(shape_id)},
        ))

        # Update load_steps
        scene.load_steps = len(scene.ext_resources) + len(scene.sub_resources) + 1

        # Write back
        scene._raw_header = None
        scene._raw_sections = None
        output = serialize_tscn(scene)
        path.write_text(output, encoding="utf-8")

        data = {
            "added": True,
            "name": node_name,
            "body_type": godot_type,
            "shape_type": shape_type,
            "size": size,
            "scene": scene_path,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Added {data['body_type']} '{data['name']}' with "
                f"{data['shape_type']} collision shape ({data['size']})"
            )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


def _parse_size(
    size_str: str, shape_type: str
) -> tuple[float, float, float]:
    """Parse size string into (width, height, radius)."""
    parts = size_str.split(",")
    if shape_type == "circle":
        radius = float(parts[0])
        return 0, 0, radius
    elif shape_type in ("rectangle", "capsule"):
        if len(parts) < 2:
            raise ProjectError(
                message=f"Shape '{shape_type}' requires 'width,height' size format",
                code="INVALID_SIZE",
                fix="Use format 'width,height', e.g., '32,32'",
            )
        return float(parts[0]), float(parts[1]), 0
    elif shape_type == "segment":
        if len(parts) < 2:
            raise ProjectError(
                message="Segment shape requires 'length,0' format",
                code="INVALID_SIZE",
                fix="Use 'length,0' format",
            )
        return float(parts[0]), float(parts[1]), 0
    return float(parts[0]) if parts else 32, float(parts[1]) if len(parts) > 1 else 32, 0


def _shape_resource_type(shape_type: str) -> str:
    """Map shape type to Godot resource type name."""
    return {
        "rectangle": "RectangleShape2D",
        "circle": "CircleShape2D",
        "capsule": "CapsuleShape2D",
        "segment": "SegmentShape2D",
        "world_boundary": "WorldBoundaryShape2D",
    }[shape_type]


def _build_shape_properties(
    shape_type: str,
    width: float,
    height: float,
    radius: float,
) -> dict[str, Any]:
    """Build shape-specific properties."""
    if shape_type == "rectangle":
        return {"size": Vector2(width, height)}
    elif shape_type == "circle":
        return {"radius": radius}
    elif shape_type == "capsule":
        return {"radius": width / 2, "height": height}
    elif shape_type == "segment":
        return {"a": Vector2(0, 0), "b": Vector2(width, height)}
    elif shape_type == "world_boundary":
        return {}
    return {}


@physics.command("add-shape")
@click.option(
    "--scene", "scene_path", required=True,
    type=click.Path(exists=True),
    help="Path to the .tscn scene file",
)
@click.option(
    "--parent", "parent_path", required=True,
    help="Parent physics body node path (e.g., Player, Enemies/Slime)",
)
@click.option(
    "--shape", "shape_type", default="rectangle",
    type=click.Choice(sorted(_SHAPE_TYPES)),
    help="Collision shape type",
)
@click.option(
    "--size", default="32,32",
    help="Shape dimensions",
)
@click.option(
    "--name", "shape_name", default="CollisionShape2D",
    help="Name for the shape node (default: CollisionShape2D)",
)
@click.pass_context
def add_shape(
    ctx: click.Context,
    scene_path: str,
    parent_path: str,
    shape_type: str,
    size: str,
    shape_name: str,
) -> None:
    """Add a collision shape to an existing physics body in a scene.

    Examples:

      auto-godot physics add-shape --scene scenes/main.tscn --parent Player --shape circle --size 16

      auto-godot physics add-shape --scene scenes/main.tscn --parent Wall --shape rectangle --size 64,16 --name HitBox
    """
    try:
        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene = parse_tscn(text)

        width, height, radius = _parse_size(size, shape_type)

        shape_id = _next_sub_resource_id(text)
        shape_props = _build_shape_properties(shape_type, width, height, radius)
        shape_sub = SubResource(
            type=_shape_resource_type(shape_type),
            id=shape_id,
            properties=shape_props,
        )
        scene.sub_resources.append(shape_sub)

        from auto_godot.formats.values import SubResourceRef
        scene.nodes.append(SceneNode(
            name=shape_name,
            type="CollisionShape2D",
            parent=parent_path,
            properties={"shape": SubResourceRef(shape_id)},
        ))

        scene.load_steps = len(scene.ext_resources) + len(scene.sub_resources) + 1
        scene._raw_header = None
        scene._raw_sections = None
        output = serialize_tscn(scene)
        path.write_text(output, encoding="utf-8")

        data = {
            "added": True,
            "shape_type": shape_type,
            "size": size,
            "parent": parent_path,
            "name": shape_name,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Added {data['shape_type']} CollisionShape2D to {data['parent']}"
            )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)
