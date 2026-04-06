"""Variant binary encoder/decoder for Godot 4.x debugger protocol.

Encodes Python values to Godot's binary Variant format and decodes
binary Variant data back to Python values. Uses struct for all binary
operations with little-endian byte order.

Type IDs match Godot 4.x variant.h (0-38). NOT Godot 3.x IDs.
"""

from __future__ import annotations

import struct
from enum import IntEnum

from gdauto.debugger.errors import ProtocolError
from gdauto.debugger.models import GodotNodePath, GodotStringName


class VariantType(IntEnum):
    """Godot 4.x Variant type IDs from core/variant/variant.h."""

    NIL = 0
    BOOL = 1
    INT = 2
    FLOAT = 3
    STRING = 4
    VECTOR2 = 5
    VECTOR2I = 6
    RECT2 = 7
    RECT2I = 8
    VECTOR3 = 9
    VECTOR3I = 10
    TRANSFORM2D = 11
    VECTOR4 = 12
    VECTOR4I = 13
    PLANE = 14
    QUATERNION = 15
    AABB = 16
    BASIS = 17
    TRANSFORM3D = 18
    PROJECTION = 19
    COLOR = 20
    STRING_NAME = 21
    NODE_PATH = 22
    RID = 23
    OBJECT = 24
    CALLABLE = 25
    SIGNAL = 26
    DICTIONARY = 27
    ARRAY = 28
    PACKED_BYTE_ARRAY = 29
    PACKED_INT32_ARRAY = 30
    PACKED_INT64_ARRAY = 31
    PACKED_FLOAT32_ARRAY = 32
    PACKED_FLOAT64_ARRAY = 33
    PACKED_STRING_ARRAY = 34
    PACKED_VECTOR2_ARRAY = 35
    PACKED_VECTOR3_ARRAY = 36
    PACKED_COLOR_ARRAY = 37
    PACKED_VECTOR4_ARRAY = 38


# Encoding flags (OR'd into the type header uint32)
ENCODE_FLAG_64 = 1 << 16
ENCODE_FLAG_OBJECT_AS_ID = 1 << 16

# Range boundaries for int32
_INT32_MIN = -(2**31)
_INT32_MAX = 2**31 - 1


# -----------------------------------------------------------------------
# String encoding helper (shared by STRING, STRING_NAME, NODE_PATH)
# -----------------------------------------------------------------------


def _encode_string_bytes(utf8: bytes) -> bytes:
    """Encode a UTF-8 byte string with length prefix and 4-byte padding."""
    length = len(utf8)
    # pad = (4 - (length % 4)) % 4
    pad = (4 - (length % 4)) % 4
    return struct.pack('<I', length) + utf8 + b'\x00' * pad


# -----------------------------------------------------------------------
# Private encoder functions (one per type)
# -----------------------------------------------------------------------


def _encode_nil() -> bytes:
    return struct.pack('<I', VariantType.NIL)


def _encode_bool(value: bool) -> bytes:
    return struct.pack('<II', VariantType.BOOL, int(value))


def _encode_int(value: int) -> bytes:
    if _INT32_MIN <= value <= _INT32_MAX:
        return struct.pack('<Ii', VariantType.INT, value)
    return struct.pack('<Iq', VariantType.INT | ENCODE_FLAG_64, value)


def _encode_float(value: float) -> bytes:
    return struct.pack('<Id', VariantType.FLOAT | ENCODE_FLAG_64, value)


def _encode_string(value: str) -> bytes:
    utf8 = value.encode('utf-8')
    return struct.pack('<I', VariantType.STRING) + _encode_string_bytes(utf8)


def _encode_string_name(value: GodotStringName) -> bytes:
    utf8 = value.value.encode('utf-8')
    header = struct.pack('<I', VariantType.STRING_NAME)
    return header + _encode_string_bytes(utf8)


