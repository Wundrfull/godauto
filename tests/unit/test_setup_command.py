"""Tests for the setup command (tool detection)."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


class TestSetupCommand:
    """Verify setup command detects and reports external tools."""

    def test_setup_exits_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "--auto"])
        assert result.exit_code == 0, result.output

    def test_setup_reports_tools(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "--auto"])
        assert "godot" in result.output.lower()
        assert "aseprite" in result.output.lower()
        assert "pixel_mcp" in result.output.lower()

    def test_setup_json_structure(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "setup", "--auto"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "tools" in data
        assert "all_found" in data
        assert "godot" in data["tools"]
        assert "aseprite" in data["tools"]
        assert "pixel_mcp" in data["tools"]

    def test_setup_tool_has_found_key(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "setup", "--auto"])
        data = json.loads(result.output)
        for tool_name, tool_info in data["tools"].items():
            assert "found" in tool_info, f"{tool_name} missing 'found' key"
            assert isinstance(tool_info["found"], bool)

    def test_setup_tool_has_path_key(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "setup", "--auto"])
        data = json.loads(result.output)
        for tool_name, tool_info in data["tools"].items():
            assert "path" in tool_info, f"{tool_name} missing 'path' key"

    def test_setup_found_tool_has_valid_path(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "setup", "--auto"])
        data = json.loads(result.output)
        for tool_name, tool_info in data["tools"].items():
            if tool_info["found"]:
                assert tool_info["path"] is not None
                assert Path(tool_info["path"]).exists(), (
                    f"{tool_name} reports found but path does not exist: "
                    f"{tool_info['path']}"
                )

    def test_setup_all_found_consistent(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "setup", "--auto"])
        data = json.loads(result.output)
        expected = all(t["found"] for t in data["tools"].values())
        assert data["all_found"] == expected

    def test_setup_human_output_shows_status(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["setup", "--auto"])
        # Should show FOUND or NOT FOUND for each tool
        assert "FOUND" in result.output or "NOT FOUND" in result.output

    def test_setup_without_auto_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["setup"])
        # Should still work without --auto (same behavior currently)
        assert result.exit_code == 0, result.output
