"""Godot binary wrapper with discovery, version validation, and subprocess management.

Handles the lifecycle of interacting with the Godot engine binary:
finding it (explicit path > GODOT_PATH env > PATH), validating its
version (>= 4.5), and invoking it in headless mode with structured
error reporting.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from auto_godot.errors import AutoGodotError, GodotBinaryError

if TYPE_CHECKING:
    from pathlib import Path

# Minimum supported Godot version
_MIN_MAJOR = 4
_MIN_MINOR = 5

# Regex to extract major.minor from version string like "4.5.2.stable.official.abc1234"
_VERSION_RE = re.compile(r"(\d+)\.(\d+)")


@dataclass
class GodotBackend:
    """Wrapper for Godot binary invocations.

    Discovers the Godot binary via explicit path, GODOT_PATH env var,
    or system PATH. Validates version >= 4.5 on first use and caches
    the result. All invocations use --headless mode.
    """

    binary_path: str | None = None
    timeout: int = 120
    _version: str | None = field(default=None, init=False, repr=False)

    def ensure_binary(self) -> str:
        """Discover and validate the Godot binary, returning its path.

        Discovery order: (1) explicit binary_path, (2) GODOT_PATH env
        var, (3) shutil.which('godot'). Raises GodotBinaryError if not
        found. Validates version >= 4.5 on first call and caches the
        result for subsequent calls.
        """
        path = self._discover_path()
        if self._version is None:
            self._check_version(path)
        return path

    def _discover_path(self) -> str:
        """Find the Godot binary using the priority chain."""
        # Priority 1: explicit binary_path
        if self.binary_path is not None:
            return self.binary_path

        # Priority 2: GODOT_PATH environment variable
        env_path = os.environ.get("GODOT_PATH")
        if env_path:
            self.binary_path = env_path
            return env_path

        # Priority 3: system PATH via shutil.which
        which_path = shutil.which("godot")
        if which_path:
            self.binary_path = which_path
            return which_path

        raise GodotBinaryError(
            message="Godot binary not found",
            code="GODOT_NOT_FOUND",
            fix=(
                "Install Godot 4.5+ and add it to PATH, "
                "or set the GODOT_PATH environment variable, "
                "or pass --godot-path <path>"
            ),
        )

    def _check_version(self, binary: str) -> str:
        """Run the binary with --version and validate the output.

        Requires major >= 4 and minor >= 5. Caches the version string
        on success. Raises GodotBinaryError on failure.
        """
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        version_str = result.stdout.strip()
        match = _VERSION_RE.search(version_str)
        if not match:
            raise GodotBinaryError(
                message=f"Could not parse Godot version from: {version_str!r}",
                code="GODOT_VERSION_PARSE",
                fix="Ensure the Godot binary outputs a valid version string",
            )

        major = int(match.group(1))
        minor = int(match.group(2))

        if major < _MIN_MAJOR or (major == _MIN_MAJOR and minor < _MIN_MINOR):
            raise GodotBinaryError(
                message=f"Godot {version_str} is too old (requires >= 4.5)",
                code="GODOT_VERSION_TOO_OLD",
                fix="Update Godot to version 4.5 or later",
            )

        self._version = version_str
        return version_str

    def run(
        self,
        args: list[str],
        project_path: Path | None = None,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Invoke Godot in headless mode with the given arguments.

        Calls ensure_binary() first to validate the binary. Builds the
        command as [binary, '--headless'] + args, optionally appending
        --path for project-scoped operations.

        Raises AutoGodotError with code GODOT_RUN_FAILED on non-zero exit.
        """
        binary = self.ensure_binary()
        cmd = [binary, "--headless"] + args

        if project_path is not None:
            cmd.extend(["--path", str(project_path)])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout or self.timeout,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else "Unknown error"
            raise AutoGodotError(
                message=f"Godot command failed: {stderr}",
                code="GODOT_RUN_FAILED",
                fix=f"Check the Godot output: {stderr}",
            )

        return result

    def launch_game(
        self,
        project_path: Path,
        port: int = 6007,
        scene: str | None = None,
    ) -> subprocess.Popen[str]:
        """Launch a Godot game with remote debug connection.

        Uses Popen (non-blocking) instead of run (blocking) so the
        game runs as a child process while auto-godot manages the TCP
        session. Does NOT use --headless; the game needs its window.
        """
        binary = self.ensure_binary()
        cmd = [
            binary,
            "--path", str(project_path),
            "--remote-debug", f"tcp://127.0.0.1:{port}",
        ]
        if scene is not None:
            cmd.append(scene)
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def check_only(
        self, project_path: Path
    ) -> subprocess.CompletedProcess[str]:
        """Run Godot's --check-only validation on a project."""
        return self.run(["--check-only"], project_path=project_path)

    def import_resources(
        self, project_path: Path, quit_after: int = 30
    ) -> subprocess.CompletedProcess[str]:
        """Run Godot's resource import on a project.

        Uses --quit-after instead of --quit to avoid the race condition
        where Godot may exit before imports complete.
        """
        return self.run(
            ["--import", "--quit-after", str(quit_after)],
            project_path=project_path,
        )
