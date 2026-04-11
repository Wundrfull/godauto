"""TexturePacker JSON metadata parser.

Parses TexturePacker JSON exports (both hash and array frame formats)
and converts to AsepriteFrame objects for reuse with the SpriteFrames
builder.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from auto_godot.errors import ValidationError
from auto_godot.formats.aseprite import AsepriteFrame, FrameRect


def _parse_rect(d: dict[str, int]) -> FrameRect:
    return FrameRect(x=d["x"], y=d["y"], w=d["w"], h=d["h"])


def _parse_frame(name: str, data: dict[str, Any], duration_ms: int) -> AsepriteFrame:
    """Convert a single TexturePacker frame entry to AsepriteFrame."""
    frame = _parse_rect(data["frame"])
    sss = _parse_rect(data.get("spriteSourceSize", data["frame"]))
    src = data.get("sourceSize", {"w": frame.w, "h": frame.h})
    return AsepriteFrame(
        filename=name,
        frame=frame,
        trimmed=data.get("trimmed", False),
        sprite_source_size=sss,
        source_size=(src["w"], src["h"]),
        duration=duration_ms,
    )


def parse_texturepacker_json(
    path: Path, fps: float = 10.0,
) -> tuple[list[AsepriteFrame], str]:
    """Parse a TexturePacker JSON file.

    Returns (frames sorted by filename, image filename from meta).
    Supports both hash and array frame formats.
    """
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(
            message=f"Failed to read TexturePacker JSON: {exc}",
            code="TEXTUREPACKER_READ_ERROR",
            fix="Check the file is valid TexturePacker JSON",
        ) from exc

    raw_frames = data.get("frames")
    if raw_frames is None:
        raise ValidationError(
            message="No 'frames' key in TexturePacker JSON",
            code="TEXTUREPACKER_NO_FRAMES",
            fix="Export from TexturePacker with JSON data format",
        )

    duration_ms = max(1, int(1000.0 / fps))
    frames: list[AsepriteFrame] = []

    if isinstance(raw_frames, dict):
        for name, fdata in raw_frames.items():
            frames.append(_parse_frame(name, fdata, duration_ms))
    elif isinstance(raw_frames, list):
        for fdata in raw_frames:
            name = fdata.get("filename", f"frame_{len(frames)}")
            frames.append(_parse_frame(name, fdata, duration_ms))
    else:
        raise ValidationError(
            message="'frames' must be an object or array",
            code="TEXTUREPACKER_INVALID_FRAMES",
            fix="Re-export from TexturePacker",
        )

    frames.sort(key=lambda f: f.filename)

    meta = data.get("meta", {})
    image = meta.get("image", path.with_suffix(".png").name)

    return frames, image


# Pattern to strip trailing frame numbers: "idle_0.png" -> "idle"
_TRAILING_NUM = re.compile(r"[_ -]?\d+$")


def group_frames_by_animation(
    frames: list[AsepriteFrame],
) -> dict[str, list[AsepriteFrame]]:
    """Group frames into animations by filename prefix.

    Strips file extension and trailing numbers/separators to derive
    animation names. E.g., "idle_0.png", "idle_1.png" -> "idle".
    """
    groups: dict[str, list[AsepriteFrame]] = {}
    for frame in frames:
        stem = Path(frame.filename).stem
        name = _TRAILING_NUM.sub("", stem) or stem
        groups.setdefault(name, []).append(frame)
    return groups
