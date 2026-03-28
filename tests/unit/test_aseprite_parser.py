"""Unit tests for Aseprite JSON parser."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from gdauto.errors import ValidationError
from gdauto.formats.aseprite import (
    AniDirection,
    AsepriteData,
    AsepriteFrame,
    AsepriteMeta,
    AsepriteTag,
    FrameRect,
    parse_aseprite_json,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


class TestParseArrayFormat:
    """Tests for json-array format parsing."""

    def test_simple_array_returns_correct_frame_count(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_simple.json")
        assert len(data.frames) == 4

    def test_simple_array_frame_dimensions(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_simple.json")
        assert data.frames[0].frame == FrameRect(x=0, y=0, w=32, h=32)
        assert data.frames[1].frame == FrameRect(x=32, y=0, w=32, h=32)
        assert data.frames[2].frame == FrameRect(x=64, y=0, w=32, h=32)
        assert data.frames[3].frame == FrameRect(x=96, y=0, w=32, h=32)

    def test_simple_array_durations(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_simple.json")
        for frame in data.frames:
            assert frame.duration == 100

    def test_simple_array_meta(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_simple.json")
        assert data.meta.image == "simple_sheet.png"
        assert data.meta.size == (128, 32)

    def test_simple_array_one_tag(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_simple.json")
        assert len(data.meta.frame_tags) == 1
        tag = data.meta.frame_tags[0]
        assert tag.name == "idle"
        assert tag.from_frame == 0
        assert tag.to_frame == 3
        assert tag.direction == AniDirection.FORWARD

    def test_simple_array_filenames(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_simple.json")
        assert data.frames[0].filename == "sprite 0.ase"
        assert data.frames[3].filename == "sprite 3.ase"


class TestParseHashFormat:
    """Tests for json-hash format auto-detection and parsing."""

    def test_hash_auto_detected(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_hash.json")
        assert len(data.frames) == 4

    def test_hash_frames_sorted_by_position(self) -> None:
        """Hash format frames should be sorted by (x, y) position."""
        data = parse_aseprite_json(FIXTURES / "aseprite_hash.json")
        xs = [f.frame.x for f in data.frames]
        assert xs == [0, 32, 64, 96]

    def test_hash_same_data_as_array(self) -> None:
        """Hash format produces the same frame data as array format."""
        array_data = parse_aseprite_json(FIXTURES / "aseprite_simple.json")
        hash_data = parse_aseprite_json(FIXTURES / "aseprite_hash.json")
        assert len(array_data.frames) == len(hash_data.frames)
        for af, hf in zip(array_data.frames, hash_data.frames):
            assert af.frame == hf.frame
            assert af.duration == hf.duration
            assert af.trimmed == hf.trimmed

    def test_hash_filenames_from_keys(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_hash.json")
        # Hash format uses dict keys as filenames
        filenames = [f.filename for f in data.frames]
        assert "sprite 0.ase" in filenames


class TestParseTrimmed:
    """Tests for trimmed sprite parsing."""

    def test_trimmed_flag(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_trimmed.json")
        for frame in data.frames:
            assert frame.trimmed is True

    def test_trimmed_sprite_source_size(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_trimmed.json")
        f0 = data.frames[0]
        assert f0.sprite_source_size == FrameRect(x=2, y=1, w=28, h=30)
        assert f0.source_size == (32, 32)

    def test_trimmed_second_frame(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_trimmed.json")
        f1 = data.frames[1]
        assert f1.sprite_source_size == FrameRect(x=1, y=0, w=30, h=31)
        assert f1.frame == FrameRect(x=28, y=0, w=30, h=31)


class TestParseDirections:
    """Tests for animation direction parsing."""

    def test_pingpong_direction(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_pingpong.json")
        assert data.meta.frame_tags[0].direction == AniDirection.PING_PONG

    def test_pingpong_reverse_direction(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_pingpong.json")
        assert data.meta.frame_tags[1].direction == AniDirection.PING_PONG_REVERSE

    def test_forward_direction(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_simple.json")
        assert data.meta.frame_tags[0].direction == AniDirection.FORWARD

    def test_all_direction_enum_values(self) -> None:
        assert AniDirection.FORWARD.value == "forward"
        assert AniDirection.REVERSE.value == "reverse"
        assert AniDirection.PING_PONG.value == "pingpong"
        assert AniDirection.PING_PONG_REVERSE.value == "pingpong_reverse"


class TestParseVariableDuration:
    """Tests for variable duration parsing."""

    def test_variable_durations(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_variable_duration.json")
        durations = [f.duration for f in data.frames]
        assert durations == [100, 200, 100]


class TestParseRepeatField:
    """Tests for the repeat field (string-to-int conversion)."""

    def test_string_repeat_converted_to_int(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_variable_duration.json")
        tag = data.meta.frame_tags[0]
        assert tag.repeat == 3
        assert isinstance(tag.repeat, int)

    def test_absent_repeat_defaults_to_zero(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_simple.json")
        tag = data.meta.frame_tags[0]
        assert tag.repeat == 0


class TestParseNoTags:
    """Tests for files with no frameTags."""

    def test_no_tags_returns_empty_list(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_no_tags.json")
        assert data.meta.frame_tags == []

    def test_no_tags_frames_still_parsed(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_no_tags.json")
        assert len(data.frames) == 3


class TestParseErrors:
    """Tests for error handling."""

    def test_invalid_json_raises_validation_error(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json at all {{{")
        with pytest.raises(ValidationError) as exc_info:
            parse_aseprite_json(bad_file)
        assert exc_info.value.code == "ASEPRITE_PARSE_ERROR"

    def test_missing_frames_key_raises_validation_error(
        self, tmp_path: Path
    ) -> None:
        bad_file = tmp_path / "no_frames.json"
        bad_file.write_text('{"meta": {}}')
        with pytest.raises(ValidationError) as exc_info:
            parse_aseprite_json(bad_file)
        assert exc_info.value.code == "ASEPRITE_INVALID_FORMAT"


class TestParseWarnings:
    """Tests for warnings on edge cases."""

    def test_zero_size_frame_warns(self, tmp_path: Path) -> None:
        """A frame with w=0 or h=0 should emit a warning."""
        import json

        bad_data = {
            "frames": [
                {
                    "filename": "zero.ase",
                    "frame": {"x": 0, "y": 0, "w": 0, "h": 32},
                    "rotated": False,
                    "trimmed": False,
                    "spriteSourceSize": {"x": 0, "y": 0, "w": 0, "h": 32},
                    "sourceSize": {"w": 32, "h": 32},
                    "duration": 100,
                }
            ],
            "meta": {
                "app": "http://www.aseprite.org/",
                "version": "1.3.7",
                "image": "zero.png",
                "format": "RGBA8888",
                "size": {"w": 32, "h": 32},
                "scale": "1",
                "slices": [],
            },
        }
        fixture = tmp_path / "zero_frame.json"
        fixture.write_text(json.dumps(bad_data))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            parse_aseprite_json(fixture)
            assert len(w) >= 1
            assert "zero" in str(w[0].message).lower()


class TestDataclasses:
    """Tests for dataclass construction and immutability."""

    def test_frame_rect_frozen(self) -> None:
        r = FrameRect(x=0, y=0, w=32, h=32)
        with pytest.raises(AttributeError):
            r.x = 10  # type: ignore[misc]

    def test_aseprite_frame_construction(self) -> None:
        frame = AsepriteFrame(
            filename="test.ase",
            frame=FrameRect(x=0, y=0, w=32, h=32),
            trimmed=False,
            sprite_source_size=FrameRect(x=0, y=0, w=32, h=32),
            source_size=(32, 32),
            duration=100,
        )
        assert frame.duration == 100

    def test_aseprite_tag_defaults(self) -> None:
        tag = AsepriteTag(
            name="test",
            from_frame=0,
            to_frame=3,
            direction=AniDirection.FORWARD,
        )
        assert tag.repeat == 0
        assert tag.color is None
        assert tag.data is None
