"""Debugger bridge package for live Godot game interaction."""

from gdauto.debugger.connect import ConnectResult, async_connect
from gdauto.debugger.errors import (
    DebuggerConnectionError,
    DebuggerError,
    DebuggerTimeoutError,
    ProtocolError,
)
from gdauto.debugger.models import GameState, NodeProperty, SceneNode, SessionInfo
from gdauto.debugger.session import DebugSession
from gdauto.debugger.session_file import (
    cleanup_session,
    read_session_file,
    write_session_file,
)
from gdauto.debugger.variant import VariantType, decode, encode

__all__ = [
    "ConnectResult",
    "DebugSession",
    "DebuggerConnectionError",
    "DebuggerError",
    "DebuggerTimeoutError",
    "GameState",
    "NodeProperty",
    "ProtocolError",
    "SceneNode",
    "SessionInfo",
    "VariantType",
    "async_connect",
    "cleanup_session",
    "decode",
    "encode",
    "read_session_file",
    "write_session_file",
]
