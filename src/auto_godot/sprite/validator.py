"""SpriteFrames validation: structural checks and headless Godot loading.

Structural validation parses the .tres file and checks resource type,
animation definitions, frame references, and texture references without
requiring a Godot binary. Headless validation creates a GDScript and
runs it in Godot to confirm the resource loads correctly.
"""

from __future__ import annotations

import tempfile
from typing import TYPE_CHECKING, Any

from auto_godot.errors import GodotBinaryError, ParseError
from auto_godot.formats.tres import GdResource, parse_tres_file
from auto_godot.formats.values import ExtResourceRef, Rect2, StringName, SubResourceRef

if TYPE_CHECKING:
    from pathlib import Path


def validate_spriteframes(path: Path) -> dict[str, Any]:
    """Validate a SpriteFrames .tres file structurally (no Godot needed).

    Returns a dict with keys: valid (bool), animations (list), issues (list),
    warnings (list), ext_resource_count (int), sub_resource_count (int).
    """
    issues: list[str] = []
    warnings: list[str] = []

    try:
        resource = parse_tres_file(path)
    except (ParseError, OSError, Exception) as exc:
        return _invalid_result(issues=[str(exc)])

    _check_resource_type(resource, issues)
    if issues:
        return _build_result(resource, [], issues, warnings)

    animations_raw = resource.resource_properties.get("animations")
    if animations_raw is None:
        issues.append("Missing 'animations' property in [resource] section")
        return _build_result(resource, [], issues, warnings)

    if not isinstance(animations_raw, list):
        issues.append("animations property is not an array")
        return _build_result(resource, [], issues, warnings)

    sub_ids = {sub.id for sub in resource.sub_resources}
    ext_ids = {ext.id for ext in resource.ext_resources}
    summaries = _check_animations(animations_raw, sub_ids, issues)
    _check_sub_resources(resource, ext_ids, issues)
    _check_load_steps(resource, warnings)

    return _build_result(resource, summaries, issues, warnings)


def validate_spriteframes_headless(
    path: Path, backend: Any
) -> dict[str, Any]:
    """Validate a SpriteFrames .tres file by loading it in headless Godot.

    Falls back to structural-only validation if the Godot binary is not
    available. Returns the same dict shape as validate_spriteframes, with
    an additional 'notes' key containing informational messages.
    """
    structural = validate_spriteframes(path)
    notes: list[str] = []

    script_content = _build_validation_script(path)

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".gd", mode="w", delete=False
        ) as tmp:
            tmp.write(script_content)
            tmp.flush()
            script_path = tmp.name

        result = backend.run(
            ["--script", script_path], project_path=path.parent
        )
        headless_result = _parse_headless_output(result.stdout)
        structural["headless_validated"] = True
        structural["headless_result"] = headless_result
        notes.append("Headless Godot validation passed")
    except GodotBinaryError:
        notes.append("Godot binary not available; structural validation only (fallback)")
        structural["headless_validated"] = False
    except Exception as exc:
        notes.append(f"Headless validation failed: {exc}; structural fallback used")
        structural["headless_validated"] = False

    structural["notes"] = notes
    return structural


def _check_resource_type(resource: GdResource, issues: list[str]) -> None:
    """Check that the resource type is SpriteFrames."""
    if resource.type != "SpriteFrames":
        issues.append(
            f"Resource type is '{resource.type}', expected 'SpriteFrames'"
        )


def _check_animations(
    animations: list[Any],
    sub_ids: set[str],
    issues: list[str],
) -> list[dict[str, Any]]:
    """Validate each animation dict and build summaries."""
    summaries: list[dict[str, Any]] = []
    for i, anim in enumerate(animations):
        if not isinstance(anim, dict):
            issues.append(f"Animation {i} is not a dictionary")
            continue
        _check_single_animation(anim, i, sub_ids, issues, summaries)
    return summaries


def _check_single_animation(
    anim: dict[str, Any],
    index: int,
    sub_ids: set[str],
    issues: list[str],
    summaries: list[dict[str, Any]],
) -> None:
    """Validate a single animation entry."""
    name = _extract_animation_name(anim, index, issues)
    frames = anim.get("frames")
    speed = anim.get("speed")
    loop = anim.get("loop")

    if frames is None:
        issues.append(f"Animation '{name}' missing 'frames' key")
    elif not isinstance(frames, list):
        issues.append(f"Animation '{name}' frames is not an array")
    else:
        _check_frames(frames, name, sub_ids, issues)

    if speed is None:
        issues.append(f"Animation '{name}' missing 'speed' key")
    elif isinstance(speed, (int, float)) and speed <= 0:
        issues.append(f"Animation '{name}' speed is {speed} (must be positive)")

    if loop is None:
        issues.append(f"Animation '{name}' missing 'loop' key")

    frame_count = len(frames) if isinstance(frames, list) else 0
    speed_val = speed if isinstance(speed, (int, float)) else 0
    if isinstance(speed_val, float):
        speed_val = round(speed_val, 2)
    summaries.append({
        "name": name,
        "frames": frame_count,
        "speed": speed_val,
        "loop": bool(loop) if loop is not None else False,
    })


