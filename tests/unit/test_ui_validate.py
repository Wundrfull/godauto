"""Tests for `auto-godot ui validate`."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


def _write_scene(tmp_path: Path, body: str) -> Path:
    """Write a minimal .tscn with the given body after the header."""
    path = tmp_path / "scene.tscn"
    path.write_text(f"[gd_scene format=3]\n\n{body}", encoding="utf-8")
    return path


def _run(scene: Path, json_mode: bool = False) -> tuple[int, str]:
    runner = CliRunner()
    args = (["-j"] if json_mode else []) + ["ui", "validate", str(scene)]
    result = runner.invoke(cli, args)
    return result.exit_code, result.output


def _findings(output: str) -> list[dict]:
    # Pre-JSON warnings may prefix output; slice from first '{'.
    brace = output.find("{")
    assert brace >= 0, output
    data = json.loads(output[brace:])
    return data["findings"]


class TestCheckContainerChildAnchor:
    def test_flags_anchor_override_under_container(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="VBoxContainer"]\n\n'
            '[node name="Btn" type="Button" parent="."]\n'
            'anchor_left = 0.5\n'
        )
        code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "container-child-anchor" in codes

    def test_no_flag_when_not_under_container(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n\n'
            '[node name="Btn" type="Button" parent="."]\n'
            'anchor_left = 0.5\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "container-child-anchor" not in codes


class TestCheckInvisiblePanelContainer:
    def test_flags_panel_container_without_override(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n\n'
            '[node name="Panel" type="PanelContainer" parent="."]\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "invisible-panel-container" in codes

    def test_no_flag_when_style_override_present(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[sub_resource type="StyleBoxFlat" id="sb"]\n\n'
            '[node name="Root" type="Control"]\n\n'
            '[node name="Panel" type="PanelContainer" parent="."]\n'
            'theme_override_styles/panel = SubResource("sb")\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "invisible-panel-container" not in codes


class TestCheckSizeFlagsBitfield:
    def test_flags_invalid_combination(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n\n'
            '[node name="Box" type="Control" parent="."]\n'
            'size_flags_horizontal = 5\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "size-flags-nonsense" in codes

    def test_allows_valid_combinations(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n\n'
            '[node name="A" type="Control" parent="."]\n'
            'size_flags_horizontal = 3\n'
            'size_flags_vertical = 6\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "size-flags-nonsense" not in codes


class TestCheckBoxChildCollapse:
    def test_flags_vbox_child_with_zero(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="VBoxContainer"]\n\n'
            '[node name="Child" type="Label" parent="."]\n'
            'size_flags_vertical = 0\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "box-child-collapsed" in codes

    def test_no_flag_when_expand_set(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="HBoxContainer"]\n\n'
            '[node name="Child" type="Label" parent="."]\n'
            'size_flags_horizontal = 3\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "box-child-collapsed" not in codes


class TestCheckButtonMouseIgnore:
    def test_flags_button_with_mouse_ignore(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n\n'
            '[node name="Btn" type="Button" parent="."]\n'
            'mouse_filter = 2\n'
        )
        code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "button-mouse-ignore" in codes
        assert code == 2  # error severity triggers exit 2

    def test_no_flag_when_mouse_filter_default(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n\n'
            '[node name="Btn" type="Button" parent="."]\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "button-mouse-ignore" not in codes


class TestCheckOverlayBlocksInput:
    def test_flags_full_rect_overlay_after_button(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n\n'
            '[node name="Btn" type="Button" parent="."]\n\n'
            '[node name="Overlay" type="Control" parent="."]\n'
            'anchors_preset = 15\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "overlay-blocks-input" in codes

    def test_no_flag_when_overlay_is_ignore(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n\n'
            '[node name="Btn" type="Button" parent="."]\n\n'
            '[node name="Overlay" type="Control" parent="."]\n'
            'anchors_preset = 15\n'
            'mouse_filter = 2\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "overlay-blocks-input" not in codes


class TestCheckAutowrapZeroWidth:
    def test_flags_label_autowrap_with_no_width(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n\n'
            '[node name="Msg" type="Label" parent="."]\n'
            'autowrap_mode = 2\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "autowrap-zero-width" in codes

    def test_no_flag_when_min_size_set(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n\n'
            '[node name="Msg" type="Label" parent="."]\n'
            'autowrap_mode = 2\n'
            'custom_minimum_size = Vector2(200, 0)\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "autowrap-zero-width" not in codes


class TestCheckScrollContainerChild:
    def test_flags_scroll_child_without_fill_expand(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="ScrollContainer"]\n\n'
            '[node name="Child" type="VBoxContainer" parent="."]\n'
            'size_flags_horizontal = 1\n'
            'size_flags_vertical = 1\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "scroll-child-collapse" in codes

    def test_no_flag_when_one_axis_fills(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="ScrollContainer"]\n\n'
            '[node name="Child" type="VBoxContainer" parent="."]\n'
            'size_flags_horizontal = 3\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "scroll-child-collapse" not in codes


class TestCheckThemeOverrideFamily:
    def test_flags_font_color_on_scroll_container(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="ScrollContainer"]\n'
            'theme_override_colors/font_color = Color(1, 0, 0, 1)\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "theme-override-mismatch" in codes

    def test_no_flag_for_valid_label_font_color(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n\n'
            '[node name="L" type="Label" parent="."]\n'
            'theme_override_colors/font_color = Color(1, 0, 0, 1)\n'
        )
        _code, out = _run(scene, json_mode=True)
        codes = {f["code"] for f in _findings(out)}
        assert "theme-override-mismatch" not in codes


class TestExitCodes:
    def test_clean_scene_exits_zero(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n'
        )
        code, _out = _run(scene)
        assert code == 0

    def test_warnings_only_exits_one(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="VBoxContainer"]\n\n'
            '[node name="Child" type="Label" parent="."]\n'
            'size_flags_vertical = 0\n'
        )
        code, _out = _run(scene)
        assert code == 1

    def test_errors_exit_two(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n\n'
            '[node name="Btn" type="Button" parent="."]\n'
            'mouse_filter = 2\n'
        )
        code, _out = _run(scene)
        assert code == 2


class TestOutputModes:
    def test_json_output_shape(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n'
        )
        _code, out = _run(scene, json_mode=True)
        brace = out.find("{")
        data = json.loads(out[brace:])
        for key in ("scene", "findings", "error_count", "warning_count",
                    "checks_run"):
            assert key in data, f"Missing {key} in JSON output"

    def test_human_output_shows_clean(self, tmp_path: Path) -> None:
        scene = _write_scene(tmp_path,
            '[node name="Root" type="Control"]\n'
        )
        _code, out = _run(scene)
        assert "Clean" in out


class TestMissingFile:
    def test_nonexistent_file_returns_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["ui", "validate", "/nonexistent.tscn"])
        assert result.exit_code != 0

    def test_nonexistent_file_json_has_error_code(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "ui", "validate", "/nonexistent.tscn"])
        assert result.exit_code != 0
        brace = result.output.find("{")
        data = json.loads(result.output[brace:])
        assert "code" in data
