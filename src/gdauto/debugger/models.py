"""Debugger data models for Godot type wrappers.

Provides Python wrappers that distinguish Godot StringName and NodePath
from plain Python str in Variant encoding contexts.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GodotStringName:
    """Distinguishes Godot StringName from plain Python str.

    Used by the Variant codec to select STRING_NAME (type 21)
    encoding instead of STRING (type 4).
    """

    value: str

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class GodotNodePath:
    """Distinguishes Godot NodePath from plain Python str.

    Used by the Variant codec to select NODE_PATH (type 22)
    encoding instead of STRING (type 4).
    """

    value: str

    def __str__(self) -> str:
        return self.value
