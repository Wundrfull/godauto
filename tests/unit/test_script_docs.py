"""Tests for script docs command and GDScript doc parser."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from auto_godot.cli import cli
from auto_godot.gdscript_docs import format_markdown, parse_gdscript

SAMPLE_SCRIPT = """\
## A player controller for the game.
class_name Player
extends CharacterBody2D

## Emitted when the player dies.
signal died
signal health_changed(new_health: int, old_health: int)

enum State { IDLE, RUNNING, JUMPING, FALLING }

## Direction the player is facing.
enum Direction {
    LEFT,
    RIGHT,
    UP,
    DOWN,
}

## Maximum speed in pixels per second.
const MAX_SPEED: float = 300.0

## Movement speed.
@export var speed: float = 200.0
@export_range(0, 100) var health: int = 50

var current_health: int = 100
## Whether the player can take damage.
var is_invincible: bool = false

func _ready() -> void:
    current_health = max_health

## Deal damage to the player.
func take_damage(amount: int) -> void:
    if is_invincible:
        return
    var old: int = current_health
    current_health -= amount

func heal(amount: int) -> int:
    return 0

static func get_default_speed() -> float:
    return 200.0
"""


class TestParseGdscript:
    """Verify parser extracts all declaration types."""

    def test_class_metadata(self) -> None:
        doc = parse_gdscript(SAMPLE_SCRIPT, "player.gd")
        assert doc.class_name == "Player"
        assert doc.extends == "CharacterBody2D"
        assert "player controller" in doc.description

    def test_signals(self) -> None:
        doc = parse_gdscript(SAMPLE_SCRIPT, "player.gd")
        assert len(doc.signals) == 2
        assert doc.signals[0]["name"] == "died"
        assert "player dies" in doc.signals[0].get("doc", "")
        assert "health_changed" in doc.signals[1]["signature"]

    def test_enums(self) -> None:
        doc = parse_gdscript(SAMPLE_SCRIPT, "player.gd")
        assert len(doc.enums) == 2
        assert "IDLE" in doc.enums[0]["values"]
        assert "DOWN" in doc.enums[1]["values"]
        assert "Direction" in doc.enums[1].get("doc", "")

    def test_constants(self) -> None:
        doc = parse_gdscript(SAMPLE_SCRIPT, "player.gd")
        assert len(doc.constants) == 1
        assert doc.constants[0]["name"] == "MAX_SPEED"

    def test_exports_including_range(self) -> None:
        doc = parse_gdscript(SAMPLE_SCRIPT, "player.gd")
        assert len(doc.exports) == 2
        assert doc.exports[0]["name"] == "speed"
        assert doc.exports[1]["name"] == "health"

    def test_variables_skip_locals(self) -> None:
        doc = parse_gdscript(SAMPLE_SCRIPT, "player.gd")
        names = [v["name"] for v in doc.variables]
        assert "current_health" in names
        assert "is_invincible" in names
        assert "old" not in names  # local var inside take_damage

    def test_functions(self) -> None:
        doc = parse_gdscript(SAMPLE_SCRIPT, "player.gd")
        names = [f["name"] for f in doc.functions]
        assert "_ready" in names
        assert "take_damage" in names
        assert "heal" in names
        heal = next(f for f in doc.functions if f["name"] == "heal")
        assert heal["return_type"] == "int"

    def test_static_function(self) -> None:
        doc = parse_gdscript(SAMPLE_SCRIPT, "player.gd")
        sf = next(f for f in doc.functions if f["name"] == "get_default_speed")
        assert sf.get("static") is True

    def test_doc_comments_on_functions(self) -> None:
        doc = parse_gdscript(SAMPLE_SCRIPT, "player.gd")
        td = next(f for f in doc.functions if f["name"] == "take_damage")
        assert "Deal damage" in td.get("doc", "")


    def test_generic_return_type(self) -> None:
        text = "func get_items() -> Array[int]:\n\treturn []\n"
        doc = parse_gdscript(text, "g.gd")
        assert doc.functions[0]["return_type"] == "Array[int]"

    def test_trailing_whitespace_top_level(self) -> None:
        text = "extends Node\nvar x: int = 0  \n"
        doc = parse_gdscript(text, "t.gd")
        assert len(doc.variables) == 1


class TestEdgeCases:
    def test_empty_script(self) -> None:
        doc = parse_gdscript("", "e.gd")
        assert doc.class_name is None
        assert doc.to_dict() == {"path": "e.gd"}

    def test_extends_only(self) -> None:
        doc = parse_gdscript("extends Node\n", "m.gd")
        assert doc.extends == "Node"

    def test_empty_sections_omitted_from_dict(self) -> None:
        d = parse_gdscript("extends Node\n", "m.gd").to_dict()
        assert "signals" not in d
        assert "exports" not in d


class TestFormatMarkdown:
    def test_title_and_extends(self) -> None:
        md = format_markdown(parse_gdscript(SAMPLE_SCRIPT, "player.gd"))
        assert md.startswith("# Player\n")
        assert "**Extends:** `CharacterBody2D`" in md

    def test_all_sections_present(self) -> None:
        md = format_markdown(parse_gdscript(SAMPLE_SCRIPT, "player.gd"))
        for section in ("Signals", "Enums", "Constants", "Exported Properties", "Functions"):
            assert f"## {section}" in md

    def test_filename_title_when_no_class(self) -> None:
        md = format_markdown(parse_gdscript("extends Node\n", "my_util.gd"))
        assert md.startswith("# my_util\n")


class TestDocsCommand:
    def test_single_file_human(self, tmp_path: Path) -> None:
        gd = tmp_path / "test.gd"
        gd.write_text("extends Node2D\n\nfunc greet() -> void:\n\tpass\n")
        result = CliRunner().invoke(cli, ["script", "docs", str(gd)])
        assert result.exit_code == 0
        assert "greet" in result.output

    def test_single_file_json(self, tmp_path: Path) -> None:
        gd = tmp_path / "p.gd"
        gd.write_text("class_name P\nextends Node\nsignal died\nfunc _ready() -> void:\n\tpass\n")
        result = CliRunner().invoke(cli, ["-j", "script", "docs", str(gd)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["scripts"][0]["class_name"] == "P"

    def test_directory_recursive(self, tmp_path: Path) -> None:
        (tmp_path / "sub").mkdir()
        (tmp_path / "a.gd").write_text("extends Node\n")
        (tmp_path / "sub" / "b.gd").write_text("extends Node2D\n")
        result = CliRunner().invoke(cli, ["-j", "script", "docs", str(tmp_path)])
        data = json.loads(result.output)
        assert data["count"] == 2

    def test_output_dir(self, tmp_path: Path) -> None:
        gd = tmp_path / "player.gd"
        gd.write_text("class_name Player\nextends Node\n")
        out = tmp_path / "docs"
        result = CliRunner().invoke(cli, ["script", "docs", str(gd), "-o", str(out)])
        assert result.exit_code == 0
        assert (out / "player.md").exists()
        assert "# Player" in (out / "player.md").read_text()

    def test_non_gd_rejected(self, tmp_path: Path) -> None:
        txt = tmp_path / "x.txt"
        txt.write_text("not gdscript")
        assert CliRunner().invoke(cli, ["script", "docs", str(txt)]).exit_code != 0

    def test_empty_dir_rejected(self, tmp_path: Path) -> None:
        d = tmp_path / "empty"
        d.mkdir()
        assert CliRunner().invoke(cli, ["script", "docs", str(d)]).exit_code != 0

    def test_duplicate_stem_collision(self, tmp_path: Path) -> None:
        (tmp_path / "scripts").mkdir()
        (tmp_path / "addons").mkdir()
        (tmp_path / "scripts" / "player.gd").write_text("extends Node2D\n")
        (tmp_path / "addons" / "player.gd").write_text("extends Node\n")
        out = tmp_path / "docs"
        result = CliRunner().invoke(
            cli, ["script", "docs", str(tmp_path), "-o", str(out)]
        )
        assert result.exit_code == 0
        md_files = list(out.glob("*.md"))
        assert len(md_files) == 2  # no overwrite