def _parse_node_path(
    path: str,
) -> tuple[list[str], list[str], bool]:
    """Parse a NodePath string into names, subnames, and absolute flag."""
    absolute = path.startswith('/')
    if absolute:
        path = path[1:]

    subnames: list[str] = []
    if ':' in path:
        parts = path.split(':')
        names = [n for n in parts[0].split('/') if n]
        subnames = parts[1:]
    else:
        names = [n for n in path.split('/') if n]

    return names, subnames, absolute


def _encode_node_path(value: GodotNodePath) -> bytes:
    """Encode a NodePath in Godot's new format (MSB set on name_count)."""
    path = value.value
    header = struct.pack('<I', VariantType.NODE_PATH)

    if not path:
        return header + struct.pack('<III', 0x80000000, 0, 0)

    names, subnames, absolute = _parse_node_path(path)
    flags = 1 if absolute else 0
    name_count_val = len(names) | 0x80000000  # MSB set = new format

    parts = [header, struct.pack('<III', name_count_val, len(subnames), flags)]
    for name in names:
        parts.append(_encode_string_bytes(name.encode('utf-8')))
    for sub in subnames:
        parts.append(_encode_string_bytes(sub.encode('utf-8')))
    return b''.join(parts)


def _encode_tuple_typed(
    values: tuple, type_hint: VariantType
) -> bytes:
    """Encode a tuple with a specific type hint."""
    fmt_map: dict[VariantType, str] = {
        VariantType.VECTOR2: '<I2f',
        VariantType.VECTOR2I: '<I2i',
        VariantType.RECT2: '<I4f',
        VariantType.RECT2I: '<I4i',
        VariantType.VECTOR3: '<I3f',
        VariantType.VECTOR3I: '<I3i',
        VariantType.COLOR: '<I4f',
        VariantType.TRANSFORM2D: '<I6f',
        VariantType.BASIS: '<I9f',
    }
    fmt = fmt_map.get(type_hint)
    if fmt is not None:
        return struct.pack(fmt, type_hint, *values)
    raise ProtocolError(
        message=f"No tuple encoding for type hint {type_hint}",
        code="UNSUPPORTED_TYPE",
    )


def _encode_array(values: list) -> bytes:
    header = struct.pack('<II', VariantType.ARRAY, len(values))
    parts = [header]
    for item in values:
        parts.append(encode(item))
    return b''.join(parts)


def _encode_dictionary(values: dict) -> bytes:
    header = struct.pack('<II', VariantType.DICTIONARY, len(values))
    parts = [header]
    for k, v in values.items():
        parts.append(encode(k))
        parts.append(encode(v))
    return b''.join(parts)


def _encode_packed_byte_array(values: bytes) -> bytes:
    length = len(values)
    pad = (4 - (length % 4)) % 4
    header = struct.pack('<II', VariantType.PACKED_BYTE_ARRAY, length)
    return header + values + b'\x00' * pad


def _encode_packed_int32_array(values: list) -> bytes:
    count = len(values)
    header = struct.pack('<II', VariantType.PACKED_INT32_ARRAY, count)
    return header + struct.pack(f'<{count}i', *values)


def _encode_packed_float32_array(values: list) -> bytes:
    count = len(values)
    header = struct.pack('<II', VariantType.PACKED_FLOAT32_ARRAY, count)
    return header + struct.pack(f'<{count}f', *values)


def _encode_packed_string_array(values: list) -> bytes:
    header = struct.pack('<II', VariantType.PACKED_STRING_ARRAY, len(values))
    parts = [header]
    for s in values:
        utf8 = s.encode('utf-8')
        parts.append(_encode_string_bytes(utf8))
    return b''.join(parts)


def _encode_rid(value: int) -> bytes:
    return struct.pack('<IQ', VariantType.RID, value)


def _encode_object_null() -> bytes:
    return struct.pack('<II', VariantType.OBJECT, 0)


def _encode_object_as_id(value: int) -> bytes:
    header = VariantType.OBJECT | ENCODE_FLAG_OBJECT_AS_ID
    return struct.pack('<IQ', header, value)


# -----------------------------------------------------------------------
# Public encode()
# -----------------------------------------------------------------------


