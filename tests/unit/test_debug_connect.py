"""Tests for the debug connect workflow (async_connect, ConnectResult)."""

from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gdauto.debugger.connect import ConnectResult, async_connect
from gdauto.debugger.errors import DebuggerConnectionError


def test_connect_result_to_dict() -> None:
    """ConnectResult.to_dict() should return the expected structure."""
    result = ConnectResult(
        host="127.0.0.1",
        port=6007,
        thread_id=1,
        game_pid=12345,
    )
    d = result.to_dict()
    assert d["status"] == "connected"
    assert d["host"] == "127.0.0.1"
    assert d["port"] == 6007
    assert d["thread_id"] == 1
    assert d["game_pid"] == 12345


@pytest.mark.asyncio
async def test_async_connect_no_project_file(tmp_path: Path) -> None:
    """async_connect should raise DebuggerConnectionError when project.godot is missing."""
    backend = MagicMock()
    with pytest.raises(DebuggerConnectionError) as exc_info:
        await async_connect(
            project_path=tmp_path,
            port=6007,
            scene=None,
            backend=backend,
            timeout=5.0,
        )
    assert exc_info.value.code == "DEBUG_NO_PROJECT"


@pytest.mark.asyncio
async def test_async_connect_port_in_use(tmp_path: Path) -> None:
    """async_connect should raise DebuggerConnectionError when port is already bound."""
    # Create project.godot so we pass validation
    (tmp_path / "project.godot").write_text("[gd_resource]\n")

    # Bind a socket to claim the port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]

    backend = MagicMock()
    try:
        # Patch DebugSession.start to raise OSError (port in use)
        with patch(
            "gdauto.debugger.connect.DebugSession",
        ) as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.start = AsyncMock(side_effect=OSError(f"Address in use: port {port}"))
            mock_session.close = AsyncMock()
            mock_session_cls.return_value = mock_session

            with pytest.raises(DebuggerConnectionError) as exc_info:
                await async_connect(
                    project_path=tmp_path,
                    port=port,
                    scene=None,
                    backend=backend,
                    timeout=5.0,
                )
            assert exc_info.value.code == "DEBUG_PORT_IN_USE"
    finally:
        sock.close()


@pytest.mark.asyncio
async def test_async_connect_game_crash(tmp_path: Path) -> None:
    """async_connect should raise DebuggerConnectionError when game exits immediately."""
    (tmp_path / "project.godot").write_text("[gd_resource]\n")

    # Mock a process that has already exited
    mock_process = MagicMock()
    mock_process.poll.return_value = 1
    mock_process.returncode = 1
    mock_process.pid = 99999
    mock_process.stderr = MagicMock()
    mock_process.stderr.read.return_value = "Segfault"
    mock_process.terminate = MagicMock()
    mock_process.kill = MagicMock()
    mock_process.wait = MagicMock()

    backend = MagicMock()
    backend.launch_game.return_value = mock_process

    with patch("gdauto.debugger.connect.DebugSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.start = AsyncMock()
        mock_session.wait_for_connection = AsyncMock()
        mock_session.send_command = AsyncMock(return_value=["some_data"])
        mock_session.close = AsyncMock()
        mock_session.thread_id = 1
        mock_session_cls.return_value = mock_session

        with pytest.raises(DebuggerConnectionError) as exc_info:
            await async_connect(
                project_path=tmp_path,
                port=16007,
                scene=None,
                backend=backend,
                timeout=5.0,
            )
        assert exc_info.value.code == "DEBUG_GAME_CRASHED"


@pytest.mark.asyncio
async def test_async_connect_cleanup_on_failure(tmp_path: Path) -> None:
    """Session and process should be cleaned up even when an exception occurs."""
    (tmp_path / "project.godot").write_text("[gd_resource]\n")

    mock_process = MagicMock()
    mock_process.poll.return_value = None  # still alive
    mock_process.pid = 88888
    mock_process.terminate = MagicMock()
    mock_process.wait = MagicMock()

    backend = MagicMock()
    backend.launch_game.return_value = mock_process

    with patch("gdauto.debugger.connect.DebugSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.start = AsyncMock()
        mock_session.wait_for_connection = AsyncMock(
            side_effect=RuntimeError("connection failed"),
        )
        mock_session.close = AsyncMock()
        mock_session_cls.return_value = mock_session

        with pytest.raises(RuntimeError, match="connection failed"):
            await async_connect(
                project_path=tmp_path,
                port=16008,
                scene=None,
                backend=backend,
                timeout=5.0,
            )

        # Verify cleanup happened
        mock_session.close.assert_awaited_once()
        mock_process.terminate.assert_called_once()
