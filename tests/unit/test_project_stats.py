"""Tests for project stats command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli

FIXTURE_PROJECT = str(
    Path(__file__).resolve().parent.parent / "fixtures" / "sample_project"
)


class TestProjectStats:
    """Verify project stats shows file counts."""

    def test_stats_exits_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["project", "stats", FIXTURE_PROJECT])
        assert result.exit_code == 0, result.output

    def test_stats_shows_name(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["project", "stats", FIXTURE_PROJECT])
        assert "Test Project" in result.output

    def test_stats_shows_counts(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["project", "stats", FIXTURE_PROJECT])
        assert "Scenes" in result.output
        assert "Scripts" in result.output

    def test_json_output(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "project", "stats", FIXTURE_PROJECT])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "Test Project"
        assert "scenes" in data
        assert "scripts" in data
        assert "total_nodes" in data

    def test_json_types(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "project", "stats", FIXTURE_PROJECT])
        data = json.loads(result.output)
        assert isinstance(data["scenes"], int)
        assert isinstance(data["scripts"], int)
        assert isinstance(data["total_nodes"], int)

    def test_nonexistent_path_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["project", "stats", "/nonexistent/path"])
        assert result.exit_code != 0
