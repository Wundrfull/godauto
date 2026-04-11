"""Session file persistence for .auto-godot/session.json.

Manages writing, reading, and cleaning up the session file that tracks
active debugger connections. Also ensures .auto-godot/ is in .gitignore
to prevent committing session state (D-04).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from auto_godot.debugger.models import SessionInfo

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_AUTO_GODOT_DIR = ".auto-godot"
_SESSION_FILE = "session.json"
_GITIGNORE_ENTRY = ".auto-godot/"


def write_session_file(project_path: Path, info: SessionInfo) -> None:
    """Write session info to .auto-godot/session.json.

    Creates the .auto-godot/ directory if needed and ensures .auto-godot/
    is listed in .gitignore.
    """
    auto_godot_dir = project_path / _AUTO_GODOT_DIR
    auto_godot_dir.mkdir(exist_ok=True)
    session_path = auto_godot_dir / _SESSION_FILE
    session_path.write_text(json.dumps(info.to_dict(), indent=2) + "\n")
    _ensure_gitignore(project_path)


def read_session_file(project_path: Path) -> SessionInfo | None:
    """Read session info from .auto-godot/session.json.

    Returns None if the file does not exist or contains invalid data.
    """
    session_path = project_path / _AUTO_GODOT_DIR / _SESSION_FILE
    if not session_path.exists():
        return None
    try:
        data = json.loads(session_path.read_text())
        return SessionInfo.from_dict(data)
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        logger.debug("Invalid session file, ignoring: %s", exc)
        return None


def cleanup_session(project_path: Path) -> None:
    """Remove session.json and .auto-godot/ directory if empty."""
    session_path = project_path / _AUTO_GODOT_DIR / _SESSION_FILE
    if session_path.exists():
        session_path.unlink()
    auto_godot_dir = project_path / _AUTO_GODOT_DIR
    if auto_godot_dir.exists() and not any(auto_godot_dir.iterdir()):
        auto_godot_dir.rmdir()


def _ensure_gitignore(project_path: Path) -> None:
    """Ensure .auto-godot/ is listed in .gitignore.

    Creates .gitignore if it does not exist. Appends .auto-godot/ if not
    already present. Adds a leading newline if the file does not end
    with one.
    """
    gitignore_path = project_path / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(_GITIGNORE_ENTRY + "\n")
        return
    content = gitignore_path.read_text()
    # Check if already present (line-level match)
    for line in content.splitlines():
        if line.strip() == _GITIGNORE_ENTRY:
            return
    # Append entry, ensuring a newline separator
    prefix = "" if content.endswith("\n") else "\n"
    gitignore_path.write_text(content + prefix + _GITIGNORE_ENTRY + "\n")
