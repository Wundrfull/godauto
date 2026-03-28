"""Import with retry and export orchestration for Godot headless mode.

Wraps GodotBackend to provide exponential backoff retry on import,
automatic import-before-export detection, and stderr status reporting.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import IO, Any

from gdauto.backend import GodotBackend
from gdauto.errors import GdautoError


def check_import_cache(project_path: Path) -> bool:
    """Check if Godot's import cache exists.

    Returns True when the .godot/imported/ directory is present,
    indicating that Godot has previously imported project resources.
    """
    return (project_path / ".godot" / "imported").exists()


def import_with_retry(
    backend: GodotBackend,
    project_path: Path,
    max_retries: int = 3,
    base_delay: float = 1.0,
    status_stream: IO[str] | Any | None = None,
) -> None:
    """Import resources with exponential backoff retry.

    Uses GodotBackend.import_resources() which already uses --quit-after
    (per D-06). Retries up to max_retries times with delays of
    base_delay * 2^attempt (1s, 2s, 4s).
    """
    if status_stream is None:
        status_stream = sys.stderr
    last_error: GdautoError | None = None
    for attempt in range(max_retries):
        try:
            status_stream.write(
                f"Importing resources (attempt {attempt + 1}/{max_retries})...\n"
            )
            backend.import_resources(project_path)
            status_stream.write("Import complete.\n")
            return
        except GdautoError as exc:
            last_error = exc
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                status_stream.write(
                    f"Import attempt {attempt + 1} failed, "
                    f"retrying in {delay:.0f}s...\n"
                )
                time.sleep(delay)
    if last_error is not None:
        raise last_error


def export_project(
    backend: GodotBackend,
    project_path: Path,
    preset: str,
    output_path: str,
    mode: str,
    auto_import: bool = True,
    status_stream: IO[str] | Any | None = None,
) -> None:
    """Export a Godot project using a named preset.

    mode must be "release", "debug", or "pack".
    If auto_import is True and import cache is missing, runs
    import_with_retry first (per D-05).
    """
    if status_stream is None:
        status_stream = sys.stderr

    # D-05: auto-import if cache missing
    if auto_import and not check_import_cache(project_path):
        status_stream.write("Import cache missing, running import first...\n")
        import_with_retry(backend, project_path, status_stream=status_stream)

    flag_map = {
        "release": "--export-release",
        "debug": "--export-debug",
        "pack": "--export-pack",
    }
    flag = flag_map[mode]

    status_stream.write(f"Exporting {mode}: {preset}...\n")
    backend.run(
        [flag, preset, output_path],
        project_path=project_path,
    )
    status_stream.write("Done.\n")