def _encode_with_type_hint(
    value: object, type_hint: VariantType
) -> bytes | None:
    """Dispatch encoding based on explicit type hint. Returns None if unhandled."""
    if type_hint == VariantType.OBJECT:
        if value is None or value == 0:
            return _encode_object_null()
        return _encode_object_as_id(int(value))  # type: ignore[arg-type]
    if type_hint == VariantType.RID:
        return _encode_rid(int(value))  # type: ignore[arg-type]
    if type_hint == VariantType.PACKED_INT32_ARRAY:
        return _encode_packed_int32_array(list(value))  # type: ignore[arg-type]
    if type_hint == VariantType.PACKED_FLOAT32_ARRAY:
        return _encode_packed_float32_array(list(value))  # type: ignore[arg-type]
    if type_hint == VariantType.PACKED_STRING_ARRAY:
        return _encode_packed_string_array(list(value))  # type: ignore[arg-type]
    if isinstance(value, tuple):
        return _encode_tuple_typed(value, type_hint)
    return None


def _encode_by_type(value: object) -> bytes:
    """Dispatch encoding based on Python value type (no type hint)."""
    if value is None:
        return _encode_nil()
    # bool before int (bool is a subclass of int in Python)
    if isinstance(value, bool):
        return _encode_bool(value)
    if isinstance(value, GodotStringName):
        return _encode_string_name(value)
    if isinstance(value, GodotNodePath):
        return _encode_node_path(value)
    if isinstance(value, int):
        return _encode_int(value)
    if isinstance(value, float):
        return _encode_float(value)
    if isinstance(value, str):
        return _encode_string(value)
    if isinstance(value, (bytes, bytearray)):
        return _encode_packed_byte_array(bytes(value))
    if isinstance(value, list):
        return _encode_array(value)
    if isinstance(value, dict):
        return _encode_dictionary(value)
    raise ProtocolError(
        message=f"Cannot encode type {type(value).__name__}",
        code="UNSUPPORTED_TYPE",
    )


def encode(value: object, type_hint: VariantType | None = None) -> bytes:
    """Encode a Python value to Godot Variant binary format.

    Args:
        value: The Python value to encode.
        type_hint: Optional type hint for ambiguous types (e.g., tuples
            that could be Vector2, Vector3, Color, etc.).

    Returns:
        Bytes in Godot's Variant binary format.

    Raises:
        ProtocolError: If the value type is unsupported.
    """
    if type_hint is not None:
        result = _encode_with_type_hint(value, type_hint)
        if result is not None:
            return result
    return _encode_by_type(value)


# -----------------------------------------------------------------------
# Private decoder helpers
# -----------------------------------------------------------------------


def _check_remaining(
    data: bytes, offset: int, needed: int, context: str
) -> None:
    """Raise ProtocolError if not enough bytes remain."""
    if offset + needed > len(data):
        raise ProtocolError(
            message=f"Truncated {context}: need {needed} bytes at offset {offset}, have {len(data) - offset}",
            code="TRUNCATED_DATA",
        )


def _decode_string_at(
    data: bytes, offset: int
) -> tuple[str, int]:
    """Decode a length-prefixed, padded UTF-8 string at offset."""
    _check_remaining(data, offset, 4, "string length")
    length = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    pad = (4 - (length % 4)) % 4
    _check_remaining(data, offset, length + pad, "string data")
    text = data[offset:offset + length].decode('utf-8')
    offset += length + pad
    return text, offset


# -----------------------------------------------------------------------
# Private decoder functions (one per type)
# -----------------------------------------------------------------------


def _decode_nil(
    data: bytes, offset: int
) -> tuple[None, int]:
    return None, offset


def _decode_bool(
    data: bytes, offset: int
) -> tuple[bool, int]:
    _check_remaining(data, offset, 4, "bool value")
    val = struct.unpack_from('<I', data, offset)[0]
    return bool(val), offset + 4


def _decode_int(
    data: bytes, offset: int, flag_64: bool
) -> tuple[int, int]:
    if flag_64:
        _check_remaining(data, offset, 8, "int64 value")
        val = struct.unpack_from('<q', data, offset)[0]
        return val, offset + 8
    _check_remaining(data, offset, 4, "int32 value")
    val = struct.unpack_from('<i', data, offset)[0]
    return val, offset + 4


