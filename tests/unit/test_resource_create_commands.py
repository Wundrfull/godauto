"""Tests for resource create-gradient and create-curve commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gdauto.cli import cli


class TestCreateGradient:
    """Verify resource create-gradient generates Gradient .tres files."""

    def test_two_stop_gradient(self, tmp_path: Path) -> None:
        out = tmp_path / "fade.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "resource", "create-gradient",
            "--stop", "0:black",
            "--stop", "1:white",
            str(out),
        ])
        assert result.exit_code == 0, result.output
        text = out.read_text()
        assert 'type="Gradient"' in text
        assert "PackedFloat32Array" in text
        assert "PackedColorArray" in text

    def test_three_stop_gradient(self, tmp_path: Path) -> None:
        out = tmp_path / "health.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "resource", "create-gradient",
            "--stop", "0:#ff0000",
            "--stop", "0.5:#ffff00",
            "--stop", "1:#00ff00",
            str(out),
        ])
        assert result.exit_code == 0
        text = out.read_text()
        assert "Gradient" in text

    def test_gradient_json(self, tmp_path: Path) -> None:
        out = tmp_path / "g.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "resource", "create-gradient",
            "--stop", "0:red",
            "--stop", "1:blue",
            str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True
        assert data["stop_count"] == 2

    def test_invalid_stop_format(self, tmp_path: Path) -> None:
        out = tmp_path / "g.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "resource", "create-gradient",
            "--stop", "invalid",
            str(out),
        ])
        assert result.exit_code != 0

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        out = tmp_path / "res" / "gradients" / "fade.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "resource", "create-gradient",
            "--stop", "0:black", "--stop", "1:white",
            str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()


class TestCreateCurve:
    """Verify resource create-curve generates Curve .tres files."""

    def test_linear_curve(self, tmp_path: Path) -> None:
        out = tmp_path / "linear.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "resource", "create-curve",
            "--point", "0,0",
            "--point", "1,1",
            str(out),
        ])
        assert result.exit_code == 0, result.output
        text = out.read_text()
        assert 'type="Curve"' in text
        assert "PackedFloat32Array" in text
        assert "point_count" in text

    def test_bell_curve(self, tmp_path: Path) -> None:
        out = tmp_path / "bell.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "resource", "create-curve",
            "--point", "0,0",
            "--point", "0.5,1",
            "--point", "1,0",
            str(out),
        ])
        assert result.exit_code == 0

    def test_curve_json(self, tmp_path: Path) -> None:
        out = tmp_path / "c.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "-j", "resource", "create-curve",
            "--point", "0,0",
            "--point", "1,1",
            str(out),
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True
        assert data["point_count"] == 2

    def test_invalid_point(self, tmp_path: Path) -> None:
        out = tmp_path / "c.tres"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "resource", "create-curve",
            "--point", "invalid",
            str(out),
        ])
        assert result.exit_code != 0
