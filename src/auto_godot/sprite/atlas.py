"""Atlas creator: shelf-packing compositor for sprite images.

Composites multiple individual sprite images into a single atlas texture
using a shelf-packing algorithm, and generates a SpriteFrames GdResource
with AtlasTexture regions for each placed image.

Requires Pillow for image loading and compositing.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from auto_godot.errors import AutoGodotError, ValidationError
from auto_godot.formats.tres import ExtResource, GdResource, SubResource
from auto_godot.formats.uid import generate_resource_id, generate_uid, uid_to_text
from auto_godot.formats.values import ExtResourceRef, Rect2, StringName, SubResourceRef

if TYPE_CHECKING:
    from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment,misc]


def _require_pillow() -> None:
    """Raise AutoGodotError if Pillow is not installed."""
    if Image is None:
        raise AutoGodotError(
            message="Pillow is required for sprite create-atlas",
            code="PILLOW_NOT_INSTALLED",
            fix="Install with: pip install auto-godot[image] (or: uv pip install auto-godot[image])",
        )


def next_power_of_two(n: int) -> int:
    """Return the smallest power of two >= n.

    Returns 1 for n <= 0. If n is already a power of two, returns n.
    """
    if n <= 0:
        return 1
    if n & (n - 1) == 0:
        return n
    return 1 << (n - 1).bit_length()


def create_atlas(
    image_paths: list[Path],
    atlas_res_path: str,
    power_of_two: bool = True,
) -> tuple[Any, GdResource]:
    """Create an atlas image and SpriteFrames resource from input images.

    Uses shelf packing (tallest-first, left-to-right rows) to place
    images. Returns (atlas_image, resource) tuple.
    """
    _require_pillow()
    if not image_paths:
        raise ValidationError(
            message="No images provided; need at least one image file",
            code="ATLAS_NO_IMAGES",
            fix="Provide at least one image file",
        )

    source_images = [Image.open(p) for p in image_paths]
    placements = _compute_shelf_placements(source_images)
    atlas_w, atlas_h = _compute_atlas_dimensions(placements, power_of_two)

    atlas_img = Image.new("RGBA", (atlas_w, atlas_h), (0, 0, 0, 0))
    for img, (x, y, _w, _h) in zip(source_images, placements, strict=False):
        atlas_img.paste(img, (x, y))

    for img in source_images:
        img.close()

    resource = _build_atlas_resource(placements, atlas_res_path)
    return (atlas_img, resource)


def _compute_shelf_placements(
    images: list[Any],
) -> list[tuple[int, int, int, int]]:
    """Compute (x, y, w, h) placements using shelf packing.

    Sorts images by height descending for better packing. Uses the
    square root of total area as initial shelf width estimate.
    """
    indexed = list(enumerate(images))
    indexed.sort(key=lambda pair: pair[1].height, reverse=True)

    total_area = sum(img.width * img.height for img in images)
    shelf_width = max(int(math.sqrt(total_area) * 1.5), images[0].width)

    # Shelf packing: fill left-to-right, start new row when full
    placements: list[tuple[int, int, int, int, int]] = []
    shelf_x = 0
    shelf_y = 0
    shelf_height = 0

    for orig_idx, img in indexed:
        if shelf_x + img.width > shelf_width and shelf_x > 0:
            shelf_y += shelf_height
            shelf_x = 0
            shelf_height = 0
        placements.append((orig_idx, shelf_x, shelf_y, img.width, img.height))
        shelf_x += img.width
        shelf_height = max(shelf_height, img.height)

    # Restore original order
    placements.sort(key=lambda p: p[0])
    return [(x, y, w, h) for _, x, y, w, h in placements]


def _compute_atlas_dimensions(
    placements: list[tuple[int, int, int, int]], power_of_two: bool
) -> tuple[int, int]:
    """Compute final atlas dimensions from placements."""
    max_x = max(x + w for x, y, w, h in placements)
    max_y = max(y + h for x, y, w, h in placements)
    if power_of_two:
        return (next_power_of_two(max_x), next_power_of_two(max_y))
    return (max_x, max_y)


def _build_atlas_resource(
    placements: list[tuple[int, int, int, int]], atlas_res_path: str
) -> GdResource:
    """Build a SpriteFrames GdResource from atlas placements."""
    ext = ExtResource(
        type="Texture2D",
        path=atlas_res_path,
        id=generate_resource_id("Texture2D"),
        uid=uid_to_text(generate_uid()),
    )

    sub_resources: list[SubResource] = []
    for x, y, w, h in placements:
        sub_resources.append(
            SubResource(
                type="AtlasTexture",
                id=generate_resource_id("AtlasTexture"),
                properties={
                    "atlas": ExtResourceRef(ext.id),
                    "region": Rect2(float(x), float(y), float(w), float(h)),
                },
            )
        )

    animation: dict[str, Any] = {
        "frames": [
            {"duration": 1.0, "texture": SubResourceRef(sub.id)}
            for sub in sub_resources
        ],
        "loop": True,
        "name": StringName("default"),
        "speed": 10.0,
    }

    return GdResource(
        type="SpriteFrames",
        format=3,
        uid=uid_to_text(generate_uid()),
        load_steps=None,
        ext_resources=[ext],
        sub_resources=sub_resources,
        resource_properties={"animations": [animation]},
    )
