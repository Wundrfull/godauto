"""Scene file operations: list and create commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import rich_click as click
from rich.console import Console
from rich.tree import Tree

from gdauto.errors import GdautoError, ProjectError, ValidationError
from gdauto.formats.tscn import SceneNode, parse_tscn, serialize_tscn, serialize_tscn_file
from gdauto.formats.uid import write_uid_file
from gdauto.formats.values import parse_value
from gdauto.output import GlobalConfig, emit, emit_error
from gdauto.scene.builder import build_scene
from gdauto.scene.lister import list_scenes


@click.group(invoke_without_command=True)
@click.pass_context
def scene(ctx: click.Context) -> None:
    """Scene file operations."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@scene.command("list")
@click.argument("path", type=click.Path(exists=False), default=".")
@click.option(
    "--depth",
    type=int,
    default=None,
    help="Limit node tree depth. Default: show full tree.",
)
@click.pass_context
def scene_list(ctx: click.Context, path: str, depth: int | None) -> None:
    """List all scenes in a Godot project directory.

    Shows scene files with their node trees, scripts, and cross-scene
    dependencies. Pass a directory or project.godot path.
    """
    project_root = _resolve_project_root(path)
    if project_root is None:
        emit_error(
            ProjectError(
                message=f"Not a Godot project directory: {path}",
                code="NOT_GODOT_PROJECT",
                fix="Run from a directory containing project.godot or pass the project path",
            ),
            ctx,
        )
        return

    result = list_scenes(project_root, depth=depth)
    emit({"scenes": result}, _print_scene_list, ctx)


def _resolve_project_root(path: str) -> Path | None:
    """Resolve a path to a Godot project root directory.

    If path points to project.godot, uses its parent. If it is a directory,
    checks for project.godot inside. Returns None if not a Godot project.
    """
    p = Path(path)
    if p.is_file() and p.name == "project.godot":
        return p.parent
    if p.is_dir():
        if (p / "project.godot").exists():
            return p
    return None


def _print_scene_list(data: dict[str, Any], verbose: bool = False) -> None:
    """Display scene list in human-readable format using rich trees."""
    console = Console()
    scenes = data["scenes"]
    if not scenes:
        console.print("No scenes found.")
        return

    for scene_info in scenes:
        tree = Tree(f"[bold]{scene_info['path']}[/bold]")
        _add_nodes_to_tree(tree, scene_info.get("nodes", []))
        console.print(tree)

    _print_dependencies(console, scenes)


def _add_nodes_to_tree(tree: Tree, nodes: list[dict[str, Any]]) -> None:
    """Add node entries to a rich Tree for display."""
    for node in nodes:
        type_str = f" [{node['type']}]" if node.get("type") else ""
        tree.add(f"{node['name']}{type_str}")


def _print_dependencies(console: Console, scenes: list[dict[str, Any]]) -> None:
    """Print cross-scene dependency summary if instances exist."""
    has_instances = any(s.get("instances") for s in scenes)
    if not has_instances:
        return
    console.print("\n[bold]Dependencies:[/bold]")
    for s in scenes:
        for inst in s.get("instances", []):
            console.print(f"  {s['path']} -> {inst}")


