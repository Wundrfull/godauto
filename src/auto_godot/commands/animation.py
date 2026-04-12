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
from auto_godot.formats.tscn import SceneNode, parse_tscn, serialize_tscn
from auto_godot.formats.values import NodePath, StringName, SubResourceRef, Vector2
from auto_godot.output import check_path, emit, emit_error, maybe_write


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

    # Godot 4 value track keys use a dictionary format with separate arrays
    times: list[float] = []
    transitions: list[float] = []
    values: list[float] = []
    for time, value in keyframes:
        times.append(float(time))
        transitions.append(1.0)  # transition type (1 = linear)
        values.append(float(value))

    keys_dict: dict[str, Any] = {
        "times": _packed_float32_array(times),
        "transitions": _packed_float32_array(transitions),
        "update": 0,
        "values": values,
    }

    return {
        f"{prefix}/type": "value",
        f"{prefix}/imported": False,
        f"{prefix}/enabled": True,
        f"{prefix}/path": NodePath(node_path),
        f"{prefix}/interp": interp_mode,
        f"{prefix}/loop_wrap": True,
        f"{prefix}/keys": keys_dict,
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


# ---------------------------------------------------------------------------
# animation create-tree
# ---------------------------------------------------------------------------


def _parse_state_list(states: str) -> list[str]:
    """Split a comma-separated state list and validate names."""
    names = [s.strip() for s in states.split(",") if s.strip()]
    if not names:
        raise ProjectError(
            message="No states provided",
            code="INVALID_STATES",
            fix="Pass at least one state: --states idle,walk",
        )
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ProjectError(
                message=f"Duplicate state '{name}' in --states",
                code="DUPLICATE_STATE",
                fix="Each state name must be unique",
            )
        seen.add(name)
    return names


def _parse_blend_times(
    blend_times: str | None, state_names: list[str],
) -> list[tuple[str, str, float]]:
    """Parse 'from->to:seconds,...' into (from, to, xfade) triples.

    'any' is treated as a wildcard expanding to every state except 'to'.
    """
    if not blend_times:
        return []
    state_set = set(state_names)
    result: list[tuple[str, str, float]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for entry in blend_times.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "->" not in entry or ":" not in entry:
            raise ProjectError(
                message=f"Invalid blend-time entry: '{entry}'",
                code="INVALID_BLEND_TIME",
                fix="Use format 'from->to:seconds', e.g., 'idle->walk:0.15'",
            )
        pair, time_str = entry.rsplit(":", 1)
        src, dst = pair.split("->", 1)
        src = src.strip()
        dst = dst.strip()
        try:
            xfade = float(time_str)
        except ValueError as err:
            raise ProjectError(
                message=f"Invalid blend time in '{entry}': '{time_str}'",
                code="INVALID_BLEND_TIME",
                fix="Use a numeric seconds value, e.g., '0.15'",
            ) from err
        if dst not in state_set:
            raise ProjectError(
                message=f"Unknown target state '{dst}' in blend-time '{entry}'",
                code="UNKNOWN_STATE",
                fix=f"Known states: {', '.join(state_names)}",
            )
        sources = [s for s in state_names if s != dst] if src == "any" else [src]
        if src != "any" and src not in state_set:
            raise ProjectError(
                message=f"Unknown source state '{src}' in blend-time '{entry}'",
                code="UNKNOWN_STATE",
                fix=f"Known states: {', '.join(state_names)} (or 'any')",
            )
        for source in sources:
            key = (source, dst)
            if key in seen_pairs:
                raise ProjectError(
                    message=f"Duplicate transition {source}->{dst}",
                    code="DUPLICATE_TRANSITION",
                    fix="Each (from, to) pair may only be given once",
                )
            seen_pairs.add(key)
            result.append((source, dst, xfade))
    return result


def _build_state_sub_resources(
    state_names: list[str],
) -> tuple[list[SubResource], dict[str, str]]:
    """Create one AnimationNodeAnimation sub-resource per state."""
    sub_resources: list[SubResource] = []
    state_to_id: dict[str, str] = {}
    for name in state_names:
        sub_id = f"AnimNodeAnimation_{name}"
        sub_resources.append(SubResource(
            type="AnimationNodeAnimation",
            id=sub_id,
            properties={"animation": StringName(name)},
        ))
        state_to_id[name] = sub_id
    return sub_resources, state_to_id


def _build_transition_sub_resources(
    transitions: list[tuple[str, str, float]],
) -> tuple[list[SubResource], list[str]]:
    """Create AnimationNodeStateMachineTransition sub-resources."""
    sub_resources: list[SubResource] = []
    ids: list[str] = []
    for src, dst, xfade in transitions:
        sub_id = f"AnimNodeStateMachineTransition_{src}_{dst}"
        sub_resources.append(SubResource(
            type="AnimationNodeStateMachineTransition",
            id=sub_id,
            properties={"xfade_time": xfade},
        ))
        ids.append(sub_id)
    return sub_resources, ids


def _build_state_machine_sub_resource(
    state_to_id: dict[str, str],
    transitions: list[tuple[str, str, float]],
    transition_ids: list[str],
    tree_id: str,
) -> SubResource:
    """Create the root AnimationNodeStateMachine sub-resource."""
    props: dict[str, Any] = {}
    for idx, (name, sub_id) in enumerate(state_to_id.items()):
        props[f"states/{name}/node"] = SubResourceRef(sub_id)
        props[f"states/{name}/position"] = Vector2(200.0 + idx * 200.0, 100.0)
    trans_array: list[Any] = []
    for (src, dst, _), t_id in zip(transitions, transition_ids, strict=True):
        trans_array.extend([src, dst, SubResourceRef(t_id)])
    if trans_array:
        props["transitions"] = trans_array
    props["graph_offset"] = Vector2(0.0, 0.0)
    return SubResource(
        type="AnimationNodeStateMachine",
        id=tree_id,
        properties=props,
    )


def _locate_animation_player(
    scene_data: Any, player_name: str,
) -> SceneNode:
    """Return the AnimationPlayer node matching player_name.

    Requires the player to be a direct child of the scene root so that
    the NodePath from a new sibling AnimationTree is "../<name>".
    """
    match: SceneNode | None = None
    for node in scene_data.nodes:
        if node.name != player_name:
            continue
        if node.type != "AnimationPlayer":
            raise ProjectError(
                message=f"Node '{player_name}' exists but is not an AnimationPlayer",
                code="WRONG_NODE_TYPE",
                fix=f"Found type '{node.type}'; pass the name of an AnimationPlayer node",
            )
        match = node
        break
    if match is None:
        raise ProjectError(
            message=f"AnimationPlayer '{player_name}' not found in scene",
            code="ANIM_PLAYER_NOT_FOUND",
            fix="Check --player matches an existing AnimationPlayer node name",
        )
    if match.parent != ".":
        raise ProjectError(
            message=f"AnimationPlayer '{player_name}' must be a direct child of the scene root",
            code="ANIM_PLAYER_NOT_AT_ROOT",
            fix="Move the AnimationPlayer to the scene root, or edit the generated AnimationTree anim_player NodePath manually",
        )
    return match


@animation.command("create-tree")
@click.option(
    "--scene", "scene_path", required=True,
    type=click.Path(),
    help="Path to the .tscn scene to modify",
)
@click.option(
    "--name", "tree_name", required=True,
    help="Name for the new AnimationTree node",
)
@click.option(
    "--states", required=True,
    help="Comma-separated state names (e.g., 'idle,walk,run,jump,fall')",
)
@click.option(
    "--player", "player_name", required=True,
    help="Name of the existing AnimationPlayer node to drive",
)
@click.option(
    "--blend-times", "blend_times", default=None,
    help="Optional 'from->to:seconds,...' list (use 'any' as a wildcard source)",
)
@click.pass_context
def create_tree(
    ctx: click.Context,
    scene_path: str,
    tree_name: str,
    states: str,
    player_name: str,
    blend_times: str | None,
) -> None:
    """Add an AnimationTree + AnimationNodeStateMachine to an existing scene.

    Examples:

      auto-godot animation create-tree --scene scenes/player.tscn --name AnimTree --states idle,walk,run --player AnimPlayer

      auto-godot animation create-tree --scene scenes/boss.tscn --name AnimTree --states idle,attack,hurt --player AnimPlayer --blend-times idle->attack:0.1,attack->idle:0.2,any->hurt:0.05
    """
    try:
        if not check_path(scene_path, ctx, "scene"):
            return
        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene_data = parse_tscn(text)

        for node in scene_data.nodes:
            if node.name == tree_name and node.parent == ".":
                raise ProjectError(
                    message=f"Node '{tree_name}' already exists at scene root",
                    code="NODE_EXISTS",
                    fix="Choose a different --name or remove the existing node",
                )

        _locate_animation_player(scene_data, player_name)

        state_names = _parse_state_list(states)
        transitions = _parse_blend_times(blend_times, state_names)

        state_subs, state_to_id = _build_state_sub_resources(state_names)
        trans_subs, trans_ids = _build_transition_sub_resources(transitions)
        tree_root_id = "AnimationNodeStateMachine_root"
        sm_sub = _build_state_machine_sub_resource(
            state_to_id, transitions, trans_ids, tree_root_id,
        )

        scene_data.sub_resources.extend(state_subs)
        scene_data.sub_resources.extend(trans_subs)
        scene_data.sub_resources.append(sm_sub)

        tree_props: dict[str, Any] = {
            "tree_root": SubResourceRef(tree_root_id),
            "anim_player": NodePath(f"../{player_name}"),
            "callback_mode_discrete": 2,
            "active": True,
        }
        scene_data.nodes.append(SceneNode(
            name=tree_name,
            type="AnimationTree",
            parent=".",
            properties=tree_props,
        ))

        scene_data._raw_header = None
        scene_data._raw_sections = None
        output = serialize_tscn(scene_data)
        maybe_write(ctx, path, output)

        data = {
            "created": True,
            "scene": scene_path,
            "tree_name": tree_name,
            "states": state_names,
            "state_count": len(state_names),
            "transition_count": len(transitions),
            "player": player_name,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Added AnimationTree '{data['tree_name']}' to {data['scene']} "
                f"({data['state_count']} states, {data['transition_count']} transitions, "
                f"driving {data['player']})"
            )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)
