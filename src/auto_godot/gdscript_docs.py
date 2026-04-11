"""GDScript documentation extractor.

Regex-based declaration extraction from .gd files. Produces structured
dicts for JSON output and Markdown for human-readable docs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Regex patterns for GDScript declarations
_CLASS_NAME = re.compile(r"^class_name\s+(\w+)")
_EXTENDS = re.compile(r"^extends\s+(\w+)")
_SIGNAL = re.compile(r"^signal\s+(\w+)(?:\(([^)]*)\))?")
_CONST = re.compile(r"^const\s+(\w+)(?:\s*:\s*\w+)?\s*=\s*(.+)")
_EXPORT = re.compile(r"^@export(?:_\w+(?:\([^)]*\))?)?\s+var\s+(\w+)\s*(?::\s*([^=]+?))?\s*(?:=\s*(.+))?$")
_VAR = re.compile(r"^var\s+(\w+)\s*(?::\s*([^=]+?))?\s*(?:=\s*(.+))?$")
_FUNC = re.compile(r"^(static\s+)?func\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([\w\[\], ]+))?")
_ENUM_START = re.compile(r"^enum\s+(\w+)\s*\{(.*)")
_DOC_COMMENT = re.compile(r"^##\s?(.*)")


def _collect_doc(lines: list[str], end: int) -> str:
    """Collect consecutive ## lines above index end (exclusive)."""
    parts: list[str] = []
    i = end - 1
    while i >= 0:
        m = _DOC_COMMENT.match(lines[i].strip())
        if m:
            parts.append(m.group(1))
            i -= 1
        else:
            break
    parts.reverse()
    return "\n".join(parts).strip()


def _parse_enum_values(lines: list[str], start: int, initial: str) -> list[str]:
    """Parse enum values from braces, handling multi-line."""
    combined = initial
    i = start + 1
    while "}" not in combined and i < len(lines):
        combined += " " + lines[i].strip()
        i += 1
    body = combined.split("}", 1)[0]
    return [v.strip() for v in body.split(",") if v.strip()]


@dataclass
class ScriptDoc:
    """Documentation extracted from a single GDScript file."""
    path: str
    class_name: str | None = None
    extends: str | None = None
    description: str = ""
    signals: list[dict[str, Any]] = field(default_factory=list)
    constants: list[dict[str, Any]] = field(default_factory=list)
    enums: list[dict[str, Any]] = field(default_factory=list)
    exports: list[dict[str, Any]] = field(default_factory=list)
    variables: list[dict[str, Any]] = field(default_factory=list)
    functions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict, omitting empty sections."""
        result: dict[str, Any] = {"path": self.path}
        if self.class_name:
            result["class_name"] = self.class_name
        if self.extends:
            result["extends"] = self.extends
        if self.description:
            result["description"] = self.description
        for key in ("signals", "constants", "enums", "exports", "variables", "functions"):
            items = getattr(self, key)
            if items:
                result[key] = items
        return result


def _extract_file_description(lines: list[str]) -> str:
    """Extract ## doc comment block before class_name/extends."""
    file_doc: list[str] = []
    for line in lines:
        stripped = line.strip()
        m = _DOC_COMMENT.match(stripped)
        if m:
            file_doc.append(m.group(1))
        elif stripped == "":
            if file_doc:
                break
        else:
            break
    return "\n".join(file_doc).strip()


def _make_entry(name: str, lines: list[str], i: int, **extra: Any) -> dict[str, Any]:
    """Build a doc entry dict with optional doc comment."""
    entry: dict[str, Any] = {"name": name, "line": i + 1, **extra}
    comment = _collect_doc(lines, i)
    if comment:
        entry["doc"] = comment
    return entry


