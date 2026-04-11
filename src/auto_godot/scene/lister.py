"""Scene lister: enumerate and summarize .tscn files in a Godot project.

Walks a project directory, parses all .tscn files, and returns metadata
including node trees, script references, instanced scene paths, and
dependency lists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from auto_godot.formats.tscn import GdScene, SceneNode, parse_tscn_file
from auto_godot.formats.values import ExtResourceRef

if TYPE_CHECKING:
    from pathlib import Path

    from auto_godot.formats.tres import ExtResource


def list_scenes(
    project_root: Path,
    depth: int | None = None,
) -> list[dict[str, Any]]:
    """List all scenes in a Godot project directory with metadata.

    Returns a list of dicts, each containing path (relative to project_root),
    root_type, node_count, node tree, scripts, instances, and dependencies.
    """
    results: list[dict[str, Any]] = []
    for tscn_path in sorted(project_root.rglob("*.tscn")):
        scene = parse_tscn_file(tscn_path)
        entry = _summarize_scene(tscn_path, scene, project_root, depth)
        results.append(entry)
    return results


def _summarize_scene(
    path: Path,
    scene: GdScene,
    root: Path,
    depth: int | None,
) -> dict[str, Any]:
    """Build a per-scene metadata dict."""
    rel_path = str(path.relative_to(root)).replace("\\", "/")
    root_type = scene.nodes[0].type if scene.nodes else None

    scripts = _find_scripts(scene.ext_resources)
    instances = _find_instances(scene.nodes, scene.ext_resources)
    dependencies = [ext.path for ext in scene.ext_resources]
    node_tree = _build_node_tree(scene.nodes, depth)

    return {
        "path": rel_path,
        "root_type": root_type,
        "node_count": len(scene.nodes),
        "nodes": node_tree,
        "scripts": scripts,
        "instances": instances,
        "dependencies": dependencies,
    }


def _find_scripts(ext_resources: list[ExtResource]) -> list[str]:
    """Filter ext_resources for Script types and return their paths."""
    return [ext.path for ext in ext_resources if ext.type == "Script"]


def _find_instances(
    nodes: list[SceneNode],
    ext_resources: list[ExtResource],
) -> list[str]:
    """Resolve instance node references to their scene paths."""
    instances: list[str] = []
    for node in nodes:
        resolved = _resolve_instance_path(node, ext_resources)
        if resolved is not None:
            instances.append(resolved)
    return instances


def _resolve_instance_path(
    node: SceneNode,
    ext_resources: list[ExtResource],
) -> str | None:
    """Resolve an instance ExtResource reference to its scene path."""
    if node.instance is None:
        return None
    # The instance value is stored as a parsed value (ExtResourceRef)
    # or as a raw string like 'ExtResource("1_player")'
    instance_val = node.instance
    ref_id: str | None = None
    if isinstance(instance_val, ExtResourceRef):
        ref_id = instance_val.id
    elif isinstance(instance_val, str):
        # Parse raw string: ExtResource("id")
        ref_id = _extract_ext_resource_id(instance_val)
    if ref_id is None:
        return None
    for ext in ext_resources:
        if ext.id == ref_id:
            return ext.path
    return None


def _extract_ext_resource_id(text: str) -> str | None:
    """Extract the ID from an ExtResource("id") string."""
    prefix = 'ExtResource("'
    if text.startswith(prefix) and text.endswith('")'):
        return text[len(prefix):-2]
    return None


def _build_node_tree(
    nodes: list[SceneNode],
    depth: int | None,
) -> list[dict[str, Any]]:
    """Convert flat node list to nested tree dicts with optional depth limit."""
    if not nodes:
        return []
    tree: list[dict[str, Any]] = []
    for node in nodes:
        node_depth = _compute_depth(node)
        if depth is not None and node_depth > depth:
            continue
        tree.append({
            "name": node.name,
            "type": node.type,
            "parent": node.parent,
        })
    return tree


def _compute_depth(node: SceneNode) -> int:
    """Compute the depth of a node based on its parent path."""
    if node.parent is None:
        return 0
    if node.parent == ".":
        return 1
    # Count path segments: "A/B" = depth 3
    return node.parent.count("/") + 2
