"""Scene builder: convert JSON definitions to GdScene instances.

Transforms a nested JSON tree describing a scene hierarchy into a flat
list of SceneNode instances with correct Godot parent paths, ready for
.tscn serialization.
"""

from __future__ import annotations

from typing import Any

from auto_godot.errors import ValidationError
from auto_godot.formats.tres import ExtResource
from auto_godot.formats.tscn import GdScene, SceneNode
from auto_godot.formats.uid import generate_resource_id, generate_uid, uid_to_text
from auto_godot.formats.values import ExtResourceRef, parse_value


def build_scene(definition: dict[str, Any]) -> GdScene:
    """Build a GdScene from a JSON definition dict.

    The definition must have a "root" key with "name" and "type". Children
    are nested under "children" arrays. An optional "resources" array
    creates ext_resources and assigns them to target nodes.
    """
    _validate_definition(definition)

    root_def = definition["root"]
    nodes = _flatten_nodes(root_def)

    ext_resources: list[ExtResource] = []
    resources_defs = definition.get("resources", [])
    if resources_defs:
        ext_resources = _build_ext_resources(resources_defs)
        _assign_resources(nodes, resources_defs, ext_resources)

    # Auto-create ExtResource entries for script properties (issue #9)
    _promote_script_properties(nodes, ext_resources)

    uid = uid_to_text(generate_uid())

    return GdScene(
        format=3,
        uid=uid,
        load_steps=None,
        ext_resources=ext_resources,
        sub_resources=[],
        nodes=nodes,
        connections=[],
    )


def _validate_definition(definition: dict[str, Any]) -> None:
    """Validate the top-level structure of a scene definition."""
    if "root" not in definition:
        raise ValidationError(
            message="Scene definition missing 'root' key",
            code="INVALID_SCENE_DEFINITION",
            fix="Provide a JSON object with root.name and root.type",
        )
    root = definition["root"]
    if "name" not in root:
        raise ValidationError(
            message="Root node missing 'name'",
            code="INVALID_SCENE_DEFINITION",
            fix="Provide a JSON object with root.name and root.type",
        )
    if "type" not in root:
        raise ValidationError(
            message="Root node missing 'type'",
            code="INVALID_SCENE_DEFINITION",
            fix="Provide a JSON object with root.name and root.type",
        )


def _flatten_nodes(root_def: dict[str, Any]) -> list[SceneNode]:
    """Recursively flatten a nested node tree into a list with parent paths."""
    nodes: list[SceneNode] = []
    root_node = _build_node(root_def, parent_path=None)
    nodes.append(root_node)
    _collect_children(root_def, parent_path=".", nodes=nodes)
    return nodes


def _collect_children(
    node_def: dict[str, Any],
    parent_path: str,
    nodes: list[SceneNode],
) -> None:
    """Recursively collect child nodes, computing Godot parent paths."""
    children = node_def.get("children", [])
    for child_def in children:
        child_node = _build_node(child_def, parent_path=parent_path)
        nodes.append(child_node)
        # Compute the path for this child's own children
        if parent_path == ".":
            next_parent = child_def["name"]
        else:
            next_parent = f"{parent_path}/{child_def['name']}"
        _collect_children(child_def, next_parent, nodes)


def _build_node(
    node_def: dict[str, Any],
    parent_path: str | None,
) -> SceneNode:
    """Create a single SceneNode from a definition dict."""
    props = _parse_properties(node_def.get("properties", {}))
    return SceneNode(
        name=node_def["name"],
        type=node_def.get("type"),
        parent=parent_path,
        properties=props,
    )


def _parse_properties(props: dict[str, str]) -> dict[str, Any]:
    """Convert string property values to typed Godot values via parse_value."""
    return {key: parse_value(val) for key, val in props.items()}


def _build_ext_resources(
    resources: list[dict[str, str]],
) -> list[ExtResource]:
    """Create ExtResource instances from a resources definition array."""
    result: list[ExtResource] = []
    for res_def in resources:
        ext = ExtResource(
            type=res_def["type"],
            path=res_def["path"],
            id=generate_resource_id(res_def["type"]),
            uid=uid_to_text(generate_uid()),
        )
        result.append(ext)
    return result


def _assign_resources(
    nodes: list[SceneNode],
    resources: list[dict[str, str]],
    ext_resources: list[ExtResource],
) -> None:
    """Assign ExtResourceRef properties to target nodes."""
    node_map = {n.name: n for n in nodes}
    for res_def, ext in zip(resources, ext_resources, strict=False):
        target_name = res_def["assign_to"]
        prop_name = res_def["property"]
        if target_name in node_map:
            node_map[target_name].properties[prop_name] = ExtResourceRef(ext.id)


def _promote_script_properties(
    nodes: list[SceneNode],
    ext_resources: list[ExtResource],
) -> None:
    """Convert raw string script paths to proper ExtResource references.

    When a node has a "script" property with a res:// string value,
    creates an ExtResource of type "Script" and replaces the raw string
    with an ExtResourceRef so Godot can load the script at runtime.
    """
    for node in nodes:
        script_val = node.properties.get("script")
        if not isinstance(script_val, str) or not script_val.startswith("res://"):
            continue
        ext = ExtResource(
            type="Script",
            path=script_val,
            id=generate_resource_id("Script"),
            uid=uid_to_text(generate_uid()),
        )
        ext_resources.append(ext)
        node.properties["script"] = ExtResourceRef(ext.id)
