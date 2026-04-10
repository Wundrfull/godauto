"""Debugger-specific error hierarchy.

All debugger errors inherit from AutoGodotError and carry machine-readable
error codes, fix suggestions, and to_dict() for --json output.
"""

from __future__ import annotations

from dataclasses import dataclass

from auto_godot.errors import AutoGodotError


@dataclass
class DebuggerError(AutoGodotError):
    """Base for all debugger-related errors."""


@dataclass
class DebuggerConnectionError(DebuggerError):
    """Raised when TCP connection fails or is refused."""


@dataclass
class DebuggerTimeoutError(DebuggerError):
    """Raised when a command response times out."""


@dataclass
class ProtocolError(DebuggerError):
    """Raised on protocol-level errors (bad encoding, invalid message)."""
