"""Custom exception hierarchy with error codes and fix suggestions.

All gdauto errors inherit from GdautoError and carry a machine-readable
error code plus an optional human-readable fix suggestion.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GdautoError(Exception):
    """Base exception for all gdauto errors.

    Carries a structured error code and optional fix suggestion so that
    both --json output and human error messages can be generated from
    the same exception instance.
    """

    message: str
    code: str
    fix: str | None = field(default=None)

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serializable dict with error, code, and optional fix."""
        result: dict[str, str] = {"error": self.message, "code": self.code}
        if self.fix is not None:
            result["fix"] = self.fix
        return result


@dataclass
class ParseError(GdautoError):
    """Raised when a Godot file cannot be parsed."""


@dataclass
class ResourceNotFoundError(GdautoError):
    """Raised when a referenced file or resource does not exist."""


@dataclass
class GodotBinaryError(GdautoError):
    """Raised when the Godot binary is missing, wrong version, or fails."""


@dataclass
class ValidationError(GdautoError):
    """Raised when input data fails validation."""


@dataclass
class ProjectError(GdautoError):
    """Raised for project-level errors (not a Godot project, bad structure)."""
