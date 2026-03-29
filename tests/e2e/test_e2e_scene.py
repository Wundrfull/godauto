"""E2E tests: scenes load in headless Godot."""

from __future__ import annotations

from pathlib import Path

import pytest

from gdauto.backend import GodotBackend
from gdauto.formats.tscn import serialize_tscn_file
from gdauto.scene.builder import build_scene


_PROJECT_GODOT = (
    "; Engine configuration file.\n"
    "config_version=5\n\n"
    "[application]\nconfig/name=\"E2ETest\"\n"
)


def _build_scene_validation_script(tscn_name: str, expected_type: str) -> str:
    """Create a GDScript that loads and validates a PackedScene.

    Checks: scene loads, can be instantiated, root node type matches,
    and reports child count.
    """
    return (
        "extends SceneTree\n"
        "\n"
        "func _init() -> void:\n"
        f'    var packed = load("res://{tscn_name}")\n'
        "    if packed == null:\n"
        '        print("VALIDATION_FAIL: Could not load scene")\n'
        "        quit(1)\n"
        "    if not packed is PackedScene:\n"
        '        print("VALIDATION_FAIL: Resource is not PackedScene, got " + packed.get_class())\n'
        "        quit(1)\n"
        "    var instance = packed.instantiate()\n"
        "    if instance == null:\n"
        '        print("VALIDATION_FAIL: Could not instantiate scene")\n'
        "        quit(1)\n"
        f'    if instance.get_class() != "{expected_type}":\n'
        '        print("VALIDATION_FAIL: Root type is " + instance.get_class()'
        f' + ", expected {expected_type}")\n'
        "        quit(1)\n"
        "    var children = instance.get_child_count()\n"
        '    print("VALIDATION_OK: root=" + instance.get_class()'
        ' + " children=" + str(children))\n'
        "    instance.queue_free()\n"
        "    quit(0)\n"
    )


@pytest.mark.requires_godot
def test_scene_loads_in_godot(
    tmp_path: Path, godot_backend: GodotBackend
) -> None:
    """Build a scene from JSON definition and validate in headless Godot."""
    # 1. Build a simple scene
    definition = {
        "root": {
            "name": "TestScene",
            "type": "Node2D",
            "children": [
                {
                    "name": "Sprite",
                    "type": "Sprite2D",
                    "properties": {
                        "position": "Vector2(10, 20)",
                    },
                },
            ],
        },
    }
    scene = build_scene(definition)

    # 2. Write to tmp_path
    tscn_path = tmp_path / "test_scene.tscn"
    serialize_tscn_file(scene, tscn_path)

    # 3. Create project.godot
    (tmp_path / "project.godot").write_text(_PROJECT_GODOT)

    # 4. Create and run validation script
    script = _build_scene_validation_script("test_scene.tscn", "Node2D")
    script_path = tmp_path / "validate.gd"
    script_path.write_text(script)

    result = godot_backend.run(
        ["--headless", "--script", str(script_path)],
        project_path=tmp_path,
    )
    assert "VALIDATION_OK" in result.stdout
    assert "children=" in result.stdout
