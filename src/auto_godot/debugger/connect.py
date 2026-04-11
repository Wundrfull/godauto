"""Connect workflow: TCP server + game launch + readiness polling.

Orchestrates the full lifecycle of connecting to a Godot game via the
remote debugger protocol: start TCP server, launch game with
--remote-debug, wait for TCP connection, poll until the scene tree
is loaded, and return a ConnectResult with connection metadata.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

from auto_godot.debugger.errors import DebuggerConnectionError, DebuggerTimeoutError
from auto_godot.debugger.session import DebugSession

if TYPE_CHECKING:
    from pathlib import Path

    from auto_godot.backend import GodotBackend

logger = logging.getLogger(__name__)

# Readiness polling: exponential backoff delays in seconds.
_READINESS_DELAYS = [0.5, 1.0, 2.0, 4.0, 8.0, 16.0]


@dataclass(frozen=True)
class ConnectResult:
    """Result of a successful debug connection."""

    host: str
    port: int
    thread_id: int | None
    game_pid: int

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dict with connection metadata."""
        return {
            "status": "connected",
            "host": self.host,
            "port": self.port,
            "thread_id": self.thread_id,
            "game_pid": self.game_pid,
        }


async def async_connect(
    project_path: Path,
    port: int,
    scene: str | None,
    backend: GodotBackend,
    timeout: float = 30.0,
) -> ConnectResult:
    """Run the full connect workflow: server, launch, wait, poll.

    Steps:
      1. Validate project_path contains project.godot
      2. Create and start DebugSession (TCP server)
      3. Launch game via backend.launch_game()
      4. Wait for the game to connect over TCP
      5. Poll for scene tree readiness with exponential backoff
      6. Return ConnectResult on success

    On any failure during steps 2-5, cleans up the session and game
    process before re-raising the error.
    """
    _validate_project(project_path)

    session = DebugSession(port=port)
    process: subprocess.Popen[str] | None = None

    try:
        await _start_session(session, port)
        process = backend.launch_game(project_path, port, scene)
        await session.wait_for_connection(timeout=timeout)
        await _poll_readiness(session)
        _check_process_alive(process)
        return ConnectResult(
            host="127.0.0.1",
            port=port,
            thread_id=session.thread_id,
            game_pid=process.pid,
        )
    except Exception:
        await _cleanup(session, process)
        raise


def _validate_project(project_path: Path) -> None:
    """Ensure project_path exists and contains project.godot."""
    if not (project_path / "project.godot").is_file():
        raise DebuggerConnectionError(
            message=f"No project.godot found in {project_path}",
            code="DEBUG_NO_PROJECT",
            fix="Ensure --project points to a directory containing project.godot",
        )


async def _start_session(session: DebugSession, port: int) -> None:
    """Start the TCP server, converting address-in-use to a clear error."""
    try:
        await session.start()
    except OSError as exc:
        raise DebuggerConnectionError(
            message=f"Cannot bind to port {port}: {exc}",
            code="DEBUG_PORT_IN_USE",
            fix=(
                f"Port {port} is already in use. "
                f"Try --port <alternative> or close the application using port {port}"
            ),
        ) from exc


async def _poll_readiness(session: DebugSession) -> None:
    """Poll scene tree until the game reports data or retries are exhausted."""
    for delay in _READINESS_DELAYS:
        try:
            response = await session.send_command(
                "scene:request_scene_tree", [], timeout=5.0,
            )
            if response:
                logger.debug("Scene tree ready after polling")
                return
        except Exception:
            # Command timeout or other transient error; retry.
            pass
        await asyncio.sleep(delay)

    raise DebuggerTimeoutError(
        message="Scene tree did not become ready within the polling window",
        code="DEBUG_SCENE_NOT_READY",
        fix="The game connected but the scene tree did not load within the timeout period",
    )


def _check_process_alive(process: subprocess.Popen[str]) -> None:
    """Verify the game process has not exited unexpectedly."""
    if process.poll() is not None:
        stderr = ""
        if process.stderr is not None:
            stderr = process.stderr.read()
        raise DebuggerConnectionError(
            message=f"Game process exited with code {process.returncode}",
            code="DEBUG_GAME_CRASHED",
            fix=f"Game crashed: {stderr}" if stderr else "Game exited unexpectedly",
        )


async def _cleanup(
    session: DebugSession,
    process: subprocess.Popen[str] | None,
) -> None:
    """Best-effort cleanup of session and game process."""
    with contextlib.suppress(Exception):
        await session.close()

    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