def _extract_animation_name(
    anim: dict[str, Any], index: int, issues: list[str]
) -> str:
    """Extract the animation name from a StringName or string value."""
    raw_name = anim.get("name")
    if raw_name is None:
        issues.append(f"Animation {index} missing 'name' key")
        return f"<unnamed-{index}>"
    if isinstance(raw_name, StringName):
        return raw_name.value
    if isinstance(raw_name, str):
        return raw_name
    return str(raw_name)


def _check_frames(
    frames: list[Any],
    anim_name: str,
    sub_ids: set[str],
    issues: list[str],
) -> None:
    """Validate frame entries in an animation."""
    for j, frame in enumerate(frames):
        if not isinstance(frame, dict):
            issues.append(
                f"Animation '{anim_name}' frame {j} is not a dictionary"
            )
            continue

        texture = frame.get("texture")
        if texture is None:
            issues.append(
                f"Animation '{anim_name}' frame {j} missing 'texture' key"
            )
        elif isinstance(texture, SubResourceRef) and texture.id not in sub_ids:
            issues.append(
                f"Animation '{anim_name}' frame {j} references "
                f"unknown SubResource '{texture.id}'"
            )

        duration = frame.get("duration")
        if duration is None:
            issues.append(
                f"Animation '{anim_name}' frame {j} missing 'duration' key"
            )


def _check_sub_resources(
    resource: GdResource,
    ext_ids: set[str],
    issues: list[str],
) -> None:
    """Validate sub_resources (AtlasTexture references and regions)."""
    for sub in resource.sub_resources:
        if sub.type != "AtlasTexture":
            continue
        atlas = sub.properties.get("atlas")
        if isinstance(atlas, ExtResourceRef) and atlas.id not in ext_ids:
            issues.append(
                f"SubResource '{sub.id}' atlas references "
                f"unknown ExtResource '{atlas.id}'"
            )
        region = sub.properties.get("region")
        if region is not None and not isinstance(region, Rect2):
            issues.append(
                f"SubResource '{sub.id}' region is not a Rect2"
            )


def _check_load_steps(resource: GdResource, warnings: list[str]) -> None:
    """Warn if load_steps does not match expected count (non-fatal)."""
    if resource.load_steps is None:
        return
    expected = len(resource.ext_resources) + len(resource.sub_resources) + 1
    if resource.load_steps != expected:
        warnings.append(
            f"load_steps is {resource.load_steps}, expected {expected}"
        )


def _build_result(
    resource: GdResource,
    summaries: list[dict[str, Any]],
    issues: list[str],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build the validation result dict from a parsed resource."""
    return {
        "valid": len(issues) == 0,
        "animations": summaries,
        "issues": issues,
        "warnings": warnings or [],
        "ext_resource_count": len(resource.ext_resources),
        "sub_resource_count": len(resource.sub_resources),
    }


def _invalid_result(issues: list[str]) -> dict[str, Any]:
    """Build a validation result for files that cannot be parsed."""
    return {
        "valid": False,
        "animations": [],
        "issues": issues,
        "warnings": [],
        "ext_resource_count": 0,
        "sub_resource_count": 0,
    }


def _build_validation_script(path: Path) -> str:
    """Create a GDScript that loads and validates a SpriteFrames resource."""
    res_path = str(path.resolve()).replace("\\", "/")
    return (
        'extends SceneTree\n'
        '\n'
        'func _init() -> void:\n'
        f'    var res = load("{res_path}")\n'
        '    if res == null:\n'
        '        print("VALIDATION_FAIL: Could not load resource")\n'
        '        quit(1)\n'
        '    if not res is SpriteFrames:\n'
        '        print("VALIDATION_FAIL: Resource is not SpriteFrames")\n'
        '        quit(1)\n'
        '    var anims = res.get_animation_names()\n'
        '    print("VALIDATION_OK: animations=" + str(anims.size()))\n'
        '    for anim_name in anims:\n'
        '        var count = res.get_frame_count(anim_name)\n'
        '        print("ANIM: " + anim_name + " frames=" + str(count))\n'
        '    quit(0)\n'
    )


def _parse_headless_output(stdout: str) -> dict[str, Any]:
    """Parse VALIDATION_OK/VALIDATION_FAIL output from the GDScript."""
    result: dict[str, Any] = {"ok": False, "animations": []}
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("VALIDATION_OK:"):
            result["ok"] = True
        elif line.startswith("VALIDATION_FAIL:"):
            result["ok"] = False
            result["error"] = line.split(":", 1)[1].strip()
        elif line.startswith("ANIM:"):
            parts = line[5:].strip().split(" frames=")
            if len(parts) == 2:
                result["animations"].append({
                    "name": parts[0].strip(),
                    "frames": int(parts[1].strip()),
                })
    return result
