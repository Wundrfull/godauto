"""Particle system creation and configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rich_click as click

from auto_godot.errors import ProjectError
from auto_godot.formats.tres import SubResource
from auto_godot.formats.tscn import (
    SceneNode,
    parse_tscn,
    resolve_parent_path,
    serialize_tscn,
)
from auto_godot.formats.values import Color, SubResourceRef, Vector2
from auto_godot.output import emit, emit_error


class _RawGodotValue:
    """Raw Godot value that bypasses serialize_value quoting."""

    def __init__(self, raw: str) -> None:
        self._raw = raw

    def __str__(self) -> str:
        return self._raw

    def __repr__(self) -> str:
        return self._raw


def _default_particle_texture_subs(
    node_name: str,
) -> tuple[list[SubResource], SubResourceRef]:
    """Create Gradient + GradientTexture2D SubResources for a particle.

    Returns (sub_resources, texture_ref) where texture_ref is a
    SubResourceRef to assign to the particle node's texture property.
    """
    grad_id = f"{node_name}_grad"
    tex_id = f"{node_name}_tex"

    gradient = SubResource(
        type="Gradient",
        id=grad_id,
        properties={
            "colors": _RawGodotValue(
                "PackedColorArray(1, 1, 1, 1, 1, 1, 1, 0)"
            ),
        },
    )
    texture = SubResource(
        type="GradientTexture2D",
        id=tex_id,
        properties={
            "gradient": SubResourceRef(grad_id),
            "fill": 1,
            "fill_from": Vector2(0.5, 0.5),
            "fill_to": Vector2(0.5, 1.0),
        },
    )
    return [gradient, texture], SubResourceRef(tex_id)


@click.group(invoke_without_command=True)
@click.pass_context
def particle(ctx: click.Context) -> None:
    """Create and manage particle effects."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Preset particle configurations
_PARTICLE_PRESETS: dict[str, dict[str, Any]] = {
    "explosion": {
        "emitting": False,
        "amount": 16,
        "lifetime": 0.5,
        "one_shot": True,
        "explosiveness": 1.0,
        "spread": 180.0,
        "gravity": Vector2(0, 0),
        "initial_velocity_min": 80.0,
        "initial_velocity_max": 150.0,
        "scale_amount_min": 1.0,
        "scale_amount_max": 2.0,
        "color": Color(1.0, 0.6, 0.1, 1.0),
    },
    "sparkle": {
        "emitting": True,
        "amount": 8,
        "lifetime": 0.8,
        "one_shot": False,
        "explosiveness": 0.0,
        "spread": 180.0,
        "gravity": Vector2(0, -20),
        "initial_velocity_min": 20.0,
        "initial_velocity_max": 40.0,
        "scale_amount_min": 0.5,
        "scale_amount_max": 1.0,
        "color": Color(1.0, 0.9, 0.3, 1.0),
    },
    "fire": {
        "emitting": True,
        "amount": 20,
        "lifetime": 1.0,
        "one_shot": False,
        "explosiveness": 0.0,
        "spread": 20.0,
        "gravity": Vector2(0, -40),
        "initial_velocity_min": 10.0,
        "initial_velocity_max": 30.0,
        "scale_amount_min": 1.0,
        "scale_amount_max": 2.0,
        "color": Color(1.0, 0.4, 0.1, 0.8),
    },
    "smoke": {
        "emitting": True,
        "amount": 12,
        "lifetime": 2.0,
        "one_shot": False,
        "explosiveness": 0.0,
        "spread": 30.0,
        "gravity": Vector2(0, -15),
        "initial_velocity_min": 5.0,
        "initial_velocity_max": 15.0,
        "scale_amount_min": 1.0,
        "scale_amount_max": 3.0,
        "color": Color(0.5, 0.5, 0.5, 0.4),
    },
    "rain": {
        "emitting": True,
        "amount": 50,
        "lifetime": 1.5,
        "one_shot": False,
        "explosiveness": 0.0,
        "spread": 5.0,
        "gravity": Vector2(0, 200),
        "initial_velocity_min": 100.0,
        "initial_velocity_max": 150.0,
        "scale_amount_min": 0.5,
        "scale_amount_max": 1.0,
        "color": Color(0.7, 0.8, 1.0, 0.6),
    },
    "dust": {
        "emitting": False,
        "amount": 6,
        "lifetime": 0.4,
        "one_shot": True,
        "explosiveness": 0.8,
        "spread": 60.0,
        "gravity": Vector2(0, 20),
        "initial_velocity_min": 20.0,
        "initial_velocity_max": 40.0,
        "scale_amount_min": 0.5,
        "scale_amount_max": 1.0,
        "color": Color(0.8, 0.7, 0.6, 0.5),
    },
}


