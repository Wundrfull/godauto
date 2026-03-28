"""Sprite sheet splitting: grid-based and JSON-defined.

Splits existing sprite sheets into frames and generates SpriteFrames
GdResource instances. Requires Pillow for reading image dimensions.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

from gdauto.errors import GdautoError, ValidationError
from gdauto.formats.tres import ExtResource, GdResource, SubResource
from gdauto.formats.uid import generate_resource_id, generate_uid, uid_to_text
from gdauto.formats.values import ExtResourceRef, Rect2, StringName, SubResourceRef

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment,misc]


def _require_pillow() -> None:
    """Raise GdautoError if Pillow is not installed."""
    if Image is None:
        raise GdautoError(
            message="Pillow is required for sprite split",
            code="PILLOW_NOT_INSTALLED",
            fix="Install with: pip install gdauto[image] (or: uv pip install gdauto[image])",
        )


def split_sheet_grid(
    image_path: Path,
    frame_w: int,
    frame_h: int,
    image_res_path: str,
    fps: float = 10.0,
) -> GdResource:
    """Split a sprite sheet into frames using a uniform grid.

    Opens the image to read dimensions, computes grid cells, and
    builds a SpriteFrames GdResource with one "default" animation.
    Partial edge frames (when image not evenly divisible) are ignored
    with a warning.
    """
    _require_pillow()
    img = Image.open(image_path)
    width, height = img.width, img.height
    img.close()

    if frame_w > width or frame_h > height:
        raise ValidationError(
            message=f"Frame size {frame_w}x{frame_h} exceeds image size {width}x{height}",
            code="SPRITE_FRAME_TOO_LARGE",
            fix=f"Use a frame size smaller than {width}x{height}",
        )

    if width % frame_w != 0 or height % frame_h != 0:
        warnings.warn(
            f"Image {width}x{height} not evenly divisible by "
            f"{frame_w}x{frame_h}; partial edge frames ignored"
        )

    cols = width // frame_w
    rows = height // frame_h

    ext = ExtResource(
        type="Texture2D",
        path=image_res_path,
        id=generate_resource_id("Texture2D"),
        uid=uid_to_text(generate_uid()),
    )

    sub_resources = _build_grid_sub_resources(rows, cols, frame_w, frame_h, ext)
    animation = _build_default_animation(sub_resources, fps)
    load_steps = 1 + len(sub_resources) + 1

    return GdResource(
        type="SpriteFrames",
        format=3,
        uid=uid_to_text(generate_uid()),
        load_steps=load_steps,
        ext_resources=[ext],
        sub_resources=sub_resources,
        resource_properties={"animations": [animation]},
    )


def _build_grid_sub_resources(
    rows: int,
    cols: int,
    frame_w: int,
    frame_h: int,
    ext: ExtResource,
) -> list[SubResource]:
    """Create AtlasTexture SubResources for each grid cell."""
    sub_resources: list[SubResource] = []
    for row in range(rows):
        for col in range(cols):
            region = Rect2(
                float(col * frame_w),
                float(row * frame_h),
                float(frame_w),
                float(frame_h),
            )
            sub_resources.append(
                SubResource(
                    type="AtlasTexture",
                    id=generate_resource_id("AtlasTexture"),
                    properties={
                        "atlas": ExtResourceRef(ext.id),
                        "region": region,
                    },
                )
            )
    return sub_resources


def _build_default_animation(
    sub_resources: list[SubResource], fps: float
) -> dict[str, Any]:
    """Build a single 'default' animation dict from sub_resources."""
    return {
        "frames": [
            {"duration": 1.0, "texture": SubResourceRef(sub.id)}
            for sub in sub_resources
        ],
        "loop": True,
        "name": StringName("default"),
        "speed": fps,
    }


def split_sheet_json(
    image_path: Path,
    json_path: Path,
    image_res_path: str,
    fps: float = 10.0,
) -> GdResource:
    """Split a sprite sheet using JSON-defined regions.

    Reads frame rectangles from a JSON file and creates a SpriteFrames
    GdResource. JSON format: {"frames": [{"x": 0, "y": 0, "w": 32, "h": 32}, ...]}.
    """
    _require_pillow()
    img = Image.open(image_path)
    img.close()

    raw = json.loads(json_path.read_text())
    frames = raw.get("frames", [])

    ext = ExtResource(
        type="Texture2D",
        path=image_res_path,
        id=generate_resource_id("Texture2D"),
        uid=uid_to_text(generate_uid()),
    )

    sub_resources = _build_json_sub_resources(frames, ext)
    animation = _build_default_animation(sub_resources, fps)
    load_steps = 1 + len(sub_resources) + 1

    return GdResource(
        type="SpriteFrames",
        format=3,
        uid=uid_to_text(generate_uid()),
        load_steps=load_steps,
        ext_resources=[ext],
        sub_resources=sub_resources,
        resource_properties={"animations": [animation]},
    )


def _build_json_sub_resources(
    frames: list[dict[str, Any]], ext: ExtResource
) -> list[SubResource]:
    """Create AtlasTexture SubResources from JSON frame definitions."""
    sub_resources: list[SubResource] = []
    for frame in frames:
        region = Rect2(
            float(frame["x"]),
            float(frame["y"]),
            float(frame["w"]),
            float(frame["h"]),
        )
        sub_resources.append(
            SubResource(
                type="AtlasTexture",
                id=generate_resource_id("AtlasTexture"),
                properties={
                    "atlas": ExtResourceRef(ext.id),
                    "region": region,
                },
            )
        )
    return sub_resources
