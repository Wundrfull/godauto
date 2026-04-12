"""Tests for .tscn parser and serializer with round-trip fidelity."""

import json
from pathlib import Path

import pytest

from auto_godot.formats.tscn import (
    Connection,
    GdScene,
    SceneNode,
    parse_tscn,
    serialize_tscn,
)
from auto_godot.formats.tres import ExtResource
from auto_godot.formats.values import ExtResourceRef, Vector2

FIXTURES = Path(__file__).parent.parent / "fixtures"
SAMPLE_TSCN = (FIXTURES / "sample.tscn").read_text()


# ---------------------------------------------------------------------------
# parse_tscn basics
# ---------------------------------------------------------------------------


class TestParseTscnBasics:
    """Tests for basic .tscn parsing."""

    def test_returns_gd_scene(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        assert isinstance(result, GdScene)

    def test_correct_format(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        assert result.format == 3

    def test_correct_uid(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        assert result.uid == "uid://btk3example123"

    def test_correct_load_steps(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        assert result.load_steps == 2


# ---------------------------------------------------------------------------
# ext_resources
# ---------------------------------------------------------------------------


class TestParseTscnExtResources:
    """Tests for ext_resource extraction in .tscn."""

    def test_ext_resource_count(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        assert len(result.ext_resources) == 1

    def test_ext_resource_fields(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        ext = result.ext_resources[0]
        assert ext.type == "Script"
        assert ext.path == "res://scripts/player.gd"
        assert ext.id == "1_script"
        assert ext.uid == "uid://c7gn4example"


# ---------------------------------------------------------------------------
# nodes
# ---------------------------------------------------------------------------


class TestParseTscnNodes:
    """Tests for node extraction."""

    def test_node_count(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        assert len(result.nodes) == 3

    def test_root_node(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        root = result.nodes[0]
        assert root.name == "Player"
        assert root.type == "CharacterBody2D"
        assert root.parent is None

    def test_child_node_with_properties(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        sprite = result.nodes[1]
        assert sprite.name == "Sprite"
        assert sprite.type == "Sprite2D"
        assert sprite.parent == "."
        assert "position" in sprite.properties

    def test_child_node_no_properties(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        collision = result.nodes[2]
        assert collision.name == "CollisionShape"
        assert collision.type == "CollisionShape2D"
        assert collision.parent == "."

    def test_node_property_values(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        root = result.nodes[0]
        assert isinstance(root.properties["script"], ExtResourceRef)
        sprite = result.nodes[1]
        assert isinstance(sprite.properties["position"], Vector2)


# ---------------------------------------------------------------------------
# connections
# ---------------------------------------------------------------------------


class TestParseTscnConnections:
    """Tests for connection extraction."""

    def test_connection_count(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        assert len(result.connections) == 1

    def test_connection_fields(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        conn = result.connections[0]
        assert conn.signal == "body_entered"
        assert conn.from_node == "."
        assert conn.to_node == "."
        assert conn.method == "_on_body_entered"

    def test_binds_populated(self) -> None:
        # binds carry bound argument values into signal handlers.
        # Previously the field existed on Connection but _extract_connection
        # never populated it, so any model rebuild lost the binding values.
        text = (
            '[gd_scene format=3]\n\n'
            '[node name="Main" type="Control"]\n\n'
            '[connection signal="pressed" from="." to="." '
            'method="_on_pressed" binds=[1, 2]]\n'
        )
        scene = parse_tscn(text)
        assert scene.connections[0].binds == [1, 2]

    def test_unbinds_populated(self) -> None:
        text = (
            '[gd_scene format=3]\n\n'
            '[node name="Main" type="Control"]\n\n'
            '[connection signal="pressed" from="." to="." '
            'method="_on_pressed" unbinds=2]\n'
        )
        scene = parse_tscn(text)
        assert scene.connections[0].unbinds == 2

    def test_binds_and_unbinds_round_trip(self) -> None:
        source = (
            '[gd_scene format=3]\n\n'
            '[node name="Main" type="Control"]\n\n'
            '[connection signal="pressed" from="." to="." '
            'method="_on_pressed" binds=[1, 2] unbinds=1]\n'
        )
        rebuilt = serialize_tscn(parse_tscn(source))
        assert "binds=[1, 2]" in rebuilt
        assert "unbinds=1" in rebuilt

    def test_no_binds_no_emit(self) -> None:
        # Connections without binds or unbinds must not emit the attribute.
        text = (
            '[gd_scene format=3]\n\n'
            '[node name="Main" type="Control"]\n\n'
            '[connection signal="pressed" from="." to="." '
            'method="_on_pressed"]\n'
        )
        rebuilt = serialize_tscn(parse_tscn(text))
        assert "binds=" not in rebuilt
        assert "unbinds=" not in rebuilt

    def test_binds_unbinds_survive_model_rebuild(self) -> None:
        # Most CLI commands null raw_header/raw_sections to force
        # serialize_tscn through _build_tscn_from_model. That path is
        # the actual data-loss surface -- exercise it explicitly.
        source = (
            '[gd_scene format=3]\n\n'
            '[node name="Main" type="Control"]\n\n'
            '[connection signal="pressed" from="." to="." '
            'method="_on_pressed" binds=[1, 2] unbinds=1]\n'
        )
        scene = parse_tscn(source)
        scene._raw_header = None
        scene._raw_sections = None
        rebuilt = serialize_tscn(scene)
        assert "binds=[1, 2]" in rebuilt
        assert "unbinds=1" in rebuilt

    def test_unbinds_malformed_drops_to_none(self) -> None:
        # A hand-edited scene with a non-integer unbinds= must not
        # crash the parse -- fall through to None.
        text = (
            '[gd_scene format=3]\n\n'
            '[node name="Main" type="Control"]\n\n'
            '[connection signal="pressed" from="." to="." '
            'method="_on_pressed" unbinds=x]\n'
        )
        scene = parse_tscn(text)
        assert scene.connections[0].unbinds is None

    def test_nested_binds_truncated_dropped_not_garbled(self) -> None:
        # The header-attr regex _ATTR_ARRAY_RE stops at the first ']',
        # so binds=[[1,2],[3]] arrives truncated as '[[1,2]'. Without
        # a balance check, parse_value returns a list containing the
        # partial string '[1,2'. Guard with _count_bracket_depth so
        # truncations drop to None rather than land as model garbage.
        text = (
            '[gd_scene format=3]\n\n'
            '[node name="Main" type="Control"]\n\n'
            '[connection signal="pressed" from="." to="." '
            'method="_on_pressed" binds=[[1,2],[3]]]\n'
        )
        scene = parse_tscn(text)
        assert scene.connections[0].binds is None


# ---------------------------------------------------------------------------
# Round-trip fidelity
# ---------------------------------------------------------------------------


class TestTscnRoundTrip:
    """Tests for serialize_tscn(parse_tscn(text)) == text."""

    def test_round_trip_sample(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        serialized = serialize_tscn(result)
        assert serialized == SAMPLE_TSCN

    def test_round_trip_with_comments(self) -> None:
        text = (
            '[gd_scene load_steps=1 format=3]\n'
            "\n"
            "; Root node\n"
            '[node name="Root" type="Node2D"]\n'
        )
        result = parse_tscn(text)
        serialized = serialize_tscn(result)
        assert serialized == text

    def test_round_trip_with_blank_lines(self) -> None:
        text = (
            '[gd_scene format=3]\n'
            "\n"
            '[node name="Root" type="Node2D"]\n'
            "\n"
            '[node name="Child" type="Sprite2D" parent="."]\n'
        )
        result = parse_tscn(text)
        serialized = serialize_tscn(result)
        assert serialized == text


# ---------------------------------------------------------------------------
# Unknown sections (D-04 lenient)
# ---------------------------------------------------------------------------


class TestTscnUnknownSections:
    """Tests for unknown section types preserved as raw."""

    def test_unknown_section_preserved(self) -> None:
        text = (
            '[gd_scene format=3]\n'
            "\n"
            '[node name="Root" type="Node2D"]\n'
            "\n"
            "[editable path=\"Sprite\"]\n"
        )
        result = parse_tscn(text)
        serialized = serialize_tscn(result)
        assert serialized == text


# ---------------------------------------------------------------------------
# Missing load_steps (Godot 4.6)
# ---------------------------------------------------------------------------


class TestTscnMissingLoadSteps:
    """Tests for handling missing load_steps attribute."""

    def test_parse_without_load_steps(self) -> None:
        text = '[gd_scene format=3]\n\n[node name="Root" type="Node2D"]\n'
        result = parse_tscn(text)
        assert result.load_steps is None


# ---------------------------------------------------------------------------
# sub_resources in .tscn
# ---------------------------------------------------------------------------


class TestTscnSubResources:
    """Tests for sub_resource extraction in .tscn."""

    def test_sub_resource_in_scene(self) -> None:
        text = (
            '[gd_scene load_steps=2 format=3]\n'
            "\n"
            '[sub_resource type="CircleShape2D" id="CircleShape2D_abc12"]\n'
            "radius = 10.0\n"
            "\n"
            '[node name="Root" type="Node2D"]\n'
        )
        result = parse_tscn(text)
        assert len(result.sub_resources) == 1
        assert result.sub_resources[0].type == "CircleShape2D"
        assert result.sub_resources[0].id == "CircleShape2D_abc12"


# ---------------------------------------------------------------------------
# to_dict() for JSON serialization
# ---------------------------------------------------------------------------


class TestTscnToDict:
    """Tests for GdScene.to_dict()."""

    def test_to_dict_returns_dict(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        d = result.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_json_serializable(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        d = result.to_dict()
        json_str = json.dumps(d, default=str)
        assert isinstance(json_str, str)

    def test_to_dict_has_nodes(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        d = result.to_dict()
        assert "nodes" in d
        assert len(d["nodes"]) == 3

    def test_to_dict_has_connections(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        d = result.to_dict()
        assert "connections" in d
        assert len(d["connections"]) == 1

    def test_to_dict_node_structure(self) -> None:
        result = parse_tscn(SAMPLE_TSCN)
        d = result.to_dict()
        root_node = d["nodes"][0]
        assert root_node["name"] == "Player"
        assert root_node["type"] == "CharacterBody2D"
