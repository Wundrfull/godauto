"""Export preset management for Godot projects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rich_click as click

from auto_godot.errors import ProjectError
from auto_godot.output import emit, emit_error


@click.group("preset", invoke_without_command=True)
@click.pass_context
def preset(ctx: click.Context) -> None:
    """Manage export presets for Godot projects."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Platform templates
_PLATFORMS: dict[str, dict[str, str]] = {
    "windows": {
        "name": "Windows Desktop",
        "platform": "Windows Desktop",
        "export_path": "export/game.exe",
    },
    "linux": {
        "name": "Linux",
        "platform": "Linux",
        "export_path": "export/game.x86_64",
    },
    "macos": {
        "name": "macOS",
        "platform": "macOS",
        "export_path": "export/game.dmg",
    },
    "web": {
        "name": "Web",
        "platform": "Web",
        "export_path": "export/index.html",
    },
    "android": {
        "name": "Android",
        "platform": "Android",
        "export_path": "export/game.apk",
    },
}


def _build_preset_section(
    index: int,
    name: str,
    platform: str,
    export_path: str,
    runnable: bool,
    dedicated_server: bool,
) -> str:
    """Build an export preset section for export_presets.cfg."""
    lines = [
        f"[preset.{index}]",
        "",
        f'name="{name}"',
        f'platform="{platform}"',
        f"runnable={'true' if runnable else 'false'}",
        f"dedicated_server={'true' if dedicated_server else 'false'}",
        "custom_features=\"\"",
        f'export_path="{export_path}"',
        "encryption_include_filters=\"\"",
        "encryption_exclude_filters=\"\"",
        "encrypt_pck=false",
        "encrypt_directory=false",
        "script_export_mode=2",
        "",
        f"[preset.{index}.options]",
        "",
    ]
    return "\n".join(lines)


