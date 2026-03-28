"""Manage Godot projects (info, validate, create)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import rich_click as click
from rich.console import Console
from rich.table import Table

from gdauto.backend import GodotBackend
from gdauto.errors import GodotBinaryError, ProjectError
from gdauto.formats.project_cfg import parse_project_config
from gdauto.formats.tscn import parse_tscn_file
from gdauto.formats.tres import parse_tres_file
from gdauto.output import GlobalConfig, emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def project(ctx: click.Context) -> None:
    """Manage Godot projects (info, validate, create)."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# project info
# ---------------------------------------------------------------------------


def _find_project_godot(path: str) -> Path:
    """Locate project.godot in the given path, raising on failure."""
    p = Path(path)
    if p.is_file() and p.name == "project.godot":
        return p
    candidate = p / "project.godot"
    if candidate.is_file():
        return candidate
    raise ProjectError(
        message=f"No project.godot found in {path}",
        code="PROJECT_NOT_FOUND",
        fix="Ensure the path points to a Godot project directory containing project.godot",
    )


def _strip_quotes(value: str) -> str:
    """Strip surrounding double quotes from a value."""
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def _extract_info(config_text: str) -> dict[str, Any]:
    """Parse project.godot text and extract project metadata."""
    cfg = parse_project_config(config_text)

    name = cfg.get_value("application", "config/name") or ""
    name = _strip_quotes(name)

    config_version = cfg.get_global("config_version") or ""

    main_scene = cfg.get_value("application", "run/main_scene") or ""
    main_scene = _strip_quotes(main_scene)

    icon = cfg.get_value("application", "config/icon") or ""
    icon = _strip_quotes(icon)

    features = cfg.get_value("application", "config/features") or ""

    # Extract autoloads
    autoloads: dict[str, str] = {}
    autoload_section = cfg.sections.get("autoload")
    if autoload_section:
        for key, val in autoload_section:
            clean_val = _strip_quotes(val)
            autoloads[key] = clean_val

    # Extract display settings
    display: dict[str, str] = {}
    vw = cfg.get_value("display", "window/size/viewport_width")
    if vw:
        display["viewport_width"] = vw
    vh = cfg.get_value("display", "window/size/viewport_height")
    if vh:
        display["viewport_height"] = vh
    stretch = cfg.get_value("display", "window/stretch/mode")
    if stretch:
        display["stretch_mode"] = _strip_quotes(stretch)

    return {
        "name": name,
        "config_version": config_version,
        "main_scene": main_scene,
        "icon": icon,
        "features": features,
        "autoloads": autoloads,
        "display": display,
    }


def _display_project_info_human(data: dict[str, Any], verbose: bool = False) -> None:
    """Display project info in human-readable format."""
    console = Console()
    console.print(f"[bold]Project:[/bold] {data['name']}")
    console.print(f"  Config version: {data['config_version']}")
    console.print(f"  Main scene: {data['main_scene']}")
    console.print(f"  Icon: {data['icon']}")
    console.print(f"  Features: {data['features']}")

    if data["autoloads"]:
        console.print("\n[bold]Autoloads:[/bold]")
        for name, path in data["autoloads"].items():
            console.print(f"  {name}: {path}")

    if data["display"]:
        console.print("\n[bold]Display:[/bold]")
        for key, val in data["display"].items():
            console.print(f"  {key}: {val}")

    if verbose:
        console.print("\n[bold]Sections and keys:[/bold]")
        console.print(f"  (extra detail shown in verbose mode)")


