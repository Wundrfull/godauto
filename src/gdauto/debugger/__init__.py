"""Debugger bridge package for live Godot game interaction."""

from gdauto.debugger.connect import ConnectResult, async_connect
from gdauto.debugger.errors import (
    DebuggerConnectionError,
    DebuggerError,
    DebuggerTimeoutError,
    ProtocolError,
)
from gdauto.debugger.session import DebugSession
from gdauto.debugger.variant import VariantType, decode, encode

__all__ = [
    "ConnectResult",
    "DebugSession",
    "DebuggerConnectionError",
    "DebuggerError",
    "DebuggerTimeoutError",
    "ProtocolError",
    "VariantType",
    "async_connect",
    "decode",
    "encode",
]
