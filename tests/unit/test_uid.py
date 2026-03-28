"""Tests for UID generation, encoding/decoding, resource ID generation, and common parsing."""

import re

import pytest

from gdauto.formats.common import (
    HeaderAttributes,
    Section,
    _count_bracket_depth,
    parse_section_header,
    parse_sections,
    serialize_sections,
)
from gdauto.formats.uid import (
    CHARS,
    generate_resource_id,
    generate_uid,
    read_uid_file,
    text_to_uid,
    uid_to_text,
    write_uid_file,
)


# ---------------------------------------------------------------------------
# UID generation
# ---------------------------------------------------------------------------


class TestGenerateUid:
    """Tests for generate_uid()."""

    def test_returns_int(self) -> None:
        result = generate_uid()
        assert isinstance(result, int)

    def test_in_range(self) -> None:
        for _ in range(100):
            uid = generate_uid()
            assert 0 <= uid <= (1 << 63) - 1

    def test_not_always_same(self) -> None:
        uids = {generate_uid() for _ in range(10)}
        assert len(uids) > 1


# ---------------------------------------------------------------------------
# uid_to_text
# ---------------------------------------------------------------------------


class TestUidToText:
    """Tests for uid_to_text()."""

    def test_starts_with_prefix(self) -> None:
        uid = generate_uid()
        text = uid_to_text(uid)
        assert text.startswith("uid://")

    def test_zero(self) -> None:
        assert uid_to_text(0) == "uid://a"

    def test_no_z_or_9_in_output(self) -> None:
        for _ in range(500):
            uid = generate_uid()
            text = uid_to_text(uid)
            encoded_part = text[6:]  # strip "uid://"
            assert "z" not in encoded_part, f"'z' found in {text}"
            assert "9" not in encoded_part, f"'9' found in {text}"

    def test_only_valid_chars(self) -> None:
        valid_chars = set(CHARS)
        for _ in range(100):
            uid = generate_uid()
            text = uid_to_text(uid)
            encoded_part = text[6:]
            for ch in encoded_part:
                assert ch in valid_chars, f"Invalid char '{ch}' in {text}"

    def test_known_value(self) -> None:
        # Verify a known UID encodes correctly by round-tripping
        uid = text_to_uid("uid://cecaux1sm7mo0")
        assert uid >= 0
        assert uid_to_text(uid) == "uid://cecaux1sm7mo0"

    def test_negative_uid(self) -> None:
        result = uid_to_text(-1)
        assert result == "uid://<invalid>"


# ---------------------------------------------------------------------------
# text_to_uid
# ---------------------------------------------------------------------------


class TestTextToUid:
    """Tests for text_to_uid()."""

    def test_round_trip_various_values(self) -> None:
        test_values = [0, 1, 33, 34, 100, 1000, 999999, (1 << 63) - 1]
        for val in test_values:
            text = uid_to_text(val)
            result = text_to_uid(text)
            assert result == val, f"Round-trip failed for {val}: {text} -> {result}"

    def test_known_uid_string(self) -> None:
        # cecaux1sm7mo0 is a known valid UID from the research
        result = text_to_uid("uid://cecaux1sm7mo0")
        assert result >= 0
        assert isinstance(result, int)

    def test_invalid_prefix(self) -> None:
        assert text_to_uid("invalid") == -1

    def test_invalid_no_uid_prefix(self) -> None:
        assert text_to_uid("xxx://abc") == -1

    def test_invalid_char_z(self) -> None:
        assert text_to_uid("uid://abcz") == -1

    def test_invalid_char_9(self) -> None:
        assert text_to_uid("uid://abc9") == -1

    def test_empty_after_prefix(self) -> None:
        # "uid://" with no encoded part: edge case
        result = text_to_uid("uid://")
        # Empty string after prefix means uid=0 (no loop iterations)
        assert result == 0

    def test_random_round_trip(self) -> None:
        for _ in range(100):
            uid = generate_uid()
            text = uid_to_text(uid)
            decoded = text_to_uid(text)
            assert decoded == uid


# ---------------------------------------------------------------------------
# generate_resource_id
# ---------------------------------------------------------------------------


class TestGenerateResourceId:
    """Tests for generate_resource_id()."""

    def test_atlas_texture_format(self) -> None:
        rid = generate_resource_id("AtlasTexture")
        assert re.match(r"^AtlasTexture_[a-zA-Z0-9_]{5}$", rid)

    def test_sphere_mesh_format(self) -> None:
        rid = generate_resource_id("SphereMesh")
        assert re.match(r"^SphereMesh_[a-zA-Z0-9_]{5}$", rid)

    def test_uniqueness(self) -> None:
        ids = {generate_resource_id("Test") for _ in range(100)}
        assert len(ids) == 100

    def test_prefix_preserved(self) -> None:
        rid = generate_resource_id("MyCustomType")
        assert rid.startswith("MyCustomType_")
        assert len(rid) == len("MyCustomType_") + 5


# ---------------------------------------------------------------------------
# UID file I/O
# ---------------------------------------------------------------------------


