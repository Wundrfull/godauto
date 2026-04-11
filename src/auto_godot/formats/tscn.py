""".tscn parser and serializer with round-trip fidelity.

Parses Godot .tscn (text scene) files into GdScene dataclasses and
serializes them back with byte-identical output for unmodified files.

Per D-06, this module owns .tscn parse/serialize. It reuses the shared
bracket-section parser from common.py and data models from tres.py.
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
from auto_godot.formats.tres import (
    ExtResource,
    SubResource,
    _extract_ext_resource,
    _extract_sub_resource,
)
from auto_godot.formats.values import serialize_value

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class SceneNode:
    """A [node] section."""

    name: str
    type: str | None  # None for instance nodes
    parent: str | None  # None for root node
    properties: dict[str, Any] = field(default_factory=dict)
    instance: str | None = None
    owner: str | None = None
    groups: list[str] | None = None
    unique_id: int | None = None
    raw_section: Section | None = None


@dataclass
class Connection:
    """A [connection] section."""

    signal: str
    from_node: str  # "from" is Python keyword
    to_node: str
    method: str
    flags: int | None = None
    binds: list[Any] | None = None
    raw_section: Section | None = None


@dataclass
class GdScene:
    """A parsed .tscn file."""

    format: int
    uid: str | None
    load_steps: int | None
    ext_resources: list[ExtResource]
    sub_resources: list[SubResource]
    nodes: list[SceneNode]
    connections: list[Connection]
    _raw_header: HeaderAttributes | None = None
    _raw_sections: list[Section] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
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
                        k: serialize_value(v)
                        for k, v in sub.properties.items()
                    },
                }
                for sub in self.sub_resources
            ],
            "nodes": [
                {
                    "name": node.name,
                    "type": node.type,
                    "parent": node.parent,
                    "unique_id": node.unique_id,
                    "properties": {
                        k: serialize_value(v)
                        for k, v in node.properties.items()
                    },
                }
                for node in self.nodes
            ],
            "connections": [
                {
                    "signal": conn.signal,
                    "from": conn.from_node,
                    "to": conn.to_node,
                    "method": conn.method,
                }
                for conn in self.connections
            ],
        }


def _extract_node(section: Section) -> SceneNode:
    """Build a SceneNode from a parsed [node] section."""
    attrs = section.header.attrs
    props = {k: v for k, v in section.properties if k != ""}
    unique_id_str = attrs.get("unique_id")

    # Parse groups from header: groups=["group1", "group2"]
    groups = None
    groups_str = attrs.get("groups")
    if groups_str:
        groups = _parse_groups_attr(groups_str)

    return SceneNode(
        name=attrs.get("name", ""),
        type=attrs.get("type"),
        parent=attrs.get("parent"),
        properties=props,
        instance=attrs.get("instance"),
        owner=attrs.get("owner"),
        groups=groups,
        unique_id=int(unique_id_str) if unique_id_str else None,
        raw_section=section,
    )


def _parse_groups_attr(raw: str) -> list[str]:
    """Parse groups attribute value like '["g1", "g2"]' into a list."""
    import re
    return re.findall(r'"([^"]*)"', raw)


def _extract_connection(section: Section) -> Connection:
    """Build a Connection from a parsed [connection] section."""
    attrs = section.header.attrs
    flags_str = attrs.get("flags")
    return Connection(
        signal=attrs.get("signal", ""),
        from_node=attrs.get("from", ""),
        to_node=attrs.get("to", ""),
        method=attrs.get("method", ""),
        flags=int(flags_str) if flags_str else None,
        raw_section=section,
    )


def parse_tscn(text: str) -> GdScene:
    """Parse a .tscn file into a GdScene.

    Calls the shared bracket-section parser and classifies sections
    as ext_resource, sub_resource, node, or connection.
    """
    header, sections = parse_sections(text)

    ext_resources: list[ExtResource] = []
    sub_resources: list[SubResource] = []
    nodes: list[SceneNode] = []
    connections: list[Connection] = []

    for section in sections:
        tag = section.header.tag
        if tag == "ext_resource":
            ext_resources.append(_extract_ext_resource(section))
        elif tag == "sub_resource":
            sub_resources.append(_extract_sub_resource(section))
        elif tag == "node":
            nodes.append(_extract_node(section))
        elif tag == "connection":
            connections.append(_extract_connection(section))
        # Other sections (editable, etc.) are preserved via raw_sections

    load_steps_str = header.attrs.get("load_steps")
    load_steps = int(load_steps_str) if load_steps_str else None

    return GdScene(
        format=int(header.attrs.get("format", "3")),
        uid=header.attrs.get("uid"),
        load_steps=load_steps,
        ext_resources=ext_resources,
        sub_resources=sub_resources,
        nodes=nodes,
        connections=connections,
        _raw_header=header,
        _raw_sections=sections,
    )


def parse_tscn_file(path: Path) -> GdScene:
    """Read a .tscn file and parse it into a GdScene."""
    return parse_tscn(path.read_text())


def serialize_tscn(scene: GdScene) -> str:
    """Serialize a GdScene back to .tscn text format.

    Uses raw sections for round-trip fidelity when available.
    """
    if scene._raw_header is not None and scene._raw_sections is not None:
        return serialize_sections(
            scene._raw_header,
            scene._raw_sections,
        )
    return _build_tscn_from_model(scene)


def serialize_tscn_file(scene: GdScene, path: Path) -> None:
    """Serialize a GdScene and write to a file."""
    path.write_text(serialize_tscn(scene))


def _build_tscn_from_model(scene: GdScene) -> str:
    """Build .tscn text from the data model (no raw sections)."""
    lines: list[str] = []

    # File header
    parts = []
    if scene.load_steps is not None:
        parts.append(f"load_steps={scene.load_steps}")
    parts.append(f"format={scene.format}")
    if scene.uid:
        parts.append(f'uid="{scene.uid}"')
    lines.append("[gd_scene " + " ".join(parts) + "]")

    # ext_resources
    for ext in scene.ext_resources:
        parts = [f'type="{ext.type}"']
        if ext.uid:
            parts.append(f'uid="{ext.uid}"')
        parts.append(f'path="{ext.path}"')
        parts.append(f'id="{ext.id}"')
        lines.append("")
        lines.append("[ext_resource " + " ".join(parts) + "]")

    # sub_resources
    for sub in scene.sub_resources:
        lines.append("")
        lines.append(f'[sub_resource type="{sub.type}" id="{sub.id}"]')
        for key, val in sub.properties.items():
            lines.append(f"{key} = {serialize_value(val)}")

    # nodes
    for node in scene.nodes:
        lines.append("")
        parts = [f'name="{node.name}"']
        if node.type:
            parts.append(f'type="{node.type}"')
        if node.parent:
            parts.append(f'parent="{node.parent}"')
        if node.instance:
            parts.append(f"instance={node.instance}")
        if node.groups:
            groups_str = ", ".join(f'"{g}"' for g in node.groups)
            parts.append(f"groups=[{groups_str}]")
        if node.unique_id is not None:
            parts.append(f"unique_id={node.unique_id}")
        lines.append("[node " + " ".join(parts) + "]")
        for key, val in node.properties.items():
            lines.append(f"{key} = {serialize_value(val)}")

    # connections
    for conn in scene.connections:
        lines.append("")
        parts = [
            f'signal="{conn.signal}"',
            f'from="{conn.from_node}"',
            f'to="{conn.to_node}"',
            f'method="{conn.method}"',
        ]
        lines.append("[connection " + " ".join(parts) + "]")

    return "\n".join(lines) + "\n"
