"""Shared bracket-section parsing for Godot .tres/.tscn files.

Provides the core state-machine parser that reads bracket-section format
files into structured Section objects, and serializes them back with
round-trip fidelity (comment/whitespace preservation per D-05, FMT-06).

The parser stores both parsed values and raw value strings for each property,
enabling exact round-trip serialization while still providing typed access
for inspection and manipulation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from auto_godot.formats.values import parse_value

# Pattern matching a section header: [tag key="value" key2=value2 ...]
_HEADER_RE = re.compile(r"^\[(\w+)(.*)?\]\s*$")

# Pattern matching a key = value property line
# Keys may contain word chars, colons, and slashes for Godot's tile
# coordinate properties (e.g., "0:0/terrain_set", "sources/0")
_PROPERTY_RE = re.compile(r"^([\w:/]+)\s*=\s*(.*)$")

# Pattern for constructor attribute values: key=Type("value")
_ATTR_CONSTRUCTOR_RE = re.compile(r'(\w+)\s*=\s*([A-Za-z_]\w*\("[^"]*"\))')
# Pattern for array attribute values in headers: key=["val1", "val2"]
_ATTR_ARRAY_RE = re.compile(r'(\w+)\s*=\s*(\[[^\]]*\])')
# Pattern for quoted attribute values in headers: key="value"
_ATTR_QUOTED_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
# Pattern for unquoted attribute values in headers: key=value
_ATTR_UNQUOTED_RE = re.compile(r"(\w+)\s*=\s*([^\s\]\"]+)")


@dataclass
class HeaderAttributes:
    """Parsed attributes from a bracket section header."""

    tag: str  # e.g., "gd_resource", "ext_resource", "node"
    attrs: dict[str, str]  # key=value pairs from header
    raw_line: str = ""  # Original header line for round-trip fidelity


@dataclass
class Section:
    """A parsed section from a .tres/.tscn file."""

    header: HeaderAttributes
    properties: list[tuple[str, Any]]  # Ordered (key, parsed_value)
    raw_properties: list[tuple[str, str]]  # Ordered (key, raw_value_string)
    leading_whitespace: list[str] = field(default_factory=list)
    trailing_content: str | None = None  # Preserved trailing text


def parse_section_header(line: str) -> HeaderAttributes | None:
    """Parse a [tag key=value ...] line into HeaderAttributes.

    Returns None if the line is not a valid section header.
    Handles quoted values (type="SpriteFrames"), unquoted values (format=3),
    and bare tags ([resource]). Stores the raw line for round-trip fidelity.
    """
    raw_line = line.strip()
    m = _HEADER_RE.match(raw_line)
    if not m:
        return None
    tag = m.group(1)
    rest = m.group(2) or ""

    attrs: dict[str, str] = {}

    # Collect all attribute matches with their positions to preserve order.
    # Constructor values (e.g. instance=ExtResource("id")) are checked first
    # since they contain quotes that would confuse the quoted/unquoted patterns.
    all_attrs: list[tuple[int, str, str]] = []

    for cm in _ATTR_CONSTRUCTOR_RE.finditer(rest):
        all_attrs.append((cm.start(), cm.group(1), cm.group(2)))

    for am in _ATTR_ARRAY_RE.finditer(rest):
        key = am.group(1)
        if not any(k == key for _, k, _ in all_attrs):
            all_attrs.append((am.start(), key, am.group(2)))

    for qm in _ATTR_QUOTED_RE.finditer(rest):
        key = qm.group(1)
        if not any(k == key for _, k, _ in all_attrs):
            all_attrs.append((qm.start(), key, qm.group(2)))

    for um in _ATTR_UNQUOTED_RE.finditer(rest):
        key = um.group(1)
        # Skip if already found as constructor or quoted
        if not any(k == key for _, k, _ in all_attrs):
            all_attrs.append((um.start(), key, um.group(2)))

    # Sort by position to preserve original order
    all_attrs.sort(key=lambda x: x[0])
    for _, key, val in all_attrs:
        attrs[key] = val

    return HeaderAttributes(tag=tag, attrs=attrs, raw_line=raw_line)


def _count_bracket_depth(text: str) -> int:
    """Count net bracket depth in text, ignoring brackets inside strings.

    Tracks {, [, ( as openers and }, ], ) as closers.
    Handles escaped quotes inside double-quoted strings.
    """
    depth = 0
    in_string = False
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if in_string:
            if ch == "\\" and i + 1 < length:
                i += 2  # skip escaped character
                continue
            if ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch in ("{", "[", "("):
                depth += 1
            elif ch in ("}", "]", ")"):
                depth -= 1
        i += 1
    return depth


def parse_sections(text: str) -> tuple[HeaderAttributes, list[Section]]:
    """Parse a .tres/.tscn file into a file header and list of sections.

    Uses a line-by-line state machine with three states:
    - IDLE: looking for section headers, accumulating blank lines/comments
    - PROPERTIES: inside a section, reading key=value pairs
    - MULTILINE: accumulating a multi-line value (unbalanced brackets)

    Returns (file_header, sections) where file_header is the first
    [gd_resource] or [gd_scene] header, and sections is an ordered list
    of all sections including ext_resource, sub_resource, node, etc.
    """
    lines = text.split("\n")
    # Remove trailing empty string from final newline
    if lines and lines[-1] == "":
        lines = lines[:-1]

    file_header: HeaderAttributes | None = None
    sections: list[Section] = []
    current_section: Section | None = None
    pending_whitespace: list[str] = []

    # Multi-line accumulation state
    multiline_key: str | None = None
    multiline_buffer: list[str] = []
    multiline_depth: int = 0

    for line in lines:
        stripped = line.rstrip("\r")

        # Check if this is a section header
        if stripped.startswith("[") and not (multiline_key is not None):
            header = parse_section_header(stripped)
            if header is not None:
                # Finalize any current section
                if current_section is not None:
                    sections.append(current_section)
                elif file_header is None and pending_whitespace:
                    # Whitespace before file header: discard or store
                    pass

                if file_header is None:
                    file_header = header
                    # File header section does not become a regular section
                    # but we still need to handle its content
                    current_section = Section(
                        header=header,
                        properties=[],
                        raw_properties=[],
                        leading_whitespace=pending_whitespace[:],
                    )
                else:
                    current_section = Section(
                        header=header,
                        properties=[],
                        raw_properties=[],
                        leading_whitespace=pending_whitespace[:],
                    )
                pending_whitespace = []
                continue

        # In multiline accumulation mode
        if multiline_key is not None:
            multiline_buffer.append(stripped)
            multiline_depth += _count_bracket_depth(stripped)
            if multiline_depth <= 0:
                # Multi-line value complete
                raw_val = "\n".join(multiline_buffer)
                parsed_val = parse_value(raw_val)
                if current_section is not None:
                    current_section.properties.append((multiline_key, parsed_val))
                    current_section.raw_properties.append((multiline_key, raw_val))
                multiline_key = None
                multiline_buffer = []
                multiline_depth = 0
            continue

        # Empty or blank line
        if stripped == "" or stripped.isspace():
            pending_whitespace.append(stripped)
            continue

        # Comment line (starts with ;)
        if stripped.startswith(";"):
            pending_whitespace.append(stripped)
            continue

        # Property line: key = value
        prop_match = _PROPERTY_RE.match(stripped)
        if prop_match and current_section is not None:
            key = prop_match.group(1)
            raw_val = prop_match.group(2)

            # If there is pending whitespace, attach to section as comments
            if pending_whitespace:
                # Attach as leading whitespace for next logical group
                # For round-trip, store in raw_properties as blank/comment lines
                for ws_line in pending_whitespace:
                    current_section.raw_properties.append(("", ws_line))
                    current_section.properties.append(("", ws_line))
                pending_whitespace = []

            # Check bracket balance for multi-line values
            depth = _count_bracket_depth(raw_val)
            if depth > 0:
                # Unbalanced: start multiline accumulation
                multiline_key = key
                multiline_buffer = [raw_val]
                multiline_depth = depth
            else:
                parsed_val = parse_value(raw_val)
                current_section.properties.append((key, parsed_val))
                current_section.raw_properties.append((key, raw_val))
            continue

        # Unrecognized line: treat as raw content (preserve per D-04)
        if current_section is not None:
            if pending_whitespace:
                for ws_line in pending_whitespace:
                    current_section.raw_properties.append(("", ws_line))
                    current_section.properties.append(("", ws_line))
                pending_whitespace = []
            current_section.raw_properties.append(("", stripped))
            current_section.properties.append(("", stripped))
        else:
            pending_whitespace.append(stripped)

    # Finalize last section
    if current_section is not None:
        # Attach any trailing whitespace
        if pending_whitespace:
            current_section.trailing_content = "\n".join(pending_whitespace)
        sections.append(current_section)

    # The file header is sections[0] if any sections exist
    if file_header is None:
        # Fallback: create an empty header
        file_header = HeaderAttributes(tag="unknown", attrs={})
    if sections:
        sections[0]
        # The first section IS the file header; remaining are body sections
        return file_header, sections[1:]
    return file_header, []


def _format_header(attrs: HeaderAttributes) -> str:
    """Format HeaderAttributes back to a [tag key=value ...] line.

    Uses the stored raw_line for round-trip fidelity when available.
    Falls back to reconstructing from attrs when no raw line exists.
    """
    if attrs.raw_line:
        return attrs.raw_line
    parts = [attrs.tag]
    for key, val in attrs.attrs.items():
        # Quote values that are not purely numeric
        if val.isdigit() or (val.startswith("-") and val[1:].isdigit()):
            parts.append(f"{key}={val}")
        else:
            parts.append(f'{key}="{val}"')
    return "[" + " ".join(parts) + "]"


def serialize_sections(
    header: HeaderAttributes,
    sections: list[Section],
    file_header_section: Section | None = None,
) -> str:
    """Reconstruct a .tres/.tscn file from header and sections.

    Uses raw_properties for round-trip fidelity. If a section has
    raw_properties, those are used directly instead of re-serializing
    parsed values.

    Args:
        header: The file header (gd_resource or gd_scene).
        sections: The body sections in order.
        file_header_section: The Section for the file header line, if
            it had properties (like [resource] in .tres). If None,
            the file header has no body properties.
    """
    lines: list[str] = []

    # File header line
    lines.append(_format_header(header))

    # File header section properties (if any)
    if file_header_section is not None:
        for key, raw_val in file_header_section.raw_properties:
            if key == "":
                lines.append(raw_val)
            else:
                lines.append(f"{key} = {raw_val}")

    # Body sections
    for section in sections:
        # Leading whitespace (blank lines, comments before this section)
        for ws_line in section.leading_whitespace:
            lines.append(ws_line)

        # Section header
        lines.append(_format_header(section.header))

        # Properties
        for key, raw_val in section.raw_properties:
            if key == "":
                # Blank line or comment preserved
                lines.append(raw_val)
            else:
                lines.append(f"{key} = {raw_val}")

        # Trailing content
        if section.trailing_content is not None:
            lines.append(section.trailing_content)

    # Ensure trailing newline
    return "\n".join(lines) + "\n"
