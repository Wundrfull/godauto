"""Debugger data models for Godot type wrappers and scene inspection.

Provides Python wrappers that distinguish Godot StringName and NodePath
from plain Python str in Variant encoding contexts, plus dataclasses
for scene tree nodes, node properties, game state, and session info
used by Phase 8 inspector and execution control commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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


@dataclass
class SceneNode:
    """A node in the live scene tree returned by the debugger.

    The 6 wire-format fields (name through children) are always populated
    by parse_scene_tree. The 3 extended fields (class_name, script_path,
    groups) are populated only when --full mode triggers secondary
    inspect_objects calls.
    """

    name: str
    type_name: str
    instance_id: int
    scene_file_path: str
    view_flags: int
    path: str
    children: list[SceneNode] = field(default_factory=list)
    # Extended fields per D-06 (populated by --full mode only)
    class_name: str | None = None
    script_path: str | None = None
    groups: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict.

        Uses key "type" (not "type_name") per D-05. Extended fields
        (class_name, script_path, groups) are included only when they
        have non-default values to keep default output clean.
        """
        result: dict[str, Any] = {
            "name": self.name,
            "type": self.type_name,
            "path": self.path,
            "instance_id": self.instance_id,
            "scene_file_path": self.scene_file_path,
            "children": [c.to_dict() for c in self.children],
        }
        if self.class_name is not None:
            result["class_name"] = self.class_name
        if self.script_path is not None:
            result["script_path"] = self.script_path
        if self.groups:
            result["groups"] = list(self.groups)
        return result

    @staticmethod
    def prune_depth(node: SceneNode, max_depth: int) -> SceneNode:
        """Return a copy of node with children pruned beyond max_depth.

        A max_depth of 0 returns the node with no children. A max_depth
        of 1 keeps direct children but removes their children.
        """
        if max_depth <= 0:
            return SceneNode(
                name=node.name,
                type_name=node.type_name,
                instance_id=node.instance_id,
                scene_file_path=node.scene_file_path,
                view_flags=node.view_flags,
                path=node.path,
                children=[],
                class_name=node.class_name,
                script_path=node.script_path,
                groups=list(node.groups),
            )
        return SceneNode(
            name=node.name,
            type_name=node.type_name,
            instance_id=node.instance_id,
            scene_file_path=node.scene_file_path,
            view_flags=node.view_flags,
            path=node.path,
            children=[
                SceneNode.prune_depth(c, max_depth - 1)
                for c in node.children
            ],
            class_name=node.class_name,
            script_path=node.script_path,
            groups=list(node.groups),
        )


@dataclass(frozen=True, slots=True)
class NodeProperty:
    """A single property of a scene node returned by inspect_object."""

    name: str
    type: int
    hint: int
    hint_string: str
    usage: int
    value: object

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict with name, value, and type."""
        return {"name": self.name, "value": self.value, "type": self.type}


@dataclass
class GameState:
    """Snapshot of the game's execution state.

    Returned by all execution control commands per D-12.
    """

    paused: bool = False
    speed: float = 1.0
    frame: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict."""
        return {"paused": self.paused, "speed": self.speed, "frame": self.frame}


@dataclass
class SessionInfo:
    """Metadata for a debugger session persisted to .auto-godot/session.json.

    Tracks the game PID to prevent duplicate launches (D-03).
    """

    host: str
    port: int
    game_pid: int
    project_path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict."""
        return {
            "host": self.host,
            "port": self.port,
            "game_pid": self.game_pid,
            "project_path": self.project_path,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SessionInfo:
        """Construct a SessionInfo from a dict (inverse of to_dict)."""
        return cls(
            host=d["host"],
            port=d["port"],
            game_pid=d["game_pid"],
            project_path=d["project_path"],
            created_at=d["created_at"],
        )
