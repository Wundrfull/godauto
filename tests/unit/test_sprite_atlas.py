"""Unit tests for atlas creation (shelf packing and CLI command)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from gdauto.errors import GdautoError, ValidationError
from gdauto.formats.tres import GdResource
from gdauto.formats.values import Rect2, StringName


# ---------------------------------------------------------------------------
# next_power_of_two
# ---------------------------------------------------------------------------


class TestNextPowerOfTwo:
    """Tests for power-of-two rounding utility."""

    def test_1_returns_1(self) -> None:
        from gdauto.sprite.atlas import next_power_of_two

        assert next_power_of_two(1) == 1

    def test_2_returns_2(self) -> None:
        from gdauto.sprite.atlas import next_power_of_two

        assert next_power_of_two(2) == 2

    def test_3_returns_4(self) -> None:
        from gdauto.sprite.atlas import next_power_of_two

        assert next_power_of_two(3) == 4

    def test_33_returns_64(self) -> None:
        from gdauto.sprite.atlas import next_power_of_two

        assert next_power_of_two(33) == 64

    def test_64_returns_64(self) -> None:
        from gdauto.sprite.atlas import next_power_of_two

        assert next_power_of_two(64) == 64

    def test_100_returns_128(self) -> None:
        from gdauto.sprite.atlas import next_power_of_two

        assert next_power_of_two(100) == 128

    def test_1024_returns_1024(self) -> None:
        from gdauto.sprite.atlas import next_power_of_two

        assert next_power_of_two(1024) == 1024

    def test_0_returns_1(self) -> None:
        from gdauto.sprite.atlas import next_power_of_two

        assert next_power_of_two(0) == 1

    def test_negative_returns_1(self) -> None:
        from gdauto.sprite.atlas import next_power_of_two

        assert next_power_of_two(-5) == 1


# ---------------------------------------------------------------------------
# create_atlas
# ---------------------------------------------------------------------------


class TestCreateAtlas:
    """Tests for atlas creation with shelf packing."""

    def _make_mock_image(self, width: int, height: int) -> MagicMock:
        """Create a mock PIL Image with given dimensions."""
        mock_img = MagicMock()
        mock_img.width = width
        mock_img.height = height
        mock_img.size = (width, height)
        mock_img.close = MagicMock()
        return mock_img

    @patch("gdauto.sprite.atlas.Image")
    def test_four_32x32_images_produces_4_sub_resources(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.atlas import create_atlas

        images = [self._make_mock_image(32, 32) for _ in range(4)]
        mock_image_module.open.side_effect = images
        mock_image_module.new.return_value = self._make_mock_image(64, 64)

        paths = [Path(f"img{i}.png") for i in range(4)]
        atlas_img, resource = create_atlas(paths, "res://atlas.png")

        assert len(resource.sub_resources) == 4
        assert resource.type == "SpriteFrames"

    @patch("gdauto.sprite.atlas.Image")
    def test_power_of_two_dimensions(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.atlas import create_atlas

        # 3 images of 30x30 require 90 total area; shelf packing with POT
        images = [self._make_mock_image(30, 30) for _ in range(3)]
        mock_image_module.open.side_effect = images
        mock_image_module.new.return_value = self._make_mock_image(64, 64)

        paths = [Path(f"img{i}.png") for i in range(3)]
        atlas_img, resource = create_atlas(
            paths, "res://atlas.png", power_of_two=True
        )

        # Verify Image.new was called with power-of-two dimensions
        new_call = mock_image_module.new.call_args
        dims = new_call[0][1]
        # Both width and height should be powers of two
        assert dims[0] & (dims[0] - 1) == 0  # power of two check
        assert dims[1] & (dims[1] - 1) == 0

    @patch("gdauto.sprite.atlas.Image")
    def test_no_pot_uses_exact_dimensions(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.atlas import create_atlas

        # Use 2 images of 30x30; total area sqrt = ~42, *1.5 = ~63
        # Both fit on one shelf (30+30=60 <= 63), so exact dims = 60x30
        images = [self._make_mock_image(30, 30) for _ in range(2)]
        mock_image_module.open.side_effect = images
        mock_image_module.new.return_value = self._make_mock_image(60, 30)

        paths = [Path(f"img{i}.png") for i in range(2)]
        atlas_img, resource = create_atlas(
            paths, "res://atlas.png", power_of_two=False
        )

        new_call = mock_image_module.new.call_args
        dims = new_call[0][1]
        # With 2 images of 30x30 on one shelf, exact dimensions = 60x30
        assert dims == (60, 30)

    @patch("gdauto.sprite.atlas.Image")
    def test_regions_are_non_overlapping(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.atlas import create_atlas

        images = [self._make_mock_image(32, 32) for _ in range(4)]
        mock_image_module.open.side_effect = images
        mock_image_module.new.return_value = self._make_mock_image(128, 128)

        paths = [Path(f"img{i}.png") for i in range(4)]
        _, resource = create_atlas(
            paths, "res://atlas.png", power_of_two=False
        )

        regions = [
            sub.properties["region"] for sub in resource.sub_resources
        ]
        # Check no two regions overlap
        for i, r1 in enumerate(regions):
            for j, r2 in enumerate(regions):
                if i >= j:
                    continue
                overlap = r1.intersection(r2)
                assert overlap is None, (
                    f"Region {i} ({r1}) overlaps with region {j} ({r2})"
                )

    @patch("gdauto.sprite.atlas.Image")
    def test_default_animation_created(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.atlas import create_atlas

        images = [self._make_mock_image(32, 32) for _ in range(2)]
        mock_image_module.open.side_effect = images
        mock_image_module.new.return_value = self._make_mock_image(64, 32)

        paths = [Path(f"img{i}.png") for i in range(2)]
        _, resource = create_atlas(paths, "res://atlas.png")

        anims = resource.resource_properties["animations"]
        assert len(anims) == 1
        assert anims[0]["name"] == StringName("default")
        assert anims[0]["loop"] is True

    @patch("gdauto.sprite.atlas.Image")
    def test_empty_image_list_raises_validation_error(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.atlas import create_atlas

        with pytest.raises(ValidationError, match="at least one image"):
            create_atlas([], "res://atlas.png")

    def test_pillow_not_installed_raises_error(self) -> None:
        from gdauto.sprite.atlas import _require_pillow

        with patch("gdauto.sprite.atlas.Image", None):
            with pytest.raises(GdautoError) as exc_info:
                _require_pillow()
            assert exc_info.value.code == "PILLOW_NOT_INSTALLED"

    @patch("gdauto.sprite.atlas.Image")
    def test_paste_called_for_each_image(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.atlas import create_atlas

        images = [self._make_mock_image(32, 32) for _ in range(3)]
        mock_image_module.open.side_effect = images
        atlas_mock = self._make_mock_image(128, 32)
        mock_image_module.new.return_value = atlas_mock

        paths = [Path(f"img{i}.png") for i in range(3)]
        atlas_img, _ = create_atlas(paths, "res://atlas.png")

        # paste should have been called 3 times
        assert atlas_mock.paste.call_count == 3


# ---------------------------------------------------------------------------
# CLI command tests
# ---------------------------------------------------------------------------


class TestCreateAtlasCLI:
    """Tests for the sprite create-atlas CLI command."""

    @patch("gdauto.sprite.atlas.Image")
    def test_create_atlas_command_exits_zero(
        self, mock_image_module: MagicMock, tmp_path: Path
    ) -> None:
        from click.testing import CliRunner

        from gdauto.cli import cli

        # Create fake input images
        img1 = tmp_path / "img1.png"
        img2 = tmp_path / "img2.png"
        img1.write_bytes(b"fake")
        img2.write_bytes(b"fake")

        mock_img = MagicMock()
        mock_img.width = 32
        mock_img.height = 32
        mock_img.size = (32, 32)
        mock_img.close = MagicMock()
        mock_img.save = MagicMock()
        mock_image_module.open.return_value = mock_img
        mock_image_module.new.return_value = mock_img

        output = tmp_path / "atlas.png"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "sprite",
                "create-atlas",
                str(img1),
                str(img2),
                "-o",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
