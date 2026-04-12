"""UI static analysis commands (ui validate)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import rich_click as click

from auto_godot.errors import ProjectError
from auto_godot.formats.tscn import GdScene, SceneNode, parse_tscn
from auto_godot.output import check_path, emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def ui(ctx: click.Context) -> None:
    """Static analysis for UI scenes (validate)."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# Godot Control / Container type sets (not full inheritance; covers the types
# users actually reach for when building UI).
# ---------------------------------------------------------------------------

CONTAINER_TYPES: frozenset[str] = frozenset({
    "Container", "BoxContainer", "VBoxContainer", "HBoxContainer",
    "GridContainer", "MarginContainer", "CenterContainer",
    "PanelContainer", "TabContainer", "SplitContainer",
    "HSplitContainer", "VSplitContainer", "ScrollContainer",
    "FlowContainer", "HFlowContainer", "VFlowContainer",
    "AspectRatioContainer", "SubViewportContainer",
})

BOX_CONTAINER_TYPES: frozenset[str] = frozenset({
    "BoxContainer", "VBoxContainer", "HBoxContainer",
})

BUTTON_TYPES: frozenset[str] = frozenset({
    "Button", "CheckBox", "CheckButton", "MenuButton", "OptionButton",
    "LinkButton", "TextureButton", "ColorPickerButton",
})

LABEL_TYPES: frozenset[str] = frozenset({"Label", "RichTextLabel"})

INTERACTIVE_TYPES: frozenset[str] = BUTTON_TYPES | frozenset({
    "LineEdit", "TextEdit", "SpinBox", "OptionButton",
    "HSlider", "VSlider", "ColorPicker",
})

# A sampled list of concrete Control descendants we recognize. Used only for
# check #9 (theme override on wrong type). A node whose type is not in this
# set is ignored by the check to avoid false positives on custom classes.
CONTROL_TYPES: frozenset[str] = CONTAINER_TYPES | BUTTON_TYPES | LABEL_TYPES | frozenset({
    "Control", "Panel", "Node2DContainer",
    "LineEdit", "TextEdit", "ProgressBar", "SpinBox",
    "HSlider", "VSlider", "HScrollBar", "VScrollBar",
    "TextureRect", "NinePatchRect", "ColorRect", "ReferenceRect",
    "Tree", "ItemList", "GraphEdit", "GraphNode", "CodeEdit",
})

# Valid size_flags bitfield values. BitField: FILL=1, EXPAND=2, SHRINK_CENTER=4,
# SHRINK_END=8. EXPAND|SHRINK_CENTER (6) and EXPAND|SHRINK_END (10) combine,
# but FILL|SHRINK_* (5, 9) and SHRINK_CENTER|SHRINK_END (12) are contradictory.
VALID_SIZE_FLAGS: frozenset[int] = frozenset({0, 1, 2, 3, 4, 6, 8, 10})

