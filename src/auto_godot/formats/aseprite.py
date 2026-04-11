"""Aseprite JSON export parser.

Reads Aseprite CLI JSON output (both array and hash frame formats) into
typed dataclasses for downstream processing by the SpriteFrames builder.

Handles all four animation directions, variable durations, trimmed sprites,
string-typed repeat fields, and zero-size frame detection.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from auto_godot.errors import ValidationError

if TYPE_CHECKING:
    from pathlib import Path


class AniDirection(Enum):
    """Aseprite animation direction values."""

    FORWARD = "forward"
    REVERSE = "reverse"
    PING_PONG = "pingpong"
    PING_PONG_REVERSE = "pingpong_reverse"


@dataclass(frozen=True, slots=True)
class FrameRect:
    """Rectangle region within a sprite sheet (integer pixels)."""

    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True, slots=True)
class AsepriteFrame:
    """A single frame from an Aseprite export."""

    filename: str
    frame: FrameRect
    trimmed: bool
    sprite_source_size: FrameRect
    source_size: tuple[int, int]
    duration: int


@dataclass(frozen=True, slots=True)
class AsepriteTag:
    """An animation tag (frame range with direction and repeat count)."""

    name: str
    from_frame: int
    to_frame: int
    direction: AniDirection
    repeat: int = 0
    color: str | None = None
    data: str | None = None


@dataclass(frozen=True, slots=True)
class AsepriteMeta:
    """Metadata from the Aseprite JSON export."""

    app: str
    version: str
    image: str
    format: str
    size: tuple[int, int]
    scale: str
    frame_tags: list[AsepriteTag] = field(default_factory=list)
    slices: list[dict] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AsepriteData:
    """Complete parsed Aseprite JSON export."""

    frames: list[AsepriteFrame]
    meta: AsepriteMeta


def parse_aseprite_json(path: Path) -> AsepriteData:
    """Parse an Aseprite JSON export file into typed dataclasses.

    Auto-detects array vs hash frame format. Hash format frames are sorted
    by sprite sheet position (x, y) to ensure consistent ordering regardless
    of dictionary key order.

    Raises ValidationError on invalid JSON or missing required keys.
    Warns on zero-size frames (w=0 or h=0).
    """
    raw = _load_json(path)
    _validate_has_frames(raw)
    frames = _parse_frames(raw["frames"])
    meta = _parse_meta(raw.get("meta", {}))
    return AsepriteData(frames=frames, meta=meta)


def _load_json(path: Path) -> dict:
    """Load and parse a JSON file, wrapping errors in ValidationError."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(
            message=f"Failed to parse JSON: {exc}",
            code="ASEPRITE_PARSE_ERROR",
            fix="Ensure the file is valid JSON exported by Aseprite",
        ) from exc
    except OSError as exc:
        raise ValidationError(
            message=f"Could not read file: {exc}",
            code="FILE_READ_ERROR",
            fix="Check that the file exists and is readable",
        ) from exc


def _validate_has_frames(raw: dict) -> None:
    """Check that the JSON contains a 'frames' key of the right type."""
    if "frames" not in raw:
        raise ValidationError(
            message="Missing 'frames' key in Aseprite JSON",
            code="ASEPRITE_INVALID_FORMAT",
            fix="Export with 'aseprite -b --data output.json'",
        )
    frames = raw["frames"]
    if not isinstance(frames, (list, dict)):
        raise ValidationError(
            message=f"'frames' must be an array or object, got {type(frames).__name__}",
            code="ASEPRITE_INVALID_FORMAT",
            fix="Export with 'aseprite -b --data output.json'",
        )


def _parse_frames(raw_frames: list | dict) -> list[AsepriteFrame]:
    """Parse frames from either array or hash format."""
    if isinstance(raw_frames, dict):
        # Hash format: convert to list sorted by spatial position
        frame_list = [
            _parse_frame(frame_data, filename=key)
            for key, frame_data in raw_frames.items()
        ]
        frame_list.sort(key=lambda f: (f.frame.x, f.frame.y))
        return frame_list
    # Array format
    return [
        _parse_frame(frame_data, filename=frame_data.get("filename", ""))
        for frame_data in raw_frames
    ]


def _parse_frame(raw_frame: dict, filename: str) -> AsepriteFrame:
    """Parse a single frame dict into an AsepriteFrame."""
    fr = raw_frame["frame"]
    frame_rect = FrameRect(x=fr["x"], y=fr["y"], w=fr["w"], h=fr["h"])

    sss = raw_frame.get("spriteSourceSize", fr)
    sprite_source = FrameRect(x=sss["x"], y=sss["y"], w=sss["w"], h=sss["h"])

    ss = raw_frame.get("sourceSize", {"w": fr["w"], "h": fr["h"]})
    source_size = (ss["w"], ss["h"])

    # Warn on zero-size frames (Pitfall 3)
    if frame_rect.w == 0 or frame_rect.h == 0:
        warnings.warn(
            f"Zero-size frame detected: '{filename}' has dimensions "
            f"{frame_rect.w}x{frame_rect.h}",
            stacklevel=3,
        )

    return AsepriteFrame(
        filename=filename,
        frame=frame_rect,
        trimmed=raw_frame.get("trimmed", False),
        sprite_source_size=sprite_source,
        source_size=source_size,
        duration=raw_frame.get("duration", 100),
    )


def _parse_meta(raw_meta: dict) -> AsepriteMeta:
    """Parse the meta section into an AsepriteMeta.

    Invalid tags are skipped with a warning rather than raising, so
    downstream consumers can implement partial failure (D-17).
    """
    size = raw_meta.get("size", {"w": 0, "h": 0})
    raw_tags = raw_meta.get("frameTags", [])
    tags: list[AsepriteTag] = []
    for raw_tag in raw_tags:
        try:
            tags.append(_parse_tag(raw_tag))
        except ValidationError as exc:
            tag_name = raw_tag.get("name", "<unknown>")
            warnings.warn(
                f"Skipping tag '{tag_name}': {exc.message}",
                stacklevel=2,
            )
    slices = raw_meta.get("slices", [])

    return AsepriteMeta(
        app=raw_meta.get("app", ""),
        version=raw_meta.get("version", ""),
        image=raw_meta.get("image", ""),
        format=raw_meta.get("format", ""),
        size=(size["w"], size["h"]),
        scale=raw_meta.get("scale", "1"),
        frame_tags=tags,
        slices=slices,
    )


def _parse_tag(raw_tag: dict) -> AsepriteTag:
    """Parse a single frameTag dict into an AsepriteTag."""
    direction_str = raw_tag["direction"]
    try:
        direction = AniDirection(direction_str)
    except ValueError as err:
        raise ValidationError(
            message=f"Unknown animation direction: '{direction_str}'",
            code="ASEPRITE_INVALID_DIRECTION",
            fix=f"Valid directions: {', '.join(d.value for d in AniDirection)}",
        ) from err

    # Repeat field is a string in Aseprite JSON (Pitfall 4)
    repeat = int(raw_tag.get("repeat", "0"))

    return AsepriteTag(
        name=raw_tag["name"],
        from_frame=raw_tag["from"],
        to_frame=raw_tag["to"],
        direction=direction,
        repeat=repeat,
        color=raw_tag.get("color"),
        data=raw_tag.get("data"),
    )
