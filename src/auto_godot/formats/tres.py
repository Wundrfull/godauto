""".tres parser and serializer with round-trip fidelity.

Parses Godot .tres (text resource) files into GdResource dataclasses and
serializes them back with byte-identical output for unmodified files.

Per D-06, this module owns .tres parse/serialize. It reuses the shared
bracket-section parser from common.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from auto_godot.formats.common import (
    HeaderAttributes,
    Section,
    parse_sections,
    serialize_sections,
)
from auto_godot.formats.values import serialize_value

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class ExtResource:
    """An [ext_resource] section."""

    type: str
    path: str
    id: str
    uid: str | None = None
    raw_section: Section | None = None


@dataclass
class SubResource:
    """A [sub_resource] section with properties."""

    type: str
    id: str
    properties: dict[str, Any] = field(default_factory=dict)
    raw_section: Section | None = None


@dataclass
class GdResource:
    """A parsed .tres file."""

    type: str
    format: int
    uid: str | None
    load_steps: int | None
    ext_resources: list[ExtResource]
    sub_resources: list[SubResource]
    resource_properties: dict[str, Any]
    _raw_header: HeaderAttributes | None = None
    _raw_sections: list[Section] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict for resource inspect."""
        return {
            "type": self.type,
            "format": self.format,
            "uid": self.uid,
            "load_steps": self.load_steps,
            "ext_resources": [
                {
                    "type": ext.type,
                    "path": ext.path,
                    "id": ext.id,
                    "uid": ext.uid,
                }
                for ext in self.ext_resources
            ],
            "sub_resources": [
                {
                    "type": sub.type,
                    "id": sub.id,
                    "properties": {
                        k: serialize_value(v) for k, v in sub.properties.items()
                    },
                }
                for sub in self.sub_resources
            ],
            "properties": {
                k: serialize_value(v) for k, v in self.resource_properties.items()
            },
        }


def _extract_ext_resource(section: Section) -> ExtResource:
    """Build an ExtResource from a parsed [ext_resource] section."""
    attrs = section.header.attrs
    return ExtResource(
        type=attrs.get("type", ""),
        path=attrs.get("path", ""),
        id=attrs.get("id", ""),
        uid=attrs.get("uid"),
        raw_section=section,
    )


def _extract_sub_resource(section: Section) -> SubResource:
    """Build a SubResource from a parsed [sub_resource] section."""
    attrs = section.header.attrs
    props = {k: v for k, v in section.properties if k != ""}
    return SubResource(
        type=attrs.get("type", ""),
        id=attrs.get("id", ""),
        properties=props,
        raw_section=section,
    )


def _extract_resource_properties(section: Section) -> dict[str, Any]:
    """Extract key-value properties from a [resource] section."""
    return {k: v for k, v in section.properties if k != ""}


def parse_tres(text: str) -> GdResource:
    """Parse a .tres file into a GdResource.

    Calls the shared bracket-section parser and classifies sections
    as ext_resource, sub_resource, or resource.
    """
    header, sections = parse_sections(text)

    ext_resources: list[ExtResource] = []
    sub_resources: list[SubResource] = []
    resource_properties: dict[str, Any] = {}

    for section in sections:
        tag = section.header.tag
        if tag == "ext_resource":
            ext_resources.append(_extract_ext_resource(section))
        elif tag == "sub_resource":
            sub_resources.append(_extract_sub_resource(section))
        elif tag == "resource":
            resource_properties = _extract_resource_properties(section)

    load_steps_str = header.attrs.get("load_steps")
    load_steps = int(load_steps_str) if load_steps_str else None

    return GdResource(
        type=header.attrs.get("type", ""),
        format=int(header.attrs.get("format", "3")),
        uid=header.attrs.get("uid"),
        load_steps=load_steps,
        ext_resources=ext_resources,
        sub_resources=sub_resources,
        resource_properties=resource_properties,
        _raw_header=header,
        _raw_sections=sections,
    )


def parse_tres_file(path: Path) -> GdResource:
    """Read a .tres file and parse it into a GdResource."""
    return parse_tres(path.read_text())


def serialize_tres(resource: GdResource) -> str:
    """Serialize a GdResource back to .tres text format.

    Uses raw sections for round-trip fidelity when available.
    """
    if resource._raw_header is not None and resource._raw_sections is not None:
        return serialize_sections(
            resource._raw_header,
            resource._raw_sections,
        )
    # Fallback: build from data model (no raw sections available)
    return _build_tres_from_model(resource)


def serialize_tres_file(resource: GdResource, path: Path) -> None:
    """Serialize a GdResource and write to a file."""
    path.write_text(serialize_tres(resource))


def _build_tres_from_model(resource: GdResource) -> str:
    """Build .tres text from the data model (no raw sections)."""
    lines: list[str] = []

    # File header
    parts = [f'type="{resource.type}"']
    if resource.load_steps is not None:
        parts.append(f"load_steps={resource.load_steps}")
    parts.append(f"format={resource.format}")
    if resource.uid:
        parts.append(f'uid="{resource.uid}"')
    lines.append("[gd_resource " + " ".join(parts) + "]")

    # ext_resources
    for ext in resource.ext_resources:
        parts = [f'type="{ext.type}"']
        if ext.uid:
            parts.append(f'uid="{ext.uid}"')
        parts.append(f'path="{ext.path}"')
        parts.append(f'id="{ext.id}"')
        lines.append("")
        lines.append("[ext_resource " + " ".join(parts) + "]")

    # sub_resources
    for sub in resource.sub_resources:
        lines.append("")
        lines.append(f'[sub_resource type="{sub.type}" id="{sub.id}"]')
        for key, val in sub.properties.items():
            lines.append(f"{key} = {serialize_value(val)}")

    # [resource] section
    if resource.resource_properties:
        lines.append("")
        lines.append("[resource]")
        for key, val in resource.resource_properties.items():
            lines.append(f"{key} = {serialize_value(val)}")

    return "\n".join(lines) + "\n"