# Theme override prefixes keyed by the Control type family that owns them.
# Used for check #9. Overrides not in a node's family are reported.
THEME_FAMILIES: dict[str, frozenset[str]] = {
    "Label": frozenset({"font_color", "font_shadow_color", "font_outline_color",
                        "font", "font_size", "line_spacing", "shadow_offset_x",
                        "shadow_offset_y", "shadow_outline_size", "outline_size"}),
    "Button": frozenset({"font_color", "font_pressed_color", "font_hover_color",
                         "font_disabled_color", "font_focus_color",
                         "font_hover_pressed_color", "font", "font_size",
                         "outline_size", "font_outline_color", "icon_max_width",
                         "h_separation", "icon_normal_color", "normal", "pressed",
                         "hover", "disabled", "focus"}),
    "ScrollContainer": frozenset({"panel", "h_separation", "v_separation"}),
    "PanelContainer": frozenset({"panel"}),
    "Container": frozenset({"h_separation", "v_separation", "separation",
                            "margin_left", "margin_top", "margin_right",
                            "margin_bottom"}),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node_path(node: SceneNode, root_name: str) -> str:
    """Build a human path like ``Root/VBox/MyButton`` from a SceneNode."""
    if node.parent is None:
        return node.name
    if node.parent == ".":
        return f"{root_name}/{node.name}"
    return f"{root_name}/{node.parent}/{node.name}"


def _build_parent_map(scene: GdScene) -> tuple[dict[str, SceneNode], list[SceneNode]]:
    """Return (name->node map using '.' or 'Parent/Child' key, root_nodes)."""
    by_key: dict[str, SceneNode] = {}
    roots: list[SceneNode] = []
    for n in scene.nodes:
        if n.parent is None:
            roots.append(n)
            by_key[n.name] = n
        else:
            key = n.name if n.parent == "." else f"{n.parent}/{n.name}"
            by_key[key] = n
    return by_key, roots


def _parent_type(node: SceneNode, scene: GdScene, root: SceneNode | None) -> str | None:
    """Return the ``type`` string of ``node``'s parent, or None."""
    if node.parent is None:
        return None
    if node.parent == "." and root is not None:
        return root.type
    # node.parent is a path like "VBox" or "VBox/Panel". Match final segment
    # against scene nodes by their relative-path key.
    for n in scene.nodes:
        if n.parent is None:
            continue
        key = n.name if n.parent == "." else f"{n.parent}/{n.name}"
        if key == node.parent:
            return n.type
    return None


def _siblings(node: SceneNode, scene: GdScene) -> list[SceneNode]:
    """Return other nodes with the same ``parent`` value, preserving order."""
    return [n for n in scene.nodes if n is not node and n.parent == node.parent]


def _has_property(node: SceneNode, key: str) -> bool:
    return key in node.properties


def _prop(node: SceneNode, key: str, default: Any = None) -> Any:
    return node.properties.get(key, default)


def _is_control_family(type_name: str | None) -> bool:
    if type_name is None:
        return False
    return type_name in CONTROL_TYPES


def _vector_x_is_zero(value: Any) -> bool:
    """True if ``value`` is missing, a Vector2 with x==0, or unparseable."""
    if value is None:
        return True
    x = getattr(value, "x", None)
    if x is None:
        txt = str(value)
        if "Vector2(" in txt:
            try:
                inner = txt.split("Vector2(", 1)[1].rsplit(")", 1)[0]
                x = float(inner.split(",", 1)[0].strip())
            except (ValueError, IndexError):
                return True
        else:
            return True
    try:
        return float(x) == 0.0
    except (TypeError, ValueError):
        return True


# ---------------------------------------------------------------------------
# Individual checks. Each returns a list of findings dicts.
# ---------------------------------------------------------------------------

def _finding(
    severity: str, code: str, scene_path: str, node_path: str,
    message: str, fix: str,
) -> dict[str, Any]:
    return {
        "severity": severity, "code": code, "scene": scene_path,
        "node": node_path, "message": message, "fix": fix,
    }


_ANCHOR_KEYS = ("anchor_left", "anchor_top", "anchor_right", "anchor_bottom")
_OFFSET_KEYS = ("offset_left", "offset_top", "offset_right", "offset_bottom")


def _check_container_child_anchor(
    node: SceneNode, parent_type: str | None, scene_path: str, path: str,
) -> list[dict[str, Any]]:
    if parent_type not in CONTAINER_TYPES:
        return []
    if not _is_control_family(node.type):
        return []
    bad = [k for k in _ANCHOR_KEYS + _OFFSET_KEYS if _has_property(node, k)]
    if not bad:
        return []
    return [_finding(
        "warning", "container-child-anchor", scene_path, path,
        f"Control under Container has manual anchor/offset overrides "
        f"({', '.join(bad)}). Containers overwrite these every layout "
        f"pass, so the values are ignored.",
        "Remove the anchor/offset overrides, or move this node outside "
        "the Container.",
    )]


def _check_invisible_panel_container(
    node: SceneNode, scene_path: str, path: str,
) -> list[dict[str, Any]]:
    if node.type != "PanelContainer":
        return []
    has_override = any(
        k.startswith("theme_override_styles/") or k == "theme"
        for k in node.properties
    )
    if has_override:
        return []
    return [_finding(
        "warning", "invisible-panel-container", scene_path, path,
        "PanelContainer has no theme or theme_override_styles/panel. "
        "It renders invisible. If you expected a visible frame, assign "
        "a StyleBox.",
        "Add `theme_override_styles/panel = SubResource(...)` or assign "
        "a Theme that styles PanelContainer.",
    )]


def _check_size_flags_bitfield(
    node: SceneNode, scene_path: str, path: str,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for axis in ("horizontal", "vertical"):
        key = f"size_flags_{axis}"
        if not _has_property(node, key):
            continue
        raw = _prop(node, key)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value not in VALID_SIZE_FLAGS:
            findings.append(_finding(
                "warning", "size-flags-nonsense", scene_path, path,
                f"{key}={value} is not a valid bitfield combination. "
                f"Valid values: 0 (FILL), 1 (EXPAND), 2 (EXPAND|FILL), "
                f"3 (FILL|EXPAND), 4 (SHRINK_CENTER), 6 (EXPAND|SHRINK_CENTER), "
                f"8 (SHRINK_END), 10 (EXPAND|SHRINK_END).",
                f"Set {key} to one of 0, 1, 2, 3, 4, 6, 8, 10.",
            ))
    return findings


def _check_box_child_collapse(
    node: SceneNode, parent_type: str | None, scene_path: str, path: str,
) -> list[dict[str, Any]]:
    if parent_type not in BOX_CONTAINER_TYPES:
        return []
    if not _is_control_family(node.type):
        return []
    axis = "horizontal" if parent_type == "HBoxContainer" else "vertical"
    if parent_type == "BoxContainer":
        axis = "horizontal"
    key = f"size_flags_{axis}"
    raw = node.properties.get(key, 1)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return []
    # FILL=1 is the default and is fine; 0 means no flags (min size); EXPAND
    # bit (2) must be set for the child to consume leftover space.
    if value & 2:
        return []
    if value == 0:
        return [_finding(
            "warning", "box-child-collapsed", scene_path, path,
            f"Child of {parent_type} has {key}=0 (no flags). The child "
            f"collapses to its minimum size in the box axis and will not "
            f"expand to fill available space.",
            f"Set {key} = 3 (FILL + EXPAND) to have the child fill the axis.",
        )]
    return []


def _check_button_ignores_mouse(
    node: SceneNode, scene_path: str, path: str,
) -> list[dict[str, Any]]:
    if node.type not in BUTTON_TYPES:
        return []
    try:
        mf = int(_prop(node, "mouse_filter", 0))
    except (TypeError, ValueError):
        return []
    if mf != 2:
        return []
    return [_finding(
        "error", "button-mouse-ignore", scene_path, path,
        f"{node.type} has mouse_filter=2 (IGNORE). It will never receive "
        f"click events.",
        "Remove the mouse_filter override, or set mouse_filter=0 (STOP) "
        "or 1 (PASS) so the button can be clicked.",
    )]


def _check_overlay_blocks_input(
    node: SceneNode, scene: GdScene, scene_path: str, path: str,
) -> list[dict[str, Any]]:
    """Flag later-sibling Controls that span the full parent rect and don't
    set mouse_filter=IGNORE, with earlier interactive siblings behind them.
    """
    if not _is_control_family(node.type):
        return []
    # Must have full-rect anchors or anchors_preset=15.
    is_full = False
    try:
        preset = int(_prop(node, "anchors_preset", -1))
        if preset == 15:
            is_full = True
    except (TypeError, ValueError):
        pass
    if not is_full:
        try:
            if (float(_prop(node, "anchor_left", 0)) == 0
                and float(_prop(node, "anchor_top", 0)) == 0
                and float(_prop(node, "anchor_right", 0)) == 1
                and float(_prop(node, "anchor_bottom", 0)) == 1):
                is_full = True
        except (TypeError, ValueError):
            pass
    if not is_full:
        return []
    try:
        mf = int(_prop(node, "mouse_filter", 0))
    except (TypeError, ValueError):
        mf = 0
    if mf == 2:
        return []
    # Look for earlier interactive siblings in document order.
    index = scene.nodes.index(node)
    earlier_interactive = [
        s for s in scene.nodes[:index]
        if s.parent == node.parent and s.type in INTERACTIVE_TYPES
    ]
    if not earlier_interactive:
        return []
    return [_finding(
        "warning", "overlay-blocks-input", scene_path, path,
        f"{node.type} with full-rect anchors and mouse_filter={mf} "
        f"(non-IGNORE) is a later sibling of interactive nodes "
        f"({', '.join(s.name for s in earlier_interactive)}). Later "
        f"siblings render on top and will swallow clicks.",
        "Set mouse_filter=2 (IGNORE) on this overlay, or move it earlier "
        "in the scene tree.",
    )]


def _check_label_autowrap(
    node: SceneNode, scene_path: str, path: str,
) -> list[dict[str, Any]]:
    if node.type not in LABEL_TYPES:
        return []
    raw = _prop(node, "autowrap_mode")
    if raw is None:
        return []
    try:
        mode = int(raw)
    except (TypeError, ValueError):
        return []
    if mode == 0:
        return []
    min_x_zero = _vector_x_is_zero(_prop(node, "custom_minimum_size"))
    if not min_x_zero:
        return []
    if not _vector_x_is_zero(_prop(node, "size")):
        return []
    return [_finding(
        "warning", "autowrap-zero-width", scene_path, path,
        f"{node.type} has autowrap_mode={mode} but custom_minimum_size.x "
        f"is 0 and no explicit size is set. Autowrap has no width to wrap "
        f"against so the text will not wrap.",
        "Set custom_minimum_size = Vector2(<width>, 0) or place the "
        "Label under a Container that supplies a width.",
    )]


def _check_scroll_container_child(
    node: SceneNode, parent_type: str | None, scene_path: str, path: str,
) -> list[dict[str, Any]]:
    if parent_type != "ScrollContainer":
        return []
    if not _is_control_family(node.type):
        return []
    try:
        h = int(_prop(node, "size_flags_horizontal", 1))
        v = int(_prop(node, "size_flags_vertical", 1))
    except (TypeError, ValueError):
        return []
    if h == 3 or v == 3:
        return []
    return [_finding(
        "warning", "scroll-child-collapse", scene_path, path,
        f"Child of ScrollContainer has "
        f"size_flags_horizontal={h}, size_flags_vertical={v}. Without "
        f"FILL+EXPAND (3) on at least one axis, the content collapses "
        f"inside the scroll region.",
        "Set size_flags_horizontal=3 and size_flags_vertical=3 on the "
        "scroll content.",
    )]


def _check_theme_override_family(
    node: SceneNode, scene_path: str, path: str,
) -> list[dict[str, Any]]:
    if node.type not in CONTROL_TYPES:
        return []
    findings: list[dict[str, Any]] = []
    for key in node.properties:
        if "/" not in key:
            continue
        if not key.startswith("theme_override_"):
            continue
        _, leaf = key.split("/", 1)
        if node.type == "Label" and leaf in THEME_FAMILIES["Label"]:
            continue
        if node.type in BUTTON_TYPES and leaf in THEME_FAMILIES["Button"]:
            continue
        if node.type == "ScrollContainer" and leaf in THEME_FAMILIES["ScrollContainer"]:
            continue
        if node.type == "PanelContainer" and leaf in THEME_FAMILIES["PanelContainer"]:
            continue
        if node.type in CONTAINER_TYPES and leaf in THEME_FAMILIES["Container"]:
            continue
        # If we don't know the family, skip rather than false-positive.
        expected = (
            THEME_FAMILIES.get(node.type)
            or (THEME_FAMILIES.get("Container") if node.type in CONTAINER_TYPES else None)
        )
        if expected is None:
            continue
        findings.append(_finding(
            "warning", "theme-override-mismatch", scene_path, path,
            f"{node.type} has theme override `{key}` which is not a "
            f"recognized property for this node type. It will be ignored "
            f"at runtime.",
            f"Remove `{key}`, or move the override to a node type that "
            "uses it.",
        ))
    return findings


CHECKS = (
    "container-child-anchor",
    "invisible-panel-container",
    "size-flags-nonsense",
    "box-child-collapsed",
    "button-mouse-ignore",
    "overlay-blocks-input",
    "autowrap-zero-width",
    "scroll-child-collapse",
    "theme-override-mismatch",
)


def _run_checks(scene: GdScene, scene_path: str) -> list[dict[str, Any]]:
    _by_key, roots = _build_parent_map(scene)
    root = roots[0] if roots else None
    root_name = root.name if root is not None else "(no-root)"
    out: list[dict[str, Any]] = []
    for node in scene.nodes:
        ptype = _parent_type(node, scene, root)
        path = _node_path(node, root_name)
        out.extend(_check_container_child_anchor(node, ptype, scene_path, path))
        out.extend(_check_invisible_panel_container(node, scene_path, path))
        out.extend(_check_size_flags_bitfield(node, scene_path, path))
        out.extend(_check_box_child_collapse(node, ptype, scene_path, path))
        out.extend(_check_button_ignores_mouse(node, scene_path, path))
        out.extend(_check_overlay_blocks_input(node, scene, scene_path, path))
        out.extend(_check_label_autowrap(node, scene_path, path))
        out.extend(_check_scroll_container_child(node, ptype, scene_path, path))
        out.extend(_check_theme_override_family(node, scene_path, path))
    return out


# ---------------------------------------------------------------------------
# ui validate
# ---------------------------------------------------------------------------


@ui.command("validate")
@click.argument("scene_path", type=click.Path())
@click.pass_context
def validate_ui(ctx: click.Context, scene_path: str) -> None:
    """Statically analyze a .tscn scene for common UI-layout mistakes.

    Checks run over the scene tree without invoking Godot:

    \b
      container-child-anchor     Control under Container with manual anchors
      invisible-panel-container  PanelContainer with no StyleBox
      size-flags-nonsense        size_flags_* with invalid bitfield value
      box-child-collapsed        VBox/HBox child with size_flags=0
      button-mouse-ignore        Button with mouse_filter=IGNORE
      overlay-blocks-input       Full-rect later sibling swallowing clicks
      autowrap-zero-width        Label autowrap with no width to wrap against
      scroll-child-collapse      ScrollContainer child without FILL+EXPAND
      theme-override-mismatch    theme_override_* on wrong node type

    Exit code: 0 clean, 1 warnings only, 2 errors present.

    Examples:

      auto-godot ui validate scenes/main.tscn

      auto-godot --json ui validate scenes/hud.tscn
    """
    try:
        if not check_path(scene_path, ctx, "scene"):
            return
        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene = parse_tscn(text)
        findings = _run_checks(scene, scene_path)

        errors = [f for f in findings if f["severity"] == "error"]
        warnings = [f for f in findings if f["severity"] == "warning"]

        data: dict[str, Any] = {
            "scene": scene_path,
            "findings": findings,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "checks_run": list(CHECKS),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            if not data["findings"]:
                click.echo(f"Clean: {data['scene']} "
                           f"({len(data['checks_run'])} checks passed)")
                return
            click.echo(
                f"{data['scene']}: {data['error_count']} error(s), "
                f"{data['warning_count']} warning(s)"
            )
            for f in data["findings"]:
                label = "ERROR" if f["severity"] == "error" else "WARN "
                click.echo(f"  [{label}] {f['code']} @ {f['node']}")
                click.echo(f"         {f['message']}")
                if verbose:
                    click.echo(f"         fix: {f['fix']}")

        emit(data, _human, ctx)

        if errors:
            sys.exit(2)
        if warnings:
            sys.exit(1)
    except ProjectError as exc:
        emit_error(exc, ctx)
