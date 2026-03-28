"""Inspect and manipulate Godot resources (.tres, .tscn)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import rich_click as click
from rich.console import Console
from rich.tree import Tree

from gdauto.errors import GdautoError, ResourceNotFoundError
from gdauto.formats.tres import GdResource, parse_tres_file
from gdauto.formats.tscn import GdScene, parse_tscn_file
from gdauto.formats.values import GodotJSONEncoder
from gdauto.output import GlobalConfig, emit_error


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
        err = GdautoError(
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
        err = GdautoError(
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
