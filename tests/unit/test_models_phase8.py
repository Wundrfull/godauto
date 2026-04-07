"""Unit tests for Phase 8 data models: SceneNode, NodeProperty, GameState, SessionInfo."""

from __future__ import annotations

from gdauto.debugger.models import GameState, NodeProperty, SceneNode, SessionInfo


class TestSceneNode:
    """Tests for SceneNode dataclass and to_dict()."""

    def test_basic_to_dict(self) -> None:
        """SceneNode.to_dict() returns expected keys with 'type' (not 'type_name')."""
        node = SceneNode(
            name="Main",
            type_name="Node2D",
            instance_id=1,
            scene_file_path="",
            view_flags=0,
            path="/root/Main",
            children=[],
        )
        d = node.to_dict()
        assert d == {
            "name": "Main",
            "type": "Node2D",
            "path": "/root/Main",
            "instance_id": 1,
            "scene_file_path": "",
            "children": [],
        }

    def test_nested_children_serialize_recursively(self) -> None:
        """SceneNode with nested children serializes children recursively."""
        child = SceneNode(
            name="Sprite",
            type_name="Sprite2D",
            instance_id=2,
            scene_file_path="",
            view_flags=0,
            path="/root/Main/Sprite",
            children=[],
        )
        parent = SceneNode(
            name="Main",
            type_name="Node2D",
            instance_id=1,
            scene_file_path="",
            view_flags=0,
            path="/root/Main",
            children=[child],
        )
        d = parent.to_dict()
        assert len(d["children"]) == 1
        assert d["children"][0]["name"] == "Sprite"
        assert d["children"][0]["type"] == "Sprite2D"

    def test_prune_depth_zero(self) -> None:
        """prune_depth(node, 0) returns node with empty children."""
        child = SceneNode(
            name="Child",
            type_name="Node",
            instance_id=2,
            scene_file_path="",
            view_flags=0,
            path="/root/Main/Child",
            children=[],
        )
        node = SceneNode(
            name="Main",
            type_name="Node2D",
            instance_id=1,
            scene_file_path="",
            view_flags=0,
            path="/root/Main",
            children=[child],
        )
        pruned = SceneNode.prune_depth(node, 0)
        assert pruned.children == []

    def test_prune_depth_one_removes_grandchildren(self) -> None:
        """prune_depth(node, 1) keeps direct children but removes grandchildren."""
        grandchild = SceneNode(
            name="GrandChild",
            type_name="Node",
            instance_id=3,
            scene_file_path="",
            view_flags=0,
            path="/root/Main/Child/GrandChild",
            children=[],
        )
        child = SceneNode(
            name="Child",
            type_name="Node",
            instance_id=2,
            scene_file_path="",
            view_flags=0,
            path="/root/Main/Child",
            children=[grandchild],
        )
        node = SceneNode(
            name="Main",
            type_name="Node2D",
            instance_id=1,
            scene_file_path="",
            view_flags=0,
            path="/root/Main",
            children=[child],
        )
        pruned = SceneNode.prune_depth(node, 1)
        assert len(pruned.children) == 1
        assert pruned.children[0].name == "Child"
        assert pruned.children[0].children == []

    def test_extended_fields_included_when_populated(self) -> None:
        """SceneNode with extended fields includes them in to_dict()."""
        node = SceneNode(
            name="Player",
            type_name="CharacterBody2D",
            instance_id=5,
            scene_file_path="",
            view_flags=0,
            path="/root/Main/Player",
            children=[],
            class_name="MyPlayer",
            script_path="res://player.gd",
            groups=["enemies", "pausable"],
        )
        d = node.to_dict()
        assert d["class_name"] == "MyPlayer"
        assert d["script_path"] == "res://player.gd"
        assert d["groups"] == ["enemies", "pausable"]

    def test_extended_fields_omitted_when_default(self) -> None:
        """SceneNode with no extended fields omits them from to_dict()."""
        node = SceneNode(
            name="Main",
            type_name="Node2D",
            instance_id=1,
            scene_file_path="",
            view_flags=0,
            path="/root/Main",
            children=[],
        )
        d = node.to_dict()
        assert "class_name" not in d
        assert "script_path" not in d
        assert "groups" not in d


class TestNodeProperty:
    """Tests for NodeProperty dataclass and to_dict()."""

    def test_to_dict(self) -> None:
        """NodeProperty.to_dict() returns name, value, type."""
        prop = NodeProperty(
            name="text",
            type=4,
            hint=0,
            hint_string="",
            usage=2,
            value="Hello",
        )
        d = prop.to_dict()
        assert d == {"name": "text", "value": "Hello", "type": 4}


class TestGameState:
    """Tests for GameState dataclass and to_dict()."""

    def test_default_to_dict(self) -> None:
        """GameState defaults: paused=False, speed=1.0, frame=0."""
        state = GameState()
        assert state.to_dict() == {"paused": False, "speed": 1.0, "frame": 0}

    def test_custom_to_dict(self) -> None:
        """GameState with custom values serializes correctly."""
        state = GameState(paused=True, speed=10.0, frame=42)
        assert state.to_dict() == {"paused": True, "speed": 10.0, "frame": 42}


class TestSessionInfo:
    """Tests for SessionInfo dataclass serialization and round-trip."""

    def test_to_dict(self) -> None:
        """SessionInfo.to_dict() returns expected dict."""
        info = SessionInfo(
            host="127.0.0.1",
            port=6007,
            game_pid=1234,
            project_path="/tmp/proj",
            created_at="2026-04-06T12:00:00Z",
        )
        d = info.to_dict()
        assert d == {
            "host": "127.0.0.1",
            "port": 6007,
            "game_pid": 1234,
            "project_path": "/tmp/proj",
            "created_at": "2026-04-06T12:00:00Z",
        }

    def test_from_dict_round_trip(self) -> None:
        """SessionInfo.from_dict(d) round-trips through to_dict()."""
        info = SessionInfo(
            host="127.0.0.1",
            port=6007,
            game_pid=1234,
            project_path="/tmp/proj",
            created_at="2026-04-06T12:00:00Z",
        )
        d = info.to_dict()
        restored = SessionInfo.from_dict(d)
        assert restored == info