@preset.command("create")
@click.option(
    "--platform", "platforms", multiple=True, required=True,
    type=click.Choice(sorted(_PLATFORMS)),
    help="Target platform(s) to add presets for",
)
@click.option(
    "--runnable/--no-runnable", default=True,
    help="Mark preset as runnable (default: yes)",
)
@click.argument("project_path", default=".", type=click.Path())
@click.pass_context
def create(
    ctx: click.Context,
    platforms: tuple[str, ...],
    runnable: bool,
    project_path: str,
) -> None:
    """Create export_presets.cfg with platform presets.

    Examples:

      auto-godot preset create --platform windows --platform web

      auto-godot preset create --platform windows --platform linux --platform macos .
    """
    try:
        project_dir = Path(project_path)
        if not (project_dir / "project.godot").exists() and project_dir.is_dir():
            pass  # Allow creating presets even without project.godot for flexibility
        elif project_dir.is_file():
            project_dir = project_dir.parent

        preset_file = project_dir / "export_presets.cfg"

        sections: list[str] = []
        created_presets: list[dict[str, str]] = []

        for i, plat_key in enumerate(platforms):
            plat_info = _PLATFORMS[plat_key]
            section = _build_preset_section(
                index=i,
                name=plat_info["name"],
                platform=plat_info["platform"],
                export_path=plat_info["export_path"],
                runnable=runnable,
                dedicated_server=False,
            )
            sections.append(section)
            created_presets.append({
                "name": plat_info["name"],
                "platform": plat_info["platform"],
                "export_path": plat_info["export_path"],
            })

        content = "\n".join(sections) + "\n"
        preset_file.write_text(content, encoding="utf-8")

        data = {
            "created": True,
            "path": str(preset_file),
            "presets": created_presets,
            "count": len(created_presets),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            names = ", ".join(p["name"] for p in data["presets"])
            click.echo(f"Created {data['path']} with presets: {names}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


@preset.command("list")
@click.argument("project_path", default=".", type=click.Path())
@click.pass_context
def list_presets(
    ctx: click.Context,
    project_path: str,
) -> None:
    """List export presets in export_presets.cfg."""
    try:
        project_dir = Path(project_path)
        if project_dir.is_file():
            project_dir = project_dir.parent

        preset_file = project_dir / "export_presets.cfg"
        if not preset_file.exists():
            raise ProjectError(
                message="No export_presets.cfg found",
                code="NO_PRESETS",
                fix="Create presets with: auto-godot preset create --platform windows",
            )

        text = preset_file.read_text(encoding="utf-8")
        presets = _parse_presets(text)

        data = {
            "presets": presets,
            "count": len(presets),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            if data["count"] == 0:
                click.echo("No export presets configured.")
                return
            click.echo(f"Export presets ({data['count']}):")
            for p in data["presets"]:
                runnable_str = " [runnable]" if p.get("runnable") else ""
                click.echo(f"  {p['name']} ({p['platform']}){runnable_str}")
                if p.get("export_path"):
                    click.echo(f"    -> {p['export_path']}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


def _parse_presets(text: str) -> list[dict[str, Any]]:
    """Parse export_presets.cfg into a list of preset dicts."""
    return [
        {k: v for k, v in p.items() if k != "options"}
        for p in _parse_presets_full(text)
    ]


def _parse_presets_full(text: str) -> list[dict[str, Any]]:
    """Parse export_presets.cfg with all fields and options."""
    import re
    presets: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_options = False

    for line in text.splitlines():
        # New preset section
        match = re.match(r"\[preset\.(\d+)\]", line)
        if match:
            if current is not None:
                presets.append(current)
            current = {"index": int(match.group(1)), "options": {}}
            in_options = False
            continue

        # Options subsection
        if re.match(r"\[preset\.\d+\.options\]", line):
            in_options = True
            continue

        # Key=value
        if current is not None and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"')
            if in_options:
                current["options"][key] = value
            elif key == "runnable":
                current[key] = value == "true"
            elif key == "dedicated_server":
                current[key] = value == "true"
            else:
                current[key] = value

    if current is not None:
        presets.append(current)

    return presets


@preset.command("list-platforms")
@click.pass_context
def list_platforms(ctx: click.Context) -> None:
    """List available export platform templates."""
    platforms = [
        {"key": key, "name": info["name"], "export_path": info["export_path"]}
        for key, info in sorted(_PLATFORMS.items())
    ]

    data = {"platforms": platforms, "count": len(platforms)}

    def _human(data: dict[str, Any], verbose: bool = False) -> None:
        click.echo(f"Available platforms ({data['count']}):")
        for p in data["platforms"]:
            click.echo(f"  {p['key']:12s} {p['name']:20s} -> {p['export_path']}")

    emit(data, _human, ctx)


# ---------------------------------------------------------------------------
# preset inspect
# ---------------------------------------------------------------------------


def _load_presets_file(project_path: str) -> tuple[Path, list[dict[str, Any]]]:
    """Resolve project dir, read export_presets.cfg, return (dir, presets)."""
    project_dir = Path(project_path)
    if project_dir.is_file():
        project_dir = project_dir.parent
    preset_file = project_dir / "export_presets.cfg"
    if not preset_file.exists():
        raise ProjectError(
            message="No export_presets.cfg found",
            code="NO_PRESETS",
            fix="Create presets with: auto-godot preset create --platform windows",
        )
    presets = _parse_presets_full(preset_file.read_text(encoding="utf-8"))
    return project_dir, presets


def _find_preset(presets: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """Find a preset by name, raising ProjectError if not found."""
    match = next((p for p in presets if p.get("name") == name), None)
    if match is None:
        names = [p.get("name", "(unnamed)") for p in presets]
        raise ProjectError(
            message=f"Preset '{name}' not found",
            code="PRESET_NOT_FOUND",
            fix=f"Available presets: {', '.join(names)}",
        )
    return match


def _display_inspect(data: dict[str, Any], verbose: bool = False) -> None:
    """Human-readable output for preset inspect."""
    click.echo(f"Preset: {data.get('name', '(unnamed)')}")
    for key, val in data.items():
        if key == "options":
            continue
        click.echo(f"  {key}: {val}")
    opts = data.get("options", {})
    if opts:
        click.echo(f"  options ({len(opts)}):")
        for k, v in opts.items():
            click.echo(f"    {k} = {v}")


@preset.command("inspect")
@click.argument("preset_name")
@click.option(
    "--project", "project_path", default=".", type=click.Path(),
    help="Project directory (default: current directory).",
)
@click.pass_context
def inspect(ctx: click.Context, preset_name: str, project_path: str) -> None:
    """Inspect a specific export preset by name.

    Shows all configuration fields and options for the named preset.

    Examples:

      auto-godot preset inspect "Windows Desktop"

      auto-godot --json preset inspect "Linux" --project /path/to/project
    """
    try:
        _, presets = _load_presets_file(project_path)
        match = _find_preset(presets, preset_name)
        emit(match, _display_inspect, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# preset validate
# ---------------------------------------------------------------------------


def _check_duplicate_names(presets: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Check for duplicate preset names."""
    warnings: list[dict[str, str]] = []
    seen: list[str] = []
    for p in presets:
        name = p.get("name", "")
        if name in seen:
            warnings.append({
                "preset": name, "issue": "duplicate_name",
                "message": f"Duplicate preset name: '{name}'",
            })
        seen.append(name)
    return warnings


def _check_preset_fields(
    p: dict[str, Any], project_dir: Path, known_platforms: set[str],
) -> list[dict[str, str]]:
    """Validate a single preset's fields."""
    warnings: list[dict[str, str]] = []
    name = p.get("name", f"preset.{p.get('index', '?')}")
    if not p.get("export_path"):
        warnings.append({
            "preset": name, "issue": "missing_export_path",
            "message": "No export_path configured",
        })
    platform = p.get("platform", "")
    if platform and platform not in known_platforms:
        warnings.append({
            "preset": name, "issue": "unknown_platform",
            "message": f"Unrecognized platform: '{platform}'",
        })
    export_path = p.get("export_path", "")
    if export_path and not (project_dir / export_path).parent.exists():
        warnings.append({
            "preset": name, "issue": "missing_export_dir",
            "message": f"Export directory does not exist: {(project_dir / export_path).parent}",
        })
    return warnings


def _display_validate(data: dict[str, Any], verbose: bool = False) -> None:
    """Human-readable output for preset validate."""
    count = data["preset_count"]
    if data["valid"]:
        click.echo(f"All {count} preset(s) valid.")
        return
    click.echo(f"Found {data['warning_count']} issue(s) in {count} preset(s):")
    for w in data["warnings"]:
        click.echo(f"  [{w['preset']}] {w['message']}")


@preset.command("validate")
@click.argument("project_path", default=".", type=click.Path())
@click.pass_context
def validate(ctx: click.Context, project_path: str) -> None:
    """Validate export presets for common issues.

    Checks: duplicate names, missing export paths, unrecognized
    platforms, and whether export directories exist.

    Examples:

      auto-godot preset validate

      auto-godot --json preset validate /path/to/project
    """
    try:
        project_dir, presets = _load_presets_file(project_path)
        known_platforms = {info["platform"] for info in _PLATFORMS.values()}
        warnings = _check_duplicate_names(presets)
        for p in presets:
            warnings.extend(_check_preset_fields(p, project_dir, known_platforms))
        data = {
            "valid": len(warnings) == 0,
            "preset_count": len(presets),
            "warning_count": len(warnings),
            "warnings": warnings,
        }
        emit(data, _display_validate, ctx)
        if warnings:
            ctx.exit(1)
    except ProjectError as exc:
        emit_error(exc, ctx)
