"""Tests for debugger inspector module: scene tree parsing, enrichment, property access, output formatting."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from auto_godot.debugger.errors import DebuggerError
from auto_godot.debugger.models import NodeProperty, SceneNode


# ---------------------------------------------------------------------------
# parse_scene_tree
# ---------------------------------------------------------------------------

class TestParseSceneTree:
    """Tests for parse_scene_tree: recursive flat-array parser."""

    def test_single_root_node(self) -> None:
        """Single node with child_count=0 returns SceneNode with empty children."""
        from auto_godot.debugger.inspector import parse_scene_tree

        data = [0, "root", "Node", 1, "", 0]
        node, offset = parse_scene_tree(data, offset=0, parent_path="")
        assert node.name == "root"
        assert node.type_name == "Node"
        assert node.instance_id == 1
        assert node.path == "/root"
        assert node.children == []
        assert offset == 6

    def test_root_with_two_children(self) -> None:
        """Root with child_count=2 recursively parses 2 children."""
        from auto_godot.debugger.inspector import parse_scene_tree

        data = [
            2, "root", "Node", 1, "", 0,
            0, "A", "Sprite2D", 2, "", 0,
            0, "B", "Label", 3, "", 0,
        ]
        node, offset = parse_scene_tree(data, offset=0, parent_path="")
        assert node.name == "root"
        assert len(node.children) == 2
        assert node.children[0].name == "A"
        assert node.children[0].type_name == "Sprite2D"
        assert node.children[0].path == "/root/A"
        assert node.children[1].name == "B"
        assert node.children[1].type_name == "Label"
        assert node.children[1].path == "/root/B"
        assert offset == 18

    def test_deeply_nested_tree(self) -> None:
        """3-level tree parses with accumulated paths."""
        from auto_godot.debugger.inspector import parse_scene_tree

        data = [
            1, "root", "Node", 1, "", 0,
            1, "Main", "Node2D", 2, "", 0,
            0, "Player", "CharacterBody2D", 3, "res://player.tscn", 0,
        ]
        node, offset = parse_scene_tree(data, offset=0, parent_path="")
        assert node.path == "/root"
        assert node.children[0].path == "/root/Main"
        assert node.children[0].children[0].path == "/root/Main/Player"
        assert node.children[0].children[0].scene_file_path == "res://player.tscn"
        assert offset == 18

    def test_extended_fields_default_to_none(self) -> None:
        """Parsed nodes have class_name=None, script_path=None, groups=[]."""
        from auto_godot.debugger.inspector import parse_scene_tree

        data = [0, "root", "Node", 1, "", 0]
        node, _ = parse_scene_tree(data, offset=0, parent_path="")
        assert node.class_name is None
        assert node.script_path is None
        assert node.groups == []

    def test_empty_tree_single_node(self) -> None:
        """Single node with child_count=0 returns SceneNode with empty children list."""
        from auto_godot.debugger.inspector import parse_scene_tree

        data = [0, "Leaf", "Sprite2D", 42, "", 0]
        node, offset = parse_scene_tree(data, offset=0, parent_path="/root")
        assert node.name == "Leaf"
        assert node.path == "/root/Leaf"
        assert node.children == []
        assert offset == 6


# ---------------------------------------------------------------------------
# parse_object_properties
# ---------------------------------------------------------------------------

class TestParseObjectProperties:
    """Tests for parse_object_properties: flat property array parser."""

    def test_basic_properties(self) -> None:
        """Parses two properties correctly from flat array."""
        from auto_godot.debugger.inspector import parse_object_properties

        data = [
            42, "Label",
            ["text", 4, 0, "", 2, "Hello", "visible", 1, 0, "", 2, True],
        ]
        obj_id, class_name, props = parse_object_properties(data)
        assert obj_id == 42
        assert class_name == "Label"
        assert len(props) == 2
        assert props[0].name == "text"
        assert props[0].value == "Hello"
        assert props[1].name == "visible"
        assert props[1].value is True

    def test_skip_category_separators(self) -> None:
        """Properties with usage==128 are skipped (category separators)."""
        from auto_godot.debugger.inspector import parse_object_properties

        data = [
            10, "Node",
            ["Category", 0, 0, "", 128, None, "name", 4, 0, "", 2, "Main"],
        ]
        _, _, props = parse_object_properties(data)
        assert len(props) == 1
        assert props[0].name == "name"

    def test_empty_property_array(self) -> None:
        """Empty property array returns empty list."""
        from auto_godot.debugger.inspector import parse_object_properties

        data = [10, "Node", []]
        _, _, props = parse_object_properties(data)
        assert props == []


# ---------------------------------------------------------------------------
# enrich_scene_tree
# ---------------------------------------------------------------------------

class TestEnrichSceneTree:
    """Tests for enrich_scene_tree: D-06 extended metadata via inspect_objects."""

    def test_populates_class_name_when_differs(self) -> None:
        """class_name is set when inspect_objects returns a different class than type_name."""
        from auto_godot.debugger.inspector import enrich_scene_tree

        root = SceneNode(
            name="Player", type_name="CharacterBody2D",
            instance_id=1, scene_file_path="", view_flags=0,
            path="/root/Player",
        )
        session = MagicMock()
        # inspect_objects returns: [obj_id, class_name, prop_array]
        session.send_command = AsyncMock(return_value=[
            1, "PlayerScript", ["script", 24, 0, "", 2, MagicMock(resource_path="res://player.gd")],
        ])
        result = asyncio.run(enrich_scene_tree(session, root))
        assert result.class_name == "PlayerScript"

    def test_class_name_none_when_matches_type(self) -> None:
        """class_name stays None when inspect_objects class matches type_name."""
        from auto_godot.debugger.inspector import enrich_scene_tree

        root = SceneNode(
            name="Label", type_name="Label",
            instance_id=1, scene_file_path="", view_flags=0,
            path="/root/Label",
        )
        session = MagicMock()
        session.send_command = AsyncMock(return_value=[
            1, "Label", ["visible", 1, 0, "", 2, True],
        ])
        result = asyncio.run(enrich_scene_tree(session, root))
        assert result.class_name is None

    def test_populates_script_path(self) -> None:
        """script_path is populated from 'script' property's resource_path."""
        from auto_godot.debugger.inspector import enrich_scene_tree

        root = SceneNode(
            name="Main", type_name="Node2D",
            instance_id=5, scene_file_path="", view_flags=0,
            path="/root/Main",
        )
        script_value = MagicMock()
        script_value.resource_path = "res://main.gd"
        session = MagicMock()
        session.send_command = AsyncMock(return_value=[
            5, "MyGame", ["script", 24, 0, "", 2, script_value],
        ])
        result = asyncio.run(enrich_scene_tree(session, root))
        assert result.script_path == "res://main.gd"

    def test_groups_default_empty(self) -> None:
        """Groups stay empty (not available via inspect_objects)."""
        from auto_godot.debugger.inspector import enrich_scene_tree

        root = SceneNode(
            name="Node", type_name="Node",
            instance_id=1, scene_file_path="", view_flags=0,
            path="/root/Node",
        )
        session = MagicMock()
        session.send_command = AsyncMock(return_value=[
            1, "Node", [],
        ])
        result = asyncio.run(enrich_scene_tree(session, root))
        assert result.groups == []

    def test_enriches_children(self) -> None:
        """enrich_scene_tree walks entire tree, calling inspect_objects per node."""
        from auto_godot.debugger.inspector import enrich_scene_tree

        child = SceneNode(
            name="Child", type_name="Sprite2D",
            instance_id=2, scene_file_path="", view_flags=0,
            path="/root/Main/Child",
        )
        root = SceneNode(
            name="Main", type_name="Node2D",
            instance_id=1, scene_file_path="", view_flags=0,
            path="/root/Main", children=[child],
        )
        session = MagicMock()
        session.send_command = AsyncMock(side_effect=[
            [1, "Node2D", []],
            [2, "Sprite2D", []],
        ])
        asyncio.run(enrich_scene_tree(session, root))
        assert session.send_command.call_count == 2


