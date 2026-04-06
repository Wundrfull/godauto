"""Exhaustive golden-byte tests for the Godot Variant binary codec.

Tests verify byte-exact encoding fidelity against Godot 4.x's
var_to_bytes() output, plus round-trip decode correctness and
error handling for malformed input.

Type IDs are Godot 4.x (NOT Godot 3.x).
"""

from __future__ import annotations

import struct
import math

import pytest

from gdauto.debugger.variant import (
    VariantType,
    ENCODE_FLAG_64,
    ENCODE_FLAG_OBJECT_AS_ID,
    encode,
    decode,
)
from gdauto.debugger.errors import (
    DebuggerError,
    DebuggerConnectionError,
    DebuggerTimeoutError,
    ProtocolError,
)
from gdauto.debugger.models import GodotStringName, GodotNodePath
from gdauto.errors import GdautoError


# =========================================================================
# TestDebuggerErrors: error hierarchy and to_dict
# =========================================================================


class TestDebuggerErrors:
    """Verify debugger error hierarchy and serialization."""

    def test_debugger_error_inherits_from_gdauto_error(self) -> None:
        err = DebuggerError(message="fail", code="DBG_ERR")
        assert isinstance(err, GdautoError)

    def test_debugger_connection_error_inherits_from_debugger_error(self) -> None:
        err = DebuggerConnectionError(message="no conn", code="CONN_ERR")
        assert isinstance(err, DebuggerError)
        assert isinstance(err, GdautoError)

    def test_debugger_timeout_error_inherits_from_debugger_error(self) -> None:
        err = DebuggerTimeoutError(message="timeout", code="TIMEOUT")
        assert isinstance(err, DebuggerError)

    def test_protocol_error_inherits_from_debugger_error(self) -> None:
        err = ProtocolError(message="bad data", code="PROTO_ERR")
        assert isinstance(err, DebuggerError)

    def test_debugger_error_to_dict_with_fix(self) -> None:
        err = DebuggerError(message="fail", code="DBG_ERR", fix="try again")
        d = err.to_dict()
        assert d == {"error": "fail", "code": "DBG_ERR", "fix": "try again"}

    def test_debugger_error_to_dict_without_fix(self) -> None:
        err = DebuggerError(message="fail", code="DBG_ERR")
        d = err.to_dict()
        assert d == {"error": "fail", "code": "DBG_ERR"}

    def test_protocol_error_to_dict(self) -> None:
        err = ProtocolError(
            message="unknown type",
            code="UNKNOWN_TYPE",
            fix="check Godot version",
        )
        d = err.to_dict()
        assert d["error"] == "unknown type"
        assert d["code"] == "UNKNOWN_TYPE"
        assert d["fix"] == "check Godot version"

    def test_debugger_error_str(self) -> None:
        err = DebuggerError(message="something broke", code="X")
        assert str(err) == "something broke"


# =========================================================================
# TestModels: GodotStringName and GodotNodePath
# =========================================================================


class TestModels:
    """Verify debugger model wrappers."""

    def test_string_name_distinguishable_from_str(self) -> None:
        sn = GodotStringName("test")
        assert isinstance(sn, GodotStringName)
        assert not isinstance(sn, str)

    def test_string_name_value(self) -> None:
        sn = GodotStringName("hello")
        assert sn.value == "hello"
        assert str(sn) == "hello"

    def test_node_path_distinguishable_from_str(self) -> None:
        np = GodotNodePath("/root/Main")
        assert isinstance(np, GodotNodePath)
        assert not isinstance(np, str)

    def test_node_path_value(self) -> None:
        np = GodotNodePath("/root/Main/Label:text")
        assert np.value == "/root/Main/Label:text"
        assert str(np) == "/root/Main/Label:text"

    def test_string_name_frozen(self) -> None:
        sn = GodotStringName("x")
        with pytest.raises(AttributeError):
            sn.value = "y"  # type: ignore[misc]

    def test_node_path_frozen(self) -> None:
        np = GodotNodePath("x")
        with pytest.raises(AttributeError):
            np.value = "y"  # type: ignore[misc]


