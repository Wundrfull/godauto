"""Tests for locale (localization/translation) commands."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli


def _make_csv(tmp_path: Path, name: str = "translations.csv") -> Path:
    """Create a test translation CSV."""
    csv_path = tmp_path / name
    csv_path.write_text("keys,en,es\nMENU_START,Start Game,Iniciar Juego\nMENU_QUIT,Quit,\n")
    return csv_path


class TestLocaleCreate:
    """Verify locale create makes a translation CSV."""

    def test_create_default(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "translations.csv"
        runner = CliRunner()
        result = runner.invoke(cli, ["locale", "create", str(csv_path)])
        assert result.exit_code == 0, result.output
        assert csv_path.exists()
        text = csv_path.read_text()
        assert "keys,en" in text

    def test_create_custom_locale(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "translations.csv"
        runner = CliRunner()
        result = runner.invoke(cli, ["locale", "create", str(csv_path), "--default", "ja"])
        assert result.exit_code == 0
        text = csv_path.read_text()
        assert "keys,ja" in text

    def test_create_fails_if_exists(self, tmp_path: Path) -> None:
        csv_path = _make_csv(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["locale", "create", str(csv_path)])
        assert result.exit_code != 0

    def test_create_json(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "translations.csv"
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "locale", "create", str(csv_path)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] is True


class TestLocaleAddLocale:
    """Verify locale add-locale adds a column."""

    def test_add_locale(self, tmp_path: Path) -> None:
        csv_path = _make_csv(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["locale", "add-locale", str(csv_path), "ja"])
        assert result.exit_code == 0, result.output
        text = csv_path.read_text()
        assert "ja" in text.split("\n")[0]

    def test_add_duplicate_locale(self, tmp_path: Path) -> None:
        csv_path = _make_csv(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["locale", "add-locale", str(csv_path), "en"])
        assert result.exit_code != 0


class TestLocaleAddKey:
    """Verify locale add-key inserts translation rows."""

    def test_add_key_with_values(self, tmp_path: Path) -> None:
        csv_path = _make_csv(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "locale", "add-key", str(csv_path), "MENU_OPTIONS",
            "--value", "en=Options", "--value", "es=Opciones",
        ])
        assert result.exit_code == 0, result.output
        text = csv_path.read_text()
        assert "MENU_OPTIONS" in text
        assert "Options" in text
        assert "Opciones" in text

    def test_add_key_empty_values(self, tmp_path: Path) -> None:
        csv_path = _make_csv(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["locale", "add-key", str(csv_path), "NEW_KEY"])
        assert result.exit_code == 0
        reader = csv.DictReader(io.StringIO(csv_path.read_text()))
        rows = list(reader)
        new_row = [r for r in rows if r["keys"] == "NEW_KEY"]
        assert len(new_row) == 1

    def test_add_duplicate_key(self, tmp_path: Path) -> None:
        csv_path = _make_csv(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["locale", "add-key", str(csv_path), "MENU_START"])
        assert result.exit_code != 0

    def test_add_key_invalid_locale(self, tmp_path: Path) -> None:
        csv_path = _make_csv(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, [
            "locale", "add-key", str(csv_path), "TEST",
            "--value", "fr=Test",
        ])
        assert result.exit_code != 0  # fr not in CSV


class TestLocaleListKeys:
    """Verify locale list-keys shows all keys."""

    def test_list_keys(self, tmp_path: Path) -> None:
        csv_path = _make_csv(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["locale", "list-keys", str(csv_path)])
        assert result.exit_code == 0
        assert "MENU_START" in result.output
        assert "MENU_QUIT" in result.output

    def test_list_keys_json(self, tmp_path: Path) -> None:
        csv_path = _make_csv(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "locale", "list-keys", str(csv_path)])
        data = json.loads(result.output)
        assert data["count"] == 2
        assert "MENU_START" in data["keys"]


class TestLocaleListLocales:
    """Verify locale list-locales shows locale columns."""

    def test_list_locales(self, tmp_path: Path) -> None:
        csv_path = _make_csv(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["locale", "list-locales", str(csv_path)])
        assert result.exit_code == 0
        assert "en" in result.output
        assert "es" in result.output

    def test_list_locales_json(self, tmp_path: Path) -> None:
        csv_path = _make_csv(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "locale", "list-locales", str(csv_path)])
        data = json.loads(result.output)
        assert data["count"] == 2
        assert "en" in data["locales"]
        assert "es" in data["locales"]


class TestLocaleAudit:
    """Verify locale audit finds missing translations."""

    def test_audit_finds_missing(self, tmp_path: Path) -> None:
        csv_path = _make_csv(tmp_path)  # MENU_QUIT has empty es value
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "locale", "audit", str(csv_path)])
        data = json.loads(result.output)
        assert not data["complete"]
        assert data["missing_count"] > 0
        missing_keys = [m["key"] for m in data["missing"]]
        assert "MENU_QUIT" in missing_keys

    def test_audit_complete(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "complete.csv"
        csv_path.write_text("keys,en\nHELLO,Hello\nBYE,Bye\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "locale", "audit", str(csv_path)])
        data = json.loads(result.output)
        assert data["complete"]
        assert result.exit_code == 0


class TestLocaleExtract:
    """Verify locale extract finds tr() keys in GDScript files."""

    def test_extract_finds_keys(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "main.gd").write_text(
            'extends Node\n\n'
            'func _ready() -> void:\n'
            '\tvar label := $Label\n'
            '\tlabel.text = tr("HELLO_WORLD")\n'
            '\tprint(tr("GOODBYE"))\n'
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "locale", "extract", str(tmp_path)])
        data = json.loads(result.output)
        assert data["count"] == 2
        assert "HELLO_WORLD" in data["keys"]
        assert "GOODBYE" in data["keys"]

    def test_extract_writes_csv(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "main.gd").write_text('func test():\n\ttr("KEY1")\n')
        out_csv = tmp_path / "keys.csv"
        runner = CliRunner()
        result = runner.invoke(cli, [
            "locale", "extract", str(tmp_path), "-o", str(out_csv)
        ])
        assert result.exit_code == 0
        assert out_csv.exists()
        text = out_csv.read_text()
        assert "KEY1" in text

    def test_extract_empty_project(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["-j", "locale", "extract", str(tmp_path)])
        data = json.loads(result.output)
        assert data["count"] == 0