# ---------------------------------------------------------------------------
# get_scene_tree
# ---------------------------------------------------------------------------

class TestGetSceneTree:
    """Tests for get_scene_tree: high-level scene tree retrieval."""

    def test_basic_retrieval(self) -> None:
        """get_scene_tree sends scene:request_scene_tree and parses response."""
        from auto_godot.debugger.inspector import get_scene_tree

        session = MagicMock()
        session.send_command = AsyncMock(return_value=[
            0, "root", "Node", 1, "", 0,
        ])
        root = asyncio.run(get_scene_tree(session))
        session.send_command.assert_called_once_with(
            "scene:request_scene_tree", [],
            response_key="scene:scene_tree",
        )
        assert root.name == "root"
        assert root.path == "/root"

    def test_with_max_depth(self) -> None:
        """get_scene_tree with max_depth prunes children."""
        from auto_godot.debugger.inspector import get_scene_tree

        session = MagicMock()
        session.send_command = AsyncMock(return_value=[
            1, "root", "Node", 1, "", 0,
            0, "Child", "Sprite2D", 2, "", 0,
        ])
        root = asyncio.run(get_scene_tree(session, max_depth=0))
        assert root.children == []

    def test_with_full_calls_enrich(self) -> None:
        """get_scene_tree with full=True calls enrich_scene_tree."""
        from auto_godot.debugger.inspector import get_scene_tree

        session = MagicMock()
        # First call: scene tree request
        # Second call: inspect_objects for enrichment
        session.send_command = AsyncMock(side_effect=[
            [0, "root", "Node", 1, "", 0],
            [1, "Node", []],
        ])
        root = asyncio.run(get_scene_tree(session, full=True))
        assert session.send_command.call_count == 2

    def test_without_full_skips_enrich(self) -> None:
        """get_scene_tree with full=False skips enrichment (default)."""
        from auto_godot.debugger.inspector import get_scene_tree

        session = MagicMock()
        session.send_command = AsyncMock(return_value=[
            0, "root", "Node", 1, "", 0,
        ])
        asyncio.run(get_scene_tree(session, full=False))
        assert session.send_command.call_count == 1


