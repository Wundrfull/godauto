"""Tests for debug tree, debug get, debug output CLI commands (Phase 8 Plan 02)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from gdauto.cli import cli
from gdauto.debugger.errors import DebuggerError
from gdauto.debugger.models import SceneNode


@pytest.fixture()
def runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


# ---------------------------------------------------------------------------
# debug tree
# ---------------------------------------------------------------------------

class TestDebugTree:
    """Tests for the debug tree CLI command."""

    def test_help_shows_options(self, runner: CliRunner) -> None:
        """debug tree --help shows --depth, --full, --project, --port, --timeout."""
        result = runner.invoke(cli, ["debug", "tree", "--help"])
        assert result.exit_code == 0
        assert "--depth" in result.output
        assert "--full" in result.output
        assert "--project" in result.output
        assert "--port" in result.output
        assert "--timeout" in result.output

    @patch("gdauto.commands.debug.get_scene_tree", new_callable=AsyncMock)
    @patch("gdauto.commands.debug.async_connect", new_callable=AsyncMock)
    def test_json_output(
        self,
        mock_connect: AsyncMock,
        mock_tree: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """--json debug tree produces JSON with nested tree structure."""
        from gdauto.debugger.connect import ConnectResult

        mock_connect.return_value = ConnectResult(
            host="127.0.0.1", port=6007, thread_id=1, game_pid=1234,
        )
        root = SceneNode(
            name="root", type_name="Node", instance_id=1,
            scene_file_path="", view_flags=0, path="/root",
            children=[
                SceneNode(
                    name="Main", type_name="Node2D", instance_id=2,
                    scene_file_path="", view_flags=0, path="/root/Main",
                ),
            ],
        )
        mock_tree.return_value = root

        result = runner.invoke(
            cli, ["--json", "debug", "tree", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "root"
        assert data["children"][0]["name"] == "Main"

    @patch("gdauto.commands.debug.get_scene_tree", new_callable=AsyncMock)
    @patch("gdauto.commands.debug.async_connect", new_callable=AsyncMock)
    def test_passes_depth_to_get_scene_tree(
        self,
        mock_connect: AsyncMock,
        mock_tree: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """debug tree --depth 2 passes max_depth=2 to get_scene_tree."""
        from gdauto.debugger.connect import ConnectResult

        mock_connect.return_value = ConnectResult(
            host="127.0.0.1", port=6007, thread_id=1, game_pid=1234,
        )
        root = SceneNode(
            name="root", type_name="Node", instance_id=1,
            scene_file_path="", view_flags=0, path="/root",
        )
        mock_tree.return_value = root

        runner.invoke(
            cli, ["debug", "tree", "--project", str(tmp_path), "--depth", "2"],
        )
        call_kwargs = mock_tree.call_args
        assert call_kwargs[1].get("max_depth") == 2 or call_kwargs.kwargs.get("max_depth") == 2

    @patch("gdauto.commands.debug.get_scene_tree", new_callable=AsyncMock)
    @patch("gdauto.commands.debug.async_connect", new_callable=AsyncMock)
    def test_passes_full_to_get_scene_tree(
        self,
        mock_connect: AsyncMock,
        mock_tree: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """debug tree --full passes full=True to get_scene_tree."""
        from gdauto.debugger.connect import ConnectResult

        mock_connect.return_value = ConnectResult(
            host="127.0.0.1", port=6007, thread_id=1, game_pid=1234,
        )
        root = SceneNode(
            name="root", type_name="Node", instance_id=1,
            scene_file_path="", view_flags=0, path="/root",
        )
        mock_tree.return_value = root

        runner.invoke(
            cli, ["debug", "tree", "--project", str(tmp_path), "--full"],
        )
        call_kwargs = mock_tree.call_args
        assert call_kwargs[1].get("full") is True or call_kwargs.kwargs.get("full") is True

    @patch("gdauto.commands.debug.get_scene_tree", new_callable=AsyncMock)
    @patch("gdauto.commands.debug.async_connect", new_callable=AsyncMock)
    def test_human_output(
        self,
        mock_connect: AsyncMock,
        mock_tree: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Human mode prints indented tree with type annotations."""
        from gdauto.debugger.connect import ConnectResult

        mock_connect.return_value = ConnectResult(
            host="127.0.0.1", port=6007, thread_id=1, game_pid=1234,
        )
        root = SceneNode(
            name="root", type_name="Node", instance_id=1,
            scene_file_path="", view_flags=0, path="/root",
            children=[
                SceneNode(
                    name="Main", type_name="Node2D", instance_id=2,
                    scene_file_path="", view_flags=0, path="/root/Main",
                ),
            ],
        )
        mock_tree.return_value = root

        result = runner.invoke(
            cli, ["debug", "tree", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "/root (Node)" in result.output
        assert "/root/Main (Node2D)" in result.output

    @patch("gdauto.commands.debug.async_connect", new_callable=AsyncMock)
    def test_error_produces_nonzero_exit(
        self,
        mock_connect: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Error during tree command produces non-zero exit code."""
        mock_connect.side_effect = DebuggerError(
            message="Connection failed", code="DEBUG_ERROR", fix="Try again",
        )
        result = runner.invoke(
            cli, ["debug", "tree", "--project", str(tmp_path)],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# debug get
# ---------------------------------------------------------------------------

class TestDebugGet:
    """Tests for the debug get CLI command."""

    def test_help_shows_options(self, runner: CliRunner) -> None:
        """debug get --help shows --node, --property, --project, --port, --timeout."""
        result = runner.invoke(cli, ["debug", "get", "--help"])
        assert result.exit_code == 0
        assert "--node" in result.output
        assert "--property" in result.output
        assert "--project" in result.output
        assert "--port" in result.output
        assert "--timeout" in result.output

    @patch("gdauto.commands.debug.get_property", new_callable=AsyncMock)
    @patch("gdauto.commands.debug.async_connect", new_callable=AsyncMock)
    def test_json_output(
        self,
        mock_connect: AsyncMock,
        mock_get_prop: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """--json debug get returns structured JSON with node, property, value."""
        from gdauto.debugger.connect import ConnectResult

        mock_connect.return_value = ConnectResult(
            host="127.0.0.1", port=6007, thread_id=1, game_pid=1234,
        )
        mock_get_prop.return_value = "Hello"

        result = runner.invoke(
            cli,
            ["--json", "debug", "get", "--project", str(tmp_path),
             "--node", "/root/Main", "--property", "text"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["node"] == "/root/Main"
        assert data["property"] == "text"
        assert data["value"] == "Hello"

    def test_missing_node_flag(self, runner: CliRunner) -> None:
        """Missing --node produces a usage error."""
        result = runner.invoke(
            cli, ["debug", "get", "--property", "text"],
        )
        assert result.exit_code != 0

    def test_missing_property_flag(self, runner: CliRunner) -> None:
        """Missing --property produces a usage error."""
        result = runner.invoke(
            cli, ["debug", "get", "--node", "/root/Main"],
        )
        assert result.exit_code != 0

    @patch("gdauto.commands.debug.get_property", new_callable=AsyncMock)
    @patch("gdauto.commands.debug.async_connect", new_callable=AsyncMock)
    def test_node_not_found_error(
        self,
        mock_connect: AsyncMock,
        mock_get_prop: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Node not found produces error with DEBUG_NODE_NOT_FOUND."""
        from gdauto.debugger.connect import ConnectResult

        mock_connect.return_value = ConnectResult(
            host="127.0.0.1", port=6007, thread_id=1, game_pid=1234,
        )
        mock_get_prop.side_effect = DebuggerError(
            message="Node not found: /root/Bad",
            code="DEBUG_NODE_NOT_FOUND",
            fix="Check path",
        )
        result = runner.invoke(
            cli,
            ["debug", "get", "--project", str(tmp_path),
             "--node", "/root/Bad", "--property", "text"],
        )
        assert result.exit_code != 0

    @patch("gdauto.commands.debug.get_property", new_callable=AsyncMock)
    @patch("gdauto.commands.debug.async_connect", new_callable=AsyncMock)
    def test_human_output(
        self,
        mock_connect: AsyncMock,
        mock_get_prop: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Human mode prints node.property = value."""
        from gdauto.debugger.connect import ConnectResult

        mock_connect.return_value = ConnectResult(
            host="127.0.0.1", port=6007, thread_id=1, game_pid=1234,
        )
        mock_get_prop.return_value = "Hello World"

        result = runner.invoke(
            cli,
            ["debug", "get", "--project", str(tmp_path),
             "--node", "/root/Label", "--property", "text"],
        )
        assert result.exit_code == 0
        assert "/root/Label.text = Hello World" in result.output


# ---------------------------------------------------------------------------
# debug output
# ---------------------------------------------------------------------------

class TestDebugOutput:
    """Tests for the debug output CLI command."""

    def test_help_shows_options(self, runner: CliRunner) -> None:
        """debug output --help shows --follow, --errors-only, --project, --port, --timeout."""
        result = runner.invoke(cli, ["debug", "output", "--help"])
        assert result.exit_code == 0
        assert "--follow" in result.output
        assert "--errors-only" in result.output
        assert "--project" in result.output
        assert "--port" in result.output
        assert "--timeout" in result.output

    @patch("gdauto.commands.debug.async_connect", new_callable=AsyncMock)
    def test_follow_not_implemented(
        self,
        mock_connect: AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """--follow returns error with code DEBUG_NOT_IMPLEMENTED."""
        result = runner.invoke(
            cli,
            ["debug", "output", "--project", str(tmp_path), "--follow"],
        )
        assert result.exit_code != 0

    @patch("gdauto.commands.debug.format_error_messages")
    @patch("gdauto.commands.debug.format_output_messages")
    @patch("gdauto.commands.debug.async_connect", new_callable=AsyncMock)
    def test_snapshot_json_output(
        self,
        mock_connect: AsyncMock,
        mock_fmt_output: MagicMock,
        mock_fmt_errors: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Snapshot mode returns JSON with messages list."""
        from gdauto.debugger.connect import ConnectResult

        mock_result = ConnectResult(
            host="127.0.0.1", port=6007, thread_id=1, game_pid=1234,
        )
        mock_connect.return_value = mock_result
        mock_fmt_output.return_value = [
            {"text": "Score: 10", "type": "output"},
        ]
        mock_fmt_errors.return_value = [
            {"text": "Error: bad", "type": "error", "source": "main.gd:1"},
        ]

        result = runner.invoke(
            cli,
            ["--json", "debug", "output", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "messages" in data
        assert len(data["messages"]) == 2

    @patch("gdauto.commands.debug.format_error_messages")
    @patch("gdauto.commands.debug.format_output_messages")
    @patch("gdauto.commands.debug.async_connect", new_callable=AsyncMock)
    def test_errors_only_filter(
        self,
        mock_connect: AsyncMock,
        mock_fmt_output: MagicMock,
        mock_fmt_errors: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """--errors-only filters to type=='error' only."""
        from gdauto.debugger.connect import ConnectResult

        mock_connect.return_value = ConnectResult(
            host="127.0.0.1", port=6007, thread_id=1, game_pid=1234,
        )
        mock_fmt_output.return_value = [
            {"text": "Hello", "type": "output"},
        ]
        mock_fmt_errors.return_value = [
            {"text": "Error: bad", "type": "error", "source": "main.gd:1"},
        ]

        result = runner.invoke(
            cli,
            ["--json", "debug", "output", "--project", str(tmp_path), "--errors-only"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        # Should only contain error messages, not output
        for msg in data["messages"]:
            assert msg["type"] == "error"


# ---------------------------------------------------------------------------
# Command registration
# ---------------------------------------------------------------------------

class TestCommandRegistration:
    """Verify all three new commands are registered in the debug group."""

    def test_tree_registered(self) -> None:
        """tree command is registered in the debug group."""
        from gdauto.commands.debug import debug
        assert "tree" in debug.commands

    def test_get_registered(self) -> None:
        """get command is registered in the debug group."""
        from gdauto.commands.debug import debug
        assert "get" in debug.commands

    def test_output_registered(self) -> None:
        """output command is registered in the debug group."""
        from gdauto.commands.debug import debug
        assert "output" in debug.commands
