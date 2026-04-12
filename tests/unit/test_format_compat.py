"""Format compatibility tests for Godot 4.5/4.6.1 dual support.

Tests that the parser accepts both old (with load_steps, without unique_id)
and new (without load_steps, with unique_id, format=4) file formats.
Verifies backwards compatibility guarantees.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from auto_godot.formats.tscn import GdScene, SceneNode, parse_tscn, serialize_tscn
from auto_godot.formats.tres import GdResource, parse_tres, serialize_tres
from auto_godot.formats.values import (
    PackedColorArray,
    PackedVector3Array,
    PackedVector4Array,
    parse_value,
    serialize_value,
)


class TestUniqueIdRoundTrip:
    """COMPAT-02: unique_id preserved on round-trip."""

    def test_parse_tscn_with_unique_id(self) -> None:
        """Verify parser extracts unique_id from node headers."""
        text = (
            "[gd_scene format=3]\n"
            "\n"
            '[node name="Root" type="Node2D" unique_id=42]\n'
        )
        scene = parse_tscn(text)
        assert scene.nodes[0].unique_id == 42

    def test_parse_tscn_without_unique_id(self) -> None:
        """Verify parser sets unique_id to None when absent."""
        text = (
            "[gd_scene format=3]\n"
            "\n"
            '[node name="Root" type="Node2D"]\n'
        )
        scene = parse_tscn(text)
        assert scene.nodes[0].unique_id is None

    def test_unique_id_round_trip_raw(self) -> None:
        """Raw-line round-trip preserves unique_id exactly."""
        text = (
            "[gd_scene format=3]\n"
            "\n"
            '[node name="Root" type="Node2D" unique_id=42]\n'
            "position = Vector2(10, 20)\n"
        )
        scene = parse_tscn(text)
        output = serialize_tscn(scene)
        assert "unique_id=42" in output

    def test_unique_id_model_serialization(self) -> None:
        """Model-based serialization emits unique_id when present."""
        scene = GdScene(
            format=3, uid=None, load_steps=None,
            ext_resources=[], sub_resources=[],
            nodes=[SceneNode(name="Root", type="Node2D", parent=None, unique_id=99)],
            connections=[],
        )
        output = serialize_tscn(scene)
        assert "unique_id=99" in output

    def test_unique_id_omitted_when_none(self) -> None:
        """Model-based serialization omits unique_id when None."""
        scene = GdScene(
            format=3, uid=None, load_steps=None,
            ext_resources=[], sub_resources=[],
            nodes=[SceneNode(name="Root", type="Node2D", parent=None)],
            connections=[],
        )
        output = serialize_tscn(scene)
        assert "unique_id" not in output

    def test_unique_id_in_to_dict(self) -> None:
        """GdScene.to_dict() includes unique_id."""
        scene = GdScene(
            format=3, uid=None, load_steps=None,
            ext_resources=[], sub_resources=[],
            nodes=[SceneNode(name="Root", type="Node2D", parent=None, unique_id=7)],
            connections=[],
        )
        d = scene.to_dict()
        assert d["nodes"][0]["unique_id"] == 7


class TestFormat4Parsing:
    """COMPAT-03: parser accepts format=4 files."""

    def test_parse_format4_tres(self) -> None:
        """Verify parser handles format=4 .tres with PackedVector4Array."""
        text = (
            '[gd_resource type="Resource" format=4]\n'
            "\n"
            "[resource]\n"
            "data = PackedVector4Array(1, 2, 3, 4, 5, 6, 7, 8)\n"
        )
        resource = parse_tres(text)
        assert resource.format == 4
        data = resource.resource_properties["data"]
        assert isinstance(data, PackedVector4Array)
        assert data.values == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)

    def test_packed_vector4_empty(self) -> None:
        """Verify empty PackedVector4Array parses correctly."""
        v = parse_value("PackedVector4Array()")
        assert isinstance(v, PackedVector4Array)
        assert v.values == ()

    def test_packed_vector4_serialize(self) -> None:
        """Verify PackedVector4Array serializes to Godot format."""
        v = PackedVector4Array((1.0, 0.5, 0.0, 1.0))
        assert serialize_value(v) == "PackedVector4Array(1, 0.5, 0, 1)"

    def test_format4_preserves_on_roundtrip(self) -> None:
        """format=4 value preserved in model."""
        text = '[gd_resource type="Resource" format=4]\n\n[resource]\n'
        resource = parse_tres(text)
        assert resource.format == 4


class TestPackedVector3Array:
    """Parser coverage for PackedVector3Array (3D meshes, paths, curves)."""

    def test_parse_packed_vector3(self) -> None:
        v = parse_value("PackedVector3Array(1, 2, 3, 4, 5, 6)")
        assert isinstance(v, PackedVector3Array)
        assert v.values == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)

    def test_parse_empty(self) -> None:
        v = parse_value("PackedVector3Array()")
        assert isinstance(v, PackedVector3Array)
        assert v.values == ()

    def test_serialize(self) -> None:
        v = PackedVector3Array((1.0, 0.5, 0.0, 2.0, 3.0, 4.0))
        assert serialize_value(v) == "PackedVector3Array(1, 0.5, 0, 2, 3, 4)"

    def test_round_trip_in_tres(self) -> None:
        text = (
            '[gd_resource type="Curve3D" format=3]\n\n'
            '[resource]\n'
            'points = PackedVector3Array(0, 0, 0, 1, 2, 3)\n'
        )
        resource = parse_tres(text)
        data = resource.resource_properties["points"]
        assert isinstance(data, PackedVector3Array)
        assert data.values == (0.0, 0.0, 0.0, 1.0, 2.0, 3.0)
        assert "PackedVector3Array(0, 0, 0, 1, 2, 3)" in serialize_tres(resource)


class TestPackedColorArray:
    """Parser coverage for PackedColorArray (gradients, terrain colors)."""

    def test_parse_packed_color(self) -> None:
        v = parse_value("PackedColorArray(1, 0, 0, 1, 0, 1, 0, 1)")
        assert isinstance(v, PackedColorArray)
        assert v.values == (1.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0)

    def test_parse_empty(self) -> None:
        v = parse_value("PackedColorArray()")
        assert isinstance(v, PackedColorArray)
        assert v.values == ()

    def test_serialize(self) -> None:
        v = PackedColorArray((1.0, 0.0, 0.0, 1.0))
        assert serialize_value(v) == "PackedColorArray(1, 0, 0, 1)"

    def test_round_trip_in_tres(self) -> None:
        text = (
            '[gd_resource type="Gradient" format=3]\n\n'
            '[resource]\n'
            'colors = PackedColorArray(1, 0, 0, 1, 0, 0, 1, 1)\n'
        )
        resource = parse_tres(text)
        data = resource.resource_properties["colors"]
        assert isinstance(data, PackedColorArray)
        assert data.values == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0)
        assert "PackedColorArray(1, 0, 0, 1, 0, 0, 1, 1)" in serialize_tres(resource)


class TestLoadStepsRemoval:
    """COMPAT-01 + BACK-01: generated files omit load_steps."""

    def test_tres_without_load_steps(self) -> None:
        """Verify model-built .tres omits load_steps when None."""
        resource = GdResource(
            type="SpriteFrames", format=3, uid=None,
            load_steps=None,
            ext_resources=[], sub_resources=[],
            resource_properties={},
        )
        output = serialize_tres(resource)
        assert "load_steps" not in output

    def test_tres_preserves_load_steps_on_roundtrip(self) -> None:
        """Per D-02: parsing a 4.5 file with load_steps preserves it in model."""
        text = '[gd_resource type="SpriteFrames" load_steps=6 format=3]\n\n[resource]\n'
        resource = parse_tres(text)
        assert resource.load_steps == 6
        # Raw round-trip preserves it
        output = serialize_tres(resource)
        assert "load_steps=6" in output

    def test_tscn_without_load_steps(self) -> None:
        """Verify model-built .tscn omits load_steps when None."""
        scene = GdScene(
            format=3, uid=None, load_steps=None,
            ext_resources=[], sub_resources=[],
            nodes=[], connections=[],
        )
        output = serialize_tscn(scene)
        assert "load_steps" not in output


class TestBackwardsCompat:
    """BACK-02: GodotBackend version validation."""

    def test_version_regex_accepts_46(self) -> None:
        """_VERSION_RE matches 4.6 version strings."""
        from auto_godot.backend import _VERSION_RE
        match = _VERSION_RE.search("4.6.1.stable.official.abc123")
        assert match is not None
        assert match.group(1) == "4"
        assert match.group(2) == "6"

    def test_version_regex_accepts_45(self) -> None:
        """_VERSION_RE matches 4.5 version strings."""
        from auto_godot.backend import _VERSION_RE
        match = _VERSION_RE.search("4.5.0.stable.official.xyz789")
        assert match is not None
        assert match.group(1) == "4"
        assert match.group(2) == "5"

    def test_version_check_accepts_46(self) -> None:
        """_check_version accepts Godot 4.6.x."""
        from auto_godot.backend import GodotBackend
        backend = GodotBackend()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="4.6.1.stable.official.abc123\n",
                returncode=0,
            )
            version = backend._check_version("godot")
            assert "4.6.1" in version

    def test_version_check_accepts_45(self) -> None:
        """_check_version accepts Godot 4.5.x."""
        from auto_godot.backend import GodotBackend
        backend = GodotBackend()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="4.5.2.stable.official.def456\n",
                returncode=0,
            )
            version = backend._check_version("godot")
            assert "4.5.2" in version
