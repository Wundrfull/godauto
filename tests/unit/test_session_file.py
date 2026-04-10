"""Unit tests for session file CRUD and .gitignore management."""

from __future__ import annotations

import json
from pathlib import Path

from auto_godot.debugger.models import SessionInfo
from auto_godot.debugger.session_file import (
    cleanup_session,
    read_session_file,
    write_session_file,
)


def _make_info() -> SessionInfo:
    """Create a test SessionInfo."""
    return SessionInfo(
        host="127.0.0.1",
        port=6007,
        game_pid=1234,
        project_path="/tmp/proj",
        created_at="2026-04-06T12:00:00Z",
    )


class TestWriteSessionFile:
    """Tests for write_session_file."""

    def test_creates_session_json(self, tmp_path: Path) -> None:
        """write_session_file creates .auto-godot/session.json with valid JSON."""
        info = _make_info()
        write_session_file(tmp_path, info)
        session_path = tmp_path / ".auto-godot" / "session.json"
        assert session_path.exists()
        data = json.loads(session_path.read_text())
        assert data["host"] == "127.0.0.1"
        assert data["port"] == 6007
        assert data["game_pid"] == 1234


class TestReadSessionFile:
    """Tests for read_session_file."""

    def test_returns_session_info_when_exists(self, tmp_path: Path) -> None:
        """read_session_file returns SessionInfo when file exists."""
        info = _make_info()
        write_session_file(tmp_path, info)
        result = read_session_file(tmp_path)
        assert result is not None
        assert result.host == "127.0.0.1"
        assert result.port == 6007

    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        """read_session_file returns None when file missing."""
        result = read_session_file(tmp_path)
        assert result is None

    def test_returns_none_on_invalid_json(self, tmp_path: Path) -> None:
        """read_session_file returns None when file contains invalid JSON."""
        auto_godot_dir = tmp_path / ".auto-godot"
        auto_godot_dir.mkdir()
        (auto_godot_dir / "session.json").write_text("not valid json{{{")
        result = read_session_file(tmp_path)
        assert result is None


class TestCleanupSession:
    """Tests for cleanup_session."""

    def test_removes_session_and_dir_if_empty(self, tmp_path: Path) -> None:
        """cleanup_session removes session.json and .auto-godot/ dir if empty."""
        info = _make_info()
        write_session_file(tmp_path, info)
        cleanup_session(tmp_path)
        assert not (tmp_path / ".auto-godot" / "session.json").exists()
        assert not (tmp_path / ".auto-godot").exists()

    def test_keeps_dir_if_other_files_exist(self, tmp_path: Path) -> None:
        """cleanup_session keeps .auto-godot/ dir if other files exist."""
        info = _make_info()
        write_session_file(tmp_path, info)
        (tmp_path / ".auto-godot" / "other.txt").write_text("keep me")
        cleanup_session(tmp_path)
        assert not (tmp_path / ".auto-godot" / "session.json").exists()
        assert (tmp_path / ".auto-godot").exists()

    def test_no_error_when_nothing_to_clean(self, tmp_path: Path) -> None:
        """cleanup_session does not raise when no session file exists."""
        cleanup_session(tmp_path)  # should not raise


class TestGitignore:
    """Tests for .gitignore management via write_session_file."""

    def test_creates_gitignore_with_auto_godot(self, tmp_path: Path) -> None:
        """write_session_file on project with no .gitignore creates one."""
        info = _make_info()
        write_session_file(tmp_path, info)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        assert ".auto-godot/" in gitignore.read_text()

    def test_appends_to_existing_gitignore(self, tmp_path: Path) -> None:
        """write_session_file appends .auto-godot/ to existing .gitignore."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("__pycache__/\n")
        info = _make_info()
        write_session_file(tmp_path, info)
        content = gitignore.read_text()
        assert "__pycache__/" in content
        assert ".auto-godot/" in content

    def test_does_not_duplicate_in_gitignore(self, tmp_path: Path) -> None:
        """write_session_file does not duplicate .auto-godot/ in .gitignore."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".auto-godot/\n")
        info = _make_info()
        write_session_file(tmp_path, info)
        content = gitignore.read_text()
        assert content.count(".auto-godot/") == 1

    def test_adds_newline_before_entry_if_missing(self, tmp_path: Path) -> None:
        """write_session_file adds newline before .auto-godot/ if file lacks trailing newline."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("__pycache__/")  # no trailing newline
        info = _make_info()
        write_session_file(tmp_path, info)
        content = gitignore.read_text()
        # Should have newline between entries
        assert "__pycache__/\n.auto-godot/\n" in content
