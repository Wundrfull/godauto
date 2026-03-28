"""Custom project.godot parser with round-trip fidelity.

Parses the INI-like project.godot format handling its unique quirks:
global keys before any section, Godot constructor values (PackedStringArray,
Object, etc.), multi-line values with bracket balancing, and semicolon
comments. All values are stored as raw strings; no interpretation of Godot
constructors is performed at this layer.

Does NOT use Python's configparser (per design decision D-04).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class _State(Enum):
    """Parser state machine states."""

    GLOBAL = auto()
    SECTION = auto()
    MULTILINE = auto()


@dataclass
class ProjectConfig:
    """Parsed project.godot file.

    Stores global keys (before any section header) and per-section
    key-value pairs. All values are raw strings. Round-trip fidelity
    is maintained by preserving the original lines.
    """

    global_keys: list[tuple[str, str]]
    sections: dict[str, list[tuple[str, str]]]
    _raw_lines: list[str] | None = field(default=None, repr=False)

    def get_global(self, key: str) -> str | None:
        """Return the value of a global key, or None if not found."""
        for k, v in self.global_keys:
            if k == key:
                return v
        return None

    def get_value(self, section: str, key: str) -> str | None:
        """Return the value of a key in a section, or None if not found."""
        entries = self.sections.get(section)
        if entries is None:
            return None
        for k, v in entries:
            if k == key:
                return v
        return None

    def section_names(self) -> list[str]:
        """Return the list of section names in parse order."""
        return list(self.sections.keys())

    def keys(self, section: str) -> list[str]:
        """Return the list of keys in a section, or empty list if missing."""
        entries = self.sections.get(section)
        if entries is None:
            return []
        return [k for k, _ in entries]

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict representation."""
        global_dict = {k: v for k, v in self.global_keys}
        sections_dict = {}
        for sec_name, entries in self.sections.items():
            sections_dict[sec_name] = {k: v for k, v in entries}
        return {"global": global_dict, "sections": sections_dict}


def _strip_quotes(value: str) -> str:
    """Strip surrounding double quotes from a value if present."""
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def _bracket_depth(text: str) -> int:
    """Count net bracket depth ({/[ open, }/] close), respecting strings.

    Returns a positive number if brackets are still open.
    """
    depth = 0
    in_string = False
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if in_string:
            if ch == '\\' and i + 1 < length:
                i += 2
                continue
            if ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch in ('{', '[', '('):
                depth += 1
            elif ch in ('}', ']', ')'):
                depth -= 1
        i += 1
    return depth


def parse_project_config(text: str) -> ProjectConfig:
    """Parse a project.godot file into a ProjectConfig.

    Uses a line-based state machine with three states: GLOBAL (before
    first section), SECTION (inside a section), and MULTILINE
    (accumulating a multi-line value with unbalanced brackets).
    """
    lines = text.split("\n")
    # Remove trailing empty string from final newline
    if lines and lines[-1] == "":
        lines = lines[:-1]

    raw_lines: list[str] = []
    global_keys: list[tuple[str, str]] = []
    sections: dict[str, list[tuple[str, str]]] = {}
    current_section: str | None = None
    state = _State.GLOBAL

    # Multi-line accumulation state
    ml_key = ""
    ml_lines: list[str] = []
    ml_depth = 0

    for line in lines:
        raw_lines.append(line)

        if state == _State.MULTILINE:
            ml_lines.append(line)
            ml_depth += _bracket_depth(line)
            if ml_depth <= 0:
                # Multi-line value complete
                value = "\n".join(ml_lines)
                if current_section is not None:
                    sections[current_section].append((ml_key, value))
                state = _State.SECTION
            continue

        stripped = line.rstrip()

        # Empty line
        if stripped == "":
            continue

        # Comment line
        if stripped.startswith(";"):
            continue

        # Section header
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1]
            if current_section not in sections:
                sections[current_section] = []
            state = _State.SECTION
            continue

        # Key=value pair
        eq_idx = stripped.find("=")
        if eq_idx != -1:
            key = stripped[:eq_idx]
            value = stripped[eq_idx + 1:]

            # Check if value has unbalanced brackets (multi-line start)
            depth = _bracket_depth(value)
            if depth > 0:
                ml_key = key
                ml_lines = [value]
                ml_depth = depth
                state = _State.MULTILINE
                continue

            # Strip quotes for simple string values
            display_value = _strip_quotes(value)

            if state == _State.GLOBAL:
                global_keys.append((key, display_value))
            elif current_section is not None:
                sections[current_section].append((key, display_value))

    return ProjectConfig(
        global_keys=global_keys,
        sections=sections,
        _raw_lines=raw_lines,
    )


def serialize_project_config(config: ProjectConfig) -> str:
    """Serialize a ProjectConfig back to project.godot text format.

    If the config was parsed from text (has _raw_lines), returns the
    original text for perfect round-trip fidelity. Otherwise,
    reconstructs from the data model.
    """
    if config._raw_lines is not None:
        return "\n".join(config._raw_lines) + "\n"

    parts: list[str] = []

    # Global keys
    for key, value in config.global_keys:
        parts.append(f"{key}={value}")
    if config.global_keys:
        parts.append("")

    # Sections
    for section_name, entries in config.sections.items():
        parts.append(f"[{section_name}]")
        parts.append("")
        for key, value in entries:
            parts.append(f"{key}={value}")
        parts.append("")

    return "\n".join(parts) + "\n"
