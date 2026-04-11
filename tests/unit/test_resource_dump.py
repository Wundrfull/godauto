"""Tests for resource dump command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli

FIXTURE_TRES = str(
    Path(__file__).resolve().parent.parent / "fixtures" / "sample.tres"
)
FIXTURE_TSCN = str(
    Path(__file__).resolve().parent.parent / "fixtures" / "sample.tscn"
)


class TestDumpTres:
    """Verify resource dump on .tres files."""

    def test_dump_exits_zero(self) -> None:
        result = CliRunner().invoke(cli, ["resource", "dump", FIXTURE_TRES])
        assert result.exit_code == 0, result.output

    def test_dump_outputs_valid_json(self) -> None:
        result = CliRunner().invoke(cli, ["resource", "dump", FIXTURE_TRES])
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_dump_contains_all_sections(self) -> None:
        result = CliRunner().invoke(cli, ["resource", "dump", FIXTURE_TRES])
        data = json.loads(result.output)
        assert "ext_resources" in data
        assert "sub_resources" in data
        assert "properties" in data
        assert data["type"] == "SpriteFrames"

    def test_dump_section_ext_resources(self) -> None:
        result = CliRunner().invoke(
            cli, ["resource", "dump", FIXTURE_TRES, "--section", "ext_resources"]
        )
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["type"] == "Texture2D"

    def test_dump_section_sub_resources(self) -> None:
        result = CliRunner().invoke(
            cli, ["resource", "dump", FIXTURE_TRES, "--section", "sub_resources"]
        )
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["type"] == "AtlasTexture"

    def test_dump_section_properties(self) -> None:
        result = CliRunner().invoke(
            cli, ["resource", "dump", FIXTURE_TRES, "--section", "properties"]
        )
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert "animations" in data


class TestDumpTscn:
    """Verify resource dump on .tscn files."""

    def test_dump_exits_zero(self) -> None:
        result = CliRunner().invoke(cli, ["resource", "dump", FIXTURE_TSCN])
        assert result.exit_code == 0, result.output

    def test_dump_contains_scene_sections(self) -> None:
        result = CliRunner().invoke(cli, ["resource", "dump", FIXTURE_TSCN])
        data = json.loads(result.output)
        assert "ext_resources" in data
        assert "nodes" in data
        assert "connections" in data

    def test_dump_section_nodes(self) -> None:
        result = CliRunner().invoke(
            cli, ["resource", "dump", FIXTURE_TSCN, "--section", "nodes"]
        )
        data = json.loads(result.output)
        assert isinstance(data, list)
        names = [n["name"] for n in data]
        assert "Player" in names
        assert "Sprite" in names

    def test_dump_section_connections(self) -> None:
        result = CliRunner().invoke(
            cli, ["resource", "dump", FIXTURE_TSCN, "--section", "connections"]
        )
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["signal"] == "body_entered"


class TestDumpErrors:
    """Verify error handling."""

    def test_unsupported_format(self, tmp_path: Path) -> None:
        txt = tmp_path / "x.txt"
        txt.write_text("hello")
        result = CliRunner().invoke(cli, ["resource", "dump", str(txt)])
        assert result.exit_code != 0

    def test_invalid_section_tscn(self) -> None:
        result = CliRunner().invoke(
            cli, ["resource", "dump", FIXTURE_TSCN, "--section", "properties"]
        )
        assert result.exit_code != 0

    def test_invalid_section_tres(self) -> None:
        result = CliRunner().invoke(
            cli, ["resource", "dump", FIXTURE_TRES, "--section", "nodes"]
        )
        assert result.exit_code != 0

    def test_nonexistent_file(self) -> None:
        result = CliRunner().invoke(cli, ["resource", "dump", "/no/such/file.tscn"])
        assert result.exit_code != 0

    def test_nonexistent_file_json_error_contract(self) -> None:
        result = CliRunner().invoke(
            cli, ["-j", "resource", "dump", "/no/such/file.tscn"]
        )
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert "error" in data
        assert data["code"] == "FILE_NOT_FOUND"
        assert "fix" in data
