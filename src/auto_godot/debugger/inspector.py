"""Scene inspection functions for live Godot game interaction.

Provides async functions to retrieve and parse the scene tree,
inspect node properties, and format game output/error messages.
All protocol communication flows through DebugSession.send_command().
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from auto_godot.debugger.errors import DebuggerError
from auto_godot.debugger.models import NodeProperty, SceneNode

if TYPE_CHECKING:
    from auto_godot.debugger.session import DebugSession


def parse_scene_tree(
    data: list[Any],
    offset: int = 0,
    parent_path: str = "",
) -> tuple[SceneNode, int]:
    """Parse a single node from the flat depth-first scene tree array.

    Each node occupies 6 consecutive values in the array:
    child_count, name, type_name, instance_id, scene_file_path, view_flags.

    Returns the parsed SceneNode and the new offset after this node
    and all its descendants.
    """
    child_count = data[offset]
    name = data[offset + 1]
    type_name = data[offset + 2]
    instance_id = data[offset + 3]
    scene_file_path = data[offset + 4]
    view_flags = data[offset + 5]
    offset += 6

    path = f"{parent_path}/{name}" if parent_path else f"/{name}"

    children: list[SceneNode] = []
    for _ in range(child_count):
        child, offset = parse_scene_tree(data, offset, path)
        children.append(child)

    node = SceneNode(
        name=name,
        type_name=type_name,
        instance_id=instance_id,
        scene_file_path=scene_file_path,
        view_flags=view_flags,
        path=path,
        children=children,
    )
    return node, offset


def parse_object_properties(
    data: list[Any],
) -> tuple[int, str, list[NodeProperty]]:
    """Parse an inspect_objects response into structured properties.

    The response format is [object_id, class_name, flat_property_array]
    where the property array contains chunks of 6 values each:
    name, type, hint, hint_string, usage, value.

    Properties with usage == 128 are category separators used by the
    Godot editor UI and are skipped.
    """
    obj_id: int = data[0]
    class_name: str = data[1]
    raw_props: list[Any] = data[2]

    props: list[NodeProperty] = []
    i = 0
    while i + 5 < len(raw_props):
        name = raw_props[i]
        prop_type = raw_props[i + 1]
        hint = raw_props[i + 2]
        hint_string = raw_props[i + 3]
        usage = raw_props[i + 4]
        value = raw_props[i + 5]
        i += 6

        # Skip category separators (editor UI sections, not real properties)
        if usage == 128:
            continue

        props.append(NodeProperty(
            name=name,
            type=prop_type,
            hint=hint,
            hint_string=hint_string,
            usage=usage,
            value=value,
        ))

    return obj_id, class_name, props


async def enrich_scene_tree(
    session: DebugSession,
    root: SceneNode,
) -> SceneNode:
    """Populate extended metadata for each node via inspect_objects calls.

    Per D-06: populates class_name, script_path, and groups for every
    node in the tree. This is O(n) network round-trips where n is the
    total number of nodes. For large scenes (1000+ nodes) this can be slow.

    Modifies nodes in place and returns the root.
    """
    queue: deque[SceneNode] = deque([root])
    while queue:
        node = queue.popleft()
        response = await session.send_command(
            "scene:inspect_objects",
            [[node.instance_id], False],
            response_key="scene:inspect_objects",
        )
        _, class_name, props = parse_object_properties(response)

        # Set class_name only when it differs from type_name
        # (indicates a custom script class)
        if class_name != node.type_name:
            node.class_name = class_name
        else:
            node.class_name = None

        # Find script property and extract resource_path
        node.script_path = None
        for prop in props:
            if prop.name == "script" and hasattr(prop.value, "resource_path"):
                node.script_path = prop.value.resource_path
                break

        # Groups are not available via inspect_objects; leave as empty
        # TODO: Groups require scene:get_node_groups or similar protocol
        # message which may not exist. Deferred to future enhancement.

        queue.extend(node.children)

    return root


async def get_scene_tree(
    session: DebugSession,
    max_depth: int | None = None,
    full: bool = False,
) -> SceneNode:
    """Retrieve and parse the live scene tree from the connected game.

    Sends scene:request_scene_tree and parses the flat response into
    a nested SceneNode hierarchy. Optionally prunes depth and/or
    enriches nodes with extended metadata.
    """
    data = await session.send_command(
        "scene:request_scene_tree", [],
        response_key="scene:scene_tree",
    )
    root, _ = parse_scene_tree(data, offset=0, parent_path="")

    if max_depth is not None:
        _prune_depth(root, max_depth)

    if full:
        await enrich_scene_tree(session, root)

    return root


def _prune_depth(
    node: SceneNode,
    max_depth: int,
    current_depth: int = 0,
) -> SceneNode:
    """Prune children beyond max_depth. Mutates in place.

    A max_depth of 0 removes all children from the root.
    A max_depth of 1 keeps direct children but clears their children.
    """
    if current_depth >= max_depth:
        node.children = []
        return node
    for child in node.children:
        _prune_depth(child, max_depth, current_depth + 1)
    return node


async def get_property(
    session: DebugSession,
    node_path: str,
    property_name: str,
) -> object:
    """Read a single property value from a node by its path.

    Resolves the NodePath to an object ID via the scene tree,
    then inspects the object's properties to find the requested one.
    """
    tree = await get_scene_tree(session)
    node = _find_node_by_path(tree, node_path)
    if node is None:
        raise DebuggerError(
            message=f"Node not found: {node_path}",
            code="DEBUG_NODE_NOT_FOUND",
            fix=f"Check that {node_path} exists in the running scene tree",
        )

    response = await session.send_command(
        "scene:inspect_objects",
        [[node.instance_id], False],
        response_key="scene:inspect_objects",
    )
    _, _, props = parse_object_properties(response)

    for prop in props:
        if prop.name == property_name:
            return prop.value

    raise DebuggerError(
        message=f"Property not found: {property_name}",
        code="DEBUG_PROPERTY_NOT_FOUND",
        fix=(
            f"Check property name; "
            f"use debug get --node {node_path} to list available properties"
        ),
    )


def _find_node_by_path(
    root: SceneNode,
    target_path: str,
) -> SceneNode | None:
    """Find a node in the tree by its full path. Returns None if not found."""
    if root.path == target_path:
        return root
    for child in root.children:
        found = _find_node_by_path(child, target_path)
        if found is not None:
            return found
    return None


def format_output_messages(
    raw_output: list[list[Any]],
) -> list[dict[str, str]]:
    """Format raw output buffer entries into structured message dicts.

    Each entry is [[strings], [types]] where types are:
      0 = LOG (maps to "output")
      1 = ERROR (maps to "error")
      2 = LOG_RICH (maps to "output")
    """
    messages: list[dict[str, str]] = []
    for entry in raw_output:
        strings = entry[0]
        types = entry[1]
        for text, msg_type in zip(strings, types, strict=False):
            type_label = "error" if msg_type == 1 else "output"
            messages.append({"text": text, "type": type_label})
    return messages


def format_error_messages(
    raw_errors: list[list[Any]],
) -> list[dict[str, str]]:
    """Format raw error buffer entries into structured error dicts.

    Each error entry from Godot is:
    [error, error_descr, source_file, source_line, source_func,
     warning, hr, min, sec, msec, callstack]
    """
    messages: list[dict[str, str]] = []
    for entry in raw_errors:
        error = entry[0]
        error_descr = entry[1]
        source_file = entry[2]
        source_line = entry[3]
        messages.append({
            "text": f"{error}: {error_descr}",
            "type": "error",
            "source": f"{source_file}:{source_line}",
        })
    return messages
