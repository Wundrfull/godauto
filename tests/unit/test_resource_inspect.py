"""Tests for resource inspect command."""

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


class TestResourceInspectTres:
    """Verify resource inspect handles .tres files."""

    def test_inspect_tres_exits_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["resource", "inspect", FIXTURE_TRES])
        assert result.exit_code == 0, result.output

    def test_inspect_tres_json_valid(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "resource", "inspect", FIXTURE_TRES]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_inspect_tres_json_metadata_keys(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "resource", "inspect", FIXTURE_TRES]
        )
        data = json.loads(result.output)
        for key in ("file", "format", "type", "uid", "warnings", "resource"):
            assert key in data, f"Missing key: {key}"

    def test_inspect_tres_json_resource_sections(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "resource", "inspect", FIXTURE_TRES]
        )
        data = json.loads(result.output)
        res = data["resource"]
        assert "ext_resources" in res
        assert "sub_resources" in res
        assert isinstance(res["ext_resources"], list)
        assert isinstance(res["sub_resources"], list)

    def test_inspect_tres_shows_resource_type(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "resource", "inspect", FIXTURE_TRES]
        )
        data = json.loads(result.output)
        assert data["type"] == "SpriteFrames"

    def test_inspect_tres_human_output_contains_filepath(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["resource", "inspect", FIXTURE_TRES])
        # Human output should mention the file somehow
        assert "sample.tres" in result.output or "SpriteFrames" in result.output


class TestResourceInspectTscn:
    """Verify resource inspect handles .tscn files."""

    def test_inspect_tscn_exits_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["resource", "inspect", FIXTURE_TSCN])
        assert result.exit_code == 0, result.output

    def test_inspect_tscn_json_contains_nodes(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "resource", "inspect", FIXTURE_TSCN]
        )
        data = json.loads(result.output)
        nodes = data["resource"]["nodes"]
        assert isinstance(nodes, list)
        assert len(nodes) > 0


class TestResourceInspectErrors:
    """Verify error handling for resource inspect."""

    def test_inspect_nonexistent_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["resource", "inspect", "nonexistent.tres"]
        )
        assert result.exit_code != 0

    def test_inspect_nonexistent_json_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "resource", "inspect", "nonexistent.tres"]
        )
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert "code" in data

    def test_inspect_unsupported_format(self, tmp_path: Path) -> None:
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not a godot file")
        runner = CliRunner()
        result = runner.invoke(
            cli, ["resource", "inspect", str(txt_file)]
        )
        assert result.exit_code != 0

    def test_inspect_unsupported_format_json(self, tmp_path: Path) -> None:
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not a godot file")
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "resource", "inspect", str(txt_file)]
        )
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert data["code"] == "UNSUPPORTED_FORMAT"


class TestResourceInspectGodotValues:
    """Verify Godot-native value serialization in JSON output."""

    def test_json_uses_godot_native_strings(self) -> None:
        """Godot value types should appear as their native format in JSON."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "resource", "inspect", FIXTURE_TRES]
        )
        data = json.loads(result.output)
        # The sample.tres has Rect2 values in sub_resources
        subs = data["resource"]["sub_resources"]
        assert len(subs) > 0
        # Region property should be serialized as Godot-native string
        region = subs[0]["properties"].get("region", "")
        assert "Rect2" in str(region), f"Expected Godot-native Rect2, got: {region}"
