"""Sprite sheet and SpriteFrames tools."""

from __future__ import annotations

from pathlib import Path

import rich_click as click

from gdauto.errors import GdautoError, ValidationError
from gdauto.formats.tres import serialize_tres_file
from gdauto.output import emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def sprite(ctx: click.Context) -> None:
    """Sprite sheet and SpriteFrames tools."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


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