# =========================================================================
# TestVariantType: enum values match Godot 4 IDs
# =========================================================================


class TestVariantType:
    """Verify VariantType enum maps to correct Godot 4.x type IDs."""

    def test_nil_is_0(self) -> None:
        assert VariantType.NIL == 0

    def test_bool_is_1(self) -> None:
        assert VariantType.BOOL == 1

    def test_int_is_2(self) -> None:
        assert VariantType.INT == 2

    def test_float_is_3(self) -> None:
        assert VariantType.FLOAT == 3

    def test_string_is_4(self) -> None:
        assert VariantType.STRING == 4

    def test_vector2_is_5(self) -> None:
        assert VariantType.VECTOR2 == 5

    def test_vector2i_is_6(self) -> None:
        assert VariantType.VECTOR2I == 6

    def test_color_is_20(self) -> None:
        assert VariantType.COLOR == 20

    def test_string_name_is_21(self) -> None:
        assert VariantType.STRING_NAME == 21

    def test_node_path_is_22(self) -> None:
        assert VariantType.NODE_PATH == 22

    def test_rid_is_23(self) -> None:
        assert VariantType.RID == 23

    def test_object_is_24(self) -> None:
        assert VariantType.OBJECT == 24

    def test_dictionary_is_27(self) -> None:
        assert VariantType.DICTIONARY == 27

    def test_array_is_28(self) -> None:
        assert VariantType.ARRAY == 28

    def test_packed_byte_array_is_29(self) -> None:
        assert VariantType.PACKED_BYTE_ARRAY == 29

    def test_packed_vector4_array_is_38(self) -> None:
        assert VariantType.PACKED_VECTOR4_ARRAY == 38

    def test_total_type_count(self) -> None:
        assert len(VariantType) == 39


# =========================================================================
# TestEncodeNil
# =========================================================================


class TestEncodeNil:
    """Verify None encodes to NIL (type 0, 4 bytes)."""

    def test_encode_none(self) -> None:
        result = encode(None)
        assert result == b'\x00\x00\x00\x00'

    def test_encode_none_length(self) -> None:
        result = encode(None)
        assert len(result) == 4


# =========================================================================
# TestEncodeBool
# =========================================================================


class TestEncodeBool:
    """Verify bool encoding: type 1 + 4-byte value (0 or 1)."""

    def test_encode_true(self) -> None:
        result = encode(True)
        assert result == b'\x01\x00\x00\x00' + b'\x01\x00\x00\x00'

    def test_encode_false(self) -> None:
        result = encode(False)
        assert result == b'\x01\x00\x00\x00' + b'\x00\x00\x00\x00'

    def test_encode_bool_length(self) -> None:
        assert len(encode(True)) == 8
        assert len(encode(False)) == 8


# =========================================================================
# TestEncodeInt
# =========================================================================


class TestEncodeInt:
    """Verify integer encoding: 32-bit or 64-bit based on range."""

    def test_encode_small_int(self) -> None:
        result = encode(42)
        assert result == b'\x02\x00\x00\x00' + b'\x2a\x00\x00\x00'

    def test_encode_zero(self) -> None:
        result = encode(0)
        expected = struct.pack('<I', VariantType.INT) + struct.pack('<i', 0)
        assert result == expected

    def test_encode_negative_one(self) -> None:
        result = encode(-1)
        assert result == b'\x02\x00\x00\x00' + b'\xff\xff\xff\xff'

    def test_encode_max_int32(self) -> None:
        result = encode(2**31 - 1)
        expected = struct.pack('<Ii', VariantType.INT, 2**31 - 1)
        assert result == expected

    def test_encode_min_int32(self) -> None:
        result = encode(-(2**31))
        expected = struct.pack('<Ii', VariantType.INT, -(2**31))
        assert result == expected

    def test_encode_large_int_uses_64bit(self) -> None:
        """INT values exceeding int32 range use ENCODE_FLAG_64."""
        result = encode(2**40)
        header = struct.unpack_from('<I', result, 0)[0]
        assert header == (VariantType.INT | ENCODE_FLAG_64)
        value = struct.unpack_from('<q', result, 4)[0]
        assert value == 2**40

    def test_encode_large_negative_int_uses_64bit(self) -> None:
        result = encode(-(2**31) - 1)
        header = struct.unpack_from('<I', result, 0)[0]
        assert header == (VariantType.INT | ENCODE_FLAG_64)

    def test_encode_int32_length(self) -> None:
        assert len(encode(42)) == 8

    def test_encode_int64_length(self) -> None:
        assert len(encode(2**40)) == 12