def _decode_float(
    data: bytes, offset: int, flag_64: bool
) -> tuple[float, int]:
    if flag_64:
        _check_remaining(data, offset, 8, "float64 value")
        val = struct.unpack_from('<d', data, offset)[0]
        return val, offset + 8
    _check_remaining(data, offset, 4, "float32 value")
    val = struct.unpack_from('<f', data, offset)[0]
    return val, offset + 4


def _decode_string(
    data: bytes, offset: int
) -> tuple[str, int]:
    return _decode_string_at(data, offset)


def _decode_string_name(
    data: bytes, offset: int
) -> tuple[GodotStringName, int]:
    text, new_offset = _decode_string_at(data, offset)
    return GodotStringName(text), new_offset


def _read_string_list(
    data: bytes, offset: int, count: int
) -> tuple[list[str], int]:
    """Read count length-prefixed padded strings from data."""
    strings: list[str] = []
    for _ in range(count):
        text, offset = _decode_string_at(data, offset)
        strings.append(text)
    return strings, offset


def _assemble_node_path(
    names: list[str], subnames: list[str], absolute: bool
) -> str:
    """Build a NodePath string from parsed components."""
    path = '/'.join(names)
    if absolute:
        path = '/' + path
    if subnames:
        path = path + ':' + ':'.join(subnames)
    return path


def _decode_node_path(
    data: bytes, offset: int
) -> tuple[GodotNodePath, int]:
    _check_remaining(data, offset, 4, "node_path name_count")
    raw_name_count = struct.unpack_from('<I', data, offset)[0]
    offset += 4

    # New format: MSB is set
    if raw_name_count & 0x80000000:
        name_count = raw_name_count & 0x7FFFFFFF
        _check_remaining(data, offset, 8, "node_path sub_count+flags")
        sub_count, flags = struct.unpack_from('<II', data, offset)
        offset += 8
        names, offset = _read_string_list(data, offset, name_count)
        subnames, offset = _read_string_list(data, offset, sub_count)
        path = _assemble_node_path(names, subnames, bool(flags & 1))
        return GodotNodePath(path), offset

    if raw_name_count == 0:
        return GodotNodePath(""), offset
    raise ProtocolError(
        message="Legacy NodePath format not supported",
        code="UNSUPPORTED_FORMAT",
    )


def _decode_tuple_floats(
    data: bytes, offset: int, count: int
) -> tuple[tuple, int]:
    """Decode count float32 values as a tuple."""
    size = count * 4
    _check_remaining(data, offset, size, f"{count}x float32")
    vals = struct.unpack_from(f'<{count}f', data, offset)
    return vals, offset + size


def _decode_tuple_ints(
    data: bytes, offset: int, count: int
) -> tuple[tuple, int]:
    """Decode count int32 values as a tuple."""
    size = count * 4
    _check_remaining(data, offset, size, f"{count}x int32")
    vals = struct.unpack_from(f'<{count}i', data, offset)
    return vals, offset + size


def _decode_rid(
    data: bytes, offset: int
) -> tuple[int, int]:
    _check_remaining(data, offset, 8, "RID value")
    val = struct.unpack_from('<Q', data, offset)[0]
    return val, offset + 8


def _decode_object(
    data: bytes, offset: int, has_id_flag: bool
) -> tuple[object, int]:
    if has_id_flag:
        _check_remaining(data, offset, 8, "object id")
        val = struct.unpack_from('<Q', data, offset)[0]
        return val, offset + 8
    _check_remaining(data, offset, 4, "object null")
    val = struct.unpack_from('<I', data, offset)[0]
    return None if val == 0 else val, offset + 4


