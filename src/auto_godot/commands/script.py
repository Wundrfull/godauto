"""Generate and manage GDScript files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rich_click as click

from auto_godot.errors import ProjectError
from auto_godot.output import emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def script(ctx: click.Context) -> None:
    """Generate and manage GDScript files."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Common Godot base classes for validation
_BASE_CLASSES = {
    "Node", "Node2D", "Node3D", "Control", "CanvasLayer",
    "CharacterBody2D", "CharacterBody3D", "RigidBody2D", "RigidBody3D",
    "StaticBody2D", "StaticBody3D", "Area2D", "Area3D",
    "Sprite2D", "Sprite3D", "AnimatedSprite2D", "AnimatedSprite3D",
    "Camera2D", "Camera3D", "Light2D",
    "AudioStreamPlayer", "AudioStreamPlayer2D", "AudioStreamPlayer3D",
    "Timer", "HTTPRequest", "TileMapLayer",
    "Resource", "RefCounted", "Object",
    "Label", "Button", "TextureButton", "TextureRect",
    "Panel", "PanelContainer", "MarginContainer",
    "HBoxContainer", "VBoxContainer", "GridContainer",
    "ScrollContainer", "TabContainer", "CenterContainer",
    "LineEdit", "TextEdit", "RichTextLabel",
    "ProgressBar", "HSlider", "VSlider", "SpinBox",
    "ColorRect", "SubViewport", "SubViewportContainer",
    "Path2D", "PathFollow2D", "Path3D", "PathFollow3D",
    "CPUParticles2D", "GPUParticles2D",
    "CPUParticles3D", "GPUParticles3D",
    "RayCast2D", "RayCast3D",
    "CollisionShape2D", "CollisionShape3D",
    "NavigationAgent2D", "NavigationAgent3D",
}


def _check_autoload_conflict(
    class_name: str, output_path: str, warnings_list: list[str]
) -> None:
    """Warn if class_name matches an existing autoload singleton name.

    Walks up from the output path to find project.godot and checks its
    [autoload] section. Also warns if the script is in an autoload
    directory and the class_name matches the expected singleton pattern.
    """
    out = Path(output_path).resolve()
    for parent in [out.parent] + list(out.parent.parents):
        project_file = parent / "project.godot"
        if project_file.exists():
            try:
                from auto_godot.formats.project_cfg import parse_project_config
                cfg = parse_project_config(project_file.read_text(encoding="utf-8"))
                autoload_section = cfg.sections.get("autoload")
                if autoload_section:
                    for name, _val in autoload_section:
                        if name == class_name:
                            warnings_list.append(
                                f"class_name '{class_name}' conflicts with autoload "
                                f"singleton '{name}'. Godot 4.x will refuse to load "
                                f"scripts where class_name equals the autoload name. "
                                f"Remove the class_name or use a different name."
                            )
                            return
            except Exception:
                pass
            return
    # No project.godot found; warn if path suggests autoload usage
    if "autoload" in str(output_path).lower():
        warnings_list.append(
            f"class_name '{class_name}' may conflict if this script is registered "
            f"as an autoload with the same name. Godot 4.x rejects scripts where "
            f"class_name equals the autoload singleton name."
        )



def _generate_script(
    extends: str,
    class_name: str | None,
    signals: list[str],
    exports: list[tuple[str, str, str]],
    onready: list[tuple[str, str, str]],
    with_ready: bool,
    with_process: bool,
    with_input: bool,
    with_physics: bool,
) -> str:
    """Generate GDScript source code from parameters."""
    lines: list[str] = []

    if class_name:
        lines.append(f"class_name {class_name}")
    lines.append(f"extends {extends}")
    lines.append("")

    if signals:
        for sig in signals:
            lines.append(f"signal {sig}")
        lines.append("")

    if exports:
        for var_name, var_type, default in exports:
            if default:
                lines.append(f"@export var {var_name}: {var_type} = {default}")
            else:
                lines.append(f"@export var {var_name}: {var_type}")
        lines.append("")

    if onready:
        for var_name, var_type, node_path in onready:
            lines.append(f'@onready var {var_name}: {var_type} = ${node_path}')
        lines.append("")

    # Generate lifecycle methods
    methods: list[tuple[str, str]] = []
    if with_ready:
        methods.append(("_ready", "pass"))
    if with_process:
        methods.append(("_process", "pass"))
    if with_physics:
        methods.append(("_physics_process", "pass"))
    if with_input:
        methods.append(("_unhandled_input", "pass"))

    for i, (method_name, body) in enumerate(methods):
        if method_name == "_process" or method_name == "_physics_process":
            lines.append(f"func {method_name}(delta: float) -> void:")
        elif method_name == "_unhandled_input":
            lines.append(f"func {method_name}(event: InputEvent) -> void:")
        else:
            lines.append(f"func {method_name}() -> void:")
        lines.append(f"\t{body}")
        if i < len(methods) - 1:
            lines.append("")
            lines.append("")

    # Ensure file ends with newline
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    return text