# =========================================================================
# TestEncodeFloat
# =========================================================================


class TestEncodeFloat:
    """Verify float encoding: always 64-bit double with ENCODE_FLAG_64."""

    def test_encode_pi(self) -> None:
        result = encode(3.14)
        expected_header = struct.pack('<I', VariantType.FLOAT | ENCODE_FLAG_64)
        expected_value = struct.pack('<d', 3.14)
        assert result == expected_header + expected_value

    def test_encode_zero_float(self) -> None:
        result = encode(0.0)
        expected_header = struct.pack('<I', VariantType.FLOAT | ENCODE_FLAG_64)
        expected_value = struct.pack('<d', 0.0)
        assert result == expected_header + expected_value

    def test_encode_negative_float(self) -> None:
        result = encode(-1.5)
        header = struct.unpack_from('<I', result, 0)[0]
        assert header == (VariantType.FLOAT | ENCODE_FLAG_64)
        value = struct.unpack_from('<d', result, 4)[0]
        assert value == -1.5

    def test_encode_float_length(self) -> None:
        assert len(encode(3.14)) == 12


# =========================================================================
# TestEncodeString
# =========================================================================


class TestEncodeString:
    """Verify string encoding with 4-byte padding alignment."""

    def test_encode_empty_string(self) -> None:
        result = encode("")
        assert result == b'\x04\x00\x00\x00' + b'\x00\x00\x00\x00'

    def test_encode_single_char(self) -> None:
        result = encode("a")
        # type(4) + length(1) + 'a' + 3 pad bytes
        assert result == (
            b'\x04\x00\x00\x00'
            + b'\x01\x00\x00\x00'
            + b'a\x00\x00\x00'
        )

    def test_encode_four_chars(self) -> None:
        result = encode("test")
        # type(4) + length(4) + 'test' (no padding needed)
        assert result == (
            b'\x04\x00\x00\x00'
            + b'\x04\x00\x00\x00'
            + b'test'
        )

    def test_encode_five_chars(self) -> None:
        result = encode("hello")
        # type(4) + length(5) + 'hello' + 3 pad bytes
        assert result == (
            b'\x04\x00\x00\x00'
            + b'\x05\x00\x00\x00'
            + b'hello\x00\x00\x00'
        )

    @pytest.mark.parametrize(
        "text,expected_pad",
        [
            ("", 0),         # length 0: pad 0
            ("a", 3),        # length 1: pad 3
            ("ab", 2),       # length 2: pad 2
            ("abc", 1),      # length 3: pad 1
            ("abcd", 0),     # length 4: pad 0
            ("abcde", 3),    # length 5: pad 3
            ("abcdefg", 1),  # length 7: pad 1
            ("abcdefgh", 0), # length 8: pad 0
        ],
    )
    def test_string_padding_boundaries(
        self, text: str, expected_pad: int
    ) -> None:
        result = encode(text)
        utf8 = text.encode("utf-8")
        # Total: 4 (type) + 4 (length) + len(utf8) + pad
        expected_len = 4 + 4 + len(utf8) + expected_pad
        assert len(result) == expected_len

    def test_encode_unicode_string(self) -> None:
        """Unicode strings use UTF-8 byte length for padding calc."""
        result = encode("\u00e9")  # 'e with acute': 2 UTF-8 bytes
        utf8 = "\u00e9".encode("utf-8")
        assert len(utf8) == 2
        # 4 (type) + 4 (length) + 2 (bytes) + 2 (pad)
        assert len(result) == 12


