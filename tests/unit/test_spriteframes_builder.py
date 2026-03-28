"""Unit tests for SpriteFrames GdResource builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from gdauto.formats.aseprite import (
    AniDirection,
    AsepriteData,
    AsepriteFrame,
    AsepriteMeta,
    AsepriteTag,
    FrameRect,
    parse_aseprite_json,
)
from gdauto.formats.tres import GdResource, parse_tres, serialize_tres
from gdauto.formats.values import Rect2, StringName, SubResourceRef
from gdauto.sprite.spriteframes import (
    build_animation_for_tag,
    build_spriteframes,
    compute_animation_timing,
    compute_margin,
    expand_pingpong,
    expand_pingpong_reverse,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers to build test data
# ---------------------------------------------------------------------------

def _make_frame(
    x: int, y: int, w: int = 32, h: int = 32, duration: int = 100
) -> AsepriteFrame:
    """Create a simple untrimmed AsepriteFrame."""
    return AsepriteFrame(
        filename=f"frame_{x}.ase",
        frame=FrameRect(x=x, y=y, w=w, h=h),
        trimmed=False,
        sprite_source_size=FrameRect(x=0, y=0, w=w, h=h),
        source_size=(w, h),
        duration=duration,
    )


def _make_simple_data(
    num_frames: int = 4,
    tag_name: str = "idle",
    direction: AniDirection = AniDirection.FORWARD,
    repeat: int = 0,
    duration: int = 100,
) -> AsepriteData:
    """Create a simple AsepriteData with one tag."""
    frames = [
        _make_frame(x=i * 32, y=0, duration=duration)
        for i in range(num_frames)
    ]
    tag = AsepriteTag(
        name=tag_name,
        from_frame=0,
        to_frame=num_frames - 1,
        direction=direction,
        repeat=repeat,
    )
    meta = AsepriteMeta(
        app="test",
        version="1.0",
        image="test.png",
        format="RGBA8888",
        size=(num_frames * 32, 32),
        scale="1",
        frame_tags=[tag],
    )
    return AsepriteData(frames=frames, meta=meta)


# ---------------------------------------------------------------------------
# compute_animation_timing
# ---------------------------------------------------------------------------

class TestComputeAnimationTiming:
    """Tests for GCD-based animation timing computation."""

    def test_uniform_durations(self) -> None:
        fps, mults = compute_animation_timing([100, 100, 100])
        assert fps == 10.0
        assert mults == [1.0, 1.0, 1.0]

    def test_variable_durations(self) -> None:
        fps, mults = compute_animation_timing([100, 200, 100])
        assert fps == 10.0
        assert mults == [1.0, 2.0, 1.0]

    def test_uniform_200ms(self) -> None:
        fps, mults = compute_animation_timing([200, 200])
        assert fps == 5.0
        assert mults == [1.0, 1.0]

    def test_empty_list(self) -> None:
        fps, mults = compute_animation_timing([])
        assert fps == 1.0
        assert mults == []

    def test_single_frame(self) -> None:
        fps, mults = compute_animation_timing([150])
        assert fps == pytest.approx(1000.0 / 150.0)
        assert mults == [1.0]


# ---------------------------------------------------------------------------
# expand_pingpong
# ---------------------------------------------------------------------------

class TestExpandPingpong:
    """Tests for pingpong frame expansion."""

    def test_four_frames(self) -> None:
        assert expand_pingpong([0, 1, 2, 3]) == [0, 1, 2, 3, 2, 1]

    def test_two_frames_no_expansion(self) -> None:
        assert expand_pingpong([0, 1]) == [0, 1]

    def test_one_frame_no_expansion(self) -> None:
        assert expand_pingpong([0]) == [0]

    def test_empty_list(self) -> None:
        assert expand_pingpong([]) == []

    def test_three_frames(self) -> None:
        assert expand_pingpong([0, 1, 2]) == [0, 1, 2, 1]


# ---------------------------------------------------------------------------
# expand_pingpong_reverse
# ---------------------------------------------------------------------------

class TestExpandPingpongReverse:
    """Tests for pingpong_reverse frame expansion."""

    def test_four_frames(self) -> None:
        assert expand_pingpong_reverse([0, 1, 2, 3]) == [3, 2, 1, 0, 1, 2]

    def test_two_frames(self) -> None:
        assert expand_pingpong_reverse([0, 1]) == [1, 0]


# ---------------------------------------------------------------------------
# compute_margin
# ---------------------------------------------------------------------------

class TestComputeMargin:
    """Tests for trimmed sprite margin computation."""

    def test_trimmed_margin(self) -> None:
        sss = FrameRect(x=2, y=1, w=28, h=30)
        source = (32, 32)
        frame = FrameRect(x=0, y=0, w=28, h=30)
        margin = compute_margin(sss, source, frame)
        assert margin is not None
        assert margin == Rect2(2.0, 1.0, 4.0, 2.0)

    def test_no_trim_returns_none(self) -> None:
        sss = FrameRect(x=0, y=0, w=32, h=32)
        source = (32, 32)
        frame = FrameRect(x=0, y=0, w=32, h=32)
        margin = compute_margin(sss, source, frame)
        assert margin is None


# ---------------------------------------------------------------------------
# build_animation_for_tag
# ---------------------------------------------------------------------------

class TestBuildAnimationForTag:
    """Tests for per-tag animation building."""

    def test_returns_tuple(self) -> None:
        data = _make_simple_data()
        from gdauto.formats.tres import ExtResource
        from gdauto.formats.uid import generate_resource_id, generate_uid, uid_to_text

        ext = ExtResource(
            type="Texture2D",
            path="res://test.png",
            id=generate_resource_id("Texture2D"),
            uid=uid_to_text(generate_uid()),
        )
        tag = data.meta.frame_tags[0]
        sub_resources, anim_dict = build_animation_for_tag(
            tag, data.frames, ext
        )
        assert isinstance(sub_resources, list)
        assert isinstance(anim_dict, dict)
        assert len(sub_resources) == 4

    def test_animation_dict_keys(self) -> None:
        data = _make_simple_data()
        from gdauto.formats.tres import ExtResource
        from gdauto.formats.uid import generate_resource_id, generate_uid, uid_to_text

        ext = ExtResource(
            type="Texture2D",
            path="res://test.png",
            id=generate_resource_id("Texture2D"),
            uid=uid_to_text(generate_uid()),
        )
        tag = data.meta.frame_tags[0]
        _, anim_dict = build_animation_for_tag(tag, data.frames, ext)
        keys = list(anim_dict.keys())
        assert keys == ["frames", "loop", "name", "speed"]

    def test_animation_name_is_stringname(self) -> None:
        data = _make_simple_data()
        from gdauto.formats.tres import ExtResource
        from gdauto.formats.uid import generate_resource_id, generate_uid, uid_to_text

        ext = ExtResource(
            type="Texture2D",
            path="res://test.png",
            id=generate_resource_id("Texture2D"),
            uid=uid_to_text(generate_uid()),
        )
        tag = data.meta.frame_tags[0]
        _, anim_dict = build_animation_for_tag(tag, data.frames, ext)
        assert isinstance(anim_dict["name"], StringName)
        assert anim_dict["name"].value == "idle"


# ---------------------------------------------------------------------------
# build_spriteframes
# ---------------------------------------------------------------------------

class TestBuildSpriteframes:
    """Tests for the full SpriteFrames builder pipeline."""

    def test_resource_type(self) -> None:
        data = _make_simple_data()
        resource = build_spriteframes(data, "res://sprites/test.png")
        assert resource.type == "SpriteFrames"

    def test_ext_resources(self) -> None:
        data = _make_simple_data()
        resource = build_spriteframes(data, "res://sprites/test.png")
        assert len(resource.ext_resources) == 1
        assert resource.ext_resources[0].type == "Texture2D"
        assert resource.ext_resources[0].path == "res://sprites/test.png"

    def test_sub_resources_count_forward(self) -> None:
        data = _make_simple_data(num_frames=4)
        resource = build_spriteframes(data, "res://sprites/test.png")
        assert len(resource.sub_resources) == 4

    def test_sub_resources_type_atlas_texture(self) -> None:
        data = _make_simple_data()
        resource = build_spriteframes(data, "res://sprites/test.png")
        for sub in resource.sub_resources:
            assert sub.type == "AtlasTexture"

    def test_load_steps(self) -> None:
        data = _make_simple_data(num_frames=4)
        resource = build_spriteframes(data, "res://sprites/test.png")
        expected = len(resource.ext_resources) + len(resource.sub_resources) + 1
        assert resource.load_steps == expected

    def test_loop_true_when_repeat_zero(self) -> None:
        data = _make_simple_data(repeat=0)
        resource = build_spriteframes(data, "res://sprites/test.png")
        anims = resource.resource_properties["animations"]
        assert anims[0]["loop"] is True

    def test_loop_false_when_repeat_positive(self) -> None:
        data = _make_simple_data(repeat=3)
        resource = build_spriteframes(data, "res://sprites/test.png")
        anims = resource.resource_properties["animations"]
        assert anims[0]["loop"] is False

    def test_no_tags_creates_default_animation(self) -> None:
        frames = [_make_frame(x=i * 32, y=0) for i in range(3)]
        meta = AsepriteMeta(
            app="test",
            version="1.0",
            image="test.png",
            format="RGBA8888",
            size=(96, 32),
            scale="1",
            frame_tags=[],
        )
        data = AsepriteData(frames=frames, meta=meta)
        resource = build_spriteframes(data, "res://sprites/test.png")
        anims = resource.resource_properties["animations"]
        assert len(anims) == 1
        assert anims[0]["name"] == StringName("default")

    def test_pingpong_creates_six_sub_resources(self) -> None:
        data = _make_simple_data(
            num_frames=4, direction=AniDirection.PING_PONG
        )
        resource = build_spriteframes(data, "res://sprites/test.png")
        # pingpong on 4 frames: [0,1,2,3,2,1] = 6
        assert len(resource.sub_resources) == 6

    def test_reverse_direction(self) -> None:
        data = _make_simple_data(
            num_frames=4, direction=AniDirection.REVERSE
        )
        resource = build_spriteframes(data, "res://sprites/test.png")
        # Reverse still uses 4 frames, just in reversed order
        assert len(resource.sub_resources) == 4
        # Verify regions are in reverse order
        regions = [
            sub.properties["region"] for sub in resource.sub_resources
        ]
        xs = [r.x for r in regions]
        assert xs == [96.0, 64.0, 32.0, 0.0]

    def test_trimmed_frames_have_margin(self) -> None:
        data = parse_aseprite_json(FIXTURES / "aseprite_trimmed.json")
        resource = build_spriteframes(data, "res://sprites/trimmed.png")
        # Both frames are trimmed, so all sub_resources should have margin
        for sub in resource.sub_resources:
            assert "margin" in sub.properties

    def test_format_is_3(self) -> None:
        data = _make_simple_data()
        resource = build_spriteframes(data, "res://sprites/test.png")
        assert resource.format == 3

    def test_uid_is_set(self) -> None:
        data = _make_simple_data()
        resource = build_spriteframes(data, "res://sprites/test.png")
        assert resource.uid is not None
        assert resource.uid.startswith("uid://")


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------

class TestSerializationRoundTrip:
    """Test that built GdResources serialize to valid .tres text."""

    def test_serialize_contains_spriteframes_header(self) -> None:
        data = _make_simple_data()
        resource = build_spriteframes(data, "res://sprites/test.png")
        text = serialize_tres(resource)
        assert '[gd_resource type="SpriteFrames"' in text

    def test_serialize_contains_atlas_texture(self) -> None:
        data = _make_simple_data()
        resource = build_spriteframes(data, "res://sprites/test.png")
        text = serialize_tres(resource)
        assert "AtlasTexture" in text

    def test_serialize_contains_stringname_animation(self) -> None:
        data = _make_simple_data()
        resource = build_spriteframes(data, "res://sprites/test.png")
        text = serialize_tres(resource)
        assert '&"idle"' in text

    def test_round_trip_parse(self) -> None:
        """Serialize a built resource and parse it back."""
        data = _make_simple_data()
        resource = build_spriteframes(data, "res://sprites/test.png")
        text = serialize_tres(resource)
        reparsed = parse_tres(text)
        assert reparsed.type == "SpriteFrames"
        assert len(reparsed.ext_resources) == 1
        assert len(reparsed.sub_resources) == 4

    def test_fixture_integration(self) -> None:
        """Parse a real fixture and build/serialize a GdResource."""
        ase_data = parse_aseprite_json(FIXTURES / "aseprite_simple.json")
        resource = build_spriteframes(
            ase_data, "res://sprites/simple_sheet.png"
        )
        text = serialize_tres(resource)
        assert '[gd_resource type="SpriteFrames"' in text
        assert '&"idle"' in text
        assert "AtlasTexture" in text
