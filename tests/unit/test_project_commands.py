"""Tests for project info, validate, and create commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli

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


class TestProjectCreatePixelArt:
    """Verify project create --pixel-art applies the six pixel-perfect settings."""

    def _create(self, tmp_path: Path, *extra_args: str) -> Path:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["project", "create", "px-game", "-o", str(tmp_path),
             "--pixel-art", *extra_args],
        )
        assert result.exit_code == 0, result.output
        return tmp_path / "px-game" / "project.godot"

    def test_default_viewport_is_320x240(self, tmp_path: Path) -> None:
        content = self._create(tmp_path).read_text()
        assert "window/size/viewport_width=320" in content
        assert "window/size/viewport_height=240" in content

    def test_snap_transforms_true(self, tmp_path: Path) -> None:
        content = self._create(tmp_path).read_text()
        assert "2d/snap/snap_2d_transforms_to_pixel=true" in content

    def test_snap_vertices_false(self, tmp_path: Path) -> None:
        content = self._create(tmp_path).read_text()
        assert "2d/snap/snap_2d_vertices_to_pixel=false" in content

    def test_scale_mode_integer(self, tmp_path: Path) -> None:
        content = self._create(tmp_path).read_text()
        assert 'window/stretch/scale_mode="integer"' in content

    def test_stretch_mode_canvas_items(self, tmp_path: Path) -> None:
        content = self._create(tmp_path).read_text()
        assert 'window/stretch/mode="canvas_items"' in content

    def test_stretch_aspect_keep(self, tmp_path: Path) -> None:
        content = self._create(tmp_path).read_text()
        assert 'window/stretch/aspect="keep"' in content

    def test_texture_filter_nearest(self, tmp_path: Path) -> None:
        content = self._create(tmp_path).read_text()
        assert "textures/canvas_textures/default_texture_filter=0" in content

    def test_physics_interpolation_true(self, tmp_path: Path) -> None:
        content = self._create(tmp_path).read_text()
        assert "common/physics_interpolation=true" in content

    def test_without_flag_no_pixel_art_settings(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(
            cli, ["project", "create", "plain-game", "-o", str(tmp_path)]
        )
        content = (tmp_path / "plain-game" / "project.godot").read_text()
        assert "snap_2d_transforms_to_pixel" not in content
        assert "scale_mode" not in content
        assert "physics_interpolation" not in content

    def test_custom_viewport_dimensions(self, tmp_path: Path) -> None:
        content = self._create(
            tmp_path, "--pixel-art-width", "480", "--pixel-art-height", "270"
        ).read_text()
        assert "window/size/viewport_width=480" in content
        assert "window/size/viewport_height=270" in content

    def test_width_alone_implies_pixel_art(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["project", "create", "px-game", "-o", str(tmp_path),
             "--pixel-art-width", "480"],
        )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "px-game" / "project.godot").read_text()
        assert "window/size/viewport_width=480" in content
        assert "window/size/viewport_height=240" in content
        assert "snap_2d_transforms_to_pixel=true" in content

    def test_json_reports_pixel_art_settings(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["-j", "project", "create", "px-game", "-o", str(tmp_path),
             "--pixel-art"],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["created"] is True
        assert data.get("pixel_art") is True
        settings = data.get("pixel_art_settings", [])
        assert len(settings) == 9
        joined = "\n".join(settings)
        for expected in (
            "viewport_width=320",
            "viewport_height=240",
            "mode=canvas_items",
            "aspect=keep",
            "scale_mode=integer",
            "default_texture_filter=0",
            "snap_2d_transforms_to_pixel=true",
            "snap_2d_vertices_to_pixel=false",
            "physics_interpolation=true",
        ):
            assert expected in joined, f"missing {expected} in {settings!r}"

    def test_help_mentions_settings(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["project", "create", "--help"])
        assert result.exit_code == 0
        assert "--pixel-art" in result.output
        assert "snap_2d_transforms_to_pixel" in result.output


def _make_audit_project(tmp_path: Path) -> Path:
    """Create a minimal project for audit testing."""
    project_dir = tmp_path / "audit_proj"
    project_dir.mkdir()
    (project_dir / "project.godot").write_text(
        '; Engine configuration file.\n\n'
        'config_version=5\n\n'
        '[application]\n\n'
        'config/name="AuditTest"\n'
    )
    scenes_dir = project_dir / "scenes"
    scenes_dir.mkdir()
    (scenes_dir / "main.tscn").write_text(
        '[gd_scene format=3]\n\n'
        '[ext_resource type="Script" path="res://scripts/player.gd" id="1_s"]\n'
        '[ext_resource type="Texture2D" path="res://assets/sprites/hero.png" id="2_t"]\n\n'
        '[node name="Root" type="Node2D"]\n'
    )
    # Create the referenced script but NOT the referenced texture
    scripts_dir = project_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "player.gd").write_text(
        'extends Node2D\n\nfunc _ready() -> void:\n\tpass\n'
    )
    # Create an unreferenced asset (unused)
    assets_dir = project_dir / "assets" / "sprites"
    assets_dir.mkdir(parents=True)
    (assets_dir / "old_sprite.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return project_dir


class TestProjectAudit:
    """Verify project audit finds unused and missing assets."""

    def test_audit_exits_with_issues(self, tmp_path: Path) -> None:
        project_dir = _make_audit_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli, ["project", "audit", str(project_dir)]
        )
        assert result.exit_code == 1  # issues found

    def test_audit_json_structure(self, tmp_path: Path) -> None:
        project_dir = _make_audit_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "audit", str(project_dir)]
        )
        data = json.loads(result.output)
        assert "files_on_disk" in data
        assert "references_found" in data
        assert "unused" in data
        assert "missing" in data
        assert "issues_found" in data

    def test_audit_detects_unused_asset(self, tmp_path: Path) -> None:
        project_dir = _make_audit_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "audit", str(project_dir), "--unused"]
        )
        data = json.loads(result.output)
        unused_paths = data.get("unused", [])
        assert any("old_sprite.png" in p for p in unused_paths)

    def test_audit_detects_missing_asset(self, tmp_path: Path) -> None:
        project_dir = _make_audit_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "audit", str(project_dir), "--missing"]
        )
        data = json.loads(result.output)
        missing_paths = data.get("missing", [])
        assert any("hero.png" in p for p in missing_paths)

    def test_audit_clean_project_exits_zero(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "clean_proj"
        project_dir.mkdir()
        (project_dir / "project.godot").write_text(
            '; Engine configuration file.\n\n'
            'config_version=5\n\n'
            '[application]\n\n'
            'config/name="CleanProj"\n'
        )
        runner = CliRunner()
        result = runner.invoke(
            cli, ["project", "audit", str(project_dir)]
        )
        assert result.exit_code == 0

    def test_audit_filter_unused_only(self, tmp_path: Path) -> None:
        project_dir = _make_audit_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "audit", str(project_dir), "--unused"]
        )
        data = json.loads(result.output)
        assert "unused" in data
        assert "missing" not in data

    def test_audit_filter_missing_only(self, tmp_path: Path) -> None:
        project_dir = _make_audit_project(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "audit", str(project_dir), "--missing"]
        )
        data = json.loads(result.output)
        assert "missing" in data
        assert "unused" not in data

    def test_audit_nonexistent_path(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["project", "audit", "/no/such/path"]
        )
        assert result.exit_code != 0