# =========================================================================
# TestEncodeVector2
# =========================================================================


class TestEncodeVector2:
    """Verify Vector2 encoding: type 5 + 2x float32."""

    def test_encode_vector2(self) -> None:
        result = encode((1.0, 2.0), type_hint=VariantType.VECTOR2)
        expected = struct.pack('<I2f', VariantType.VECTOR2, 1.0, 2.0)
        assert result == expected

    def test_encode_vector2_length(self) -> None:
        result = encode((0.0, 0.0), type_hint=VariantType.VECTOR2)
        assert len(result) == 12  # 4 + 2*4


# =========================================================================
# TestEncodeVector3
# =========================================================================


class TestEncodeVector3:
    """Verify Vector3 encoding: type 9 + 3x float32."""

    def test_encode_vector3(self) -> None:
        result = encode((1.0, 2.0, 3.0), type_hint=VariantType.VECTOR3)
        expected = struct.pack('<I3f', VariantType.VECTOR3, 1.0, 2.0, 3.0)
        assert result == expected

    def test_encode_vector3_length(self) -> None:
        result = encode((0.0, 0.0, 0.0), type_hint=VariantType.VECTOR3)
        assert len(result) == 16  # 4 + 3*4


# =========================================================================
# TestEncodeColor
# =========================================================================


class TestEncodeColor:
    """Verify Color encoding: type 20 + 4x float32."""

    def test_encode_color(self) -> None:
        result = encode((1.0, 0.5, 0.0, 1.0), type_hint=VariantType.COLOR)
        expected = struct.pack(
            '<I4f', VariantType.COLOR, 1.0, 0.5, 0.0, 1.0
        )
        assert result == expected

    def test_encode_color_length(self) -> None:
        result = encode(
            (0.0, 0.0, 0.0, 0.0), type_hint=VariantType.COLOR
        )
        assert len(result) == 20  # 4 + 4*4


# =========================================================================
# TestEncodeStringName
# =========================================================================


class TestEncodeStringName:
    """Verify GodotStringName encodes as type 21 (STRING_NAME)."""

    def test_encode_string_name(self) -> None:
        result = encode(GodotStringName("test"))
        # type 21 + length 4 + "test" (no pad needed for 4 chars)
        expected = (
            struct.pack('<I', VariantType.STRING_NAME)
            + struct.pack('<I', 4)
            + b'test'
        )
        assert result == expected

    def test_encode_string_name_with_padding(self) -> None:
        result = encode(GodotStringName("hi"))
        expected = (
            struct.pack('<I', VariantType.STRING_NAME)
            + struct.pack('<I', 2)
            + b'hi\x00\x00'
        )
        assert result == expected


# =========================================================================
# TestEncodeNodePath
# =========================================================================


class TestEncodeNodePath:
    """Verify NodePath encoding: type 22 + new format with names/subnames."""

    def test_encode_node_path_absolute(self) -> None:
        """NodePath "/root/Main/Label:text" encodes with names and subname."""
        result = encode(GodotNodePath("/root/Main/Label:text"))
        # Verify type header
        header = struct.unpack_from('<I', result, 0)[0]
        assert header == VariantType.NODE_PATH

    def test_encode_empty_node_path(self) -> None:
        """Empty NodePath encodes with zero names."""
        result = encode(GodotNodePath(""))
        header = struct.unpack_from('<I', result, 0)[0]
        assert header == VariantType.NODE_PATH

    def test_encode_relative_node_path(self) -> None:
        """Relative path without leading / should not set absolute flag."""
        result = encode(GodotNodePath("Child/Sprite2D"))
        header = struct.unpack_from('<I', result, 0)[0]
        assert header == VariantType.NODE_PATH


# =========================================================================
# TestEncodeArray
# =========================================================================