@scene.command("create")
@click.argument("json_file", type=click.Path(exists=False))
@click.option(
    "-o", "--output",
    type=click.Path(),
    default=None,
    help="Output .tscn path. Default: replaces .json with .tscn.",
)
@click.pass_context
def scene_create(ctx: click.Context, json_file: str, output: str | None) -> None:
    r"""Create a Godot scene (.tscn) from a JSON definition file.

    \b
    JSON FORMAT:
      {
        "root": {
          "name": "Main",
          "type": "Node2D",
          "properties": {"position": "Vector2(100, 50)"},
          "children": [
            {"name": "Player", "type": "Sprite2D", "properties": {}}
          ]
        },
        "resources": [
          {
            "type": "Texture2D",
            "path": "res://sprite.png",
            "assign_to": "Player",
            "property": "texture"
          }
        ]
      }

    \b
    FIELDS:
      root.name       (required) Root node name
      root.type       (required) Godot node type (Node2D, Control, etc.)
      root.properties (optional) Key-value pairs of Godot properties
      root.children   (optional) Array of child node objects (same schema)
      resources       (optional) External resources to create and assign
      resources[].type       Resource type (Texture2D, Script, etc.)
      resources[].path       res:// path to the resource file
      resources[].assign_to  Node name to assign the resource to
      resources[].property   Property name on the target node

    \b
    NOTES:
      - Script properties with res:// paths are auto-converted to ExtResource refs
      - Property values use Godot syntax: Vector2(x,y), Color(r,g,b,a), etc.
    """
    json_path = Path(json_file)
    if not json_path.exists():
        emit_error(
            GdautoError(
                message=f"File not found: {json_file}",
                code="FILE_NOT_FOUND",
                fix="Check the file path",
            ),
            ctx,
        )
        return

    definition = _load_json(json_path, ctx)
    if definition is None:
        return

    try:
        gd_scene = build_scene(definition)
    except ValidationError as exc:
        emit_error(exc, ctx)
        return

    output_path = _resolve_scene_output(output, json_path)
    serialize_tscn_file(gd_scene, output_path)

    if gd_scene.uid:
        write_uid_file(output_path, gd_scene.uid)

    def _human(data: dict[str, Any], verbose: bool = False) -> None:
        click.echo(f"Created scene: {data['path']} ({data['nodes']} nodes)")

    emit(
        {
            "path": str(output_path),
            "nodes": len(gd_scene.nodes),
            "ext_resources": len(gd_scene.ext_resources),
        },
        _human,
        ctx,
    )


def _load_json(json_path: Path, ctx: click.Context) -> dict[str, Any] | None:
    """Load and parse a JSON file, emitting errors on failure."""
    try:
        text = json_path.read_text(encoding="utf-8")
        return json.loads(text)
    except json.JSONDecodeError as exc:
        emit_error(
            GdautoError(
                message=f"Invalid JSON: {exc}",
                code="INVALID_JSON",
                fix="Validate the JSON file",
            ),
            ctx,
        )
        return None


def _resolve_scene_output(output: str | None, json_path: Path) -> Path:
    """Determine the output .tscn path from CLI options."""
    if output is not None:
        return Path(output)
    if json_path.suffix == ".json":
        return json_path.with_suffix(".tscn")
    return Path(str(json_path) + ".tscn")


# ---------------------------------------------------------------------------
# scene add-node
# ---------------------------------------------------------------------------


@scene.command("add-node")
@click.option(
    "--scene", "scene_path", required=True,
    type=click.Path(exists=True),
    help="Path to the .tscn scene file",
)
@click.option(
    "--name", "node_name", required=True,
    help="Name for the new node",
)
@click.option(
    "--type", "node_type", required=True,
    help="Godot node type (e.g., Sprite2D, Label, Timer, Node2D)",
)
@click.option(
    "--parent", "parent_path", default=None,
    help="Parent node path (default: root node)",
)
@click.option(
    "--property", "properties", multiple=True,
    help="Node properties as 'key=value' (e.g., 'visible=false', 'position=Vector2(10, 20)')",
)
@click.pass_context
def add_node(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    node_type: str,
    parent_path: str | None,
    properties: tuple[str, ...],
) -> None:
    """Add a node to an existing scene file.

    Examples:

      gdauto scene add-node --scene scenes/main.tscn --name Timer --type Timer

      gdauto scene add-node --scene scenes/main.tscn --name Label --type Label --parent HUD --property "text=Score: 0"

      gdauto scene add-node --scene scenes/player.tscn --name Sprite --type Sprite2D --property "position=Vector2(0, -16)"
    """
    try:
        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene_data = parse_tscn(text)

        parent = parent_path or "."

        # Check for duplicate
        for node in scene_data.nodes:
            if node.name == node_name and node.parent == parent:
                raise ProjectError(
                    message=f"Node '{node_name}' already exists at parent '{parent}'",
                    code="NODE_EXISTS",
                    fix="Choose a different name or remove the existing node",
                )

        # Parse properties
        parsed_props: dict[str, Any] = {}
        for prop in properties:
            if "=" not in prop:
                raise ProjectError(
                    message=f"Invalid property format: '{prop}'. Expected 'key=value'",
                    code="INVALID_PROPERTY",
                    fix="Use 'key=value' format, e.g., 'visible=false'",
                )
            key, value_str = prop.split("=", 1)
            parsed_props[key.strip()] = parse_value(value_str.strip())

        scene_data.nodes.append(SceneNode(
            name=node_name,
            type=node_type,
            parent=parent,
            properties=parsed_props,
        ))

        scene_data._raw_header = None
        scene_data._raw_sections = None
        output = serialize_tscn(scene_data)
        path.write_text(output, encoding="utf-8")

        data = {
            "added": True,
            "name": node_name,
            "type": node_type,
            "parent": parent,
            "property_count": len(parsed_props),
            "scene": scene_path,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Added {data['type']} '{data['name']}' to {data['scene']}"
            )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# scene remove-node
