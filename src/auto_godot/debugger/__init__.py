"""Debugger bridge package for live Godot game interaction."""

from auto_godot.debugger.connect import ConnectResult, async_connect
from auto_godot.debugger.errors import (
    DebuggerConnectionError,
    DebuggerError,
    DebuggerTimeoutError,
    ProtocolError,
)
from auto_godot.debugger.inspector import (
    format_error_messages,
    format_output_messages,
    get_property,
    get_scene_tree,
)
from auto_godot.debugger.models import GameState, NodeProperty, SceneNode, SessionInfo
from auto_godot.debugger.session import DebugSession
from auto_godot.debugger.session_file import (
    cleanup_session,
    read_session_file,
    write_session_file,
)
from auto_godot.debugger.variant import VariantType, decode, encode

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
    "format_error_messages",
    "format_output_messages",
    "get_property",
    "get_scene_tree",
    "read_session_file",
    "write_session_file",
]
