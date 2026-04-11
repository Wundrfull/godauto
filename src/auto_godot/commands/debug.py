"""Live game interaction via Godot's remote debugger protocol."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import rich_click as click

from auto_godot.backend import GodotBackend
from auto_godot.debugger.connect import async_connect
from auto_godot.debugger.errors import DebuggerError
from auto_godot.debugger.execution import (
    get_speed,
    pause_game,
    resume_game,
    set_speed,
    step_frame,
)
from auto_godot.debugger.inspector import (
    format_error_messages,
    format_output_messages,
    get_property,
    get_scene_tree,
)
from auto_godot.debugger.session import DebugSession
from auto_godot.errors import AutoGodotError
from auto_godot.output import GlobalConfig, emit, emit_error

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from auto_godot.debugger.models import GameState

T = TypeVar("T")


async def _run_with_session[T](
    project_path: Path,
    port: int,
    timeout: float,
    backend: GodotBackend,
    fn: Callable[[DebugSession], Awaitable[T]],
) -> T:
    """Auto-connect helper: start session, launch game, run callback.

    Creates a DebugSession, starts the TCP server, launches the game
    via GodotBackend, waits for the connection, executes the callback,
    and cleans up. This makes every inspection command independently
    runnable (D-01) without requiring a prior `debug connect`.
    """
    session = DebugSession(port=port)
    process: subprocess.Popen[str] | None = None
    try:
        await session.start()
        process = backend.launch_game(project_path, port)
        await session.wait_for_connection(timeout=timeout)
        result = await fn(session)
        return result
    finally:
        await session.close()
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


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
    back to auto-godot's TCP server. Waits for the game to connect and
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
    except (DebuggerError, AutoGodotError) as exc:
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


@debug.command("tree")
@click.option(
    "--project",
    type=click.Path(exists=True),
    default=".",
    help="Path to Godot project directory.",
)
@click.option(
    "--port",
    type=int,
    default=6007,
    help="TCP port for debugger connection.",
)
@click.option(
    "--depth",
    type=int,
    default=None,
    help="Maximum tree depth to display.",
)
@click.option(
    "--full",
    is_flag=True,
    default=False,
    help="Include extended metadata per node (class_name, script_path, groups). Slower: O(n) network calls.",
)
@click.option(
    "--timeout",
    type=float,
    default=30.0,
    help="Connection timeout in seconds.",
)
@click.pass_context
def debug_tree(
    ctx: click.Context,
    project: str,
    port: int,
    depth: int | None,
    full: bool,
    timeout: float,
) -> None:
    """Display the live scene tree from a running Godot game.

    Connects to the game, retrieves the scene tree, and displays it
    as a nested hierarchy. Use --depth to limit traversal depth and
    --full to include extended metadata per node.
    """
    config: GlobalConfig = ctx.obj
    backend = GodotBackend(binary_path=config.godot_path)

    async def _get_tree(session: DebugSession) -> Any:
        return await get_scene_tree(session, max_depth=depth, full=full)

    try:
        tree = asyncio.run(
            _run_with_session(
                project_path=Path(project),
                port=port,
                timeout=timeout,
                backend=backend,
                fn=_get_tree,
            )
        )
    except (DebuggerError, AutoGodotError) as exc:
        emit_error(exc, ctx)
        return
    emit(tree.to_dict(), _print_scene_tree, ctx)


def _print_scene_tree(
    data: dict[str, Any], verbose: bool = False, indent: int = 0,
) -> None:
    """Display scene tree in human-readable indented format."""
    prefix = "  " * indent
    line = f"{prefix}{data['path']} ({data['type']})"
    # Show extended metadata if present
    extras: list[str] = []
    if data.get("class_name"):
        extras.append(data["class_name"])
    if data.get("script_path"):
        extras.append(data["script_path"])
    if extras:
        line += f" [{', '.join(extras)}]"
    click.echo(line)
    for child in data.get("children", []):
        _print_scene_tree(child, verbose=verbose, indent=indent + 1)


@debug.command("get")
@click.option(
    "--node",
    required=True,
    help="NodePath (e.g., /root/Main/ScoreLabel).",
)
@click.option(
    "--property",
    "prop_name",
    required=True,
    help="Property name (e.g., text).",
)
@click.option(
    "--project",
    type=click.Path(exists=True),
    default=".",
    help="Path to Godot project directory.",
)
@click.option(
    "--port",
    type=int,
    default=6007,
    help="TCP port for debugger connection.",
)
@click.option(
    "--timeout",
    type=float,
    default=30.0,
    help="Connection timeout in seconds.",
)
@click.pass_context
def debug_get(
    ctx: click.Context,
    node: str,
    prop_name: str,
    project: str,
    port: int,
    timeout: float,
) -> None:
    """Read a single property value from a node in the running game.

    Resolves the NodePath to the object, inspects its properties,
    and returns the requested value.
    """
    config: GlobalConfig = ctx.obj
    backend = GodotBackend(binary_path=config.godot_path)

    async def _get_prop(session: DebugSession) -> object:
        return await get_property(session, node, prop_name)

    try:
        value = asyncio.run(
            _run_with_session(
                project_path=Path(project),
                port=port,
                timeout=timeout,
                backend=backend,
                fn=_get_prop,
            )
        )
    except (DebuggerError, AutoGodotError) as exc:
        emit_error(exc, ctx)
        return
    emit(
        {"node": node, "property": prop_name, "value": value},
        _print_property,
        ctx,
    )


def _print_property(data: dict[str, Any], verbose: bool = False) -> None:
    """Display property value in human-readable format."""
    click.echo(f"{data['node']}.{data['property']} = {data['value']}")


@debug.command("output")
@click.option(
    "--project",
    type=click.Path(exists=True),
    default=".",
    help="Path to Godot project directory.",
)
@click.option(
    "--port",
    type=int,
    default=6007,
    help="TCP port for debugger connection.",
)
@click.option(
    "--timeout",
    type=float,
    default=30.0,
    help="Connection timeout in seconds.",
)
@click.option(
    "--follow",
    is_flag=True,
    default=False,
    help="Stream output continuously (like tail -f).",
)
@click.option(
    "--errors-only",
    is_flag=True,
    default=False,
    help="Show only error messages.",
)
@click.pass_context
def debug_output(
    ctx: click.Context,
    project: str,
    port: int,
    timeout: float,
    follow: bool,
    errors_only: bool,
) -> None:
    """Capture game print() output and runtime errors.

    By default returns a snapshot of buffered messages and exits.
    Use --errors-only to filter to errors only.
    """
    if follow:
        emit_error(
            DebuggerError(
                message="Follow mode not yet supported",
                code="DEBUG_NOT_IMPLEMENTED",
                fix="Use snapshot mode (without --follow) for now",
            ),
            ctx,
        )
        return

    config: GlobalConfig = ctx.obj
    backend = GodotBackend(binary_path=config.godot_path)

    async def _get_output(session: DebugSession) -> list[dict[str, str]]:
        raw_output = session.drain_output()
        raw_errors = session.drain_errors()
        messages = format_output_messages(raw_output)
        messages.extend(format_error_messages(raw_errors))
        return messages

    try:
        all_messages = asyncio.run(
            _run_with_session(
                project_path=Path(project),
                port=port,
                timeout=timeout,
                backend=backend,
                fn=_get_output,
            )
        )
    except (DebuggerError, AutoGodotError) as exc:
        emit_error(exc, ctx)
        return

    if errors_only:
        all_messages = [m for m in all_messages if m.get("type") == "error"]

    emit({"messages": all_messages}, _print_output_messages, ctx)


def _print_output_messages(
    data: dict[str, Any], verbose: bool = False,
) -> None:
    """Display output messages in human-readable format."""
    for msg in data.get("messages", []):
        prefix = "[ERROR] " if msg.get("type") == "error" else ""
        click.echo(f"{prefix}{msg['text']}")


# ---------------------------------------------------------------------------
# Execution control commands (Plan 08-03)
# ---------------------------------------------------------------------------


def _print_game_state(
    data: dict[str, Any], verbose: bool = False, action: str = "",
) -> None:
    """Display game state in human-readable format."""
    speed = data["speed"]
    if action == "paused":
        click.echo(f"Game paused (speed: {speed}x)")
    elif action == "resumed":
        click.echo(f"Game resumed (speed: {speed}x)")
    elif action == "stepped":
        click.echo(f"Stepped one frame (paused, speed: {speed}x)")
    elif action == "speed_set":
        click.echo(f"Speed set to {speed}x")
    elif action == "speed_query":
        click.echo(f"Current speed: {speed}x")


@debug.command("pause")
@click.option(
    "--project",
    type=click.Path(exists=True),
    default=".",
    help="Path to Godot project directory.",
)
@click.option(
    "--port",
    type=int,
    default=6007,
    help="TCP port for debugger connection.",
)
@click.option(
    "--timeout",
    type=float,
    default=30.0,
    help="Connection timeout in seconds.",
)
@click.pass_context
def debug_pause(
    ctx: click.Context, project: str, port: int, timeout: float,
) -> None:
    """Pause the running game."""
    config: GlobalConfig = ctx.obj
    backend = GodotBackend(binary_path=config.godot_path)
    try:
        result = asyncio.run(
            _run_with_session(
                project_path=Path(project),
                port=port,
                timeout=timeout,
                backend=backend,
                fn=pause_game,
            )
        )
    except (DebuggerError, AutoGodotError) as exc:
        emit_error(exc, ctx)
        return
    data = result.to_dict()
    emit(data, lambda d, verbose=False: _print_game_state(d, verbose, "paused"), ctx)


@debug.command("resume")
@click.option(
    "--project",
    type=click.Path(exists=True),
    default=".",
    help="Path to Godot project directory.",
)
@click.option(
    "--port",
    type=int,
    default=6007,
    help="TCP port for debugger connection.",
)
@click.option(
    "--timeout",
    type=float,
    default=30.0,
    help="Connection timeout in seconds.",
)
@click.pass_context
def debug_resume(
    ctx: click.Context, project: str, port: int, timeout: float,
) -> None:
    """Resume a paused game."""
    config: GlobalConfig = ctx.obj
    backend = GodotBackend(binary_path=config.godot_path)
    try:
        result = asyncio.run(
            _run_with_session(
                project_path=Path(project),
                port=port,
                timeout=timeout,
                backend=backend,
                fn=resume_game,
            )
        )
    except (DebuggerError, AutoGodotError) as exc:
        emit_error(exc, ctx)
        return
    data = result.to_dict()
    emit(data, lambda d, verbose=False: _print_game_state(d, verbose, "resumed"), ctx)


@debug.command("step")
@click.option(
    "--project",
    type=click.Path(exists=True),
    default=".",
    help="Path to Godot project directory.",
)
@click.option(
    "--port",
    type=int,
    default=6007,
    help="TCP port for debugger connection.",
)
@click.option(
    "--timeout",
    type=float,
    default=30.0,
    help="Connection timeout in seconds.",
)
@click.pass_context
def debug_step(
    ctx: click.Context, project: str, port: int, timeout: float,
) -> None:
    """Step one frame (pauses first if running)."""
    config: GlobalConfig = ctx.obj
    backend = GodotBackend(binary_path=config.godot_path)
    try:
        result = asyncio.run(
            _run_with_session(
                project_path=Path(project),
                port=port,
                timeout=timeout,
                backend=backend,
                fn=step_frame,
            )
        )
    except (DebuggerError, AutoGodotError) as exc:
        emit_error(exc, ctx)
        return
    data = result.to_dict()
    emit(data, lambda d, verbose=False: _print_game_state(d, verbose, "stepped"), ctx)


@debug.command("speed")
@click.argument("multiplier", type=float, required=False, default=None)
@click.option(
    "--project",
    type=click.Path(exists=True),
    default=".",
    help="Path to Godot project directory.",
)
@click.option(
    "--port",
    type=int,
    default=6007,
    help="TCP port for debugger connection.",
)
@click.option(
    "--timeout",
    type=float,
    default=30.0,
    help="Connection timeout in seconds.",
)
@click.pass_context
def debug_speed(
    ctx: click.Context,
    multiplier: float | None,
    project: str,
    port: int,
    timeout: float,
) -> None:
    """Get or set game speed multiplier.

    MULTIPLIER is a positive float (e.g., 10 for 10x speed, 0.5 for
    half speed). Omit MULTIPLIER to query the current speed.
    """
    config: GlobalConfig = ctx.obj
    backend = GodotBackend(binary_path=config.godot_path)

    if multiplier is None:
        async def _query(session: DebugSession) -> GameState:
            return get_speed(session)

        try:
            result = asyncio.run(
                _run_with_session(
                    project_path=Path(project),
                    port=port,
                    timeout=timeout,
                    backend=backend,
                    fn=_query,
                )
            )
        except (DebuggerError, AutoGodotError) as exc:
            emit_error(exc, ctx)
            return
        data = result.to_dict()
        emit(
            data,
            lambda d, verbose=False: _print_game_state(d, verbose, "speed_query"),
            ctx,
        )
    else:
        async def _set(session: DebugSession) -> GameState:
            return await set_speed(session, multiplier)  # type: ignore[arg-type]

        try:
            result = asyncio.run(
                _run_with_session(
                    project_path=Path(project),
                    port=port,
                    timeout=timeout,
                    backend=backend,
                    fn=_set,
                )
            )
        except (DebuggerError, AutoGodotError) as exc:
            emit_error(exc, ctx)
            return
        data = result.to_dict()
        emit(
            data,
            lambda d, verbose=False: _print_game_state(d, verbose, "speed_set"),
            ctx,
        )
