"""Tests for GodotBackend.launch_game() method."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from auto_godot.backend import GodotBackend


@pytest.fixture()
def backend() -> GodotBackend:
    """Create a backend with a fake binary path and cached version.

    Setting _version bypasses the version check in ensure_binary(),
    so no real subprocess.run call is made during discovery.
    """
    b = GodotBackend(binary_path="/usr/bin/godot")
    b._version = "4.5.0.stable"
    return b


@patch("auto_godot.backend.subprocess.Popen")
def test_launch_game_returns_popen(
    mock_popen: MagicMock,
    backend: GodotBackend,
    tmp_path: Path,
) -> None:
    """launch_game should call Popen with --remote-debug and return the result."""
    sentinel = MagicMock()
    mock_popen.return_value = sentinel

    result = backend.launch_game(tmp_path)

    assert result is sentinel
    args = mock_popen.call_args
    cmd = args[0][0]
    assert "--remote-debug" in cmd
    assert "tcp://127.0.0.1:6007" in cmd
    assert "--path" in cmd


@patch("auto_godot.backend.subprocess.Popen")
def test_launch_game_custom_port(
    mock_popen: MagicMock,
    backend: GodotBackend,
    tmp_path: Path,
) -> None:
    """launch_game should use the specified port in the remote-debug URL."""
    backend.launch_game(tmp_path, port=9999)

    cmd = mock_popen.call_args[0][0]
    assert "tcp://127.0.0.1:9999" in cmd


@patch("auto_godot.backend.subprocess.Popen")
def test_launch_game_with_scene(
    mock_popen: MagicMock,
    backend: GodotBackend,
    tmp_path: Path,
) -> None:
    """launch_game should append the scene path to the command."""
    backend.launch_game(tmp_path, scene="res://scenes/main.tscn")

    cmd = mock_popen.call_args[0][0]
    assert "res://scenes/main.tscn" in cmd


@patch("auto_godot.backend.subprocess.Popen")
def test_launch_game_no_headless(
    mock_popen: MagicMock,
    backend: GodotBackend,
    tmp_path: Path,
) -> None:
    """launch_game must NOT include --headless (game needs its window)."""
    backend.launch_game(tmp_path)

    cmd = mock_popen.call_args[0][0]
    assert "--headless" not in cmd


@patch("auto_godot.backend.subprocess.Popen")
def test_launch_game_calls_ensure_binary(
    mock_popen: MagicMock,
    tmp_path: Path,
) -> None:
    """launch_game should call ensure_binary() before creating the process."""
    backend = GodotBackend(binary_path="/usr/bin/godot")
    with patch.object(backend, "ensure_binary", return_value="/usr/bin/godot") as mock_ensure:
        backend.launch_game(tmp_path)
        mock_ensure.assert_called_once()