# ---------------------------------------------------------------------------


@scene.command("remove-node")
@click.option(
    "--scene", "scene_path", required=True,
    type=click.Path(exists=True),
    help="Path to the .tscn scene file",
)
@click.option(
    "--name", "node_name", required=True,
    help="Name of the node to remove",
)
@click.option(
    "--parent", "parent_path", default=None,
    help="Parent node path to disambiguate (if multiple nodes share the name)",
)
@click.pass_context
def remove_node(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    parent_path: str | None,
) -> None:
    """Remove a node (and its children) from a scene file.

    Examples:

      gdauto scene remove-node --scene scenes/main.tscn --name Timer

      gdauto scene remove-node --scene scenes/main.tscn --name Sprite --parent Player
    """
    try:
        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene_data = parse_tscn(text)

        # Find the node to remove
        target_idx = None
        for i, node in enumerate(scene_data.nodes):
            if node.name == node_name:
                if parent_path is None or node.parent == parent_path:
                    target_idx = i
                    break

        if target_idx is None:
            raise ProjectError(
                message=f"Node '{node_name}' not found in scene",
                code="NODE_NOT_FOUND",
                fix="Check the node name and parent path",
            )

        # Build the path prefix for this node to remove children
        target_node = scene_data.nodes[target_idx]
        if target_node.parent is None:
            # Removing root node
            raise ProjectError(
                message="Cannot remove root node",
                code="CANNOT_REMOVE_ROOT",
                fix="Remove the scene file instead",
            )

        # Build the full path of this node
        if target_node.parent == ".":
            node_full_path = node_name
        else:
            node_full_path = f"{target_node.parent}/{node_name}"

        # Remove this node and all children
        indices_to_remove: set[int] = {target_idx}
        for i, node in enumerate(scene_data.nodes):
            if node.parent == node_full_path or (
                node.parent and node.parent.startswith(node_full_path + "/")
            ):
                indices_to_remove.add(i)

        removed_count = len(indices_to_remove)
        scene_data.nodes = [
            n for i, n in enumerate(scene_data.nodes)
            if i not in indices_to_remove
        ]

        # Also remove connections involving the removed node
        scene_data.connections = [
            c for c in scene_data.connections
            if c.from_node != node_name
            and c.to_node != node_name
            and not c.from_node.startswith(node_full_path)
            and not c.to_node.startswith(node_full_path)
        ]

        scene_data._raw_header = None
        scene_data._raw_sections = None
        output = serialize_tscn(scene_data)
        path.write_text(output, encoding="utf-8")

        data = {
            "removed": True,
            "name": node_name,
            "nodes_removed": removed_count,
            "scene": scene_path,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Removed '{data['name']}' ({data['nodes_removed']} node(s)) from {data['scene']}"
            )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# scene set-property
# ---------------------------------------------------------------------------