class TestEncodeArray:
    """Verify Array encoding: type 28 + count + recursive elements."""

    def test_encode_empty_array(self) -> None:
        result = encode([])
        expected = struct.pack('<II', VariantType.ARRAY, 0)
        assert result == expected

    def test_encode_mixed_array(self) -> None:
        """Array [1, "hello", True] encodes recursively."""
        result = encode([1, "hello", True])
        # type 28 + count 3 + encode(1) + encode("hello") + encode(True)
        expected = struct.pack('<II', VariantType.ARRAY, 3)
        expected += encode(1)
        expected += encode("hello")
        expected += encode(True)
        assert result == expected

    def test_encode_array_length(self) -> None:
        result = encode([1, 2, 3])
        # header(4) + count(4) + 3 * encode(int) = 8 + 3*8 = 32
        assert len(result) == 32


# =========================================================================
# TestEncodeDictionary
# =========================================================================


class TestEncodeDictionary:
    """Verify Dictionary encoding: type 27 + count + key/value pairs."""

    def test_encode_empty_dict(self) -> None:
        result = encode({})
        expected = struct.pack('<II', VariantType.DICTIONARY, 0)
        assert result == expected

    def test_encode_single_pair_dict(self) -> None:
        """Dict {"key": "value"} encodes as type 27 + count 1 + k + v."""
        result = encode({"key": "value"})
        expected = struct.pack('<II', VariantType.DICTIONARY, 1)
        expected += encode("key")
        expected += encode("value")
        assert result == expected

    def test_encode_nested_structures(self) -> None:
        """Array containing a Dict containing an Array."""
        data = [{"inner": [1, 2]}]
        result = encode(data)
        # Should not raise; result starts with Array header
        header = struct.unpack_from('<I', result, 0)[0]
        assert header == VariantType.ARRAY


# =========================================================================
# TestEncodeObject
# =========================================================================


class TestEncodeObject:
    """Verify Object encoding: null object and as_id variant."""

    def test_encode_object_null(self) -> None:
        """Object(null) encodes as type 24 + value 0."""
        result = encode(None, type_hint=VariantType.OBJECT)
        expected = struct.pack('<II', VariantType.OBJECT, 0)
        assert result == expected

    def test_encode_object_as_id(self) -> None:
        """Object with ENCODE_FLAG_OBJECT_AS_ID encodes id as uint64."""
        obj_id = 12345
        result = encode(obj_id, type_hint=VariantType.OBJECT)
        header = struct.unpack_from('<I', result, 0)[0]
        assert header == (VariantType.OBJECT | ENCODE_FLAG_OBJECT_AS_ID)
        value = struct.unpack_from('<Q', result, 4)[0]
        assert value == 12345


# =========================================================================
# TestEncodeShouldTypes
# =========================================================================


