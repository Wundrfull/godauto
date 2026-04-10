"""E2E tests: SpriteFrames resources load in headless Godot."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_godot.backend import GodotBackend
from auto_godot.formats.aseprite import parse_aseprite_json
from auto_godot.formats.tres import serialize_tres_file
from auto_godot.sprite.spriteframes import build_spriteframes


FIXTURES = Path(__file__).parent.parent / "fixtures"

_PROJECT_GODOT = (
    "; Engine configuration file.\n"
    "config_version=5\n\n"
    "[application]\nconfig/name=\"E2ETest\"\n"
)


def _build_spriteframes_validation_script(tres_name: str) -> str:
    """Create a GDScript that loads and validates a SpriteFrames resource.

    Uses res:// path so Godot resolves the file within the project directory.
    """
    return (
        "extends SceneTree\n"
        "\n"
        "func _init() -> void:\n"
        f'    var res = load("res://{tres_name}")\n'
        "    if res == null:\n"
        '        print("VALIDATION_FAIL: Could not load SpriteFrames")\n'
        "        quit(1)\n"
        "    if not res is SpriteFrames:\n"
        '        print("VALIDATION_FAIL: Resource is not SpriteFrames, got " + res.get_class())\n'
        "        quit(1)\n"
        "    var anims = res.get_animation_names()\n"
        "    if anims.size() == 0:\n"
        '        print("VALIDATION_FAIL: No animations found")\n'
        "        quit(1)\n"
        '    print("VALIDATION_OK: animations=" + str(anims.size()))\n'
        "    for anim_name in anims:\n"
        '        print("ANIM: " + anim_name + " frames=" + str(res.get_frame_count(anim_name)))\n'
        "    quit(0)\n"
    )


@pytest.mark.requires_godot
def test_spriteframes_loads_in_godot(
    tmp_path: Path, godot_backend: GodotBackend
) -> None:
    """Generate a SpriteFrames from Aseprite JSON and validate in headless Godot."""
    # 1. Parse the simple Aseprite fixture
    aseprite_data = parse_aseprite_json(FIXTURES / "aseprite_simple.json")

    # 2. Build SpriteFrames resource
    resource = build_spriteframes(aseprite_data, "res://test_sheet.png")

    # 3. Write to tmp_path as .tres file
    tres_path = tmp_path / "test_spriteframes.tres"
    serialize_tres_file(resource, tres_path)

    # 4. Create a minimal project.godot so Godot recognizes the directory
    (tmp_path / "project.godot").write_text(_PROJECT_GODOT)

    # 5. Create validation GDScript
    script = _build_spriteframes_validation_script("test_spriteframes.tres")
    script_path = tmp_path / "validate.gd"
    script_path.write_text(script)

    # 6. Run headless Godot
    result = godot_backend.run(
        ["--headless", "--script", str(script_path)],
        project_path=tmp_path,
    )

    # 7. Check output
    assert "VALIDATION_OK" in result.stdout


@pytest.mark.requires_godot
def test_spriteframes_no_load_steps(
    tmp_path: Path, godot_backend: GodotBackend
) -> None:
    """Validate SpriteFrames without load_steps loads in headless Godot (VAL-01)."""
    # 1. Parse the simple Aseprite fixture
    aseprite_data = parse_aseprite_json(FIXTURES / "aseprite_simple.json")

    # 2. Build SpriteFrames resource
    resource = build_spriteframes(aseprite_data, "res://test_sheet.png")

    # 3. Confirm load_steps is None at the Python level
    assert resource.load_steps is None

    # 4. Write to tmp_path as .tres file
    tres_path = tmp_path / "test_nols.tres"
    serialize_tres_file(resource, tres_path)

    # 5. Confirm load_steps is absent in the serialized text
    tres_text = tres_path.read_text()
    assert "load_steps" not in tres_text

    # 6. Create a minimal project.godot so Godot recognizes the directory
    (tmp_path / "project.godot").write_text(_PROJECT_GODOT)

    # 7. Create validation GDScript
    script = _build_spriteframes_validation_script("test_nols.tres")
    script_path = tmp_path / "validate.gd"
    script_path.write_text(script)

    # 8. Run headless Godot
    result = godot_backend.run(
        ["--headless", "--script", str(script_path)],
        project_path=tmp_path,
    )

    # 9. Check output
    assert "VALIDATION_OK" in result.stdout
