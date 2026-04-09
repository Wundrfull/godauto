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


def _find_node(
    scene_data: Any, node_name: str, parent_path: str | None
) -> SceneNode | None:
    """Find a node by name and optional parent path."""
    from gdauto.formats.tscn import GdScene

    for node in scene_data.nodes:
        if node.name == node_name:
            if parent_path is None:
                return node
            if node.parent == parent_path:
                return node
    return None


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
# scene add-timer
# ---------------------------------------------------------------------------


@scene.command("add-timer")
@click.option(
    "--scene", "scene_path", required=True,
    type=click.Path(exists=True),
    help="Path to the .tscn scene file",
)
@click.option("--name", "node_name", required=True, help="Timer node name")
@click.option("--wait", "wait_time", required=True, type=float, help="Wait time in seconds")
@click.option("--one-shot/--repeating", default=False, help="One-shot or repeating (default: repeating)")
@click.option("--autostart/--no-autostart", default=False, help="Start automatically")
@click.option("--parent", "parent_path", default=None, help="Parent node path")
@click.option("--connect", "connect_method", default=None, help="Auto-connect timeout signal to this method on parent")
@click.pass_context
def add_timer(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    wait_time: float,
    one_shot: bool,
    autostart: bool,
    parent_path: str | None,
    connect_method: str | None,
) -> None:
    """Add a Timer node with common settings to a scene.

    Examples:

      gdauto scene add-timer --scene scenes/main.tscn --name SpawnTimer --wait 2.0 --repeating --autostart --connect _on_spawn_timer_timeout

      gdauto scene add-timer --scene scenes/player.tscn --name CooldownTimer --wait 0.5 --one-shot --parent Player
    """
    try:
        from gdauto.formats.tscn import Connection

        path_obj = Path(scene_path)
        text = path_obj.read_text(encoding="utf-8")
        scene_data = parse_tscn(text)

        parent = parent_path or "."

        for node in scene_data.nodes:
            if node.name == node_name and node.parent == parent:
                raise ProjectError(
                    message=f"Node '{node_name}' already exists",
                    code="NODE_EXISTS",
                    fix="Choose a different name",
                )

        props: dict[str, Any] = {"wait_time": wait_time}
        if one_shot:
            props["one_shot"] = True
        if autostart:
            props["autostart"] = True

        scene_data.nodes.append(SceneNode(
            name=node_name,
            type="Timer",
            parent=parent,
            properties=props,
        ))

        if connect_method:
            to_node = "." if parent == "." else parent
            scene_data.connections.append(Connection(
                signal="timeout",
                from_node=node_name,
                to_node=to_node,
                method=connect_method,
            ))

        scene_data._raw_header = None
        scene_data._raw_sections = None
        output = serialize_tscn(scene_data)
        path_obj.write_text(output, encoding="utf-8")

        data = {
            "added": True,
            "name": node_name,
            "wait_time": wait_time,
            "one_shot": one_shot,
            "autostart": autostart,
            "connected": connect_method,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            mode = "one-shot" if data["one_shot"] else "repeating"
            auto = ", autostart" if data["autostart"] else ""
            conn = f", connected to {data['connected']}" if data["connected"] else ""
            click.echo(f"Added Timer '{data['name']}' ({data['wait_time']}s, {mode}{auto}{conn})")

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


# ---------------------------------------------------------------------------
# scene add-group
# ---------------------------------------------------------------------------


@scene.command("add-group")
@click.option(
    "--scene", "scene_path", required=True,
    type=click.Path(exists=True),
    help="Path to the .tscn scene file",
)
@click.option(
    "--node", "node_name", required=True,
    help="Name of the node to add to a group",
)
@click.option(
    "--group", "groups", multiple=True, required=True,
    help="Group name(s) to add (e.g., 'enemies', 'destructible')",
)
@click.option(
    "--parent", "parent_path", default=None,
    help="Parent node path to disambiguate",
)
@click.pass_context
def add_group(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    groups: tuple[str, ...],
    parent_path: str | None,
) -> None:
    """Add a node to one or more groups in a scene file.

    Examples:

      gdauto scene add-group --scene scenes/enemy.tscn --node Enemy --group enemies --group damageable

      gdauto scene add-group --scene scenes/coin.tscn --node Coin --group collectibles
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

        if target.groups is None:
            target.groups = []

        added: list[str] = []
        for group in groups:
            if group not in target.groups:
                target.groups.append(group)
                added.append(group)

        scene_data._raw_header = None
        scene_data._raw_sections = None
        output = serialize_tscn(scene_data)
        path.write_text(output, encoding="utf-8")

        data = {
            "updated": True,
            "node": node_name,
            "groups_added": added,
            "total_groups": target.groups,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            groups_str = ", ".join(data["groups_added"])
            click.echo(f"Added '{data['node']}' to groups: {groups_str}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# scene add-camera
# ---------------------------------------------------------------------------


@scene.command("add-camera")
@click.option("--scene", "scene_path", required=True, type=click.Path(exists=True), help="Scene file")
@click.option("--name", "node_name", default="Camera2D", help="Camera node name")
@click.option("--zoom", default=1.0, type=float, help="Zoom level (1.0 = default, 2.0 = 2x)")
@click.option("--smoothing/--no-smoothing", default=True, help="Position smoothing (default: on)")
@click.option("--smoothing-speed", default=5.0, type=float, help="Smoothing speed (default: 5.0)")
@click.option("--limit-left", type=int, default=None, help="Left camera limit in pixels")
@click.option("--limit-top", type=int, default=None, help="Top camera limit in pixels")
@click.option("--limit-right", type=int, default=None, help="Right camera limit in pixels")
@click.option("--limit-bottom", type=int, default=None, help="Bottom camera limit in pixels")
@click.option("--current/--no-current", default=True, help="Set as current camera (default: yes)")
@click.option("--parent", "parent_path", default=None, help="Parent node path")
@click.pass_context
def add_camera(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    zoom: float,
    smoothing: bool,
    smoothing_speed: float,
    limit_left: int | None,
    limit_top: int | None,
    limit_right: int | None,
    limit_bottom: int | None,
    current: bool,
    parent_path: str | None,
) -> None:
    """Add a Camera2D node with common settings to a scene.

    Examples:

      gdauto scene add-camera --scene scenes/level.tscn --zoom 2 --smoothing --parent Player

      gdauto scene add-camera --scene scenes/main.tscn --limit-left 0 --limit-top 0 --limit-right 1920 --limit-bottom 1080
    """
    try:
        from gdauto.formats.values import Vector2 as Vec2

        path_obj = Path(scene_path)
        text = path_obj.read_text(encoding="utf-8")
        scene_data = parse_tscn(text)
        parent = parent_path or "."

        for node in scene_data.nodes:
            if node.name == node_name and node.parent == parent:
                raise ProjectError(
                    message=f"Node '{node_name}' already exists",
                    code="NODE_EXISTS",
                    fix="Choose a different name",
                )

        props: dict[str, Any] = {}
        if current:
            props["enabled"] = True
        if zoom != 1.0:
            props["zoom"] = Vec2(zoom, zoom)
        if smoothing:
            props["position_smoothing_enabled"] = True
            props["position_smoothing_speed"] = smoothing_speed
        if limit_left is not None:
            props["limit_left"] = limit_left
        if limit_top is not None:
            props["limit_top"] = limit_top
        if limit_right is not None:
            props["limit_right"] = limit_right
        if limit_bottom is not None:
            props["limit_bottom"] = limit_bottom

        scene_data.nodes.append(SceneNode(
            name=node_name,
            type="Camera2D",
            parent=parent,
            properties=props,
        ))

        scene_data._raw_header = None
        scene_data._raw_sections = None
        output = serialize_tscn(scene_data)
        path_obj.write_text(output, encoding="utf-8")

        data = {
            "added": True,
            "name": node_name,
            "zoom": zoom,
            "smoothing": smoothing,
            "current": current,
            "has_limits": any(v is not None for v in [limit_left, limit_top, limit_right, limit_bottom]),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            parts = [f"Camera2D '{data['name']}'"]
            if data["zoom"] != 1.0:
                parts.append(f"zoom={data['zoom']}x")
            if data["smoothing"]:
                parts.append("smoothing")
            if data["has_limits"]:
                parts.append("with limits")
            click.echo("Added " + ", ".join(parts))

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# scene duplicate-node
# ---------------------------------------------------------------------------


@scene.command("duplicate-node")
@click.option("--scene", "scene_path", required=True, type=click.Path(exists=True), help="Scene file")
@click.option("--node", "node_name", required=True, help="Name of the node to duplicate")
@click.option("--new-name", required=True, help="Name for the duplicated node")
@click.option("--parent", "parent_path", default=None, help="Parent path to disambiguate source")
@click.option("--property", "properties", multiple=True, help="Override properties on the copy as 'key=value'")
@click.pass_context
def duplicate_node(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    new_name: str,
    parent_path: str | None,
    properties: tuple[str, ...],
) -> None:
    """Duplicate an existing node in a scene with a new name.

    Examples:

      gdauto scene duplicate-node --scene scenes/level.tscn --node Enemy --new-name Enemy2 --property "position=Vector2(200, 50)"

      gdauto scene duplicate-node --scene scenes/main.tscn --node Coin --new-name Coin2
    """
    try:
        path_obj = Path(scene_path)
        text = path_obj.read_text(encoding="utf-8")
        scene_data = parse_tscn(text)

        # Find source node
        source = None
        for node in scene_data.nodes:
            if node.name == node_name:
                if parent_path is None or node.parent == parent_path:
                    source = node
                    break

        if source is None:
            raise ProjectError(
                message=f"Node '{node_name}' not found",
                code="NODE_NOT_FOUND",
                fix="Check the node name",
            )

        # Check new name doesn't exist at same parent
        for node in scene_data.nodes:
            if node.name == new_name and node.parent == source.parent:
                raise ProjectError(
                    message=f"Node '{new_name}' already exists at same parent",
                    code="NODE_EXISTS",
                    fix="Choose a different name",
                )

        # Clone properties
        new_props = dict(source.properties)

        # Apply overrides
        for prop in properties:
            if "=" not in prop:
                raise ProjectError(
                    message=f"Invalid property format: '{prop}'",
                    code="INVALID_PROPERTY",
                    fix="Use 'key=value' format",
                )
            key, value_str = prop.split("=", 1)
            new_props[key.strip()] = parse_value(value_str.strip())

        scene_data.nodes.append(SceneNode(
            name=new_name,
            type=source.type,
            parent=source.parent,
            properties=new_props,
            instance=source.instance,
            groups=list(source.groups) if source.groups else None,
        ))

        scene_data._raw_header = None
        scene_data._raw_sections = None
        output = serialize_tscn(scene_data)
        path_obj.write_text(output, encoding="utf-8")

        data = {
            "duplicated": True,
            "source": node_name,
            "new_name": new_name,
            "overrides": len(properties),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Duplicated '{data['source']}' as '{data['new_name']}'")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# scene list-nodes
# ---------------------------------------------------------------------------


@scene.command("list-nodes")
@click.argument("scene_path", type=click.Path(exists=True))
@click.pass_context
def list_nodes(ctx: click.Context, scene_path: str) -> None:
    """List all nodes in a scene file with their types and parents.

    Examples:

      gdauto scene list-nodes scenes/main.tscn
    """
    try:
        text = Path(scene_path).read_text(encoding="utf-8")
        scene_data = parse_tscn(text)

        nodes_info: list[dict[str, Any]] = []
        for node in scene_data.nodes:
            info: dict[str, Any] = {
                "name": node.name,
                "type": node.type,
                "parent": node.parent,
            }
            if node.groups:
                info["groups"] = node.groups
            if node.instance:
                info["instance"] = node.instance
            prop_count = len(node.properties)
            if prop_count > 0:
                info["property_count"] = prop_count
            nodes_info.append(info)

        data = {
            "nodes": nodes_info,
            "count": len(nodes_info),
            "scene": scene_path,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Nodes in {data['scene']} ({data['count']}):")
            for node in data["nodes"]:
                type_str = f" [{node['type']}]" if node.get("type") else " [instance]"
                parent_str = f" parent={node['parent']}" if node["parent"] else ""
                groups_str = f" groups={node['groups']}" if node.get("groups") else ""
                click.echo(f"  {node['name']}{type_str}{parent_str}{groups_str}")

        emit(data, _human, ctx)
    except Exception as exc:
        emit_error(
            ProjectError(
                message=f"Failed to parse scene: {exc}",
                code="PARSE_ERROR",
                fix="Ensure the file is a valid .tscn scene file",
            ),
            ctx,
        )


# ---------------------------------------------------------------------------
# scene rename-node
# ---------------------------------------------------------------------------


@scene.command("rename-node")
@click.option("--scene", "scene_path", required=True, type=click.Path(exists=True),
              help="Path to the .tscn scene file")
@click.option("--node", "node_name", required=True, help="Current name of the node")
@click.option("--parent", "parent_path", default=None, help="Parent node path to disambiguate")
@click.option("--new-name", required=True, help="New name for the node")
@click.pass_context
def rename_node(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    parent_path: str | None,
    new_name: str,
) -> None:
    """Rename a node in a scene file.

    Updates the node name and all parent references from other nodes
    that reference the renamed node.

    Examples:

      gdauto scene rename-node --scene scenes/main.tscn --node Timer --new-name SpawnTimer

      gdauto scene rename-node --scene scenes/main.tscn --node Label --parent HUD --new-name ScoreLabel
    """
    try:
        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene_data = parse_tscn(text)

        target = _find_node(scene_data, node_name, parent_path)
        if target is None:
            raise ProjectError(
                message=f"Node '{node_name}' not found in scene",
                code="NODE_NOT_FOUND",
                fix="Check the node name and parent path",
            )

        old_name = target.name
        # Build the old path for parent reference updates
        if target.parent is None or target.parent == ".":
            old_path = old_name
        else:
            old_path = f"{target.parent}/{old_name}" if target.parent != "." else old_name

        new_path = f"{target.parent}/{new_name}" if target.parent and target.parent != "." else new_name

        # Rename the node
        target.name = new_name

        # Update parent references in child nodes
        for node in scene_data.nodes:
            if node.parent == old_path:
                node.parent = new_path
            elif node.parent and node.parent.startswith(old_path + "/"):
                node.parent = new_path + node.parent[len(old_path):]

        # Update connection references
        for conn in scene_data.connections:
            if conn.from_node == old_name:
                conn.from_node = new_name
            if conn.to_node == old_name:
                conn.to_node = new_name

        scene_data._raw_header = None
        scene_data._raw_sections = None
        path.write_text(serialize_tscn(scene_data), encoding="utf-8")

        data = {"renamed": True, "old_name": old_name, "new_name": new_name, "scene": scene_path}

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Renamed '{data['old_name']}' -> '{data['new_name']}' in {data['scene']}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# scene reorder-node
# ---------------------------------------------------------------------------


@scene.command("reorder-node")
@click.option("--scene", "scene_path", required=True, type=click.Path(exists=True),
              help="Path to the .tscn scene file")
@click.option("--node", "node_name", required=True, help="Name of the node to move")
@click.option("--parent", "parent_path", default=None, help="Parent node path to disambiguate")
@click.option("--index", "target_index", required=True, type=int,
              help="Target child index (0-based)")
@click.pass_context
def reorder_node(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    parent_path: str | None,
    target_index: int,
) -> None:
    """Reorder a node among its siblings in a scene file.

    Moves the node to the specified child index within its parent.

    Examples:

      gdauto scene reorder-node --scene scenes/main.tscn --node ScoreLabel --parent HUD --index 0
    """
    try:
        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene_data = parse_tscn(text)

        target = _find_node(scene_data, node_name, parent_path)
        if target is None:
            raise ProjectError(
                message=f"Node '{node_name}' not found in scene",
                code="NODE_NOT_FOUND",
                fix="Check the node name and parent path",
            )

        # Find the parent path for sibling lookup
        node_parent = target.parent

        # Gather siblings (nodes with the same parent), preserving order
        siblings = [n for n in scene_data.nodes if n.parent == node_parent]

        if target not in siblings:
            raise ProjectError(
                message=f"Node '{node_name}' not found among siblings",
                code="NODE_NOT_FOUND",
                fix="Check the node name and parent path",
            )

        # Remove target from current position
        scene_data.nodes.remove(target)

        # Find where siblings start in the main node list
        remaining_siblings = [n for n in scene_data.nodes if n.parent == node_parent]

        if target_index <= 0 or not remaining_siblings:
            # Insert before first sibling
            if remaining_siblings:
                insert_pos = scene_data.nodes.index(remaining_siblings[0])
            else:
                insert_pos = len(scene_data.nodes)
        elif target_index >= len(remaining_siblings):
            # Insert after last sibling
            insert_pos = scene_data.nodes.index(remaining_siblings[-1]) + 1
        else:
            insert_pos = scene_data.nodes.index(remaining_siblings[target_index])

        scene_data.nodes.insert(insert_pos, target)

        scene_data._raw_header = None
        scene_data._raw_sections = None
        path.write_text(serialize_tscn(scene_data), encoding="utf-8")

        data = {"reordered": True, "name": node_name, "index": target_index, "scene": scene_path}

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Moved '{data['name']}' to index {data['index']} in {data['scene']}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# scene set-resource
# ---------------------------------------------------------------------------


@scene.command("set-resource")
@click.option("--scene", "scene_path", required=True, type=click.Path(exists=True),
              help="Path to the .tscn scene file")
@click.option("--node", "node_name", required=True, help="Name of the node to modify")
@click.option("--parent", "parent_path", default=None, help="Parent node path to disambiguate")
@click.option("--property", "prop_name", required=True,
              help="Property name to set (e.g., theme, material, texture)")
@click.option("--resource", required=True,
              help="res:// path to the resource (e.g., res://theme/game_theme.tres)")
@click.option("--type", "res_type", required=True,
              help="Resource type (e.g., Theme, ShaderMaterial, Texture2D)")
@click.pass_context
def set_resource(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    parent_path: str | None,
    prop_name: str,
    resource: str,
    res_type: str,
) -> None:
    """Assign an external resource to a node property.

    Creates (or reuses) an ext_resource entry and sets the property
    on the target node to reference it.

    Examples:

      gdauto scene set-resource --scene scenes/main.tscn --node Main --property theme --resource res://theme/game_theme.tres --type Theme

      gdauto scene set-resource --scene scenes/player.tscn --node Sprite --property material --resource res://shaders/flash_material.tres --type ShaderMaterial
    """
    from gdauto.formats.tres import ExtResource

    try:
        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene_data = parse_tscn(text)

        target = _find_node(scene_data, node_name, parent_path)
        if target is None:
            raise ProjectError(
                message=f"Node '{node_name}' not found in scene",
                code="NODE_NOT_FOUND",
                fix="Check the node name and parent path",
            )

        # Check if an ext_resource with this path already exists
        existing_ext = None
        for ext in scene_data.ext_resources:
            if ext.path == resource:
                existing_ext = ext
                break

        if existing_ext is None:
            # Allocate a new ext_resource ID
            used_ids = {int(ext.id) for ext in scene_data.ext_resources if ext.id.isdigit()}
            new_id = str(max(used_ids, default=0) + 1)
            new_ext = ExtResource(
                type=res_type,
                path=resource,
                id=new_id,
            )
            scene_data.ext_resources.append(new_ext)
            ext_id = new_id
        else:
            ext_id = existing_ext.id

        # Set the property to reference the ext_resource
        target.properties[prop_name] = f'ExtResource("{ext_id}")'

        # Update load_steps
        scene_data.load_steps = len(scene_data.ext_resources) + len(scene_data.sub_resources) + 1

        scene_data._raw_header = None
        scene_data._raw_sections = None
        path.write_text(serialize_tscn(scene_data), encoding="utf-8")

        data = {
            "set": True,
            "node": node_name,
            "property": prop_name,
            "resource": resource,
            "type": res_type,
            "scene": scene_path,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Set {data['node']}.{data['property']} = {data['resource']} ({data['type']})"
            )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)
