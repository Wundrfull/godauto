"""PostToolUse hook: check auto-godot command output for known error patterns.

Fires after every Bash command. Early-exits on non-auto-godot commands
to avoid performance impact. Checks stdout/stderr for patterns that
indicate bugs, regressions, or common mistakes.

Returns JSON with decision="block" (advisory warning to Claude) when
issues are detected, or exits 0 silently on success.
"""

from __future__ import annotations

import json
import re
import sys


# Known error patterns: (compiled_regex, severity, message_template)
# severity: "warn" = advisory, "error" = strong recommendation to fix
PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # ExtResource serialization bug: quotes around the whole expression
    (
        re.compile(r'"ExtResource\(\\"'),
        "error",
        "Double-quoted ExtResource detected in output. "
        "This is a serialization bug: ExtResource refs must use bare syntax "
        "like ExtResource(\"1_id\"), not wrapped in extra quotes.",
    ),
    # res:// path without directory structure (just filename)
    (
        re.compile(r'res://[^/\s"]+\.(png|tres|tscn|gd)\b(?!/)'),
        "warn",
        "res:// path appears to reference a file at project root. "
        "Assets should be in subdirectories: res://assets/, res://scenes/, res://scripts/.",
    ),
    # class_name collision with autoload
    (
        re.compile(r"class_name.*already in use", re.IGNORECASE),
        "error",
        "class_name conflict detected. A class_name cannot match an autoload "
        "singleton name. Use 'auto-godot project list-autoloads' to check.",
    ),
    # Godot runtime errors from headless mode
    (
        re.compile(r"ERROR:.*Failed to load resource"),
        "error",
        "Godot failed to load a resource. Run 'auto-godot import' to sync "
        ".import files, then retry.",
    ),
    (
        re.compile(r"ERROR:.*Invalid UID"),
        "error",
        "Invalid UID detected. Delete the .import file for the affected "
        "resource and run 'auto-godot import' to regenerate.",
    ),
    (
        re.compile(r"ERROR:.*Cannot instance scene"),
        "error",
        "Cannot instance scene. Check for circular instance references "
        "or missing .tscn files.",
    ),
    # Shell expansion of dollar signs (common mistake)
    (
        re.compile(r'--property\s+"[^"]*\$'),
        "warn",
        "Property value may have shell-expanded a $ variable. "
        "Use single quotes for --property values containing $: "
        "--property 'text=Buy ($50)'",
    ),
]


def check_output(tool_output: str) -> list[dict[str, str]]:
    """Check command output against known error patterns."""
    findings: list[dict[str, str]] = []
    for pattern, severity, message in PATTERNS:
        if pattern.search(tool_output):
            findings.append({"severity": severity, "message": message})
    return findings


def main() -> None:
    """Read hook input from stdin, check output, emit warnings."""
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    # Only process Bash commands
    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    # Only process auto-godot commands
    command = hook_input.get("tool_input", {}).get("command", "")
    if "auto-godot" not in command and "godot" not in command:
        sys.exit(0)

    # Combine stdout and stderr for pattern matching
    response = hook_input.get("tool_response", {})
    stdout = response.get("stdout", "")
    stderr = response.get("stderr", "")
    combined = f"{stdout}\n{stderr}"

    # Also check the command itself (for shell expansion patterns)
    combined = f"{command}\n{combined}"

    findings = check_output(combined)

    if not findings:
        sys.exit(0)

    # Build warning message
    errors = [f for f in findings if f["severity"] == "error"]
    warnings = [f for f in findings if f["severity"] == "warn"]

    lines: list[str] = []
    if errors:
        lines.append(f"auto-godot output check: {len(errors)} error(s) detected")
        for f in errors:
            lines.append(f"  ERROR: {f['message']}")
    if warnings:
        lines.append(f"auto-godot output check: {len(warnings)} warning(s) detected")
        for f in warnings:
            lines.append(f"  WARN: {f['message']}")

    # Emit as advisory block (PostToolUse cannot prevent execution,
    # but "block" signals Claude should address the issue)
    result = {
        "decision": "block",
        "reason": "\n".join(lines),
    }
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
