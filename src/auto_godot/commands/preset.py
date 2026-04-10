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
    import re
    presets: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in text.splitlines():
        # New preset section
        match = re.match(r'\[preset\.(\d+)\]', line)
        if match:
            if current is not None:
                presets.append(current)
            current = {"index": int(match.group(1))}
            continue

        # Options subsection (skip)
        if re.match(r'\[preset\.\d+\.options\]', line):
            continue

        # Key=value in current preset
        if current is not None and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"')
            if key in ("name", "platform", "export_path"):
                current[key] = value
            elif key == "runnable":
                current[key] = value == "true"

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
