"""Unit tests for Phase 8 DebugSession enhancements.

Tests debug_enter/debug_exit dispatch, response_key parameter,
send_fire_and_forget, drain methods, current_speed tracking,
and game_state property.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from auto_godot.debugger.errors import DebuggerConnectionError
from auto_godot.debugger.models import GameState
from auto_godot.debugger.protocol import encode_message
from auto_godot.debugger.session import DebugSession


def _get_session_port(session: DebugSession) -> int:
    """Extract the OS-assigned port from a session started with port=0."""
    assert session._server is not None
    return session._server.sockets[0].getsockname()[1]


async def _connect_mock_client(
    port: int,
    host: str = "127.0.0.1",
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Open a TCP connection to the session, simulating a Godot game."""
    return await asyncio.open_connection(host, port)


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


class TestDebugEnterExit:
    """Tests for debug_enter/debug_exit dispatch and game_paused state."""

    @pytest.mark.asyncio
    async def test_game_paused_defaults_false(self) -> None:
        """session.game_paused defaults to False on fresh session."""
        async with DebugSession(port=0) as session:
            assert session.game_paused is False

    @pytest.mark.asyncio
    async def test_debug_enter_sets_paused(self) -> None:
        """When session receives debug_enter, game_paused becomes True."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            await _send_raw_message(client_writer, "debug_enter", [1, False, "", 0])
            await asyncio.sleep(0.05)
            assert session.game_paused is True
            client_writer.close()
            await client_writer.wait_closed()

    @pytest.mark.asyncio
    async def test_debug_exit_sets_unpaused(self) -> None:
        """When session receives debug_exit, game_paused becomes False."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            # First pause, then unpause
            await _send_raw_message(client_writer, "debug_enter", [1, False, "", 0])
            await asyncio.sleep(0.05)
            assert session.game_paused is True

            await _send_raw_message(client_writer, "debug_exit", [1, False, "", 0])
            await asyncio.sleep(0.05)
            assert session.game_paused is False
            client_writer.close()
            await client_writer.wait_closed()


class TestResponseKey:
    """Tests for the response_key parameter on send_command."""

    @pytest.mark.asyncio
    async def test_response_key_resolves_correctly(self) -> None:
        """send_command with response_key registers future under that key."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            async def respond_after_delay() -> None:
                await asyncio.sleep(0.05)
                # Response arrives as "scene:scene_tree" (the response_key)
                await _send_raw_message(
                    client_writer, "scene:scene_tree", ["tree_data"],
                )

            respond_task = asyncio.create_task(respond_after_delay())
            result = await session.send_command(
                "scene:request_scene_tree", [],
                response_key="scene:scene_tree",
                timeout=5.0,
            )
            assert result == ["tree_data"]
            await respond_task
            client_writer.close()
            await client_writer.wait_closed()

    @pytest.mark.asyncio
    async def test_send_command_without_response_key_backward_compat(self) -> None:
        """send_command without response_key uses command name as key."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            async def respond_after_delay() -> None:
                await asyncio.sleep(0.05)
                await _send_raw_message(
                    client_writer, "get_stack_dump", ["stack_data"],
                )

            respond_task = asyncio.create_task(respond_after_delay())
            result = await session.send_command(
                "get_stack_dump", [], timeout=5.0,
            )
            assert result == ["stack_data"]
            await respond_task
            client_writer.close()
            await client_writer.wait_closed()


class TestSendFireAndForget:
    """Tests for send_fire_and_forget method."""

    @pytest.mark.asyncio
    async def test_sends_without_pending_future(self) -> None:
        """send_fire_and_forget sends message without creating a pending future."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            await session.send_fire_and_forget("scene:suspend_changed", [True])
            # No pending future should exist
            assert "scene:suspend_changed" not in session._pending
            client_writer.close()
            await client_writer.wait_closed()

    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self) -> None:
        """send_fire_and_forget raises DebuggerConnectionError if not connected."""
        async with DebugSession(port=0) as session:
            with pytest.raises(DebuggerConnectionError, match="Not connected"):
                await session.send_fire_and_forget("some_command", [])

    @pytest.mark.asyncio
    async def test_uses_thread_id(self) -> None:
        """send_fire_and_forget uses the session's thread_id."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            client_reader, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            # Send a message to capture thread_id first
            await _send_raw_message(client_writer, "output", ["hello"], thread_id=42)
            await asyncio.sleep(0.05)
            assert session.thread_id == 42

            # Now fire and forget; should use thread_id=42
            await session.send_fire_and_forget("test_cmd", [True])
            # Just verify it did not raise
            client_writer.close()
            await client_writer.wait_closed()


class TestDrainMethods:
    """Tests for drain_output() and drain_errors()."""

    @pytest.mark.asyncio
    async def test_drain_output_returns_and_clears(self) -> None:
        """drain_output() returns list and clears the buffer."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            await _send_raw_message(client_writer, "output", ["msg1"])
            await _send_raw_message(client_writer, "output", ["msg2"])
            await asyncio.sleep(0.1)
            assert len(session.output_buffer) == 2

            drained = session.drain_output()
            assert len(drained) == 2
            assert drained[0] == ["msg1"]
            assert drained[1] == ["msg2"]
            # Buffer should now be empty
            assert session.output_buffer == []
            client_writer.close()
            await client_writer.wait_closed()

    @pytest.mark.asyncio
    async def test_drain_errors_returns_and_clears(self) -> None:
        """drain_errors() returns list and clears the buffer."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            await _send_raw_message(client_writer, "error", ["err1"])
            await asyncio.sleep(0.1)
            assert len(session.error_buffer) == 1

            drained = session.drain_errors()
            assert len(drained) == 1
            assert drained[0] == ["err1"]
            assert session.error_buffer == []
            client_writer.close()
            await client_writer.wait_closed()


class TestCurrentSpeedAndGameState:
    """Tests for current_speed tracking and game_state property."""

    @pytest.mark.asyncio
    async def test_current_speed_defaults_to_one(self) -> None:
        """session.current_speed defaults to 1.0."""
        async with DebugSession(port=0) as session:
            assert session.current_speed == 1.0

    @pytest.mark.asyncio
    async def test_game_state_property(self) -> None:
        """session.game_state returns GameState with current values."""
        async with DebugSession(port=0) as session:
            state = session.game_state
            assert isinstance(state, GameState)
            assert state.paused is False
            assert state.speed == 1.0
            assert state.frame == 0

    @pytest.mark.asyncio
    async def test_game_state_reflects_pause(self) -> None:
        """session.game_state reflects game_paused after debug_enter."""
        async with DebugSession(port=0) as session:
            port = _get_session_port(session)
            _, client_writer = await _connect_mock_client(port)
            await asyncio.sleep(0.05)

            await _send_raw_message(client_writer, "debug_enter", [1, False, "", 0])
            await asyncio.sleep(0.05)
            state = session.game_state
            assert state.paused is True
            client_writer.close()
            await client_writer.wait_closed()

    @pytest.mark.asyncio
    async def test_game_state_reflects_speed(self) -> None:
        """session.game_state reflects current_speed when set externally."""
        async with DebugSession(port=0) as session:
            session.current_speed = 5.0
            state = session.game_state
            assert state.speed == 5.0
