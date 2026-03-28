"""End-to-end integration tests for the gdauto CLI.

Tests the full pipeline: create a project, inspect it, validate it,
and verify all command groups are accessible.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gdauto.cli import cli

FIXTURE_PROJECT = str(
    Path(__file__).resolve().parent.parent / "fixtures" / "sample_project"
)
FIXTURE_TRES = str(
    Path(__file__).resolve().parent.parent / "fixtures" / "sample.tres"
)


class TestCreateThenInfo:
    """Test pipeline: create project, then run info on it."""

    def test_create_then_info(self, tmp_path: Path) -> None:
        runner = CliRunner()
        # Create the project
        result = runner.invoke(
            cli, ["project", "create", "my-game", "-o", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output

        # Run info on the created project
        result = runner.invoke(
            cli, ["-j", "project", "info", str(tmp_path / "my-game")]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["name"] == "my-game"
        assert data["config_version"] == "5"


class TestCreateThenValidate:
    """Test pipeline: create project, then validate it."""

    def test_create_then_validate(self, tmp_path: Path) -> None:
        runner = CliRunner()
        # Create the project
        result = runner.invoke(
            cli, ["project", "create", "my-game", "-o", str(tmp_path)]
        )
        assert result.exit_code == 0

        # Validate the created project
        result = runner.invoke(
            cli, ["-j", "project", "validate", str(tmp_path / "my-game")]
        )
        data = json.loads(result.output)
        # A freshly created project should have zero issues
        assert data["issues_found"] == 0


class TestCreateThenInspectScene:
    """Test pipeline: create project, then inspect its main scene."""

    def test_create_then_inspect_scene(self, tmp_path: Path) -> None:
        runner = CliRunner()
        # Create the project
        result = runner.invoke(
            cli, ["project", "create", "my-game", "-o", str(tmp_path)]
        )
        assert result.exit_code == 0

        # Inspect the main scene
        scene_path = str(tmp_path / "my-game" / "scenes" / "main.tscn")
        result = runner.invoke(
            cli, ["-j", "resource", "inspect", scene_path]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "format" in data
        assert "type" in data


class TestErrorJsonFormat:
    """Verify error JSON format across commands."""

    def test_resource_inspect_error_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "resource", "inspect", "does_not_exist.tres"]
        )
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert "error" in data
        assert "code" in data

    def test_project_info_error_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "info", "/no/such/path"]
        )
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert "error" in data
        assert "code" in data


class TestAllCommandGroupsAccessible:
    """Verify all six command groups respond to --help."""

    def test_all_groups_help(self) -> None:
        runner = CliRunner()
        for group in ("project", "export", "sprite", "tileset", "scene", "resource"):
            result = runner.invoke(cli, [group, "--help"])
            assert result.exit_code == 0, f"Failed for group: {group}"


class TestFixtureProjectEndToEnd:
    """Verify commands work against the fixture project."""

    def test_fixture_project_info_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "info", FIXTURE_PROJECT]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "Test Project"

    def test_fixture_tres_inspect_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "resource", "inspect", FIXTURE_TRES]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["type"] == "SpriteFrames"

    def test_fixture_project_validate_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "validate", FIXTURE_PROJECT]
        )
        data = json.loads(result.output)
        assert "missing_resources" in data
        assert "files_scanned" in data