class TestUidFileIo:
    """Tests for write_uid_file() and read_uid_file()."""

    def test_write_and_read(self, tmp_path: object) -> None:
        from pathlib import Path

        tmp = Path(str(tmp_path))
        resource_path = tmp / "sprite.tres"
        resource_path.write_text("[gd_resource]")
        uid_text = "uid://cecaux1sm7mo0"
        write_uid_file(resource_path, uid_text)
        result = read_uid_file(resource_path)
        assert result == uid_text

    def test_read_missing_file(self, tmp_path: object) -> None:
        from pathlib import Path

        tmp = Path(str(tmp_path))
        resource_path = tmp / "nonexistent.tres"
        result = read_uid_file(resource_path)
        assert result is None


# ---------------------------------------------------------------------------
# parse_section_header
# ---------------------------------------------------------------------------


class TestParseSectionHeader:
    """Tests for parse_section_header()."""

    def test_gd_resource_header(self) -> None:
        result = parse_section_header('[gd_resource type="SpriteFrames" format=3]')
        assert result is not None
        assert result.tag == "gd_resource"
        assert result.attrs["type"] == "SpriteFrames"
        assert result.attrs["format"] == "3"

    def test_ext_resource_header(self) -> None:
        result = parse_section_header(
            '[ext_resource type="Texture2D" uid="uid://abc" '
            'path="res://img.png" id="1_img"]'
        )
        assert result is not None
        assert result.tag == "ext_resource"
        assert result.attrs["type"] == "Texture2D"
        assert result.attrs["uid"] == "uid://abc"
        assert result.attrs["path"] == "res://img.png"
        assert result.attrs["id"] == "1_img"

    def test_node_header(self) -> None:
        result = parse_section_header(
            '[node name="Player" type="CharacterBody2D" parent="."]'
        )
        assert result is not None
        assert result.tag == "node"
        assert result.attrs["name"] == "Player"
        assert result.attrs["type"] == "CharacterBody2D"
        assert result.attrs["parent"] == "."

    def test_sub_resource_header(self) -> None:
        result = parse_section_header(
            '[sub_resource type="AtlasTexture" id="AtlasTexture_abc12"]'
        )
        assert result is not None
        assert result.tag == "sub_resource"
        assert result.attrs["type"] == "AtlasTexture"
        assert result.attrs["id"] == "AtlasTexture_abc12"

    def test_bare_resource_header(self) -> None:
        result = parse_section_header("[resource]")
        assert result is not None
        assert result.tag == "resource"
        assert result.attrs == {}

    def test_not_a_header(self) -> None:
        assert parse_section_header("key = value") is None
        assert parse_section_header("") is None
        assert parse_section_header("just text") is None


# ---------------------------------------------------------------------------
# Bracket depth tracking
# ---------------------------------------------------------------------------


class TestBracketDepth:
    """Tests for bracket depth tracking."""

    def test_balanced_brackets(self) -> None:
        assert _count_bracket_depth("[{}]") == 0

    def test_opening_brackets(self) -> None:
        assert _count_bracket_depth("[{") == 2

    def test_closing_brackets(self) -> None:
        assert _count_bracket_depth("}]") == -2

    def test_nested(self) -> None:
        assert _count_bracket_depth("[{()}]") == 0

    def test_ignores_brackets_in_strings(self) -> None:
        assert _count_bracket_depth('"[{("') == 0

    def test_handles_escaped_quotes(self) -> None:
        # String with escaped quote: "[\"" -- the bracket is inside the string
        assert _count_bracket_depth('"[\\"" [') == 1


# ---------------------------------------------------------------------------
# Multi-line value accumulation
# ---------------------------------------------------------------------------


class TestMultiLineValues:
    """Tests for multi-line value parsing via parse_sections."""

    def test_multiline_array_value(self) -> None:
        text = (
            '[gd_resource type="Test" format=3]\n'
            "\n"
            "[resource]\n"
            "data = [{\n"
            '"key": "value"\n'
            "}, {\n"
            '"key2": "value2"\n'
            "}]\n"
        )
        header, sections = parse_sections(text)
        assert header.tag == "gd_resource"
        # Find the resource section
        resource_sections = [s for s in sections if s.header.tag == "resource"]
        assert len(resource_sections) == 1
        resource = resource_sections[0]
        # Should have one property named "data"
        real_props = [(k, v) for k, v in resource.raw_properties if k != ""]
        assert len(real_props) == 1
        assert real_props[0][0] == "data"


# ---------------------------------------------------------------------------
# Comment and blank line preservation
# ---------------------------------------------------------------------------


class TestCommentAndBlankPreservation:
    """Tests that comments and blank lines are preserved."""

    def test_comments_preserved(self) -> None:
        text = (
            '[gd_resource type="Test" format=3]\n'
            "\n"
            "[resource]\n"
            "; this is a comment\n"
            "key = 42\n"
        )
        header, sections = parse_sections(text)
        resource = sections[0]
        # Comment should be preserved in raw_properties
        has_comment = any(
            v.startswith(";") for k, v in resource.raw_properties if k == ""
        )
        assert has_comment

    def test_blank_lines_between_sections(self) -> None:
        text = (
            '[gd_resource type="Test" format=3]\n'
            "\n"
            '[ext_resource type="Texture2D" path="res://a.png" id="1_a"]\n'
            "\n"
            "[resource]\n"
            "key = 1\n"
        )
        header, sections = parse_sections(text)
        assert len(sections) == 2
        # Second section should have a blank line in leading_whitespace
        assert "" in sections[1].leading_whitespace
