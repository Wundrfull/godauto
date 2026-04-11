"""Create and manage AnimationPlayer resources."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rich_click as click

from auto_godot.errors import ProjectError
from auto_godot.formats.tres import (
    GdResource,
    SubResource,
    serialize_tres_file,
)
from auto_godot.formats.values import NodePath, SubResourceRef
from auto_godot.output import emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def animation(ctx: click.Context) -> None:
    """Create and manage animation resources."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Interpolation modes
_INTERP_MODES = {"nearest": 0, "linear": 1, "cubic": 2}

# Loop modes
_LOOP_MODES = {"none": 0, "linear": 1, "pingpong": 2}


def _build_track_properties(
    track_idx: int,
    node_path: str,
    keyframes: list[tuple[float, Any]],
    interp: str,
) -> dict[str, Any]:
    """Build track property entries for an Animation sub-resource."""
    interp_mode = _INTERP_MODES.get(interp, 1)
    prefix = f"tracks/{track_idx}"

    # Build the packed keyframe array
    # Format: [time, transition, value, time, transition, value, ...]
    key_values: list[float] = []
    for time, value in keyframes:
        key_values.append(float(time))
        key_values.append(1.0)  # transition type (1 = linear)
        if isinstance(value, (int, float)):
            key_values.append(float(value))
        else:
            key_values.append(float(value))

    return {
        f"{prefix}/type": "value",
        f"{prefix}/imported": False,
        f"{prefix}/enabled": True,
        f"{prefix}/path": NodePath(node_path),
        f"{prefix}/interp": interp_mode,
        f"{prefix}/loop_wrap": True,
        f"{prefix}/keys": _packed_float32_array(key_values),
    }


class _RawGodotValue:
    """Wrapper for raw Godot value strings that bypass serialize_value quoting."""

    def __init__(self, raw: str) -> None:
        self._raw = raw

    def __str__(self) -> str:
        return self._raw

    def __repr__(self) -> str:
        return self._raw


def _format_float(v: float) -> str:
    """Format a float for Godot: 1.0 -> '1', 1.5 -> '1.5'."""
    if v == int(v):
        return str(int(v))
    return str(v)


def _packed_float32_array(values: list[float]) -> _RawGodotValue:
    """Create a PackedFloat32Array Godot value."""
    formatted = ", ".join(_format_float(v) for v in values)
    return _RawGodotValue(f"PackedFloat32Array({formatted})")


