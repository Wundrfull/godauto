"""Tests for the export pipeline: retry logic, auto-import, and export orchestration."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gdauto.errors import GdautoError


# ---------------------------------------------------------------------------
# import_with_retry tests
# ---------------------------------------------------------------------------


class TestImportWithRetry:
    """Tests for import_with_retry exponential backoff behavior."""

    def test_success_on_first_attempt(self) -> None:
        """import_with_retry calls backend.import_resources once on success."""
        from gdauto.export.pipeline import import_with_retry

        backend = MagicMock()
        backend.import_resources.return_value = MagicMock()
        stream = io.StringIO()

        import_with_retry(backend, Path("/project"), status_stream=stream)

        backend.import_resources.assert_called_once_with(Path("/project"))

    def test_retries_up_to_three_times(self) -> None:
        """import_with_retry retries 3 times on GdautoError with 1s, 2s, 4s delays."""
        from gdauto.export.pipeline import import_with_retry

        backend = MagicMock()
        backend.import_resources.side_effect = GdautoError(
            message="Import failed", code="GODOT_RUN_FAILED"
        )
        stream = io.StringIO()

        with patch("gdauto.export.pipeline.time.sleep") as mock_sleep:
            with pytest.raises(GdautoError, match="Import failed"):
                import_with_retry(
                    backend, Path("/project"), max_retries=3, status_stream=stream
                )

        assert backend.import_resources.call_count == 3
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)
        assert mock_sleep.call_count == 2

    def test_raises_last_error_after_exhaustion(self) -> None:
        """import_with_retry raises the last GdautoError after max_retries exhausted."""
        from gdauto.export.pipeline import import_with_retry

        backend = MagicMock()
        errors = [
            GdautoError(message="Fail 1", code="E1"),
            GdautoError(message="Fail 2", code="E2"),
            GdautoError(message="Fail 3", code="E3"),
        ]
        backend.import_resources.side_effect = errors
        stream = io.StringIO()

        with patch("gdauto.export.pipeline.time.sleep"):
            with pytest.raises(GdautoError, match="Fail 3"):
                import_with_retry(
                    backend, Path("/project"), max_retries=3, status_stream=stream
                )

    def test_writes_status_to_stream(self) -> None:
        """import_with_retry writes status messages to the provided stream."""
        from gdauto.export.pipeline import import_with_retry

        backend = MagicMock()
        backend.import_resources.return_value = MagicMock()
        stream = io.StringIO()

        import_with_retry(backend, Path("/project"), status_stream=stream)

        output = stream.getvalue()
        assert "Importing resources" in output
        assert "Import complete" in output

    def test_retry_status_messages(self) -> None:
        """import_with_retry writes retry messages on failure."""
        from gdauto.export.pipeline import import_with_retry

        backend = MagicMock()
        backend.import_resources.side_effect = [
            GdautoError(message="Fail", code="E"),
            MagicMock(),
        ]
        stream = io.StringIO()

        with patch("gdauto.export.pipeline.time.sleep"):
            import_with_retry(
                backend, Path("/project"), max_retries=3, status_stream=stream
            )

        output = stream.getvalue()
        assert "failed" in output.lower()
        assert "retrying" in output.lower()

    def test_exponential_backoff_delays(self) -> None:
        """import_with_retry uses exponential backoff: 1s, 2s, 4s."""
        from gdauto.export.pipeline import import_with_retry

        backend = MagicMock()
        backend.import_resources.side_effect = GdautoError(
            message="Fail", code="E"
        )
        stream = io.StringIO()

        with patch("gdauto.export.pipeline.time.sleep") as mock_sleep:
            with pytest.raises(GdautoError):
                import_with_retry(
                    backend,
                    Path("/project"),
                    max_retries=3,
                    base_delay=1.0,
                    status_stream=stream,
                )

        # 2 sleeps: after attempt 0 and attempt 1 (not after last attempt)
        calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert calls == [1.0, 2.0]


# ---------------------------------------------------------------------------
# check_import_cache tests
# ---------------------------------------------------------------------------


class TestCheckImportCache:
    """Tests for check_import_cache directory detection."""

    def test_returns_false_when_missing(self, tmp_path: Path) -> None:
        """check_import_cache returns False when .godot/imported/ does not exist."""
        from gdauto.export.pipeline import check_import_cache

        assert check_import_cache(tmp_path) is False

    def test_returns_true_when_exists(self, tmp_path: Path) -> None:
        """check_import_cache returns True when .godot/imported/ directory exists."""
        from gdauto.export.pipeline import check_import_cache

        (tmp_path / ".godot" / "imported").mkdir(parents=True)
        assert check_import_cache(tmp_path) is True


# ---------------------------------------------------------------------------
# export_project tests
# ---------------------------------------------------------------------------


class TestExportProject:
    """Tests for export_project with mode flags and auto-import."""

    def test_release_mode_flag(self, tmp_path: Path) -> None:
        """export_project with mode='release' calls backend.run with --export-release."""
        from gdauto.export.pipeline import export_project

        backend = MagicMock()
        # Pre-create import cache to skip auto-import
        (tmp_path / ".godot" / "imported").mkdir(parents=True)
        stream = io.StringIO()

        export_project(
            backend, tmp_path, "MyPreset", "/output/game.exe",
            mode="release", status_stream=stream,
        )

        backend.run.assert_called_once_with(
            ["--export-release", "MyPreset", "/output/game.exe"],
            project_path=tmp_path,
        )

    def test_debug_mode_flag(self, tmp_path: Path) -> None:
        """export_project with mode='debug' calls backend.run with --export-debug."""
        from gdauto.export.pipeline import export_project

        backend = MagicMock()
        (tmp_path / ".godot" / "imported").mkdir(parents=True)
        stream = io.StringIO()

        export_project(
            backend, tmp_path, "MyPreset", "/output/game.exe",
            mode="debug", status_stream=stream,
        )

        backend.run.assert_called_once_with(
            ["--export-debug", "MyPreset", "/output/game.exe"],
            project_path=tmp_path,
        )

    def test_pack_mode_flag(self, tmp_path: Path) -> None:
        """export_project with mode='pack' calls backend.run with --export-pack."""
        from gdauto.export.pipeline import export_project

        backend = MagicMock()
        (tmp_path / ".godot" / "imported").mkdir(parents=True)
        stream = io.StringIO()

        export_project(
            backend, tmp_path, "MyPreset", "/output/game.pck",
            mode="pack", status_stream=stream,
        )

        backend.run.assert_called_once_with(
            ["--export-pack", "MyPreset", "/output/game.pck"],
            project_path=tmp_path,
        )

    def test_auto_imports_when_cache_missing(self, tmp_path: Path) -> None:
        """export_project auto-imports when check_import_cache returns False (D-05)."""
        from gdauto.export.pipeline import export_project

        backend = MagicMock()
        stream = io.StringIO()

        with patch("gdauto.export.pipeline.time.sleep"):
            export_project(
                backend, tmp_path, "MyPreset", "/output/game.exe",
                mode="release", status_stream=stream,
            )

        # import_resources should be called (from auto-import)
        backend.import_resources.assert_called()
        # run should also be called (for the export itself)
        backend.run.assert_called_once()

    def test_no_auto_import_when_cache_exists(self, tmp_path: Path) -> None:
        """export_project does NOT auto-import when cache exists."""
        from gdauto.export.pipeline import export_project

        backend = MagicMock()
        (tmp_path / ".godot" / "imported").mkdir(parents=True)
        stream = io.StringIO()

        export_project(
            backend, tmp_path, "MyPreset", "/output/game.exe",
            mode="release", status_stream=stream,
        )

        backend.import_resources.assert_not_called()

    def test_writes_status_to_stderr(self, tmp_path: Path) -> None:
        """export_project writes stderr status lines (D-07)."""
        from gdauto.export.pipeline import export_project

        backend = MagicMock()
        (tmp_path / ".godot" / "imported").mkdir(parents=True)
        stream = io.StringIO()

        export_project(
            backend, tmp_path, "MyPreset", "/output/game.exe",
            mode="release", status_stream=stream,
        )

        output = stream.getvalue()
        assert "Exporting" in output
        assert "Done" in output
