"""Tiled .tmx/.tmj parser for basic tileset extraction (per D-08).

Parses Tiled map files to extract embedded tileset definitions. External
tileset references (.tsj files) are skipped; only inline tileset data
with full attribute sets is extracted. Uses stdlib json and
xml.etree.ElementTree (per D-09: no third-party parsing dependencies).
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import TYPE_CHECKING

from auto_godot.errors import ValidationError

if TYPE_CHECKING:
    from pathlib import Path

_REQUIRED_JSON_FIELDS = ("tilewidth", "tileheight", "columns", "tilecount", "image")


@dataclass
class TiledTileset:
    """Minimal tileset data extracted from a Tiled file."""

    name: str
    tile_width: int
    tile_height: int
    columns: int
    tile_count: int
    image_path: str
    image_width: int
    image_height: int
    margin: int = 0
    spacing: int = 0

    @property
    def rows(self) -> int:
        """Compute row count from tile_count and columns."""
        if self.columns <= 0:
            return 0
        return (self.tile_count + self.columns - 1) // self.columns


def parse_tiled_json(path: Path) -> list[TiledTileset]:
    """Parse a Tiled .tmj (JSON) file and extract embedded tilesets.

    Skips external tileset references (entries with a 'source' key but
    no 'tilewidth'). Raises ValidationError if a required field is missing
    from an embedded tileset entry.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    tilesets_raw = data.get("tilesets", [])
    result: list[TiledTileset] = []

    for entry in tilesets_raw:
        # Skip external .tsj references
        if "source" in entry and "tilewidth" not in entry:
            continue
        _validate_json_entry(entry)
        result.append(_tileset_from_json(entry))

    return result


def parse_tiled_xml(path: Path) -> list[TiledTileset]:
    """Parse a Tiled .tmx (XML) file and extract embedded tilesets.

    Finds all <tileset> elements and extracts attributes and <image>
    child elements. Returns an empty list if no tileset elements exist.
    """
    tree = ET.parse(path)  # noqa: S314
    root = tree.getroot()
    result: list[TiledTileset] = []

    for ts_elem in root.findall("tileset"):
        tileset = _tileset_from_xml(ts_elem)
        if tileset is not None:
            result.append(tileset)

    return result


def parse_tiled_file(path: Path) -> list[TiledTileset]:
    """Parse a Tiled file, dispatching by file extension.

    Supports .tmj/.json for JSON format and .tmx/.xml for XML format.
    Raises ValidationError for unsupported extensions.
    """
    suffix = path.suffix.lower()
    if suffix in (".tmj", ".json"):
        return parse_tiled_json(path)
    if suffix in (".tmx", ".xml"):
        return parse_tiled_xml(path)
    raise ValidationError(
        message=f"Unsupported Tiled file format: {suffix}",
        code="UNSUPPORTED_TILED_FORMAT",
        fix="Use .tmj (JSON) or .tmx (XML) Tiled map files",
    )


def _validate_json_entry(entry: dict) -> None:
    """Check that all required fields are present in a JSON tileset entry."""
    missing = [f for f in _REQUIRED_JSON_FIELDS if f not in entry]
    if missing:
        raise ValidationError(
            message=f"Tiled tileset missing required fields: {', '.join(missing)}",
            code="TILED_MISSING_FIELDS",
            fix="Ensure the Tiled file has embedded tileset data (not external .tsj)",
        )


def _tileset_from_json(entry: dict) -> TiledTileset:
    """Build a TiledTileset from a JSON tileset entry."""
    return TiledTileset(
        name=entry.get("name", ""),
        tile_width=int(entry["tilewidth"]),
        tile_height=int(entry["tileheight"]),
        columns=int(entry["columns"]),
        tile_count=int(entry["tilecount"]),
        image_path=str(entry["image"]),
        image_width=int(entry.get("imagewidth", 0)),
        image_height=int(entry.get("imageheight", 0)),
        margin=int(entry.get("margin", 0)),
        spacing=int(entry.get("spacing", 0)),
    )


def _tileset_from_xml(ts_elem: ET.Element) -> TiledTileset | None:
    """Build a TiledTileset from an XML <tileset> element.

    Returns None if the element lacks required attributes or an <image>
    child element.
    """
    image_elem = ts_elem.find("image")
    if image_elem is None:
        return None

    tilewidth = ts_elem.get("tilewidth")
    tileheight = ts_elem.get("tileheight")
    if tilewidth is None or tileheight is None:
        return None

    return TiledTileset(
        name=ts_elem.get("name", ""),
        tile_width=int(tilewidth),
        tile_height=int(tileheight),
        columns=int(ts_elem.get("columns", "0")),
        tile_count=int(ts_elem.get("tilecount", "0")),
        image_path=image_elem.get("source", ""),
        image_width=int(image_elem.get("width", "0")),
        image_height=int(image_elem.get("height", "0")),
        margin=int(ts_elem.get("margin", "0")),
        spacing=int(ts_elem.get("spacing", "0")),
    )
