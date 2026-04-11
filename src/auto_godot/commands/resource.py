"""Inspect and manipulate Godot resources (.tres, .tscn)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import rich_click as click
from rich.console import Console
from rich.tree import Tree

from auto_godot.errors import AutoGodotError, ProjectError, ResourceNotFoundError
from auto_godot.formats.tres import GdResource, parse_tres_file, serialize_tres_file
from auto_godot.formats.tscn import GdScene, parse_tscn_file
from auto_godot.formats.values import Color, GodotJSONEncoder
from auto_godot.output import GlobalConfig, emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def resource(ctx: click.Context) -> None:
    """Inspect and manipulate Godot resources (.tres, .tscn)."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _build_tres_data(file_path: Path, res: GdResource) -> dict[str, Any]:
    """Build metadata wrapper dict for a .tres resource."""
    return {
        "file": str(file_path.resolve()),
        "format": res.format,
        "type": res.type,
        "uid": res.uid,
        "warnings": [],
        "resource": res.to_dict(),
    }


def _build_tscn_data(file_path: Path, scene: GdScene) -> dict[str, Any]:
    """Build metadata wrapper dict for a .tscn scene."""
    return {
        "file": str(file_path.resolve()),
        "format": scene.format,
        "type": "Scene",
        "uid": scene.uid,
        "warnings": [],
        "resource": scene.to_dict(),
    }


def _display_tres_human(data: dict[str, Any], verbose: bool = False) -> None:
    """Display .tres resource in human-readable tree format."""
    console = Console()
    tree = Tree(f"[bold]{data['file']}[/bold] ({data['type']})")

    res = data["resource"]

    # ext_resources branch
    if res.get("ext_resources"):
        ext_branch = tree.add("[bold]ext_resources[/bold]")
        for ext in res["ext_resources"]:
            ext_branch.add(f"{ext['id']}: {ext['type']} ({ext['path']})")

    # sub_resources branch
    if res.get("sub_resources"):
        sub_branch = tree.add("[bold]sub_resources[/bold]")
        for sub in res["sub_resources"]:
            node = sub_branch.add(f"{sub['id']}: {sub['type']}")
            if verbose:
                for k, v in sub.get("properties", {}).items():
                    node.add(f"{k} = {v}")

    # resource properties
    if res.get("properties"):
        prop_branch = tree.add("[bold]properties[/bold]")
        for k, v in res["properties"].items():
            val_str = str(v)
            if not verbose and len(val_str) > 80:
                val_str = val_str[:77] + "..."
            prop_branch.add(f"{k} = {val_str}")

    console.print(tree)


def _display_tscn_human(data: dict[str, Any], verbose: bool = False) -> None:
    """Display .tscn scene in human-readable tree format."""
    console = Console()
    tree = Tree(f"[bold]{data['file']}[/bold] (Scene)")

    res = data["resource"]

    # ext_resources branch
    if res.get("ext_resources"):
        ext_branch = tree.add("[bold]ext_resources[/bold]")
        for ext in res["ext_resources"]:
            ext_branch.add(f"{ext['id']}: {ext['type']} ({ext['path']})")

    # nodes branch
    if res.get("nodes"):
        nodes_branch = tree.add("[bold]nodes[/bold]")
        for node in res["nodes"]:
            label = node["name"]
            if node.get("type"):
                label += f" ({node['type']})"
            if node.get("parent"):
                label += f" [dim]parent={node['parent']}[/dim]"
            n = nodes_branch.add(label)
            if verbose:
                for k, v in node.get("properties", {}).items():
                    n.add(f"{k} = {v}")

    # connections branch
    if res.get("connections"):
        conn_branch = tree.add("[bold]connections[/bold]")
        for conn in res["connections"]:
            conn_branch.add(
                f"{conn['signal']}: {conn['from']} -> {conn['to']}.{conn['method']}"
            )

    console.print(tree)


@resource.command()
@click.argument("file", type=click.Path())
@click.pass_context
def inspect(ctx: click.Context, file: str) -> None:
    """Inspect a Godot resource (.tres) or scene (.tscn) file."""
    config: GlobalConfig = ctx.obj

    file_path = Path(file)

    # Check file exists
    if not file_path.exists():
        err = ResourceNotFoundError(
            message=f"File not found: {file}",
            code="FILE_NOT_FOUND",
            fix="Check the file path and ensure the file exists",
        )
        emit_error(err, ctx)
        return

    # Check extension
    suffix = file_path.suffix.lower()
    if suffix not in (".tres", ".tscn"):
        err = AutoGodotError(
            message=f"Unsupported file format: {suffix}",
            code="UNSUPPORTED_FORMAT",
            fix="resource inspect supports .tres and .tscn files",
        )
        emit_error(err, ctx)
        return

    try:
        if suffix == ".tres":
            _inspect_tres(ctx, file_path, config)
        else:
            _inspect_tscn(ctx, file_path, config)
    except Exception as exc:
        err = AutoGodotError(
            message=f"Failed to parse {file}: {exc}",
            code="PARSE_ERROR",
            fix="Ensure the file is a valid Godot resource or scene file",
        )
        emit_error(err, ctx)


