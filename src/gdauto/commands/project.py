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
from gdauto.formats.project_cfg import parse_project_config, serialize_project_config
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


def _extract_godot_version(features: str) -> str | None:
    """Extract engine version from features PackedStringArray.

    The features string looks like: PackedStringArray("4.5", "GL Compatibility")
    The first quoted element that looks like a version number is the engine version.
    """
    import re
    match = re.search(r'PackedStringArray\("([0-9]+\.[0-9]+[^"]*)"', features)
    if match:
        return match.group(1)
    return None


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

    # Extract autoloads, stripping the * singleton prefix for clean paths
    autoloads: dict[str, str] = {}
    autoload_section = cfg.sections.get("autoload")
    if autoload_section:
        for key, val in autoload_section:
            clean_val = _strip_quotes(val).lstrip("*")
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

    godot_version = _extract_godot_version(features)

    return {
        "name": name,
        "config_version": config_version,
        "godot_version": godot_version,
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
    if data.get("godot_version"):
        console.print(f"  Godot version: {data['godot_version']}")
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


def _check_project_godot_refs(
    cfg: Any, project_root: Path, missing: list[str]
) -> None:
    """Check res:// paths referenced in project.godot against the filesystem."""
    # Check main_scene and icon from [application]
    for key in ("run/main_scene", "config/icon"):
        val = cfg.get_value("application", key)
        if val is None:
            continue
        clean = _strip_quotes(val)
        if clean.startswith("res://"):
            rel = clean.replace("res://", "", 1)
            if not (project_root / rel).exists() and clean not in missing:
                missing.append(clean)

    # Check autoload paths
    autoload_section = cfg.sections.get("autoload")
    if autoload_section:
        for _key, val in autoload_section:
            clean = _strip_quotes(val).lstrip("*")
            if clean.startswith("res://"):
                rel = clean.replace("res://", "", 1)
                if not (project_root / rel).exists() and clean not in missing:
                    missing.append(clean)


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

        # Also check resource references inside project.godot
        config_text = project_godot.read_text(encoding="utf-8")
        cfg = parse_project_config(config_text)
        _check_project_godot_refs(cfg, project_root, missing)

        # Include autoload scripts so they are not reported as orphans
        autoload_section = cfg.sections.get("autoload")
        if autoload_section:
            for _key, val in autoload_section:
                clean = _strip_quotes(val).lstrip("*")
                if clean.startswith("res://"):
                    all_refs.add(clean)

        orphans = _collect_orphan_scripts(project_root, all_refs)

        # Count files scanned (project.godot counts as +1)
        scanned = sum(
            1 for _ in project_root.rglob("*.tscn")
        ) + sum(
            1 for _ in project_root.rglob("*.tres")
        ) + 1

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
    # Check if any .gd scripts exist
    gd_files = list(project_root.rglob("*.gd"))
    if not gd_files:
        report["script_errors"] = []
        report["godot_check_skipped"] = True
        report["godot_check_skip_reason"] = "no .gd scripts found"
        config: GlobalConfig = ctx.obj
        if not config.json_mode and not config.quiet:
            click.echo(
                "Note: --check-only requested but no .gd scripts found; "
                "Godot syntax check skipped",
                err=True,
            )
        return

    config = ctx.obj
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
        report["godot_check_skipped"] = False
        report["issues_found"] += len(errors)
    except GodotBinaryError:
        # Godot not available; continue with file-level checks only
        report["script_errors"] = []
        report["godot_check_skipped"] = True
        report["godot_check_skip_reason"] = "Godot binary not available"
        if not config.json_mode and not config.quiet:
            click.echo(
                "Note: --check-only requested but Godot binary not found; "
                "syntax check skipped",
                err=True,
            )


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


# ---------------------------------------------------------------------------
# project add-autoload
# ---------------------------------------------------------------------------


@project.command("add-autoload")
@click.option(
    "--name", required=True,
    help="Autoload singleton name (e.g., GameState)",
)
@click.option(
    "--path", "script_path", required=True,
    help="Godot res:// path to the script (e.g., res://scripts/game_state.gd)",
)
@click.option(
    "--no-singleton", is_flag=True, default=False,
    help="Register without the singleton '*' prefix",
)
@click.argument("project_path", default=".", type=click.Path())
@click.pass_context
def add_autoload(
    ctx: click.Context,
    name: str,
    script_path: str,
    no_singleton: bool,
    project_path: str,
) -> None:
    """Register an autoload singleton in project.godot."""
    try:
        project_godot = _find_project_godot(project_path)
        config_text = project_godot.read_text(encoding="utf-8")
        cfg = parse_project_config(config_text)

        # Check for duplicates
        existing = cfg.sections.get("autoload", [])
        for key, _val in existing:
            if key == name:
                raise ProjectError(
                    message=f"Autoload '{name}' already exists",
                    code="AUTOLOAD_EXISTS",
                    fix=f"Remove the existing autoload or choose a different name",
                )

        # Build the value with or without singleton prefix
        prefix = "" if no_singleton else "*"
        value = f'"{prefix}{script_path}"'

        # Add autoload section if it doesn't exist, then append the entry
        _add_autoload_entry(project_godot, name, value)

        data = {
            "added": True,
            "name": name,
            "path": script_path,
            "singleton": not no_singleton,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Registered autoload '{data['name']}' -> {data['path']}"
                f"{' (singleton)' if data['singleton'] else ''}"
            )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


def _add_autoload_entry(
    project_godot: Path, name: str, value: str
) -> None:
    """Append an autoload entry to project.godot, creating the section if needed."""
    _add_section_entry(project_godot, "autoload", name, value)


def _add_section_entry(
    project_godot: Path, section: str, name: str, value: str
) -> None:
    """Append a key=value entry to a section, creating the section if needed."""
    text = project_godot.read_text(encoding="utf-8")
    lines = text.split("\n")

    section_idx = None
    for i, line in enumerate(lines):
        if line.strip() == f"[{section}]":
            section_idx = i
            break

    entry_line = f"{name}={value}"

    if section_idx is not None:
        insert_idx = section_idx + 1
        while insert_idx < len(lines):
            stripped = lines[insert_idx].strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                break
            insert_idx += 1
        lines.insert(insert_idx, entry_line)
    else:
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(f"[{section}]")
        lines.append("")
        lines.append(entry_line)

    project_godot.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# project add-input
# ---------------------------------------------------------------------------

# Godot physical keycode mapping (common keys)
_KEY_CODES: dict[str, int] = {
    "a": 65, "b": 66, "c": 67, "d": 68, "e": 69, "f": 70,
    "g": 71, "h": 72, "i": 73, "j": 74, "k": 75, "l": 76,
    "m": 77, "n": 78, "o": 79, "p": 80, "q": 81, "r": 82,
    "s": 83, "t": 84, "u": 85, "v": 86, "w": 87, "x": 88,
    "y": 89, "z": 90,
    "0": 48, "1": 49, "2": 50, "3": 51, "4": 52,
    "5": 53, "6": 54, "7": 55, "8": 56, "9": 57,
    "space": 32, "escape": 4194305, "enter": 4194309,
    "tab": 4194306, "backspace": 4194308,
    "up": 4194320, "down": 4194322, "left": 4194319, "right": 4194321,
    "shift": 4194325, "ctrl": 4194326, "alt": 4194328,
    "f1": 4194332, "f2": 4194333, "f3": 4194334, "f4": 4194335,
    "f5": 4194336, "f6": 4194337, "f7": 4194338, "f8": 4194339,
    "f9": 4194340, "f10": 4194341, "f11": 4194342, "f12": 4194343,
}

# Mouse button indices for Godot
_MOUSE_BUTTONS: dict[str, int] = {
    "left": 1, "right": 2, "middle": 3,
    "wheel_up": 4, "wheel_down": 5,
}

# Joypad button indices
_JOY_BUTTONS: dict[str, int] = {
    "a": 0, "b": 1, "x": 2, "y": 3,
    "lb": 9, "rb": 10, "lt": -1, "rt": -1,
    "start": 6, "select": 4,
    "l3": 7, "r3": 8,
    "dpad_up": 11, "dpad_down": 12, "dpad_left": 13, "dpad_right": 14,
}


def _build_key_event(key_name: str) -> str:
    """Build a Godot InputEventKey Object() string for a key name."""
    lower = key_name.lower()
    if lower not in _KEY_CODES:
        raise ProjectError(
            message=f"Unknown key: '{key_name}'. Valid keys: {', '.join(sorted(_KEY_CODES))}",
            code="INVALID_KEY",
            fix="Use a key name like 'w', 'space', 'escape', 'up', 'f1', etc.",
        )
    physical_keycode = _KEY_CODES[lower]
    return (
        'Object(InputEventKey,'
        '"resource_local_to_scene":false,'
        '"resource_name":"",'
        '"device":-1,'
        '"window_id":0,'
        '"alt_pressed":false,'
        '"shift_pressed":false,'
        '"ctrl_pressed":false,'
        '"meta_pressed":false,'
        '"pressed":false,'
        '"keycode":0,'
        f'"physical_keycode":{physical_keycode},'
        '"key_label":0,'
        '"unicode":0,'
        '"location":0,'
        '"echo":false,'
        '"script":null'
        ')'
    )


def _build_mouse_event(button_name: str) -> str:
    """Build a Godot InputEventMouseButton Object() string."""
    lower = button_name.lower()
    if lower not in _MOUSE_BUTTONS:
        raise ProjectError(
            message=f"Unknown mouse button: '{button_name}'. Valid: {', '.join(sorted(_MOUSE_BUTTONS))}",
            code="INVALID_MOUSE_BUTTON",
            fix="Use 'left', 'right', 'middle', 'wheel_up', or 'wheel_down'.",
        )
    button_index = _MOUSE_BUTTONS[lower]
    return (
        'Object(InputEventMouseButton,'
        '"resource_local_to_scene":false,'
        '"resource_name":"",'
        '"device":-1,'
        '"window_id":0,'
        '"alt_pressed":false,'
        '"shift_pressed":false,'
        '"ctrl_pressed":false,'
        '"meta_pressed":false,'
        f'"button_mask":{button_index},'
        f'"position":Vector2(0, 0),'
        f'"global_position":Vector2(0, 0),'
        f'"factor":1.0,'
        f'"button_index":{button_index},'
        '"cancelled":false,'
        '"pressed":true,'
        '"double_click":false,'
        '"script":null'
        ')'
    )


def _build_joypad_event(button_name: str) -> str:
    """Build a Godot InputEventJoypadButton Object() string."""
    lower = button_name.lower()
    if lower not in _JOY_BUTTONS:
        raise ProjectError(
            message=f"Unknown joypad button: '{button_name}'. Valid: {', '.join(sorted(_JOY_BUTTONS))}",
            code="INVALID_JOY_BUTTON",
            fix="Use 'a', 'b', 'x', 'y', 'lb', 'rb', 'start', 'select', 'dpad_up', etc.",
        )
    button_index = _JOY_BUTTONS[lower]
    return (
        'Object(InputEventJoypadButton,'
        '"resource_local_to_scene":false,'
        '"resource_name":"",'
        '"device":-1,'
        f'"button_index":{button_index},'
        '"pressure":0.0,'
        '"pressed":false,'
        '"script":null'
        ')'
    )


def _build_input_value(
    events: list[str], deadzone: float
) -> str:
    """Build the full multi-line input action value for project.godot."""
    events_str = ", ".join(events)
    return (
        '{\n'
        f'"deadzone": {deadzone},\n'
        f'"events": [{events_str}\n'
        ']}'
    )


@project.command("add-input")
@click.option(
    "--action", required=True,
    help="Input action name (e.g., move_up, jump, attack)",
)
@click.option(
    "--key", "keys", multiple=True,
    help="Keyboard key(s) to bind (e.g., w, space, escape, up)",
)
@click.option(
    "--mouse", "mouse_buttons", multiple=True,
    help="Mouse button(s) to bind (e.g., left, right, middle)",
)
@click.option(
    "--joypad", "joypad_buttons", multiple=True,
    help="Joypad button(s) to bind (e.g., a, b, dpad_up)",
)
@click.option(
    "--deadzone", default=0.2, type=float,
    help="Deadzone for analog inputs (default: 0.2)",
)
@click.argument("project_path", default=".", type=click.Path())
@click.pass_context
def add_input(
    ctx: click.Context,
    action: str,
    keys: tuple[str, ...],
    mouse_buttons: tuple[str, ...],
    joypad_buttons: tuple[str, ...],
    deadzone: float,
    project_path: str,
) -> None:
    """Add an input action with key/mouse/joypad bindings to project.godot."""
    try:
        if not keys and not mouse_buttons and not joypad_buttons:
            raise ProjectError(
                message="No input events specified",
                code="NO_INPUT_EVENTS",
                fix="Provide at least one --key, --mouse, or --joypad binding",
            )

        project_godot = _find_project_godot(project_path)
        config_text = project_godot.read_text(encoding="utf-8")
        cfg = parse_project_config(config_text)

        existing = cfg.sections.get("input", [])
        for key, _val in existing:
            if key == action:
                raise ProjectError(
                    message=f"Input action '{action}' already exists",
                    code="INPUT_EXISTS",
                    fix="Remove the existing action or choose a different name",
                )

        events: list[str] = []
        for k in keys:
            events.append(_build_key_event(k))
        for m in mouse_buttons:
            events.append(_build_mouse_event(m))
        for j in joypad_buttons:
            events.append(_build_joypad_event(j))

        value = _build_input_value(events, deadzone)
        _add_section_entry(project_godot, "input", action, value)

        data = {
            "added": True,
            "action": action,
            "keys": list(keys),
            "mouse_buttons": list(mouse_buttons),
            "joypad_buttons": list(joypad_buttons),
            "deadzone": deadzone,
            "event_count": len(events),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            bindings: list[str] = []
            if data["keys"]:
                bindings.append(f"keys={','.join(data['keys'])}")
            if data["mouse_buttons"]:
                bindings.append(f"mouse={','.join(data['mouse_buttons'])}")
            if data["joypad_buttons"]:
                bindings.append(f"joypad={','.join(data['joypad_buttons'])}")
            click.echo(
                f"Added input action '{data['action']}' "
                f"with {data['event_count']} binding(s): {', '.join(bindings)}"
            )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)
