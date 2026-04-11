"""Async TCP session for Godot debugger protocol.

Manages the TCP server lifecycle: starts listening, accepts a single
game connection, runs a background receive loop that continuously
drains messages (preventing buffer flooding), and dispatches responses
to pending command futures.

The recv loop handles three message categories:
  1. Responses to commands we sent (dispatched to pending Futures)
  2. Unsolicited output/error messages (buffered, capped at 1000)
  3. Performance profiling messages (discarded silently; ~60/sec)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
from dataclasses import dataclass, field
from typing import Any

from auto_godot.debugger.errors import (
    DebuggerConnectionError,
    DebuggerTimeoutError,
    ProtocolError,
)
from auto_godot.debugger.models import GameState
from auto_godot.debugger.protocol import read_message, write_message

logger = logging.getLogger(__name__)

# Maximum entries in output/error buffers before oldest are dropped.
_BUFFER_CAP = 1000


@dataclass
class DebugSession:
    """Async TCP session that accepts a Godot debugger connection.

    Usage::

        async with DebugSession(port=6007) as session:
            await session.wait_for_connection(timeout=30)
            result = await session.send_command("get_stack_dump", [])
    """

    port: int = 6007
    host: str = "127.0.0.1"

    # Internal state (initialized in __post_init__)
    _server: asyncio.Server | None = field(default=None, init=False, repr=False)
    _reader: asyncio.StreamReader | None = field(default=None, init=False, repr=False)
    _writer: asyncio.StreamWriter | None = field(default=None, init=False, repr=False)
    _connected: asyncio.Event = field(default_factory=asyncio.Event, init=False, repr=False)
    _recv_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _thread_id: int | None = field(default=None, init=False, repr=False)
    _pending: dict[str, asyncio.Future[list[Any]]] = field(
        default_factory=dict, init=False, repr=False,
    )
    _output_buffer: list[list[Any]] = field(default_factory=list, init=False, repr=False)
    _error_buffer: list[list[Any]] = field(default_factory=list, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)
    game_paused: bool = field(default=False, init=False, repr=False)
    current_speed: float = field(default=1.0, init=False, repr=False)

    async def start(self) -> None:
        """Start the TCP server and begin listening for connections.

        Returns immediately after the server socket is bound. Call
        wait_for_connection() to block until a game connects.
        """
        self._closed = False
        self._server = await asyncio.start_server(
            self._handle_connection, self.host, self.port,
        )
        # Ensure SO_REUSEADDR for quick port reuse after crashes.
        # asyncio sets this on some platforms, but be explicit.
        for sock in self._server.sockets:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    async def wait_for_connection(self, timeout: float = 30.0) -> None:
        """Block until a game connects or timeout expires.

        Raises DebuggerTimeoutError if no connection arrives within
        the specified timeout.
        """
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=timeout)
        except TimeoutError as err:
            raise DebuggerTimeoutError(
                message=f"No game connected within {timeout}s",
                code="DEBUG_CONNECT_TIMEOUT",
                fix=f"Check that the game launched successfully and can reach {self.host}:{self.port}",
            ) from err

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Callback invoked when a game connects to the TCP server."""
        self._reader = reader
        self._writer = writer
        self._connected.set()
        self._recv_task = asyncio.create_task(self._recv_loop())

    async def _recv_loop(self) -> None:
        """Continuously read messages from the connected game.

        Dispatches responses to pending futures, buffers output/error
        messages, and silently discards performance profiling data.
        """
        assert self._reader is not None
        try:
            while not self._closed:
                command, thread_id, data = await read_message(self._reader)
                # Capture thread_id from first received message
                if self._thread_id is None:
                    self._thread_id = thread_id
                self._dispatch(command, data)
        except asyncio.IncompleteReadError:
            # Game closed the connection
            logger.debug("Game disconnected (incomplete read)")
            self._closed = True
        except ProtocolError as exc:
            logger.warning("Protocol error in recv_loop: %s", exc)
            # Connection may still be usable; mark closed to be safe
            self._closed = True

    def _dispatch(self, command: str, data: list[Any]) -> None:
        """Route a received message to the correct handler."""
        if command in self._pending:
            self._pending.pop(command).set_result(data)
        elif command == "debug_enter":
            self.game_paused = True
        elif command == "debug_exit":
            self.game_paused = False
        elif command == "output":
            self._append_buffer(self._output_buffer, data)
        elif command == "error":
            self._append_buffer(self._error_buffer, data)
        elif command.startswith("performance:"):
            # Performance profiling messages arrive ~60/sec; discard.
            pass
        else:
            logger.debug("Discarding unknown unsolicited message: %s", command)

    @staticmethod
    def _append_buffer(buf: list[list[Any]], data: list[Any]) -> None:
        """Append to a capped buffer, dropping the oldest entry if full."""
        if len(buf) >= _BUFFER_CAP:
            buf.pop(0)
        buf.append(data)

    async def send_command(
        self,
        command: str,
        data: list[Any] | None = None,
        timeout: float = 10.0,
        response_key: str | None = None,
    ) -> list[Any]:
        """Send a command to the game and wait for its response.

        Creates a Future keyed by response_key (or command name if not
        specified), sends the message, and awaits the response with a
        timeout. The recv_loop dispatches the response to the Future
        when it arrives.

        The response_key parameter handles commands where the request
        and response have different names (e.g. "scene:request_scene_tree"
        sends the request but "scene:scene_tree" is the response).

        Raises DebuggerConnectionError if not connected.
        Raises DebuggerTimeoutError if the response does not arrive.
        """
        if self._writer is None or self._closed:
            raise DebuggerConnectionError(
                message="Not connected to a game",
                code="DEBUG_NOT_CONNECTED",
                fix="Call start() and wait_for_connection() before sending commands",
            )
        key = response_key if response_key is not None else command
        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[Any]] = loop.create_future()
        self._pending[key] = future
        thread_id = self._thread_id if self._thread_id is not None else 1
        await write_message(self._writer, command, data or [], thread_id)
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as err:
            self._pending.pop(key, None)
            raise DebuggerTimeoutError(
                message=f"Command '{command}' timed out after {timeout}s",
                code="DEBUG_CMD_TIMEOUT",
                fix=f"Command '{command}' did not receive a response within {timeout}s",
            ) from err
        return result

    async def send_fire_and_forget(
        self, command: str, data: list[Any] | None = None,
    ) -> None:
        """Send a command without waiting for a response.

        Used for execution control commands (pause, resume, step, speed)
        where Godot confirms state changes via unsolicited debug_enter/
        debug_exit messages rather than matching responses.
        """
        if self._writer is None or self._closed:
            raise DebuggerConnectionError(
                message="Not connected to a game",
                code="DEBUG_NOT_CONNECTED",
                fix="Call start() and wait_for_connection() before sending commands",
            )
        thread_id = self._thread_id if self._thread_id is not None else 1
        await write_message(self._writer, command, data or [], thread_id)

    def drain_output(self) -> list[list[Any]]:
        """Return buffered output messages and clear the buffer."""
        result = list(self._output_buffer)
        self._output_buffer.clear()
        return result

    def drain_errors(self) -> list[list[Any]]:
        """Return buffered error messages and clear the buffer."""
        result = list(self._error_buffer)
        self._error_buffer.clear()
        return result

    @property
    def game_state(self) -> GameState:
        """Return a snapshot of the game's execution state."""
        return GameState(
            paused=self.game_paused,
            speed=self.current_speed,
            frame=0,
        )

    async def close(self) -> None:
        """Shut down the session, cancelling background tasks and closing sockets."""
        self._closed = True
        if self._recv_task is not None and not self._recv_task.done():
            self._recv_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._recv_task
            self._recv_task = None
        if self._writer is not None:
            self._writer.close()
            with contextlib.suppress(OSError, ConnectionError):
                await self._writer.wait_closed()
            self._writer = None
        self._reader = None
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._connected.clear()
        self._thread_id = None
        self._pending.clear()
        self._output_buffer.clear()
        self._error_buffer.clear()
        self.game_paused = False
        self.current_speed = 1.0

    @property
    def connected(self) -> bool:
        """Whether a game is currently connected."""
        return self._connected.is_set()

    @property
    def thread_id(self) -> int | None:
        """Thread ID captured from the first received message."""
        return self._thread_id

    @property
    def output_buffer(self) -> list[list[Any]]:
        """Copy of buffered output messages from the game."""
        return list(self._output_buffer)

    @property
    def error_buffer(self) -> list[list[Any]]:
        """Copy of buffered error messages from the game."""
        return list(self._error_buffer)

    async def __aenter__(self) -> DebugSession:
        """Start the session as an async context manager."""
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Close the session when exiting the context manager."""
        await self.close()