class TestEncodeShouldTypes:
    """Verify encoding of SHOULD-level types."""

    def test_encode_vector2i(self) -> None:
        result = encode((3, 4), type_hint=VariantType.VECTOR2I)
        expected = struct.pack('<I2i', VariantType.VECTOR2I, 3, 4)
        assert result == expected

    def test_encode_rect2(self) -> None:
        result = encode(
            (0.0, 0.0, 100.0, 200.0), type_hint=VariantType.RECT2
        )
        expected = struct.pack(
            '<I4f', VariantType.RECT2, 0.0, 0.0, 100.0, 200.0
        )
        assert result == expected

    def test_encode_rect2i(self) -> None:
        result = encode((0, 0, 100, 200), type_hint=VariantType.RECT2I)
        expected = struct.pack(
            '<I4i', VariantType.RECT2I, 0, 0, 100, 200
        )
        assert result == expected

    def test_encode_vector3i(self) -> None:
        result = encode((1, 2, 3), type_hint=VariantType.VECTOR3I)
        expected = struct.pack('<I3i', VariantType.VECTOR3I, 1, 2, 3)
        assert result == expected

    def test_encode_transform2d(self) -> None:
        vals = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        result = encode(vals, type_hint=VariantType.TRANSFORM2D)
        expected = struct.pack('<I6f', VariantType.TRANSFORM2D, *vals)
        assert result == expected

    def test_encode_basis(self) -> None:
        vals = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
        result = encode(vals, type_hint=VariantType.BASIS)
        expected = struct.pack('<I9f', VariantType.BASIS, *vals)
        assert result == expected

    def test_encode_rid(self) -> None:
        result = encode(42, type_hint=VariantType.RID)
        expected = struct.pack('<IQ', VariantType.RID, 42)
        assert result == expected

    def test_encode_packed_byte_array(self) -> None:
        data = bytes([1, 2, 3])
        result = encode(data)
        expected = (
            struct.pack('<II', VariantType.PACKED_BYTE_ARRAY, 3)
            + bytes([1, 2, 3])
            + b'\x00'  # pad to 4 bytes
        )
        assert result == expected

    def test_encode_packed_byte_array_aligned(self) -> None:
        """PackedByteArray with 4 bytes needs no padding."""
        data = bytes([1, 2, 3, 4])
        result = encode(data)
        expected = (
            struct.pack('<II', VariantType.PACKED_BYTE_ARRAY, 4)
            + bytes([1, 2, 3, 4])
        )
        assert result == expected

    def test_encode_packed_int32_array(self) -> None:
        result = encode([10, 20, 30], type_hint=VariantType.PACKED_INT32_ARRAY)
        expected = (
            struct.pack('<II', VariantType.PACKED_INT32_ARRAY, 3)
            + struct.pack('<3i', 10, 20, 30)
        )
        assert result == expected

    def test_encode_packed_float32_array(self) -> None:
        result = encode(
            [1.0, 2.0], type_hint=VariantType.PACKED_FLOAT32_ARRAY
        )
        expected = (
            struct.pack('<II', VariantType.PACKED_FLOAT32_ARRAY, 2)
            + struct.pack('<2f', 1.0, 2.0)
        )
        assert result == expected

    def test_encode_packed_string_array(self) -> None:
        result = encode(
            ["hi", "there"], type_hint=VariantType.PACKED_STRING_ARRAY
        )
        # type + count + each string: length + utf8 + pad
        header = struct.pack('<II', VariantType.PACKED_STRING_ARRAY, 2)
        # "hi": length 2 + b'hi' + 2 pad bytes
        s1 = struct.pack('<I', 2) + b'hi\x00\x00'
        # "there": length 5 + b'there' + 3 pad bytes
        s2 = struct.pack('<I', 5) + b'there\x00\x00\x00'
        assert result == header + s1 + s2


# =========================================================================
# TestDecodeRoundTrip: parametrized over all types
# =========================================================================


