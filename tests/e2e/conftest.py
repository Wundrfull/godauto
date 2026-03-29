"""E2E test configuration: auto-skip when Godot binary is absent.

Per D-07: @pytest.mark.requires_godot marker on all E2E tests.
Tests skip gracefully when no Godot binary is found.
"""

from __future__ import annotations

import shutil

import pytest

from gdauto.backend import GodotBackend


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip tests marked requires_godot when Godot is absent."""
    if shutil.which("godot"):
        return
    skip_godot = pytest.mark.skip(reason="Godot binary not found on PATH")
    for item in items:
        if "requires_godot" in item.keywords:
            item.add_marker(skip_godot)


@pytest.fixture
def godot_backend() -> GodotBackend:
    """Provide a GodotBackend instance for E2E tests."""
    return GodotBackend()
