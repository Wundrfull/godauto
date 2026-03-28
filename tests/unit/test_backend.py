"""Tests for GodotBackend binary discovery, version validation, and subprocess management."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gdauto.backend import GodotBackend
from gdauto.errors import GdautoError, GodotBinaryError


class TestBinaryDiscovery:
    """Tests for Godot binary discovery priority: flag > env > PATH."""

    def test_no_binary_anywhere_raises_godot_binary_error(self) -> None:
        """GodotBackend with no binary path, no env, no PATH raises GodotBinaryError."""
        backend = GodotBackend()
        with patch("shutil.which", return_value=None):
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(GodotBinaryError) as exc_info:
                    backend.ensure_binary()
                assert exc_info.value.code == "GODOT_NOT_FOUND"

    def test_error_fix_contains_path_and_env_var(self) -> None:
        """GodotBinaryError.fix mentions PATH and GODOT_PATH."""
        backend = GodotBackend()
        with patch("shutil.which", return_value=None):
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(GodotBinaryError) as exc_info:
                    backend.ensure_binary()
                assert "PATH" in exc_info.value.fix
                assert "GODOT_PATH" in exc_info.value.fix

    def test_explicit_binary_path_stored(self) -> None:
        """GodotBackend with explicit binary_path uses that path."""
        backend = GodotBackend(binary_path="/usr/bin/godot")
        assert backend.binary_path == "/usr/bin/godot"

    def test_explicit_path_takes_priority(self) -> None:
        """Explicit binary_path is used even when env and PATH are set."""
        backend = GodotBackend(binary_path="/opt/godot")
        mock_result = MagicMock()
        mock_result.stdout = "4.5.2.stable.official.abc1234"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = backend.ensure_binary()
        assert result == "/opt/godot"

    def test_env_var_takes_priority_over_path(self) -> None:
        """GODOT_PATH env var is used when no explicit path is set."""
        backend = GodotBackend()
        mock_result = MagicMock()
        mock_result.stdout = "4.5.0.stable.official.abc1234"
        mock_result.returncode = 0
        with patch.dict("os.environ", {"GODOT_PATH": "/env/godot"}):
            with patch("subprocess.run", return_value=mock_result):
                result = backend.ensure_binary()
        assert result == "/env/godot"

    def test_path_discovery_via_which(self) -> None:
        """shutil.which('godot') is used when no explicit path or env var."""
        backend = GodotBackend()
        mock_result = MagicMock()
        mock_result.stdout = "4.5.0.stable.official.abc1234"
        mock_result.returncode = 0
        with patch.dict("os.environ", {}, clear=True):
            with patch("shutil.which", return_value="/usr/local/bin/godot"):
                with patch("subprocess.run", return_value=mock_result):
                    result = backend.ensure_binary()
        assert result == "/usr/local/bin/godot"


class TestVersionValidation:
    """Tests for Godot version checking and validation."""

    def test_version_452_succeeds(self) -> None:
        """Version 4.5.2.stable.official.abc1234 passes validation."""
        backend = GodotBackend(binary_path="/usr/bin/godot")
        mock_result = MagicMock()
        mock_result.stdout = "4.5.2.stable.official.abc1234"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = backend.ensure_binary()
        assert result == "/usr/bin/godot"

    def test_version_440_too_old(self) -> None:
        """Version 4.4.0 raises GodotBinaryError with GODOT_VERSION_TOO_OLD."""
        backend = GodotBackend(binary_path="/usr/bin/godot")
        mock_result = MagicMock()
        mock_result.stdout = "4.4.0.stable.official.abc1234"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(GodotBinaryError) as exc_info:
                backend.ensure_binary()
            assert exc_info.value.code == "GODOT_VERSION_TOO_OLD"

    def test_version_3_too_old(self) -> None:
        """Version 3.5.0.stable raises GodotBinaryError."""
        backend = GodotBackend(binary_path="/usr/bin/godot")
        mock_result = MagicMock()
        mock_result.stdout = "3.5.0.stable"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(GodotBinaryError) as exc_info:
                backend.ensure_binary()
            assert exc_info.value.code == "GODOT_VERSION_TOO_OLD"

    def test_version_cached_after_first_call(self) -> None:
        """Version check is cached; second ensure_binary does not invoke subprocess again."""
        backend = GodotBackend(binary_path="/usr/bin/godot")
        mock_result = MagicMock()
        mock_result.stdout = "4.5.0.stable.official.abc1234"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            backend.ensure_binary()
            backend.ensure_binary()
            # Should only be called once for version check
            assert mock_run.call_count == 1


class TestRunCommand:
    """Tests for GodotBackend.run() subprocess invocation."""

    def _make_backend(self) -> GodotBackend:
        """Create a backend with cached version (skip version check)."""
        backend = GodotBackend(binary_path="/usr/bin/godot")
        backend._version = "4.5.0"
        return backend

    def test_run_constructs_headless_command(self) -> None:
        """run(['--version']) invokes [binary, '--headless', '--version']."""
        backend = self._make_backend()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            backend.run(["--version"])
            cmd = mock_run.call_args[0][0]
            assert cmd == ["/usr/bin/godot", "--headless", "--version"]

    def test_run_nonzero_raises_error(self) -> None:
        """run() with non-zero return code raises GdautoError."""
        backend = self._make_backend()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Something went wrong"
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(GdautoError) as exc_info:
                backend.run(["--check-only"])
            assert exc_info.value.code == "GODOT_RUN_FAILED"

    def test_run_passes_timeout(self) -> None:
        """run() with timeout parameter passes it to subprocess.run."""
        backend = self._make_backend()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            backend.run(["--version"], timeout=5)
            assert mock_run.call_args[1]["timeout"] == 5

    def test_run_with_project_path(self) -> None:
        """run() with project_path appends --path to command."""
        backend = self._make_backend()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            backend.run(["--check-only"], project_path=Path("/my/project"))
            cmd = mock_run.call_args[0][0]
            assert "--path" in cmd
            assert str(Path("/my/project")) in cmd


class TestCheckOnly:
    """Tests for GodotBackend.check_only() convenience method."""

    def test_check_only_invokes_check_flag(self) -> None:
        """check_only() passes --check-only and --path to run."""
        backend = GodotBackend(binary_path="/usr/bin/godot")
        backend._version = "4.5.0"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            backend.check_only(Path("/my/project"))
            cmd = mock_run.call_args[0][0]
            assert "--check-only" in cmd
            assert "--path" in cmd