def _parse_declaration(doc: ScriptDoc, lines: list[str], i: int, s: str) -> None:
    """Try to match a single top-level declaration and append to doc."""
    if m := _CLASS_NAME.match(s):
        doc.class_name = m.group(1)
    elif m := _EXTENDS.match(s):
        doc.extends = m.group(1)
    elif m := _ENUM_START.match(s):
        vals = _parse_enum_values(lines, i, m.group(2))
        doc.enums.append(_make_entry(m.group(1), lines, i, values=vals))
    elif m := _SIGNAL.match(s):
        doc.signals.append(_make_entry(m.group(1), lines, i, signature=s))
    elif m := _CONST.match(s):
        doc.constants.append(_make_entry(m.group(1), lines, i, signature=s))
    elif m := _EXPORT.match(s):
        doc.exports.append(_make_entry(m.group(1), lines, i, signature=s))
    elif m := _VAR.match(s):
        doc.variables.append(_make_entry(m.group(1), lines, i, signature=s))
    elif m := _FUNC.match(s):
        extra: dict[str, Any] = {
            "params": m.group(3).strip(),
            "return_type": (m.group(4) or "void").strip(),
        }
        if m.group(1):
            extra["static"] = True
        doc.functions.append(_make_entry(m.group(2), lines, i, **extra))


def parse_gdscript(text: str, file_path: str = "") -> ScriptDoc:
    """Parse a GDScript file and extract documentation."""
    doc = ScriptDoc(path=file_path)
    lines = text.split("\n")
    doc.description = _extract_file_description(lines)
    for i, raw in enumerate(lines):
        if not raw[:1].isspace():
            _parse_declaration(doc, lines, i, raw.strip())
    return doc


def _md_header(sd: ScriptDoc) -> list[str]:
    """Render title, extends, and description."""
    p: list[str] = []
    title = sd.class_name or Path(sd.path).stem
    p.append(f"# {title}\n")
    if sd.extends:
        p.append(f"**Extends:** `{sd.extends}`\n")
    if sd.description:
        p.append(sd.description + "\n")
    return p


def _md_sections(sd: ScriptDoc) -> list[str]:
    """Render signals, enums, constants, exports, variables, functions."""
    p: list[str] = []
    if sd.signals:
        p.append("## Signals\n")
        for sig in sd.signals:
            p.append(f"### `{sig['signature']}`\n")
            if sig.get("doc"):
                p.append(sig["doc"] + "\n")
    if sd.enums:
        p.append("## Enums\n")
        for en in sd.enums:
            p.append(f"### {en['name']}\n")
            if en.get("doc"):
                p.append(en["doc"] + "\n")
            p.extend(f"- `{val}`" for val in en["values"])
            p.append("")
    if sd.constants:
        p.append("## Constants\n")
        for c in sd.constants:
            line = f"- `{c['signature']}`"
            if c.get("doc"):
                line += f"\n  {c['doc']}"
            p.append(line + "\n")
    if sd.exports:
        p.append("## Exported Properties\n")
        p.append("| Name | Declaration | Description |")
        p.append("|------|-------------|-------------|")
        for exp in sd.exports:
            doc_cell = exp.get("doc", "").replace("\n", " ")
            p.append(f"| {exp['name']} | `{exp['signature']}` | {doc_cell} |")
        p.append("")
    if sd.variables:
        p.append("## Variables\n")
        for v in sd.variables:
            line = f"- `{v['signature']}`"
            if v.get("doc"):
                line += f"\n  {v['doc']}"
            p.append(line + "\n")
    if sd.functions:
        p.append("## Functions\n")
        for fn in sd.functions:
            static = "static " if fn.get("static") else ""
            p.append(f"### `{static}func {fn['name']}({fn['params']}) -> {fn['return_type']}`\n")
            if fn.get("doc"):
                p.append(fn["doc"] + "\n")
    return p


def format_markdown(sd: ScriptDoc) -> str:
    """Format a ScriptDoc as Markdown."""
    parts = _md_header(sd) + _md_sections(sd)
    return "\n".join(parts).rstrip() + "\n"
