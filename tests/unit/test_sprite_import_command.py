"""Tests for sprite import-aseprite CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gdauto.cli import cli

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_SIMPLE = str(FIXTURES_DIR / "aseprite_simple.json")
FIXTURE_NO_TAGS = str(FIXTURES_DIR / "aseprite_no_tags.json")


class TestImportAsepriteBasic:
    """Verify basic import-aseprite functionality."""

    def test_import_creates_tres_file(self, tmp_path: Path) -> None:
        output = tmp_path / "output.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "import-aseprite", FIXTURE_SIMPLE, "-o", str(output)],
        )
        assert result.exit_code == 0, result.output + (result.stderr or "")
        assert output.exists()

    def test_import_default_output_path(self, tmp_path: Path) -> None:
        """Input foo.json produces foo.tres in the same directory."""
        src = tmp_path / "character.json"
        src.write_text((FIXTURES_DIR / "aseprite_simple.json").read_text())
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "import-aseprite", str(src)],
        )
        assert result.exit_code == 0, result.output + (result.stderr or "")
        expected = tmp_path / "character.tres"
        assert expected.exists()

    def test_generated_tres_has_spriteframes_header(self, tmp_path: Path) -> None:
        output = tmp_path / "output.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "import-aseprite", FIXTURE_SIMPLE, "-o", str(output)],
        )
        assert result.exit_code == 0, result.output
        content = output.read_text()
        assert '[gd_resource type="SpriteFrames"' in content

    def test_generated_tres_has_atlas_texture_sub_resources(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / "output.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "import-aseprite", FIXTURE_SIMPLE, "-o", str(output)],
        )
        assert result.exit_code == 0, result.output
        content = output.read_text()
        assert 'type="AtlasTexture"' in content

    def test_generated_tres_has_animation_name(self, tmp_path: Path) -> None:
        output = tmp_path / "output.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "import-aseprite", FIXTURE_SIMPLE, "-o", str(output)],
        )
        assert result.exit_code == 0, result.output
        content = output.read_text()
        assert '&"idle"' in content

    def test_no_tags_produces_default_animation(self, tmp_path: Path) -> None:
        output = tmp_path / "output.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "import-aseprite", FIXTURE_NO_TAGS, "-o", str(output)],
        )
        assert result.exit_code == 0, result.output
        content = output.read_text()
        assert '&"default"' in content


class TestImportAsepriteOptions:
    """Verify command options work correctly."""

    def test_custom_output_path(self, tmp_path: Path) -> None:
        output = tmp_path / "custom" / "out.tres"
        output.parent.mkdir(parents=True)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "import-aseprite", FIXTURE_SIMPLE, "-o", str(output)],
        )
        assert result.exit_code == 0, result.output
        assert output.exists()

    def test_custom_res_path(self, tmp_path: Path) -> None:
        output = tmp_path / "output.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "sprite", "import-aseprite", FIXTURE_SIMPLE,
                "-o", str(output),
                "--res-path", "res://art/character.png",
            ],
        )
        assert result.exit_code == 0, result.output
        content = output.read_text()
        assert "res://art/character.png" in content

    def test_default_res_path_uses_meta_image(self, tmp_path: Path) -> None:
        """Default res path should be res:// + meta.image from the JSON."""
        output = tmp_path / "output.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "import-aseprite", FIXTURE_SIMPLE, "-o", str(output)],
        )
        assert result.exit_code == 0, result.output
        content = output.read_text()
        # aseprite_simple.json has meta.image = "simple_sheet.png"
        assert "res://simple_sheet.png" in content


class TestImportAsepriteJson:
    """Verify --json output mode."""

    def test_json_output_valid(self, tmp_path: Path) -> None:
        output = tmp_path / "output.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "-j", "sprite", "import-aseprite", FIXTURE_SIMPLE,
                "-o", str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_json_output_has_required_keys(self, tmp_path: Path) -> None:
        output = tmp_path / "output.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "-j", "sprite", "import-aseprite", FIXTURE_SIMPLE,
                "-o", str(output),
            ],
        )
        data = json.loads(result.output)
        assert "output_path" in data
        assert "animation_count" in data
        assert "frame_count" in data

    def test_json_output_correct_counts(self, tmp_path: Path) -> None:
        output = tmp_path / "output.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "-j", "sprite", "import-aseprite", FIXTURE_SIMPLE,
                "-o", str(output),
            ],
        )
        data = json.loads(result.output)
        # aseprite_simple.json has 1 tag ("idle") with 4 frames
        assert data["animation_count"] == 1
        assert data["frame_count"] == 4


