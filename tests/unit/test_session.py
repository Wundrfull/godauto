"""Unit tests for DebugSession async TCP session.

Tests use port=0 (OS-assigned free port) and mock TCP clients
to exercise the session lifecycle, recv loop dispatch, buffer
management, and timeout behavior.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from auto_godot.debugger.errors import DebuggerConnectionError, DebuggerTimeoutError
from auto_godot.debugger.protocol import encode_message
from auto_godot.debugger.session import DebugSession, _BUFFER_CAP


def _get_session_port(session: DebugSession) -> int:
    """Extract the OS-assigned port from a session started with port=0."""
    assert session._server is not None
    return session._server.sockets[0].getsockname()[1]


async def _connect_mock_client(
    port: int,
    host: str = "127.0.0.1",
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Open a TCP connection to the session, simulating a Godot game."""
    reader, writer = await asyncio.open_connection(host, port)
    return reader, writer


async def _send_raw_message(
    writer: asyncio.StreamWriter,
    command: str,
    data: list[Any],
    thread_id: int = 1,
) -> None:
    """Send a framed protocol message to the session from a mock client."""
    framed = encode_message(command, data, thread_id)
    writer.write(framed)
    await writer.drain()


class TestSessionLifecycle:
    """Tests for start, close, and context manager."""

    @pytest.mark.asyncio
    async def test_session_start_and_close(self) -> None:
        """Session starts listening and cleans up on close."""
        session = DebugSession(port=0)
        await session.start()
        assert session._server is not None
        assert session._server.is_serving()
        await session.close()
        assert session._server is None

    @pytest.mark.asyncio
    async def test_session_context_manager(self) -> None:
        """Context manager starts and stops the session."""
        async with DebugSession(port=0) as session:
            assert session._server is not None
            assert session.connected is False
        # After exiting context, server should be cleaned up
        assert session._server is None

    @pytest.mark.asyncio
    async def test_session_close_idempotent(self) -> None:
        """Closing an already-closed session does not raise."""
        session = DebugSession(port=0)
        await session.start()
        await session.close()
        await session.close()  # second close should be safe


class TestSessionConnection:
    """Tests for accepting TCP connections."""

    @pytest.mark.asyncio
    async def test_session_accept_connection(self) -> None:
        """Session detects when a mock game connects."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            # Give the event loop a chance to process the connection
            await asyncio.sleep(0.05)
            assert session.connected is True
            client_writer.close()
            await client_writer.wait_closed()

    @pytest.mark.asyncio
    async def test_session_wait_for_connection_timeout(self) -> None:
        """wait_for_connection raises DebuggerTimeoutError on timeout."""
        async with DebugSession(port=0) as session:
            with pytest.raises(DebuggerTimeoutError, match="No game connected"):
                await session.wait_for_connection(timeout=0.1)

    @pytest.mark.asyncio
    async def test_session_wait_for_connection_success(self) -> None:
        """wait_for_connection returns when a client connects."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)

            async def delayed_connect() -> asyncio.StreamWriter:
                await asyncio.sleep(0.05)
                _, writer = await _connect_mock_client(port)
                return writer

            connect_task = asyncio.create_task(delayed_connect())
            await session.wait_for_connection(timeout=5.0)
            assert session.connected is True
            writer = await connect_task
            writer.close()
            await writer.wait_closed()


class TestRecvLoop:
    """Tests for the background receive loop message dispatch."""

    @pytest.mark.asyncio
    async def test_recv_loop_captures_thread_id(self) -> None:
        """First received message's thread_id is captured."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)
            assert session.thread_id is None
            # Send a message with thread_id=42
            await _send_raw_message(client_writer, "some_msg", ["data"], thread_id=42)
            await asyncio.sleep(0.05)
            assert session.thread_id == 42
            client_writer.close()
            await client_writer.wait_closed()

    @pytest.mark.asyncio
    async def test_recv_loop_dispatches_to_pending(self) -> None:
        """Response messages resolve the correct pending Future."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            # Start send_command (it will wait for a response)
            async def respond_after_delay() -> None:
                await asyncio.sleep(0.05)
                await _send_raw_message(
                    client_writer, "test_response", ["result_data"],
                )

            respond_task = asyncio.create_task(respond_after_delay())
            result = await session.send_command("test_response", [], timeout=5.0)
            assert result == ["result_data"]
            await respond_task
            client_writer.close()
            await client_writer.wait_closed()

    @pytest.mark.asyncio
    async def test_recv_loop_buffers_output(self) -> None:
        """Output messages are buffered."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            await _send_raw_message(client_writer, "output", ["Hello, world!"])
            await asyncio.sleep(0.05)
            assert len(session.output_buffer) == 1
            assert session.output_buffer[0] == ["Hello, world!"]
            client_writer.close()
            await client_writer.wait_closed()

    @pytest.mark.asyncio
    async def test_recv_loop_buffers_errors(self) -> None:
        """Error messages are buffered."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            await _send_raw_message(client_writer, "error", ["something broke"])
            await asyncio.sleep(0.05)
            assert len(session.error_buffer) == 1
            assert session.error_buffer[0] == ["something broke"]
            client_writer.close()
            await client_writer.wait_closed()

    @pytest.mark.asyncio
    async def test_recv_loop_discards_performance(self) -> None:
        """Performance profiling messages are silently discarded."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            await _send_raw_message(
                client_writer, "performance:profile_frame", [0.016],
            )
            await asyncio.sleep(0.05)
            assert len(session.output_buffer) == 0
            assert len(session.error_buffer) == 0
            client_writer.close()
            await client_writer.wait_closed()

    @pytest.mark.asyncio
    async def test_output_buffer_cap(self) -> None:
        """Output buffer caps at 1000 entries, dropping oldest."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            # Send 1001 output messages
            for i in range(_BUFFER_CAP + 1):
                await _send_raw_message(client_writer, "output", [f"msg-{i}"])
            # Allow recv loop to process all messages
            await asyncio.sleep(0.3)
            assert len(session.output_buffer) == _BUFFER_CAP
            # Oldest (msg-0) should have been dropped; newest is msg-1000
            assert session.output_buffer[-1] == [f"msg-{_BUFFER_CAP}"]
            assert session.output_buffer[0] == ["msg-1"]
            client_writer.close()
            await client_writer.wait_closed()


class TestSendCommand:
    """Tests for send_command timeout and error behavior."""

    @pytest.mark.asyncio
    async def test_send_command_timeout(self) -> None:
        """send_command raises DebuggerTimeoutError when no response arrives."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            with pytest.raises(DebuggerTimeoutError, match="timed out"):
                await session.send_command("no_reply", [], timeout=0.1)
            # Pending future should be cleaned up
            assert "no_reply" not in session._pending
            client_writer.close()
            await client_writer.wait_closed()

    @pytest.mark.asyncio
    async def test_send_command_not_connected(self) -> None:
        """send_command raises DebuggerConnectionError if not connected."""
        async with DebugSession(port=0) as session:
            with pytest.raises(DebuggerConnectionError, match="Not connected"):
                await session.send_command("anything", [])


class TestConnectionClosed:
    """Tests for game disconnection handling."""

    @pytest.mark.asyncio
    async def test_connection_closed_by_game(self) -> None:
        """recv_loop exits cleanly when the game disconnects."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)
            assert session.connected is True

            # Disconnect the mock client
            client_writer.close()
            await client_writer.wait_closed()
            # Give recv_loop time to notice the disconnection
            await asyncio.sleep(0.1)
            assert session._closed is True
