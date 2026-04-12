"""Tests for the Godot node type allowlist."""

from __future__ import annotations

from auto_godot.formats.godot_types import (
    KNOWN_NODE_TYPES,
    is_known_node_type,
    suggest_node_types,
)


class TestIsKnownNodeType:
    def test_core_types(self) -> None:
        assert is_known_node_type("Node")
        assert is_known_node_type("Node2D")
        assert is_known_node_type("Node3D")
        assert is_known_node_type("Control")

    def test_common_2d_types(self) -> None:
        for name in (
            "Sprite2D", "AnimatedSprite2D", "Area2D", "Camera2D",
            "CharacterBody2D", "RigidBody2D", "StaticBody2D",
            "CollisionShape2D", "CollisionPolygon2D", "TileMap",
            "Timer", "Line2D", "Path2D",
        ):
            assert is_known_node_type(name), name

    def test_common_3d_types(self) -> None:
        for name in (
            "Sprite3D", "MeshInstance3D", "Camera3D", "CharacterBody3D",
            "RigidBody3D", "DirectionalLight3D", "OmniLight3D", "SpotLight3D",
            "Area3D", "CollisionShape3D",
        ):
            assert is_known_node_type(name), name

    def test_common_ui_types(self) -> None:
        for name in (
            "Label", "Button", "TextureButton", "LineEdit", "RichTextLabel",
            "VBoxContainer", "HBoxContainer", "Panel", "PanelContainer",
            "CenterContainer", "GridContainer", "ScrollContainer",
            "TextureRect", "NinePatchRect", "ColorRect", "ProgressBar",
        ):
            assert is_known_node_type(name), name

    def test_unknown_types(self) -> None:
        assert not is_known_node_type("NotARealNode")
        assert not is_known_node_type("MyCustomClass")
        # Case matters
        assert not is_known_node_type("sprite2d")
        assert not is_known_node_type("SPRITE2D")

    def test_empty_string(self) -> None:
        assert not is_known_node_type("")


class TestSuggestNodeTypes:
    def test_typo_character_body_2d(self) -> None:
        hits = suggest_node_types("CharcterBody2D")
        assert "CharacterBody2D" in hits

    def test_typo_sprite_3x(self) -> None:
        hits = suggest_node_types("Sprite3X")
        assert "Sprite3D" in hits

    def test_case_insensitive(self) -> None:
        hits = suggest_node_types("charcterbody2d")
        assert "CharacterBody2D" in hits

    def test_label_typo(self) -> None:
        hits = suggest_node_types("Labl")
        assert "Label" in hits

    def test_wildly_different_returns_few_or_none(self) -> None:
        # Something totally unrelated shouldn't flood with suggestions
        hits = suggest_node_types("XXXXXXXX")
        assert len(hits) <= 3

    def test_empty_string_returns_empty(self) -> None:
        assert suggest_node_types("") == []

    def test_respects_limit(self) -> None:
        hits = suggest_node_types("Body", limit=2)
        assert len(hits) <= 2


class TestAllowlistShape:
    def test_contains_hundreds_of_types(self) -> None:
        # Sanity floor: we should have a meaningful coverage of the Node tree
        assert len(KNOWN_NODE_TYPES) >= 150

    def test_all_entries_are_strings(self) -> None:
        for name in KNOWN_NODE_TYPES:
            assert isinstance(name, str) and name