# ---------------------------------------------------------------------------
# get_property
# ---------------------------------------------------------------------------

class TestGetProperty:
    """Tests for get_property: NodePath-to-value resolution."""

    def test_returns_property_value(self) -> None:
        """get_property returns the property value for a matching node and property."""
        from auto_godot.debugger.inspector import get_property

        session = MagicMock()
        # First call: get scene tree
        session.send_command = AsyncMock(side_effect=[
            # scene tree response
            [1, "root", "Node", 1, "", 0,
             0, "Label", "Label", 42, "", 0],
            # inspect_objects response
            [42, "Label", ["text", 4, 0, "", 2, "Hello"]],
        ])
        value = asyncio.run(get_property(session, "/root/Label", "text"))
        assert value == "Hello"

    def test_node_not_found(self) -> None:
        """get_property raises DebuggerError with code DEBUG_NODE_NOT_FOUND."""
        from auto_godot.debugger.inspector import get_property

        session = MagicMock()
        session.send_command = AsyncMock(return_value=[
            0, "root", "Node", 1, "", 0,
        ])
        with pytest.raises(DebuggerError) as exc_info:
            asyncio.run(get_property(session, "/root/NonExistent", "text"))
        assert exc_info.value.code == "DEBUG_NODE_NOT_FOUND"

    def test_property_not_found(self) -> None:
        """get_property raises DebuggerError with code DEBUG_PROPERTY_NOT_FOUND."""
        from auto_godot.debugger.inspector import get_property

        session = MagicMock()
        session.send_command = AsyncMock(side_effect=[
            # scene tree
            [0, "root", "Node", 1, "", 0],
            # inspect_objects with no matching property
            [1, "Node", ["visible", 1, 0, "", 2, True]],
        ])
        with pytest.raises(DebuggerError) as exc_info:
            asyncio.run(get_property(session, "/root", "nonexistent"))
        assert exc_info.value.code == "DEBUG_PROPERTY_NOT_FOUND"


