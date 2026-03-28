"""Sprite sheet and SpriteFrames tools."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Any

import rich_click as click

from gdauto.errors import GdautoError, ValidationError
from gdauto.formats.aseprite import (
    AniDirection,
    AsepriteTag,
    parse_aseprite_json,
)
from gdauto.formats.tres import (
    ExtResource,
    GdResource,
    serialize_tres_file,
)
from gdauto.formats.uid import generate_resource_id, generate_uid, uid_to_text
from gdauto.output import emit, emit_error
from gdauto.sprite.spriteframes import build_animation_for_tag


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
      gdauto sprite import-aseprite character.json
      gdauto sprite import-aseprite character.json -o sprites/character.tres
      gdauto sprite import-aseprite character.json --res-path res://art/character.png
    """
    json_path = Path(json_file)
    if not json_path.exists():
        emit_error(
            GdautoError(
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
                if "Skipping tag" in msg:
                    warnings_list.append(msg)
                    click.echo(msg, err=True)
    except (ValidationError, GdautoError) as exc:
        emit_error(exc, ctx)
        return

    # If parser skipped tags and none remain, all tags failed (D-17)
    had_skipped_tags = len(warnings_list) > 0
    no_valid_tags = len(aseprite_data.meta.frame_tags) == 0
    if had_skipped_tags and no_valid_tags:
        emit_error(
            GdautoError(
                message="All animation tags failed to process",
                code="SPRITE_ALL_TAGS_FAILED",
                fix="Check the Aseprite JSON for valid frame tags",
            ),
            ctx,
        )
        return

    image_res_path = _resolve_image_path(res_path, aseprite_data.meta.image)
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


def _resolve_image_path(res_path: str | None, meta_image: str) -> str:
    """Determine the Godot res:// path for the sprite sheet texture."""
    if res_path is not None:
        return res_path
    return "res://" + meta_image


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
    from gdauto.formats.tres import SubResource

    tags = list(aseprite_data.meta.frame_tags)
    if not tags:
        tags = [AsepriteTag(
            name="default", from_frame=0,
            to_frame=len(aseprite_data.frames) - 1,
            direction=AniDirection.FORWARD, repeat=0,
        )]

    ext = ExtResource(
        type="Texture2D",
        path=image_res_path,
        id=generate_resource_id("Texture2D"),
        uid=uid_to_text(generate_uid()),
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
        except (GdautoError, Exception) as exc:
            msg = f"Skipping animation '{tag.name}': {exc}"
            click.echo(msg, err=True)
            warnings_list.append(msg)

    if not successful_animations:
        emit_error(
            GdautoError(
                message="All animation tags failed to process",
                code="SPRITE_ALL_TAGS_FAILED",
                fix="Check the Aseprite JSON for valid frame tags",
            ),
            ctx,
        )
        return None

    load_steps = 1 + len(all_sub_resources) + 1
    resource = GdResource(
        type="SpriteFrames", format=3,
        uid=uid_to_text(generate_uid()),
        load_steps=load_steps,
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
        click.echo(
            f"  Warning: {len(data['warnings'])} animation(s) skipped"
            " due to errors",
            err=True,
        )


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
@click.pass_context
def split(
    ctx: click.Context,
    image_file: str,
    frame_size: str | None,
    json_meta: str | None,
    output: str | None,
    res_path: str | None,
    fps: float,
) -> None:
    """Split a sprite sheet into frames and generate a SpriteFrames .tres."""
    image_path = Path(image_file)
    if not image_path.exists():
        emit_error(
            GdautoError(
                message=f"Image file not found: {image_file}",
                code="FILE_NOT_FOUND",
                fix="Check the file path and try again",
            ),
            ctx,
        )
        return

    if frame_size is None and json_meta is None:
        emit_error(
            GdautoError(
                message="Either --frame-size or --json-meta is required",
                code="SPRITE_SPLIT_NO_SIZE",
                fix="Provide --frame-size WxH or --json-meta file.json",
            ),
            ctx,
        )
        return

    output_path = Path(output) if output else image_path.with_suffix(".tres")
    image_res = res_path or f"res://{image_path.name}"

    try:
        resource = _do_split(image_path, frame_size, json_meta, image_res, fps)
    except (GdautoError, ValidationError) as exc:
        emit_error(exc, ctx)
        return

    serialize_tres_file(resource, output_path)

    def _human(data: dict, verbose: bool = False) -> None:  # type: ignore[type-arg]
        click.echo(
            f"Created {data['output']} with {data['frame_count']} frames"
        )

    emit(
        {
            "output": str(output_path),
            "frame_count": len(resource.sub_resources),
            "image": str(image_path),
        },
        _human,
        ctx,
    )


def _do_split(
    image_path: Path,
    frame_size: str | None,
    json_meta: str | None,
    image_res: str,
    fps: float,
) -> GdResource:  # type: ignore[return]
    """Dispatch to grid or JSON splitting based on provided options."""
    from gdauto.sprite.splitter import split_sheet_grid, split_sheet_json

    if frame_size is not None:
        frame_w, frame_h = _parse_frame_size(frame_size)
        return split_sheet_grid(image_path, frame_w, frame_h, image_res, fps)
    if json_meta is not None:
        json_path = Path(json_meta)
        if not json_path.exists():
            raise GdautoError(
                message=f"JSON metadata file not found: {json_meta}",
                code="FILE_NOT_FOUND",
                fix="Check the JSON file path and try again",
            )
        return split_sheet_json(image_path, json_path, image_res, fps)


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
    except ValueError:
        raise ValidationError(
            message=f"Invalid frame size values: {frame_size}",
            code="INVALID_FRAME_SIZE",
            fix="Width and height must be integers (e.g., 32x32)",
        )


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
            GdautoError(
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
        from gdauto.sprite.atlas import create_atlas

        atlas_img, resource = create_atlas(
            image_paths, atlas_res, power_of_two=not no_pot
        )
    except (GdautoError, ValidationError) as exc:
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
            GdautoError(
                message=f"File not found: {tres_file}",
                code="FILE_NOT_FOUND",
                fix="Check the path to your .tres file",
            ),
            ctx,
        )
        return

    from gdauto.sprite.validator import (
        validate_spriteframes,
        validate_spriteframes_headless,
    )

    result = validate_spriteframes(tres_path)

    if godot:
        from gdauto.backend import GodotBackend

        config = ctx.obj
        backend = GodotBackend(
            binary_path=config.godot_path if config else None
        )
        result = validate_spriteframes_headless(tres_path, backend)

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
