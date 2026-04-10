"""Tests for Tiled .tmj/.tmx parser and import-tiled CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from auto_godot.cli import cli

FIXTURES = Path(__file__).parent.parent / "fixtures"
TMJ_FILE = FIXTURES / "sample_tiled.tmj"
TMX_FILE = FIXTURES / "sample_tiled.tmx"


# ---------------------------------------------------------------------------
# parse_tiled_json
# ---------------------------------------------------------------------------


class TestParseTiledJson:
    """Tests for parse_tiled_json."""

    def test_returns_list_with_one_tileset(self) -> None:
        from auto_godot.tileset.tiled import parse_tiled_json

        result = parse_tiled_json(TMJ_FILE)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_tileset_has_correct_fields(self) -> None:
        from auto_godot.tileset.tiled import parse_tiled_json

        ts = parse_tiled_json(TMJ_FILE)[0]
        assert ts.tile_width == 32
        assert ts.tile_height == 32
        assert ts.columns == 8
        assert ts.tile_count == 48
        assert ts.image_path == "terrain.png"
        assert ts.margin == 0
        assert ts.spacing == 0
        assert ts.image_width == 256
        assert ts.image_height == 192
        assert ts.name == "terrain"

    def test_embedded_tileset_extracted(self) -> None:
        """Embedded tileset (has tilewidth, no source key) is extracted."""
        from auto_godot.tileset.tiled import parse_tiled_json

        result = parse_tiled_json(TMJ_FILE)
        assert len(result) == 1
        assert result[0].tile_width == 32

    def test_external_tileset_reference_skipped(self, tmp_path: Path) -> None:
        """External .tsj reference (has source, no tilewidth) returns empty."""
        from auto_godot.tileset.tiled import parse_tiled_json

        data = {
            "tilesets": [
                {"firstgid": 1, "source": "terrain.tsj"}
            ],
            "layers": [],
        }
        tmj = tmp_path / "external.tmj"
        tmj.write_text(json.dumps(data))
        result = parse_tiled_json(tmj)
        assert result == []

    def test_missing_required_field_raises_validation_error(self, tmp_path: Path) -> None:
        from auto_godot.errors import ValidationError
        from auto_godot.tileset.tiled import parse_tiled_json

        data = {
            "tilesets": [
                {
                    "firstgid": 1,
                    "name": "broken",
                    "tilewidth": 32,
                    "tileheight": 32,
                    # missing: columns, tilecount, image
                }
            ],
        }
        tmj = tmp_path / "missing.tmj"
        tmj.write_text(json.dumps(data))
        with pytest.raises(ValidationError):
            parse_tiled_json(tmj)

    def test_rows_property(self) -> None:
        from auto_godot.tileset.tiled import parse_tiled_json

        ts = parse_tiled_json(TMJ_FILE)[0]
        # 48 tiles / 8 columns = 6 rows
        assert ts.rows == 6


# ---------------------------------------------------------------------------
# parse_tiled_xml
# ---------------------------------------------------------------------------


class TestParseTiledXml:
    """Tests for parse_tiled_xml."""

    def test_returns_list_with_one_tileset(self) -> None:
        from auto_godot.tileset.tiled import parse_tiled_xml

        result = parse_tiled_xml(TMX_FILE)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_extracts_tile_size_from_attributes(self) -> None:
        from auto_godot.tileset.tiled import parse_tiled_xml

        ts = parse_tiled_xml(TMX_FILE)[0]
        assert ts.tile_width == 32
        assert ts.tile_height == 32

    def test_extracts_image_source_from_child(self) -> None:
        from auto_godot.tileset.tiled import parse_tiled_xml

        ts = parse_tiled_xml(TMX_FILE)[0]
        assert ts.image_path == "terrain.png"
        assert ts.image_width == 256
        assert ts.image_height == 192

    def test_missing_tileset_element_returns_empty(self, tmp_path: Path) -> None:
        from auto_godot.tileset.tiled import parse_tiled_xml

        tmx = tmp_path / "empty.tmx"
        tmx.write_text(
            '<?xml version="1.0"?>\n<map version="1.10"></map>\n'
        )
        result = parse_tiled_xml(tmx)
        assert result == []


# ---------------------------------------------------------------------------
# parse_tiled_file dispatch
# ---------------------------------------------------------------------------


class TestParseTiledFile:
    """Tests for parse_tiled_file dispatch."""

    def test_dispatches_tmj(self) -> None:
        from auto_godot.tileset.tiled import parse_tiled_file

        result = parse_tiled_file(TMJ_FILE)
        assert len(result) == 1

    def test_dispatches_tmx(self) -> None:
        from auto_godot.tileset.tiled import parse_tiled_file

        result = parse_tiled_file(TMX_FILE)
        assert len(result) == 1

    def test_unsupported_extension_raises(self, tmp_path: Path) -> None:
        from auto_godot.errors import ValidationError
        from auto_godot.tileset.tiled import parse_tiled_file

        bad = tmp_path / "map.txt"
        bad.write_text("not a tiled file")
        with pytest.raises(ValidationError):
            parse_tiled_file(bad)


# ---------------------------------------------------------------------------
# CLI import-tiled
# ---------------------------------------------------------------------------


class TestImportTiledCli:
    """Tests for the tileset import-tiled CLI command."""

    def test_import_tmj_produces_tres(self, tmp_path: Path) -> None:
        runner = CliRunner()
        output = tmp_path / "from_tiled.tres"
        result = runner.invoke(
            cli,
            ["tileset", "import-tiled", str(TMJ_FILE), "-o", str(output)],
        )
        assert result.exit_code == 0, result.output
        assert output.exists()
        content = output.read_text()
        assert "TileSet" in content

    def test_import_tmx_produces_tres(self, tmp_path: Path) -> None:
        runner = CliRunner()
        output = tmp_path / "from_tiled.tres"
        result = runner.invoke(
            cli,
            ["tileset", "import-tiled", str(TMX_FILE), "-o", str(output)],
        )
        assert result.exit_code == 0, result.output
        assert output.exists()

    def test_nonexistent_file_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["tileset", "import-tiled", "/no/such/file.tmj"],
        )
        assert result.exit_code != 0

    def test_nonexistent_file_json_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "tileset", "import-tiled", "/no/such/file.tmj"],
        )
        assert result.exit_code != 0
        err = json.loads(result.output or result.stderr_bytes.decode() if hasattr(result, 'stderr_bytes') else "")
        assert err["code"] == "FILE_NOT_FOUND"

    def test_no_tilesets_error(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.tmj"
        empty.write_text(json.dumps({"tilesets": [], "layers": []}))
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["tileset", "import-tiled", str(empty)],
        )
        assert result.exit_code != 0

    def test_import_json_output(self, tmp_path: Path) -> None:
        runner = CliRunner()
        output = tmp_path / "out.tres"
        result = runner.invoke(
            cli,
            [
                "--json", "tileset", "import-tiled",
                str(TMJ_FILE), "-o", str(output),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["tileset_name"] == "terrain"
        assert data["tile_count"] == 48
        assert data["source_format"] == "tmj"
