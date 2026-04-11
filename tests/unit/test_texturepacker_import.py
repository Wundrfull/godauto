"""Tests for TexturePacker import command and parser."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli
from auto_godot.formats.texturepacker import (
    group_frames_by_animation,
    parse_texturepacker_json,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "texturepacker_sample.json"


class TestParseTexturePackerJson:
    def test_parses_hash_format(self) -> None:
        frames, image = parse_texturepacker_json(FIXTURE)
        assert len(frames) == 4
        assert image == "atlas.png"

    def test_frames_sorted_by_filename(self) -> None:
        frames, _ = parse_texturepacker_json(FIXTURE)
        names = [f.filename for f in frames]
        assert names == sorted(names)

    def test_frame_regions(self) -> None:
        frames, _ = parse_texturepacker_json(FIXTURE)
        first = frames[0]  # idle_0.png (sorted first)
        assert first.frame.w == 32
        assert first.frame.h == 32

    def test_fps_affects_duration(self) -> None:
        frames_10, _ = parse_texturepacker_json(FIXTURE, fps=10.0)
        frames_20, _ = parse_texturepacker_json(FIXTURE, fps=20.0)
        assert frames_10[0].duration == 100  # 1000/10
        assert frames_20[0].duration == 50   # 1000/20

    def test_array_format(self, tmp_path: Path) -> None:
        data = {
            "frames": [
                {"filename": "a.png", "frame": {"x": 0, "y": 0, "w": 16, "h": 16},
                 "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": 16, "h": 16},
                 "sourceSize": {"w": 16, "h": 16}},
            ],
            "meta": {"image": "sheet.png"},
        }
        f = tmp_path / "tp.json"
        f.write_text(json.dumps(data))
        frames, image = parse_texturepacker_json(f)
        assert len(frames) == 1
        assert image == "sheet.png"

    def test_invalid_json_error(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text("not json")
        import pytest
        from auto_godot.errors import ValidationError
        with pytest.raises(ValidationError):
            parse_texturepacker_json(f)

    def test_no_frames_key_error(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.json"
        f.write_text('{"meta": {}}')
        import pytest
        from auto_godot.errors import ValidationError
        with pytest.raises(ValidationError, match="No 'frames'"):
            parse_texturepacker_json(f)


class TestGroupFramesByAnimation:
    def test_groups_by_prefix(self) -> None:
        frames, _ = parse_texturepacker_json(FIXTURE)
        groups = group_frames_by_animation(frames)
        assert "idle" in groups
        assert "run" in groups
        assert len(groups["idle"]) == 2
        assert len(groups["run"]) == 2

    def test_single_frame_no_number(self, tmp_path: Path) -> None:
        data = {
            "frames": {"logo.png": {
                "frame": {"x": 0, "y": 0, "w": 64, "h": 64},
                "trimmed": False,
                "spriteSourceSize": {"x": 0, "y": 0, "w": 64, "h": 64},
                "sourceSize": {"w": 64, "h": 64},
            }},
            "meta": {"image": "sheet.png"},
        }
        f = tmp_path / "tp.json"
        f.write_text(json.dumps(data))
        frames, _ = parse_texturepacker_json(f)
        groups = group_frames_by_animation(frames)
        assert "logo" in groups


class TestImportTexturePackerCommand:
    def test_basic_import(self, tmp_path: Path) -> None:
        out = tmp_path / "result.tres"
        result = CliRunner().invoke(cli, [
            "sprite", "import-texturepacker", str(FIXTURE), "-o", str(out),
        ])
        assert result.exit_code == 0, result.output
        assert out.exists()
        content = out.read_text()
        assert "SpriteFrames" in content
        assert "AtlasTexture" in content

    def test_json_output(self, tmp_path: Path) -> None:
        out = tmp_path / "result.tres"
        result = CliRunner().invoke(cli, [
            "-j", "sprite", "import-texturepacker", str(FIXTURE), "-o", str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["animation_count"] == 2
        assert data["frame_count"] == 4

    def test_frame_count_matches_actual_frames(self, tmp_path: Path) -> None:
        """frame_count must reflect actual frames, not sub-resource count."""
        out = tmp_path / "result.tres"
        result = CliRunner().invoke(cli, [
            "-j", "sprite", "import-texturepacker", str(FIXTURE), "-o", str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        # Fixture has 2 idle frames + 2 run frames = 4 total
        frames, _ = parse_texturepacker_json(FIXTURE)
        groups = group_frames_by_animation(frames)
        expected = sum(len(fs) for fs in groups.values())
        assert data["frame_count"] == expected

    def test_custom_fps(self, tmp_path: Path) -> None:
        out = tmp_path / "result.tres"
        result = CliRunner().invoke(cli, [
            "-j", "sprite", "import-texturepacker", str(FIXTURE),
            "-o", str(out), "--fps", "12",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["animation_count"] == 2

    def test_default_output_path(self) -> None:
        result = CliRunner().invoke(cli, [
            "-j", "sprite", "import-texturepacker", str(FIXTURE),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["output_path"].endswith(".tres")

    def test_generated_tres_valid(self, tmp_path: Path) -> None:
        out = tmp_path / "result.tres"
        CliRunner().invoke(cli, [
            "sprite", "import-texturepacker", str(FIXTURE), "-o", str(out),
        ])
        content = out.read_text()
        assert "[gd_resource" in content
        assert "atlas = ExtResource(" in content
        assert "region = Rect2(" in content
