"""Manage Godot translation/localization CSV files."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

import rich_click as click

from auto_godot.errors import ProjectError
from auto_godot.output import emit, emit_error


@click.group(invoke_without_command=True)
@click.pass_context
def locale(ctx: click.Context) -> None:
    """Manage Godot localization and translation files."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a translation CSV, returning (headers, rows as dicts)."""
    text = path.read_text(encoding="utf-8")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    rows = list(reader)
    return list(headers), rows


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    """Write translation CSV with consistent formatting."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


@locale.command("create")
@click.argument("csv_file", type=click.Path())
@click.option(
    "--default", "default_locale", default="en",
    help="Default locale column. Default: en.",
)
@click.pass_context
def create(ctx: click.Context, csv_file: str, default_locale: str) -> None:
    """Create a translation CSV with a default locale column.

    Examples:

      auto-godot locale create translations.csv

      auto-godot locale create translations.csv --default ja
    """
    try:
        path = Path(csv_file)
        if path.exists():
            raise ProjectError(
                message=f"File already exists: {csv_file}",
                code="FILE_EXISTS",
                fix="Choose a different filename or delete the existing file",
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_csv(path, ["keys", default_locale], [])
        data = {"created": True, "path": csv_file, "locale": default_locale}

        def _human(d: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Created {d['path']} with default locale '{d['locale']}'")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


@locale.command("add-locale")
@click.argument("csv_file", type=click.Path(exists=True))
@click.argument("locale_code")
@click.pass_context
def add_locale(ctx: click.Context, csv_file: str, locale_code: str) -> None:
    """Add a locale column to a translation CSV.

    Examples:

      auto-godot locale add-locale translations.csv es

      auto-godot locale add-locale translations.csv ja
    """
    try:
        path = Path(csv_file)
        headers, rows = _read_csv(path)
        if locale_code in headers:
            raise ProjectError(
                message=f"Locale '{locale_code}' already exists in {csv_file}",
                code="LOCALE_EXISTS",
                fix="Choose a different locale code",
            )
        headers.append(locale_code)
        for row in rows:
            row[locale_code] = ""
        _write_csv(path, headers, rows)
        data = {"added": True, "locale": locale_code, "file": csv_file}

        def _human(d: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Added locale '{d['locale']}' to {d['file']}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


@locale.command("add-key")
@click.argument("csv_file", type=click.Path(exists=True))
@click.argument("key")
@click.option(
    "--value", "values", multiple=True,
    help="Locale=value pairs. E.g., --value en=Start --value es=Iniciar.",
)
@click.pass_context
def add_key(
    ctx: click.Context, csv_file: str, key: str, values: tuple[str, ...]
) -> None:
    """Add a translation key with optional locale values.

    Examples:

      auto-godot locale add-key translations.csv MENU_START --value "en=Start Game" --value "es=Iniciar Juego"

      auto-godot locale add-key translations.csv MENU_QUIT --value "en=Quit"
    """
    try:
        path = Path(csv_file)
        headers, rows = _read_csv(path)

        # Check for duplicate key
        existing_keys = {row.get("keys", "") for row in rows}
        if key in existing_keys:
            raise ProjectError(
                message=f"Key '{key}' already exists in {csv_file}",
                code="KEY_EXISTS",
                fix="Choose a different key name or edit the existing one",
            )

        new_row: dict[str, str] = {"keys": key}
        for h in headers:
            if h != "keys":
                new_row[h] = ""

        # Parse locale=value pairs
        for val_str in values:
            if "=" not in val_str:
                raise ProjectError(
                    message=f"Invalid value format: '{val_str}'",
                    code="INVALID_VALUE",
                    fix="Use locale=value format, e.g., --value en=Start",
                )
            loc, text = val_str.split("=", 1)
            if loc not in headers:
                raise ProjectError(
                    message=f"Locale '{loc}' not in CSV. Available: {headers[1:]}",
                    code="LOCALE_NOT_FOUND",
                    fix=f"Add the locale first: auto-godot locale add-locale {csv_file} {loc}",
                )
            new_row[loc] = text

        rows.append(new_row)
        _write_csv(path, headers, rows)

        data = {"added": True, "key": key, "file": csv_file}

        def _human(d: dict[str, Any], verbose: bool = False) -> None:
            click.echo(f"Added key '{d['key']}' to {d['file']}")

        emit(data, _human, ctx)
    except ProjectError as exc:
        emit_error(exc, ctx)


@locale.command("list-keys")
@click.argument("csv_file", type=click.Path(exists=True))
@click.pass_context
def list_keys(ctx: click.Context, csv_file: str) -> None:
    """List all translation keys in a CSV file.

    Examples:

      auto-godot locale list-keys translations.csv

      auto-godot --json locale list-keys translations.csv
    """
    path = Path(csv_file)
    headers, rows = _read_csv(path)
    keys = [row.get("keys", "") for row in rows]
    data = {"keys": keys, "count": len(keys), "file": csv_file}

    def _human(d: dict[str, Any], verbose: bool = False) -> None:
        click.echo(f"Keys in {d['file']} ({d['count']}):")
        for k in d["keys"]:
            click.echo(f"  {k}")

    emit(data, _human, ctx)


@locale.command("list-locales")
@click.argument("csv_file", type=click.Path(exists=True))
@click.pass_context
def list_locales(ctx: click.Context, csv_file: str) -> None:
    """List all locale columns in a translation CSV.

    Examples:

      auto-godot locale list-locales translations.csv
    """
    path = Path(csv_file)
    headers, _rows = _read_csv(path)
    locales = [h for h in headers if h != "keys"]
    data = {"locales": locales, "count": len(locales), "file": csv_file}

    def _human(d: dict[str, Any], verbose: bool = False) -> None:
        click.echo(f"Locales in {d['file']} ({d['count']}):")
        for loc in d["locales"]:
            click.echo(f"  {loc}")

    emit(data, _human, ctx)


@locale.command("audit")
@click.argument("csv_file", type=click.Path(exists=True))
@click.pass_context
def audit(ctx: click.Context, csv_file: str) -> None:
    """Find missing translations (keys with empty values for any locale).

    Examples:

      auto-godot locale audit translations.csv

      auto-godot --json locale audit translations.csv
    """
    path = Path(csv_file)
    headers, rows = _read_csv(path)
    locales = [h for h in headers if h != "keys"]

    missing: list[dict[str, str]] = []
    for row in rows:
        key = row.get("keys", "")
        for loc in locales:
            val = row.get(loc, "").strip()
            if not val:
                missing.append({"key": key, "locale": loc})

    data = {
        "file": csv_file,
        "total_keys": len(rows),
        "total_locales": len(locales),
        "missing": missing,
        "missing_count": len(missing),
        "complete": len(missing) == 0,
    }

    def _human(d: dict[str, Any], verbose: bool = False) -> None:
        click.echo(f"Audit: {d['file']}")
        click.echo(f"  Keys: {d['total_keys']}, Locales: {d['total_locales']}")
        if d["complete"]:
            click.echo("  All translations complete.")
        else:
            click.echo(f"  Missing translations: {d['missing_count']}")
            for m in d["missing"]:
                click.echo(f"    {m['key']} [{m['locale']}]")

    emit(data, _human, ctx)
    if not data["complete"]:
        ctx.exit(1)


@locale.command("extract")
@click.argument("project_path", default=".", type=click.Path(exists=True))
@click.option(
    "-o", "--output", type=click.Path(),
    help="Write extracted keys to a CSV file.",
)
@click.pass_context
def extract(ctx: click.Context, project_path: str, output: str | None) -> None:
    """Extract translatable strings from GDScript tr() calls.

    Scans .gd files for tr("KEY") patterns and reports all translation
    keys used in the project.

    Examples:

      auto-godot locale extract /path/to/project

      auto-godot locale extract . --output keys.csv
    """
    root = Path(project_path)
    tr_pattern = re.compile(r'\btr\(\s*"([^"]+)"\s*\)')
    found_keys: dict[str, list[str]] = {}  # key -> [file paths]

    for gd_file in root.rglob("*.gd"):
        if ".godot" in gd_file.parts or ".import" in gd_file.parts:
            continue
        try:
            text = gd_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in tr_pattern.finditer(text):
            key = match.group(1)
            rel = str(gd_file.relative_to(root))
            found_keys.setdefault(key, []).append(rel)

    data: dict[str, Any] = {
        "keys": sorted(found_keys.keys()),
        "count": len(found_keys),
        "sources": {k: v for k, v in sorted(found_keys.items())},
    }

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_csv(out_path, ["keys", "en"], [{"keys": k, "en": ""} for k in sorted(found_keys)])
        data["output_file"] = output

    def _human(d: dict[str, Any], verbose: bool = False) -> None:
        click.echo(f"Found {d['count']} translatable key(s):")
        for k in d["keys"]:
            sources = d["sources"][k]
            click.echo(f"  {k} (in {', '.join(sources)})")
        if "output_file" in d:
            click.echo(f"\nWrote keys to {d['output_file']}")

    emit(data, _human, ctx)
