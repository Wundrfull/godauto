"""JSON vs human output abstraction.

Provides emit() for normal output and emit_error() for error output,
switching between JSON and human-readable formats based on GlobalConfig.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    import click

    from auto_godot.errors import AutoGodotError



@dataclass
class GlobalConfig:
    """Global configuration passed through Click context.

    Stores the state of global flags so that all commands can check
    output mode, verbosity, and Godot binary location.
    """

    json_mode: bool = field(default=False)
    verbose: bool = field(default=False)
    quiet: bool = field(default=False)
    dry_run: bool = field(default=False)
    dry_run_acknowledged: bool = field(default=False)
    godot_path: str | None = field(default=None)


def emit(
    data: dict[str, Any],
    human_fn: Callable[..., None],
    ctx: click.Context | Any,
) -> None:
    """Emit output as JSON or human-readable format.

    In json_mode, serializes data to stdout as JSON. Otherwise, calls
    human_fn unless quiet mode is active.
    """
    config: GlobalConfig = ctx.obj
    if config.json_mode:
        sys.stdout.write(json.dumps(data, indent=2) + "\n")
    elif not config.quiet:
        human_fn(data, verbose=config.verbose)


def maybe_write(
    ctx: click.Context | Any,
    path: Any,
    content: str,
) -> bool:
    """Write content to path unless dry_run is active.

    Returns True if the file was written, False if skipped (dry-run).
    In dry-run mode, emits a preview message to stderr.
    """
    from pathlib import Path as _Path

    config: GlobalConfig = ctx.obj
    file_path = _Path(path)
    if config.dry_run:
        exists = file_path.exists()
        action = "overwrite" if exists else "create"
        if not config.json_mode and not config.quiet:
            sys.stderr.write(
                f"[dry-run] Would {action}: {file_path} "
                f"({len(content)} bytes)\n"
            )
        config.dry_run_acknowledged = True
        return False
    file_path.write_text(content, encoding="utf-8")
    return True


def emit_error(error: AutoGodotError, ctx: click.Context | Any) -> None:
    """Emit an error as JSON or human-readable format to stderr.

    In json_mode, writes the error dict as JSON to stderr.
    In human mode, writes colored error text with optional fix suggestion.
    Always signals a non-zero exit via ctx.exit(1).
    """
    config: GlobalConfig = ctx.obj
    if config.json_mode:
        sys.stderr.write(json.dumps(error.to_dict()) + "\n")
    else:
        sys.stderr.write(f"Error: {error.message}\n")
        if error.fix is not None:
            sys.stderr.write(f"Fix: {error.fix}\n")
    ctx.exit(1)