@project.command()
@click.argument("path", default=".", type=click.Path())
@click.pass_context
def info(ctx: click.Context, path: str) -> None:
    """Show project metadata (name, version, autoloads, settings)."""
    try:
        if not Path(path).exists():
            raise ProjectError(
                message=f"Path does not exist: {path}",
                code="PROJECT_NOT_FOUND",
                fix="Ensure the path points to a Godot project directory containing project.godot",
            )
        project_godot = _find_project_godot(path)
        config_text = project_godot.read_text(encoding="utf-8")
        data = _extract_info(config_text)
        emit(data, _display_project_info_human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# project validate
# ---------------------------------------------------------------------------


def _collect_res_paths(project_root: Path) -> tuple[list[str], set[str]]:
    """Walk .tscn/.tres files and collect all res:// references.

    Returns (list of missing resource paths, set of all referenced res:// paths).
    """
    all_refs: set[str] = set()
    missing: list[str] = []

    for ext in ("*.tscn", "*.tres"):
        for fpath in project_root.rglob(ext):
            try:
                text = fpath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            # Extract res:// paths from the raw text
            _extract_res_refs(text, all_refs)

    # Check each ref against the filesystem
    for ref in sorted(all_refs):
        rel = ref.replace("res://", "", 1)
        resolved = project_root / rel
        if not resolved.exists():
            missing.append(ref)

    return missing, all_refs


def _extract_res_refs(text: str, refs: set[str]) -> None:
    """Extract all res:// paths from file text into the refs set."""
    import re
    for match in re.finditer(r'res://[^\s"\')\]]+', text):
        refs.add(match.group(0))


def _collect_orphan_scripts(
    project_root: Path, all_refs: set[str]
) -> list[str]:
    """Find .gd files not referenced by any .tscn/.tres file."""
    orphans: list[str] = []
    for gd_file in project_root.rglob("*.gd"):
        rel_path = gd_file.relative_to(project_root).as_posix()
        res_path = f"res://{rel_path}"
        # Also check with * prefix (autoload singletons)
        if res_path not in all_refs and f"*{res_path}" not in all_refs:
            orphans.append(res_path)
    return orphans


def _display_validation_report_human(
    data: dict[str, Any], verbose: bool = False
) -> None:
    """Display validation report in human-readable format."""
    console = Console()
    console.print(f"[bold]Validation Report[/bold]")
    console.print(f"  Files scanned: {data['files_scanned']}")
    console.print(f"  Issues found: {data['issues_found']}")

    if data["missing_resources"]:
        console.print("\n[bold red]Missing resources:[/bold red]")
        for res in data["missing_resources"]:
            console.print(f"  {res}")

    if data.get("orphan_scripts"):
        console.print("\n[bold yellow]Orphan scripts:[/bold yellow]")
        for script in data["orphan_scripts"]:
            console.print(f"  {script}")

    if data.get("script_errors"):
        console.print("\n[bold red]Script errors:[/bold red]")
        for err_line in data["script_errors"]:
            console.print(f"  {err_line}")

    if data["issues_found"] == 0:
        console.print("\n[green]All checks passed.[/green]")


@project.command()
@click.argument("path", default=".", type=click.Path())
@click.option(
    "--check-only", is_flag=True,
    help="Run Godot --check-only for script syntax validation",
)
@click.pass_context
def validate(ctx: click.Context, path: str, check_only: bool) -> None:
    """Validate project structure: check res:// paths, detect missing resources."""
    try:
        if not Path(path).exists():
            raise ProjectError(
                message=f"Path does not exist: {path}",
                code="PROJECT_NOT_FOUND",
                fix="Ensure the path points to a Godot project directory",
            )
        project_godot = _find_project_godot(path)
        project_root = project_godot.parent

        missing, all_refs = _collect_res_paths(project_root)
        orphans = _collect_orphan_scripts(project_root, all_refs)

        # Count files scanned
        scanned = sum(
            1 for _ in project_root.rglob("*.tscn")
        ) + sum(
            1 for _ in project_root.rglob("*.tres")
        )

        report: dict[str, Any] = {
            "missing_resources": missing,
            "broken_references": missing,  # alias for compatibility
            "orphan_scripts": orphans,
            "files_scanned": scanned,
            "issues_found": len(missing),
        }

        # Optional Godot --check-only
        if check_only:
            _run_check_only(ctx, project_root, report)

        emit(report, _display_validation_report_human, ctx)

        if report["issues_found"] > 0:
            ctx.exit(1)
    except ProjectError as exc:
        emit_error(exc, ctx)


def _run_check_only(
    ctx: click.Context,
    project_root: Path,
    report: dict[str, Any],
) -> None:
    """Run Godot --check-only and add script errors to report."""
    config: GlobalConfig = ctx.obj
    try:
        backend = GodotBackend(binary_path=config.godot_path)
        result = backend.check_only(project_root)
        # Parse stderr for errors
        errors: list[str] = []
        if result.stderr:
            for line in result.stderr.splitlines():
                if "error" in line.lower():
                    errors.append(line.strip())
        report["script_errors"] = errors
        report["issues_found"] += len(errors)
    except GodotBinaryError:
        # Godot not available; continue with file-level checks only
        report["script_errors"] = []


# ---------------------------------------------------------------------------
# project create
# ---------------------------------------------------------------------------

_GITIGNORE_CONTENT = """\
# Godot 4+ specific ignores
.godot/

# Godot-specific ignores
*.import
export_presets.cfg

# Mono-specific ignores
.mono/
data_*/
mono_crash.*.txt
"""

_ICON_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">
  <rect width="128" height="128" fill="#478cbf"/>
</svg>
"""


def _display_create_human(data: dict[str, Any], verbose: bool = False) -> None:
    """Display project creation result in human-readable format."""
    console = Console()
    console.print(f"[green]Created project at:[/green] {data['path']}")
    if verbose:
        console.print("[bold]Files created:[/bold]")
        for f in data["files"]:
            console.print(f"  {f}")


@project.command()
@click.argument("name")
@click.option(
    "-o", "--output", default=".",
    type=click.Path(), help="Parent directory for new project",
)
@click.pass_context
def create(ctx: click.Context, name: str, output: str) -> None:
    """Scaffold a new Godot project with recommended structure."""
    try:
        target = Path(output) / name
        if target.exists():
            raise ProjectError(
                message=f"Directory already exists: {target}",
                code="PROJECT_EXISTS",
                fix="Choose a different name or remove the existing directory",
            )

        created_files = _scaffold_project(target, name)

        data = {
            "created": True,
            "path": str(target.resolve()),
            "files": created_files,
        }
        emit(data, _display_create_human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


def _scaffold_project(target: Path, name: str) -> list[str]:
    """Create project directory structure and files."""
    created: list[str] = []

    # Create directories
    target.mkdir(parents=True)
    for subdir in ("scenes", "scripts", "assets", "sprites", "tilesets"):
        (target / subdir).mkdir()

    # project.godot
    project_godot = target / "project.godot"
    project_godot.write_text(
        f'; Engine configuration file.\n'
        f'\n'
        f'config_version=5\n'
        f'\n'
        f'[application]\n'
        f'\n'
        f'config/name="{name}"\n'
        f'run/main_scene="res://scenes/main.tscn"\n'
        f'config/features=PackedStringArray("4.5", "GL Compatibility")\n'
        f'config/icon="res://icon.svg"\n',
        encoding="utf-8",
    )
    created.append("project.godot")

    # main.tscn
    main_tscn = target / "scenes" / "main.tscn"
    main_tscn.write_text(
        '[gd_scene format=3]\n'
        '\n'
        '[node name="Main" type="Node2D"]\n',
        encoding="utf-8",
    )
    created.append("scenes/main.tscn")

    # icon.svg
    icon = target / "icon.svg"
    icon.write_text(_ICON_SVG, encoding="utf-8")
    created.append("icon.svg")

    # .gitignore
    gitignore = target / ".gitignore"
    gitignore.write_text(_GITIGNORE_CONTENT, encoding="utf-8")
    created.append(".gitignore")

    # .gdignore (empty, for future use)
    gdignore = target / ".gdignore"
    gdignore.write_text("", encoding="utf-8")
    created.append(".gdignore")

    return created
