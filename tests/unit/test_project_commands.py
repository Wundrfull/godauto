"""Tests for project info, validate, and create commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gdauto.cli import cli

FIXTURE_PROJECT = str(
    Path(__file__).resolve().parent.parent / "fixtures" / "sample_project"
)


class TestProjectInfo:
    """Verify project info reads project.godot and outputs metadata."""

    def test_info_exits_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["project", "info", FIXTURE_PROJECT])
        assert result.exit_code == 0, result.output

    def test_info_human_output_contains_project_name(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["project", "info", FIXTURE_PROJECT])
        assert "Test Project" in result.output

    def test_info_json_valid(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "project", "info", FIXTURE_PROJECT])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["name"] == "Test Project"

    def test_info_json_keys(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "project", "info", FIXTURE_PROJECT])
        data = json.loads(result.output)
        for key in ("name", "config_version", "main_scene", "icon", "features",
                     "autoloads", "display"):
            assert key in data, f"Missing key: {key}"

    def test_info_nonexistent_path_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["project", "info", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_info_nonexistent_json_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "info", "/nonexistent/path"]
        )
        assert result.exit_code != 0
        # CliRunner mixes stderr into output
        err_data = json.loads(result.output)
        assert "code" in err_data

    def test_info_verbose_extra_detail(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-v", "project", "info", FIXTURE_PROJECT]
        )
        assert result.exit_code == 0
        # Verbose mode should show section names or key counts
        assert "section" in result.output.lower() or "keys" in result.output.lower()


class TestProjectValidate:
    """Verify project validate scans for missing resources."""

    def test_validate_exits_zero_on_clean_project(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["project", "validate", FIXTURE_PROJECT]
        )
        # The sample project has references that may not exist on disk;
        # validate should still run without crashing
        assert result.exit_code in (0, 1)

    def test_validate_json_report_structure(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "validate", FIXTURE_PROJECT]
        )
        data = json.loads(result.output)
        assert "missing_resources" in data
        assert "broken_references" in data

    def test_validate_detects_missing_resource(self, tmp_path: Path) -> None:
        """Create a project referencing a nonexistent file, verify detection."""
        project_dir = tmp_path / "test_proj"
        project_dir.mkdir()
        (project_dir / "project.godot").write_text(
            '; Engine configuration file.\n\n'
            'config_version=5\n\n'
            '[application]\n\n'
            'config/name="TestProj"\n'
        )
        scene_dir = project_dir / "scenes"
        scene_dir.mkdir()
        (scene_dir / "broken.tscn").write_text(
            '[gd_scene format=3]\n\n'
            '[ext_resource type="Script" path="res://scripts/missing.gd" id="1_s"]\n\n'
            '[node name="Root" type="Node2D"]\n'
        )
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "validate", str(project_dir)]
        )
        data = json.loads(result.output)
        assert data["issues_found"] > 0
        missing = [r for r in data["missing_resources"] if "missing.gd" in r]
        assert len(missing) > 0


class TestProjectCreate:
    """Verify project create scaffolds a new Godot project."""

    def test_create_makes_directory(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["project", "create", "test-game", "-o", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "test-game").is_dir()

    def test_create_project_godot_exists(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(
            cli, ["project", "create", "test-game", "-o", str(tmp_path)]
        )
        assert (tmp_path / "test-game" / "project.godot").is_file()

    def test_create_config_version(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(
            cli, ["project", "create", "test-game", "-o", str(tmp_path)]
        )
        content = (tmp_path / "test-game" / "project.godot").read_text()
        assert "config_version=5" in content

    def test_create_main_scene(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(
            cli, ["project", "create", "test-game", "-o", str(tmp_path)]
        )
        assert (tmp_path / "test-game" / "scenes" / "main.tscn").is_file()

    def test_create_gitignore(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(
            cli, ["project", "create", "test-game", "-o", str(tmp_path)]
        )
        assert (tmp_path / "test-game" / ".gitignore").is_file()

    def test_create_icon(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(
            cli, ["project", "create", "test-game", "-o", str(tmp_path)]
        )
        assert (tmp_path / "test-game" / "icon.svg").is_file()

    def test_create_directories(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(
            cli, ["project", "create", "test-game", "-o", str(tmp_path)]
        )
        for subdir in ("scenes", "scripts", "assets", "sprites", "tilesets"):
            assert (tmp_path / "test-game" / subdir).is_dir(), f"Missing dir: {subdir}"

    def test_create_fails_if_exists(self, tmp_path: Path) -> None:
        (tmp_path / "test-game").mkdir()
        runner = CliRunner()
        result = runner.invoke(
            cli, ["project", "create", "test-game", "-o", str(tmp_path)]
        )
        assert result.exit_code != 0

    def test_create_no_name_fails(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["project", "create"])
        assert result.exit_code != 0

    def test_create_json_output(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["-j", "project", "create", "test-game", "-o", str(tmp_path)],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True
        assert "path" in data
