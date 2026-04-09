"""Manage signal connections in Godot scene files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rich_click as click

from gdauto.errors import ProjectError
from gdauto.formats.tscn import (
    Connection,
    parse_tscn,
    serialize_tscn,
)
from gdauto.output import emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def signal(ctx: click.Context) -> None:
    """Manage signal connections in scene files."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@signal.command("connect")
@click.option(
    "--scene", "scene_path", required=True,
    type=click.Path(exists=True),
    help="Path to the .tscn scene file",
)
@click.option(
    "--signal", "signal_name", required=True,
    help="Signal name (e.g., pressed, body_entered, timeout)",
)
@click.option(
    "--from", "from_node", required=True,
    help="Source node path (e.g., Button, Timer, Area2D/CollisionShape2D)",
)
@click.option(
    "--to", "to_node", required=True,
    help="Target node path (e.g., ., Parent/Child)",
)
@click.option(
    "--method", required=True,
    help="Target method name (e.g., _on_button_pressed)",
)
@click.option(
    "--flags", default=0, type=int,
    help="Connection flags (default: 0). 1=deferred, 2=persist, 4=one_shot",
)
@click.pass_context
def connect_signal(
    ctx: click.Context,
    scene_path: str,
    signal_name: str,
    from_node: str,
    to_node: str,
    method: str,
    flags: int,
) -> None:
    """Connect a signal between nodes in a scene file.

    Examples:

      gdauto signal connect --scene scenes/main.tscn --signal pressed --from Button --to . --method _on_button_pressed

      gdauto signal connect --scene scenes/game.tscn --signal timeout --from Timer --to . --method _on_timer_timeout

      gdauto signal connect --scene scenes/player.tscn --signal body_entered --from Area2D --to . --method _on_area_body_entered --flags 4
    """
    try:
        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene = parse_tscn(text)

        # Check for duplicate connections
        for conn in scene.connections:
            if (conn.signal == signal_name
                    and conn.from_node == from_node
                    and conn.to_node == to_node
                    and conn.method == method):
                raise ProjectError(
                    message=(
                        f"Connection already exists: {from_node}.{signal_name} "
                        f"-> {to_node}.{method}"
                    ),
                    code="CONNECTION_EXISTS",
                    fix="Remove the existing connection or use a different method name",
                )

        # Add connection
        scene.connections.append(Connection(
            signal=signal_name,
            from_node=from_node,
            to_node=to_node,
            method=method,
            flags=flags if flags > 0 else None,
        ))

        # Write back
        scene._raw_header = None
        scene._raw_sections = None
        output = serialize_tscn(scene)
        path.write_text(output, encoding="utf-8")

        data = {
            "connected": True,
            "signal": signal_name,
            "from": from_node,
            "to": to_node,
            "method": method,
            "flags": flags,
            "scene": scene_path,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Connected {data['from']}.{data['signal']} "
                f"-> {data['to']}.{data['method']}"
            )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


@signal.command("list")
@click.argument("scene_path", type=click.Path(exists=True))
@click.pass_context
def list_signals(
    ctx: click.Context,
    scene_path: str,
) -> None:
    """List all signal connections in a scene file."""
    try:
        text = Path(scene_path).read_text(encoding="utf-8")
        scene = parse_tscn(text)

        connections = []
        for conn in scene.connections:
            connections.append({
                "signal": conn.signal,
                "from": conn.from_node,
                "to": conn.to_node,
                "method": conn.method,
                "flags": conn.flags or 0,
            })

        data = {
            "connections": connections,
            "count": len(connections),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            if data["count"] == 0:
                click.echo("No signal connections.")
                return
            click.echo(f"Signal connections ({data['count']}):")
            for conn in data["connections"]:
                flags_str = ""
                if conn["flags"]:
                    flag_names = []
                    if conn["flags"] & 1:
                        flag_names.append("deferred")
                    if conn["flags"] & 2:
                        flag_names.append("persist")
                    if conn["flags"] & 4:
                        flag_names.append("one_shot")
                    flags_str = f" [{', '.join(flag_names)}]"
                click.echo(
                    f"  {conn['from']}.{conn['signal']} "
                    f"-> {conn['to']}.{conn['method']}{flags_str}"
                )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


@signal.command("disconnect")
@click.option(
    "--scene", "scene_path", required=True,
    type=click.Path(exists=True),
    help="Path to the .tscn scene file",
)
@click.option(
    "--signal", "signal_name", required=True,
    help="Signal name to disconnect",
)
@click.option(
    "--from", "from_node", required=True,
    help="Source node path",
)
@click.option(
    "--to", "to_node", required=True,
    help="Target node path",
)
@click.option(
    "--method", required=True,
    help="Target method name",
)
@click.pass_context
def disconnect_signal(
    ctx: click.Context,
    scene_path: str,
    signal_name: str,
    from_node: str,
    to_node: str,
    method: str,
) -> None:
    """Remove a signal connection from a scene file."""
    try:
        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene = parse_tscn(text)

        original_count = len(scene.connections)
        scene.connections = [
            conn for conn in scene.connections
            if not (conn.signal == signal_name
                    and conn.from_node == from_node
                    and conn.to_node == to_node
                    and conn.method == method)
        ]

        if len(scene.connections) == original_count:
            raise ProjectError(
                message=(
                    f"Connection not found: {from_node}.{signal_name} "
                    f"-> {to_node}.{method}"
                ),
                code="CONNECTION_NOT_FOUND",
                fix="Check the signal name, node paths, and method name",
            )

        scene._raw_header = None
        scene._raw_sections = None
        output = serialize_tscn(scene)
        path.write_text(output, encoding="utf-8")

        data = {
            "disconnected": True,
            "signal": signal_name,
            "from": from_node,
            "to": to_node,
            "method": method,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Disconnected {data['from']}.{data['signal']} "
                f"-> {data['to']}.{data['method']}"
            )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)
