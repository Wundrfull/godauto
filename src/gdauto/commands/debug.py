"""Live game interaction via Godot's remote debugger protocol."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import rich_click as click

from gdauto.backend import GodotBackend
from gdauto.debugger.connect import ConnectResult, async_connect
from gdauto.debugger.errors import DebuggerError
from gdauto.errors import GdautoError
from gdauto.output import GlobalConfig, emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def debug(ctx: click.Context) -> None:
    """Live game interaction via Godot's remote debugger protocol.

    Connect to a running game, inspect state, inject input, and
    verify behavior.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@debug.command("connect")
@click.option(
    "--project",
    type=click.Path(exists=True),
    default=".",
    help="Path to Godot project directory. Default: current directory.",
)
@click.option(
    "--port",
    type=int,
    default=6007,
    help="TCP port for debugger connection. Default: 6007.",
)
@click.option(
    "--scene",
    type=str,
    default=None,
    help="Specific scene to launch (e.g., res://scenes/main.tscn).",
)
@click.option(
    "--timeout",
    type=float,
    default=30.0,
    help="Connection timeout in seconds. Default: 30.",
)
@click.pass_context
def debug_connect(
    ctx: click.Context,
    project: str,
    port: int,
    scene: str | None,
    timeout: float,
) -> None:
    """Start TCP server, launch game, and wait for debugger connection.

    Launches the Godot game at --project with --remote-debug pointing
    back to gdauto's TCP server. Waits for the game to connect and
    reports connection status. The game runs until explicitly
    disconnected or the process exits.
    """
    config: GlobalConfig = ctx.obj
    backend = GodotBackend(binary_path=config.godot_path)
    try:
        result = asyncio.run(
            async_connect(
                project_path=Path(project),
                port=port,
                scene=scene,
                backend=backend,
                timeout=timeout,
            )
        )
    except (DebuggerError, GdautoError) as exc:
        emit_error(exc, ctx)
        return
    emit(result.to_dict(), _print_connect_status, ctx)


def _print_connect_status(data: dict[str, Any], verbose: bool = False) -> None:
    """Display connection status in human-readable format."""
    click.echo(
        f"Connected to game (PID {data['game_pid']}) "
        f"on {data['host']}:{data['port']}"
    )
    if verbose and data.get("thread_id") is not None:
        click.echo(f"  Thread ID: {data['thread_id']}")
