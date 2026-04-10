"""Tests for SpriteFrames validation (structural and headless)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from auto_godot.cli import cli

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
SAMPLE_TRES = FIXTURES_DIR / "sample.tres"


class TestValidateSpriteframesStructural:
    """Structural validation without Godot binary."""

    def test_valid_spriteframes_returns_valid(self) -> None:
        from auto_godot.sprite.validator import validate_spriteframes

        result = validate_spriteframes(SAMPLE_TRES)
        assert result["valid"] is True
        assert len(result["issues"]) == 0

    def test_valid_spriteframes_has_animation_info(self) -> None:
        from auto_godot.sprite.validator import validate_spriteframes

        result = validate_spriteframes(SAMPLE_TRES)
        anims = result["animations"]
        assert len(anims) == 1
        assert anims[0]["name"] == "idle"
        assert anims[0]["frames"] == 2

    def test_wrong_resource_type_returns_invalid(self, tmp_path: Path) -> None:
        from auto_godot.sprite.validator import validate_spriteframes

        tres = tmp_path / "theme.tres"
        tres.write_text(
            '[gd_resource type="Theme" format=3]\n\n[resource]\n'
        )
        result = validate_spriteframes(tres)
        assert result["valid"] is False
        assert any("Theme" in issue and "SpriteFrames" in issue for issue in result["issues"])

    def test_missing_animations_property(self, tmp_path: Path) -> None:
        from auto_godot.sprite.validator import validate_spriteframes

        tres = tmp_path / "empty_sf.tres"
        tres.write_text(
            '[gd_resource type="SpriteFrames" format=3]\n\n[resource]\n'
        )
        result = validate_spriteframes(tres)
        assert result["valid"] is False
        assert any("animations" in issue for issue in result["issues"])

    def test_broken_subresource_reference(self, tmp_path: Path) -> None:
        from auto_godot.sprite.validator import validate_spriteframes

        # Animation references SubResource("nonexistent") which does not exist
        tres = tmp_path / "broken_ref.tres"
        tres.write_text(
            '[gd_resource type="SpriteFrames" load_steps=2 format=3]\n'
            '\n'
            '[ext_resource type="Texture2D" path="res://x.png" id="1_t"]\n'
            '\n'
            '[resource]\n'
            'animations = [{\n'
            '"frames": [{\n'
            '"duration": 1.0,\n'
            '"texture": SubResource("nonexistent")\n'
            '}],\n'
            '"loop": true,\n'
            '"name": &"walk",\n'
            '"speed": 8.0\n'
            '}]\n'
        )
        result = validate_spriteframes(tres)
        assert result["valid"] is False
        assert any("nonexistent" in issue for issue in result["issues"])

    def test_nonexistent_file_returns_invalid(self) -> None:
        from auto_godot.sprite.validator import validate_spriteframes

        result = validate_spriteframes(Path("/does/not/exist.tres"))
        assert result["valid"] is False
        assert len(result["issues"]) > 0

    def test_result_has_resource_counts(self) -> None:
        from auto_godot.sprite.validator import validate_spriteframes

        result = validate_spriteframes(SAMPLE_TRES)
        assert "ext_resource_count" in result
        assert "sub_resource_count" in result
        assert result["ext_resource_count"] == 1
        assert result["sub_resource_count"] == 2


class TestValidateSpriteframesHeadless:
    """Headless Godot validation with mocked backend."""

    def test_headless_calls_backend_run(self) -> None:
        from auto_godot.sprite.validator import validate_spriteframes_headless

        mock_backend = MagicMock()
        mock_backend.run.return_value = MagicMock(
            stdout="VALIDATION_OK: animations=1\nANIM: idle frames=2\n",
            returncode=0,
        )

        result = validate_spriteframes_headless(SAMPLE_TRES, mock_backend)
        assert mock_backend.run.called
        call_args = mock_backend.run.call_args
        # Should pass --script argument
        assert any("--script" in str(a) for a in call_args[0][0])

    def test_headless_fallback_on_godot_binary_error(self) -> None:
        from auto_godot.errors import GodotBinaryError
        from auto_godot.sprite.validator import validate_spriteframes_headless

        mock_backend = MagicMock()
        mock_backend.run.side_effect = GodotBinaryError(
            message="Godot not found",
            code="GODOT_NOT_FOUND",
        )

        result = validate_spriteframes_headless(SAMPLE_TRES, mock_backend)
        # Falls back to structural validation; sample.tres is valid
        assert result["valid"] is True
        assert any("fallback" in note.lower() or "structural" in note.lower()
                    for note in result.get("notes", []))


class TestValidateCli:
    """CLI command tests for `auto-godot sprite validate`."""

    def test_validate_valid_file_exits_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["sprite", "validate", str(SAMPLE_TRES)])
        assert result.exit_code == 0, result.output + (result.stderr or "")

    def test_validate_nonexistent_file_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["sprite", "validate", "nonexistent.tres"])
        assert result.exit_code != 0

    def test_validate_json_output(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json", "sprite", "validate", str(SAMPLE_TRES)]
        )
        assert result.exit_code == 0, result.output + (result.stderr or "")
        data = json.loads(result.output)
        assert "valid" in data
        assert "animations" in data
        assert "issues" in data

    def test_validate_godot_flag_no_binary_graceful(self) -> None:
        """--godot flag without Godot binary should fall back gracefully."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "validate", "--godot", str(SAMPLE_TRES)],
        )
        # Should still succeed with structural validation
        assert result.exit_code == 0, result.output + (result.stderr or "")

    def test_validate_help_shows_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["sprite", "validate", "--help"])
        assert result.exit_code == 0
        assert "--godot" in result.output