def _inspect_tres(
    ctx: click.Context, file_path: Path, config: GlobalConfig
) -> None:
    """Parse and output a .tres file."""
    res = parse_tres_file(file_path)
    data = _build_tres_data(file_path, res)

    if config.json_mode:
        sys.stdout.write(
            json.dumps(data, cls=GodotJSONEncoder, indent=2) + "\n"
        )
    elif not config.quiet:
        _display_tres_human(data, verbose=config.verbose)


def _inspect_tscn(
    ctx: click.Context, file_path: Path, config: GlobalConfig
) -> None:
    """Parse and output a .tscn file."""
    scene = parse_tscn_file(file_path)
    data = _build_tscn_data(file_path, scene)

    if config.json_mode:
        sys.stdout.write(
            json.dumps(data, cls=GodotJSONEncoder, indent=2) + "\n"
        )
    elif not config.quiet:
        _display_tscn_human(data, verbose=config.verbose)


# ---------------------------------------------------------------------------
# resource create-gradient
# ---------------------------------------------------------------------------


def _parse_gradient_color(s: str) -> tuple[float, Color]:
    """Parse 'offset:color' string (e.g., '0:#ff0000' or '0.5:white')."""
    from auto_godot.commands.theme import _parse_color
    if ":" not in s:
        raise ProjectError(
            message=f"Invalid gradient stop: '{s}'. Expected 'offset:color'",
            code="INVALID_GRADIENT_STOP",
            fix="Use format 'offset:color', e.g., '0:#ff0000' or '0.5:white'",
        )
    offset_str, color_str = s.split(":", 1)
    offset = float(offset_str)
    color = _parse_color(color_str)
    return offset, color


class _RawGodotStr:
    """Raw Godot value for serialize_value fallback."""

    def __init__(self, raw: str) -> None:
        self._raw = raw

    def __str__(self) -> str:
        return self._raw

    def __repr__(self) -> str:
        return self._raw