@animation.command("create-library")
@click.option(
    "--name", "anim_name", required=True, multiple=True,
    help="Animation name(s) to include (e.g., 'idle', 'walk', 'attack')",
)
@click.option(
    "--length", "lengths", multiple=True, type=float,
    help="Duration(s) in seconds (matched to --name order, default: 1.0)",
)
@click.option(
    "--loop", "loop_modes", multiple=True,
    type=click.Choice(sorted(_LOOP_MODES)),
    help="Loop mode(s) (matched to --name order, default: none)",
)
@click.argument("output_path", type=click.Path())
@click.pass_context
def create_library(
    ctx: click.Context,
    anim_name: tuple[str, ...],
    lengths: tuple[float, ...],
    loop_modes: tuple[str, ...],
    output_path: str,
) -> None:
    """Create an AnimationLibrary .tres with named animations.

    Examples:

      auto-godot animation create-library --name idle --name walk --length 1.0 --length 0.8 --loop linear --loop linear animations.tres

      auto-godot animation create-library --name attack --length 0.5 animations/combat.tres
    """
    try:
        sub_resources: list[SubResource] = []
        anim_map: dict[str, SubResourceRef] = {}

        for i, name in enumerate(anim_name):
            length = lengths[i] if i < len(lengths) else 1.0
            loop_mode_str = loop_modes[i] if i < len(loop_modes) else "none"
            loop_mode = _LOOP_MODES.get(loop_mode_str, 0)

            sub_id = f"{name}_anim"
            sub_resources.append(SubResource(
                type="Animation",
                id=sub_id,
                properties={
                    "resource_name": name,
                    "length": length,
                    "loop_mode": loop_mode,
                },
            ))
            anim_map[name] = SubResourceRef(sub_id)

        resource = GdResource(
            type="AnimationLibrary",
            format=3,
            uid=None,
            load_steps=len(sub_resources) + 1,
            ext_resources=[],
            sub_resources=sub_resources,
            resource_properties={"_data": anim_map},
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        serialize_tres_file(resource, out)

        data = {
            "created": True,
            "path": str(out),
            "animations": list(anim_name),
            "count": len(anim_name),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            names = ", ".join(data["animations"])
            click.echo(f"Created AnimationLibrary at {data['path']} with: {names}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


@animation.command("add-track")
@click.option(
    "--library", "library_path", required=True,
    type=click.Path(exists=True),
    help="Path to an AnimationLibrary .tres file",
)
@click.option(
    "--animation", "anim_name", required=True,
    help="Name of the animation to add the track to",
)
@click.option(
    "--property", "node_property", required=True,
    help="Node property path (e.g., 'Sprite2D:modulate', '.:position:x')",
)
@click.option(
    "--keyframe", "keyframes", multiple=True, required=True,
    help="Keyframes as 'time=value' (e.g., '0=0', '0.5=100', '1.0=0')",
)
@click.option(
    "--interp", default="linear",
    type=click.Choice(sorted(_INTERP_MODES)),
    help="Interpolation mode (default: linear)",
)
@click.pass_context
def add_track(
    ctx: click.Context,
    library_path: str,
    anim_name: str,
    node_property: str,
    keyframes: tuple[str, ...],
    interp: str,
) -> None:
    """Add a property track to an animation in a library.

    Examples:

      auto-godot animation add-track --library anims.tres --animation idle --property "Sprite2D:modulate:a" --keyframe "0=1.0" --keyframe "0.5=0.5" --keyframe "1.0=1.0"

      auto-godot animation add-track --library anims.tres --animation walk --property ".:position:x" --keyframe "0=0" --keyframe "0.5=16" --keyframe "1.0=0"
    """
    try:
        parsed_kf = _parse_keyframes(keyframes)
        path = Path(library_path)
        text = path.read_text(encoding="utf-8")

        from auto_godot.formats.tres import parse_tres
        resource = parse_tres(text)

        # Find the animation sub-resource
        target_sub = None
        for sub in resource.sub_resources:
            if sub.properties.get("resource_name") == anim_name or sub.id == f"{anim_name}_anim":
                target_sub = sub
                break

        if target_sub is None:
            raise ProjectError(
                message=f"Animation '{anim_name}' not found in {library_path}",
                code="ANIMATION_NOT_FOUND",
                fix="Available animations: check with 'auto-godot animation list-tracks'",
            )

        # Find next track index
        track_idx = 0
        for key in target_sub.properties:
            if key.startswith("tracks/") and key.endswith("/type"):
                idx = int(key.split("/")[1])
                track_idx = max(track_idx, idx + 1)

        # Add track properties
        track_props = _build_track_properties(
            track_idx, node_property, parsed_kf, interp,
        )
        target_sub.properties.update(track_props)

        # Write back (clear raw data to force rebuild from model)
        resource._raw_header = None
        resource._raw_sections = None
        serialize_tres_file(resource, path)

        data = {
            "added": True,
            "animation": anim_name,
            "property": node_property,
            "track_index": track_idx,
            "keyframe_count": len(parsed_kf),
            "interp": interp,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Added track {data['track_index']} to '{data['animation']}': "
                f"{data['property']} ({data['keyframe_count']} keyframes, {data['interp']})"
            )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


def _parse_keyframes(keyframes: tuple[str, ...]) -> list[tuple[float, float]]:
    """Parse 'time=value' keyframe strings."""
    result: list[tuple[float, float]] = []
    for kf in keyframes:
        if "=" not in kf:
            raise ProjectError(
                message=f"Invalid keyframe format: '{kf}'. Expected 'time=value'",
                code="INVALID_KEYFRAME",
                fix="Use format 'time=value', e.g., '0.5=100.0'",
            )
        time_str, value_str = kf.split("=", 1)
        try:
            result.append((float(time_str), float(value_str)))
        except ValueError as err:
            raise ProjectError(
                message=f"Invalid keyframe values: '{kf}'. Both time and value must be numbers",
                code="INVALID_KEYFRAME",
                fix="Use numeric values, e.g., '0.5=100.0'",
            ) from err
    return result


@animation.command("list-tracks")
@click.argument("library_path", type=click.Path(exists=True))
@click.pass_context
def list_tracks(
    ctx: click.Context,
    library_path: str,
) -> None:
    """List animations and tracks in an AnimationLibrary .tres file."""
    try:
        text = Path(library_path).read_text(encoding="utf-8")

        from auto_godot.formats.tres import parse_tres
        resource = parse_tres(text)

        animations: list[dict[str, Any]] = []
        for sub in resource.sub_resources:
            if sub.type != "Animation":
                continue

            name = sub.properties.get("resource_name", sub.id)
            length = sub.properties.get("length", 1.0)
            loop_mode = sub.properties.get("loop_mode", 0)

            tracks: list[dict[str, str]] = []
            track_idx = 0
            while f"tracks/{track_idx}/type" in sub.properties:
                track_type = sub.properties.get(f"tracks/{track_idx}/type", "value")
                path_val = sub.properties.get(f"tracks/{track_idx}/path", "")
                path_str = path_val.path if hasattr(path_val, "path") else str(path_val)
                tracks.append({
                    "index": track_idx,
                    "type": track_type,
                    "path": path_str,
                })
                track_idx += 1

            animations.append({
                "name": name,
                "length": length,
                "loop_mode": loop_mode,
                "tracks": tracks,
                "track_count": len(tracks),
            })

        data = {
            "animations": animations,
            "count": len(animations),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"AnimationLibrary ({data['count']} animations):")
            for anim in data["animations"]:
                loop_str = {0: "", 1: " [loop]", 2: " [pingpong]"}.get(
                    anim["loop_mode"], ""
                )
                click.echo(
                    f"  {anim['name']} ({anim['length']}s, "
                    f"{anim['track_count']} tracks{loop_str})"
                )
                for track in anim["tracks"]:
                    click.echo(f"    [{track['index']}] {track['type']}: {track['path']}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)
