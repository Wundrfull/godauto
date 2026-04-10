"""E2E tests: scenes load in headless Godot."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_godot.backend import GodotBackend
from auto_godot.formats.tscn import parse_tscn, serialize_tscn, serialize_tscn_file
from auto_godot.scene.builder import build_scene


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


@pytest.mark.requires_godot
def test_scene_unique_id_round_trip(
    tmp_path: Path, godot_backend: GodotBackend
) -> None:
    """Validate .tscn with unique_id round-trips and loads in Godot (VAL-03).

    Parses a hand-crafted .tscn with unique_id on nodes, serializes it back,
    verifies unique_id preserved in text, and confirms the file loads in Godot.
    """
    # 1. Create a hand-crafted .tscn with unique_id on nodes
    tscn_content = (
        "[gd_scene format=3]\n"
        "\n"
        '[node name="Root" type="Node2D" unique_id=42]\n'
        "\n"
        '[node name="Child" type="Sprite2D" parent="." unique_id=99]\n'
        "position = Vector2(10, 20)\n"
    )

    # 2. Parse and serialize back (round-trip)
    scene = parse_tscn(tscn_content)
    round_tripped = serialize_tscn(scene)

    # 3. Python-side assertions: unique_id values preserved
    assert "unique_id=42" in round_tripped
    assert "unique_id=99" in round_tripped

    # 4. Write the round-tripped text to disk
    tscn_path = tmp_path / "test_scene_uid.tscn"
    tscn_path.write_text(round_tripped)

    # 5. Create project.godot
    (tmp_path / "project.godot").write_text(_PROJECT_GODOT)

    # 6. Create and run validation script
    script = _build_scene_validation_script("test_scene_uid.tscn", "Node2D")
    script_path = tmp_path / "validate.gd"
    script_path.write_text(script)

    result = godot_backend.run(
        ["--headless", "--script", str(script_path)],
        project_path=tmp_path,
    )

    # 7. Confirm the file loads and child node survived the round-trip
    assert "VALIDATION_OK" in result.stdout
    assert "children=1" in result.stdout