@resource.command("create-gradient")
@click.option(
    "--stop", "stops", multiple=True, required=True,
    help="Gradient stops as 'offset:color' (e.g., '0:#000000', '1:#ffffff', '0.5:red')",
)
@click.argument("output_path", type=click.Path())
@click.pass_context
def create_gradient(
    ctx: click.Context,
    stops: tuple[str, ...],
    output_path: str,
) -> None:
    """Create a Gradient .tres resource.

    Examples:

      auto-godot resource create-gradient --stop "0:black" --stop "1:white" gradients/fade.tres

      auto-godot resource create-gradient --stop "0:#ff0000" --stop "0.5:#ffff00" --stop "1:#00ff00" gradients/health.tres
    """
    try:
        parsed = [_parse_gradient_color(s) for s in stops]
        parsed.sort(key=lambda x: x[0])

        offsets = _RawGodotStr(
            "PackedFloat32Array(" + ", ".join(str(o) for o, _ in parsed) + ")"
        )
        colors = _RawGodotStr(
            "PackedColorArray(" + ", ".join(
                f"{c.r}, {c.g}, {c.b}, {c.a}" for _, c in parsed
            ) + ")"
        )

        resource_obj = GdResource(
            type="Gradient",
            format=3,
            uid=None,
            load_steps=None,
            ext_resources=[],
            sub_resources=[],
            resource_properties={
                "offsets": offsets,
                "colors": colors,
            },
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        serialize_tres_file(resource_obj, out)

        data = {
            "created": True,
            "path": str(out),
            "stop_count": len(parsed),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Created gradient at {data['path']} ({data['stop_count']} stops)")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# resource create-curve
# ---------------------------------------------------------------------------


@resource.command("create-curve")
@click.option(
    "--point", "points", multiple=True, required=True,
    help="Curve points as 'x,y' (e.g., '0,0', '0.5,1', '1,0')",
)
@click.argument("output_path", type=click.Path())
@click.pass_context
def create_curve(
    ctx: click.Context,
    points: tuple[str, ...],
    output_path: str,
) -> None:
    """Create a Curve .tres resource for gameplay values.

    Examples:

      auto-godot resource create-curve --point "0,0" --point "0.5,1" --point "1,0" curves/damage_falloff.tres

      auto-godot resource create-curve --point "0,0" --point "1,1" curves/linear.tres
    """
    try:
        parsed_points: list[tuple[float, float]] = []
        for p in points:
            parts = p.split(",")
            if len(parts) != 2:
                raise ProjectError(
                    message=f"Invalid curve point: '{p}'. Expected 'x,y'",
                    code="INVALID_CURVE_POINT",
                    fix="Use format 'x,y', e.g., '0.5,1.0'",
                )
            parsed_points.append((float(parts[0]), float(parts[1])))

        # Build the _data PackedFloat32Array
        # Godot Curve _data format: [x, y, left_tangent, left_mode, right_tangent, right_mode, ...]
        data_values: list[float] = []
        for x, y in parsed_points:
            data_values.extend([x, y, 0.0, 0.0, 0.0, 0.0])

        curve_data = _RawGodotStr(
            "PackedFloat32Array(" + ", ".join(str(v) for v in data_values) + ")"
        )

        resource_obj = GdResource(
            type="Curve",
            format=3,
            uid=None,
            load_steps=None,
            ext_resources=[],
            sub_resources=[],
            resource_properties={
                "min_value": 0.0,
                "max_value": 1.0,
                "point_count": len(parsed_points),
                "_data": curve_data,
            },
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        serialize_tres_file(resource_obj, out)

        data = {
            "created": True,
            "path": str(out),
            "point_count": len(parsed_points),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Created curve at {data['path']} ({data['point_count']} points)")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# resource list
# ---------------------------------------------------------------------------


@resource.command("list")
@click.option("--scene", "scene_path", required=True, type=click.Path(exists=True),
              help="Path to a .tscn or .tres file")
@click.pass_context
def list_resources(ctx: click.Context, scene_path: str) -> None:
    """List external resources referenced by a scene or resource file.

    Examples:

      auto-godot resource list --scene scenes/main.tscn
    """
    try:
        file_path = Path(scene_path)
        suffix = file_path.suffix.lower()

        if suffix == ".tscn":
            scene_data = parse_tscn_file(file_path)
            resources = [
                {"id": ext.id, "type": ext.type, "path": ext.path, "uid": ext.uid}
                for ext in scene_data.ext_resources
            ]
        elif suffix == ".tres":
            res_data = parse_tres_file(file_path)
            resources = [
                {"id": ext.id, "type": ext.type, "path": ext.path, "uid": ext.uid}
                for ext in res_data.ext_resources
            ]
        else:
            raise ProjectError(
                message=f"Unsupported file type: {suffix}",
                code="INVALID_FILE_TYPE",
                fix="Provide a .tscn or .tres file",
            )

        data = {"resources": resources, "count": len(resources), "file": scene_path}

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Resources in {data['file']} ({data['count']}):")
            for res in data["resources"]:
                uid_str = f" uid={res['uid']}" if res.get("uid") else ""
                click.echo(f"  [{res['id']}] {res['type']}: {res['path']}{uid_str}")
            if not data["resources"]:
                click.echo("  (none)")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)
    except Exception as exc:
        emit_error(
            ProjectError(
                message=f"Failed to parse file: {exc}",
                code="PARSE_ERROR",
                fix="Ensure the file is a valid .tscn or .tres file",
            ),
            ctx,
        )


# ---------------------------------------------------------------------------
# resource dump
# ---------------------------------------------------------------------------

_TSCN_SECTIONS = ("ext_resources", "sub_resources", "nodes", "connections")
_TRES_SECTIONS = ("ext_resources", "sub_resources", "properties")


@resource.command("dump")
@click.argument("file", type=click.Path())
@click.option(
    "--section",
    type=str,
    default=None,
    help="Dump only a specific section (nodes, ext_resources, sub_resources, properties, connections).",
)
@click.pass_context
def dump(ctx: click.Context, file: str, section: str | None) -> None:
    """Dump parsed structure of a .tscn/.tres file as JSON.

    Always outputs JSON regardless of --json flag. Use --section to
    filter to a specific part of the parsed file.

    Examples:

      auto-godot resource dump scene.tscn

      auto-godot resource dump scene.tscn --section nodes

      auto-godot resource dump spriteframes.tres --section properties
    """
    file_path = Path(file)

    if not file_path.exists():
        emit_error(
            ProjectError(
                message=f"File not found: {file}",
                code="FILE_NOT_FOUND",
                fix="Check the file path exists",
            ),
            ctx,
        )
        return

    suffix = file_path.suffix.lower()

    if suffix not in (".tres", ".tscn"):
        emit_error(
            ProjectError(
                message=f"Unsupported file format: {suffix}",
                code="UNSUPPORTED_FORMAT",
                fix="resource dump supports .tres and .tscn files",
            ),
            ctx,
        )
        return

    valid_sections = _TSCN_SECTIONS if suffix == ".tscn" else _TRES_SECTIONS
    if section is not None and section not in valid_sections:
        emit_error(
            ProjectError(
                message=f"Invalid section '{section}' for {suffix} file",
                code="INVALID_SECTION",
                fix=f"Valid sections: {', '.join(valid_sections)}",
            ),
            ctx,
        )
        return

    try:
        if suffix == ".tscn":
            parsed = parse_tscn_file(file_path).to_dict()
        else:
            parsed = parse_tres_file(file_path).to_dict()

        output = parsed[section] if section else parsed
        sys.stdout.write(json.dumps(output, cls=GodotJSONEncoder, indent=2) + "\n")
    except Exception as exc:
        emit_error(
            ProjectError(
                message=f"Failed to parse {file}: {exc}",
                code="PARSE_ERROR",
                fix="Ensure the file is a valid Godot resource or scene file",
            ),
            ctx,
        )
