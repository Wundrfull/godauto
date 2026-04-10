"""Unit tests for debugger protocol message framing.

Tests encode_message, decode_message, read_message, and write_message
for correct wire format, round-trip fidelity, validation, and size limits.
"""

from __future__ import annotations

import asyncio
import struct

import pytest

from auto_godot.debugger.errors import ProtocolError
from auto_godot.debugger.protocol import (
    MAX_MESSAGE_SIZE,
    decode_message,
    encode_message,
    read_message,
    write_message,
)
from auto_godot.debugger.variant import decode, encode


class TestEncodeMessage:
    """Tests for encode_message wire format."""

    def test_encode_message_structure(self) -> None:
        """Encoded message starts with 4-byte LE length prefix."""
        result = encode_message("test", [])
        assert len(result) > 4
        length_prefix = struct.unpack('<I', result[:4])[0]
        assert length_prefix == len(result) - 4

    def test_encode_message_contains_command(self) -> None:
        """Decoded payload first element is the command string."""
        result = encode_message("test", [])
        payload = result[4:]
        value, _ = decode(payload)
        assert isinstance(value, list)
        assert value[0] == "test"

    def test_encode_message_contains_thread_id_default(self) -> None:
        """Default thread_id is 1."""
        result = encode_message("cmd", [])
        payload = result[4:]
        value, _ = decode(payload)
        assert value[1] == 1

    def test_encode_message_contains_thread_id_custom(self) -> None:
        """Custom thread_id appears in decoded array."""
        result = encode_message("cmd", [], thread_id=42)
        payload = result[4:]
        value, _ = decode(payload)
        assert value[1] == 42

    def test_encode_message_contains_data(self) -> None:
        """Data list appears as third element in decoded array."""
        result = encode_message("cmd", [1, "hello"])
        payload = result[4:]
        value, _ = decode(payload)
        assert value[2] == [1, "hello"]

    def test_encode_message_empty_data(self) -> None:
        """Empty data list encodes correctly."""
        result = encode_message("cmd", [])
        payload = result[4:]
        value, _ = decode(payload)
        assert value[2] == []


class TestDecodeMessage:
    """Tests for decode_message validation and extraction."""

    def test_decode_message_round_trip(self) -> None:
        """Round-trip: encode then decode produces original values."""
        encoded = encode_message("cmd", ["arg1", 42])
        payload = encoded[4:]  # strip length prefix
        command, tid, data = decode_message(payload)
        assert command == "cmd"
        assert tid == 1
        assert data == ["arg1", 42]

    def test_decode_message_with_custom_thread_id(self) -> None:
        """Round-trip preserves custom thread_id."""
        encoded = encode_message("run", [True], thread_id=99)
        command, tid, data = decode_message(encoded[4:])
        assert command == "run"
        assert tid == 99
        assert data == [True]

    def test_decode_message_invalid_element_count_two(self) -> None:
        """Two-element array raises ProtocolError."""
        payload = encode(["cmd", 1])  # only 2 elements, no data list
        with pytest.raises(ProtocolError, match="3-element array"):
            decode_message(payload)

    def test_decode_message_invalid_element_count_four(self) -> None:
        """Four-element array raises ProtocolError."""
        payload = encode(["cmd", 1, [], "extra"])
        with pytest.raises(ProtocolError, match="3-element array"):
            decode_message(payload)

    def test_decode_message_not_an_array(self) -> None:
        """Non-array payload raises ProtocolError."""
        payload = encode("just a string")
        with pytest.raises(ProtocolError, match="3-element array"):
            decode_message(payload)

    def test_decode_message_invalid_command_type(self) -> None:
        """Non-string command raises ProtocolError."""
        payload = encode([42, 1, []])
        with pytest.raises(ProtocolError, match="command must be str"):
            decode_message(payload)

    def test_decode_message_invalid_thread_id_type(self) -> None:
        """Non-int thread_id raises ProtocolError."""
        payload = encode(["cmd", "not_int", []])
        with pytest.raises(ProtocolError, match="thread_id must be int"):
            decode_message(payload)

    def test_decode_message_invalid_data_type(self) -> None:
        """Non-list data raises ProtocolError."""
        payload = encode(["cmd", 1, "not_list"])
        with pytest.raises(ProtocolError, match="data must be list"):
            decode_message(payload)


class TestReadMessage:
    """Tests for async read_message from StreamReader."""

    @pytest.mark.asyncio
    async def test_read_message_happy_path(self) -> None:
        """Valid encoded message is read and decoded correctly."""
        framed = encode_message("test_cmd", [1, 2, 3], thread_id=5)
        reader = asyncio.StreamReader()
        reader.feed_data(framed)
        command, tid, data = await read_message(reader)
        assert command == "test_cmd"
        assert tid == 5
        assert data == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_read_message_size_limit(self) -> None:
        """Message exceeding 8 MiB limit raises ProtocolError."""
        # Feed a length prefix claiming 9,000,000 bytes
        oversized_prefix = struct.pack('<I', 9_000_000)
        reader = asyncio.StreamReader()
        reader.feed_data(oversized_prefix)
        with pytest.raises(ProtocolError, match="exceeds maximum") as exc_info:
            await read_message(reader)
        assert exc_info.value.code == "PROTO_MSG_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_read_message_exactly_at_limit(self) -> None:
        """Message at exactly 8 MiB limit raises ProtocolError (> check)."""
        # 8 MiB + 1 byte should fail
        oversized_prefix = struct.pack('<I', MAX_MESSAGE_SIZE + 1)
        reader = asyncio.StreamReader()
        reader.feed_data(oversized_prefix)
        with pytest.raises(ProtocolError):
            await read_message(reader)

    @pytest.mark.asyncio
    async def test_read_message_multiple_messages(self) -> None:
        """Multiple messages can be read sequentially from the same reader."""
        msg1 = encode_message("first", ["a"])
        msg2 = encode_message("second", ["b"])
        reader = asyncio.StreamReader()
        reader.feed_data(msg1 + msg2)

        cmd1, _, data1 = await read_message(reader)
        cmd2, _, data2 = await read_message(reader)
        assert cmd1 == "first" and data1 == ["a"]
        assert cmd2 == "second" and data2 == ["b"]


class TestWriteMessage:
    """Tests for async write_message to StreamWriter."""

    @pytest.mark.asyncio
    async def test_write_message(self) -> None:
        """Written bytes match encode_message output."""
        # Create a mock writer that captures written bytes
        written_chunks: list[bytes] = []

        class MockTransport:
            def get_extra_info(self, name: str, default: object = None) -> object:
                return default

        class MockWriter:
            def write(self, data: bytes) -> None:
                written_chunks.append(data)

            async def drain(self) -> None:
                pass

        writer = MockWriter()  # type: ignore[assignment]
        await write_message(writer, "test", [1, 2], thread_id=3)  # type: ignore[arg-type]

        written = b"".join(written_chunks)
        expected = encode_message("test", [1, 2], thread_id=3)
        assert written == expected
