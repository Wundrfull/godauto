"""Audio resource and bus management for Godot projects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import rich_click as click

from auto_godot.errors import ProjectError
from auto_godot.formats.tscn import (
    ExtResource,
    SceneNode,
    parse_tscn,
    serialize_tscn,
)
from auto_godot.output import emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def audio(ctx: click.Context) -> None:
    """Manage audio resources, players, and bus layouts."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# Valid AudioStreamPlayer types
_PLAYER_TYPES = {"AudioStreamPlayer", "AudioStreamPlayer2D", "AudioStreamPlayer3D"}

# Supported audio file extensions
_AUDIO_EXTENSIONS = {".ogg", ".wav", ".mp3"}


def _find_next_ext_resource_id(scene_text: str) -> str:
    """Find the next available ext_resource ID in a scene."""
    import re
    ids = re.findall(r'id="([^"]+)"', scene_text)
    # Generate a new unique ID
    counter = 1
    while f"{counter}_audio" in ids:
        counter += 1
    return f"{counter}_audio"


@audio.command("add-player")
@click.option(
    "--scene", "scene_path", required=True,
    type=click.Path(exists=True),
    help="Path to the .tscn scene file to modify",
)
@click.option(
    "--name", "node_name", required=True,
    help="Name for the AudioStreamPlayer node",
)
@click.option(
    "--stream", "stream_path", default=None,
    help="res:// path to the audio file (e.g., res://audio/jump.ogg)",
)
@click.option(
    "--type", "player_type", default="AudioStreamPlayer",
    type=click.Choice(sorted(_PLAYER_TYPES), case_sensitive=True),
    help="Player type (default: AudioStreamPlayer)",
)
@click.option(
    "--bus", default="Master",
    help="Audio bus name (default: Master)",
)
@click.option(
    "--volume", "volume_db", default=0.0, type=float,
    help="Volume in dB (default: 0.0)",
)
@click.option(
    "--autoplay/--no-autoplay", default=False,
    help="Enable autoplay (default: off)",
)
@click.option(
    "--parent", "parent_path", default=None,
    help="Parent node path within the scene (default: root node)",
)
@click.pass_context
def add_player(
    ctx: click.Context,
    scene_path: str,
    node_name: str,
    stream_path: str | None,
    player_type: str,
    bus: str,
    volume_db: float,
    autoplay: bool,
    parent_path: str | None,
) -> None:
    """Add an AudioStreamPlayer node to an existing scene.

    Examples:

      auto-godot audio add-player --scene scenes/main.tscn --name BGM --stream res://audio/music.ogg --bus Music --autoplay

      auto-godot audio add-player --scene scenes/player.tscn --name JumpSound --stream res://audio/jump.ogg --type AudioStreamPlayer2D --bus SFX
    """
    try:
        path = Path(scene_path)
        text = path.read_text(encoding="utf-8")

        # Parse the scene to manipulate it
        scene = parse_tscn(text)

        # Check for duplicate node names at the target parent
        for node in scene.nodes:
            if node.name == node_name and node.parent == (parent_path or "."):
                raise ProjectError(
                    message=f"Node '{node_name}' already exists in the scene",
                    code="NODE_EXISTS",
                    fix="Choose a different node name or remove the existing node",
                )

        # Add ext_resource for the audio stream if provided
        ext_resource_id = None
        if stream_path:
            ext_resource_id = _find_next_ext_resource_id(text)
            scene.ext_resources.append(ExtResource(
                type="AudioStream",
                path=stream_path,
                id=ext_resource_id,
                uid=None,
            ))

        # Build node properties
        properties: dict[str, Any] = {}
        if ext_resource_id:
            from auto_godot.formats.values import ExtResourceRef
            properties["stream"] = ExtResourceRef(ext_resource_id)
        if volume_db != 0.0:
            properties["volume_db"] = volume_db
        if bus != "Master":
            from auto_godot.formats.values import StringName
            properties["bus"] = StringName(bus)
        if autoplay:
            properties["autoplay"] = True

        # Determine parent path for the new node
        parent = "." if parent_path is None else parent_path

        # Add the node
        scene.nodes.append(SceneNode(
            name=node_name,
            type=player_type,
            parent=parent,
            properties=properties,
        ))

        # Update load_steps
        if scene.load_steps is not None:
            scene.load_steps = len(scene.ext_resources) + len(scene.sub_resources) + 1

        # Write back (rebuild from model since we modified it)
        scene._raw_header = None
        scene._raw_sections = None
        output = serialize_tscn(scene)
        path.write_text(output, encoding="utf-8")

        data = {
            "added": True,
            "node_name": node_name,
            "player_type": player_type,
            "stream": stream_path,
            "bus": bus,
            "volume_db": volume_db,
            "autoplay": autoplay,
            "scene": scene_path,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            parts = [f"Added {data['player_type']} '{data['node_name']}'"]
            if data["stream"]:
                parts.append(f"stream={data['stream']}")
            parts.append(f"bus={data['bus']}")
            click.echo(" ".join(parts) + f" to {data['scene']}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


@audio.command("create-bus-layout")
@click.option(
    "--bus", "buses", multiple=True, required=True,
    help="Bus definition as 'name:parent' (e.g., 'SFX:Master', 'Music:Master')",
)
@click.argument("output_path", type=click.Path())
@click.pass_context
def create_bus_layout(
    ctx: click.Context,
    buses: tuple[str, ...],
    output_path: str,
) -> None:
    """Generate a Godot audio bus layout .tres file.

    Examples:

      auto-godot audio create-bus-layout --bus "SFX:Master" --bus "Music:Master" audio/bus_layout.tres

      auto-godot audio create-bus-layout --bus "SFX:Master" --bus "Music:Master" --bus "UI:Master" audio/bus_layout.tres
    """
    try:
        parsed = _parse_bus_defs(buses)
        content = _build_bus_layout_tres(parsed)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")

        data = {
            "created": True,
            "path": str(out),
            "buses": [{"name": n, "parent": p} for n, p in parsed],
            "bus_count": len(parsed) + 1,  # +1 for Master
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            names = ["Master"] + [b["name"] for b in data["buses"]]
            click.echo(f"Created bus layout at {data['path']} with buses: {', '.join(names)}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


def _parse_bus_defs(
    buses: tuple[str, ...],
) -> list[tuple[str, str]]:
    """Parse 'name:parent' bus definitions."""
    result: list[tuple[str, str]] = []
    for bus_def in buses:
        if ":" not in bus_def:
            raise ProjectError(
                message=f"Invalid bus format: '{bus_def}'. Expected 'name:parent'",
                code="INVALID_BUS_FORMAT",
                fix="Use format 'name:parent', e.g., 'SFX:Master'",
            )
        name, parent = bus_def.split(":", 1)
        result.append((name.strip(), parent.strip()))
    return result


def _build_bus_layout_tres(buses: list[tuple[str, str]]) -> str:
    """Build a Godot AudioBusLayout .tres file."""
    # Godot's AudioBusLayout stores buses as indexed entries
    lines: list[str] = []
    lines.append('[gd_resource type="AudioBusLayout" format=3]')
    lines.append("")
    lines.append("[resource]")

    for i, (name, parent) in enumerate(buses):
        # Bus indices start at 1 (Master is 0 and implicit)
        idx = i + 1
        lines.append(f'bus/{idx}/name = "{name}"')
        lines.append(f"bus/{idx}/solo = false")
        lines.append(f"bus/{idx}/mute = false")
        lines.append(f"bus/{idx}/bypass_fx = false")
        lines.append(f"bus/{idx}/volume_db = 0.0")
        lines.append(f'bus/{idx}/send = "{parent}"')

    return "\n".join(lines) + "\n"


@audio.command("list-buses")
@click.argument("bus_layout_path", type=click.Path(exists=True))
@click.pass_context
def list_buses(
    ctx: click.Context,
    bus_layout_path: str,
) -> None:
    """List audio buses from a bus layout .tres file."""
    try:
        text = Path(bus_layout_path).read_text(encoding="utf-8")
        buses = _parse_bus_layout(text)

        data = {
            "buses": [{"name": "Master", "index": 0, "send": ""}] + buses,
            "count": len(buses) + 1,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Audio Buses ({data['count']}):")
            for bus in data["buses"]:
                send = f" -> {bus['send']}" if bus.get("send") else ""
                click.echo(f"  [{bus['index']}] {bus['name']}{send}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


def _parse_bus_layout(text: str) -> list[dict[str, Any]]:
    """Parse bus entries from a .tres AudioBusLayout file."""
    import re
    buses: dict[int, dict[str, Any]] = {}

    for match in re.finditer(r'bus/(\d+)/(\w+)\s*=\s*(.+)', text):
        idx = int(match.group(1))
        key = match.group(2)
        value = match.group(3).strip().strip('"')

        if idx not in buses:
            buses[idx] = {"index": idx, "name": "", "send": ""}
        buses[idx][key] = value

    return [buses[i] for i in sorted(buses)]


# ---------------------------------------------------------------------------
# audio generate-placeholder
# ---------------------------------------------------------------------------

# Preset sound types with parameters: (frequency_hz, duration_ms, wave_type)
_SOUND_PRESETS: dict[str, tuple[float, int, str]] = {
    "click": (800.0, 50, "sine"),
    "beep": (440.0, 200, "sine"),
    "coin": (1200.0, 150, "sine"),
    "whoosh": (0.0, 300, "noise"),
    "hurt": (200.0, 200, "sawtooth"),
    "jump": (400.0, 150, "sine_sweep"),
}


@audio.command("generate-placeholder")
@click.option(
    "--type", "sound_type",
    type=click.Choice(list(_SOUND_PRESETS.keys()) + ["tone"]),
    default="beep",
    help="Sound type preset (default: beep).",
)
@click.option(
    "--frequency", type=float, default=None,
    help="Frequency in Hz (overrides preset, used with --type tone).",
)
@click.option(
    "--duration", type=int, default=None,
    help="Duration in milliseconds (overrides preset).",
)
@click.option(
    "--sample-rate", type=int, default=22050,
    help="Sample rate (default: 22050).",
)
@click.argument("output_path", type=click.Path())
@click.pass_context
def generate_placeholder(
    ctx: click.Context,
    sound_type: str,
    frequency: float | None,
    duration: int | None,
    sample_rate: int,
    output_path: str,
) -> None:
    """Generate a placeholder WAV audio file for CLI-only workflows.

    Creates simple synthesized sounds (clicks, beeps, coin sounds, etc.)
    using Python's wave module. No external dependencies required.

    Examples:

      auto-godot audio generate-placeholder assets/audio/click.wav

      auto-godot audio generate-placeholder --type coin assets/audio/coin.wav

      auto-godot audio generate-placeholder --type tone --frequency 880 --duration 500 assets/audio/tone.wav
    """
    import math
    import struct
    import wave

    try:
        # Resolve parameters from preset or overrides
        if sound_type == "tone":
            freq = frequency or 440.0
            dur_ms = duration or 200
            wave_type = "sine"
        else:
            preset_freq, preset_dur, wave_type = _SOUND_PRESETS[sound_type]
            freq = frequency if frequency is not None else preset_freq
            dur_ms = duration if duration is not None else preset_dur

        num_samples = int(sample_rate * dur_ms / 1000)
        samples: list[int] = []

        import random
        for i in range(num_samples):
            t = i / sample_rate
            if wave_type == "noise":
                val = random.uniform(-1.0, 1.0)
            elif wave_type == "sawtooth":
                val = 2.0 * (t * freq - math.floor(t * freq + 0.5))
            elif wave_type == "sine_sweep":
                sweep_freq = freq + (freq * 2 - freq) * (i / num_samples)
                val = math.sin(2.0 * math.pi * sweep_freq * t)
            else:
                val = math.sin(2.0 * math.pi * freq * t)

            # Apply fade-out envelope to avoid clicks
            envelope = 1.0 - (i / num_samples) ** 2
            sample = int(val * envelope * 32767 * 0.8)
            sample = max(-32768, min(32767, sample))
            samples.append(sample)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with wave.open(str(out), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))

        data = {
            "created": True,
            "path": str(out),
            "type": sound_type,
            "frequency": freq,
            "duration_ms": dur_ms,
            "sample_rate": sample_rate,
            "file_size": out.stat().st_size,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(
                f"Generated {data['type']} sound: {data['path']} "
                f"({data['duration_ms']}ms, {data['frequency']}Hz, "
                f"{data['file_size']} bytes)"
            )

        from auto_godot.output import emit
        emit(data, _human, ctx)
    except Exception as exc:
        from auto_godot.errors import AutoGodotError
        from auto_godot.output import emit_error
        emit_error(
            AutoGodotError(
                message=f"Failed to generate audio: {exc}",
                code="AUDIO_GENERATE_FAILED",
                fix="Check the output path and parameters",
            ),
            ctx,
        )
