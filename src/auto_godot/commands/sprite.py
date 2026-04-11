"""Sprite sheet and SpriteFrames tools."""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import rich_click as click

from auto_godot.errors import AutoGodotError, ValidationError
from auto_godot.formats.aseprite import (
    AniDirection,
    AsepriteTag,
    parse_aseprite_json,
)
from auto_godot.formats.tres import (
    ExtResource,
    GdResource,
    serialize_tres_file,
)
from auto_godot.formats.uid import generate_resource_id, generate_uid, uid_to_text
from auto_godot.output import emit, emit_error
from auto_godot.sprite.spriteframes import build_animation_for_tag


@click.group(invoke_without_command=True)
@click.pass_context
def sprite(ctx: click.Context) -> None:
    """Sprite sheet and SpriteFrames tools."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@sprite.command("import-aseprite")
@click.argument("json_file", type=click.Path(exists=False))
@click.option(
    "-o", "--output",
    type=click.Path(),
    default=None,
    help="Output .tres path. Default: replaces .json with .tres.",
)
@click.option(
    "--res-path",
    type=str,
    default=None,
    help="Godot res:// path for the sprite sheet texture. "
         "Default: res://<image filename from JSON>.",
)
@click.pass_context
def import_aseprite(
    ctx: click.Context,
    json_file: str,
    output: str | None,
    res_path: str | None,
) -> None:
    r"""Convert Aseprite JSON sprite sheet exports to Godot SpriteFrames .tres resources.

    Reads an Aseprite JSON metadata file (exported with --format json-array or
    --format json-hash) and generates a valid Godot SpriteFrames resource file.

    \b
    ASEPRITE EXPORT SETTINGS (recommended):
      aseprite -b input.ase --sheet sheet.png --data sheet.json \
        --format json-array --sheet-type packed

    \b
    OPTIONS:
      --format json-array    (recommended, preserves frame order)
      --sheet-type packed    (or horizontal/vertical/rows/columns)
      --trim                 (optional; trimmed sprites are fully supported)
      --list-tags            (includes animation tags in JSON output)

    \b
    COMMON PITFALLS:
      1. Missing --list-tags: animations require frameTags in the JSON.
         Without --list-tags, all frames become a single "default" animation.
      2. Wrong --format: json-hash keys may reorder frames. Use json-array.
      3. Duplicate tag names: Godot requires unique animation names.

    \b
    EXAMPLES:
      auto-godot sprite import-aseprite character.json
      auto-godot sprite import-aseprite character.json -o sprites/character.tres
      auto-godot sprite import-aseprite character.json --res-path res://art/character.png
    """
    try:
        _do_import_aseprite(ctx, json_file, output, res_path)
    except Exception as exc:
        emit_error(
            AutoGodotError(
                message=f"Unexpected error: {exc}",
                code="INTERNAL_ERROR",
                fix="Report this issue with the full command and input file",
            ),
            ctx,
        )


def _do_import_aseprite(
    ctx: click.Context,
    json_file: str,
    output: str | None,
    res_path: str | None,
) -> None:
    """Inner implementation of import-aseprite, wrapped for error handling."""
    json_path = Path(json_file)
    if not json_path.exists():
        emit_error(
            AutoGodotError(
                message=f"File not found: {json_file}",
                code="FILE_NOT_FOUND",
                fix="Check the path to your Aseprite JSON export",
            ),
            ctx,
        )
        return

    # Capture warnings from parser (e.g. skipped tags with invalid directions)
    warnings_list: list[str] = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            aseprite_data = parse_aseprite_json(json_path)
            for w in caught:
                msg = str(w.message)
                warnings_list.append(msg)
                click.echo(msg, err=True)
    except (ValidationError, AutoGodotError) as exc:
        emit_error(exc, ctx)
        return

    # If parser skipped tags and none remain, all tags failed (D-17)
    had_skipped_tags = any("Skipping tag" in w for w in warnings_list)
    no_valid_tags = len(aseprite_data.meta.frame_tags) == 0
    if had_skipped_tags and no_valid_tags:
        emit_error(
            AutoGodotError(
                message="All animation tags failed to process",
                code="SPRITE_ALL_TAGS_FAILED",
                fix="Check the Aseprite JSON for valid frame tags",
            ),
            ctx,
        )
        return

    # Explicit zero-frames check so the warning is always in structured output
    if len(aseprite_data.frames) == 0:
        warnings_list.append(
            "Aseprite JSON contains zero frames; the generated SpriteFrames "
            "will have no animation data"
        )

    # Warn when frames have non-uniform sizes (causes animation jitter)
    if len(aseprite_data.frames) > 1:
        sizes = {(f.frame.w, f.frame.h) for f in aseprite_data.frames}
        if len(sizes) > 1:
            size_list = ", ".join(f"{w}x{h}" for w, h in sorted(sizes))
            warnings_list.append(
                f"Frames have non-uniform sizes ({size_list}); "
                "this may cause animation jitter. "
                "Re-export with --no-trim to fix."
            )

    image_res_path = _resolve_image_path(
        res_path, aseprite_data.meta.image, output,
    )

    result = _build_resource(aseprite_data, image_res_path, warnings_list, ctx)
    if result is None:
        return

    resource, successful_animations, all_sub_resources = result
    output_path = _resolve_output_path(output, json_path)
    serialize_tres_file(resource, output_path)
    _emit_result(
        ctx, output_path, successful_animations,
        all_sub_resources, image_res_path, warnings_list,
    )


def _find_project_root(start: Path) -> Path | None:
    """Walk up from start to find a directory containing project.godot."""
    current = start.resolve()
    for parent in [current] + list(current.parents):
        if (parent / "project.godot").exists():
            return parent
    return None


def _resolve_image_path(
    res_path: str | None, meta_image: str, output: str | None
) -> str:
    """Determine the Godot res:// path for the sprite sheet texture.

    Priority: explicit --res-path > inferred from output path relative to
    project root > inferred from output directory > flat filename.
    When an output path is given, the function locates project.godot and
    computes the res:// path relative to the project root so that agents
    get correct paths regardless of CWD or absolute/relative output paths.
    """
    if res_path is not None:
        return res_path

    image_name = Path(meta_image).name

    if output is not None:
        output_path = Path(output).resolve()
        output_dir = output_path.parent

        # Try to find project root and compute res:// path relative to it
        project_root = _find_project_root(output_dir)
        if project_root is not None:
            try:
                rel = (output_dir / image_name).relative_to(project_root)
                return "res://" + rel.as_posix()
            except ValueError:
                pass

        # Fallback: use the output path as given (relative paths only)
        if not Path(output).is_absolute():
            out_dir = Path(output).parent
            if str(out_dir) != ".":
                return "res://" + (out_dir / image_name).as_posix()

    return "res://" + image_name


def _resolve_output_path(output: str | None, json_path: Path) -> Path:
    """Determine the output .tres path."""
    if output is not None:
        return Path(output)
    return json_path.with_suffix(".tres")


def _build_resource(
    aseprite_data: Any,
    image_res_path: str,
    warnings_list: list[str],
    ctx: click.Context,
) -> tuple[GdResource, list[dict[str, Any]], list[Any]] | None:
    """Build the SpriteFrames GdResource with per-tag error handling."""
    from auto_godot.formats.tres import SubResource

    tags = list(aseprite_data.meta.frame_tags)
    if not tags:
        tags = [AsepriteTag(
            name="default", from_frame=0,
            to_frame=len(aseprite_data.frames) - 1,
            direction=AniDirection.FORWARD, repeat=0,
        )]

    # Omit UID so Godot assigns its own on first import. Random UIDs
    # cause "invalid UID" warnings and break resource loading (#20).
    ext = ExtResource(
        type="Texture2D",
        path=image_res_path,
        id=generate_resource_id("Texture2D"),
        uid=None,
    )

    successful_animations: list[dict[str, Any]] = []
    all_sub_resources: list[SubResource] = []

    for tag in tags:
        try:
            tag_subs, anim_dict = build_animation_for_tag(
                tag, aseprite_data.frames, ext,
            )
            all_sub_resources.extend(tag_subs)
            successful_animations.append(anim_dict)
        except (AutoGodotError, Exception) as exc:
            msg = f"Skipping animation '{tag.name}': {exc}"
            click.echo(msg, err=True)
            warnings_list.append(msg)

    if not successful_animations:
        emit_error(
            AutoGodotError(
                message="All animation tags failed to process",
                code="SPRITE_ALL_TAGS_FAILED",
                fix="Check the Aseprite JSON for valid frame tags",
            ),
            ctx,
        )
        return None

    resource = GdResource(
        type="SpriteFrames", format=3,
        uid=uid_to_text(generate_uid()),
        load_steps=None,
        ext_resources=[ext],
        sub_resources=all_sub_resources,
        resource_properties={"animations": successful_animations},
    )
    return (resource, successful_animations, all_sub_resources)


def _print_import_result(data: dict[str, Any], verbose: bool = False) -> None:
    """Display import result in human-readable format."""
    output = data["output_path"]
    anims = data["animation_count"]
    frames = data["frame_count"]
    click.echo(f"Created {output} with {anims} animation(s) ({frames} frames)")
    if data.get("warnings"):
        for warning in data["warnings"]:
            click.echo(f"  Warning: {warning}", err=True)


def _emit_result(
    ctx: click.Context,
    output_path: Path,
    successful_animations: list[dict[str, Any]],
    all_sub_resources: list[Any],
    image_res_path: str,
    warnings_list: list[str],
) -> None:
    """Emit the import result in JSON or human format."""
    data: dict[str, Any] = {
        "output_path": str(output_path),
        "animation_count": len(successful_animations),
        "frame_count": len(all_sub_resources),
        "image_path": image_res_path,
        "warnings": warnings_list,
    }
    emit(data, _print_import_result, ctx)


# ---------------------------------------------------------------------------
# sprite import-texturepacker
# ---------------------------------------------------------------------------


@sprite.command("import-texturepacker")
@click.argument("json_file", type=click.Path(exists=True))
@click.option(
    "-o", "--output", type=click.Path(), default=None,
    help="Output .tres path. Default: replaces .json with .tres.",
)
@click.option(
    "--res-path", type=str, default=None,
    help="Godot res:// path for the atlas texture.",
)
@click.option(
    "--fps", type=float, default=10.0,
    help="Animation FPS (default: 10). TexturePacker has no duration info.",
)
@click.pass_context
def import_texturepacker(
    ctx: click.Context,
    json_file: str,
    output: str | None,
    res_path: str | None,
    fps: float,
) -> None:
    """Convert TexturePacker JSON atlas exports to Godot SpriteFrames .tres.

    Reads a TexturePacker JSON metadata file and generates a SpriteFrames
    resource. Frames are grouped into animations by filename prefix
    (strips trailing numbers: idle_0, idle_1 -> animation "idle").

    Examples:

      auto-godot sprite import-texturepacker atlas.json

      auto-godot sprite import-texturepacker atlas.json -o sprites/atlas.tres --fps 12
    """
    from auto_godot.formats.texturepacker import (
        group_frames_by_animation,
        parse_texturepacker_json,
    )
    from auto_godot.formats.tres import SubResource

    try:
        json_path = Path(json_file)
        frames, meta_image = parse_texturepacker_json(json_path, fps=fps)

        if not frames:
            emit_error(
                AutoGodotError(
                    message="TexturePacker JSON contains zero frames",
                    code="TEXTUREPACKER_NO_FRAMES",
                    fix="Check the TexturePacker export contains sprite data",
                ),
                ctx,
            )
            return

        image_res_path = _resolve_image_path(res_path, meta_image, output)

        ext = ExtResource(
            type="Texture2D",
            path=image_res_path,
            id=generate_resource_id("Texture2D"),
            uid=None,
        )

        groups = group_frames_by_animation(frames)
        all_sub_resources: list[SubResource] = []
        animations: list[dict[str, Any]] = []

        for anim_name, anim_frames in groups.items():
            tag = AsepriteTag(
                name=anim_name,
                from_frame=0,
                to_frame=len(anim_frames) - 1,
                direction=AniDirection.FORWARD,
                repeat=0,
            )
            tag_subs, anim_dict = build_animation_for_tag(
                tag, anim_frames, ext,
            )
            all_sub_resources.extend(tag_subs)
            animations.append(anim_dict)

        resource = GdResource(
            type="SpriteFrames", format=3,
            uid=uid_to_text(generate_uid()),
            load_steps=None,
            ext_resources=[ext],
            sub_resources=all_sub_resources,
            resource_properties={"animations": animations},
        )

        output_path = _resolve_output_path(output, json_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        serialize_tres_file(resource, output_path)

        data: dict[str, Any] = {
            "output_path": str(output_path),
            "animation_count": len(animations),
            "frame_count": sum(len(fs) for fs in groups.values()),
            "image_path": image_res_path,
            "animations": [str(a.get("name", "")) for a in animations],
            "warnings": [],
        }
        emit(data, _print_import_result, ctx)
    except (ValidationError, AutoGodotError) as exc:
        emit_error(exc, ctx)


@sprite.command("split")
@click.argument("image_file", type=click.Path(exists=False))
@click.option(
    "--frame-size",
    type=str,
    default=None,
    help="Frame size as WxH (e.g., 32x32). Required if no --json-meta.",
)
@click.option(
    "--json-meta",
    type=click.Path(exists=False),
    default=None,
    help="JSON file with frame region definitions.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help="Output .tres path. Default: <image_name>.tres",
)
@click.option(
    "--res-path",
    type=str,
    default=None,
    help="Godot res:// path for the sprite sheet.",
)
@click.option(
    "--fps",
    type=float,
    default=10.0,
    help="Animation FPS for the generated SpriteFrames. Default: 10.",
)
@click.option(
    "--tags-from",
    type=click.Path(exists=False),
    default=None,
    help="Aseprite JSON file to read frameTags from for animation names. "
         "Auto-detected from adjacent .json file if not specified.",
)
@click.pass_context
def split(
    ctx: click.Context,
    image_file: str,
    frame_size: str | None,
    json_meta: str | None,
    output: str | None,
    res_path: str | None,
    fps: float,
    tags_from: str | None,
) -> None:
    """Split a sprite sheet into frames and generate a SpriteFrames .tres."""
    image_path = Path(image_file)
    if not image_path.exists():
        emit_error(
            AutoGodotError(
                message=f"Image file not found: {image_file}",
                code="FILE_NOT_FOUND",
                fix="Check the file path and try again",
            ),
            ctx,
        )
        return

    if frame_size is None and json_meta is None:
        emit_error(
            AutoGodotError(
                message="Either --frame-size or --json-meta is required",
                code="SPRITE_SPLIT_NO_SIZE",
                fix="Provide --frame-size WxH or --json-meta file.json",
            ),
            ctx,
        )
        return

    output_path = Path(output) if output else image_path.with_suffix(".tres")
    image_res = res_path or f"res://{image_path.name}"

    # Resolve tag source: explicit --tags-from, or auto-detect adjacent .json
    tag_data = _resolve_tags(tags_from, image_path)

    try:
        resource = _do_split(
            image_path, frame_size, json_meta, image_res, fps, tag_data,
        )
    except (AutoGodotError, ValidationError) as exc:
        emit_error(exc, ctx)
        return

    serialize_tres_file(resource, output_path)

    anim_count = len(resource.resource_properties.get("animations", []))

    def _human(data: dict, verbose: bool = False) -> None:  # type: ignore[type-arg]
        click.echo(
            f"Created {data['output']} with {data['animation_count']} "
            f"animation(s) ({data['frame_count']} frames)"
        )

    emit(
        {
            "output": str(output_path),
            "frame_count": len(resource.sub_resources),
            "animation_count": anim_count,
            "image": str(image_path),
        },
        _human,
        ctx,
    )


def _resolve_tags(
    tags_from: str | None, image_path: Path
) -> list[dict[str, Any]] | None:
    """Resolve animation tags from --tags-from or auto-detected adjacent JSON.

    Returns a list of raw tag dicts (with name, from, to keys) or None
    if no tag source is available.
    """
    tag_path: Path | None = None
    if tags_from is not None:
        tag_path = Path(tags_from)
        if not tag_path.exists():
            return None
    else:
        # Auto-detect adjacent .json file with same stem
        candidate = image_path.with_suffix(".json")
        if candidate.exists():
            tag_path = candidate

    if tag_path is None:
        return None

    try:
        raw = json.loads(tag_path.read_text(encoding="utf-8"))
        meta = raw.get("meta", {})
        tags = meta.get("frameTags", [])
        if tags:
            return tags
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _do_split(
    image_path: Path,
    frame_size: str | None,
    json_meta: str | None,
    image_res: str,
    fps: float,
    tag_data: list[dict[str, Any]] | None = None,
) -> GdResource:  # type: ignore[return]
    """Dispatch to grid or JSON splitting based on provided options."""
    from auto_godot.sprite.splitter import split_sheet_grid, split_sheet_json

    if frame_size is not None:
        frame_w, frame_h = _parse_frame_size(frame_size)
        resource = split_sheet_grid(
            image_path, frame_w, frame_h, image_res, fps,
        )
    elif json_meta is not None:
        json_path = Path(json_meta)
        if not json_path.exists():
            raise AutoGodotError(
                message=f"JSON metadata file not found: {json_meta}",
                code="FILE_NOT_FOUND",
                fix="Check the JSON file path and try again",
            )
        resource = split_sheet_json(image_path, json_path, image_res, fps)
    else:
        return None  # type: ignore[return-value]

    # Apply tag data to split animations by frame range
    if tag_data and resource is not None:
        _apply_tags_to_resource(resource, tag_data, fps)

    return resource


def _apply_tags_to_resource(
    resource: GdResource,
    tag_data: list[dict[str, Any]],
    fps: float,
) -> None:
    """Replace the single 'default' animation with tagged animations.

    Reads frameTags from Aseprite JSON and slices the sub_resources
    into per-tag animation entries.
    """
    from auto_godot.formats.values import StringName, SubResourceRef

    subs = resource.sub_resources
    animations: list[dict[str, Any]] = []

    for tag in tag_data:
        name = tag.get("name", "default")
        from_idx = tag.get("from", 0)
        to_idx = tag.get("to", len(subs) - 1)

        # Clamp indices to available sub_resources
        from_idx = max(0, min(from_idx, len(subs) - 1))
        to_idx = max(from_idx, min(to_idx, len(subs) - 1))

        frames = [
            {"duration": 1.0, "texture": SubResourceRef(subs[i].id)}
            for i in range(from_idx, to_idx + 1)
        ]
        animations.append({
            "frames": frames,
            "loop": True,
            "name": StringName(name),
            "speed": fps,
        })

    if animations:
        resource.resource_properties["animations"] = animations


def _parse_frame_size(frame_size: str) -> tuple[int, int]:
    """Parse a 'WxH' string into (width, height) integers."""
    parts = frame_size.lower().split("x")
    if len(parts) != 2:
        raise ValidationError(
            message=f"Invalid frame size format: {frame_size}",
            code="INVALID_FRAME_SIZE",
            fix="Use format WxH (e.g., 32x32)",
        )
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError as err:
        raise ValidationError(
            message=f"Invalid frame size values: {frame_size}",
            code="INVALID_FRAME_SIZE",
            fix="Width and height must be integers (e.g., 32x32)",
        ) from err


@sprite.command("create-atlas")
@click.argument("image_files", nargs=-1, required=True, type=click.Path(exists=False))
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    required=True,
    help="Output atlas image path (e.g., atlas.png).",
)
@click.option(
    "--tres-output",
    type=click.Path(),
    default=None,
    help="Output .tres path. Default: <output>.tres (e.g., atlas.tres).",
)
@click.option(
    "--res-path",
    type=str,
    default=None,
    help="Godot res:// path for the atlas texture.",
)
@click.option(
    "--no-pot",
    is_flag=True,
    default=False,
    help="Disable power-of-two atlas dimensions.",
)
@click.pass_context
def create_atlas_cmd(
    ctx: click.Context,
    image_files: tuple[str, ...],
    output: str,
    tres_output: str | None,
    res_path: str | None,
    no_pot: bool,
) -> None:
    """Composite multiple sprite images into a single atlas texture."""
    image_paths = [Path(f) for f in image_files]
    missing = [p for p in image_paths if not p.exists()]
    if missing:
        emit_error(
            AutoGodotError(
                message=f"Image file(s) not found: {', '.join(str(m) for m in missing)}",
                code="FILE_NOT_FOUND",
                fix="Check file paths and try again",
            ),
            ctx,
        )
        return

    output_path = Path(output)
    tres_path = Path(tres_output) if tres_output else output_path.with_suffix(".tres")
    atlas_res = res_path or f"res://{output_path.name}"

    try:
        from auto_godot.sprite.atlas import create_atlas

        atlas_img, resource = create_atlas(
            image_paths, atlas_res, power_of_two=not no_pot
        )
    except (AutoGodotError, ValidationError) as exc:
        emit_error(exc, ctx)
        return

    atlas_img.save(output_path)
    serialize_tres_file(resource, tres_path)

    def _human(data: dict, verbose: bool = False) -> None:  # type: ignore[type-arg]
        click.echo(
            f"Created atlas {data['atlas_output']} "
            f"({data['atlas_width']}x{data['atlas_height']}) "
            f"with {data['image_count']} images, "
            f"tres: {data['tres_output']}"
        )

    emit(
        {
            "atlas_output": str(output_path),
            "tres_output": str(tres_path),
            "image_count": len(image_paths),
            "atlas_width": atlas_img.width,
            "atlas_height": atlas_img.height,
        },
        _human,
        ctx,
    )


@sprite.command("validate")
@click.argument("tres_file", type=click.Path(exists=False))
@click.option(
    "--godot",
    is_flag=True,
    default=False,
    help="Also validate by loading in headless Godot (requires Godot binary).",
)
@click.pass_context
def validate(ctx: click.Context, tres_file: str, godot: bool) -> None:
    """Validate a SpriteFrames .tres resource file.

    Checks structure, animation definitions, frame references, and texture
    references. With --godot, also loads the resource in headless Godot
    to confirm it is valid.
    """
    tres_path = Path(tres_file)
    if not tres_path.exists():
        emit_error(
            AutoGodotError(
                message=f"File not found: {tres_file}",
                code="FILE_NOT_FOUND",
                fix="Check the path to your .tres file",
            ),
            ctx,
        )
        return

    from auto_godot.sprite.validator import (
        validate_spriteframes,
        validate_spriteframes_headless,
    )

    result = validate_spriteframes(tres_path)

    if godot:
        from auto_godot.backend import GodotBackend

        config = ctx.obj
        backend = GodotBackend(
            binary_path=config.godot_path if config else None
        )
        result = validate_spriteframes_headless(tres_path, backend)

    # Validate always writes to stdout (both valid and invalid results).
    # This differs from error commands which write to stderr. The validate
    # result is structured data, not an error, so consumers should always
    # read stdout and check the "valid" key regardless of exit code.
    emit(result, _print_validate_result, ctx)

    if not result["valid"]:
        ctx.exit(1)


def _print_validate_result(data: dict[str, Any], verbose: bool = False) -> None:
    """Display validation result in human-readable format."""
    if data["valid"]:
        anims = data.get("animations", [])
        total_frames = sum(a.get("frames", 0) for a in anims)
        click.echo(
            f"Valid SpriteFrames with {len(anims)} animation(s) "
            f"({total_frames} frames)"
        )
        if verbose:
            for anim in anims:
                click.echo(
                    f"  {anim['name']}: {anim['frames']} frames, "
                    f"{anim['speed']} FPS, loop={anim['loop']}"
                )
    else:
        click.echo(
            f"Invalid SpriteFrames: {len(data['issues'])} issue(s)"
        )
        for issue in data["issues"]:
            click.echo(f"  - {issue}")


# ---------------------------------------------------------------------------
# sprite list-animations
# ---------------------------------------------------------------------------


@sprite.command("list-animations")
@click.argument("tres_file", type=click.Path(exists=True))
@click.pass_context
def list_animations(ctx: click.Context, tres_file: str) -> None:
    """List animations in a SpriteFrames .tres resource.

    Examples:

      auto-godot sprite list-animations sprites/character.tres
    """
    from auto_godot.formats.tres import parse_tres_file

    try:
        path = Path(tres_file)
        resource = parse_tres_file(path)

        if resource.type != "SpriteFrames":
            emit_error(
                AutoGodotError(
                    message=f"Not a SpriteFrames resource: {resource.type}",
                    code="INVALID_RESOURCE_TYPE",
                    fix="Provide a SpriteFrames .tres file",
                ),
                ctx,
            )
            return

        animations: list[dict[str, Any]] = []
        for sub in resource.sub_resources:
            if sub.type == "SpriteFrames":
                anim_data = sub.properties.get("animations")
                if anim_data:
                    # Parse animation array from the resource properties
                    pass

        # The animations are stored in the main resource properties
        anim_prop = resource.resource_properties.get("animations")
        if anim_prop and isinstance(anim_prop, list):
            for anim in anim_prop:
                if isinstance(anim, dict):
                    name = anim.get("name", "unknown")
                    if hasattr(name, "value"):
                        name = name.value
                    frames = anim.get("frames", [])
                    frame_count = len(frames) if isinstance(frames, list) else 0
                    speed = anim.get("speed", 5.0)
                    loop = anim.get("loop", True)
                    animations.append({
                        "name": str(name),
                        "frames": frame_count,
                        "speed": speed,
                        "loop": loop,
                    })

        data = {
            "animations": animations,
            "count": len(animations),
            "file": tres_file,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Animations in {data['file']} ({data['count']}):")
            for anim in data["animations"]:
                click.echo(
                    f"  {anim['name']}: {anim['frames']} frames, "
                    f"{anim['speed']} FPS, loop={anim['loop']}"
                )
            if not data["animations"]:
                click.echo("  (none)")

        emit(data, _human, ctx)
    except Exception as exc:
        emit_error(
            AutoGodotError(
                message=f"Failed to read SpriteFrames: {exc}",
                code="PARSE_ERROR",
                fix="Ensure the file is a valid SpriteFrames .tres",
            ),
            ctx,
        )


# ---------------------------------------------------------------------------
# sprite export
# ---------------------------------------------------------------------------

# Aseprite binary path (from CLAUDE.md game dev toolkit)
_DEFAULT_ASEPRITE = r"C:\Program Files (x86)\Steam\steamapps\common\Aseprite\Aseprite.exe"


@sprite.command("export")
@click.argument("aseprite_file", type=click.Path())
@click.option("-o", "--output-dir", type=click.Path(), default=None,
              help="Output directory. Default: same directory as input file.")
@click.option("--aseprite-path", type=click.Path(), default=None, envvar="ASEPRITE_PATH",
              help="Path to Aseprite binary. Default: ASEPRITE_PATH env or standard install.")
@click.option("--sheet-type", type=click.Choice(["packed", "rows", "horizontal", "vertical"]),
              default="packed", help="Sprite sheet layout (default: packed).")
@click.option("--trim/--no-trim", default=False, help="Trim transparent pixels (default: no). Trimming can cause animation jitter from non-uniform frame sizes.")
@click.option("--import-tres/--no-import-tres", "do_import", default=True,
              help="Also generate SpriteFrames .tres (default: yes).")
@click.pass_context
def export_sprite(
    ctx: click.Context,
    aseprite_file: str,
    output_dir: str | None,
    aseprite_path: str | None,
    sheet_type: str,
    trim: bool,
    do_import: bool,
) -> None:
    """Export an Aseprite file to PNG sprite sheet + JSON metadata.

    Calls the Aseprite CLI to export a .aseprite/.ase file into a sprite
    sheet PNG and JSON metadata, then optionally imports to SpriteFrames .tres.

    Requires Aseprite installed. Set ASEPRITE_PATH env var or use --aseprite-path
    if not in the default Steam location.

    Examples:

      auto-godot sprite export art/cookie.aseprite

      auto-godot sprite export art/player.ase -o assets/sprites/player

      auto-godot sprite export art/enemy.aseprite --no-import-tres
    """
    import subprocess

    try:
        ase_path = Path(aseprite_file)
        if not ase_path.exists():
            emit_error(
                AutoGodotError(
                    message=f"Aseprite file not found: {aseprite_file}",
                    code="FILE_NOT_FOUND",
                    fix="Check the path to the .aseprite file",
                ),
                ctx,
            )
            return

        # Find Aseprite binary
        ase_bin = aseprite_path or _DEFAULT_ASEPRITE
        if not Path(ase_bin).exists():
            import shutil
            found = shutil.which("aseprite")
            if found:
                ase_bin = found
            else:
                emit_error(
                    AutoGodotError(
                        message=f"Aseprite not found at: {ase_bin}",
                        code="ASEPRITE_NOT_FOUND",
                        fix="Install Aseprite or set ASEPRITE_PATH environment variable",
                    ),
                    ctx,
                )
                return

        # Determine output paths
        basename = ase_path.stem
        out_dir = Path(output_dir) if output_dir else ase_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        sheet_png = out_dir / f"{basename}_sheet.png"
        sheet_json = out_dir / f"{basename}.json"

        # Build Aseprite CLI command
        cmd = [
            str(ase_bin), "-b", str(ase_path),
            "--sheet", str(sheet_png),
            "--data", str(sheet_json),
            "--format", "json-array",
            "--sheet-type", sheet_type,
            "--list-tags",
        ]
        if trim:
            cmd.append("--trim")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            emit_error(
                AutoGodotError(
                    message=f"Aseprite export failed: {result.stderr.strip()}",
                    code="ASEPRITE_EXPORT_FAILED",
                    fix="Check the Aseprite file and export settings",
                ),
                ctx,
            )
            return

        files_created = [str(sheet_png), str(sheet_json)]

        # Optionally import to SpriteFrames
        tres_path = None
        if do_import and sheet_json.exists():
            tres_path = out_dir / f"{basename}.tres"
            _do_import_aseprite(ctx, str(sheet_json), str(tres_path), None)
            files_created.append(str(tres_path))

        data = {
            "exported": True,
            "source": aseprite_file,
            "files": files_created,
            "sheet": str(sheet_png),
            "json": str(sheet_json),
            "tres": str(tres_path) if tres_path else None,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Exported: {data['source']}")
            for f in data["files"]:
                click.echo(f"  -> {f}")

        emit(data, _human, ctx)
    except subprocess.TimeoutExpired:
        emit_error(
            AutoGodotError(
                message="Aseprite export timed out after 30 seconds",
                code="ASEPRITE_TIMEOUT",
                fix="Try exporting manually or increase timeout",
            ),
            ctx,
        )
    except Exception as exc:
        emit_error(
            AutoGodotError(
                message=f"Export failed: {exc}",
                code="EXPORT_ERROR",
                fix="Check the Aseprite file and installation",
            ),
            ctx,
        )


# ---------------------------------------------------------------------------
# sprite export-all
# ---------------------------------------------------------------------------


@sprite.command("export-all")
@click.argument("source_dir", type=click.Path(), default="art")
@click.option("-o", "--output-dir", type=click.Path(), default="assets/sprites",
              help="Base output directory (default: assets/sprites).")
@click.option("--aseprite-path", type=click.Path(), default=None, envvar="ASEPRITE_PATH",
              help="Path to Aseprite binary.")
@click.option("--import-tres/--no-import-tres", "do_import", default=True,
              help="Also generate SpriteFrames .tres for each.")
@click.pass_context
def export_all(
    ctx: click.Context,
    source_dir: str,
    output_dir: str,
    aseprite_path: str | None,
    do_import: bool,
) -> None:
    """Batch export all Aseprite files from a directory.

    Finds all .aseprite and .ase files in the source directory and
    exports each to a sprite sheet PNG + JSON, organized by name.

    Examples:

      auto-godot sprite export-all

      auto-godot sprite export-all art -o sprites

      auto-godot sprite export-all art --no-import-tres
    """
    try:
        src = Path(source_dir)
        if not src.exists():
            emit_error(
                AutoGodotError(
                    message=f"Source directory not found: {source_dir}",
                    code="DIR_NOT_FOUND",
                    fix="Check the path to the art source directory",
                ),
                ctx,
            )
            return

        files = list(src.glob("*.aseprite")) + list(src.glob("*.ase"))
        if not files:
            emit_error(
                AutoGodotError(
                    message=f"No .aseprite or .ase files found in {source_dir}",
                    code="NO_FILES_FOUND",
                    fix="Ensure the source directory contains Aseprite files",
                ),
                ctx,
            )
            return

        results: list[dict[str, Any]] = []
        for f in sorted(files):
            name = f.stem
            dest = Path(output_dir) / name
            dest.mkdir(parents=True, exist_ok=True)
            # Invoke export for each file
            ctx.invoke(
                export_sprite,
                aseprite_file=str(f),
                output_dir=str(dest),
                aseprite_path=aseprite_path,
                sheet_type="packed",
                trim=True,
                do_import=do_import,
            )
            results.append({"file": str(f), "output": str(dest)})

        data = {
            "exported": len(results),
            "source_dir": source_dir,
            "output_dir": output_dir,
            "files": results,
        }

        def _human(data: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Exported {data['exported']} files from {data['source_dir']}")

        emit(data, _human, ctx)
    except Exception as exc:
        emit_error(
            AutoGodotError(
                message=f"Batch export failed: {exc}",
                code="BATCH_EXPORT_ERROR",
                fix="Check the source directory and Aseprite installation",
            ),
            ctx,
        )
