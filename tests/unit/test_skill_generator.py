"""Tests for SKILL.md generator using Click introspection."""

from __future__ import annotations

import pytest


def test_generate_skill_md_starts_with_title() -> None:
    """Output should start with '# gdauto' as the document title."""
    from gdauto.skill.generator import generate_skill_md

    result = generate_skill_md()
    assert result.startswith("# gdauto")


def test_generate_skill_md_has_commands_section() -> None:
    """Output should contain a '## Commands' section header."""
    from gdauto.skill.generator import generate_skill_md

    result = generate_skill_md()
    assert "## Commands" in result


def test_generate_skill_md_contains_all_command_groups() -> None:
    """Output should contain all registered command group names."""
    from gdauto.skill.generator import generate_skill_md

    result = generate_skill_md()
    for group in ("project", "resource", "export", "sprite", "tileset", "scene", "skill"):
        assert group in result, f"Command group '{group}' not found in output"


def test_generate_skill_md_contains_subcommands() -> None:
    """Output should contain known subcommand names."""
    from gdauto.skill.generator import generate_skill_md

    result = generate_skill_md()
    for subcommand in ("import-aseprite", "create-atlas", "split", "validate"):
        assert subcommand in result, f"Subcommand '{subcommand}' not found in output"


def test_generate_skill_md_has_global_options() -> None:
    """Output should contain '## Global Options' with known global flags."""
    from gdauto.skill.generator import generate_skill_md

    result = generate_skill_md()
    assert "## Global Options" in result
    for flag in ("--json", "--verbose", "--quiet", "--godot-path"):
        assert flag in result, f"Global flag '{flag}' not found in output"


def test_generate_skill_md_has_examples() -> None:
    """Output should contain at least one '**Example:**' block per D-11."""
    from gdauto.skill.generator import generate_skill_md

    result = generate_skill_md()
    assert "**Example:**" in result


def test_generate_skill_md_contains_param_descriptions() -> None:
    """Output should contain argument and option names from actual commands."""
    from gdauto.skill.generator import generate_skill_md

    result = generate_skill_md()
    # import-aseprite has a JSON_FILE argument
    assert "JSON_FILE" in result or "json_file" in result.lower()
    # sprite import-aseprite has --output option
    assert "--output" in result


def test_generate_skill_md_contains_help_text() -> None:
    """Output should include actual help text strings from commands."""
    from gdauto.skill.generator import generate_skill_md

    result = generate_skill_md()
    # Root group help
    assert "Agent-native CLI" in result
    # Sprite group help
    assert "Sprite sheet" in result or "sprite" in result.lower()


def test_render_command_mock() -> None:
    """_render_command on a simple mock info dict produces expected markdown."""
    from gdauto.skill.generator import _render_command

    lines: list[str] = []
    mock_info = {
        "name": "mock-cmd",
        "help": "A mock command for testing.",
        "hidden": False,
        "deprecated": False,
        "params": [
            {
                "name": "input_file",
                "param_type_name": "argument",
                "type": {"name": "PATH"},
                "required": True,
                "help": None,
                "opts": ["input_file"],
            },
            {
                "name": "output",
                "param_type_name": "option",
                "type": {"name": "PATH"},
                "required": False,
                "default": None,
                "help": "Output file path.",
                "opts": ["-o", "--output"],
                "is_flag": False,
                "multiple": False,
                "nargs": 1,
            },
        ],
        "commands": {},
    }
    _render_command("mock-cmd", mock_info, "gdauto", lines)
    rendered = "\n".join(lines)
    assert "mock-cmd" in rendered
    assert "A mock command" in rendered
    assert "INPUT_FILE" in rendered or "input_file" in rendered.lower()


def test_hidden_commands_excluded() -> None:
    """Hidden commands should be excluded from the generated output."""
    from gdauto.skill.generator import _should_skip

    assert _should_skip({"hidden": True, "deprecated": False}) is True
    assert _should_skip({"hidden": False, "deprecated": True}) is True
    assert _should_skip({"hidden": False, "deprecated": False}) is False
