"""Manage Godot projects (info, validate, create)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import rich_click as click
from rich.console import Console
from rich.table import Table

from auto_godot.backend import GodotBackend
from auto_godot.errors import GodotBinaryError, ProjectError
from auto_godot.formats.project_cfg import parse_project_config, serialize_project_config
from auto_godot.formats.tscn import parse_tscn_file
from auto_godot.formats.tres import parse_tres_file
from auto_godot.output import GlobalConfig, emit, emit_error


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


def _detect_godot_version() -> str:
    """Detect the installed Godot engine version, falling back to 4.5."""
    try:
        backend = GodotBackend()
        backend.ensure_binary()
        version_str = backend._version or ""
        import re
        match = re.search(r"(\d+\.\d+)", version_str)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "4.5"


def _scaffold_project(target: Path, name: str) -> list[str]:
    """Create project directory structure and files."""
    created: list[str] = []

    # Create directories
    target.mkdir(parents=True)
    for subdir in ("scenes", "scripts", "assets", "sprites", "tilesets"):
        (target / subdir).mkdir()

    godot_version = _detect_godot_version()

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
        f'config/features=PackedStringArray("{godot_version}", "GL Compatibility")\n'
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

        # Check if the target script has a class_name that conflicts (#21)
        warnings_list: list[str] = []
        script_file = project_godot.parent / script_path.removeprefix("res://")
        if script_file.exists():
            try:
                import re
                script_text = script_file.read_text(encoding="utf-8")
                match = re.search(r'^class_name\s+(\w+)', script_text, re.MULTILINE)
                if match and match.group(1) == name:
                    warnings_list.append(
                        f"Script has class_name '{name}' which conflicts with "
                        f"autoload singleton name '{name}'. Godot 4.x will refuse "
                        f"to load it. Remove the class_name from the script."
                    )
            except Exception:
                pass

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
            "warnings": warnings_list,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Registered autoload '{data['name']}' -> {data['path']}"
                f"{' (singleton)' if data['singleton'] else ''}"
            )
            for w in data.get("warnings", []):
                click.echo(f"Warning: {w}", err=True)

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# project run
# ---------------------------------------------------------------------------


@project.command("run")
@click.argument("path", default=".", type=click.Path())
@click.option(
    "--quit-after", type=int, default=3,
    help="Seconds to run before quitting (default: 3).",
)
@click.pass_context
def run_project(ctx: click.Context, path: str, quit_after: int) -> None:
    """Run headless Godot smoke test: load the project, quit after N seconds.

    Captures any engine errors or warnings. Exit code 0 means the project
    loaded cleanly; non-zero means errors were detected.

    Examples:

      auto-godot project run

      auto-godot project run --quit-after 5

      auto-godot --json project run
    """
    try:
        project_godot = _find_project_godot(path)
        project_root = project_godot.parent

        config: GlobalConfig = ctx.obj
        backend = GodotBackend(binary_path=config.godot_path)

        import subprocess
        binary = backend.ensure_binary()
        cmd = [
            binary, "--headless",
            "--path", str(project_root),
            "--quit-after", str(quit_after),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=quit_after + 30,
        )

        stdout_lines = result.stdout.strip().splitlines() if result.stdout else []
        stderr_lines = result.stderr.strip().splitlines() if result.stderr else []

        errors = [l for l in stderr_lines if "ERROR" in l or "SCRIPT ERROR" in l]
        warnings = [l for l in stderr_lines if "WARNING" in l]

        data = {
            "success": result.returncode == 0 and len(errors) == 0,
            "exit_code": result.returncode,
            "errors": errors,
            "warnings": warnings,
            "stdout_lines": len(stdout_lines),
            "stderr_lines": len(stderr_lines),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            if data["success"]:
                click.echo("Project loaded cleanly (no errors)")
            else:
                click.echo(f"Project load found {len(data['errors'])} error(s):")
                for e in data["errors"]:
                    click.echo(f"  {e}")
            if data["warnings"] and verbose:
                click.echo(f"\nWarnings ({len(data['warnings'])}):")
                for w in data["warnings"]:
                    click.echo(f"  {w}")

        emit(data, _human, ctx)

        if not data["success"]:
            ctx.exit(1)
    except GodotBinaryError as exc:
        emit_error(exc, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)
    except Exception as exc:
        from auto_godot.errors import AutoGodotError
        emit_error(
            AutoGodotError(
                message=f"Run failed: {exc}",
                code="PROJECT_RUN_FAILED",
                fix="Ensure Godot is installed and the project is valid",
            ),
            ctx,
        )


# ---------------------------------------------------------------------------
# project test
# ---------------------------------------------------------------------------


@project.command("test")
@click.argument("path", default=".", type=click.Path())
@click.option(
    "--quit-after", type=int, default=3,
    help="Seconds to run in headless smoke test (default: 3).",
)
@click.option(
    "--check-only", is_flag=True,
    help="Also run Godot --check-only for GDScript syntax validation.",
)
@click.pass_context
def test_project(ctx: click.Context, path: str, quit_after: int, check_only: bool) -> None:
    """Full project validation: text checks + headless load test.

    Combines `project validate` (text-format checks), optional `--check-only`
    (GDScript syntax), and a headless Godot run to catch runtime errors.

    Examples:

      auto-godot project test

      auto-godot --json project test --check-only
    """
    try:
        project_godot = _find_project_godot(path)
        project_root = project_godot.parent

        # Step 1: text validation (same as project validate)
        missing, all_refs = _collect_res_paths(project_root)
        config_text = project_godot.read_text(encoding="utf-8")
        cfg = parse_project_config(config_text)
        _check_project_godot_refs(cfg, project_root, missing)

        autoload_section = cfg.sections.get("autoload")
        if autoload_section:
            for _key, val in autoload_section:
                clean = _strip_quotes(val).lstrip("*")
                if clean.startswith("res://"):
                    all_refs.add(clean)

        orphans = _collect_orphan_scripts(project_root, all_refs)

        # Step 2: optional --check-only
        script_errors: list[str] = []
        if check_only:
            config: GlobalConfig = ctx.obj
            backend = GodotBackend(binary_path=config.godot_path)
            try:
                result = backend.check_only(project_root)
                if result.stderr:
                    script_errors = [
                        l for l in result.stderr.strip().splitlines()
                        if "ERROR" in l or "error" in l.lower()
                    ]
            except Exception as exc:
                script_errors.append(str(exc))

        # Step 3: headless smoke test
        runtime_errors: list[str] = []
        runtime_warnings: list[str] = []
        runtime_success = True
        try:
            config_obj: GlobalConfig = ctx.obj
            backend = GodotBackend(binary_path=config_obj.godot_path)
            import subprocess
            binary = backend.ensure_binary()
            cmd = [
                binary, "--headless",
                "--path", str(project_root),
                "--quit-after", str(quit_after),
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=quit_after + 30,
            )
            if result.stderr:
                for line in result.stderr.strip().splitlines():
                    if "ERROR" in line or "SCRIPT ERROR" in line:
                        runtime_errors.append(line)
                    elif "WARNING" in line:
                        runtime_warnings.append(line)
            if result.returncode != 0 or runtime_errors:
                runtime_success = False
        except GodotBinaryError:
            runtime_errors.append("Godot binary not found; skipped headless test")
            runtime_success = False
        except Exception as exc:
            runtime_errors.append(f"Headless test failed: {exc}")
            runtime_success = False

        all_ok = (
            len(missing) == 0
            and len(script_errors) == 0
            and runtime_success
        )

        data = {
            "success": all_ok,
            "text_validation": {
                "missing_resources": missing,
                "orphan_scripts": orphans,
                "issues": len(missing),
            },
            "script_check": {
                "errors": script_errors,
                "ran": check_only,
            },
            "runtime_test": {
                "success": runtime_success,
                "errors": runtime_errors,
                "warnings": runtime_warnings,
            },
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            tv = data["text_validation"]
            rt = data["runtime_test"]
            sc = data["script_check"]

            if tv["issues"] > 0:
                click.echo(f"Text validation: {tv['issues']} issue(s)")
                for r in tv["missing_resources"]:
                    click.echo(f"  Missing: {r}")
            else:
                click.echo("Text validation: passed")

            if sc["ran"]:
                if sc["errors"]:
                    click.echo(f"Script check: {len(sc['errors'])} error(s)")
                    for e in sc["errors"]:
                        click.echo(f"  {e}")
                else:
                    click.echo("Script check: passed")

            if rt["success"]:
                click.echo("Runtime test: passed")
            else:
                click.echo(f"Runtime test: {len(rt['errors'])} error(s)")
                for e in rt["errors"]:
                    click.echo(f"  {e}")

            if data["success"]:
                click.echo("\nAll checks passed.")
            else:
                click.echo("\nSome checks failed.")

        emit(data, _human, ctx)

        if not all_ok:
            ctx.exit(1)
    except ProjectError as exc:
        emit_error(exc, ctx)


@project.command("stats")
@click.argument("path", default=".", type=click.Path())
@click.pass_context
def stats(ctx: click.Context, path: str) -> None:
    """Show project statistics: file counts, total nodes, resource types."""
    try:
        project_godot = _find_project_godot(path)
        project_root = project_godot.parent

        scene_files = list(project_root.rglob("*.tscn"))
        tres_files = list(project_root.rglob("*.tres"))
        gd_files = list(project_root.rglob("*.gd"))
        asset_files = list(project_root.rglob("*.png")) + list(project_root.rglob("*.ogg")) + list(project_root.rglob("*.wav"))

        total_nodes = 0
        for sf in scene_files:
            try:
                from auto_godot.formats.tscn import parse_tscn_file
                scene = parse_tscn_file(sf)
                total_nodes += len(scene.nodes)
            except Exception:
                pass

        config_text = project_godot.read_text(encoding="utf-8")
        info = _extract_info(config_text)

        data = {
            "name": info["name"],
            "godot_version": info.get("godot_version"),
            "scenes": len(scene_files),
            "resources": len(tres_files),
            "scripts": len(gd_files),
            "assets": len(asset_files),
            "total_nodes": total_nodes,
            "autoloads": len(info.get("autoloads", {})),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Project: {data['name']}")
            if data.get("godot_version"):
                click.echo(f"  Godot: {data['godot_version']}")
            click.echo(f"  Scenes:    {data['scenes']}")
            click.echo(f"  Scripts:   {data['scripts']}")
            click.echo(f"  Resources: {data['resources']}")
            click.echo(f"  Assets:    {data['assets']}")
            click.echo(f"  Nodes:     {data['total_nodes']}")
            click.echo(f"  Autoloads: {data['autoloads']}")

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


# ---------------------------------------------------------------------------
# project set-display
# ---------------------------------------------------------------------------


@project.command("set-display")
@click.option("--width", type=int, help="Viewport width in pixels")
@click.option("--height", type=int, help="Viewport height in pixels")
@click.option("--window-width", type=int, help="Window width override")
@click.option("--window-height", type=int, help="Window height override")
@click.option(
    "--stretch-mode",
    type=click.Choice(["disabled", "canvas_items", "viewport"]),
    help="Stretch mode",
)
@click.option(
    "--stretch-aspect",
    type=click.Choice(["ignore", "keep", "keep_width", "keep_height", "expand"]),
    help="Stretch aspect",
)
@click.option(
    "--texture-filter",
    type=click.Choice(["nearest", "linear"]),
    help="Default texture filter (nearest for pixel art)",
)
@click.argument("project_path", default=".", type=click.Path())
@click.pass_context
def set_display(
    ctx: click.Context,
    width: int | None,
    height: int | None,
    window_width: int | None,
    window_height: int | None,
    stretch_mode: str | None,
    stretch_aspect: str | None,
    texture_filter: str | None,
    project_path: str,
) -> None:
    """Configure display/window settings in project.godot.

    Examples:

      auto-godot project set-display --width 320 --height 180 --window-width 1280 --window-height 720

      auto-godot project set-display --stretch-mode viewport --stretch-aspect keep --texture-filter nearest
    """
    try:
        project_godot = _find_project_godot(project_path)
        changed: list[str] = []
        settings: list[tuple[str, str, str]] = []

        if width is not None:
            settings.append(("display", "window/size/viewport_width", str(width)))
            changed.append(f"viewport_width={width}")
        if height is not None:
            settings.append(("display", "window/size/viewport_height", str(height)))
            changed.append(f"viewport_height={height}")
        if window_width is not None:
            settings.append(("display", "window/size/window_width_override", str(window_width)))
            changed.append(f"window_width={window_width}")
        if window_height is not None:
            settings.append(("display", "window/size/window_height_override", str(window_height)))
            changed.append(f"window_height={window_height}")
        if stretch_mode is not None:
            settings.append(("display", "window/stretch/mode", f'"{stretch_mode}"'))
            changed.append(f"stretch_mode={stretch_mode}")
        if stretch_aspect is not None:
            settings.append(("display", "window/stretch/aspect", f'"{stretch_aspect}"'))
            changed.append(f"stretch_aspect={stretch_aspect}")
        if texture_filter is not None:
            val = "0" if texture_filter == "nearest" else "1"
            settings.append(("rendering", "textures/canvas_textures/default_texture_filter", val))
            changed.append(f"texture_filter={texture_filter}")

        if not settings:
            raise ProjectError(
                message="No display settings specified",
                code="NO_SETTINGS",
                fix="Provide at least one display option (--width, --height, etc.)",
            )

        for section, key, value in settings:
            _set_project_value(project_godot, section, key, value)

        data = {
            "updated": True,
            "changes": changed,
            "count": len(changed),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Updated display: {', '.join(data['changes'])}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


def _format_godot_value(value: str) -> str:
    """Quote string values for project.godot if needed."""
    if value.startswith('"') and value.endswith('"'):
        return value
    try:
        float(value)
        return value
    except ValueError:
        pass
    if value in ("true", "false", "null"):
        return value
    if any(value.startswith(p) for p in (
        "Vector2(", "Vector3(", "Color(", "Rect2(", "Transform",
        "SubResource(", "ExtResource(", "PackedScene(",
    )):
        return value
    return f'"{value}"'


def _set_project_value(
    project_godot: Path, section: str, key: str, value: str
) -> None:
    """Set a key=value in a section of project.godot, creating if needed."""
    text = project_godot.read_text(encoding="utf-8")
    lines = text.split("\n")

    section_idx = None
    key_idx = None

    for i, line in enumerate(lines):
        if line.strip() == f"[{section}]":
            section_idx = i

    if section_idx is not None:
        for i in range(section_idx + 1, len(lines)):
            stripped = lines[i].strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                break
            if stripped.startswith(f"{key}="):
                key_idx = i
                break

    formatted_value = _format_godot_value(value)
    entry_line = f"{key}={formatted_value}"

    if key_idx is not None:
        lines[key_idx] = entry_line
    elif section_idx is not None:
        insert_idx = section_idx + 1
        while insert_idx < len(lines) and lines[insert_idx].strip() == "":
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
# project set-rendering
# ---------------------------------------------------------------------------


@project.command("set-rendering")
@click.option(
    "--method",
    type=click.Choice(["forward_plus", "mobile", "gl_compatibility"]),
    help="Rendering method",
)
@click.option(
    "--msaa-2d",
    type=click.Choice(["disabled", "2x", "4x", "8x"]),
    help="MSAA for 2D",
)
@click.option(
    "--msaa-3d",
    type=click.Choice(["disabled", "2x", "4x", "8x"]),
    help="MSAA for 3D",
)
@click.argument("project_path", default=".", type=click.Path())
@click.pass_context
def set_rendering(
    ctx: click.Context,
    method: str | None,
    msaa_2d: str | None,
    msaa_3d: str | None,
    project_path: str,
) -> None:
    """Configure rendering settings in project.godot.

    Examples:

      auto-godot project set-rendering --method gl_compatibility

      auto-godot project set-rendering --msaa-2d 4x --msaa-3d 4x
    """
    try:
        project_godot = _find_project_godot(project_path)
        changed: list[str] = []
        settings: list[tuple[str, str, str]] = []

        if method is not None:
            settings.append(("rendering", "renderer/rendering_method", f'"{method}"'))
            changed.append(f"method={method}")
        if msaa_2d is not None:
            val_map = {"disabled": "0", "2x": "1", "4x": "2", "8x": "3"}
            settings.append((
                "rendering", "anti_aliasing/quality/msaa_2d",
                val_map.get(msaa_2d, "0"),
            ))
            changed.append(f"msaa_2d={msaa_2d}")
        if msaa_3d is not None:
            val_map = {"disabled": "0", "2x": "1", "4x": "2", "8x": "3"}
            settings.append((
                "rendering", "anti_aliasing/quality/msaa_3d",
                val_map.get(msaa_3d, "0"),
            ))
            changed.append(f"msaa_3d={msaa_3d}")

        if not settings:
            raise ProjectError(
                message="No rendering settings specified",
                code="NO_SETTINGS",
                fix="Provide at least one rendering option",
            )

        for section, key, value in settings:
            _set_project_value(project_godot, section, key, value)

        data = {"updated": True, "changes": changed, "count": len(changed)}

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Updated rendering: {', '.join(data['changes'])}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# project add-layer
# ---------------------------------------------------------------------------


_LAYER_TYPES = {
    "2d_physics": "layer_names/2d_physics/layer_",
    "2d_render": "layer_names/2d_render/layer_",
    "3d_physics": "layer_names/3d_physics/layer_",
    "3d_render": "layer_names/3d_render/layer_",
    "2d_navigation": "layer_names/2d_navigation/layer_",
    "3d_navigation": "layer_names/3d_navigation/layer_",
    "avoidance": "layer_names/avoidance/layer_",
}


@project.command("add-layer")
@click.option(
    "--type", "layer_type", required=True,
    type=click.Choice(sorted(_LAYER_TYPES)),
    help="Layer type",
)
@click.option(
    "--index", required=True, type=int,
    help="Layer index (1-32)",
)
@click.option(
    "--name", "layer_name", required=True,
    help="Layer name",
)
@click.argument("project_path", default=".", type=click.Path())
@click.pass_context
def add_layer(
    ctx: click.Context,
    layer_type: str,
    index: int,
    layer_name: str,
    project_path: str,
) -> None:
    """Name a physics/render/navigation layer in project.godot.

    Examples:

      auto-godot project add-layer --type 2d_physics --index 1 --name player

      auto-godot project add-layer --type 2d_physics --index 2 --name enemy

      auto-godot project add-layer --type 2d_render --index 1 --name foreground
    """
    try:
        if index < 1 or index > 32:
            raise ProjectError(
                message=f"Layer index must be 1-32, got {index}",
                code="INVALID_LAYER_INDEX",
                fix="Use a layer index between 1 and 32",
            )

        project_godot = _find_project_godot(project_path)
        prefix = _LAYER_TYPES[layer_type]
        key = f"{prefix}{index}"
        value = f'"{layer_name}"'

        _set_project_value(project_godot, "layer_names", key, value)

        data = {
            "added": True,
            "layer_type": layer_type,
            "index": index,
            "name": layer_name,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Named {data['layer_type']} layer {data['index']} = '{data['name']}'"
            )

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# project set-config
# ---------------------------------------------------------------------------


@project.command("set-config")
@click.option("--section", required=True, help="Section name (e.g., application, display).")
@click.option("--key", required=True, help="Setting key (e.g., config/name, run/main_scene).")
@click.option("--value", required=True, help="Value to set.")
@click.argument("project_path", default=".", type=click.Path())
@click.pass_context
def set_config(
    ctx: click.Context,
    section: str,
    key: str,
    value: str,
    project_path: str,
) -> None:
    """Set a key-value pair in project.godot.

    Generic setter for any project.godot configuration. Creates the
    section if it does not exist, updates in place if the key exists.

    Examples:

      auto-godot project set-config --section application --key config/name --value "My Game"

      auto-godot project set-config --section display --key window/size/viewport_width --value 1920
    """
    try:
        project_godot = _find_project_godot(project_path)
        _set_project_value(project_godot, section, key, value)

        data = {
            "updated": True,
            "section": section,
            "key": key,
            "value": value,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Set [{data['section']}] {data['key']} = {data['value']}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# project set-main-scene
# ---------------------------------------------------------------------------


@project.command("set-main-scene")
@click.option("--scene", required=True, help="Scene path (e.g., res://scenes/main.tscn).")
@click.argument("project_path", default=".", type=click.Path())
@click.pass_context
def set_main_scene(
    ctx: click.Context,
    scene: str,
    project_path: str,
) -> None:
    """Set the main scene in project.godot.

    Examples:

      auto-godot project set-main-scene --scene res://scenes/main.tscn
    """
    try:
        project_godot = _find_project_godot(project_path)
        _set_project_value(
            project_godot, "application", "run/main_scene", f'"{scene}"'
        )

        data = {
            "updated": True,
            "main_scene": scene,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Main scene set to: {data['main_scene']}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# project add-plugin
# ---------------------------------------------------------------------------


@project.command("add-plugin")
@click.option("--name", "plugin_name", required=True, help="Plugin name (e.g., gut)")
@click.option("--path", "plugin_path", required=True,
              help="Plugin config path (e.g., res://addons/gut/plugin.cfg)")
@click.argument("project_path", default=".", type=click.Path())
@click.pass_context
def add_plugin(
    ctx: click.Context,
    plugin_name: str,
    plugin_path: str,
    project_path: str,
) -> None:
    """Enable a plugin in project.godot.

    Sets the editor_plugins/enabled array to include the plugin.

    Examples:

      auto-godot project add-plugin --name gut --path res://addons/gut/plugin.cfg
    """
    try:
        project_godot = _find_project_godot(project_path)
        text = project_godot.read_text(encoding="utf-8")
        cfg = parse_project_config(text)

        # Check if plugin is already enabled
        existing = cfg.get_value("editor_plugins", "enabled")
        if existing and plugin_path in existing:
            raise ProjectError(
                message=f"Plugin '{plugin_name}' is already enabled",
                code="PLUGIN_EXISTS",
                fix="Plugin is already in editor_plugins/enabled",
            )

        # Build the new PackedStringArray value
        if existing:
            # Parse existing array and add new entry
            import re
            entries = re.findall(r'"([^"]*)"', existing)
            if plugin_path not in entries:
                entries.append(plugin_path)
            quoted = ', '.join(f'"{e}"' for e in entries)
            value = f"PackedStringArray({quoted})"
        else:
            value = f'PackedStringArray("{plugin_path}")'

        _set_project_value(project_godot, "editor_plugins", "enabled", value)

        data = {"added": True, "name": plugin_name, "path": plugin_path}

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Enabled plugin '{data['name']}' ({data['path']})")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)
