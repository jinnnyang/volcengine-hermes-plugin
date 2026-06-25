"""Binary protocol helpers for Volcengine Doubao ASR WebSocket messages."""
from __future__ import annotations

import gzip
import json
import struct
from typing import Any, Dict

PROTOCOL_VERSION = 0x1
HEADER_SIZE_WORDS = 0x1

MESSAGE_TYPE_FULL_CLIENT_REQUEST = 0x1
MESSAGE_TYPE_AUDIO_ONLY_REQUEST = 0x2
MESSAGE_TYPE_FULL_SERVER_RESPONSE = 0x9
MESSAGE_TYPE_SERVER_ACK = 0xB
MESSAGE_TYPE_ERROR_RESPONSE = 0xF

FLAG_NO_SEQUENCE = 0x0
FLAG_POS_SEQUENCE = 0x1
FLAG_NEG_SEQUENCE = 0x2
FLAG_NEG_WITH_SEQUENCE = 0x3

MESSAGE_SERIALIZATION_RAW = 0x0
MESSAGE_SERIALIZATION_JSON = 0x1
MESSAGE_COMPRESSION_NONE = 0x0
MESSAGE_COMPRESSION_GZIP = 0x1
RESERVED = 0x0


def _header(
    message_type: int,
    *,
    flags: int = FLAG_NO_SEQUENCE,
    serialization: int = MESSAGE_SERIALIZATION_JSON,
    compression: int = MESSAGE_COMPRESSION_GZIP,
) -> bytes:
    return bytes([
        (PROTOCOL_VERSION << 4) | HEADER_SIZE_WORDS,
        (message_type << 4) | flags,
        (serialization << 4) | compression,
        RESERVED,
    ])


def _json_loads(payload: bytes) -> Any:
    return json.loads(payload.decode("utf-8"))


def build_full_client_request(payload: Dict[str, Any], *, sequence: int = 1) -> bytes:
    """Build a gzip-compressed JSON full-client request frame with sequence."""
    raw_payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    compressed_payload = gzip.compress(raw_payload)
    return b"".join([
        _header(
            MESSAGE_TYPE_FULL_CLIENT_REQUEST,
            flags=FLAG_POS_SEQUENCE if sequence >= 0 else FLAG_NEG_WITH_SEQUENCE,
            serialization=MESSAGE_SERIALIZATION_JSON,
            compression=MESSAGE_COMPRESSION_GZIP,
        ),
        struct.pack(">i", sequence),
        struct.pack(">I", len(compressed_payload)),
        compressed_payload,
    ])


def build_audio_only_request(audio: bytes, *, sequence: int, final: bool = False, compress: bool = False) -> bytes:
    """Build an ASR audio-only request frame.

    Volcengine ASR V3 expects audio chunks wrapped in AUDIO_ONLY_REQUEST frames,
    not naked websocket binary payloads. The final empty audio frame carries a
    negative sequence number to mark end-of-audio.
    """
    payload = gzip.compress(audio) if compress and audio else audio
    final_sequence = -abs(sequence) if final else sequence
    return b"".join([
        _header(
            MESSAGE_TYPE_AUDIO_ONLY_REQUEST,
            flags=FLAG_NEG_WITH_SEQUENCE if final else FLAG_POS_SEQUENCE,
            serialization=MESSAGE_SERIALIZATION_RAW,
            compression=MESSAGE_COMPRESSION_GZIP if compress and audio else MESSAGE_COMPRESSION_NONE,
        ),
        struct.pack(">i", final_sequence),
        struct.pack(">I", len(payload)),
        payload,
    ])


def parse_server_response(message: bytes) -> Dict[str, Any]:
    """Parse a Volcengine ASR V3 server frame.

    Handles full server responses, server ACKs, error frames, sequence flags,
    gzip payloads, and last-package markers.
    """
    if len(message) < 4:
        raise ValueError("Volcengine ASR response is too short")

    header_size = message[0] & 0x0F
    header_bytes = header_size * 4
    if len(message) < header_bytes:
        raise ValueError("Volcengine ASR response has an invalid header")

    message_type = message[1] >> 4
    flags = message[1] & 0x0F
    serialization = message[2] >> 4
    compression = message[2] & 0x0F
    payload = message[header_bytes:]
    result: Dict[str, Any] = {"is_last_package": bool(flags & FLAG_NEG_SEQUENCE)}
    payload_message = None
    payload_size = 0

    if message_type == MESSAGE_TYPE_FULL_SERVER_RESPONSE:
        if flags & FLAG_POS_SEQUENCE:
            if len(payload) < 4:
                raise ValueError("Volcengine ASR response is missing sequence")
            sequence = struct.unpack(">i", payload[:4])[0]
            result["sequence"] = sequence
            if sequence < 0:
                result["is_last_package"] = True
            payload = payload[4:]
        if len(payload) < 4:
            raise ValueError("Volcengine ASR response is missing payload size")
        payload_size = struct.unpack(">i", payload[:4])[0]
        payload_message = payload[4:4 + abs(payload_size)]

    elif message_type == MESSAGE_TYPE_SERVER_ACK:
        if len(payload) < 4:
            return result
        sequence = struct.unpack(">i", payload[:4])[0]
        result["sequence"] = sequence
        if sequence < 0:
            result["is_last_package"] = True
        payload = payload[4:]
        if len(payload) >= 4:
            payload_size = struct.unpack(">I", payload[:4])[0]
            payload_message = payload[4:4 + payload_size]
        else:
            return result

    elif message_type == MESSAGE_TYPE_ERROR_RESPONSE:
        if len(payload) < 8:
            raise ValueError("Volcengine ASR error response is missing code or payload size")
        result["code"] = struct.unpack(">I", payload[:4])[0]
        payload_size = struct.unpack(">I", payload[4:8])[0]
        payload_message = payload[8:8 + payload_size]

    else:
        raise ValueError(f"Unsupported Volcengine ASR message type: {message_type}")

    if payload_message is None:
        return result
    if compression == MESSAGE_COMPRESSION_GZIP:
        payload_message = gzip.decompress(payload_message)
    if serialization == MESSAGE_SERIALIZATION_JSON:
        payload_message = _json_loads(payload_message)
    elif serialization != MESSAGE_SERIALIZATION_RAW:
        payload_message = str(payload_message)

    result["message"] = payload_message
    result["size"] = payload_size
    return result
