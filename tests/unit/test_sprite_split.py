"""Unit tests for sprite sheet splitting (grid-based and JSON-defined)."""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gdauto.errors import GdautoError, ValidationError
from gdauto.formats.tres import GdResource
from gdauto.formats.values import Rect2, StringName, SubResourceRef


# ---------------------------------------------------------------------------
# split_sheet_grid
# ---------------------------------------------------------------------------


class TestSplitSheetGrid:
    """Tests for grid-based sprite sheet splitting."""

    def _make_mock_image(self, width: int, height: int) -> MagicMock:
        """Create a mock PIL Image with given dimensions."""
        mock_img = MagicMock()
        mock_img.width = width
        mock_img.height = height
        mock_img.close = MagicMock()
        return mock_img

    @patch("gdauto.sprite.splitter.Image")
    def test_128x64_with_32x32_frames_produces_8_sub_resources(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.splitter import split_sheet_grid

        mock_image_module.open.return_value = self._make_mock_image(128, 64)
        resource = split_sheet_grid(
            Path("sheet.png"), 32, 32, "res://sheet.png"
        )
        assert len(resource.sub_resources) == 8

    @patch("gdauto.sprite.splitter.Image")
    def test_creates_default_animation_with_all_frames(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.splitter import split_sheet_grid

        mock_image_module.open.return_value = self._make_mock_image(128, 64)
        resource = split_sheet_grid(
            Path("sheet.png"), 32, 32, "res://sheet.png"
        )
        anims = resource.resource_properties["animations"]
        assert len(anims) == 1
        assert anims[0]["name"] == StringName("default")
        assert len(anims[0]["frames"]) == 8

    @patch("gdauto.sprite.splitter.Image")
    def test_region_computation_col1_row0(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.splitter import split_sheet_grid

        mock_image_module.open.return_value = self._make_mock_image(128, 64)
        resource = split_sheet_grid(
            Path("sheet.png"), 32, 32, "res://sheet.png"
        )
        # col=1, row=0 is the second sub_resource (index 1)
        region = resource.sub_resources[1].properties["region"]
        assert region == Rect2(32.0, 0.0, 32.0, 32.0)

    @patch("gdauto.sprite.splitter.Image")
    def test_frame_too_large_raises_validation_error(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.splitter import split_sheet_grid

        mock_image_module.open.return_value = self._make_mock_image(64, 64)
        with pytest.raises(ValidationError, match="exceeds image size") as exc_info:
            split_sheet_grid(Path("sheet.png"), 128, 128, "res://sheet.png")
        assert exc_info.value.code == "SPRITE_FRAME_TOO_LARGE"

    @patch("gdauto.sprite.splitter.Image")
    def test_non_divisible_size_warns(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.splitter import split_sheet_grid

        mock_image_module.open.return_value = self._make_mock_image(100, 64)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            resource = split_sheet_grid(
                Path("sheet.png"), 32, 32, "res://sheet.png"
            )
            assert len(w) == 1
            assert "not evenly divisible" in str(w[0].message)
        # 100 // 32 = 3 cols, 64 // 32 = 2 rows = 6 frames
        assert len(resource.sub_resources) == 6

    @patch("gdauto.sprite.splitter.Image")
    def test_resource_type_is_spriteframes(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.splitter import split_sheet_grid

        mock_image_module.open.return_value = self._make_mock_image(64, 64)
        resource = split_sheet_grid(
            Path("sheet.png"), 32, 32, "res://sheet.png"
        )
        assert resource.type == "SpriteFrames"
        assert resource.format == 3

    @patch("gdauto.sprite.splitter.Image")
    def test_load_steps_computed_correctly(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.splitter import split_sheet_grid

        mock_image_module.open.return_value = self._make_mock_image(64, 32)
        resource = split_sheet_grid(
            Path("sheet.png"), 32, 32, "res://sheet.png"
        )
        # 1 ext_resource + 2 sub_resources + 1 = 4
        assert resource.load_steps == 4

    @patch("gdauto.sprite.splitter.Image")
    def test_custom_fps(
        self, mock_image_module: MagicMock
    ) -> None:
        from gdauto.sprite.splitter import split_sheet_grid

        mock_image_module.open.return_value = self._make_mock_image(64, 32)
        resource = split_sheet_grid(
            Path("sheet.png"), 32, 32, "res://sheet.png", fps=24.0
        )
        anims = resource.resource_properties["animations"]
        assert anims[0]["speed"] == 24.0


# ---------------------------------------------------------------------------
# split_sheet_json
# ---------------------------------------------------------------------------


class TestSplitSheetJson:
    """Tests for JSON-defined sprite sheet splitting."""

    def _make_mock_image(self, width: int, height: int) -> MagicMock:
        """Create a mock PIL Image with given dimensions."""
        mock_img = MagicMock()
        mock_img.width = width
        mock_img.height = height
        mock_img.close = MagicMock()
        return mock_img

    @patch("gdauto.sprite.splitter.Image")
    def test_json_regions_create_sub_resources(
        self, mock_image_module: MagicMock, tmp_path: Path
    ) -> None:
        from gdauto.sprite.splitter import split_sheet_json

        mock_image_module.open.return_value = self._make_mock_image(128, 64)
        json_data = {
            "frames": [
                {"x": 0, "y": 0, "w": 32, "h": 32},
                {"x": 32, "y": 0, "w": 32, "h": 32},
                {"x": 64, "y": 0, "w": 32, "h": 32},
            ]
        }
        json_path = tmp_path / "regions.json"
        json_path.write_text(json.dumps(json_data))

        resource = split_sheet_json(
            Path("sheet.png"), json_path, "res://sheet.png"
        )
        assert len(resource.sub_resources) == 3
        assert resource.sub_resources[0].properties["region"] == Rect2(
            0.0, 0.0, 32.0, 32.0
        )


# ---------------------------------------------------------------------------
# Pillow not installed
# ---------------------------------------------------------------------------


class TestPillowNotInstalled:
    """Tests for graceful handling when Pillow is missing."""

    def test_require_pillow_raises_when_none(self) -> None:
        from gdauto.sprite.splitter import _require_pillow

        with patch("gdauto.sprite.splitter.Image", None):
            with pytest.raises(GdautoError) as exc_info:
                _require_pillow()
            assert exc_info.value.code == "PILLOW_NOT_INSTALLED"
            assert "pip install gdauto[image]" in (exc_info.value.fix or "")


# ---------------------------------------------------------------------------
# CLI command tests
# ---------------------------------------------------------------------------


class TestSplitCLI:
    """Tests for the sprite split CLI command."""

    def test_no_frame_size_or_json_meta_exits_nonzero(self) -> None:
        from click.testing import CliRunner

        from gdauto.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["sprite", "split", "sheet.png"])
        assert result.exit_code != 0

    @patch("gdauto.sprite.splitter.Image")
    @patch("gdauto.formats.tres.serialize_tres_file")
    def test_frame_size_exits_zero(
        self,
        mock_serialize: MagicMock,
        mock_image_module: MagicMock,
        tmp_path: Path,
    ) -> None:
        from click.testing import CliRunner

        from gdauto.cli import cli

        mock_img = MagicMock()
        mock_img.width = 128
        mock_img.height = 64
        mock_img.close = MagicMock()
        mock_image_module.open.return_value = mock_img

        image_file = tmp_path / "sheet.png"
        image_file.write_bytes(b"fake")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sprite", "split", str(image_file), "--frame-size", "32x32"],
        )
        assert result.exit_code == 0

    def test_nonexistent_image_exits_nonzero(self) -> None:
        from click.testing import CliRunner

        from gdauto.cli import cli

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "sprite",
                "split",
                "nonexistent.png",
                "--frame-size",
                "32x32",
            ],
        )
        assert result.exit_code != 0
