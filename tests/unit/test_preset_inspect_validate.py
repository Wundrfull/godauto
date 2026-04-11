"""Tests for preset inspect and validate commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli

SAMPLE_PRESETS = """\
[preset.0]

name="Windows Desktop"
platform="Windows Desktop"
runnable=true
dedicated_server=false
custom_features=""
export_path="export/game.exe"
encrypt_pck=false
script_export_mode=2

[preset.0.options]

binary_format/embed_pck=true
texture_format/s3tc_bptc=true

[preset.1]

name="Web"
platform="Web"
runnable=false
dedicated_server=false
custom_features=""
export_path="export/index.html"
encrypt_pck=false

[preset.1.options]

html/export_icon=true
"""


def _create_presets(tmp_path: Path, content: str = SAMPLE_PRESETS) -> Path:
    """Write a preset file and return the project directory."""
    (tmp_path / "export_presets.cfg").write_text(content, encoding="utf-8")
    return tmp_path


class TestPresetInspect:
    def test_inspect_by_name(self, tmp_path: Path) -> None:
        _create_presets(tmp_path)
        result = CliRunner().invoke(
            cli, ["preset", "inspect", "Windows Desktop", "--project", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "Windows Desktop" in result.output

    def test_inspect_json(self, tmp_path: Path) -> None:
        _create_presets(tmp_path)
        result = CliRunner().invoke(
            cli, ["-j", "preset", "inspect", "Windows Desktop", "--project", str(tmp_path)]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "Windows Desktop"
        assert data["platform"] == "Windows Desktop"
        assert data["runnable"] is True

    def test_inspect_includes_options(self, tmp_path: Path) -> None:
        _create_presets(tmp_path)
        result = CliRunner().invoke(
            cli, ["-j", "preset", "inspect", "Windows Desktop", "--project", str(tmp_path)]
        )
        data = json.loads(result.output)
        assert "options" in data
        assert data["options"]["binary_format/embed_pck"] == "true"

    def test_inspect_not_found(self, tmp_path: Path) -> None:
        _create_presets(tmp_path)
        result = CliRunner().invoke(
            cli, ["preset", "inspect", "Nonexistent", "--project", str(tmp_path)]
        )
        assert result.exit_code != 0

    def test_inspect_no_presets_file(self, tmp_path: Path) -> None:
        result = CliRunner().invoke(
            cli, ["preset", "inspect", "Windows Desktop", "--project", str(tmp_path)]
        )
        assert result.exit_code != 0


class TestPresetValidate:
    def test_valid_presets(self, tmp_path: Path) -> None:
        _create_presets(tmp_path)
        (tmp_path / "export").mkdir()  # Create export dir
        result = CliRunner().invoke(
            cli, ["preset", "validate", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_valid_json(self, tmp_path: Path) -> None:
        _create_presets(tmp_path)
        (tmp_path / "export").mkdir()
        result = CliRunner().invoke(
            cli, ["-j", "preset", "validate", str(tmp_path)]
        )
        data = json.loads(result.output)
        assert data["valid"] is True
        assert data["preset_count"] == 2

    def test_duplicate_name_warning(self, tmp_path: Path) -> None:
        content = (
            '[preset.0]\nname="Dup"\nplatform="Windows Desktop"\nexport_path="a.exe"\n'
            '[preset.0.options]\n'
            '[preset.1]\nname="Dup"\nplatform="Linux"\nexport_path="a.x86"\n'
            '[preset.1.options]\n'
        )
        _create_presets(tmp_path, content)
        result = CliRunner().invoke(
            cli, ["-j", "preset", "validate", str(tmp_path)]
        )
        assert result.exit_code == 0  # warnings are informational, not errors
        data = json.loads(result.output)
        assert data["valid"] is False
        issues = [w["issue"] for w in data["warnings"]]
        assert "duplicate_name" in issues

    def test_missing_export_path_warning(self, tmp_path: Path) -> None:
        content = '[preset.0]\nname="Bad"\nplatform="Windows Desktop"\n[preset.0.options]\n'
        _create_presets(tmp_path, content)
        result = CliRunner().invoke(
            cli, ["-j", "preset", "validate", str(tmp_path)]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["valid"] is False
        issues = [w["issue"] for w in data["warnings"]]
        assert "missing_export_path" in issues

    def test_unknown_platform_warning(self, tmp_path: Path) -> None:
        content = '[preset.0]\nname="T"\nplatform="PS5"\nexport_path="a.bin"\n[preset.0.options]\n'
        _create_presets(tmp_path, content)
        result = CliRunner().invoke(
            cli, ["-j", "preset", "validate", str(tmp_path)]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["valid"] is False
        issues = [w["issue"] for w in data["warnings"]]
        assert "unknown_platform" in issues

    def test_missing_export_dir_warning(self, tmp_path: Path) -> None:
        _create_presets(tmp_path)  # No export/ dir created
        result = CliRunner().invoke(
            cli, ["-j", "preset", "validate", str(tmp_path)]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["valid"] is False
        issues = [w["issue"] for w in data["warnings"]]
        assert "missing_export_dir" in issues

    def test_no_presets_file(self, tmp_path: Path) -> None:
        result = CliRunner().invoke(
            cli, ["preset", "validate", str(tmp_path)]
        )
        assert result.exit_code != 0
