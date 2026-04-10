"""Tests for .tres parser and serializer with round-trip fidelity."""

import json
from pathlib import Path

import pytest

from auto_godot.formats.tres import (
    ExtResource,
    GdResource,
    SubResource,
    parse_tres,
    serialize_tres,
)
from auto_godot.formats.values import ExtResourceRef, Rect2, SubResourceRef

FIXTURES = Path(__file__).parent.parent / "fixtures"
SAMPLE_TRES = (FIXTURES / "sample.tres").read_text()


# ---------------------------------------------------------------------------
# parse_tres basics
# ---------------------------------------------------------------------------


class TestParseTresBasics:
    """Tests for basic .tres parsing."""

    def test_returns_gd_resource(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        assert isinstance(result, GdResource)

    def test_correct_type(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        assert result.type == "SpriteFrames"

    def test_correct_format(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        assert result.format == 3

    def test_correct_uid(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        assert result.uid == "uid://cecaux1sm7mo0"

    def test_correct_load_steps(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        assert result.load_steps == 3


# ---------------------------------------------------------------------------
# ext_resources
# ---------------------------------------------------------------------------


class TestParseTresExtResources:
    """Tests for ext_resource extraction."""

    def test_ext_resource_count(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        assert len(result.ext_resources) == 1

    def test_ext_resource_fields(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        ext = result.ext_resources[0]
        assert ext.type == "Texture2D"
        assert ext.path == "res://sprites/character.png"
        assert ext.id == "1_sheet"
        assert ext.uid == "uid://dax5h8example"


# ---------------------------------------------------------------------------
# sub_resources
# ---------------------------------------------------------------------------


class TestParseTresSubResources:
    """Tests for sub_resource extraction."""

    def test_sub_resource_count(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        assert len(result.sub_resources) == 2

    def test_sub_resource_fields(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        sub = result.sub_resources[0]
        assert sub.type == "AtlasTexture"
        assert sub.id == "AtlasTexture_abc12"
        assert "atlas" in sub.properties
        assert "region" in sub.properties

    def test_sub_resource_values(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        sub = result.sub_resources[0]
        assert isinstance(sub.properties["atlas"], ExtResourceRef)
        assert sub.properties["atlas"].id == "1_sheet"
        assert isinstance(sub.properties["region"], Rect2)
        assert sub.properties["region"].x == 0
        assert sub.properties["region"].w == 32


# ---------------------------------------------------------------------------
# [resource] section
# ---------------------------------------------------------------------------


class TestParseTresResourceSection:
    """Tests for the [resource] section properties."""

    def test_resource_properties_exist(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        assert "animations" in result.resource_properties

    def test_animations_is_list(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        anims = result.resource_properties["animations"]
        assert isinstance(anims, list)


# ---------------------------------------------------------------------------
# Round-trip fidelity
# ---------------------------------------------------------------------------


class TestTresRoundTrip:
    """Tests for serialize_tres(parse_tres(text)) == text."""

    def test_round_trip_sample(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        serialized = serialize_tres(result)
        assert serialized == SAMPLE_TRES

    def test_round_trip_with_comments(self) -> None:
        text = (
            '[gd_resource type="Test" format=3]\n'
            "\n"
            "; This is a comment\n"
            "[resource]\n"
            "value = 42\n"
        )
        result = parse_tres(text)
        serialized = serialize_tres(result)
        assert serialized == text

    def test_round_trip_with_blank_lines(self) -> None:
        text = (
            '[gd_resource type="Test" format=3]\n'
            "\n"
            '[ext_resource type="Texture2D" path="res://a.png" id="1_a"]\n'
            "\n"
            "[resource]\n"
            "data = 1\n"
        )
        result = parse_tres(text)
        serialized = serialize_tres(result)
        assert serialized == text

    def test_round_trip_multiline_array(self) -> None:
        text = (
            '[gd_resource type="Test" format=3]\n'
            "\n"
            "[resource]\n"
            "arr = [{\n"
            '"key": 1\n'
            "}]\n"
        )
        result = parse_tres(text)
        serialized = serialize_tres(result)
        assert serialized == text


# ---------------------------------------------------------------------------
# Unknown sections (D-04 lenient)
# ---------------------------------------------------------------------------


class TestTresUnknownSections:
    """Tests for unknown section types preserved as raw."""

    def test_unknown_section_preserved(self) -> None:
        text = (
            '[gd_resource type="Test" format=3]\n'
            "\n"
            "[custom_section]\n"
            "x = 10\n"
        )
        result = parse_tres(text)
        serialized = serialize_tres(result)
        assert serialized == text


# ---------------------------------------------------------------------------
# Missing load_steps (Godot 4.6)
# ---------------------------------------------------------------------------


class TestTresMissingLoadSteps:
    """Tests for handling missing load_steps attribute."""

    def test_parse_without_load_steps(self) -> None:
        text = '[gd_resource type="Test" format=3]\n\n[resource]\nvalue = 1\n'
        result = parse_tres(text)
        assert result.load_steps is None
        assert result.type == "Test"


# ---------------------------------------------------------------------------
# to_dict() for JSON serialization
# ---------------------------------------------------------------------------


class TestTresToDict:
    """Tests for GdResource.to_dict()."""

    def test_to_dict_returns_dict(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        d = result.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_json_serializable(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        d = result.to_dict()
        # Should not raise
        json_str = json.dumps(d, default=str)
        assert isinstance(json_str, str)

    def test_to_dict_has_type(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        d = result.to_dict()
        assert d["type"] == "SpriteFrames"

    def test_to_dict_has_ext_resources(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        d = result.to_dict()
        assert "ext_resources" in d
        assert len(d["ext_resources"]) == 1

    def test_to_dict_has_sub_resources(self) -> None:
        result = parse_tres(SAMPLE_TRES)
        d = result.to_dict()
        assert "sub_resources" in d
        assert len(d["sub_resources"]) == 2
