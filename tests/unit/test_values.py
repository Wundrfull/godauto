"""Tests for Godot value type dataclasses, parsing, and serialization."""

from __future__ import annotations

import json
import math

import pytest

from auto_godot.formats.values import (
    AABB,
    Color,
    ExtResourceRef,
    GodotJSONEncoder,
    NodePath,
    Rect2,
    Rect2i,
    StringName,
    SubResourceRef,
    Transform2D,
    Transform3D,
    Vector2,
    Vector2i,
    Vector3,
    Vector3i,
    parse_value,
    serialize_value,
)


class TestVector2:
    """Test Vector2 dataclass and arithmetic operations."""

    def test_add(self) -> None:
        result = Vector2(1.0, 2.0) + Vector2(3.0, 4.0)
        assert result == Vector2(4.0, 6.0)

    def test_sub(self) -> None:
        result = Vector2(1.0, 2.0) - Vector2(0.5, 0.5)
        assert result == Vector2(0.5, 1.5)

    def test_mul_scalar(self) -> None:
        result = Vector2(3.0, 4.0) * 2.0
        assert result == Vector2(6.0, 8.0)

    def test_rmul_scalar(self) -> None:
        result = 2.0 * Vector2(3.0, 4.0)
        assert result == Vector2(6.0, 8.0)

    def test_dot(self) -> None:
        assert Vector2(3.0, 4.0).dot(Vector2(1.0, 0.0)) == 3.0

    def test_length(self) -> None:
        assert Vector2(3.0, 4.0).length() == 5.0

    def test_normalized(self) -> None:
        n = Vector2(3.0, 4.0).normalized()
        assert math.isclose(n.x, 0.6, rel_tol=1e-9)
        assert math.isclose(n.y, 0.8, rel_tol=1e-9)

    def test_to_godot_whole_numbers(self) -> None:
        assert Vector2(0.0, 0.0).to_godot() == "Vector2(0, 0)"

    def test_to_godot_fractional(self) -> None:
        assert Vector2(1.5, 2.0).to_godot() == "Vector2(1.5, 2)"

    def test_frozen(self) -> None:
        v = Vector2(1.0, 2.0)
        with pytest.raises(AttributeError):
            v.x = 5.0  # type: ignore[misc]

    def test_equality(self) -> None:
        assert Vector2(1.0, 2.0) == Vector2(1.0, 2.0)
        assert Vector2(1.0, 2.0) != Vector2(1.0, 3.0)


class TestVector2i:
    """Test Vector2i dataclass and arithmetic operations."""

    def test_add(self) -> None:
        result = Vector2i(1, 2) + Vector2i(3, 4)
        assert result == Vector2i(4, 6)

    def test_sub(self) -> None:
        result = Vector2i(5, 7) - Vector2i(1, 2)
        assert result == Vector2i(4, 5)

    def test_mul_scalar(self) -> None:
        result = Vector2i(3, 4) * 2
        assert result == Vector2i(6, 8)

    def test_to_godot(self) -> None:
        assert Vector2i(1, 2).to_godot() == "Vector2i(1, 2)"


class TestVector3:
    """Test Vector3 dataclass and arithmetic operations."""

    def test_add(self) -> None:
        result = Vector3(1.0, 2.0, 3.0) + Vector3(4.0, 5.0, 6.0)
        assert result == Vector3(5.0, 7.0, 9.0)

    def test_sub(self) -> None:
        result = Vector3(5.0, 7.0, 9.0) - Vector3(1.0, 2.0, 3.0)
        assert result == Vector3(4.0, 5.0, 6.0)

    def test_mul_scalar(self) -> None:
        result = Vector3(1.0, 2.0, 3.0) * 2.0
        assert result == Vector3(2.0, 4.0, 6.0)

    def test_dot(self) -> None:
        assert Vector3(1.0, 0.0, 0.0).dot(Vector3(0.0, 1.0, 0.0)) == 0.0

    def test_cross(self) -> None:
        result = Vector3(1.0, 0.0, 0.0).cross(Vector3(0.0, 1.0, 0.0))
        assert result == Vector3(0.0, 0.0, 1.0)

    def test_length(self) -> None:
        assert Vector3(0.0, 3.0, 4.0).length() == 5.0

    def test_to_godot(self) -> None:
        assert Vector3(1.0, 2.0, 3.0).to_godot() == "Vector3(1, 2, 3)"


