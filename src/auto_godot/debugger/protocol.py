"""Protocol message framing for Godot debugger wire format.

Godot's remote debugger protocol wraps commands in a 3-element Variant
Array: [command_name: str, thread_id: int, data: list]. Each message
is length-prefixed with a 4-byte little-endian uint32 giving the size
of the Variant-encoded payload.

Functions:
    encode_message: Build a framed wire message from command, data, thread_id.
    decode_message: Extract command, thread_id, data from a Variant payload.
    read_message: Async read a complete message from a StreamReader.
    write_message: Async write a framed message to a StreamWriter.
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

from auto_godot.debugger.errors import ProtocolError
from auto_godot.debugger.variant import decode, encode

if TYPE_CHECKING:
    import asyncio

# Maximum message payload size: 8 MiB.
# Messages exceeding this likely indicate protocol desynchronization.
MAX_MESSAGE_SIZE = 8_388_608


def encode_message(command: str, data: list, thread_id: int = 1) -> bytes:
    """Encode a debugger command as a length-prefixed wire message.

    Builds the 3-element array [command, thread_id, data], Variant-encodes
    it, and prepends a 4-byte little-endian length prefix.
    """
    payload = encode([command, thread_id, data])
    return struct.pack('<I', len(payload)) + payload


def decode_message(payload: bytes) -> tuple[str, int, list]:
    """Decode a Variant payload into (command, thread_id, data).

    The payload must NOT include the 4-byte length prefix; that should
    be stripped by the caller (read_message handles this automatically).

    Raises ProtocolError if the payload is not a valid 3-element array
    with [str, int, list] structure.
    """
    value, _ = decode(payload)
    if not isinstance(value, list) or len(value) != 3:
        raise ProtocolError(
            message="Invalid message: expected 3-element array "
                    f"[command, thread_id, data], got {type(value).__name__}"
                    + (f" with {len(value)} elements" if isinstance(value, list) else ""),
            code="PROTO_INVALID_MESSAGE",
            fix="Expected 3-element array [command: str, thread_id: int, data: list]",
        )
    command, tid, data = value[0], value[1], value[2]
    if not isinstance(command, str):
        raise ProtocolError(
            message=f"Invalid message: command must be str, got {type(command).__name__}",
            code="PROTO_INVALID_MESSAGE",
            fix="Expected 3-element array [command: str, thread_id: int, data: list]",
        )
    if not isinstance(tid, int):
        raise ProtocolError(
            message=f"Invalid message: thread_id must be int, got {type(tid).__name__}",
            code="PROTO_INVALID_MESSAGE",
            fix="Expected 3-element array [command: str, thread_id: int, data: list]",
        )
    if not isinstance(data, list):
        raise ProtocolError(
            message=f"Invalid message: data must be list, got {type(data).__name__}",
            code="PROTO_INVALID_MESSAGE",
            fix="Expected 3-element array [command: str, thread_id: int, data: list]",
        )
    return command, tid, data


async def read_message(reader: asyncio.StreamReader) -> tuple[str, int, list]:
    """Read a complete framed message from an async StreamReader.

    Reads the 4-byte length prefix, validates the size is within bounds,
    reads the payload, and decodes it.

    Raises ProtocolError if the message size exceeds 8 MiB (likely
    indicating protocol desynchronization).
    """
    size_data = await reader.readexactly(4)
    size = struct.unpack('<I', size_data)[0]
    if size > MAX_MESSAGE_SIZE:
        raise ProtocolError(
            message=f"Message size {size} exceeds maximum {MAX_MESSAGE_SIZE} bytes (8 MiB)",
            code="PROTO_MSG_TOO_LARGE",
            fix="This usually indicates a protocol synchronization error",
        )
    payload = await reader.readexactly(size)
    return decode_message(payload)


async def write_message(
    writer: asyncio.StreamWriter,
    command: str,
    data: list,
    thread_id: int = 1,
) -> None:
    """Write a framed message to an async StreamWriter.

    Encodes the message and drains the writer to ensure the data
    is flushed to the transport.
    """
    framed = encode_message(command, data, thread_id)
    writer.write(framed)
    await writer.drain()
