"""Godot value type dataclasses with parsing, serialization, and arithmetic.

Provides typed Python representations of all Godot value types found in
.tscn/.tres files, along with parse_value() and serialize_value() functions
for converting between Godot text format and Python objects.

Follows D-02 (typed dataclasses with arithmetic), D-03 (Godot-native JSON
serialization), and D-04 (lenient parsing of unknown constructors).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Float formatting helper
# ---------------------------------------------------------------------------

def _fmt_float(v: float) -> str:
    """Format a float matching Godot's serialization convention.

    Whole numbers lose the trailing .0 (e.g. 0.0 -> "0", 32.0 -> "32").
    Fractional values keep their decimal part (e.g. 1.5 -> "1.5").
    """
    if v == int(v) and math.isfinite(v):
        return str(int(v))
    return str(v)


# ---------------------------------------------------------------------------
# Vector2
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Vector2:
    """2D vector with float components."""

    x: float
    y: float

    def __add__(self, other: object) -> Vector2:
        if not isinstance(other, Vector2):
            return NotImplemented
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: object) -> Vector2:
        if not isinstance(other, Vector2):
            return NotImplemented
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: object) -> Vector2:
        if not isinstance(scalar, (int, float)):
            return NotImplemented
        return Vector2(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: object) -> Vector2:
        return self.__mul__(scalar)

    def dot(self, other: Vector2) -> float:
        """Compute dot product with another Vector2."""
        return self.x * other.x + self.y * other.y

    def length(self) -> float:
        """Compute the magnitude of this vector."""
        return math.sqrt(self.x * self.x + self.y * self.y)

    def normalized(self) -> Vector2:
        """Return a unit-length copy of this vector."""
        mag = self.length()
        if mag == 0:
            return Vector2(0.0, 0.0)
        return Vector2(self.x / mag, self.y / mag)

    def to_godot(self) -> str:
        """Serialize to Godot text format."""
        return f"Vector2({_fmt_float(self.x)}, {_fmt_float(self.y)})"


# ---------------------------------------------------------------------------
# Vector2i
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Vector2i:
    """2D vector with integer components."""

    x: int
    y: int

    def __add__(self, other: object) -> Vector2i:
        if not isinstance(other, Vector2i):
            return NotImplemented
        return Vector2i(self.x + other.x, self.y + other.y)

    def __sub__(self, other: object) -> Vector2i:
        if not isinstance(other, Vector2i):
            return NotImplemented
        return Vector2i(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: object) -> Vector2i:
        if not isinstance(scalar, int):
            return NotImplemented
        return Vector2i(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: object) -> Vector2i:
        return self.__mul__(scalar)

    def to_godot(self) -> str:
        """Serialize to Godot text format."""
        return f"Vector2i({self.x}, {self.y})"


# ---------------------------------------------------------------------------
# Vector3
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Vector3:
    """3D vector with float components."""

    x: float
    y: float
    z: float

    def __add__(self, other: object) -> Vector3:
        if not isinstance(other, Vector3):
            return NotImplemented
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: object) -> Vector3:
        if not isinstance(other, Vector3):
            return NotImplemented
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: object) -> Vector3:
        if not isinstance(scalar, (int, float)):
            return NotImplemented
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    def __rmul__(self, scalar: object) -> Vector3:
        return self.__mul__(scalar)

    def dot(self, other: Vector3) -> float:
        """Compute dot product with another Vector3."""
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: Vector3) -> Vector3:
        """Compute cross product with another Vector3."""
        return Vector3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def length(self) -> float:
        """Compute the magnitude of this vector."""
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def normalized(self) -> Vector3:
        """Return a unit-length copy of this vector."""
        mag = self.length()
        if mag == 0:
            return Vector3(0.0, 0.0, 0.0)
        return Vector3(self.x / mag, self.y / mag, self.z / mag)

    def to_godot(self) -> str:
        """Serialize to Godot text format."""
        return f"Vector3({_fmt_float(self.x)}, {_fmt_float(self.y)}, {_fmt_float(self.z)})"


# ---------------------------------------------------------------------------
# Vector3i
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Vector3i:
    """3D vector with integer components."""

    x: int
    y: int
    z: int

    def __add__(self, other: object) -> Vector3i:
        if not isinstance(other, Vector3i):
            return NotImplemented
        return Vector3i(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: object) -> Vector3i:
        if not isinstance(other, Vector3i):
            return NotImplemented
        return Vector3i(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: object) -> Vector3i:
        if not isinstance(scalar, int):
            return NotImplemented
        return Vector3i(self.x * scalar, self.y * scalar, self.z * scalar)

    def __rmul__(self, scalar: object) -> Vector3i:
        return self.__mul__(scalar)

    def to_godot(self) -> str:
        """Serialize to Godot text format."""
        return f"Vector3i({self.x}, {self.y}, {self.z})"


# ---------------------------------------------------------------------------
# Rect2
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Rect2:
    """2D rectangle with float components (position + size)."""

    x: float
    y: float
    w: float
    h: float

    @property
    def position(self) -> Vector2:
        """Return the top-left corner as a Vector2."""
        return Vector2(self.x, self.y)

    @property
    def size(self) -> Vector2:
        """Return the dimensions as a Vector2."""
        return Vector2(self.w, self.h)

    def contains(self, point: Vector2) -> bool:
        """Check if a point lies within this rectangle (inclusive)."""
        return (
            self.x <= point.x <= self.x + self.w
            and self.y <= point.y <= self.y + self.h
        )

    def intersection(self, other: Rect2) -> Rect2 | None:
        """Compute the overlapping rectangle, or None if no overlap."""
        left = max(self.x, other.x)
        top = max(self.y, other.y)
        right = min(self.x + self.w, other.x + other.w)
        bottom = min(self.y + self.h, other.y + other.h)
        if left >= right or top >= bottom:
            return None
        return Rect2(left, top, right - left, bottom - top)

    def to_godot(self) -> str:
        """Serialize to Godot text format."""
        return (
            f"Rect2({_fmt_float(self.x)}, {_fmt_float(self.y)}, "
            f"{_fmt_float(self.w)}, {_fmt_float(self.h)})"
        )


# ---------------------------------------------------------------------------
# Rect2i
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Rect2i:
    """2D rectangle with integer components (position + size)."""

    x: int
    y: int
    w: int
    h: int

    @property
    def position(self) -> Vector2i:
        """Return the top-left corner as a Vector2i."""
        return Vector2i(self.x, self.y)

    @property
    def size(self) -> Vector2i:
        """Return the dimensions as a Vector2i."""
        return Vector2i(self.w, self.h)

    def contains(self, point: Vector2i) -> bool:
        """Check if a point lies within this rectangle (inclusive)."""
        return (
            self.x <= point.x <= self.x + self.w
            and self.y <= point.y <= self.y + self.h
        )

    def intersection(self, other: Rect2i) -> Rect2i | None:
        """Compute the overlapping rectangle, or None if no overlap."""
        left = max(self.x, other.x)
        top = max(self.y, other.y)
        right = min(self.x + self.w, other.x + other.w)
        bottom = min(self.y + self.h, other.y + other.h)
        if left >= right or top >= bottom:
            return None
        return Rect2i(left, top, right - left, bottom - top)

    def to_godot(self) -> str:
        """Serialize to Godot text format."""
        return f"Rect2i({self.x}, {self.y}, {self.w}, {self.h})"


# ---------------------------------------------------------------------------
# Color
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Color:
    """RGBA color with float components (0.0 to 1.0)."""

    r: float
    g: float
    b: float
    a: float = 1.0

    def to_godot(self) -> str:
        """Serialize to Godot text format."""
        return (
            f"Color({_fmt_float(self.r)}, {_fmt_float(self.g)}, "
            f"{_fmt_float(self.b)}, {_fmt_float(self.a)})"
        )


# ---------------------------------------------------------------------------
# Transform2D
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Transform2D:
    """2D transformation matrix (2x2 basis + origin)."""

    xx: float
    xy: float
    yx: float
    yy: float
    ox: float
    oy: float

    def to_godot(self) -> str:
        """Serialize to Godot text format."""
        parts = [self.xx, self.xy, self.yx, self.yy, self.ox, self.oy]
        return "Transform2D(" + ", ".join(_fmt_float(p) for p in parts) + ")"


# ---------------------------------------------------------------------------
# Transform3D
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Transform3D:
    """3D transformation matrix (3x3 basis + origin)."""

    xx: float
    xy: float
    xz: float
    yx: float
    yy: float
    yz: float
    zx: float
    zy: float
    zz: float
    ox: float
    oy: float
    oz: float

    def to_godot(self) -> str:
        """Serialize to Godot text format."""
        parts = [
            self.xx, self.xy, self.xz,
            self.yx, self.yy, self.yz,
            self.zx, self.zy, self.zz,
            self.ox, self.oy, self.oz,
        ]
        return "Transform3D(" + ", ".join(_fmt_float(p) for p in parts) + ")"


# ---------------------------------------------------------------------------
# AABB
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AABB:
    """Axis-aligned bounding box (position + size in 3D)."""

    x: float
    y: float
    z: float
    sx: float
    sy: float
    sz: float

    def to_godot(self) -> str:
        """Serialize to Godot text format."""
        parts = [self.x, self.y, self.z, self.sx, self.sy, self.sz]
        return "AABB(" + ", ".join(_fmt_float(p) for p in parts) + ")"


# ---------------------------------------------------------------------------
# StringName
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class StringName:
    """Godot StringName (interned string), serialized as &"value"."""

    value: str

    def to_godot(self) -> str:
        """Serialize to Godot text format."""
        return f'&"{self.value}"'


# ---------------------------------------------------------------------------
# NodePath
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class NodePath:
    """Godot NodePath, serialized as NodePath("path")."""

    path: str

    def to_godot(self) -> str:
        """Serialize to Godot text format."""
        return f'NodePath("{self.path}")'


# ---------------------------------------------------------------------------
# Resource references
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ExtResourceRef:
    """Reference to an external resource: ExtResource("id")."""

    id: str

    def to_godot(self) -> str:
        """Serialize to Godot text format."""
        return f'ExtResource("{self.id}")'


@dataclass(frozen=True, slots=True)
class SubResourceRef:
    """Reference to a sub-resource: SubResource("id")."""

    id: str

    def to_godot(self) -> str:
        """Serialize to Godot text format."""
        return f'SubResource("{self.id}")'


# ---------------------------------------------------------------------------
# All Godot value dataclasses for isinstance checks
# ---------------------------------------------------------------------------

_GODOT_TYPES = (
    Vector2, Vector2i, Vector3, Vector3i,
    Rect2, Rect2i, Color,
    Transform2D, Transform3D, AABB,
    StringName, NodePath,
    ExtResourceRef, SubResourceRef,
)


# ---------------------------------------------------------------------------
# Parsing internals
# ---------------------------------------------------------------------------

# Pattern to match a constructor call: TypeName(...)
_CONSTRUCTOR_RE = re.compile(r"^([A-Za-z_]\w*)\(")

# Mapping from constructor names to their factory functions
_FLOAT_CONSTRUCTORS: dict[str, type] = {
    "Vector2": Vector2,
    "Vector3": Vector3,
    "Rect2": Rect2,
    "Color": Color,
    "Transform2D": Transform2D,
    "Transform3D": Transform3D,
    "AABB": AABB,
}

_INT_CONSTRUCTORS: dict[str, type] = {
    "Vector2i": Vector2i,
    "Vector3i": Vector3i,
    "Rect2i": Rect2i,
}


def _find_matching_paren(text: str, start: int) -> int:
    """Find the index of the closing paren matching the one at start.

    Respects nested parentheses and quoted strings.
    """
    depth = 1
    i = start + 1
    length = len(text)
    while i < length and depth > 0:
        ch = text[i]
        if ch == '"':
            # Skip quoted string
            i += 1
            while i < length and text[i] != '"':
                if text[i] == '\\':
                    i += 1  # skip escaped char
                i += 1
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        i += 1
    return i - 1


def _split_args(text: str) -> list[str]:
    """Split a comma-separated argument list, respecting nested delimiters and strings."""
    args: list[str] = []
    depth = 0
    current: list[str] = []
    in_string = False
    i = 0
    length = len(text)
    # Track nesting for parens, brackets, and braces
    _OPENERS = frozenset("([{")
    _CLOSERS = frozenset(")]}")

    while i < length:
        ch = text[i]
        if in_string:
            current.append(ch)
            if ch == '\\' and i + 1 < length:
                i += 1
                current.append(text[i])
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
            current.append(ch)
        elif ch in _OPENERS:
            depth += 1
            current.append(ch)
        elif ch in _CLOSERS:
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1

    remainder = "".join(current).strip()
    if remainder:
        args.append(remainder)
    return args


def _parse_string_content(text: str) -> str:
    """Parse a quoted string, handling escape sequences."""
    # Remove surrounding quotes
    inner = text[1:-1]
    # Process escape sequences
    result: list[str] = []
    i = 0
    while i < len(inner):
        if inner[i] == '\\' and i + 1 < len(inner):
            next_ch = inner[i + 1]
            if next_ch == '"':
                result.append('"')
            elif next_ch == '\\':
                result.append('\\')
            elif next_ch == 'n':
                result.append('\n')
            elif next_ch == 't':
                result.append('\t')
            else:
                result.append('\\')
                result.append(next_ch)
            i += 2
        else:
            result.append(inner[i])
            i += 1
    return "".join(result)


def _parse_array(text: str) -> list[Any]:
    """Parse a Godot array literal: [item1, item2, ...]."""
    inner = text[1:-1].strip()
    if not inner:
        return []
    args = _split_args(inner)
    return [parse_value(a) for a in args]


def _parse_dict(text: str) -> dict[Any, Any]:
    """Parse a Godot dictionary literal: {key: value, ...}."""
    inner = text[1:-1].strip()
    if not inner:
        return {}
    result: dict[Any, Any] = {}
    args = _split_args(inner)
    for arg in args:
        # Split on first colon that is not inside quotes
        colon_idx = _find_colon(arg)
        if colon_idx == -1:
            continue
        key_str = arg[:colon_idx].strip()
        val_str = arg[colon_idx + 1:].strip()
        result[parse_value(key_str)] = parse_value(val_str)
    return result


def _find_colon(text: str) -> int:
    """Find the index of the first colon not inside quotes or nested delimiters."""
    depth = 0
    in_string = False
    for i, ch in enumerate(text):
        if in_string:
            if ch == '\\':
                continue
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == ':' and depth == 0:
            return i
    return -1


# ---------------------------------------------------------------------------
# parse_value
# ---------------------------------------------------------------------------

def parse_value(text: str) -> Any:
    """Parse a Godot value string into the corresponding Python type.

    Handles all Godot constructor forms (Vector2, Rect2, Color, etc.),
    primitives (null, bool, int, float, string), resource references,
    packed arrays, array/dict literals, and StringName syntax.

    Unknown constructors return the raw string per D-04 (lenient parser).
    """
    text = text.strip()

    # null
    if text == "null":
        return None

    # bool
    if text == "true":
        return True
    if text == "false":
        return False

    # StringName: &"value"
    if text.startswith('&"') and text.endswith('"'):
        return StringName(_parse_string_content(text[1:]))

    # Quoted string
    if text.startswith('"') and text.endswith('"'):
        return _parse_string_content(text)

    # Array literal
    if text.startswith("[") and text.endswith("]"):
        return _parse_array(text)

    # Dictionary literal
    if text.startswith("{") and text.endswith("}"):
        return _parse_dict(text)

    # Constructor call: TypeName(...)
    m = _CONSTRUCTOR_RE.match(text)
    if m:
        type_name = m.group(1)
        paren_start = m.end() - 1  # index of '('
        paren_end = _find_matching_paren(text, paren_start)

        inner = text[paren_start + 1:paren_end].strip()
        return _parse_constructor(type_name, inner, text)

    # Integer (check before float since ints have no dot or 'e')
    if _looks_like_integer(text):
        return int(text)

    # Float
    if _looks_like_float(text):
        return float(text)

    # Fallback: return raw string (D-04 lenient)
    return text


def _looks_like_integer(text: str) -> bool:
    """Check if text looks like an integer literal."""
    if not text:
        return False
    start = 1 if text[0] in ('+', '-') else 0
    return text[start:].isdigit() and len(text[start:]) > 0


def _looks_like_float(text: str) -> bool:
    """Check if text looks like a float literal."""
    try:
        float(text)
        return True
    except ValueError:
        return False


def _parse_constructor(type_name: str, inner: str, raw: str) -> Any:
    """Parse a constructor call given the type name and inner arguments."""
    # Float-based constructors
    if type_name in _FLOAT_CONSTRUCTORS:
        args = _split_args(inner)
        float_args = [float(a) for a in args]
        return _FLOAT_CONSTRUCTORS[type_name](*float_args)

    # Integer-based constructors
    if type_name in _INT_CONSTRUCTORS:
        args = _split_args(inner)
        int_args = [int(a) for a in args]
        return _INT_CONSTRUCTORS[type_name](*int_args)

    # NodePath
    if type_name == "NodePath":
        args = _split_args(inner)
        if args and args[0].startswith('"') and args[0].endswith('"'):
            return NodePath(_parse_string_content(args[0]))
        return NodePath(inner)

    # ExtResource
    if type_name == "ExtResource":
        args = _split_args(inner)
        if args and args[0].startswith('"') and args[0].endswith('"'):
            return ExtResourceRef(_parse_string_content(args[0]))
        return ExtResourceRef(inner)

    # SubResource
    if type_name == "SubResource":
        args = _split_args(inner)
        if args and args[0].startswith('"') and args[0].endswith('"'):
            return SubResourceRef(_parse_string_content(args[0]))
        return SubResourceRef(inner)

    # PackedStringArray
    if type_name == "PackedStringArray":
        if not inner:
            return []
        args = _split_args(inner)
        return [_parse_string_content(a) for a in args]

    # PackedFloat32Array / PackedFloat64Array
    if type_name in ("PackedFloat32Array", "PackedFloat64Array"):
        if not inner:
            return []
        args = _split_args(inner)
        return [float(a) for a in args]

    # PackedInt32Array / PackedInt64Array
    if type_name in ("PackedInt32Array", "PackedInt64Array"):
        if not inner:
            return []
        args = _split_args(inner)
        return [int(a) for a in args]

    # PackedByteArray
    if type_name == "PackedByteArray":
        if not inner:
            return b""
        args = _split_args(inner)
        return bytes(int(a) for a in args)

    # Unknown constructor: return raw string per D-04
    return raw


# ---------------------------------------------------------------------------
# serialize_value
# ---------------------------------------------------------------------------

def serialize_value(value: Any) -> str:
    """Convert a Python value to its Godot text format representation.

    For Godot dataclass types, calls .to_godot().
    For primitives, produces Godot-compatible string representations.
    """
    # Godot dataclass types (have to_godot method)
    if isinstance(value, _GODOT_TYPES):
        return value.to_godot()

    # None -> null
    if value is None:
        return "null"

    # Bool before int (bool is a subclass of int in Python)
    if isinstance(value, bool):
        return "true" if value else "false"

    # int
    if isinstance(value, int):
        return str(value)

    # float
    if isinstance(value, float):
        return _fmt_float(value)

    # str
    if isinstance(value, str):
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'

    # bytes
    if isinstance(value, bytes):
        items = ", ".join(str(b) for b in value)
        return f"PackedByteArray({items})"

    # list
    if isinstance(value, list):
        if not value:
            return "[]"
        items = ", ".join(serialize_value(item) for item in value)
        return f"[{items}]"

    # dict
    if isinstance(value, dict):
        if not value:
            return "{}"
        pairs = ", ".join(
            f"{serialize_value(k)}: {serialize_value(v)}"
            for k, v in value.items()
        )
        return f"{{{pairs}}}"

    # Fallback: string representation
    return str(value)


# ---------------------------------------------------------------------------
# GodotJSONEncoder (D-03)
# ---------------------------------------------------------------------------

class GodotJSONEncoder(json.JSONEncoder):
    """JSON encoder that serializes Godot value types as native strings.

    Per D-03, Godot types appear as their Godot text representation in JSON
    output (e.g. Vector2(1.5, 2.0) becomes the JSON string "Vector2(1.5, 2)").
    """

    def default(self, o: Any) -> Any:
        """Encode Godot types as their native string representation."""
        if isinstance(o, _GODOT_TYPES):
            return o.to_godot()
        return super().default(o)