class TestImportAsepriteErrors:
    """Verify error handling."""

    def test_nonexistent_file_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "import-aseprite", "nonexistent_file.json"],
        )
        assert result.exit_code != 0

    def test_nonexistent_file_json_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["-j", "sprite", "import-aseprite", "nonexistent_file.json"],
        )
        assert result.exit_code != 0


class TestImportAsepriteHelp:
    """Verify help text contains import guide."""

    def test_help_contains_export_settings(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "import-aseprite", "--help"],
        )
        assert result.exit_code == 0
        assert "ASEPRITE EXPORT SETTINGS" in result.output

    def test_help_contains_json_array_recommendation(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "import-aseprite", "--help"],
        )
        assert result.exit_code == 0
        assert "--format json-array" in result.output

    def test_help_contains_common_pitfalls(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "import-aseprite", "--help"],
        )
        assert result.exit_code == 0
        assert "COMMON PITFALLS" in result.output


class TestImportAsepritePartialFailure:
    """Verify partial tag failure handling (D-17)."""

    def test_partial_failure_still_outputs_tres(self, tmp_path: Path) -> None:
        """Create a fixture with one valid tag and one bad tag, verify partial success."""
        fixture = tmp_path / "partial.json"
        fixture.write_text(json.dumps({
            "frames": [
                {
                    "filename": "frame 0",
                    "frame": {"x": 0, "y": 0, "w": 32, "h": 32},
                    "rotated": False,
                    "trimmed": False,
                    "spriteSourceSize": {"x": 0, "y": 0, "w": 32, "h": 32},
                    "sourceSize": {"w": 32, "h": 32},
                    "duration": 100,
                },
                {
                    "filename": "frame 1",
                    "frame": {"x": 32, "y": 0, "w": 32, "h": 32},
                    "rotated": False,
                    "trimmed": False,
                    "spriteSourceSize": {"x": 0, "y": 0, "w": 32, "h": 32},
                    "sourceSize": {"w": 32, "h": 32},
                    "duration": 100,
                },
            ],
            "meta": {
                "app": "http://www.aseprite.org/",
                "version": "1.3.7",
                "image": "partial_sheet.png",
                "format": "RGBA8888",
                "size": {"w": 64, "h": 32},
                "scale": "1",
                "frameTags": [
                    {
                        "name": "walk",
                        "from": 0,
                        "to": 1,
                        "direction": "forward",
                    },
                    {
                        "name": "bad_anim",
                        "from": 0,
                        "to": 1,
                        "direction": "INVALID_DIRECTION",
                    },
                ],
                "slices": [],
            },
        }))
        output = tmp_path / "partial.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "import-aseprite", str(fixture), "-o", str(output)],
        )
        assert result.exit_code == 0, result.output
        assert output.exists()
        content = output.read_text()
        assert '&"walk"' in content
        # bad_anim should be skipped (parser filters invalid direction tags)
        assert "bad_anim" not in content

    def test_all_tags_fail_exits_nonzero(self, tmp_path: Path) -> None:
        """When every tag fails, command should exit non-zero."""
        fixture = tmp_path / "all_bad.json"
        fixture.write_text(json.dumps({
            "frames": [
                {
                    "filename": "frame 0",
                    "frame": {"x": 0, "y": 0, "w": 32, "h": 32},
                    "rotated": False,
                    "trimmed": False,
                    "spriteSourceSize": {"x": 0, "y": 0, "w": 32, "h": 32},
                    "sourceSize": {"w": 32, "h": 32},
                    "duration": 100,
                },
            ],
            "meta": {
                "app": "http://www.aseprite.org/",
                "version": "1.3.7",
                "image": "all_bad_sheet.png",
                "format": "RGBA8888",
                "size": {"w": 32, "h": 32},
                "scale": "1",
                "frameTags": [
                    {
                        "name": "bad1",
                        "from": 0,
                        "to": 0,
                        "direction": "BOGUS",
                    },
                    {
                        "name": "bad2",
                        "from": 0,
                        "to": 0,
                        "direction": "ALSO_BOGUS",
                    },
                ],
                "slices": [],
            },
        }))
        output = tmp_path / "all_bad.tres"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "import-aseprite", str(fixture), "-o", str(output)],
        )
        assert result.exit_code != 0
