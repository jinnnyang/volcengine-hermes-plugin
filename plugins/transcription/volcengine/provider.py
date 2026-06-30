"""Volcengine Doubao Seed ASR backend for Hermes transcription."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import shutil
import subprocess
import tempfile
import uuid
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # Hermes runtime
    from agent.transcription_provider import TranscriptionProvider
except ModuleNotFoundError:  # Local plugin tests outside Hermes source tree
    class TranscriptionProvider:  # type: ignore[no-redef]
        @property
        def name(self) -> str:
            raise NotImplementedError

        @property
        def display_name(self) -> str:
            return self.name

        def is_available(self) -> bool:
            return True

        def list_models(self) -> List[Dict[str, Any]]:
            return []

        def default_model(self) -> Optional[str]:
            models = self.list_models()
            return models[0].get("id") if models else None

        def get_setup_schema(self) -> Dict[str, Any]:
            return {"name": self.display_name, "badge": "", "tag": "", "env_vars": []}

try:
    from plugins._volcengine_common.config import resolve_volcengine_api_key
except ModuleNotFoundError:  # pragma: no cover - local file-loading fallback
    import importlib.util as _importlib_util

    config_path = Path(__file__).resolve().parents[2] / "_volcengine_common" / "config.py"
    spec = _importlib_util.spec_from_file_location("volcengine_common_config", config_path)
    config_module = _importlib_util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(config_module)
    resolve_volcengine_api_key = config_module.resolve_volcengine_api_key

try:
    from plugins.transcription.volcengine.protocol import (
        build_audio_only_request,
        build_full_client_request,
        parse_server_response,
    )
except ModuleNotFoundError:  # pragma: no cover - local file-loading fallback
    import importlib.util as _importlib_util

    protocol_path = Path(__file__).with_name("protocol.py")
    spec = _importlib_util.spec_from_file_location("volcengine_transcription_protocol", protocol_path)
    protocol_module = _importlib_util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(protocol_module)
    build_audio_only_request = protocol_module.build_audio_only_request
    build_full_client_request = protocol_module.build_full_client_request
    parse_server_response = protocol_module.parse_server_response


DEFAULT_MODEL = "doubao-seed-asr-2.0"
DEFAULT_RESOURCE_ID = "volc.seedasr.sauc.duration"
ASR_ASYNC_ENDPOINT = "wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_async"
ASR_NOSTREAM_ENDPOINT = "wss://openspeech.bytedance.com/api/v3/plan/sauc/bigmodel_nostream"
# Hermes currently hands transcription providers a completed audio file, so the
# accuracy-prioritised single-stream endpoint is the default. The async endpoint
# is kept as a named constant for future realtime streaming support.
ASR_ENDPOINT = ASR_NOSTREAM_ENDPOINT
DEFAULT_CHUNK_SIZE = 3200


class VolcengineTranscriptionProvider(TranscriptionProvider):
    """Transcription provider backed by Volcengine Doubao ASR."""

    @property
    def name(self) -> str:
        return "volcengine"

    @property
    def display_name(self) -> str:
        return "Volcengine Doubao ASR"

    def is_available(self) -> bool:
        return bool(resolve_volcengine_api_key()) and importlib.util.find_spec("websockets") is not None

    def list_models(self) -> List[Dict[str, Any]]:
        return [{"id": DEFAULT_MODEL, "display": "Doubao Seed ASR 2.0"}]

    def default_model(self) -> str:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Volcengine Doubao ASR",
            "badge": "paid",
            "tag": "Doubao Seed ASR 2.0 via Volcengine OpenSpeech",
            "env_vars": [
                {
                    "key": "VOLCENGINE_API_KEY",
                    "prompt": "Volcengine API Key (shared for all services)",
                    "url": "https://console.volcengine.com/ark/region:ark+cn-beijing/apikey",
                }
            ],
        }

    def _build_headers(self, *, resource_id: str = DEFAULT_RESOURCE_ID) -> Dict[str, str]:
        api_key = resolve_volcengine_api_key()
        request_id = str(uuid.uuid4())
        connect_id = str(uuid.uuid4())
        return {
            "X-Api-Key": api_key,
            "X-Api-Resource-Id": resource_id,
            "X-Api-Request-Id": request_id,
            "X-Api-Connect-Id": connect_id,
            "X-Api-Sequence": "-1",
        }

    def _prepare_audio(self, file_path: str, *, output_path: Optional[str] = None) -> str:
        path = Path(file_path)
        if path.suffix.lower() == ".wav" and self._is_target_wav(path):
            return str(path)

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg is required to convert audio to mono pcm_s16le 16000Hz WAV")

        target = output_path or str(Path(tempfile.mkdtemp(prefix="volcengine-asr-")) / "input.wav")
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            target,
        ]
        subprocess.run(command, check=True, capture_output=True)
        return target

    def _is_target_wav(self, path: Path) -> bool:
        try:
            with wave.open(str(path), "rb") as wav:
                return wav.getnchannels() == 1 and wav.getframerate() == 16000 and wav.getsampwidth() == 2
        except (wave.Error, EOFError):
            return path.suffix.lower() == ".wav"

    def transcribe(
        self,
        file_path: str,
        *,
        model: Optional[str] = None,
        language: Optional[str] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        try:
            if not resolve_volcengine_api_key():
                raise RuntimeError(
                    "Missing Volcengine API key. Set VOLCENGINE_API_KEY or ARK_API_KEY."
                )
            if importlib.util.find_spec("websockets") is None:
                raise RuntimeError("Python package 'websockets' is required for Volcengine ASR")

            normalized_language = None if language in (None, "", "auto") else language
            prepared_audio = self._prepare_audio(file_path)
            transcript = asyncio.run(
                self._run_asr_websocket(
                    prepared_audio,
                    headers=self._build_headers(resource_id=str(extra.get("resource_id") or DEFAULT_RESOURCE_ID)),
                    model=model or self.default_model(),
                    language=normalized_language,
                    endpoint=str(extra.get("endpoint") or ASR_ENDPOINT),
                    chunk_size=int(extra.get("chunk_size") or DEFAULT_CHUNK_SIZE),
                )
            )
            return {"success": True, "transcript": transcript, "provider": self.name}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "transcript": "", "error": str(exc), "provider": self.name}

    async def _run_asr_websocket(
        self,
        file_path: str,
        *,
        headers: Dict[str, str],
        model: str,
        language: Optional[str],
        endpoint: str,
        chunk_size: int,
    ) -> str:
        import websockets

        request: Dict[str, Any] = {
            "user": {"uid": "hermes"},
            "audio": {"format": "wav", "codec": "raw", "rate": 16000, "bits": 16, "channel": 1},
            "request": {"model_name": "bigmodel", "enable_itn": True, "enable_punc": True, "result_type": "full"},
        }
        if language:
            request["audio"]["language"] = language

        transcript = ""
        last_response: Dict[str, Any] = {}
        async with websockets.connect(endpoint, additional_headers=headers) as websocket:
            sequence = 1
            await websocket.send(build_full_client_request(request, sequence=sequence))
            with open(file_path, "rb") as audio_file:
                while True:
                    chunk = audio_file.read(chunk_size)
                    if not chunk:
                        break
                    sequence += 1
                    await websocket.send(build_audio_only_request(chunk, sequence=sequence))
            sequence += 1
            await websocket.send(build_audio_only_request(b"", sequence=sequence, final=True))

            while True:
                response = parse_server_response(await websocket.recv())
                last_response = response
                if response.get("code") and int(response["code"]) != 0:
                    message = response.get("message") or {}
                    raise RuntimeError(
                        f"ASR API Error [{response.get('code')}]: {message}; "
                        f"request_id={headers.get('X-Api-Request-Id')}"
                    )
                candidate = _extract_transcript(response)
                if candidate:
                    transcript = candidate
                if response.get("is_last_package"):
                    break

        if not transcript:
            transcript = _extract_transcript(last_response)
        return transcript


def _extract_transcript(response: Dict[str, Any]) -> str:
    message = response.get("message") if isinstance(response, dict) else None
    if isinstance(message, dict):
        text = _extract_transcript(message)
        if text:
            return text

    result = response.get("result") or response.get("Result") or response
    if isinstance(result, list):
        return "".join(_extract_transcript(item) for item in result if isinstance(item, dict))
    if isinstance(result, dict):
        for key in ("text", "Text", "transcript", "Transcript"):
            value = result.get(key)
            if value:
                return str(value)
        utterances = result.get("utterances") or result.get("Utterances")
        if isinstance(utterances, list):
            return "".join(str(item.get("text") or item.get("Text") or "") for item in utterances if isinstance(item, dict))
    return ""
