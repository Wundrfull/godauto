"""SpriteFrames GdResource builder from Aseprite data.

Transforms parsed AsepriteData into Godot SpriteFrames GdResource instances
ready for .tres serialization. Handles all animation directions, variable
durations via GCD-based FPS, trimmed sprite margins, and loop settings.
"""

from __future__ import annotations

import math
from functools import reduce
from typing import Any

from gdauto.formats.aseprite import (
    AniDirection,
    AsepriteData,
    AsepriteFrame,
    AsepriteTag,
    FrameRect,
)
from gdauto.formats.tres import ExtResource, GdResource, SubResource
from gdauto.formats.uid import generate_resource_id, generate_uid, uid_to_text
from gdauto.formats.values import ExtResourceRef, Rect2, StringName, SubResourceRef


def compute_animation_timing(
    durations_ms: list[int],
) -> tuple[float, list[float]]:
    """Compute base FPS and per-frame duration multipliers from ms durations.

    Uses GCD of all durations to find the smallest time unit, then derives
    a base FPS and multipliers. Empty list returns (1.0, []).
    """
    if not durations_ms:
        return (1.0, [])
    gcd = reduce(math.gcd, durations_ms)
    base_fps = 1000.0 / gcd
    multipliers = [d / gcd for d in durations_ms]
    return (base_fps, multipliers)


def expand_pingpong(frame_indices: list[int]) -> list[int]:
    """Expand frame indices for pingpong animation direction.

    For 3+ frames, appends reversed middle frames: [0,1,2,3] -> [0,1,2,3,2,1].
    For 2 or fewer frames, returns unchanged (no meaningful bounce).
    """
    if len(frame_indices) <= 2:
        return list(frame_indices)
    return frame_indices + frame_indices[-2:0:-1]


def expand_pingpong_reverse(frame_indices: list[int]) -> list[int]:
    """Expand frame indices for pingpong_reverse animation direction.

    Starts from the last frame going backward, then bounces forward:
    [0,1,2,3] -> [3,2,1,0,1,2]. For 2 or fewer, just reverses.
    """
    if len(frame_indices) <= 2:
        return list(reversed(frame_indices))
    reversed_frames = list(reversed(frame_indices))
    return reversed_frames + frame_indices[1:-1]


def compute_margin(
    sprite_source_size: FrameRect,
    source_size: tuple[int, int],
    frame: FrameRect,
) -> Rect2 | None:
    """Compute AtlasTexture margin for trimmed sprites.

    Returns None if all margin values are zero (no trimming needed).
    """
    margin_x = float(sprite_source_size.x)
    margin_y = float(sprite_source_size.y)
    margin_w = float(source_size[0] - frame.w)
    margin_h = float(source_size[1] - frame.h)
    if margin_x == 0.0 and margin_y == 0.0 and margin_w == 0.0 and margin_h == 0.0:
        return None
    return Rect2(margin_x, margin_y, margin_w, margin_h)


def _apply_direction(
    frame_indices: list[int], direction: AniDirection
) -> list[int]:
    """Apply animation direction expansion to frame indices."""
    if direction == AniDirection.FORWARD:
        return frame_indices
    if direction == AniDirection.REVERSE:
        return list(reversed(frame_indices))
    if direction == AniDirection.PING_PONG:
        return expand_pingpong(frame_indices)
    return expand_pingpong_reverse(frame_indices)


def _build_atlas_sub_resources(
    expanded_frames: list[AsepriteFrame],
    ext_resource: ExtResource,
) -> list[SubResource]:
    """Create AtlasTexture SubResources for expanded frame list."""
    sub_resources: list[SubResource] = []
    for frame in expanded_frames:
        props: dict[str, Any] = {
            "atlas": ExtResourceRef(ext_resource.id),
            "region": Rect2(
                float(frame.frame.x),
                float(frame.frame.y),
                float(frame.frame.w),
                float(frame.frame.h),
            ),
        }
        if frame.trimmed:
            margin = compute_margin(
                frame.sprite_source_size, frame.source_size, frame.frame
            )
            if margin is not None:
                props["margin"] = margin
        sub_resources.append(
            SubResource(
                type="AtlasTexture",
                id=generate_resource_id("AtlasTexture"),
                properties=props,
            )
        )
    return sub_resources


def build_animation_for_tag(
    tag: AsepriteTag,
    frames: list[AsepriteFrame],
    ext_resource: ExtResource,
) -> tuple[list[SubResource], dict[str, Any]]:
    """Build SubResources and animation dict for a single animation tag.

    Extracts the tag's frame range (inclusive end), applies direction
    expansion, computes timing, and creates AtlasTexture sub-resources.
    Returns (sub_resources, animation_dict) tuple.
    """
    tag_frames = frames[tag.from_frame : tag.to_frame + 1]
    base_indices = list(range(len(tag_frames)))
    expanded_indices = _apply_direction(base_indices, tag.direction)
    expanded_frames = [tag_frames[idx] for idx in expanded_indices]

    durations = [f.duration for f in expanded_frames]
    base_fps, multipliers = compute_animation_timing(durations)

    sub_resources = _build_atlas_sub_resources(expanded_frames, ext_resource)

    anim_dict: dict[str, Any] = {
        "frames": [
            {"duration": multipliers[j], "texture": SubResourceRef(sub_resources[j].id)}
            for j in range(len(expanded_frames))
        ],
        "loop": tag.repeat == 0,
        "name": StringName(tag.name),
        "speed": base_fps,
    }
    return (sub_resources, anim_dict)


def build_spriteframes(
    aseprite: AsepriteData, image_path: str
) -> GdResource:
    """Build a SpriteFrames GdResource from parsed Aseprite data.

    Creates one ExtResource for the texture, AtlasTexture SubResources
    for each animation frame, and an animations array with timing and
    loop settings. If no tags exist, creates a single "default" animation.
    """
    ext = ExtResource(
        type="Texture2D",
        path=image_path,
        id=generate_resource_id("Texture2D"),
        uid=uid_to_text(generate_uid()),
    )
    tags = aseprite.meta.frame_tags or []
    if not tags:
        tags = [AsepriteTag(
            name="default", from_frame=0,
            to_frame=len(aseprite.frames) - 1,
            direction=AniDirection.FORWARD, repeat=0,
        )]

    all_subs: list[SubResource] = []
    animations: list[dict[str, Any]] = []
    for tag in tags:
        subs, anim = build_animation_for_tag(tag, aseprite.frames, ext)
        all_subs.extend(subs)
        animations.append(anim)

    return GdResource(
        type="SpriteFrames", format=3,
        uid=uid_to_text(generate_uid()),
        load_steps=None,
        ext_resources=[ext], sub_resources=all_subs,
        resource_properties={"animations": animations},
    )