class TestVector3i:
    """Test Vector3i dataclass."""

    def test_add(self) -> None:
        result = Vector3i(1, 2, 3) + Vector3i(4, 5, 6)
        assert result == Vector3i(5, 7, 9)

    def test_to_godot(self) -> None:
        assert Vector3i(1, 2, 3).to_godot() == "Vector3i(1, 2, 3)"


class TestRect2:
    """Test Rect2 dataclass with contains and intersection."""

    def test_contains_inside(self) -> None:
        assert Rect2(0.0, 0.0, 10.0, 10.0).contains(Vector2(5.0, 5.0)) is True

    def test_contains_outside(self) -> None:
        assert Rect2(0.0, 0.0, 10.0, 10.0).contains(Vector2(15.0, 5.0)) is False

    def test_contains_edge(self) -> None:
        # Point on the boundary is inside
        assert Rect2(0.0, 0.0, 10.0, 10.0).contains(Vector2(0.0, 0.0)) is True

    def test_intersection_overlap(self) -> None:
        result = Rect2(0.0, 0.0, 10.0, 10.0).intersection(Rect2(5.0, 5.0, 10.0, 10.0))
        assert result == Rect2(5.0, 5.0, 5.0, 5.0)

    def test_intersection_no_overlap(self) -> None:
        result = Rect2(0.0, 0.0, 10.0, 10.0).intersection(Rect2(20.0, 20.0, 5.0, 5.0))
        assert result is None

    def test_size_property(self) -> None:
        r = Rect2(10.0, 20.0, 30.0, 40.0)
        assert r.size == Vector2(30.0, 40.0)

    def test_position_property(self) -> None:
        r = Rect2(10.0, 20.0, 30.0, 40.0)
        assert r.position == Vector2(10.0, 20.0)

    def test_to_godot(self) -> None:
        assert Rect2(0.0, 0.0, 32.0, 32.0).to_godot() == "Rect2(0, 0, 32, 32)"


class TestRect2i:
    """Test Rect2i dataclass."""

    def test_to_godot(self) -> None:
        assert Rect2i(0, 0, 32, 32).to_godot() == "Rect2i(0, 0, 32, 32)"

    def test_contains(self) -> None:
        assert Rect2i(0, 0, 10, 10).contains(Vector2i(5, 5)) is True
        assert Rect2i(0, 0, 10, 10).contains(Vector2i(15, 5)) is False


class TestColor:
    """Test Color dataclass."""

    def test_fields(self) -> None:
        c = Color(1.0, 0.5, 0.0, 1.0)
        assert c.r == 1.0
        assert c.g == 0.5
        assert c.b == 0.0
        assert c.a == 1.0

    def test_default_alpha(self) -> None:
        c = Color(1.0, 0.5, 0.0)
        assert c.a == 1.0

    def test_to_godot(self) -> None:
        assert Color(1.0, 0.5, 0.0, 1.0).to_godot() == "Color(1, 0.5, 0, 1)"