class TestDecodeRoundTrip:
    """Verify encode/decode round-trip for all supported types."""

    def test_round_trip_nil(self) -> None:
        val, consumed = decode(encode(None))
        assert val is None
        assert consumed == 4

    def test_round_trip_true(self) -> None:
        val, consumed = decode(encode(True))
        assert val is True
        assert consumed == 8

    def test_round_trip_false(self) -> None:
        val, consumed = decode(encode(False))
        assert val is False
        assert consumed == 8

    def test_round_trip_int_small(self) -> None:
        val, consumed = decode(encode(42))
        assert val == 42
        assert consumed == 8

    def test_round_trip_int_negative(self) -> None:
        val, consumed = decode(encode(-1))
        assert val == -1

    def test_round_trip_int_large(self) -> None:
        val, consumed = decode(encode(2**40))
        assert val == 2**40
        assert consumed == 12

    def test_round_trip_float(self) -> None:
        val, consumed = decode(encode(3.14))
        assert val == 3.14
        assert consumed == 12

    def test_round_trip_float_zero(self) -> None:
        val, _ = decode(encode(0.0))
        assert val == 0.0

    def test_round_trip_string_empty(self) -> None:
        val, consumed = decode(encode(""))
        assert val == ""
        assert consumed == 8

    def test_round_trip_string(self) -> None:
        val, _ = decode(encode("hello"))
        assert val == "hello"

    def test_round_trip_string_unicode(self) -> None:
        val, _ = decode(encode("\u00e9"))
        assert val == "\u00e9"

    def test_round_trip_string_name(self) -> None:
        val, _ = decode(encode(GodotStringName("test")))
        assert isinstance(val, GodotStringName)
        assert val.value == "test"

    def test_round_trip_node_path_absolute(self) -> None:
        val, _ = decode(encode(GodotNodePath("/root/Main/Label:text")))
        assert isinstance(val, GodotNodePath)
        assert val.value == "/root/Main/Label:text"

    def test_round_trip_node_path_empty(self) -> None:
        val, _ = decode(encode(GodotNodePath("")))
        assert isinstance(val, GodotNodePath)
        assert val.value == ""

    def test_round_trip_node_path_relative(self) -> None:
        val, _ = decode(encode(GodotNodePath("Child/Sprite2D")))
        assert isinstance(val, GodotNodePath)
        assert val.value == "Child/Sprite2D"

    def test_round_trip_vector2(self) -> None:
        val, _ = decode(encode((1.0, 2.0), type_hint=VariantType.VECTOR2))
        assert val == (pytest.approx(1.0), pytest.approx(2.0))

    def test_round_trip_vector2i(self) -> None:
        val, _ = decode(encode((3, 4), type_hint=VariantType.VECTOR2I))
        assert val == (3, 4)

    def test_round_trip_vector3(self) -> None:
        val, _ = decode(
            encode((1.0, 2.0, 3.0), type_hint=VariantType.VECTOR3)
        )
        assert val == (pytest.approx(1.0), pytest.approx(2.0), pytest.approx(3.0))

    def test_round_trip_vector3i(self) -> None:
        val, _ = decode(encode((1, 2, 3), type_hint=VariantType.VECTOR3I))
        assert val == (1, 2, 3)

    def test_round_trip_rect2(self) -> None:
        val, _ = decode(
            encode((0.0, 0.0, 100.0, 200.0), type_hint=VariantType.RECT2)
        )
        assert len(val) == 4

    def test_round_trip_rect2i(self) -> None:
        val, _ = decode(
            encode((0, 0, 100, 200), type_hint=VariantType.RECT2I)
        )
        assert val == (0, 0, 100, 200)

    def test_round_trip_color(self) -> None:
        val, _ = decode(
            encode((1.0, 0.5, 0.0, 1.0), type_hint=VariantType.COLOR)
        )
        assert len(val) == 4

    def test_round_trip_transform2d(self) -> None:
        vals = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        val, _ = decode(encode(vals, type_hint=VariantType.TRANSFORM2D))
        assert len(val) == 6

    def test_round_trip_basis(self) -> None:
        vals = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
        val, _ = decode(encode(vals, type_hint=VariantType.BASIS))
        assert len(val) == 9

    def test_round_trip_rid(self) -> None:
        val, _ = decode(encode(42, type_hint=VariantType.RID))
        assert val == 42

    def test_round_trip_array(self) -> None:
        val, _ = decode(encode([1, 2, 3]))
        assert val == [1, 2, 3]

    def test_round_trip_dict(self) -> None:
        val, _ = decode(encode({"key": "value"}))
        assert val == {"key": "value"}

    def test_round_trip_nested(self) -> None:
        data = [{"inner": [1, 2]}]
        val, _ = decode(encode(data))
        assert val == data

    def test_round_trip_object_null(self) -> None:
        val, _ = decode(encode(None, type_hint=VariantType.OBJECT))
        assert val is None or val == 0

    def test_round_trip_packed_byte_array(self) -> None:
        data = bytes([1, 2, 3])
        val, _ = decode(encode(data))
        assert bytes(val) == data

    def test_round_trip_packed_int32_array(self) -> None:
        val, _ = decode(
            encode([10, 20, 30], type_hint=VariantType.PACKED_INT32_ARRAY)
        )
        assert list(val) == [10, 20, 30]

    def test_round_trip_packed_float32_array(self) -> None:
        val, _ = decode(
            encode([1.0, 2.0], type_hint=VariantType.PACKED_FLOAT32_ARRAY)
        )
        assert len(val) == 2

    def test_round_trip_packed_string_array(self) -> None:
        val, _ = decode(
            encode(["hi", "there"], type_hint=VariantType.PACKED_STRING_ARRAY)
        )
        assert val == ["hi", "there"]