@script.command()
@click.option("--extends", default="Node2D", help="Base class to extend (default: Node2D)")
@click.option("--class-name", default=None, help="Optional class_name declaration")
@click.option("--signal", "signals", multiple=True, help="Signal declarations (e.g., 'died' or 'health_changed(amount: int)')")
@click.option("--export", "exports", multiple=True, help="Exported vars as 'name:type=default' (e.g., 'speed:float=100.0')")
@click.option("--onready", "onready_vars", multiple=True, help="@onready vars as 'name:Type=NodePath' (e.g., 'sprite:Sprite2D=Sprite2D')")
@click.option("--ready/--no-ready", default=True, help="Include _ready() method (default: yes)")
@click.option("--process/--no-process", default=False, help="Include _process() method")
@click.option("--input/--no-input", "with_input", default=False, help="Include _unhandled_input() method")
@click.option("--physics/--no-physics", default=False, help="Include _physics_process() method")
@click.argument("output_path", type=click.Path())
@click.pass_context
def create(
    ctx: click.Context,
    extends: str,
    class_name: str | None,
    signals: tuple[str, ...],
    exports: tuple[str, ...],
    onready_vars: tuple[str, ...],
    ready: bool,
    process: bool,
    with_input: bool,
    physics: bool,
    output_path: str,
) -> None:
    """Generate a GDScript file with boilerplate.

    Examples:

      auto-godot script create --extends CharacterBody2D --export "speed:float=200.0" scripts/player.gd

      auto-godot script create --extends Control --signal "clicked" --ready --process scripts/ui/hud.gd
    """
    try:
        parsed_exports = _parse_exports(exports)
        parsed_onready = _parse_onready(onready_vars)

        warnings_list: list[str] = []

        # Warn if class_name matches an autoload name (#21). Godot 4.x
        # rejects scripts where class_name equals the autoload singleton name.
        if class_name:
            _check_autoload_conflict(class_name, output_path, warnings_list)

        source = _generate_script(
            extends=extends,
            class_name=class_name,
            signals=list(signals),
            exports=parsed_exports,
            onready=parsed_onready,
            with_ready=ready,
            with_process=process,
            with_input=with_input,
            with_physics=physics,
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(source, encoding="utf-8")

        data = {
            "created": True,
            "path": str(out),
            "extends": extends,
            "class_name": class_name,
            "signals": list(signals),
            "exports": [f"{n}:{t}={d}" if d else f"{n}:{t}" for n, t, d in parsed_exports],
            "lines": source.count("\n"),
            "warnings": warnings_list,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Created {data['path']} (extends {data['extends']}, {data['lines']} lines)")
            for w in data.get("warnings", []):
                click.echo(f"Warning: {w}", err=True)

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


def _parse_exports(exports: tuple[str, ...]) -> list[tuple[str, str, str]]:
    """Parse 'name:type=default' strings into (name, type, default) tuples."""
    result: list[tuple[str, str, str]] = []
    for exp in exports:
        default = ""
        if "=" in exp:
            left, default = exp.split("=", 1)
        else:
            left = exp

        if ":" not in left:
            raise ProjectError(
                message=f"Invalid export format: '{exp}'. Expected 'name:type' or 'name:type=default'",
                code="INVALID_EXPORT_FORMAT",
                fix="Use format 'name:type=default', e.g., 'speed:float=100.0' or 'health:int'",
            )
        name, var_type = left.split(":", 1)
        result.append((name.strip(), var_type.strip(), default.strip()))
    return result


@script.command("attach")
@click.option("--scene", "scene_path", required=True, type=click.Path(exists=True), help="Scene file to modify")
@click.option("--node", "node_name", required=True, help="Node name to attach the script to")
@click.option("--script", "script_path", required=True, help="res:// path to the script (e.g., res://scripts/player.gd)")
@click.option("--parent", "parent_path", default=None, help="Parent node path to disambiguate")
@click.pass_context
def attach(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    script_path: str,
    parent_path: str | None,
) -> None:
    """Attach a GDScript to a node in a scene file.

    Creates the ext_resource reference and sets the script property on the
    target node. If the script is already attached, reports it.

    Examples:

      auto-godot script attach --scene scenes/main.tscn --node Player --script res://scripts/player.gd

      auto-godot script attach --scene scenes/level.tscn --node Enemy --script res://scripts/enemy.gd --parent Enemies
    """
    try:

        from auto_godot.formats.tscn import ExtResource, parse_tscn, serialize_tscn
        from auto_godot.formats.values import ExtResourceRef

        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene = parse_tscn(text)

        # Find target node
        target = None
        for node in scene.nodes:
            if node.name == node_name and (parent_path is None or node.parent == parent_path):
                target = node
                break

        if target is None:
            raise ProjectError(
                message=f"Node '{node_name}' not found in scene",
                code="NODE_NOT_FOUND",
                fix="Check the node name and parent path",
            )

        # Check if script already attached
        if "script" in target.properties:
            raise ProjectError(
                message=f"Node '{node_name}' already has a script attached",
                code="SCRIPT_EXISTS",
                fix="Remove the existing script first or choose a different node",
            )

        # Add ext_resource for the script
        existing_ids = {ext.id for ext in scene.ext_resources}
        counter = 1
        ext_id = f"{counter}_script"
        while ext_id in existing_ids:
            counter += 1
            ext_id = f"{counter}_script"

        scene.ext_resources.append(ExtResource(
            type="Script",
            path=script_path,
            id=ext_id,
            uid=None,
        ))

        target.properties["script"] = ExtResourceRef(ext_id)

        # Update load_steps
        scene.load_steps = len(scene.ext_resources) + len(scene.sub_resources) + 1

        scene._raw_header = None
        scene._raw_sections = None
        output = serialize_tscn(scene)
        path.write_text(output, encoding="utf-8")

        data = {
            "attached": True,
            "node": node_name,
            "script": script_path,
            "scene": scene_path,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Attached {data['script']} to '{data['node']}'")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


def _parse_onready(onready_vars: tuple[str, ...]) -> list[tuple[str, str, str]]:
    """Parse 'name:Type=NodePath' strings into (name, type, path) tuples."""
    result: list[tuple[str, str, str]] = []
    for var in onready_vars:
        if "=" not in var:
            raise ProjectError(
                message=f"Invalid onready format: '{var}'. Expected 'name:Type=NodePath'",
                code="INVALID_ONREADY_FORMAT",
                fix="Use format 'name:Type=NodePath', e.g., 'sprite:Sprite2D=Sprite2D'",
            )
        left, node_path = var.split("=", 1)
        if ":" not in left:
            raise ProjectError(
                message=f"Invalid onready format: '{var}'. Expected 'name:Type=NodePath'",
                code="INVALID_ONREADY_FORMAT",
                fix="Use format 'name:Type=NodePath', e.g., 'sprite:Sprite2D=Sprite2D'",
            )
        name, var_type = left.split(":", 1)
        result.append((name.strip(), var_type.strip(), node_path.strip()))
    return result


# ---------------------------------------------------------------------------
# Script editing helpers
# ---------------------------------------------------------------------------


def _read_script(file_path: str) -> tuple[Path, str]:
    """Read a GDScript file, raising ProjectError if not found."""
    path = Path(file_path)
    if not path.exists():
        raise ProjectError(
            message=f"Script not found: {file_path}",
            code="SCRIPT_NOT_FOUND",
            fix="Check the file path",
        )
    return path, path.read_text(encoding="utf-8")


def _find_insert_point(lines: list[str], section: str) -> int:
    """Find the right line index to insert a new element into a GDScript.

    section can be: "var", "signal", "export", "method"
    Returns the line index where the new content should be inserted.
    """
    if section == "method":
        # Methods go at the end of the file
        return len(lines)

    # Variables, signals, exports go after the last of their kind,
    # or after extends/class_name if none exist yet
    markers = {
        "var": ("var ", "@onready", "@export"),
        "signal": ("signal ",),
        "export": ("@export ",),
    }

    target_prefixes = markers.get(section, ())
    last_match = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        for prefix in target_prefixes:
            if stripped.startswith(prefix):
                last_match = i

    if last_match >= 0:
        return last_match + 1

    # No existing matches; insert after extends/class_name block
    insert_after = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("extends ") or stripped.startswith("class_name ") or stripped == "" and insert_after > 0:
            insert_after = i + 1
        elif stripped and insert_after > 0:
            break

    return insert_after


# ---------------------------------------------------------------------------
# script add-method
# ---------------------------------------------------------------------------


@script.command("add-method")
@click.option("--file", "file_path", required=True, type=click.Path(),
              help="Path to the .gd script file")
@click.option("--name", "method_name", required=True,
              help="Method name (e.g., _on_button_pressed)")
@click.option("--body", default="pass",
              help="Method body (use \\n for newlines)")
@click.option("--params", default="",
              help="Method parameters (e.g., 'delta: float')")
@click.option("--return-type", "return_type", default="void",
              help="Return type (default: void)")
@click.pass_context
def add_method(
    ctx: click.Context,
    file_path: str,
    method_name: str,
    body: str,
    params: str,
    return_type: str,
) -> None:
    """Add a method to an existing GDScript file.

    Examples:

      auto-godot script add-method --file scripts/main.gd --name _on_button_pressed --body "score += 1"

      auto-godot script add-method --file scripts/player.gd --name take_damage --params "amount: int" --body "health -= amount"
    """
    try:
        path, text = _read_script(file_path)
        lines = text.split("\n")

        # Check if method already exists
        for line in lines:
            if line.strip().startswith(f"func {method_name}("):
                raise ProjectError(
                    message=f"Method '{method_name}' already exists in {file_path}",
                    code="METHOD_EXISTS",
                    fix="Choose a different name or edit the existing method",
                )

        # Build method
        param_str = params if params else ""
        method_lines = [
            "",
            "",
            f"func {method_name}({param_str}) -> {return_type}:",
        ]
        for body_line in body.replace("\\n", "\n").replace("\\t", "\t").split("\n"):
            method_lines.append(f"\t{body_line}")

        insert_idx = _find_insert_point(lines, "method")
        for i, ml in enumerate(method_lines):
            lines.insert(insert_idx + i, ml)

        result_text = "\n".join(lines)
        if not result_text.endswith("\n"):
            result_text += "\n"
        path.write_text(result_text, encoding="utf-8")

        data = {"added": True, "method": method_name, "file": file_path}

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Added method '{data['method']}' to {data['file']}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# script add-var
# ---------------------------------------------------------------------------


@script.command("add-var")
@click.option("--file", "file_path", required=True, type=click.Path(),
              help="Path to the .gd script file")
@click.option("--name", "var_name", required=True, help="Variable name")
@click.option("--type", "var_type", required=True, help="Variable type (e.g., int, float, String)")
@click.option("--value", "default_value", default=None, help="Default value")
@click.pass_context
def add_var(
    ctx: click.Context,
    file_path: str,
    var_name: str,
    var_type: str,
    default_value: str | None,
) -> None:
    """Add a variable declaration to an existing GDScript file.

    Examples:

      auto-godot script add-var --file scripts/main.gd --name score --type int --value 0

      auto-godot script add-var --file scripts/player.gd --name health --type float --value 100.0
    """
    try:
        path, text = _read_script(file_path)
        lines = text.split("\n")

        if default_value is not None:
            new_line = f"var {var_name}: {var_type} = {default_value}"
        else:
            new_line = f"var {var_name}: {var_type}"

        insert_idx = _find_insert_point(lines, "var")
        lines.insert(insert_idx, new_line)

        result_text = "\n".join(lines)
        if not result_text.endswith("\n"):
            result_text += "\n"
        path.write_text(result_text, encoding="utf-8")

        data = {"added": True, "var": var_name, "type": var_type, "file": file_path}

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Added var '{data['var']}: {data['type']}' to {data['file']}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# script add-export
# ---------------------------------------------------------------------------


@script.command("add-export")
@click.option("--file", "file_path", required=True, type=click.Path(),
              help="Path to the .gd script file")
@click.option("--name", "var_name", required=True, help="Variable name")
@click.option("--type", "var_type", required=True, help="Variable type")
@click.option("--value", "default_value", default=None, help="Default value")
@click.pass_context
def add_export(
    ctx: click.Context,
    file_path: str,
    var_name: str,
    var_type: str,
    default_value: str | None,
) -> None:
    """Add an @export variable to an existing GDScript file.

    Examples:

      auto-godot script add-export --file scripts/main.gd --name speed --type float --value 100.0
    """
    try:
        path, text = _read_script(file_path)
        lines = text.split("\n")

        if default_value is not None:
            new_line = f"@export var {var_name}: {var_type} = {default_value}"
        else:
            new_line = f"@export var {var_name}: {var_type}"

        insert_idx = _find_insert_point(lines, "export")
        lines.insert(insert_idx, new_line)

        result_text = "\n".join(lines)
        if not result_text.endswith("\n"):
            result_text += "\n"
        path.write_text(result_text, encoding="utf-8")

        data = {"added": True, "export": var_name, "type": var_type, "file": file_path}

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Added @export '{data['export']}: {data['type']}' to {data['file']}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# script add-signal
# ---------------------------------------------------------------------------


@script.command("add-signal")
@click.option("--file", "file_path", required=True, type=click.Path(),
              help="Path to the .gd script file")
@click.option("--name", "signal_name", required=True, help="Signal name")
@click.option("--params", default=None,
              help="Signal parameters (e.g., 'new_score: int, old_score: int')")
@click.pass_context
def add_signal(
    ctx: click.Context,
    file_path: str,
    signal_name: str,
    params: str | None,
) -> None:
    """Add a signal declaration to an existing GDScript file.

    Examples:

      auto-godot script add-signal --file scripts/main.gd --name score_changed --params "new_score: int"
    """
    try:
        path, text = _read_script(file_path)
        lines = text.split("\n")

        new_line = f"signal {signal_name}({params})" if params else f"signal {signal_name}"

        insert_idx = _find_insert_point(lines, "signal")
        lines.insert(insert_idx, new_line)

        result_text = "\n".join(lines)
        if not result_text.endswith("\n"):
            result_text += "\n"
        path.write_text(result_text, encoding="utf-8")

        data = {"added": True, "signal": signal_name, "file": file_path}

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Added signal '{data['signal']}' to {data['file']}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


# ---------------------------------------------------------------------------
# script list-methods
# ---------------------------------------------------------------------------


@script.command("list-methods")
@click.argument("file_path", type=click.Path(exists=True))
@click.pass_context
def list_methods(ctx: click.Context, file_path: str) -> None:
    """List all methods in a GDScript file.

    Examples:

      auto-godot script list-methods scripts/main.gd
    """
    import re
    try:
        path = Path(file_path)
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")

        methods: list[dict[str, str]] = []
        for i, line in enumerate(lines):
            match = re.match(r'^func\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*(\w+))?', line)
            if match:
                methods.append({
                    "name": match.group(1),
                    "params": match.group(2).strip(),
                    "return_type": match.group(3) or "void",
                    "line": str(i + 1),
                })

        data = {"methods": methods, "count": len(methods), "file": file_path}

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Methods in {data['file']} ({data['count']}):")
            for m in data["methods"]:
                params = f"({m['params']})" if m["params"] else "()"
                click.echo(f"  L{m['line']}: {m['name']}{params} -> {m['return_type']}")
            if not data["methods"]:
                click.echo("  (none)")

        emit(data, _human, ctx)
    except Exception as exc:
        emit_error(
            ProjectError(
                message=f"Failed to read script: {exc}",
                code="SCRIPT_READ_ERROR",
                fix="Check the file path",
            ),
            ctx,
        )


# ---------------------------------------------------------------------------
# script list-vars
# ---------------------------------------------------------------------------


@script.command("list-vars")
@click.argument("file_path", type=click.Path(exists=True))
@click.pass_context
def list_vars(ctx: click.Context, file_path: str) -> None:
    """List all variables in a GDScript file.

    Shows var, @export, @onready, and const declarations.

    Examples:

      auto-godot script list-vars scripts/main.gd
    """
    import re
    try:
        path = Path(file_path)
        text = path.read_text(encoding="utf-8")
        lines = text.split("\n")

        variables: list[dict[str, str]] = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Match: var name: Type = value, @export var ..., @onready var ..., const ...
            for prefix in ("@export var ", "@onready var ", "var ", "const "):
                if stripped.startswith(prefix):
                    rest = stripped[len(prefix):]
                    # Extract name
                    name_match = re.match(r'(\w+)', rest)
                    if name_match:
                        kind = "export" if prefix.startswith("@export") else \
                               "onready" if prefix.startswith("@onready") else \
                               "const" if prefix.startswith("const") else "var"
                        variables.append({
                            "name": name_match.group(1),
                            "kind": kind,
                            "declaration": stripped,
                            "line": str(i + 1),
                        })
                    break

        data = {"variables": variables, "count": len(variables), "file": file_path}

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Variables in {data['file']} ({data['count']}):")
            for v in data["variables"]:
                click.echo(f"  L{v['line']}: [{v['kind']}] {v['declaration']}")
            if not data["variables"]:
                click.echo("  (none)")

        emit(data, _human, ctx)
    except Exception as exc:
        emit_error(
            ProjectError(
                message=f"Failed to read script: {exc}",
                code="SCRIPT_READ_ERROR",
                fix="Check the file path",
            ),
            ctx,
        )
