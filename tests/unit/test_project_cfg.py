"""Tests for project.godot parser with round-trip fidelity."""

from __future__ import annotations

from pathlib import Path

import pytest

from gdauto.formats.project_cfg import (
    ProjectConfig,
    parse_project_config,
    serialize_project_config,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "sample_project"
SAMPLE_PROJECT_GODOT = FIXTURE_DIR / "project.godot"


@pytest.fixture()
def sample_text() -> str:
    """Load the sample project.godot fixture."""
    return SAMPLE_PROJECT_GODOT.read_text(encoding="utf-8")


@pytest.fixture()
def config(sample_text: str) -> ProjectConfig:
    """Parse the sample project.godot fixture."""
    return parse_project_config(sample_text)


class TestGlobalKeys:
    """Tests for global key parsing (keys before any section)."""

    def test_global_config_version(self, config: ProjectConfig) -> None:
        """Global key config_version=5 is parsed before any section."""
        assert config.get_global("config_version") == "5"

    def test_global_missing_key_returns_none(self, config: ProjectConfig) -> None:
        """Requesting a non-existent global key returns None."""
        assert config.get_global("nonexistent") is None


class TestSectionParsing:
    """Tests for section and key parsing."""

    def test_section_names(self, config: ProjectConfig) -> None:
        """All sections are discovered."""
        names = config.section_names()
        assert "application" in names
        assert "autoload" in names
        assert "display" in names
        assert "input" in names
        assert "rendering" in names

    def test_section_key_config_name(self, config: ProjectConfig) -> None:
        """Section key config/name is parsed with correct value."""
        assert config.get_value("application", "config/name") == "Test Project"

    def test_section_key_main_scene(self, config: ProjectConfig) -> None:
        """Section key run/main_scene returns the res:// path."""
        assert config.get_value("application", "run/main_scene") == "res://main.tscn"

    def test_slash_separated_keys_preserved(self, config: ProjectConfig) -> None:
        """Keys with slashes like window/size/viewport_width are kept as-is."""
        keys = config.keys("display")
        assert "window/size/viewport_width" in keys
        assert "window/size/viewport_height" in keys
        assert "window/stretch/mode" in keys

    def test_keys_for_section(self, config: ProjectConfig) -> None:
        """keys() returns the list of keys in a section."""
        app_keys = config.keys("application")
        assert "config/name" in app_keys
        assert "run/main_scene" in app_keys
        assert "config/tags" in app_keys

    def test_empty_section_returns_empty(self, config: ProjectConfig) -> None:
        """Requesting keys from a missing section returns empty list."""
        assert config.keys("nonexistent") == []

    def test_missing_section_value_returns_none(self, config: ProjectConfig) -> None:
        """get_value for missing section returns None."""
        assert config.get_value("nonexistent", "key") is None

    def test_missing_key_in_section_returns_none(self, config: ProjectConfig) -> None:
        """get_value for existing section but missing key returns None."""
        assert config.get_value("application", "nonexistent") is None


class TestValuePreservation:
    """Tests for raw value preservation (values stored as strings)."""

    def test_quoted_string_extracted(self, config: ProjectConfig) -> None:
        """Quoted string value has quotes stripped."""
        val = config.get_value("application", "config/name")
        assert val == "Test Project"
        assert not val.startswith('"')

    def test_godot_constructor_preserved_as_string(
        self, config: ProjectConfig
    ) -> None:
        """Godot constructor value like PackedStringArray(...) is preserved as raw string."""
        val = config.get_value("application", "config/tags")
        assert val is not None
        assert "PackedStringArray" in val

    def test_boolean_value_preserved_as_string(self, config: ProjectConfig) -> None:
        """Boolean value 'true' is stored as the string 'true'."""
        # config_version is "5" (string), not int
        assert config.get_global("config_version") == "5"

    def test_integer_value_preserved_as_string(self, config: ProjectConfig) -> None:
        """Integer value is stored as string."""
        val = config.get_value("display", "window/size/viewport_width")
        assert val == "1280"
        assert isinstance(val, str)


class TestMultilineValues:
    """Tests for multi-line value accumulation."""

    def test_multiline_object_value(self, config: ProjectConfig) -> None:
        """Multi-line value with {Object(...)} spanning lines is accumulated."""
        val = config.get_value("input", "move_up")
        assert val is not None
        # The value should contain the full multi-line content
        assert "deadzone" in val
        assert "Object(InputEventKey" in val
        assert "}" in val


class TestComments:
    """Tests for comment preservation."""

    def test_semicolon_comments_preserved_in_round_trip(
        self, sample_text: str
    ) -> None:
        """Semicolon comments are preserved through parse/serialize cycle."""
        config = parse_project_config(sample_text)
        output = serialize_project_config(config)
        assert "; Engine configuration file." in output
        assert "; It's best edited using the editor UI" in output


class TestRoundTrip:
    """Tests for serialization round-trip fidelity."""

    def test_round_trip_identity(self, sample_text: str) -> None:
        """serialize(parse(text)) produces identical output."""
        config = parse_project_config(sample_text)
        output = serialize_project_config(config)
        assert output == sample_text

    def test_round_trip_minimal(self) -> None:
        """Round-trip works on a minimal project.godot."""
        text = "config_version=5\n\n[application]\n\nconfig/name=\"Minimal\"\n"
        config = parse_project_config(text)
        output = serialize_project_config(config)
        assert output == text


class TestToDict:
    """Tests for JSON-serializable dict conversion."""

    def test_to_dict_has_global(self, config: ProjectConfig) -> None:
        """to_dict() includes global keys."""
        d = config.to_dict()
        assert "global" in d
        assert d["global"]["config_version"] == "5"

    def test_to_dict_has_sections(self, config: ProjectConfig) -> None:
        """to_dict() includes all sections with their keys."""
        d = config.to_dict()
        assert "sections" in d
        assert "application" in d["sections"]
        assert d["sections"]["application"]["config/name"] == "Test Project"