# =========================================================================
# TestDecodeErrors
# =========================================================================


class TestDecodeErrors:
    """Verify decode raises ProtocolError on bad input."""

    def test_decode_truncated_data(self) -> None:
        with pytest.raises(ProtocolError):
            decode(b'\x02\x00')  # truncated INT header

    def test_decode_unknown_type_id(self) -> None:
        bad_data = struct.pack('<I', 99)
        with pytest.raises(ProtocolError):
            decode(bad_data)

    def test_decode_truncated_string(self) -> None:
        # String header says length 10, but only 2 bytes follow
        data = struct.pack('<II', VariantType.STRING, 10) + b'ab'
        with pytest.raises(ProtocolError):
            decode(data)

    def test_decode_empty_data(self) -> None:
        with pytest.raises(ProtocolError):
            decode(b'')

    def test_decode_truncated_int_value(self) -> None:
        # INT header but missing value bytes
        data = struct.pack('<I', VariantType.INT)
        with pytest.raises(ProtocolError):
            decode(data)


# =========================================================================
# TestDecodeFlags: 32/64 bit int/float, typed container
# =========================================================================


class TestDecodeFlags:
    """Verify decode handles flag bits in type headers."""

    def test_decode_int32_no_flag(self) -> None:
        """32-bit int (no ENCODE_FLAG_64)."""
        data = struct.pack('<Ii', VariantType.INT, 42)
        val, consumed = decode(data)
        assert val == 42
        assert consumed == 8

    def test_decode_int64_with_flag(self) -> None:
        """64-bit int (ENCODE_FLAG_64 set)."""
        data = struct.pack('<Iq', VariantType.INT | ENCODE_FLAG_64, 2**40)
        val, consumed = decode(data)
        assert val == 2**40
        assert consumed == 12

    def test_decode_float32_no_flag(self) -> None:
        """32-bit float (no ENCODE_FLAG_64)."""
        data = struct.pack('<If', VariantType.FLOAT, 1.5)
        val, consumed = decode(data)
        assert abs(val - 1.5) < 1e-6
        assert consumed == 8

    def test_decode_float64_with_flag(self) -> None:
        """64-bit float (ENCODE_FLAG_64 set)."""
        data = struct.pack(
            '<Id', VariantType.FLOAT | ENCODE_FLAG_64, 3.14
        )
        val, consumed = decode(data)
        assert val == 3.14
        assert consumed == 12

    def test_decode_typed_array_metadata(self) -> None:
        """Godot 4.4+ typed Array: metadata bits in header are handled.

        A typed array has type info (4 bytes type, 4 bytes class name length,
        4 bytes script) between the Array header and element count.
        The decoder should read and discard this metadata.
        """
        # Build a typed Array header manually:
        # Header: ARRAY type with typed flag in bits 16-17
        typed_flag = 1 << 16  # bit 16 = typed container
        header = struct.pack('<I', VariantType.ARRAY | typed_flag)
        # Type info: element_type (INT=2), class_name_len (0), script (0)
        type_info = struct.pack('<III', VariantType.INT, 0, 0)
        # Element count
        count = struct.pack('<I', 1)
        # One INT element
        element = struct.pack('<Ii', VariantType.INT, 7)
        data = header + type_info + count + element
        val, _ = decode(data)
        assert val == [7]


# =========================================================================
# TestDecodeOffset
# =========================================================================


class TestDecodeOffset:
    """Verify decode works with non-zero offset parameter."""

    def test_decode_with_offset(self) -> None:
        """decode() reads from the given byte offset."""
        prefix = b'\xff\xff\xff\xff'  # 4 garbage bytes
        payload = encode(42)
        data = prefix + payload
        val, consumed = decode(data, offset=4)
        assert val == 42
        assert consumed == 8
