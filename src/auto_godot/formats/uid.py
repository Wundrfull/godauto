"""UID generation, encoding/decoding, .uid file I/O, and resource ID generation.

Implements Godot's base-34 UID encoding (characters a-y, 0-8; never z or 9)
and the Type_xxxxx resource ID format with 5-character random suffix.

Per FMT-05 and the UID algorithm from Godot's resource_uid.cpp source.
"""

from __future__ import annotations

import secrets
from pathlib import Path

# Base-34 character set: a-y (25) + 0-8 (9) = 34 total.
# Godot's off-by-one bug means 'z' and '9' are never used.
CHARS = "abcdefghijklmnopqrstuvwxy012345678"
BASE = len(CHARS)  # 34
MAX_UID = (1 << 63) - 1  # 63-bit maximum

# Characters used for resource ID suffixes (Type_xxxxx format)
RESOURCE_ID_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
RESOURCE_ID_LENGTH = 5


def generate_uid() -> int:
    """Generate a random 63-bit UID matching Godot's format."""
    return secrets.randbelow(MAX_UID + 1)


def uid_to_text(uid: int) -> str:
    """Convert numeric UID to uid:// text format.

    Prepends each digit (LSB computed first, placed at right), matching
    Godot's id_to_text algorithm where the result string is built by
    prepending characters. Returns "uid://<invalid>" for negative values.
    """
    if uid < 0:
        return "uid://<invalid>"
    result = ""
    value = uid
    while True:
        result = CHARS[value % BASE] + result  # prepend, not append
        value //= BASE
        if value == 0:
            break
    return "uid://" + result


def text_to_uid(text: str) -> int:
    """Convert uid:// text to numeric UID.

    Returns -1 on invalid input (wrong prefix, invalid characters).
    Decodes most-significant digit first (reverses encoding order).
    """
    if not text.startswith("uid://"):
        return -1
    encoded = text[6:]
    if encoded == "<invalid>":
        return -1
    if not encoded:
        return 0
    uid = 0
    for char in encoded:
        uid *= BASE
        if "a" <= char <= "y":
            uid += ord(char) - ord("a")
        elif "0" <= char <= "8":
            uid += ord(char) - ord("0") + 25
        else:
            return -1
    return uid & MAX_UID


def generate_resource_id(type_name: str) -> str:
    """Generate a resource ID in the Type_xxxxx format.

    Uses 5 random characters from the alphanumeric + underscore set,
    matching Godot's generate_scene_unique_id() algorithm.
    """
    suffix = "".join(secrets.choice(RESOURCE_ID_CHARS) for _ in range(RESOURCE_ID_LENGTH))
    return f"{type_name}_{suffix}"


def write_uid_file(path: Path, uid_text: str) -> None:
    """Write a .uid companion file next to the given resource path."""
    uid_path = Path(str(path) + ".uid")
    uid_path.write_text(uid_text + "\n")


def read_uid_file(path: Path) -> str | None:
    """Read a .uid companion file. Returns None if not found."""
    uid_path = Path(str(path) + ".uid")
    if uid_path.exists():
        return uid_path.read_text().strip()
    return None