class TestTransform2D:
    """Test Transform2D dataclass."""

    def test_identity(self) -> None:
        t = Transform2D(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        assert t.xx == 1.0
        assert t.xy == 0.0
        assert t.yx == 0.0
        assert t.yy == 1.0
        assert t.ox == 0.0
        assert t.oy == 0.0

    def test_to_godot(self) -> None:
        t = Transform2D(1.0, 0.0, 0.0, 1.0, 100.0, 200.0)
        assert t.to_godot() == "Transform2D(1, 0, 0, 1, 100, 200)"


class TestTransform3D:
    """Test Transform3D dataclass."""

    def test_to_godot(self) -> None:
        t = Transform3D(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
        assert t.to_godot() == "Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)"


class TestAABB:
    """Test AABB dataclass."""

    def test_to_godot(self) -> None:
        a = AABB(0.0, 0.0, 0.0, 1.0, 1.0, 1.0)
        assert a.to_godot() == "AABB(0, 0, 0, 1, 1, 1)"


class TestStringName:
    """Test StringName dataclass."""

    def test_value(self) -> None:
        assert StringName("idle").value == "idle"

    def test_to_godot(self) -> None:
        assert StringName("idle").to_godot() == '&"idle"'


class TestNodePath:
    """Test NodePath dataclass."""

    def test_path(self) -> None:
        assert NodePath("Path/To/Node").path == "Path/To/Node"

    def test_to_godot(self) -> None:
        assert NodePath("Path/To/Node").to_godot() == 'NodePath("Path/To/Node")'


class TestExtResourceRef:
    """Test ExtResourceRef dataclass."""

    def test_to_godot(self) -> None:
        ref = ExtResourceRef("1_sheet")
        assert ref.to_godot() == 'ExtResource("1_sheet")'


class TestSubResourceRef:
    """Test SubResourceRef dataclass."""

    def test_to_godot(self) -> None:
        ref = SubResourceRef("AtlasTexture_abc12")
        assert ref.to_godot() == 'SubResource("AtlasTexture_abc12")'


class TestParseValue:
    """Test the parse_value function for all Godot value types."""

    def test_vector2(self) -> None:
        assert parse_value("Vector2(1.5, 2.0)") == Vector2(1.5, 2.0)

    def test_vector2i(self) -> None:
        assert parse_value("Vector2i(1, 2)") == Vector2i(1, 2)

    def test_vector3(self) -> None:
        assert parse_value("Vector3(1.0, 2.0, 3.0)") == Vector3(1.0, 2.0, 3.0)

    def test_vector3i(self) -> None:
        assert parse_value("Vector3i(1, 2, 3)") == Vector3i(1, 2, 3)

    def test_rect2(self) -> None:
        assert parse_value("Rect2(0, 0, 32, 32)") == Rect2(0.0, 0.0, 32.0, 32.0)

    def test_rect2i(self) -> None:
        assert parse_value("Rect2i(0, 0, 32, 32)") == Rect2i(0, 0, 32, 32)

    def test_color(self) -> None:
        assert parse_value("Color(1, 0.5, 0, 1)") == Color(1.0, 0.5, 0.0, 1.0)

    def test_transform2d(self) -> None:
        result = parse_value("Transform2D(1, 0, 0, 1, 100, 200)")
        assert result == Transform2D(1.0, 0.0, 0.0, 1.0, 100.0, 200.0)

    def test_transform3d(self) -> None:
        result = parse_value("Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)")
        assert result == Transform3D(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)

    def test_aabb(self) -> None:
        result = parse_value("AABB(0, 0, 0, 1, 1, 1)")
        assert result == AABB(0.0, 0.0, 0.0, 1.0, 1.0, 1.0)

    def test_string_name(self) -> None:
        assert parse_value('&"idle"') == StringName("idle")

    def test_node_path(self) -> None:
        assert parse_value('NodePath("Path/To/Node")') == NodePath("Path/To/Node")

    def test_ext_resource(self) -> None:
        assert parse_value('ExtResource("1_sheet")') == ExtResourceRef("1_sheet")

    def test_sub_resource(self) -> None:
        result = parse_value('SubResource("AtlasTexture_abc12")')
        assert result == SubResourceRef("AtlasTexture_abc12")

    def test_null(self) -> None:
        assert parse_value("null") is None

    def test_true(self) -> None:
        assert parse_value("true") is True

    def test_false(self) -> None:
        assert parse_value("false") is False

    def test_integer(self) -> None:
        assert parse_value("42") == 42
        assert isinstance(parse_value("42"), int)

    def test_negative_integer(self) -> None:
        assert parse_value("-7") == -7

    def test_float(self) -> None:
        result = parse_value("3.14")
        assert result == 3.14
        assert isinstance(result, float)

    def test_negative_float(self) -> None:
        assert parse_value("-1.5") == -1.5

    def test_float_scientific(self) -> None:
        assert parse_value("1e-05") == 1e-05

    def test_string(self) -> None:
        assert parse_value('"hello"') == "hello"

    def test_string_with_escaped_quotes(self) -> None:
        assert parse_value(r'"say \"hi\""') == 'say "hi"'

    def test_string_escape_newline(self) -> None:
        assert parse_value(r'"line1\nline2"') == "line1\nline2"

    def test_string_escape_carriage_return(self) -> None:
        assert parse_value(r'"a\rb"') == "a\rb"

    def test_string_escape_tab(self) -> None:
        assert parse_value(r'"a\tb"') == "a\tb"

    def test_string_escape_backspace(self) -> None:
        assert parse_value(r'"a\bb"') == "a\bb"

    def test_string_escape_formfeed(self) -> None:
        assert parse_value(r'"a\fb"') == "a\fb"

    def test_string_escape_backslash(self) -> None:
        assert parse_value(r'"a\\b"') == "a\\b"

    def test_string_unicode_bmp(self) -> None:
        assert parse_value(r'"caf\u00e9"') == "café"

    def test_string_unicode_emoji_via_surrogate(self) -> None:
        # BMP code for a music sheet section symbol
        assert parse_value(r'"\u00a7"') == "§"

    def test_string_unicode_surrogate_pair(self) -> None:
        # U+1F600 emitted by Godot as UTF-16 pair D83D + DE00.
        # Decoded independently that gives two lone surrogates; must
        # combine into the astral code point.
        assert parse_value(r'"\uD83D\uDE00"') == "\U0001F600"

    def test_string_unicode_lone_high_surrogate(self) -> None:
        # Lone high surrogate is invalid Unicode; fall through to
        # literal passthrough so it round-trips unchanged.
        assert parse_value(r'"\uD800"') == r"\uD800"

    def test_string_unicode_lone_low_surrogate(self) -> None:
        assert parse_value(r'"\uDC00"') == r"\uDC00"

    def test_string_unicode_U_6digit(self) -> None:
        # Extended 6-hex form: U+1F600 (grinning face)
        assert parse_value(r'"\U01F600"') == "\U0001F600"

    def test_string_unknown_escape_preserved(self) -> None:
        # D-04: unknown escapes pass through as backslash + char
        assert parse_value(r'"a\xb"') == r"a\xb"

    def test_string_serialize_escapes_newline(self) -> None:
        # Raw newline in property value corrupts .tscn line-based format
        assert serialize_value("a\nb") == r'"a\nb"'

    def test_string_serialize_escapes_tab_and_cr(self) -> None:
        assert serialize_value("a\tb\rc") == r'"a\tb\rc"'

    def test_string_serialize_escapes_backslash_first(self) -> None:
        # Must escape backslash BEFORE adding its own escapes or we double
        assert serialize_value("a\\nb") == r'"a\\nb"'

    def test_string_round_trip_multiline(self) -> None:
        original = "line1\nline2\tindented\r\n"
        assert parse_value(serialize_value(original)) == original

    def test_string_round_trip_unicode(self) -> None:
        original = "héllo 世界"
        # No forced unicode escape on emit — UTF-8 direct is fine in Godot
        assert parse_value(serialize_value(original)) == original

    def test_string_round_trip_quotes_and_backslash(self) -> None:
        original = 'say "hi" \\ back'
        assert parse_value(serialize_value(original)) == original

    def test_packed_string_array(self) -> None:
        result = parse_value('PackedStringArray("a", "b", "c")')
        assert result == ["a", "b", "c"]

    def test_packed_string_array_empty(self) -> None:
        result = parse_value("PackedStringArray()")
        assert result == []

    def test_packed_float32_array(self) -> None:
        result = parse_value("PackedFloat32Array(0.0, 1.0, 2.0)")
        assert result == [0.0, 1.0, 2.0]

    def test_packed_int32_array(self) -> None:
        result = parse_value("PackedInt32Array(0, 1, 2)")
        assert result == [0, 1, 2]

    def test_packed_byte_array(self) -> None:
        result = parse_value("PackedByteArray(0, 255, 128)")
        assert result == bytes([0, 255, 128])

    def test_unknown_constructor_returns_raw(self) -> None:
        """Per D-04, unknown constructors return the raw string."""
        result = parse_value("SomeUnknown(1, 2, 3)")
        assert result == "SomeUnknown(1, 2, 3)"

    def test_array_literal(self) -> None:
        result = parse_value("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_empty_array(self) -> None:
        result = parse_value("[]")
        assert result == []

    def test_dictionary_literal(self) -> None:
        result = parse_value('{"key": "value"}')
        assert result == {"key": "value"}

    def test_empty_dictionary(self) -> None:
        result = parse_value("{}")
        assert result == {}

    def test_vector2_no_spaces(self) -> None:
        """Godot sometimes omits spaces after commas."""
        assert parse_value("Vector2(1.5,2.0)") == Vector2(1.5, 2.0)


class TestSerializeValue:
    """Test the serialize_value function."""

    def test_vector2(self) -> None:
        assert serialize_value(Vector2(1.5, 2.0)) == "Vector2(1.5, 2)"

    def test_rect2(self) -> None:
        assert serialize_value(Rect2(0.0, 0.0, 32.0, 32.0)) == "Rect2(0, 0, 32, 32)"

    def test_color(self) -> None:
        assert serialize_value(Color(1.0, 0.5, 0.0, 1.0)) == "Color(1, 0.5, 0, 1)"

    def test_string_name(self) -> None:
        assert serialize_value(StringName("idle")) == '&"idle"'

    def test_node_path(self) -> None:
        assert serialize_value(NodePath("Path/To/Node")) == 'NodePath("Path/To/Node")'

    def test_ext_resource(self) -> None:
        assert serialize_value(ExtResourceRef("1_sheet")) == 'ExtResource("1_sheet")'

    def test_sub_resource(self) -> None:
        result = serialize_value(SubResourceRef("AtlasTexture_abc12"))
        assert result == 'SubResource("AtlasTexture_abc12")'

    def test_none(self) -> None:
        assert serialize_value(None) == "null"

    def test_true(self) -> None:
        assert serialize_value(True) == "true"

    def test_false(self) -> None:
        assert serialize_value(False) == "false"

    def test_int(self) -> None:
        assert serialize_value(42) == "42"

    def test_negative_int(self) -> None:
        assert serialize_value(-7) == "-7"

    def test_float_whole(self) -> None:
        # Whole floats serialize without .0
        assert serialize_value(5.0) == "5"

    def test_float_fractional(self) -> None:
        assert serialize_value(3.14) == "3.14"

    def test_string(self) -> None:
        assert serialize_value("hello") == '"hello"'

    def test_string_with_quotes(self) -> None:
        assert serialize_value('say "hi"') == r'"say \"hi\""'

    def test_list(self) -> None:
        assert serialize_value([1, 2, 3]) == "[1, 2, 3]"

    def test_empty_list(self) -> None:
        assert serialize_value([]) == "[]"

    def test_dict(self) -> None:
        result = serialize_value({"key": "value"})
        assert result == '{"key": "value"}'

    def test_empty_dict(self) -> None:
        assert serialize_value({}) == "{}"

    def test_bool_before_int(self) -> None:
        """Bool is a subclass of int; serialize_value must handle bool first."""
        assert serialize_value(True) == "true"
        assert serialize_value(False) == "false"
        # Ensure these are NOT "1" and "0"
        assert serialize_value(True) != "1"


class TestRoundTrip:
    """Test that parse_value(serialize_value(v)) == v for all types."""

    @pytest.mark.parametrize("value", [
        Vector2(1.5, 2.0),
        Vector2(0.0, 0.0),
        Vector2i(1, 2),
        Vector3(1.0, 2.0, 3.0),
        Vector3i(1, 2, 3),
        Rect2(0.0, 0.0, 32.0, 32.0),
        Rect2i(0, 0, 32, 32),
        Color(1.0, 0.5, 0.0, 1.0),
        Transform2D(1.0, 0.0, 0.0, 1.0, 100.0, 200.0),
        Transform3D(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
        AABB(0.0, 0.0, 0.0, 1.0, 1.0, 1.0),
        StringName("idle"),
        NodePath("Path/To/Node"),
        ExtResourceRef("1_sheet"),
        SubResourceRef("AtlasTexture_abc12"),
    ])
    def test_round_trip_godot_types(self, value: object) -> None:
        serialized = serialize_value(value)
        parsed = parse_value(serialized)
        assert parsed == value, f"Round-trip failed: {value!r} -> {serialized!r} -> {parsed!r}"

    @pytest.mark.parametrize("value,expected_serial", [
        (None, "null"),
        (True, "true"),
        (False, "false"),
        (42, "42"),
        (3.14, "3.14"),
        ("hello", '"hello"'),
    ])
    def test_round_trip_primitives(self, value: object, expected_serial: str) -> None:
        serialized = serialize_value(value)
        assert serialized == expected_serial
        parsed = parse_value(serialized)
        assert parsed == value


class TestGodotJSONEncoder:
    """Test JSON serialization with Godot-native string format (D-03)."""

    def test_vector2_in_json(self) -> None:
        data = {"position": Vector2(1.5, 2.0)}
        result = json.dumps(data, cls=GodotJSONEncoder)
        assert result == '{"position": "Vector2(1.5, 2)"}'

    def test_color_in_json(self) -> None:
        data = {"color": Color(1.0, 0.0, 0.0, 1.0)}
        result = json.dumps(data, cls=GodotJSONEncoder)
        assert result == '{"color": "Color(1, 0, 0, 1)"}'

    def test_mixed_types(self) -> None:
        data = {
            "name": "test",
            "position": Vector2(0.0, 0.0),
            "enabled": True,
            "count": 5,
        }
        result = json.loads(json.dumps(data, cls=GodotJSONEncoder))
        assert result["name"] == "test"
        assert result["position"] == "Vector2(0, 0)"
        assert result["enabled"] is True
        assert result["count"] == 5

    def test_string_name_in_json(self) -> None:
        data = {"animation": StringName("idle")}
        result = json.dumps(data, cls=GodotJSONEncoder)
        assert result == '{"animation": "&\\"idle\\""}'

    def test_none_in_json(self) -> None:
        """None should serialize as JSON null, not the string 'null'."""
        data = {"value": None}
        result = json.dumps(data, cls=GodotJSONEncoder)
        assert result == '{"value": null}'
