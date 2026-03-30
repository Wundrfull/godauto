"""Tests for GitHub issue fixes (#1-#17).

Each test class covers one or more issues to verify the fix works as expected.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from gdauto.cli import cli
from gdauto.formats.values import ExtResourceRef
from gdauto.scene.builder import build_scene

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_PROJECT = str(FIXTURES_DIR / "sample_project")
FIXTURE_SIMPLE = str(FIXTURES_DIR / "aseprite_simple.json")


# ---------------------------------------------------------------------------
# Issue #9: scene create script property as ExtResource
# ---------------------------------------------------------------------------


class TestScriptPropertyPromotion:
    """Verify that string script properties become ExtResource refs."""

    def test_script_string_promoted_to_ext_resource_ref(self) -> None:
        definition = {
            "root": {
                "name": "Main",
                "type": "Node2D",
                "properties": {"script": "res://scripts/main.gd"},
            },
        }
        result = build_scene(definition)
        assert isinstance(result.nodes[0].properties["script"], ExtResourceRef)

    def test_script_promotion_creates_ext_resource(self) -> None:
        definition = {
            "root": {
                "name": "Main",
                "type": "Node2D",
                "properties": {"script": "res://scripts/main.gd"},
            },
        }
        result = build_scene(definition)
        scripts = [e for e in result.ext_resources if e.type == "Script"]
        assert len(scripts) == 1
        assert scripts[0].path == "res://scripts/main.gd"

    def test_script_promotion_on_child_node(self) -> None:
        definition = {
            "root": {
                "name": "Root",
                "type": "Node2D",
                "children": [
                    {
                        "name": "Player",
                        "type": "CharacterBody2D",
                        "properties": {"script": "res://scripts/player.gd"},
                    },
                ],
            },
        }
        result = build_scene(definition)
        player = [n for n in result.nodes if n.name == "Player"][0]
        assert isinstance(player.properties["script"], ExtResourceRef)

    def test_non_res_script_not_promoted(self) -> None:
        definition = {
            "root": {
                "name": "Root",
                "type": "Node2D",
                "properties": {"script": "some_local_path.gd"},
            },
        }
        result = build_scene(definition)
        # Non-res:// strings are not promoted
        assert result.nodes[0].properties["script"] == "some_local_path.gd"


# ---------------------------------------------------------------------------
# Issue #12: project validate autoload scripts not orphaned
# ---------------------------------------------------------------------------


class TestAutoloadNotOrphan:
    """Verify autoload-registered scripts are excluded from orphan list."""

    def test_autoload_script_not_in_orphans(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        (project_dir / "project.godot").write_text(
            '; config\n\nconfig_version=5\n\n'
            '[application]\n\nconfig/name="Test"\n\n'
            '[autoload]\n\nGameState="*res://scripts/game_state.gd"\n',
            encoding="utf-8",
        )
        scripts_dir = project_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "game_state.gd").write_text(
            "extends Node\n", encoding="utf-8"
        )
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "validate", str(project_dir)]
        )
        data = json.loads(result.output)
        assert "res://scripts/game_state.gd" not in data["orphan_scripts"]


# ---------------------------------------------------------------------------
# Issue #14: sprite validate --json always writes to stdout
# ---------------------------------------------------------------------------


class TestSpriteValidateStdout:
    """Verify validate always writes structured output to stdout."""

    def test_valid_result_on_stdout(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "sprite", "validate", str(FIXTURES_DIR / "sample.tres")]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["valid"] is True

    def test_invalid_result_still_on_stdout(self, tmp_path: Path) -> None:
        tres = tmp_path / "bad.tres"
        tres.write_text(
            '[gd_resource type="Theme" format=3]\n\n[resource]\n',
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "sprite", "validate", str(tres)]
        )
        assert result.exit_code == 1
        # Output should be parseable JSON on stdout
        data = json.loads(result.output)
        assert data["valid"] is False


# ---------------------------------------------------------------------------
# Issue #1: godot_version in project info --json
# ---------------------------------------------------------------------------


class TestGodotVersionKey:
    """Verify project info --json includes godot_version."""

    def test_godot_version_present(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "info", FIXTURE_PROJECT]
        )
        data = json.loads(result.output)
        assert "godot_version" in data

    def test_godot_version_value(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "info", FIXTURE_PROJECT]
        )
        data = json.loads(result.output)
        assert data["godot_version"] == "4.5"


# ---------------------------------------------------------------------------
# Issue #2: validate checks project.godot resource references
# ---------------------------------------------------------------------------


class TestProjectGodotRefValidation:
    """Verify validate checks main_scene and icon in project.godot."""

    def test_missing_main_scene_detected(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        (project_dir / "project.godot").write_text(
            '; config\n\nconfig_version=5\n\n'
            '[application]\n\n'
            'config/name="Test"\n'
            'run/main_scene="res://scenes/missing.tscn"\n'
            'config/icon="res://icon.svg"\n',
            encoding="utf-8",
        )
        (project_dir / "icon.svg").write_text("<svg/>", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "validate", str(project_dir)]
        )
        data = json.loads(result.output)
        assert "res://scenes/missing.tscn" in data["missing_resources"]

    def test_files_scanned_includes_project_godot(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        (project_dir / "project.godot").write_text(
            '; config\n\nconfig_version=5\n\n'
            '[application]\n\nconfig/name="Test"\n',
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "validate", str(project_dir)]
        )
        data = json.loads(result.output)
        # project.godot counts as +1
        assert data["files_scanned"] >= 1


# ---------------------------------------------------------------------------
# Issue #4: res:// path inference from -o
# ---------------------------------------------------------------------------


class TestResPathInference:
    """Verify --res-path is auto-inferred from -o directory."""

    def test_relative_output_subdir_infers_res_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        src = tmp_path / "input.json"
        src.write_text(Path(FIXTURE_SIMPLE).read_text(), encoding="utf-8")
        # Create the output subdirectory
        out_dir = tmp_path / "sprites" / "aseprite"
        out_dir.mkdir(parents=True)

        # cd into tmp_path so the relative -o resolves correctly
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "-j", "sprite", "import-aseprite", str(src),
                "-o", "sprites/aseprite/output.tres",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        # Should infer res://sprites/aseprite/simple_sheet.png
        assert data["image_path"] == "res://sprites/aseprite/simple_sheet.png"

    def test_absolute_output_uses_flat_path(self, tmp_path: Path) -> None:
        """Absolute -o paths can't be converted to res://, so use flat."""
        src = tmp_path / "input.json"
        src.write_text(Path(FIXTURE_SIMPLE).read_text(), encoding="utf-8")
        output = tmp_path / "output.tres"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["-j", "sprite", "import-aseprite", str(src), "-o", str(output)],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        # Absolute path, so flat fallback
        assert data["image_path"] == "res://simple_sheet.png"

    def test_no_output_uses_flat_path(self, tmp_path: Path) -> None:
        src = tmp_path / "input.json"
        src.write_text(Path(FIXTURE_SIMPLE).read_text(), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["-j", "sprite", "import-aseprite", str(src)],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        # No -o, so flat path
        assert data["image_path"] == "res://simple_sheet.png"


# ---------------------------------------------------------------------------
# Issue #6: speed field rounding in sprite validate
# ---------------------------------------------------------------------------


class TestSpeedRounding:
    """Verify speed values are rounded to 2 decimal places."""

    def test_speed_rounded(self) -> None:
        from gdauto.sprite.validator import validate_spriteframes

        result = validate_spriteframes(FIXTURES_DIR / "sample.tres")
        for anim in result["animations"]:
            speed = anim["speed"]
            if isinstance(speed, float):
                assert speed == round(speed, 2)


# ---------------------------------------------------------------------------
# Issue #10: project add-autoload command
# ---------------------------------------------------------------------------


class TestProjectAddAutoload:
    """Verify add-autoload registers singletons in project.godot."""

    def test_add_autoload_creates_entry(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        (project_dir / "project.godot").write_text(
            '; config\n\nconfig_version=5\n\n'
            '[application]\n\nconfig/name="Test"\n',
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "project", "add-autoload",
                "--name", "GameState",
                "--path", "res://scripts/game_state.gd",
                str(project_dir),
            ],
        )
        assert result.exit_code == 0, result.output
        content = (project_dir / "project.godot").read_text()
        assert "[autoload]" in content
        assert "GameState" in content
        assert "res://scripts/game_state.gd" in content

    def test_add_autoload_json_output(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        (project_dir / "project.godot").write_text(
            '; config\n\nconfig_version=5\n\n'
            '[application]\n\nconfig/name="Test"\n',
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "-j", "project", "add-autoload",
                "--name", "GameState",
                "--path", "res://scripts/game_state.gd",
                str(project_dir),
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["added"] is True
        assert data["name"] == "GameState"
        assert data["singleton"] is True

    def test_add_autoload_duplicate_fails(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        (project_dir / "project.godot").write_text(
            '; config\n\nconfig_version=5\n\n'
            '[application]\n\nconfig/name="Test"\n\n'
            '[autoload]\n\nGameState="*res://scripts/game_state.gd"\n',
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "project", "add-autoload",
                "--name", "GameState",
                "--path", "res://scripts/other.gd",
                str(project_dir),
            ],
        )
        assert result.exit_code != 0

    def test_add_autoload_no_singleton(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        (project_dir / "project.godot").write_text(
            '; config\n\nconfig_version=5\n\n'
            '[application]\n\nconfig/name="Test"\n',
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "-j", "project", "add-autoload",
                "--name", "Utils",
                "--path", "res://scripts/utils.gd",
                "--no-singleton",
                str(project_dir),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["singleton"] is False
        content = (project_dir / "project.godot").read_text()
        # No * prefix
        assert '"res://scripts/utils.gd"' in content


# ---------------------------------------------------------------------------
# Issue #11: autoloads strip * prefix in project info
# ---------------------------------------------------------------------------


class TestAutoloadStripPrefix:
    """Verify project info --json strips * from autoload paths."""

    def test_autoload_path_no_star(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["-j", "project", "info", FIXTURE_PROJECT]
        )
        data = json.loads(result.output)
        for _name, path in data["autoloads"].items():
            assert not path.startswith("*"), f"Path still has * prefix: {path}"
            assert path.startswith("res://")


# ---------------------------------------------------------------------------
# Issue #17: empty frames warning in structured output
# ---------------------------------------------------------------------------


class TestEmptyFramesWarning:
    """Verify empty frames produce a warning in the JSON output."""

    def test_empty_frames_json_has_warning(self, tmp_path: Path) -> None:
        empty_json = tmp_path / "empty.json"
        empty_json.write_text(
            json.dumps({
                "frames": [],
                "meta": {
                    "app": "test",
                    "version": "1.0",
                    "image": "empty.png",
                    "format": "RGBA8888",
                    "size": {"w": 0, "h": 0},
                    "scale": "1",
                    "frameTags": [],
                    "slices": [],
                },
            }),
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["-j", "sprite", "import-aseprite", str(empty_json)],
        )
        # Should either produce a warning in output or error
        # The important thing: no silent success with 0 frames
        output_text = result.output
        if result.exit_code == 0:
            data = json.loads(output_text)
            assert any("zero frames" in w.lower() for w in data.get("warnings", []))


# ---------------------------------------------------------------------------
# Issue #3: --check-only diagnostic key
# ---------------------------------------------------------------------------


class TestCheckOnlyDiagnostic:
    """Verify --check-only adds diagnostic keys when skipped."""

    def test_no_scripts_adds_skip_key(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        (project_dir / "project.godot").write_text(
            '; config\n\nconfig_version=5\n\n'
            '[application]\n\nconfig/name="Test"\n',
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["-j", "project", "validate", "--check-only", str(project_dir)],
        )
        data = json.loads(result.output)
        assert data.get("godot_check_skipped") is True
        assert "no .gd scripts" in data.get("godot_check_skip_reason", "")


# ---------------------------------------------------------------------------
# Issue #8: scene create --help has actual schema
# ---------------------------------------------------------------------------


class TestSceneCreateHelp:
    """Verify scene create --help shows JSON format, not circular reference."""

    def test_help_shows_json_format(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scene", "create", "--help"])
        assert "JSON FORMAT:" in result.output
        assert "root.name" in result.output
        assert "root.type" in result.output

    def test_help_no_circular_reference(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scene", "create", "--help"])
        assert "See 'gdauto scene create --help'" not in result.output


# ---------------------------------------------------------------------------
# Issue #5: sprite split --tags-from
# ---------------------------------------------------------------------------


class TestSplitTagsFrom:
    """Verify sprite split reads frameTags when --tags-from is provided."""

    def test_tags_from_produces_named_animations(self, tmp_path: Path) -> None:
        """Create a minimal sprite sheet image and JSON with tags."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        # Create a 64x32 test image (2 frames of 32x32)
        img = Image.new("RGBA", (64, 32), (255, 0, 0, 255))
        img_path = tmp_path / "sheet.png"
        img.save(img_path)

        # Create Aseprite JSON with frameTags
        tag_json = tmp_path / "sheet.json"
        tag_json.write_text(
            json.dumps({
                "frames": [
                    {
                        "filename": "0",
                        "frame": {"x": 0, "y": 0, "w": 32, "h": 32},
                        "rotated": False,
                        "trimmed": False,
                        "spriteSourceSize": {"x": 0, "y": 0, "w": 32, "h": 32},
                        "sourceSize": {"w": 32, "h": 32},
                        "duration": 100,
                    },
                    {
                        "filename": "1",
                        "frame": {"x": 32, "y": 0, "w": 32, "h": 32},
                        "rotated": False,
                        "trimmed": False,
                        "spriteSourceSize": {"x": 0, "y": 0, "w": 32, "h": 32},
                        "sourceSize": {"w": 32, "h": 32},
                        "duration": 100,
                    },
                ],
                "meta": {
                    "app": "test",
                    "version": "1.0",
                    "image": "sheet.png",
                    "format": "RGBA8888",
                    "size": {"w": 64, "h": 32},
                    "scale": "1",
                    "frameTags": [
                        {"name": "walk", "from": 0, "to": 0, "direction": "forward"},
                        {"name": "run", "from": 1, "to": 1, "direction": "forward"},
                    ],
                    "slices": [],
                },
            }),
            encoding="utf-8",
        )

        output = tmp_path / "output.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "-j", "sprite", "split", str(img_path),
                "--frame-size", "32x32",
                "--tags-from", str(tag_json),
                "-o", str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["animation_count"] == 2

        content = output.read_text()
        assert '&"walk"' in content
        assert '&"run"' in content

    def test_auto_detect_adjacent_json(self, tmp_path: Path) -> None:
        """Tags auto-detected from adjacent .json with same stem."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img = Image.new("RGBA", (32, 32), (255, 0, 0, 255))
        img_path = tmp_path / "sprite.png"
        img.save(img_path)

        # Adjacent JSON with same stem
        tag_json = tmp_path / "sprite.json"
        tag_json.write_text(
            json.dumps({
                "frames": [],
                "meta": {
                    "frameTags": [
                        {"name": "idle", "from": 0, "to": 0, "direction": "forward"},
                    ],
                },
            }),
            encoding="utf-8",
        )

        output = tmp_path / "output.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "-j", "sprite", "split", str(img_path),
                "--frame-size", "32x32",
                "-o", str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["animation_count"] == 1
        content = output.read_text()
        assert '&"idle"' in content