@particle.command("add")
@click.option(
    "--scene", "scene_path", required=True,
    type=click.Path(exists=True),
    help="Path to the .tscn scene file",
)
@click.option(
    "--name", "node_name", required=True,
    help="Name for the particle node",
)
@click.option(
    "--preset", "preset_name", default=None,
    type=click.Choice(sorted(_PARTICLE_PRESETS)),
    help="Use a built-in particle preset",
)
@click.option(
    "--parent", "parent_path", default=None,
    help="Parent node path (default: root)",
)
@click.option(
    "--amount", default=None, type=int,
    help="Number of particles (overrides preset)",
)
@click.option(
    "--lifetime", default=None, type=float,
    help="Particle lifetime in seconds (overrides preset)",
)
@click.option(
    "--one-shot/--continuous", default=None,
    help="One-shot or continuous emission (overrides preset)",
)
@click.pass_context
def add(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    preset_name: str | None,
    parent_path: str | None,
    amount: int | None,
    lifetime: float | None,
    one_shot: bool | None,
) -> None:
    """Add a CPUParticles2D node to a scene.

    Examples:

      auto-godot particle add --scene scenes/main.tscn --name Explosion --preset explosion

      auto-godot particle add --scene scenes/player.tscn --name DustTrail --preset dust --parent Player

      auto-godot particle add --scene scenes/fx.tscn --name Custom --amount 32 --lifetime 2.0 --continuous
    """
    try:
        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")
        scene = parse_tscn(text)

        parent = resolve_parent_path(scene.nodes, parent_path) if parent_path else "."

        for node in scene.nodes:
            if node.name == node_name and node.parent == parent:
                raise ProjectError(
                    message=f"Node '{node_name}' already exists",
                    code="NODE_EXISTS",
                    fix="Choose a different name",
                )

        # Start from preset or defaults
        if preset_name:
            props = dict(_PARTICLE_PRESETS[preset_name])
        else:
            props = {
                "emitting": False,
                "amount": 8,
                "lifetime": 1.0,
                "one_shot": False,
                "spread": 45.0,
                "gravity": Vector2(0, 98),
                "initial_velocity_min": 10.0,
                "initial_velocity_max": 30.0,
                "color": Color(1.0, 1.0, 1.0, 1.0),
            }

        # Apply overrides
        if amount is not None:
            props["amount"] = amount
        if lifetime is not None:
            props["lifetime"] = lifetime
        if one_shot is not None:
            props["one_shot"] = one_shot
            if one_shot:
                props["emitting"] = False

        # Add default particle texture (radial white-to-transparent gradient)
        tex_subs, tex_ref = _default_particle_texture_subs(node_name)
        scene.sub_resources.extend(tex_subs)
        props["texture"] = tex_ref

        scene.nodes.append(SceneNode(
            name=node_name,
            type="CPUParticles2D",
            parent=parent,
            properties=props,
        ))

        scene._raw_header = None
        scene._raw_sections = None
        output = serialize_tscn(scene)
        path.write_text(output, encoding="utf-8")

        data = {
            "added": True,
            "name": node_name,
            "preset": preset_name,
            "amount": props.get("amount"),
            "lifetime": props.get("lifetime"),
            "one_shot": props.get("one_shot"),
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            src = f"preset={data['preset']}" if data["preset"] else "custom"
            click.echo(f"Added CPUParticles2D '{data['name']}' ({src})")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


@particle.command("list-presets")
@click.pass_context
def list_presets(ctx: click.Context) -> None:
    """List available particle presets."""
    presets = []
    for name, props in sorted(_PARTICLE_PRESETS.items()):
        presets.append({
            "name": name,
            "amount": props["amount"],
            "lifetime": props["lifetime"],
            "one_shot": props["one_shot"],
        })

    data = {"presets": presets, "count": len(presets)}

    def _human(data: dict[str, Any], verbose: bool = False) -> None:
        click.echo(f"Particle presets ({data['count']}):")
        for p in data["presets"]:
            mode = "one-shot" if p["one_shot"] else "continuous"
            click.echo(f"  {p['name']:12s} {p['amount']:3d} particles, {p['lifetime']}s ({mode})")

    emit(data, _human, ctx)
