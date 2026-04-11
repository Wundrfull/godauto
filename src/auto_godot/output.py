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


def check_path(path: str, ctx: click.Context | Any, label: str = "file") -> bool:
    """Verify a file exists, emitting a --json-safe error if not.

    Returns True when the path exists. When it does not, emits the
    error through emit_error (respecting --json) and returns False.
    Commands should ``return`` when this returns False.
    """
    from pathlib import Path as _Path

    from auto_godot.errors import ProjectError

    if not _Path(path).exists():
        emit_error(
            ProjectError(
                message=f"{label.title()} not found: {path}",
                code="FILE_NOT_FOUND",
                fix=f"Check that the {label} path is correct and the file exists",
            ),
            ctx,
        )
        return False
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