def _decode_array(
    data: bytes, offset: int, header: int
) -> tuple[list, int]:
    # Check for typed container metadata (Godot 4.4+)
    # Bits 16-17 of the header indicate typed array
    typed_flag = (header >> 16) & 0x3
    if typed_flag:
        # Read and discard type metadata: 3 uint32s
        _check_remaining(data, offset, 12, "typed array metadata")
        offset += 12  # skip element_type, class_name_len, script

    _check_remaining(data, offset, 4, "array count")
    count = struct.unpack_from('<I', data, offset)[0]
    # Mask off the shared flag bit (MSB)
    count = count & 0x7FFFFFFF
    offset += 4

    items: list[object] = []
    for _ in range(count):
        val, consumed = decode(data, offset)
        offset += consumed
        items.append(val)
    return items, offset


def _decode_dictionary(
    data: bytes, offset: int, header: int
) -> tuple[dict, int]:
    # Check for typed container metadata (Godot 4.4+)
    typed_flag = (header >> 16) & 0x3
    if typed_flag:
        _check_remaining(data, offset, 12, "typed dict metadata")
        offset += 12

    _check_remaining(data, offset, 4, "dict count")
    count = struct.unpack_from('<I', data, offset)[0]
    count = count & 0x7FFFFFFF
    offset += 4

    result: dict[object, object] = {}
    for _ in range(count):
        key, consumed = decode(data, offset)
        offset += consumed
        val, consumed = decode(data, offset)
        offset += consumed
        result[key] = val
    return result, offset


def _decode_packed_byte_array(
    data: bytes, offset: int
) -> tuple[list[int], int]:
    _check_remaining(data, offset, 4, "packed byte array count")
    count = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    pad = (4 - (count % 4)) % 4
    _check_remaining(data, offset, count + pad, "packed byte array data")
    vals = list(data[offset:offset + count])
    offset += count + pad
    return vals, offset


def _decode_packed_int32_array(
    data: bytes, offset: int
) -> tuple[list[int], int]:
    _check_remaining(data, offset, 4, "packed int32 array count")
    count = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    size = count * 4
    _check_remaining(data, offset, size, "packed int32 array data")
    vals = list(struct.unpack_from(f'<{count}i', data, offset))
    return vals, offset + size


def _decode_packed_float32_array(
    data: bytes, offset: int
) -> tuple[list[float], int]:
    _check_remaining(data, offset, 4, "packed float32 array count")
    count = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    size = count * 4
    _check_remaining(data, offset, size, "packed float32 array data")
    vals = list(struct.unpack_from(f'<{count}f', data, offset))
    return vals, offset + size


def _decode_packed_string_array(
    data: bytes, offset: int
) -> tuple[list[str], int]:
    _check_remaining(data, offset, 4, "packed string array count")
    count = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    strings: list[str] = []
    for _ in range(count):
        text, offset = _decode_string_at(data, offset)
        strings.append(text)
    return strings, offset


# Type ID to float/int count mapping for simple vector/matrix types
_FLOAT_TUPLE_SIZES: dict[int, int] = {
    VariantType.VECTOR2: 2,
    VariantType.RECT2: 4,
    VariantType.VECTOR3: 3,
    VariantType.TRANSFORM2D: 6,
    VariantType.VECTOR4: 4,
    VariantType.PLANE: 4,
    VariantType.QUATERNION: 4,
    VariantType.AABB: 6,
    VariantType.BASIS: 9,
    VariantType.TRANSFORM3D: 12,
    VariantType.PROJECTION: 16,
    VariantType.COLOR: 4,
}

_INT_TUPLE_SIZES: dict[int, int] = {
    VariantType.VECTOR2I: 2,
    VariantType.RECT2I: 4,
    VariantType.VECTOR3I: 3,
    VariantType.VECTOR4I: 4,
}


# -----------------------------------------------------------------------
# Public decode()
# -----------------------------------------------------------------------


_NOT_FOUND = object()  # sentinel for dispatch miss