@scene.command("set-property")
@click.option(
    "--scene", "scene_path", required=True,
    type=click.Path(exists=True),
    help="Path to the .tscn scene file",
)
@click.option(
    "--node", "node_name", required=True,
    help="Name of the node to modify",
)
@click.option(
    "--parent", "parent_path", default=None,
    help="Parent node path to disambiguate",
)
@click.option(
    "--property", "properties", multiple=True, required=True,
    help="Property as 'key=value' (e.g., 'visible=false', 'position=Vector2(10, 20)')",
)
@click.pass_context
def set_property(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    parent_path: str | None,
    properties: tuple[str, ...],
) -> None:
    """Set properties on an existing node in a scene file.

    Examples:

      gdauto scene set-property --scene scenes/main.tscn --node Player --property "visible=false"

      gdauto scene set-property --scene scenes/main.tscn --node Sprite --parent Player --property "modulate=Color(1, 0, 0, 1)"
    """
    try:
        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene_data = parse_tscn(text)

        target = None
        for node in scene_data.nodes:
            if node.name == node_name:
                if parent_path is None or node.parent == parent_path:
                    target = node
                    break

        if target is None:
            raise ProjectError(
                message=f"Node '{node_name}' not found",
                code="NODE_NOT_FOUND",
                fix="Check the node name and parent path",
            )

        changed: list[str] = []
        for prop in properties:
            if "=" not in prop:
                raise ProjectError(
                    message=f"Invalid property format: '{prop}'",
                    code="INVALID_PROPERTY",
                    fix="Use 'key=value' format",
                )
            key, value_str = prop.split("=", 1)
            key = key.strip()
            target.properties[key] = parse_value(value_str.strip())
            changed.append(key)

        scene_data._raw_header = None
        scene_data._raw_sections = None
        output = serialize_tscn(scene_data)
        path.write_text(output, encoding="utf-8")

        data = {
            "updated": True,
            "node": node_name,
            "properties_changed": changed,
            "count": len(changed),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            props = ", ".join(data["properties_changed"])
            click.echo(f"Set {props} on '{data['node']}'")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# scene add-instance
# ---------------------------------------------------------------------------


@scene.command("add-instance")
@click.option(
    "--scene", "scene_path", required=True,
    type=click.Path(exists=True),
    help="Path to the .tscn scene file to modify",
)
@click.option(
    "--name", "node_name", required=True,
    help="Name for the instanced node",
)
@click.option(
    "--instance", "instance_path", required=True,
    help="res:// path to the scene to instance (e.g., res://scenes/player.tscn)",
)
@click.option(
    "--parent", "parent_path", default=None,
    help="Parent node path (default: root)",
)
@click.option(
    "--property", "properties", multiple=True,
    help="Override properties as 'key=value'",
)
@click.pass_context
def add_instance(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    instance_path: str,
    parent_path: str | None,
    properties: tuple[str, ...],
) -> None:
    """Add a scene instance to an existing scene file.

    Examples:

      gdauto scene add-instance --scene scenes/level.tscn --name Player --instance res://scenes/player.tscn

      gdauto scene add-instance --scene scenes/level.tscn --name Enemy1 --instance res://scenes/enemy.tscn --property "position=Vector2(100, 50)"
    """
    try:
        from gdauto.formats.tscn import ExtResource
        from gdauto.formats.values import ExtResourceRef
        import re

        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene_data = parse_tscn(text)

        parent = parent_path or "."

        for node in scene_data.nodes:
            if node.name == node_name and node.parent == parent:
                raise ProjectError(
                    message=f"Node '{node_name}' already exists",
                    code="NODE_EXISTS",
                    fix="Choose a different name",
                )

        # Add ext_resource for the instanced scene
        existing_ids = {ext.id for ext in scene_data.ext_resources}
        counter = 1
        ext_id = f"{counter}_instance"
        while ext_id in existing_ids:
            counter += 1
            ext_id = f"{counter}_instance"

        scene_data.ext_resources.append(ExtResource(
            type="PackedScene",
            path=instance_path,
            id=ext_id,
            uid=None,
        ))

        # Parse override properties
        parsed_props: dict[str, Any] = {}
        for prop in properties:
            if "=" not in prop:
                raise ProjectError(
                    message=f"Invalid property format: '{prop}'",
                    code="INVALID_PROPERTY",
                    fix="Use 'key=value' format",
                )
            key, value_str = prop.split("=", 1)
            parsed_props[key.strip()] = parse_value(value_str.strip())

        # Instance nodes have no type, they have instance
        scene_data.nodes.append(SceneNode(
            name=node_name,
            type=None,
            parent=parent,
            properties=parsed_props,
            instance=f'ExtResource("{ext_id}")',
        ))

        # Update load_steps
        scene_data.load_steps = len(scene_data.ext_resources) + len(scene_data.sub_resources) + 1

        scene_data._raw_header = None
        scene_data._raw_sections = None
        output = serialize_tscn(scene_data)
        path.write_text(output, encoding="utf-8")

        data = {
            "added": True,
            "name": node_name,
            "instance": instance_path,
            "parent": parent,
            "overrides": len(parsed_props),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Added instance '{data['name']}' of {data['instance']}"
            )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)
