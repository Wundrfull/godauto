"""Tests for scene builder: JSON definition to GdScene conversion."""

from __future__ import annotations

import pytest

from gdauto.errors import ValidationError
from gdauto.formats.tscn import GdScene, SceneNode, serialize_tscn
from gdauto.formats.values import ExtResourceRef, Vector2
from gdauto.scene.builder import build_scene


class TestBuildSceneMinimal:
    """Tests for minimal root-only scene definitions."""

    def test_root_only_returns_gd_scene(self) -> None:
        definition = {"root": {"name": "Root", "type": "Node2D"}}
        result = build_scene(definition)
        assert isinstance(result, GdScene)

    def test_root_only_single_node(self) -> None:
        definition = {"root": {"name": "Root", "type": "Node2D"}}
        result = build_scene(definition)
        assert len(result.nodes) == 1

    def test_root_node_parent_is_none(self) -> None:
        definition = {"root": {"name": "Root", "type": "Node2D"}}
        result = build_scene(definition)
        assert result.nodes[0].parent is None

    def test_root_node_type(self) -> None:
        definition = {"root": {"name": "Root", "type": "Node2D"}}
        result = build_scene(definition)
        assert result.nodes[0].type == "Node2D"


class TestBuildSceneNesting:
    """Tests for nested node hierarchy and parent path computation."""

    def test_direct_children_parent_is_dot(self) -> None:
        definition = {
            "root": {
                "name": "Root",
                "type": "Node2D",
                "children": [
                    {"name": "Child", "type": "Sprite2D"},
                ],
            },
        }
        result = build_scene(definition)
        child = [n for n in result.nodes if n.name == "Child"][0]
        assert child.parent == "."

    def test_grandchild_parent_is_child_name(self) -> None:
        definition = {
            "root": {
                "name": "Root",
                "type": "Node2D",
                "children": [
                    {
                        "name": "ChildName",
                        "type": "Node2D",
                        "children": [
                            {"name": "Grandchild", "type": "Sprite2D"},
                        ],
                    },
                ],
            },
        }
        result = build_scene(definition)
        grandchild = [n for n in result.nodes if n.name == "Grandchild"][0]
        assert grandchild.parent == "ChildName"

    def test_three_level_nesting_parent_paths(self) -> None:
        definition = {
            "root": {
                "name": "Root",
                "type": "Node2D",
                "children": [
                    {
                        "name": "A",
                        "type": "Node2D",
                        "children": [
                            {
                                "name": "B",
                                "type": "Node2D",
                                "children": [
                                    {"name": "C", "type": "Sprite2D"},
                                ],
                            },
                        ],
                    },
                ],
            },
        }
        result = build_scene(definition)
        a_node = [n for n in result.nodes if n.name == "A"][0]
        b_node = [n for n in result.nodes if n.name == "B"][0]
        c_node = [n for n in result.nodes if n.name == "C"][0]
        assert a_node.parent == "."
        assert b_node.parent == "A"
        assert c_node.parent == "A/B"


class TestBuildSceneProperties:
    """Tests for property passthrough via parse_value."""

    def test_properties_parsed_to_godot_types(self) -> None:
        definition = {
            "root": {
                "name": "Root",
                "type": "Node2D",
                "properties": {"position": "Vector2(100, 200)"},
            },
        }
        result = build_scene(definition)
        pos = result.nodes[0].properties["position"]
        assert isinstance(pos, Vector2)
        assert pos.x == 100.0
        assert pos.y == 200.0


class TestBuildSceneResources:
    """Tests for external resource creation and assignment."""

    def test_resources_create_ext_resources(self) -> None:
        definition = {
            "root": {"name": "Root", "type": "Node2D"},
            "resources": [
                {
                    "type": "Script",
                    "path": "res://test.gd",
                    "assign_to": "Root",
                    "property": "script",
                },
            ],
        }
        result = build_scene(definition)
        assert len(result.ext_resources) == 1
        assert result.ext_resources[0].type == "Script"
        assert result.ext_resources[0].path == "res://test.gd"

    def test_resource_assigned_to_target_node(self) -> None:
        definition = {
            "root": {"name": "Root", "type": "Node2D"},
            "resources": [
                {
                    "type": "Script",
                    "path": "res://test.gd",
                    "assign_to": "Root",
                    "property": "script",
                },
            ],
        }
        result = build_scene(definition)
        root = result.nodes[0]
        assert "script" in root.properties
        assert isinstance(root.properties["script"], ExtResourceRef)

    def test_multiple_resources_load_steps_omitted(self) -> None:
        definition = {
            "root": {"name": "Root", "type": "Node2D"},
            "resources": [
                {
                    "type": "Script",
                    "path": "res://test.gd",
                    "assign_to": "Root",
                    "property": "script",
                },
                {
                    "type": "Texture2D",
                    "path": "res://icon.png",
                    "assign_to": "Root",
                    "property": "texture",
                },
            ],
        }
        result = build_scene(definition)
        assert result.load_steps is None


class TestBuildSceneUidAndSerialization:
    """Tests for UID generation and serialization output."""

    def test_uid_starts_with_uid_prefix(self) -> None:
        definition = {"root": {"name": "Root", "type": "Node2D"}}
        result = build_scene(definition)
        assert result.uid is not None
        assert result.uid.startswith("uid://")

    def test_serialize_produces_valid_tscn(self) -> None:
        definition = {"root": {"name": "Root", "type": "Node2D"}}
        result = build_scene(definition)
        text = serialize_tscn(result)
        assert "[gd_scene" in text
        assert '[node name="Root"' in text


class TestBuildSceneEdgeCases:
    """Tests for edge cases and validation."""

    def test_empty_children_produces_root_only(self) -> None:
        definition = {
            "root": {
                "name": "Root",
                "type": "Node2D",
                "children": [],
            },
        }
        result = build_scene(definition)
        assert len(result.nodes) == 1

    def test_missing_root_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            build_scene({"other": {}})
        assert exc_info.value.code == "INVALID_SCENE_DEFINITION"

    def test_root_missing_name_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            build_scene({"root": {"type": "Node2D"}})
        assert exc_info.value.code == "INVALID_SCENE_DEFINITION"

    def test_root_missing_type_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            build_scene({"root": {"name": "Root"}})
        assert exc_info.value.code == "INVALID_SCENE_DEFINITION"
