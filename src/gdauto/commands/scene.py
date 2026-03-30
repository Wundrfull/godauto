"""Scene file operations: list and create commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import rich_click as click
from rich.console import Console
from rich.tree import Tree

from gdauto.errors import GdautoError, ProjectError, ValidationError
from gdauto.formats.tscn import serialize_tscn_file
from gdauto.formats.uid import write_uid_file
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