def _dispatch_scalar(
    data: bytes, offset: int, base_type: int, flag_64: bool
) -> tuple[object, int]:
    """Decode scalar and string types from data at offset."""
    if base_type == VariantType.NIL:
        return _decode_nil(data, offset)
    if base_type == VariantType.BOOL:
        return _decode_bool(data, offset)
    if base_type == VariantType.INT:
        return _decode_int(data, offset, flag_64)
    if base_type == VariantType.FLOAT:
        return _decode_float(data, offset, flag_64)
    if base_type == VariantType.STRING:
        return _decode_string(data, offset)
    if base_type == VariantType.STRING_NAME:
        return _decode_string_name(data, offset)
    if base_type == VariantType.NODE_PATH:
        return _decode_node_path(data, offset)
    if base_type == VariantType.RID:
        return _decode_rid(data, offset)
    if base_type == VariantType.OBJECT:
        return _decode_object(data, offset, flag_64)
    return _NOT_FOUND, offset


def _dispatch_composite(
    data: bytes, offset: int, base_type: int, header: int
) -> tuple[object, int]:
    """Decode composite types (tuples, arrays, dicts, packed arrays)."""
    if base_type in _FLOAT_TUPLE_SIZES:
        return _decode_tuple_floats(data, offset, _FLOAT_TUPLE_SIZES[base_type])
    if base_type in _INT_TUPLE_SIZES:
        return _decode_tuple_ints(data, offset, _INT_TUPLE_SIZES[base_type])
    if base_type == VariantType.ARRAY:
        return _decode_array(data, offset, header)
    if base_type == VariantType.DICTIONARY:
        return _decode_dictionary(data, offset, header)
    return _dispatch_packed(data, offset, base_type)


def _dispatch_packed(
    data: bytes, offset: int, base_type: int
) -> tuple[object, int]:
    """Decode packed array types."""
    if base_type == VariantType.PACKED_BYTE_ARRAY:
        return _decode_packed_byte_array(data, offset)
    if base_type == VariantType.PACKED_INT32_ARRAY:
        return _decode_packed_int32_array(data, offset)
    if base_type == VariantType.PACKED_INT64_ARRAY:
        return _decode_packed_int64_array(data, offset)
    if base_type == VariantType.PACKED_FLOAT32_ARRAY:
        return _decode_packed_float32_array(data, offset)
    if base_type == VariantType.PACKED_FLOAT64_ARRAY:
        return _decode_packed_float64_array(data, offset)
    if base_type == VariantType.PACKED_STRING_ARRAY:
        return _decode_packed_string_array(data, offset)
    raise ProtocolError(
        message=f"Unknown Variant type ID: {base_type}",
        code="UNKNOWN_TYPE",
        fix="Check that the Godot version matches (requires Godot 4.x)",
    )


def decode(data: bytes, offset: int = 0) -> tuple[object, int]:
    """Decode a Godot Variant from binary data.

    Args:
        data: Raw bytes containing one or more encoded Variants.
        offset: Byte offset to start reading from.

    Returns:
        A tuple of (decoded_value, bytes_consumed) where bytes_consumed
        is the number of bytes read (not the new offset).

    Raises:
        ProtocolError: On truncated data, unknown type ID, or malformed input.
    """
    start = offset
    _check_remaining(data, offset, 4, "variant header")
    header = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    base_type = header & 0xFFFF
    flag_64 = bool(header & ENCODE_FLAG_64)

    val, offset = _dispatch_scalar(data, offset, base_type, flag_64)
    if val is _NOT_FOUND:
        val, offset = _dispatch_composite(data, offset, base_type, header)
    return val, offset - start


def _decode_packed_int64_array(
    data: bytes, offset: int
) -> tuple[list[int], int]:
    _check_remaining(data, offset, 4, "packed int64 array count")
    count = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    size = count * 8
    _check_remaining(data, offset, size, "packed int64 array data")
    vals = list(struct.unpack_from(f'<{count}q', data, offset))
    return vals, offset + size


def _decode_packed_float64_array(
    data: bytes, offset: int
) -> tuple[list[float], int]:
    _check_remaining(data, offset, 4, "packed float64 array count")
    count = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    size = count * 8
    _check_remaining(data, offset, size, "packed float64 array data")
    vals = list(struct.unpack_from(f'<{count}d', data, offset))
    return vals, offset + size
