"""Tests for export preset management commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


class TestPresetCreate:
    """Verify preset create generates export_presets.cfg."""

    def test_single_platform(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "preset", "create",
            "--platform", "windows",
            str(tmp_path),
        ])
        assert result.exit_code == 0, result.output
        preset_file = tmp_path / "export_presets.cfg"
        assert preset_file.exists()
        text = preset_file.read_text()
        assert "[preset.0]" in text
        assert "Windows Desktop" in text

    def test_multiple_platforms(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "preset", "create",
            "--platform", "windows",
            "--platform", "linux",
            "--platform", "web",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        text = (tmp_path / "export_presets.cfg").read_text()
        assert "[preset.0]" in text
        assert "[preset.1]" in text
        assert "[preset.2]" in text
        assert "Windows Desktop" in text
        assert "Linux" in text
        assert "Web" in text

    def test_runnable_flag(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(cli, [
            "preset", "create",
            "--platform", "windows",
            "--runnable",
            str(tmp_path),
        ])
        text = (tmp_path / "export_presets.cfg").read_text()
        assert "runnable=true" in text

    def test_no_runnable_flag(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(cli, [
            "preset", "create",
            "--platform", "windows",
            "--no-runnable",
            str(tmp_path),
        ])
        text = (tmp_path / "export_presets.cfg").read_text()
        assert "runnable=false" in text

    def test_json_output(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "preset", "create",
            "--platform", "windows",
            "--platform", "web",
            str(tmp_path),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True
        assert data["count"] == 2


class TestPresetCreateContent:
    """Verify export_presets.cfg content structure."""

    def test_has_export_path(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(cli, [
            "preset", "create", "--platform", "windows", str(tmp_path),
        ])
        text = (tmp_path / "export_presets.cfg").read_text()
        assert "export_path=" in text
        assert ".exe" in text

    def test_has_options_section(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(cli, [
            "preset", "create", "--platform", "windows", str(tmp_path),
        ])
        text = (tmp_path / "export_presets.cfg").read_text()
        assert "[preset.0.options]" in text

    def test_web_export_path(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(cli, [
            "preset", "create", "--platform", "web", str(tmp_path),
        ])
        text = (tmp_path / "export_presets.cfg").read_text()
        assert "index.html" in text


class TestPresetList:
    """Verify listing export presets."""

    def test_list_presets(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(cli, [
            "preset", "create",
            "--platform", "windows",
            "--platform", "web",
            str(tmp_path),
        ])
        result = runner.invoke(cli, ["preset", "list", str(tmp_path)])
        assert result.exit_code == 0
        assert "Windows" in result.output
        assert "Web" in result.output

    def test_list_json(self, tmp_path: Path) -> None:
        runner = CliRunner()
        runner.invoke(cli, [
            "preset", "create",
            "--platform", "windows",
            str(tmp_path),
        ])
        result = runner.invoke(cli, ["-j", "preset", "list", str(tmp_path)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["presets"][0]["platform"] == "Windows Desktop"

    def test_list_no_presets_error(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["preset", "list", str(tmp_path)])
        assert result.exit_code != 0


class TestListPlatforms:
    """Verify listing available platforms."""

    def test_list_platforms(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["preset", "list-platforms"])
        assert result.exit_code == 0
        assert "windows" in result.output
        assert "linux" in result.output
        assert "web" in result.output

    def test_list_platforms_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "preset", "list-platforms"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 5
        keys = [p["key"] for p in data["platforms"]]
        assert "windows" in keys
        assert "web" in keys