# ---------------------------------------------------------------------------
# _find_node_by_path
# ---------------------------------------------------------------------------

class TestFindNodeByPath:
    """Tests for _find_node_by_path: recursive path lookup."""

    def test_find_root(self) -> None:
        """Find root node by its path."""
        from auto_godot.debugger.inspector import _find_node_by_path

        root = SceneNode(
            name="root", type_name="Node", instance_id=1,
            scene_file_path="", view_flags=0, path="/root",
        )
        assert _find_node_by_path(root, "/root") is root

    def test_find_nested(self) -> None:
        """Find deeply nested node."""
        from auto_godot.debugger.inspector import _find_node_by_path

        player = SceneNode(
            name="Player", type_name="CharacterBody2D", instance_id=3,
            scene_file_path="", view_flags=0, path="/root/Main/Player",
        )
        main = SceneNode(
            name="Main", type_name="Node2D", instance_id=2,
            scene_file_path="", view_flags=0, path="/root/Main",
            children=[player],
        )
        root = SceneNode(
            name="root", type_name="Node", instance_id=1,
            scene_file_path="", view_flags=0, path="/root",
            children=[main],
        )
        assert _find_node_by_path(root, "/root/Main/Player") is player

    def test_not_found_returns_none(self) -> None:
        """Returns None for non-existent path."""
        from auto_godot.debugger.inspector import _find_node_by_path

        root = SceneNode(
            name="root", type_name="Node", instance_id=1,
            scene_file_path="", view_flags=0, path="/root",
        )
        assert _find_node_by_path(root, "/root/NonExistent") is None


# ---------------------------------------------------------------------------
# format_output_messages
# ---------------------------------------------------------------------------

class TestFormatOutputMessages:
    """Tests for format_output_messages: game print() output formatting."""

    def test_basic_output(self) -> None:
        """Formats output messages with type mapping."""
        from auto_godot.debugger.inspector import format_output_messages

        raw = [[["Score: 10", "Level 2"], [0, 0]]]
        result = format_output_messages(raw)
        assert len(result) == 2
        assert result[0] == {"text": "Score: 10", "type": "output"}
        assert result[1] == {"text": "Level 2", "type": "output"}

    def test_error_type(self) -> None:
        """Type 1 maps to 'error'."""
        from auto_godot.debugger.inspector import format_output_messages

        raw = [[["Something failed"], [1]]]
        result = format_output_messages(raw)
        assert result[0]["type"] == "error"

    def test_log_rich_type(self) -> None:
        """Type 2 maps to 'output' (LOG_RICH)."""
        from auto_godot.debugger.inspector import format_output_messages

        raw = [[["Rich text"], [2]]]
        result = format_output_messages(raw)
        assert result[0]["type"] == "output"

    def test_empty_buffer(self) -> None:
        """Empty buffer returns empty list."""
        from auto_godot.debugger.inspector import format_output_messages

        assert format_output_messages([]) == []


# ---------------------------------------------------------------------------
# format_error_messages
# ---------------------------------------------------------------------------

class TestFormatErrorMessages:
    """Tests for format_error_messages: game error formatting."""

    def test_basic_error(self) -> None:
        """Formats error with source location."""
        from auto_godot.debugger.inspector import format_error_messages

        raw = [["NullRef", "Object is null", "main.gd", 42, "_ready", False, 0, 0, 0, 0, ""]]
        result = format_error_messages(raw)
        assert len(result) == 1
        assert result[0]["text"] == "NullRef: Object is null"
        assert result[0]["type"] == "error"
        assert result[0]["source"] == "main.gd:42"

    def test_empty_errors(self) -> None:
        """Empty error buffer returns empty list."""
        from auto_godot.debugger.inspector import format_error_messages

        assert format_error_messages([]) == []
